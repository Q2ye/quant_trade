# -*- coding: utf-8 -*-
"""
微盘股策略（进攻型卫星 · 阶段 4c）
====================================================================================
定位：卫星池进攻型子仓，微盘低定价效率 + 壳价值 alpha，双指数择时防独立崩塌。
依据：`docs/00-核心策略体系/策略设计.md` §四 + `微盘反例统计报告.md`（M3 实证口径）

核心逻辑：
  选池（月度重选）  circ_mv < 50亿（万元500000）+ 非ST + 非北交所 + 近20日成交额>3000万(千元30000)
                    + 市值最小 50 只
  门控1（大盘）     market_state_daily.regime == BULL
  门控2（微盘趋势）  自建微盘等权指数 > MA20（数据库无中证2000，M3 实证自建方案）
  买入             Top10-20 等权，单票 ≤5%，总仓 ≤80%
  风控             单票止损 -10%；浮盈 30% 减半；任一门关闭 → 整体空仓
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


class MicrocapStrategy(BaseStrategy):
	"""微盘股 + 双指数择时 — 月度重选持仓型策略"""

	DEFAULT_PARAMS: Dict[str, Any] = {
		# ── 选池（M3 反例统计口径，单位已换算） ──
		"max_circ_mv": 500000,            # 流通市值上限 50 亿（stock_daily_basic.circ_mv 单位=万元）
		"pool_size": 50,                  # 微盘池大小（市值最小 50 只）
		"min_amount_wan": 3000,           # 日均成交额下限 3000 万元（stock_daily.amount 千元 → /10）
		"rebuild_pool_freq": 20,          # 每 20 交易日重选池
		"rebalance_interval": 20,         # 持仓调仓间隔（交易日，20=月度，M3 口径；>0 消除日频换手）
		# ── 择时（双门控） ──
		"use_market_gate": True,          # 门控1：大盘 regime BULL
		"use_micro_gate": True,           # 门控2：微盘指数 > MA20
		"micro_ma_window": 20,            # 微盘择时均线窗口
		# ── 买入 ──
		"holdings": 15,                   # 持仓数量（等权 Top N）
		"max_single_weight": 0.05,        # 单票上限 5%
		"max_total_weight": 0.80,         # 总仓位上限 80%（留 20% 现金防流动性枯竭）
		"momentum_window": 20,            # 选股动量窗口（20日动量排序）
		"use_momentum": False,            # 2026-08 实证：动量Top15为巨大负贡献（等权+31% vs 动量+1.24%），
		                                  # 默认等权（M3口径）；True 仅用于对照实验
		# ── 风控 ──
		"stop_loss": -0.10,               # 单票止损 10%
		"profit_reduce": 0.30,            # 浮盈 30% 减半
		"lookback_days": 120,             # 缓存回看（动量/均线）
	}

	# 回测预加载标记：load_live_state 为纯市场数据预加载（无实盘持仓恢复），回测可安全调用
	BACKTEST_PRELOAD_STATE = True

	def __init__(self, name: str, strategy_type=None, parameters: Optional[Dict[str, Any]] = None):
		super().__init__(name=name, strategy_type=strategy_type, parameters=parameters)
		merged = dict(self.DEFAULT_PARAMS)
		if parameters:
			merged.update(parameters)
		self.parameters = merged

		# 参数展开
		self.max_circ_mv = float(merged["max_circ_mv"])
		self.pool_size = int(merged["pool_size"])
		self.min_amount_wan = float(merged["min_amount_wan"])
		self.rebuild_pool_freq = int(merged["rebuild_pool_freq"])
		self.rebalance_interval = int(merged.get("rebalance_interval", self.rebuild_pool_freq))
		self.use_market_gate = bool(merged["use_market_gate"])
		self.use_micro_gate = bool(merged["use_micro_gate"])
		self.micro_ma_window = int(merged["micro_ma_window"])
		self.holdings = int(merged["holdings"])
		self.max_single_weight = float(merged["max_single_weight"])
		self.max_total_weight = float(merged["max_total_weight"])
		self.momentum_window = int(merged["momentum_window"])
		self.use_momentum = bool(merged.get("use_momentum", True))
		self.stop_loss = float(merged["stop_loss"])
		self.profit_reduce = float(merged["profit_reduce"])
		self.lookback_days = int(merged["lookback_days"])

		# 状态
		self._data_cache: Dict[str, pd.DataFrame] = {}
		self._bar_count: int = 0
		self._last_batch_date: Optional[str] = None
		self._last_rebuild_date: Optional[str] = None
		self._last_rebalance_date: Optional[str] = None   # 上次持仓调仓日（月度重排）
		self._exited_today: set = set()                   # 当日已退出股票（防止同日止损后立刻买回）
		self._pool: List[str] = []                    # 当前微盘池
		self._circ_mv_snapshots: Dict[str, Dict[str, float]] = {}  # {月末日: {code: circ_mv}}
		self._regime_by_date: Dict[str, str] = {}     # {date: BULL/NEUTRAL/BEAR}
		self._micro_nav: float = 1.0                  # 自建微盘等权指数（门控2）
		self._micro_nav_history: List[float] = []
		self._holdings: Dict[str, Dict[str, Any]] = {}  # {code: {entry_price, entry_date, peak, ...}}

	# ───────────────────────── 生命周期 ─────────────────────────
	def on_init(self) -> None:
		"""加载模型/数据（无 ML 模型，占位）"""
		logger.info(f"{self.name} on_init: 微盘选股策略，依赖 circ_mv 数据")

	async def load_live_state(self, db, strategy_id: str = "", start_date: str = "") -> None:
		"""预加载：circ_mv 月末快照 + 大盘 regime 历史。

		start_date: 回测时传入回测起始日，circ_mv 快照窗口按其前移（覆盖选池预热）；
		            实盘留空默认近 3 年（date.today()-3y）。
		"""
		try:
			from datetime import timedelta
			from sqlalchemy import text
			sf = getattr(self, "_db_session_factory", None)
			if sf is None:
				logger.warning("微盘策略: session_factory 未注入，跳过数据预加载")
				return
			# 2026-08 修复：回测数据窗口适配（start_date 前移 370 天，覆盖月末快照预热；
			# 实盘默认近 3 年）。加载后按日期过滤计算，无未来函数。
			_hist_start = (
				date.fromisoformat(start_date) - timedelta(days=370)
				if start_date
				else date.today().replace(year=date.today().year - 3)
			)
			async with sf() as session:
				# 1. circ_mv 月末快照（join stock_basic 过滤 ST/北交所）
				r = await session.execute(text("""
					SELECT d.trade_date, d.ts_code, b.name, d.circ_mv
					FROM stock_daily_basic d
					JOIN stock_basic b ON b.ts_code = d.ts_code
					WHERE d.trade_date IN (
						SELECT DISTINCT ON (to_char(trade_date, 'YYYY-MM')) trade_date
						FROM stock_daily_basic
						WHERE trade_date >= :s
						ORDER BY to_char(trade_date, 'YYYY-MM'), trade_date DESC
					)
				"""), {"s": _hist_start})
				for row in r.fetchall():
					d = str(row[0])[:10]
					name = str(row[2] or "")
					if name.startswith("ST") or name.startswith("*ST") or str(row[1]).endswith(".BJ"):
						continue
					self._circ_mv_snapshots.setdefault(d, {})[row[1]] = float(row[3] or 0)
				# 2026-08 修复（宇宙）：微盘需从全 A 选最小市值，此前 _universe 恒空
				# → 回测落入"stock_basic 前1000只=深市主板"兜底，微盘语义被破坏。
				# 取"任一期末快照中满足 circ_mv<=50亿 的股票"作为全市场候选池
				# （含创业板/科创板等，已排除 ST/北交所——预加载查询已过滤）。
				self._universe = sorted({
					c for snap in self._circ_mv_snapshots.values()
					for c, mv in snap.items() if mv <= self.max_circ_mv
				})

				# 2. 大盘 regime
				r = await session.execute(text(
					"SELECT trade_date, regime FROM market_state_daily ORDER BY trade_date"
				))
				for row in r.fetchall():
					self._regime_by_date[str(row[0])[:10]] = str(row[1])
			logger.info(
				f"{self.name} 预加载: circ_mv 快照 {len(self._circ_mv_snapshots)} 个月, "
				f"regime {len(self._regime_by_date)} 天"
			)
		except Exception as e:
			logger.warning(f"微盘策略预加载失败: {e}")

	@property
	def universe(self) -> List[str]:
		"""全 A 股票池（微盘从全市场选，含创业板 300）。"""
		return list(getattr(self, "_universe", []))

	# ───────────────────────── 主逻辑（audit-strategy 四模块拆分） ─────────────────────────
	def on_bar(self, bar: BarData) -> List[TradingSignal]:
		"""逐 bar：缓存个股 K 线 + 持仓止损即时检查。"""
		self._bar_count += 1
		self._append_data(bar)
		return self.check_stop_profit_stop_loss(bar)

	def on_bar_batch_end(self, trade_date: Any = None) -> List[TradingSignal]:
		"""每批次结束：门控 → 月度重选 → 调仓（再平衡/清仓）。"""
		td = str(trade_date)[:10] if trade_date else ""
		if not td or td == self._last_batch_date:
			return []
		self._last_batch_date = td
		signals: List[TradingSignal] = []
		signals.extend(self._rebalance(td))
		return signals

	def _rebalance(self, td: str) -> List[TradingSignal]:
		"""每日调仓：更新微盘指数 → 门控 → 月度重选 → 买卖。"""
		signals: List[TradingSignal] = []

		# 1. 更新自建微盘指数（池内股票等权日收益）
		self._update_micro_nav(td)

		# 2. 门控
		gate1 = self._check_market_gate(td)
		gate2 = self._check_micro_gate()

		# 3. 月度重选池
		if self._last_rebuild_date is None or self._trade_date_diff(self._last_rebuild_date, td) >= self.rebuild_pool_freq:
			self._rebuild_pool(td)
			self._last_rebuild_date = td

		# 4. 任一门关闭 → 整体空仓
		if not gate1 or not gate2:
			signals.extend(self._close_all(td, reason="门控关闭空仓"))
			self._exited_today.clear()
			return signals

		# 5. 双门开 → 按 M3 月度口径调仓：仅在调仓间隔到期、或空仓重新入场时
		#    重排 Top N（此前每天重排 → 平均持有 5 天、2033 笔高换手）。
		#    止损/止盈仍由 on_bar 每日检查（risk 不因调仓降频而放松）。
		do_rebalance = (
			not self._holdings
			or self._last_rebalance_date is None
			or self._trade_date_diff(self._last_rebalance_date, td) >= self.rebalance_interval
		)
		if do_rebalance:
			signals.extend(self.generate_entry_signals(td))
			signals.extend(self.generate_exit_signals(td))
			self._last_rebalance_date = td
		self._exited_today.clear()
		return signals

	# ── 模块1：开仓（双门开时买入 Top N 等权） ──
	def generate_entry_signals(self, td: str) -> List[TradingSignal]:
		"""买入：池内按 20 日动量评分（或市值最小）选 Top N 等权，单票 ≤5%、总仓 ≤80%。

		use_momentum=False 时为 M3 等权对照组（按市值最小取前 holdings 只，无动量）。
		"""
		signals: List[TradingSignal] = []
		if not self._pool:
			return signals
		if self.use_momentum:
			# 动量评分
			scored: List[tuple] = []
			for code in self._pool:
				df = self._data_cache.get(code)
				if df is None or len(df) < self.momentum_window + 2:
					continue
				mom = self._momentum(code, df)
				if mom is None:
					continue
				scored.append((code, mom))
			scored.sort(key=lambda x: x[1], reverse=True)
			targets = [c for c, _ in scored[: self.holdings]]
		else:
			# 等权对照组：池已按 circ_mv 升序，直接取最小前 holdings 只
			targets = [c for c in self._pool[: self.holdings] if c in self._data_cache]

		# 现有持仓中跌出 Top → 由 generate_exit_signals 处理
		weight = self.max_single_weight
		for code in targets:
			if code in self._holdings or code in self._exited_today:
				continue  # 当日已止损/清仓的股票不立刻买回（防同日卖出又买入的重复信号）
			df = self._data_cache.get(code)
			price = float(df["close"].iloc[-1]) if df is not None and len(df) else 0.0
			if price <= 0:
				continue
			sig = self._make_entry_signal(code, weight, price, td, reason="微盘双门开买入")
			if sig:
				signals.append(sig)
				self._holdings[code] = {
					"entry_price": price, "entry_date": td, "peak": price,
					"entry_weight": weight,
				}
		return signals

	# ── 模块2：平仓（跌出 Top / 门控已处理） ──
	def generate_exit_signals(self, td: str) -> List[TradingSignal]:
		"""卖出：现有持仓跌出 Top holdings 或总仓超限。"""
		signals: List[TradingSignal] = []
		if not self._pool:
			return signals
		if self.use_momentum:
			# 池内动量 Top N
			scored: List[tuple] = []
			for code in self._pool:
				df = self._data_cache.get(code)
				if df is None or len(df) < self.momentum_window + 2:
					continue
				mom = self._momentum(code, df)
				if mom is not None:
					scored.append((code, mom))
			scored.sort(key=lambda x: x[1], reverse=True)
			keep = {c for c, _ in scored[: self.holdings]}
		else:
			# 等权对照组：持仓目标 = 市值最小前 holdings 只
			keep = set(self._pool[: self.holdings])

		for code in list(self._holdings.keys()):
			if code in keep:
				continue
			df = self._data_cache.get(code)
			price = float(df["close"].iloc[-1]) if df is not None and len(df) else 0.0
			sig = self._make_exit_signal(code, price, f"跌出 Top{self.holdings} 调出")
			if sig:
				signals.append(sig)
				self._holdings.pop(code, None)
		return signals

	# ── 模块3：止盈止损（on_bar 即时检查） ──
	def check_stop_profit_stop_loss(self, bar: BarData) -> List[TradingSignal]:
		"""单票止损 -10%；浮盈 30% 减半。"""
		signals: List[TradingSignal] = []
		code = bar.ts_code
		h = self._holdings.get(code)
		if not h:
			return signals
		close = float(bar.close or 0)
		entry = float(h.get("entry_price", 0) or 0)
		if close <= 0 or entry <= 0:
			return signals
		# 止损
		if close <= entry * (1 + self.stop_loss):
			sig = self._make_exit_signal(code, close, f"止损: 亏损 ≥{-self.stop_loss:.0%}")
			if sig:
				signals.append(sig)
				self._holdings.pop(code, None)
				self._exited_today.add(code)  # 当日不再买回
			return signals
		# 减半（浮盈 30%）
		h["peak"] = max(float(h.get("peak", entry) or entry), close)
		gain = close / entry - 1
		if gain >= self.profit_reduce and "reduced" not in h:
			h["reduced"] = True
			sig = self._make_partial_exit(code, close, f"浮盈 {gain:.0%} ≥{self.profit_reduce:.0%} 减半")
			if sig:
				signals.append(sig)
		return signals

	# ── 模块4：仓位（等权 Top N） ──
	def calculate_position_size(self, code: str, price: float, capital: float) -> int:
		if price <= 0:
			return 0
		amount = min(self.max_single_weight, self.max_total_weight / max(len(self._holdings) + 1, 1)) * capital
		return max(int(amount / price / 100) * 100, 100)

	# ───────────────────────── 选池 / 门控 / 指数 ─────────────────────────
	def _rebuild_pool(self, td: str) -> None:
		"""月度重选：最近月末 circ_mv 快照 + 流动性（缓存近 20 日均额）→ 市值最小 pool_size 只。"""
		# 最近月末快照
		snap_dates = sorted(self._circ_mv_snapshots.keys())
		chosen = None
		for d in snap_dates:
			if d <= td:
				chosen = d
			else:
				break
		if chosen is None:
			return
		snapshot = self._circ_mv_snapshots[chosen]

		cands = []
		for code, circ_mv in snapshot.items():
			if circ_mv > self.max_circ_mv:
				continue
			df = self._data_cache.get(code)
			if df is None or len(df) < 21:
				continue
			# 流动性：近 20 日均额 ≥ min_amount_wan 万元（amount 千元 → 万元）
			amt20 = float(df["amount"].astype(float).tail(20).mean()) / 10.0 if "amount" in df.columns else 0.0
			if amt20 < self.min_amount_wan:
				continue
			cands.append((code, circ_mv))
		cands.sort(key=lambda x: x[1])
		self._pool = [c for c, _ in cands[: self.pool_size]]
		logger.info(f"微盘池重选({td}): {len(self._pool)} 只（快照 {chosen}）")

	def _check_market_gate(self, td: str) -> bool:
		"""门控1：大盘 regime BULL。"""
		if not self.use_market_gate:
			return True
		return self._regime_by_date.get(td, "NEUTRAL") == "BULL"

	def _check_micro_gate(self) -> bool:
		"""门控2：自建微盘指数 > MA20。"""
		if not self.use_micro_gate:
			return True
		hist = self._micro_nav_history
		if len(hist) < self.micro_ma_window:
			return True  # 样本不足放行（预热期）
		ma = sum(hist[-self.micro_ma_window:]) / self.micro_ma_window
		return self._micro_nav > ma

	def _update_micro_nav(self, td: str) -> None:
		"""微盘指数：池内股票当日等权收益累积。"""
		if not self._pool:
			self._micro_nav_history.append(self._micro_nav)
			return
		ret_sum, cnt = 0.0, 0
		for code in self._pool:
			df = self._data_cache.get(code)
			if df is None or len(df) < 2:
				continue
			closes = df["close"].astype(float)
			if closes.iloc[-2] > 0:
				ret_sum += closes.iloc[-1] / closes.iloc[-2] - 1
				cnt += 1
		if cnt > 0:
			self._micro_nav *= (1 + ret_sum / cnt)
		self._micro_nav_history.append(self._micro_nav)

	def _close_all(self, td: str, reason: str) -> List[TradingSignal]:
		"""整体空仓（门控关闭）。"""
		signals: List[TradingSignal] = []
		for code in list(self._holdings.keys()):
			df = self._data_cache.get(code)
			price = float(df["close"].iloc[-1]) if df is not None and len(df) else 0.0
			sig = self._make_exit_signal(code, price, reason)
			if sig:
				signals.append(sig)
			self._holdings.pop(code, None)
			self._exited_today.add(code)
		return signals

	def _momentum(self, code: str, df: pd.DataFrame) -> Optional[float]:
		"""20 日动量（简单收益率）。"""
		try:
			closes = df["close"].astype(float)
			if len(closes) <= self.momentum_window or closes.iloc[-self.momentum_window - 1] <= 0:
				return None
			return closes.iloc[-1] / closes.iloc[-self.momentum_window - 1] - 1
		except Exception:
			return None

	def _trade_date_diff(self, d1: str, d2: str) -> int:
		"""交易日差（用 regime 日历近似）。"""
		if not d1 or not d2 or d1 >= d2:
			return 0
		dates = [d for d in self._regime_by_date if d1 <= d <= d2]
		return len(dates) - 1 if dates else 0

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
		if len(df) and str(df["trade_date"].iloc[-1])[:10] == td:
			df.iloc[-1] = list(row.values())
		else:
			self._data_cache[code] = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
		if len(self._data_cache[code]) > self.lookback_days + 20:
			self._data_cache[code] = self._data_cache[code].tail(self.lookback_days + 20).reset_index(drop=True)

	def _make_entry_signal(self, code: str, weight: float, price: float, td: str, reason: str) -> Optional[TradingSignal]:
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
			quantity=0,
			amount=0.0,
			confidence=0.7,
			reason=f"微盘: {reason}",
			timestamp=datetime.now(),
			order_mode="close",
		)
		sig.weight = weight
		sig.stop_loss_price = price * (1 + self.stop_loss)  # 每笔开仓必须带止损
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
			reason=f"微盘: {reason}",
			timestamp=datetime.now(),
			order_mode="close",
		)
		sig.weight = 1.0
		return sig

	def _make_partial_exit(self, code: str, price: float, reason: str) -> Optional[TradingSignal]:
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
			reason=f"微盘: {reason}",
			timestamp=datetime.now(),
			order_mode="close",
		)
		sig.weight = 0.5  # 减半
		return sig

	@staticmethod
	def _gen_id() -> str:
		import uuid
		return str(uuid.uuid4())
