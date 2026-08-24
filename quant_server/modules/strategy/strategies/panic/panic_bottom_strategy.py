# -*- coding: utf-8 -*-
"""
恐慌抄底策略（事件型卫星 · 阶段 4b）
====================================================================================
定位：卫星池事件型子仓，博单次进攻倍数（1.3x-10x），平时闲置。
依据：`docs/00-核心策略体系/策略设计.md` §二 + `恐慌抄底反例统计报告.md`（M2 修订口径）

事件驱动状态机（跨日，显式状态变量）：
  idle      → [T日: panic≥阈值 + 条件B（年线门已关，2026-08 口径核对）]  → t1
  t1        → [T+1: panic 未再创新高 + 真恐慌确认（panic<水位 或 300收阳）]  → buy_wait
  buy_wait  → [T+1+3=T+4] 选股（超跌+质量分 TopN 等权）→ 买入信号  → holding
  holding   → 阶梯止盈(15/30/50%) / 单票止损(-15%) / 20交易日时间兜底

数据（load_live_state 预加载 + on_bar 增量缓存）：
  panic_index（恐慌指数，DB）｜ index_daily（沪深300/CSI500）｜ stock_daily（候选池）
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from core.engines.types.entities import BarData
from modules.strategy.constants import SignalType, SignalDirection
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class PanicBottomStrategy(BaseStrategy):
	"""恐慌抄底 — 事件驱动状态机策略"""

	DEFAULT_PARAMS: Dict[str, Any] = {
		# ── 触发（M2 反例统计修订口径） ──
		"panic_threshold": 3.0,             # 条件A：恐慌指数 ≥ 3.0（M2 实证最佳工作点）
		"use_annual_gate": False,           # 年线门（2026-08 关闭）：CSI500<MA250→熊市放弃。
		                                    # 口径核对结论：反例统计 15 次信号实为无年线门口径，
		                                    # 阈值3.0 下开启年线门 → 2019-2025 全区间 0 触发（实证）。
		                                    # 年线门为阈值2.0 噪音场景设计，3.0 下关闭恢复 18 触发日
		"cond_b_below_ma250_pct": 0.05,     # 条件B：沪深300 收盘 < MA250×(1-5%)（2026-08 回退：放宽致假信号轮 2022-03-23 -14.6%）
		"cond_b_low60_pct": 0.03,           # 条件B：沪深300 距 60 日前低 < -3%（2026-08 回退：放宽致候选仅1-2只的假信号轮，净负面）
		"cond_b_ret5_pct": 0.08,            # 条件B：沪深300 近 5 日跌幅 > 8%
		"confirm_window_days": 5,           # [废弃 2026-08] 确认窗口压缩到 T+1，此参数不再使用
		"confirm_panic_level": 1.5,         # 确认：恐慌指数回落 < 1.5
		"buy_delay_days": 3,                # T+1 确认后第 3 交易日买入（触发后 T+4，贴近 V 型底）
		# ── 选股（T+7 候选池） ──
		"candidate_drop_pct": 0.15,         # 超跌筛选：近 5 日跌幅 > 15%（恐慌急跌）
		"candidate_drawdown_pct": 0.25,     # [2026-08 回退] 距 60 日高点回撤超跌（方向3验证失败：选入质量差标的胜率暴跌；仅保留日志计算）
		"min_amount_wan": 500,              # 流动性下限：近 20 日均成交额 ≥ 500 万元
		"max_holdings": 10,                 # 持仓上限（分散 10 只；2026-08 集中 6×15% 被证伪回退——超跌股方差大不宜集中）
		"max_single_weight": 0.10,          # 单票仓位 ≤ 10%（分散控风险）
		"min_candidates": 0,                # 候选不足放弃阈值（0=禁用；2026-08 验证：放弃小轮致时序变化丢失 2024-02 大轮，回退）
		# ── 错杀弹性（2026-08 方向A v2：选恐慌前强势被错杀的优质股，反弹弹性更大） ──
		"overshoot_floor": 0.05,            # 恐慌前第10~20日相对强度(股票-沪深300) ≥5% 视为前期强势被错杀
		"overshoot_boost": 0.30,            # 优质股(质量分>1)+恐慌前强势被错杀 → 质量分 ×1.3
		# ── 止盈止损（严格执行，不设止损不上线） ──
		"max_holding_days": 40,             # 时间兜底：持仓满 40 交易日清仓（最后保险）
		# ── 止盈止损（2026-08 调整：固定止盈 20/40/60 + ATR 移动兜底 + ATR 硬止损） ──
		"tp1": 0.20,                        # 阶梯止盈档1：浮盈 20% → 卖 1/3（恐慌反弹普遍 20%+）
		"tp2": 0.40,                        # 阶梯止盈档2：浮盈 40% → 卖 1/3
		"tp3": 0.60,                        # 阶梯止盈档3：浮盈 60% → 清仓
		"atr_window": 14,                   # ATR 计算窗口（恐慌后 14 日波动）
		"trail_mult": 1.5,                  # 标准 ATR 移动兜底倍数（从最高点回撤 1.5×ATR 清仓）
		"stop_mult": 2.5,                   # ATR 硬止损：入场价 - 2.5×ATR
		"stop_loss_pct": 0.15,              # 开仓信号止损价估算占位（实际止损由 ATR 动态执行，audit 每笔开仓须带止损价）
		# ── 数据 ──
		"hs300_code": "000300.SH",          # 沪深300（条件B/确认收阳）
		"csi500_code": "000905.SH",         # CSI500（年线门）
		"lookback_days": 260,               # 指标回看（MA250 年线）
	}

	# 回测预加载标记：load_live_state 为纯市场数据预加载（无实盘持仓恢复），回测可安全调用
	BACKTEST_PRELOAD_STATE = True

	def __init__(self, name: str, strategy_type=None, parameters: Optional[Dict[str, Any]] = None):
		super().__init__(name=name, strategy_type=strategy_type, parameters=parameters)
		merged = dict(self.DEFAULT_PARAMS)
		if parameters:
			merged.update(parameters)
		self.parameters = merged

		# 参数展开（集中管理，避免散落魔术数字）
		self.panic_threshold = float(merged["panic_threshold"])
		self.use_annual_gate = bool(merged["use_annual_gate"])
		self.cond_b_below_ma250_pct = float(merged["cond_b_below_ma250_pct"])
		self.cond_b_low60_pct = float(merged["cond_b_low60_pct"])
		self.cond_b_ret5_pct = float(merged["cond_b_ret5_pct"])
		self.confirm_window_days = int(merged["confirm_window_days"])
		self.confirm_panic_level = float(merged["confirm_panic_level"])
		self.buy_delay_days = int(merged["buy_delay_days"])
		self.candidate_drop_pct = float(merged["candidate_drop_pct"])
		self.candidate_drawdown_pct = float(merged["candidate_drawdown_pct"])
		self.min_amount_wan = float(merged["min_amount_wan"])
		self.max_holdings = int(merged["max_holdings"])
		self.max_single_weight = float(merged["max_single_weight"])
		self.min_candidates = int(merged["min_candidates"])
		self.overshoot_floor = float(merged["overshoot_floor"])
		self.overshoot_boost = float(merged["overshoot_boost"])
		self.max_holding_days = int(merged["max_holding_days"])
		self.tp1, self.tp2, self.tp3 = (float(merged[k]) for k in ("tp1", "tp2", "tp3"))
		self.atr_window = int(merged["atr_window"])
		self.trail_mult = float(merged["trail_mult"])
		self.stop_mult = float(merged["stop_mult"])
		self.stop_loss_pct = float(merged["stop_loss_pct"])
		self.hs300_code = str(merged["hs300_code"])
		self.csi500_code = str(merged["csi500_code"])
		self.lookback_days = int(merged["lookback_days"])

		# 显式状态变量（跨日状态机）
		self._stage: str = "idle"            # idle / t1 / confirm / buy_wait / holding
		self._trigger_date: Optional[str] = None
		self._trigger_panic: float = 0.0
		self._t1_passed: bool = False
		self._confirm_date: Optional[str] = None
		self._buy_date: Optional[str] = None
		self._last_batch_date: Optional[str] = None
		self._bar_count: int = 0

		# 数据缓存
		self._data_cache: Dict[str, pd.DataFrame] = {}
		self._panic_by_date: Dict[str, float] = {}    # {YYYY-MM-DD: panic_idx}
		self._hs300_by_date: Dict[str, Dict[str, float]] = {}  # {date: {close, amount}}
		self._csi500_by_date: Dict[str, float] = {}   # {date: close}
		# 基本面质量数据（质量分选股器，§2.4，2026-08）
		self._st_codes: set = set()                   # ST 股票（非ST 必需过滤）
		self._revenue_history: Dict[str, List[tuple]] = {}  # {code: [(ann_date, end_date, revenue)]} 按 ann_date 升序
		self._roe_history: Dict[str, List[tuple]] = {}      # {code: [(ann_date, end_date, roe)]} 按 ann_date 升序

		# 持仓（策略自管：entry_price/entry_date/peak/sold_tiers）
		self._holdings: Dict[str, Dict[str, Any]] = {}

	# ───────────────────────── 生命周期 ─────────────────────────
	def on_init(self) -> None:
		"""加载模型/数据（恐慌抄底无 ML 模型，占位）"""
		logger.info(f"{self.name} on_init: 事件驱动策略，无模型依赖")

	async def load_live_state(self, db, strategy_id: str = "", start_date: str = "") -> None:
		"""引擎启动时预加载市场数据（panic_index + 沪深300/CSI500 历史）到内存缓存。

		start_date: 回测时传入回测起始日，数据窗口按其前移（覆盖 MA250 预热）；
		            实盘留空默认近 3 年（date.today()-3y）。
		"""
		try:
			from datetime import timedelta
			from sqlalchemy import text
			sf = getattr(self, "_db_session_factory", None)
			if sf is None:
				logger.warning("恐慌抄底: session_factory 未注入，跳过市场数据预加载")
				return
			# 2026-08 修复：回测数据窗口适配（start_date 前移 400 天，覆盖 250 交易日 MA250 预热；
			# 实盘默认近 3 年）。加载后按 d<=td 过滤计算，无未来函数。
			_hist_start = (
				date.fromisoformat(start_date) - timedelta(days=400)
				if start_date
				else date.today().replace(year=date.today().year - 3)
			)
			async with sf() as session:
				# 恐慌指数全量
				r = await session.execute(text(
					"SELECT trade_date, panic_idx FROM panic_index ORDER BY trade_date"
				))
				for row in r.fetchall():
					self._panic_by_date[str(row[0])[:10]] = float(row[1] or 0)
				# 沪深300 / CSI500（近 3 年，覆盖 MA250）
				for code, target in ((self.hs300_code, "hs300"), (self.csi500_code, "csi500")):
					r = await session.execute(text(
						"SELECT trade_date, close, amount FROM index_daily "
						"WHERE ts_code = :c AND trade_date >= :s ORDER BY trade_date"
					), {"c": code, "s": _hist_start})
					for row in r.fetchall():
						d = str(row[0])[:10]
						if target == "hs300":
							self._hs300_by_date[d] = {"close": float(row[1] or 0), "amount": float(row[2] or 0)}
						else:
							self._csi500_by_date[d] = float(row[1] or 0)
				# 质量分基本面数据（非ST/营收/ROE，§2.4）
				await self._load_fundamentals(session)
			logger.info(
				f"{self.name} 市场数据预加载: panic={len(self._panic_by_date)}天, "
				f"hs300={len(self._hs300_by_date)}天, csi500={len(self._csi500_by_date)}天, "
				f"st={len(self._st_codes)}只, 营收历史={len(self._revenue_history)}只, roe历史={len(self._roe_history)}只"
			)
		except Exception as e:
			logger.warning(f"恐慌抄底市场数据预加载失败: {e}")

	async def _load_fundamentals(self, session) -> None:
		"""质量分基本面预加载：非ST + 营收 + ROE（§2.4 质量分）。

		营收/ROE 按 ann_date（披露日）升序缓存，选股时取恐慌日之前最新披露，
		避免未来函数（报告期数据仅在披露后才可用）。
		"""
		try:
			from sqlalchemy import text
			# 1. 非ST（stock_basic.name 含 ST）+ 宇宙（全市场活跃候选）
			#    2026-08 修复：恐慌选股需全市场超跌，此前 _universe 恒空 →
			#    回测落入"前1000只=深市主板"兜底，选股范围被扭曲。
			_all_codes: list = []
			r = await session.execute(text(
				"SELECT ts_code, name FROM stock_basic WHERE list_status = 'L'"
			))
			for row in r.fetchall():
				_all_codes.append(row[0])
				if row[1] and "ST" in str(row[1]).upper():
					self._st_codes.add(row[0])
			self._universe = sorted(c for c in _all_codes if c not in self._st_codes)
			# 2. 营收（financial_income，revenue 单位=万元）
			r = await session.execute(text(
				"SELECT ts_code, ann_date, end_date, revenue FROM financial_income "
				"WHERE revenue IS NOT NULL AND ann_date IS NOT NULL "
				"ORDER BY ts_code, ann_date"
			))
			for row in r.fetchall():
				self._revenue_history.setdefault(row[0], []).append(
					(str(row[1])[:10], str(row[2])[:10], float(row[3]))
				)
			# 3. ROE（stock_fina_indicators，roe 单位=%）
			r = await session.execute(text(
				"SELECT ts_code, ann_date, end_date, roe FROM stock_fina_indicators "
				"WHERE roe IS NOT NULL AND ann_date IS NOT NULL "
				"ORDER BY ts_code, ann_date"
			))
			for row in r.fetchall():
				self._roe_history.setdefault(row[0], []).append(
					(str(row[1])[:10], str(row[2])[:10], float(row[3]))
				)
		except Exception as e:
			logger.warning(f"恐慌抄底基本面预加载失败: {e}")

	@staticmethod
	def _latest_value(history: Optional[List[tuple]], td: str) -> Optional[float]:
		"""取 ann_date <= td 的最新一条 value（history 按 ann_date 升序）。"""
		if not history:
			return None
		best = None
		for ann, _end, val in history:
			if ann <= td:
				best = val
			else:
				break
		return best

	# ───────────────────────── 主逻辑（audit-strategy 四模块拆分） ─────────────────────────
	def on_bar(self, bar: BarData) -> List[TradingSignal]:
		"""逐 bar：缓存个股 K 线 + 持仓止盈止损即时检查。"""
		self._bar_count += 1
		self._append_data(bar)
		signals: List[TradingSignal] = []
		# 持仓止盈止损（用当日收盘价判断）
		signals.extend(self.check_stop_profit_stop_loss(bar))
		return signals

	def on_bar_batch_end(self, trade_date: Any = None) -> List[TradingSignal]:
		"""每批次结束：市场级状态机推进（触发/确认/选股/买入）+ 时间兜底。"""
		td = str(trade_date)[:10] if trade_date else ""
		if not td or td == self._last_batch_date:
			return []
		self._last_batch_date = td
		signals: List[TradingSignal] = []
		# 时间兜底（持仓满 max_holding_days 清仓）
		signals.extend(self._check_time_exit(td))
		# 状态机推进
		signals.extend(self._advance_state_machine(td))
		return signals

	def _advance_state_machine(self, td: str) -> List[TradingSignal]:
		"""状态机：idle → t1 → confirm → buy_wait → holding（返回交易信号）。"""
		signals: List[TradingSignal] = []

		# 市场数据缺失保护
		if td not in self._panic_by_date:
			return signals

		if self._stage == "idle":
			# 触发检测：条件A + 条件B + 年线门
			if self._check_trigger(td):
				self._stage = "t1"
				self._trigger_date = td
				self._trigger_panic = self._panic_by_date.get(td, 0.0)
				self._t1_passed = False
				logger.info(f"恐慌触发: {td} panic={self._trigger_panic:.2f} → t1 等待确认")
			return signals

		if self._stage == "t1":
			# T+1 一次性完成：条件C（panic 未新高）+ 真恐慌确认（panic<确认水位 或 300收阳）
			# 2026-08 修正：确认窗口压缩到 T+1（不再等待 T+2~T+6），买入提前到触发后 T+4
			cur_panic = self._panic_by_date.get(td, 0.0)
			if cur_panic > self._trigger_panic:
				# 恐慌加剧 → 序列失效
				self._reset_state_machine()
				logger.info(f"T+1 恐慌加剧: {td} panic={cur_panic:.2f} > {self._trigger_panic:.2f} → 序列取消")
				return signals
			# 条件C 通过 → 真恐慌确认
			hs = self._hs300_by_date.get(td)
			prev_hs = self._hs300_by_date.get(self._prev_trade_date(td))
			confirmed = cur_panic < self.confirm_panic_level
			if not confirmed and hs and prev_hs and hs["close"] > prev_hs["close"]:
				confirmed = True
			if confirmed:
				self._confirm_date = td
				self._stage = "buy_wait"
				self._buy_date = self._shift_trade_dates(td, self.buy_delay_days)
				logger.info(f"T+1 真恐慌确认: {td} panic={cur_panic:.2f} → T+{self.buy_delay_days}({self._buy_date}) 买入待定")
			else:
				# T+1 未确认 → 序列结束（确认窗口仅 T+1）
				self._reset_state_machine()
				logger.info(f"T+1({td}) 真恐慌未确认 panic={cur_panic:.2f} → 序列取消")
			return signals

		if self._stage == "buy_wait":
			# T+7 买入
			if td >= (self._buy_date or "9999"):
				signals.extend(self.generate_entry_signals(td))
				if self._holdings:
					self._stage = "holding"
				else:
					# 无候选买入 → 序列结束
					self._reset_state_machine()
			return signals

		if self._stage == "holding":
			# 持仓清空（止损/止盈/时间兜底）→ 回到 idle
			if not self._holdings:
				self._reset_state_machine()
				logger.info(f"{td} 持仓清空，状态机回 idle，等待下次恐慌")
			else:
				pass

		return signals

	# ── 模块1：开仓信号（T+7 选股） ──
	def generate_entry_signals(self, td: str) -> List[TradingSignal]:
		"""T+7 选股：全市场超跌 + 质量分 + 流动性 → TopN 等权买入信号。"""
		if self._holdings:
			return []
		candidates: List[tuple] = []
		for code, df in self._data_cache.items():
			if df is None or len(df) < 6:
				continue
			score = self._score_candidate(code, df, td)
			if score is not None:
				candidates.append((code, score))
		candidates.sort(key=lambda x: x[1], reverse=True)
		candidates = candidates[: self.max_holdings]
		if len(candidates) < self.min_candidates:
			# 2026-08 方向A：候选不足（结构性崩盘如微盘崩盘选不出优质超跌股）→ 放弃本轮，避免硬买大亏
			logger.info(f"T+{self.buy_delay_days}({td}) 候选仅 {len(candidates)} 只(<{self.min_candidates})，放弃本轮")
			return []

		# 等权分仓：单票 ≤ max_single_weight
		weight = min(1.0 / len(candidates), self.max_single_weight)
		signals: List[TradingSignal] = []
		for code, score in candidates:
			df = self._data_cache.get(code)
			price = float(df["close"].iloc[-1]) if df is not None and len(df) else 0.0
			sig = self._make_entry_signal(code, weight, price, td, score)
			if sig:
				signals.append(sig)
				self._holdings[code] = {
					"entry_price": price,
					"entry_date": td,
					"peak": price,
					"sold_tiers": set(),
					"entry_weight": weight,
				}
		logger.info(f"T+{self.buy_delay_days}({td}) 恐慌抄底买入: {len(signals)} 只, 等权 {weight:.0%}")
		return signals

	def _relative_overshoot(self, df: pd.DataFrame, td: str) -> float:
		"""恐慌前相对强度：股票 − 沪深300 恐慌前第 10~20 日收益。正值 = 前期强势被恐慌错杀。

		v3（2026-08）：v1 用恐慌中相对跌幅（恐慌日普跌无区分度）、v2 窗口跨恐慌开始段，
		均无效。改用恐慌前第 10~20 个交易日（避开恐慌开始段）的相对强度——
		「前期强势 + 恐慌中超跌」= 错杀强势股，恐慌反弹领涨这类票。
		"""
		try:
			closes = df["close"].astype(float)
			if len(closes) < 21:
				return 0.0
			stock_ret = closes.iloc[-11] / closes.iloc[-21] - 1  # 恐慌前第10~20日股票收益
			hs300_dates = sorted([d for d in self._hs300_by_date if d <= td])
			if len(hs300_dates) < 21:
				return 0.0
			hs_now = self._hs300_by_date[hs300_dates[-11]]["close"]   # td-10
			hs_prev = self._hs300_by_date[hs300_dates[-21]]["close"]  # td-20
			if hs_prev <= 0:
				return 0.0
			hs300_ret = hs_now / hs_prev - 1
			return stock_ret - hs300_ret  # 正值 = 恐慌前相对强势
		except Exception:
			return 0.0

	def _score_candidate(self, code: str, df: pd.DataFrame, td: str) -> Optional[float]:
		"""候选评分（§2.4 质量权重）：超跌 × 质量分(营收/ROE/非ST) × 流动性分 × 错杀弹性。"""
		try:
			closes = df["close"].astype(float)
			if len(closes) < 21:
				return None
			# 超跌：近 5 日跌>15%（恐慌急跌）——2026-08 回退方向3（中期回调超跌选入质量差，胜率 64→49%）
			close_now = float(closes.iloc[-1])
			drop5 = close_now / closes.iloc[-6] - 1 if closes.iloc[-6] > 0 else 0.0
			hi60 = float(closes.tail(60).max())
			drawdown = close_now / hi60 - 1 if hi60 > 0 else 0.0  # 保留计算仅供日志
			if drop5 > -self.candidate_drop_pct:
				return None
			# 流动性：近 20 日均成交额（amount 千元 → 万元 /10）
			amt20 = df["amount"].astype(float).tail(20).mean() / 10.0 if "amount" in df.columns else 0.0
			if amt20 < self.min_amount_wan:
				return None
			# 非ST（§2.4 必需过滤）
			if code in self._st_codes:
				return None
			# 营收（§2.4 基础过滤：>5000 万；数据缺失时降级不拒，避免误杀）
			revenue = self._latest_value(self._revenue_history.get(code), td)
			if revenue is not None and revenue < 5000:
				return None
			# ROE（§2.4 质量分：ROE>5% ×1.5；数据缺失时降级）
			roe = self._latest_value(self._roe_history.get(code), td)
			# 质量分（营收>1亿 ×1.2，ROE>5% ×1.5）
			quality = 1.0
			if revenue is not None and revenue > 10000:
				quality *= 1.2
			if roe is not None and roe > 5.0:
				quality *= 1.5
			# 错杀弹性（2026-08 方向A v2）：优质股(质量分>1)恐慌前相对强势(≥floor) + 恐慌中超跌 = 错杀强势股
			overshoot = self._relative_overshoot(df, td)
			if quality > 1.0 and overshoot > self.overshoot_floor:
				quality *= (1 + self.overshoot_boost)
			# 流动性分（§2.4：>5000万 ×1.5，>1000万 ×1.2）
			liq = 1.0
			if amt20 > 5000:
				liq = 1.5
			elif amt20 > 1000:
				liq = 1.2
			# 当日未涨停（可买入）
			if len(closes) >= 2 and closes.iloc[-2] > 0:
				pct = closes.iloc[-1] / closes.iloc[-2] - 1
				if pct > 0.095:  # 涨停不追
					return None
			score = (-drop5) * quality * liq
			logger.info(f"[选股] {code} {td}: drop5={drop5:.1%} 回撤={drawdown:.1%} 质量={quality:.2f} 错杀={overshoot:.1%} 流动={liq:.1f} → score={score:.2f}")
			return score
		except Exception:
			return None

	# ── 模块2：平仓信号（时间兜底） ──
	def generate_exit_signals(self, td: str) -> List[TradingSignal]:
		"""时间兜底清仓（持仓满 max_holding_days）。"""
		return self._check_time_exit(td)

	def _check_time_exit(self, td: str) -> List[TradingSignal]:
		signals: List[TradingSignal] = []
		for code in list(self._holdings.keys()):
			h = self._holdings[code]
			entry_d = h.get("entry_date", "")
			days = self._trade_date_diff(entry_d, td)
			if entry_d and days >= self.max_holding_days:
				df = self._data_cache.get(code)
				price = float(df["close"].iloc[-1]) if df is not None and len(df) else 0.0
				sig = self._make_exit_signal(code, price, f"时间兜底: 持仓 {days} 日 ≥ {self.max_holding_days}")
				if sig:
					signals.append(sig)
					self._holdings.pop(code, None)
		return signals

	# ── 模块3：止盈止损（on_bar 即时检查） ──
	def check_stop_profit_stop_loss(self, bar: BarData) -> List[TradingSignal]:
		"""固定止盈(20/40/60) + ATR 移动兜底 + ATR 硬止损。

		恐慌反弹为脉冲式（快速涨 20-40% 后回落）：固定止盈分批锁定吃到反弹；
		ATR 移动兜底防见顶回落利润回吐；ATR 硬止损自适应高波动替代固定 -15%。
		顺序：硬止损(亏先走) → 固定止盈(吃反弹) → 移动兜底(未达档位但见顶回落)。
		"""
		signals: List[TradingSignal] = []
		code = bar.ts_code
		h = self._holdings.get(code)
		if not h:
			return signals
		close = float(bar.close or 0)
		entry = float(h.get("entry_price", 0) or 0)
		if close <= 0 or entry <= 0:
			return signals

		atr = self._calc_atr(code)
		if atr <= 0:
			# ATR 数据不足（< atr_window+1 根 bar），跳过止损判定避免误平仓
			return signals

		# 更新持仓最高点（移动兜底基准）
		h["peak"] = max(float(h.get("peak", entry) or entry), float(bar.high or close))

		# 1. ATR 硬止损：close < 入场价 - stop_mult×ATR（亏钱先走）
		if close < entry - self.stop_mult * atr:
			logger.info(f"[卖出] {code} ATR硬止损: 买{entry:.2f} 卖{close:.2f} ({close/entry-1:.1%})")
			sig = self._make_exit_signal(code, close, f"ATR硬止损: 入场-{self.stop_mult:.1f}×ATR({atr:.2f})")
			if sig:
				signals.append(sig)
				self._holdings.pop(code, None)
			return signals

		# 2. 固定止盈（阶梯分批）：20/40/60
		gain = close / entry - 1
		sold = h.get("sold_tiers", set())
		if gain >= self.tp3 and "tp3" not in sold:
			logger.info(f"[卖出] {code} 止盈档3清仓: 买{entry:.2f} 卖{close:.2f} +{gain:.0%}")
			sig = self._make_exit_signal(code, close, f"阶梯止盈档3: 浮盈 {gain:.0%} ≥{self.tp3:.0%} 清仓")
			if sig:
				signals.append(sig)
				self._holdings.pop(code, None)
			return signals
		if gain >= self.tp2 and "tp2" not in sold:
			sold.add("tp2")
			sig = self._make_partial_exit(code, close, "tp2", f"阶梯止盈档2: 浮盈 {gain:.0%} ≥{self.tp2:.0%} 卖1/3")
			if sig:
				signals.append(sig)
		elif gain >= self.tp1 and "tp1" not in sold:
			sold.add("tp1")
			sig = self._make_partial_exit(code, close, "tp1", f"阶梯止盈档1: 浮盈 {gain:.0%} ≥{self.tp1:.0%} 卖1/3")
			if sig:
				signals.append(sig)

		# 4. ATR 移动兜底（动态倍数）：close < 最高点 - 当前倍数×ATR
		if close < h["peak"] - self.trail_mult * atr:
			_max_gain = h["peak"] / entry - 1 if entry > 0 else 0.0
			logger.info(f"[卖出] {code} 移动兜底: 买{entry:.2f} 峰值{h['peak']:.2f}(+{_max_gain:.0%}) 现卖{close:.2f}({gain:.1%}) {self.trail_mult:.1f}×ATR")
			sig = self._make_exit_signal(code, close, f"移动兜底: 高点回撤{self.trail_mult:.1f}×ATR({atr:.2f})")
			if sig:
				signals.append(sig)
				self._holdings.pop(code, None)
		return signals

	def _calc_atr(self, code: str) -> float:
		"""ATR（真实波幅均值，atr_window 日）：恐慌后波动自适应止损/止盈基准。"""
		df = self._data_cache.get(code)
		if df is None or len(df) < self.atr_window + 1:
			return 0.0
		try:
			high = df["high"].astype(float)
			low = df["low"].astype(float)
			close = df["close"].astype(float)
			prev_close = close.shift(1)
			tr = pd.concat([
				high - low,
				(high - prev_close).abs(),
				(low - prev_close).abs(),
			], axis=1).max(axis=1)
			atr = tr.tail(self.atr_window).mean()
			return float(atr) if atr > 0 else 0.0
		except Exception:
			return 0.0

	# ── 模块4：仓位计算（等权 TopN） ──
	def calculate_position_size(self, code: str, price: float, capital: float) -> int:
		"""单票等权仓位：weight × capital / price，最小 100 股。"""
		if price <= 0:
			return 0
		amount = self.max_single_weight * capital
		shares = max(int(amount / price / 100) * 100, 100)
		return shares

	# ───────────────────────── 触发条件（M2 修订口径） ─────────────────────────
	def _check_trigger(self, td: str) -> bool:
		"""T 日触发：条件A(panic≥阈值) + 条件B(年线下4.5%/距前低2.5%/5日跌8%)。"""
		panic = self._panic_by_date.get(td, 0.0)
		if panic < self.panic_threshold:
			return False
		# 年线门（2026-08 已关）
		if self.use_annual_gate and self._is_bear_market(td):
			logger.info(f"年线门拦截: {td} panic={panic:.2f} 但 CSI500 熊市，放弃")
			return False
		# 条件B
		hs = self._hs300_by_date.get(td)
		if not hs:
			logger.info(f"[触发评估] {td} panic={panic:.2f} 沪深300数据缺失 → 不触发")
			return False
		close = hs["close"]
		ma250 = self._hs300_ma250(td)
		low60 = self._hs300_low60(td)
		ret5 = self._hs300_ret5(td)
		c1 = bool(ma250 and close < ma250 * (1 - self.cond_b_below_ma250_pct))
		c2 = bool(low60 and close / low60 - 1 < -self.cond_b_low60_pct)
		c3 = bool(ret5 is not None and ret5 < -self.cond_b_ret5_pct)
		# 触发评估日志（2026-08：分析边界误判/未触发原因）
		_vs = f"年线{close/ma250-1:+.1%}(需<-{self.cond_b_below_ma250_pct:.1%})" if ma250 else "年线数据不足"
		_vs2 = f"距60低{close/low60-1 if low60 else 0:+.1%}(需<-{self.cond_b_low60_pct:.1%})"
		_vs3 = f"5日{ret5*100 if ret5 is not None else 0:+.0f}%(需<-{self.cond_b_ret5_pct:.0%})"
		logger.info(f"[触发评估] {td} panic={panic:.2f} 沪深300={close:.0f} | {_vs} | {_vs2} | {_vs3} → {'✓触发' if (c1 or c2 or c3) else '✗不触发'}")
		return c1 or c2 or c3

	def _is_bear_market(self, td: str) -> bool:
		"""年线门：CSI500 收盘 < MA250。"""
		closes = [v for d, v in sorted(self._csi500_by_date.items()) if d <= td]
		if len(closes) < 250:
			return False
		ma250 = sum(closes[-250:]) / 250.0
		return closes[-1] < ma250

	def _hs300_ma250(self, td: str) -> Optional[float]:
		closes = [v["close"] for d, v in sorted(self._hs300_by_date.items()) if d <= td]
		if len(closes) < 250:
			return None
		return sum(closes[-250:]) / 250.0

	def _hs300_low60(self, td: str) -> Optional[float]:
		closes = [v["close"] for d, v in sorted(self._hs300_by_date.items()) if d <= td]
		if len(closes) < 61:
			return None
		return min(closes[-61:-1])

	def _hs300_ret5(self, td: str) -> Optional[float]:
		closes = [v["close"] for d, v in sorted(self._hs300_by_date.items()) if d <= td]
		if len(closes) < 6:
			return None
		return closes[-1] / closes[-6] - 1

	def _prev_trade_date(self, td: str) -> str:
		dates = [d for d in self._hs300_by_date if d < td]
		return max(dates) if dates else ""

	def _trade_date_diff(self, d1: str, d2: str) -> int:
		"""两个日期之间的交易日数（用沪深300 交易日历近似）。"""
		if not d1 or not d2 or d1 >= d2:
			return 0
		dates = [d for d in self._hs300_by_date if d1 <= d <= d2]
		return len(dates) - 1 if dates else 0

	def _shift_trade_dates(self, td: str, n: int) -> str:
		"""从 td 起向后数 n 个交易日。"""
		dates = [d for d in sorted(self._hs300_by_date) if d >= td]
		if len(dates) > n:
			return dates[n]
		return dates[-1] if dates else td

	def _reset_state_machine(self) -> None:
		self._stage = "idle"
		self._trigger_date = None
		self._trigger_panic = 0.0
		self._t1_passed = False
		self._confirm_date = None
		self._buy_date = None

	def _append_data(self, bar: BarData) -> None:
		code = bar.ts_code
		td = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
		row = {
			"trade_date": td,
			"close": float(bar.close or 0),
			"open": float(getattr(bar, "open", bar.close) or bar.close),
			"high": float(getattr(bar, "high", bar.close) or bar.close),
			"low": float(getattr(bar, "low", bar.close) or bar.close),
			"volume": float(getattr(bar, "volume", 0) or 0),
			"amount": float(getattr(bar, "amount", 0) or 0),
		}
		if code not in self._data_cache:
			self._data_cache[code] = pd.DataFrame(columns=list(row.keys()))
		df = self._data_cache[code]
		# 去重：同代码同日不重复追加
		if len(df) and str(df["trade_date"].iloc[-1])[:10] == td:
			df.iloc[-1] = list(row.values())
		else:
			self._data_cache[code] = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
		# 限长
		if len(self._data_cache[code]) > self.lookback_days + 40:
			self._data_cache[code] = self._data_cache[code].tail(self.lookback_days + 40).reset_index(drop=True)

	def _make_entry_signal(self, code: str, weight: float, price: float, td: str, score: float) -> Optional[TradingSignal]:
		if price <= 0:
			return None
		sig = TradingSignal(
			id=self._gen_id(),
			strategy_id=self.name,
			strategy_name=self.name,
			ts_code=code,
			signal_type=SignalType.ENTRY,
			direction=SignalDirection.LONG,
			price=price,
			quantity=0,  # 数量由 Sizer 按 weight 计算
			amount=0.0,
			confidence=0.75,
			reason=f"恐慌抄底: T+{self.buy_delay_days} 超跌买入 (drop5={score:.1%})",
			timestamp=datetime.now(),
			order_mode="close",
		)
		sig.weight = weight
		sig.stop_loss_price = price * (1 - self.stop_loss_pct)  # 每笔开仓必须带止损
		return sig

	def _make_exit_signal(self, code: str, price: float, reason: str) -> Optional[TradingSignal]:
		if price <= 0:
			return None
		sig = TradingSignal(
			id=self._gen_id(),
			strategy_id=self.name,
			strategy_name=self.name,
			ts_code=code,
			signal_type=SignalType.EXIT,
			direction=SignalDirection.CLOSE_LONG,
			price=price,
			quantity=0,
			amount=0.0,
			confidence=0.9,
			reason=f"恐慌抄底: {reason}",
			timestamp=datetime.now(),
			order_mode="close",
		)
		sig.weight = 1.0  # 清仓
		return sig

	def _make_partial_exit(self, code: str, price: float, tier: str, reason: str) -> Optional[TradingSignal]:
		"""阶梯止盈分批卖出（1/3 仓）。"""
		if price <= 0:
			return None
		sig = TradingSignal(
			id=self._gen_id(),
			strategy_id=self.name,
			strategy_name=self.name,
			ts_code=code,
			signal_type=SignalType.TAKE_PROFIT,
			direction=SignalDirection.CLOSE_LONG,
			price=price,
			quantity=0,
			amount=0.0,
			confidence=0.85,
			reason=f"恐慌抄底: {reason}",
			timestamp=datetime.now(),
			order_mode="close",
		)
		sig.weight = 1 / 3  # 卖 1/3
		return sig

	@staticmethod
	def _gen_id() -> str:
		import uuid
		return str(uuid.uuid4())
