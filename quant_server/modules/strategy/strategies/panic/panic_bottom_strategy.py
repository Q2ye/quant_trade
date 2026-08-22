# -*- coding: utf-8 -*-
"""
恐慌抄底策略（事件型卫星 · 阶段 4b）
====================================================================================
定位：卫星池事件型子仓，博单次进攻倍数（1.3x-10x），平时闲置。
依据：`docs/00-核心策略体系/策略设计.md` §二 + `恐慌抄底反例统计报告.md`（M2 修订口径）

事件驱动状态机（跨日，显式状态变量）：
  idle      → [T日: panic≥阈值 + 条件B + 年线门非熊]          → t1
  t1        → [T+1: panic 未再创新高（M2 修订：免成交额缩量）]  → confirm
  confirm   → [T+2~T+6: panic<确认水位 或 沪深300收阳]         → buy_wait
  buy_wait  → [T+7] 选股（超跌+质量分 TopN 等权）→ 买入信号      → holding
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
		"use_annual_gate": True,            # 年线门：CSI500 < MA250 → 熊市放弃（不抄底）
		"cond_b_below_ma250_pct": 0.05,     # 条件B：沪深300 收盘 < MA250×(1-5%)
		"cond_b_low60_pct": 0.03,           # 条件B：沪深300 距 60 日前低 < -3%
		"cond_b_ret5_pct": 0.08,            # 条件B：沪深300 近 5 日跌幅 > 8%
		"confirm_window_days": 5,           # T+2~T+6 真恐慌确认窗口（5 个交易日）
		"confirm_panic_level": 1.5,         # 确认：恐慌指数回落 < 1.5
		"buy_delay_days": 7,                # T+7 买入
		# ── 选股（T+7 候选池） ──
		"candidate_drop_pct": 0.15,         # 超跌筛选：近 5 日跌幅 > 15%
		"min_amount_wan": 500,              # 流动性下限：近 20 日均成交额 ≥ 500 万元
		"max_holdings": 10,                 # 持仓上限（分散 10 只）
		"max_single_weight": 0.10,          # 单票仓位 ≤ 10%
		# ── 止盈止损（严格执行，不设止损不上线） ──
		"tp1": 0.15,                        # 阶梯止盈档1：浮盈 15% → 卖 1/3
		"tp2": 0.30,                        # 阶梯止盈档2：浮盈 30% → 卖 1/3
		"tp3": 0.50,                        # 阶梯止盈档3：浮盈 50% → 清仓
		"stop_loss_pct": 0.15,              # 单票止损：亏损 15% 立即离场
		"max_holding_days": 20,             # 时间兜底：持仓满 20 交易日清仓
		# ── 数据 ──
		"hs300_code": "000300.SH",          # 沪深300（条件B/确认收阳）
		"csi500_code": "000905.SH",         # CSI500（年线门）
		"lookback_days": 260,               # 指标回看（MA250 年线）
	}

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
		self.min_amount_wan = float(merged["min_amount_wan"])
		self.max_holdings = int(merged["max_holdings"])
		self.max_single_weight = float(merged["max_single_weight"])
		self.tp1, self.tp2, self.tp3 = (float(merged[k]) for k in ("tp1", "tp2", "tp3"))
		self.stop_loss_pct = float(merged["stop_loss_pct"])
		self.max_holding_days = int(merged["max_holding_days"])
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

		# 持仓（策略自管：entry_price/entry_date/peak/sold_tiers）
		self._holdings: Dict[str, Dict[str, Any]] = {}

	# ───────────────────────── 生命周期 ─────────────────────────
	def on_init(self) -> None:
		"""加载模型/数据（恐慌抄底无 ML 模型，占位）"""
		logger.info(f"{self.name} on_init: 事件驱动策略，无模型依赖")

	async def load_live_state(self, db, strategy_id: str = "") -> None:
		"""引擎启动时预加载市场数据（panic_index + 沪深300/CSI500 历史）到内存缓存。"""
		try:
			from sqlalchemy import text
			sf = getattr(self, "_db_session_factory", None)
			if sf is None:
				logger.warning("恐慌抄底: session_factory 未注入，跳过市场数据预加载")
				return
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
					), {"c": code, "s": date.today().replace(year=date.today().year - 3)})
					for row in r.fetchall():
						d = str(row[0])[:10]
						if target == "hs300":
							self._hs300_by_date[d] = {"close": float(row[1] or 0), "amount": float(row[2] or 0)}
						else:
							self._csi500_by_date[d] = float(row[1] or 0)
			logger.info(
				f"{self.name} 市场数据预加载: panic={len(self._panic_by_date)}天, "
				f"hs300={len(self._hs300_by_date)}天, csi500={len(self._csi500_by_date)}天"
			)
		except Exception as e:
			logger.warning(f"恐慌抄底市场数据预加载失败: {e}")

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
			# T+1 条件C：panic 未再创新高（M2 修订：免成交额缩量）
			cur_panic = self._panic_by_date.get(td, 0.0)
			if cur_panic <= self._trigger_panic:
				self._t1_passed = True
				self._stage = "confirm"
				self._confirm_date = None
				logger.info(f"T+1 抛压未增强: {td} panic={cur_panic:.2f} ≤ {self._trigger_panic:.2f} → confirm 窗口")
			else:
				# 恐慌加剧 → 序列失效
				self._reset_state_machine()
				logger.info(f"T+1 恐慌加剧: {td} panic={cur_panic:.2f} > {self._trigger_panic:.2f} → 序列取消")
			return signals

		if self._stage == "confirm":
			# T+2~T+6 真恐慌确认：panic < confirm_panic_level 或 沪深300 收阳
			cur_panic = self._panic_by_date.get(td, 0.0)
			hs = self._hs300_by_date.get(td)
			prev_hs = self._hs300_by_date.get(self._prev_trade_date(td))
			confirmed = cur_panic < self.confirm_panic_level
			if not confirmed and hs and prev_hs and hs["close"] > prev_hs["close"]:
				confirmed = True
			if confirmed:
				self._confirm_date = td
				self._stage = "buy_wait"
				self._buy_date = self._shift_trade_dates(td, self.buy_delay_days)
				logger.info(f"真恐慌确认: {td} panic={cur_panic:.2f} → T+7({self._buy_date}) 买入待定")
			else:
				# 超窗（从触发日算 T+2~T+6）→ 放弃
				days_since = self._trade_date_diff(self._trigger_date or "", td)
				if days_since > 1 + self.confirm_window_days:
					self._reset_state_machine()
					logger.info(f"确认窗口超时: {td}（{days_since} 日）→ 序列取消")
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
			# 持仓中：状态机保持（止盈止损在 on_bar / _check_time_exit 处理）
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
		if not candidates:
			logger.info(f"T+7({td}) 无超跌候选，序列结束")
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
		logger.info(f"T+7({td}) 恐慌抄底买入: {len(signals)} 只, 等权 {weight:.0%}")
		return signals

	def _score_candidate(self, code: str, df: pd.DataFrame, td: str) -> Optional[float]:
		"""候选评分：5 日跌幅 > 阈值（超跌）+ 流动性 + 非涨跌停 + 质量分。"""
		try:
			closes = df["close"].astype(float)
			if len(closes) < 21:
				return None
			# 超跌：近 5 日跌幅 > candidate_drop_pct
			drop5 = closes.iloc[-1] / closes.iloc[-6] - 1 if closes.iloc[-6] > 0 else 0.0
			if drop5 > -self.candidate_drop_pct:
				return None
			# 流动性：近 20 日均成交额 ≥ min_amount_wan 万元（amount 千元 → 万元 /10）
			if "amount" in df.columns:
				amt20 = df["amount"].astype(float).tail(20).mean() / 10.0  # 千元→万元
				if amt20 < self.min_amount_wan:
					return None
			# 当日未涨停（可买入）
			if len(closes) >= 2 and closes.iloc[-2] > 0:
				pct = closes.iloc[-1] / closes.iloc[-2] - 1
				if pct > 0.095:  # 涨停不追
					return None
			# 质量分：超跌越深越高（可扩展 ROE/营收，数据可得后叠加）
			score = -drop5
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
		"""每笔开仓必须带止损；阶梯止盈让利润奔跑。"""
		signals: List[TradingSignal] = []
		code = bar.ts_code
		h = self._holdings.get(code)
		if not h:
			return signals
		close = float(bar.close or 0)
		entry = float(h.get("entry_price", 0) or 0)
		if close <= 0 or entry <= 0:
			return signals

		# 止损（硬止损优先）
		if close <= entry * (1 - self.stop_loss_pct):
			sig = self._make_exit_signal(code, close, f"止损: 亏损 ≥{self.stop_loss_pct:.0%}")
			if sig:
				signals.append(sig)
				self._holdings.pop(code, None)
			return signals

		# 阶梯止盈（peak 跟踪 + 档位分批）
		h["peak"] = max(float(h.get("peak", entry) or entry), close)
		gain = close / entry - 1
		sold = h.get("sold_tiers", set())

		if gain >= self.tp3 and "tp3" not in sold:
			# 档3：浮盈 50% → 清仓
			sig = self._make_exit_signal(code, close, f"阶梯止盈档3: 浮盈 {gain:.0%} ≥{self.tp3:.0%} 清仓")
			if sig:
				signals.append(sig)
				self._holdings.pop(code, None)
			return signals

		if gain >= self.tp2 and "tp2" not in sold:
			# 档2：浮盈 30% → 卖 1/3
			sold.add("tp2")
			sig = self._make_partial_exit(code, close, "tp2", f"阶梯止盈档2: 浮盈 {gain:.0%} ≥{self.tp2:.0%} 卖1/3")
			if sig:
				signals.append(sig)
		elif gain >= self.tp1 and "tp1" not in sold:
			# 档1：浮盈 15% → 卖 1/3
			sold.add("tp1")
			sig = self._make_partial_exit(code, close, "tp1", f"阶梯止盈档1: 浮盈 {gain:.0%} ≥{self.tp1:.0%} 卖1/3")
			if sig:
				signals.append(sig)
		return signals

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
		"""T 日触发：条件A(panic≥阈值) + 条件B(300年线下5%/距前低3%/5日跌8%) + 年线门(非熊)。"""
		panic = self._panic_by_date.get(td, 0.0)
		if panic < self.panic_threshold:
			return False
		# 年线门：CSI500 < MA250 → 熊市放弃
		if self.use_annual_gate and self._is_bear_market(td):
			logger.info(f"年线门拦截: {td} panic={panic:.2f} 但 CSI500 熊市，放弃")
			return False
		# 条件B
		hs = self._hs300_by_date.get(td)
		if not hs:
			return False
		close = hs["close"]
		ma250 = self._hs300_ma250(td)
		if ma250 and close < ma250 * (1 - self.cond_b_below_ma250_pct):
			return True
		low60 = self._hs300_low60(td)
		if low60 and close / low60 - 1 < -self.cond_b_low60_pct:
			return True
		ret5 = self._hs300_ret5(td)
		if ret5 is not None and ret5 < -self.cond_b_ret5_pct:
			return True
		return False

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

	# ───────────────────────── 数据与信号构造 ─────────────────────────
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
			reason=f"恐慌抄底: T+7 超跌买入 (drop5={score:.1%})",
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
