# -*- coding: utf-8 -*-
"""
全球资产轮动策略 V2 — 激进进攻版
核心定位：高弹性ETF短周期动量轮动，目标年化40%-60%
改造点：
  1. 资产池仅保留最高弹性赛道ETF，放弃大类分散
  2. 短周期动量（20日）+ 高频调仓（3交易日），捕捉波段行情
  3. 单标的满仓集中，最大化最强趋势的收益贡献
  4. R²仅作过滤不乘积削弱，保留脉冲行情的高收益
  5. 新增移动止盈，让利润奔跑；8%硬止损严格控亏
  6. 修复原版入场价重置、skip_window失效、动量口径不一致三大bug
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd
from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

# 权重变化阈值：新旧权重相对差异超过此比例才触发调权信号
_WEIGHT_CHANGE_THRESHOLD = 0.20


class GlobalRotationV2AggressiveStrategy(BaseStrategy):
	"""
	全球资产轮动 V2 激进进攻版
	策略类型：ROTATION
	决策频率：每3交易日调仓 + 日频止损/止盈
	"""
	strategy_type: StrategyType = StrategyType.ROTATION

	# =========================================================================
	# 高弹性进攻资产池（6只，年化波动30%-45%）
	# 仅保留趋势性最强、波段弹性最大的赛道，放弃低波动分散资产
	# =========================================================================
	ASSET_POOL: List[str] = [
		"512480.SH",  # 半导体ETF  科技成长核心，弹性拉满
		"512880.SH",  # 证券ETF    A股牛市放大器
		"513050.SH",  # 中概互联   跨境高弹性龙头
		"159915.SZ",  # 创业板ETF  A股成长弹性代表
		"513100.SH",  # 纳指100    美股科技长牛基底
		"513180.SH",  # 恒生科技ETF 港股科技高弹性
	]

	# 美股配对标的（仅纳指一只，保留结构）
	US_PAIR: List[str] = []

	# 防御资产（仅止损后临时落脚，不参与动量排名）
	CASH_ANCHOR: str = "511990.SH"   # 货基
	DEFENSE_ASSET: str = "511260.SH"  # 十年国债

	# =========================================================================
	# 激进版默认参数
	# =========================================================================
	DEFAULT_PARAMS: Dict[str, Any] = {
		# 动量核心参数
		"momentum_window": 20,            # 动量窗口：20个交易日≈1个月
		"skip_window": 1,                 # 跳过最近1天，降低滞后性
		"max_holdings": 1,                # 仅持有动量排名第1的标的，极致集中
		"max_single_weight": 1.0,         # 单标的满仓上限
		# 风控参数
		"stop_loss": -0.08,               # 硬止损：单笔最大亏损8%
		"trailing_stop_start": 0.15,      # 移动止盈启动阈值：浮盈15%
		"trailing_stop_drawdown": 0.06,   # 移动止盈回撤幅度：从高点回落6%
		# 因子参数
		"r2_filter_threshold": 0.2,       # R²过滤阈值，低于则剔除（仅过滤不乘积）
		"crash_penalty_threshold": -0.08, # 尾端跳水惩罚阈值：单日跌超8%
		"crash_penalty_factor": 0.7,      # 跳水惩罚系数：得分打7折
		# 运行参数
		"min_history": 25,                # 预热最少天数
		"use_absolute_momentum": False,   # 默认关闭绝对动量门，永远满仓进攻
		"use_open_crash_filter": False,   # 默认关闭开盘暴跌过滤，激进做多
		"rebalance_frequency": 3,         # 每3个交易日调仓一次
		"verbose_logging": False,
	}

	def __init__(
			self,
			name: str = "全球资产轮动V2-激进版",
			strategy_type: StrategyType = StrategyType.ROTATION,
			parameters: Optional[Dict[str, Any]] = None,
	):
		merged = dict(self.DEFAULT_PARAMS)
		if parameters:
			merged.update(parameters)
		super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

		# 核心参数提取
		self.momentum_window: int = int(merged["momentum_window"])
		self.skip_window: int = int(merged["skip_window"])
		self.max_holdings: int = int(merged["max_holdings"])
		self.max_single_weight: float = float(merged["max_single_weight"])
		self.stop_loss: float = float(merged["stop_loss"])
		self.trailing_stop_start: float = float(merged["trailing_stop_start"])
		self.trailing_stop_drawdown: float = float(merged["trailing_stop_drawdown"])
		self.r2_filter_threshold: float = float(merged["r2_filter_threshold"])
		self.crash_penalty_threshold: float = float(merged["crash_penalty_threshold"])
		self.crash_penalty_factor: float = float(merged["crash_penalty_factor"])
		self.min_history: int = int(merged["min_history"])
		self.use_absolute_momentum: bool = bool(merged.get("use_absolute_momentum", False))
		self.use_open_crash_filter: bool = bool(merged.get("use_open_crash_filter", False))
		self.rebalance_frequency = merged.get("rebalance_frequency", 3)
		self.verbose_logging: bool = bool(merged.get("verbose_logging", False))

		# 运行时状态
		self._last_rebalance_days: int = 0
		self._last_trade_date: str = ""
		self._current_holdings: Dict[str, float] = {}
		self._entry_prices: Dict[str, float] = {}       # 首次建仓入场价，永不重置
		self._peak_highs: Dict[str, float] = {}         # 持仓阶段最高价，用于移动止盈
		self._data_cache: Dict[str, pd.DataFrame] = {}
		self._cache_last_date: Dict[str, str] = {}
		self._stopped_today: Set[str] = set()           # 当日止损/止盈黑名单
		self._bar_count: int = 0
		self._warmup_warned: bool = False
		self._reset_warned: Set[str] = set()

		logger.info(
			f"激进版轮动策略初始化: {name}, "
			f"进攻池={len(self.ASSET_POOL)}只, "
			f"动量窗口={self.momentum_window}天, "
			f"调仓频率=每{self.rebalance_frequency}交易日, "
			f"硬止损={self.stop_loss:.0%}, "
			f"移动止盈={self.trailing_stop_start:.0%}启动 / 回撤{self.trailing_stop_drawdown:.0%}"
		)

	# =========================================================================
	# 生命周期
	# =========================================================================
	def on_init(self) -> None:
		errors = self._validate_params()
		if errors:
			raise ValueError(f"参数校验失败: {'; '.join(errors)}")
		self._universe = list(dict.fromkeys(self.ASSET_POOL + [self.CASH_ANCHOR, self.DEFENSE_ASSET]))
		logger.info(f"激进版策略初始化完成, universe={len(self._universe)}只")

	async def on_start(self) -> None:
		self._last_rebalance_days = 0
		self._last_trade_date = ""
		self._bar_count = 0
		self._current_holdings.clear()
		self._entry_prices.clear()
		self._peak_highs.clear()
		self._data_cache.clear()
		self._cache_last_date.clear()
		self._reset_warned.clear()
		self._stopped_today.clear()
		self._warmup_warned = False
		loaded = await self._preload_history()
		logger.info(f"激进版策略已启动，预热数据{loaded}行")

	async def _preload_history(self) -> int:
		session_factory = getattr(self, "_db_session_factory", None)
		if session_factory is None:
			return 0
		from datetime import date as _dt
		from modules.strategy.engines.data_feed_engine import DataFeedEngine as _DFE
		end_date = _dt.today()
		start_date = _dt(2018, 1, 1)
		try:
			async with session_factory() as db:
				engine = _DFE(db)
				symbols = list(dict.fromkeys(self._universe))
				df = await engine.load_historical_data(
					symbols=symbols,
					start_date=start_date.isoformat(),
					end_date=end_date.isoformat(),
				)
				if not df.empty:
					for ts_code in df["ts_code"].unique():
						sub = df[df["ts_code"] == ts_code].copy().sort_values("trade_date").reset_index(drop=True)
						self._data_cache[ts_code] = sub
						self._cache_last_date[ts_code] = str(sub["trade_date"].iloc[-1])[:10] if len(sub) > 0 else ""
					return len(df)
		except Exception as e:
			logger.warning(f"历史预热失败: {e}")
		return 0

	def on_stop(self) -> None:
		self._data_cache.clear()
		self._cache_last_date.clear()
		self._current_holdings.clear()
		self._entry_prices.clear()
		self._peak_highs.clear()
		self._stopped_today.clear()
		logger.info("激进版策略已停止")

	# =========================================================================
	# 核心入口
	# =========================================================================
	def on_bar(self, bar: BarData) -> List[TradingSignal]:
		try:
			if bar.ts_code not in self._universe:
				return []
			self._append_data(bar.ts_code, bar)
			trade_date = str(getattr(bar, "trade_date", "") or "")[:10]
			if trade_date:
				self._last_trade_date = trade_date
		except Exception as e:
			logger.error(f"on_bar异常: {bar.ts_code}: {e}", exc_info=True)
		return []

	def _should_rebalance(self) -> bool:
		interval = int(self.rebalance_frequency)
		return self._bar_count - self._last_rebalance_days >= interval

	def _mark_rebalanced(self) -> None:
		self._last_rebalance_days = self._bar_count

	def on_bar_batch_end(self, trade_date: Any = None) -> List[TradingSignal]:
		signals: List[TradingSignal] = []
		try:
			td = str(trade_date)[:10] if trade_date else self._last_trade_date
			if not td:
				return signals
			self._last_trade_date = td
			self._bar_count += 1
			self._stopped_today.clear()

			# Step1: 日频风控检查（硬止损 + 移动止盈）
			stop_signals = self._daily_risk_check()
			signals.extend(stop_signals)

			# Step2: 定期调仓
			if self._should_rebalance():
				rebalance_signals = self._run_rebalance()
				signals.extend(rebalance_signals)
				self._mark_rebalanced()
		except Exception as e:
			logger.error(f"on_bar_batch_end异常: {e}", exc_info=True)
		return signals

	# =========================================================================
	# 日频风控：硬止损 + 移动止盈
	# =========================================================================
	def _daily_risk_check(self) -> List[TradingSignal]:
		signals: List[TradingSignal] = []
		for code in list(self._current_holdings.keys()):
			entry_price = self._entry_prices.get(code)
			if entry_price is None or entry_price <= 0:
				continue
			current_price = self._get_price(code)
			if current_price <= 0 or not self._is_fresh(code):
				continue

			# 更新阶段高点
			peak = self._peak_highs.get(code, entry_price)
			if current_price > peak:
				peak = current_price
				self._peak_highs[code] = peak

			pnl = current_price / entry_price - 1.0

			# 1. 硬止损（最高优先级）
			if pnl <= self.stop_loss:
				exit_sig = self._make_exit_signal(
					code,
					reason=f"硬止损: 浮亏{pnl:.1%}",
					signal_type=SignalType.STOP_LOSS,
				)
				if exit_sig:
					signals.append(exit_sig)
					self._clear_holding(code)
					self._stopped_today.add(code)
					logger.warning(f"硬止损触发: {code} 入场{entry_price:.2f} 现价{current_price:.2f} 浮亏{pnl:.1%}")
				continue

			# 2. 移动止盈
			if pnl >= self.trailing_stop_start:
				drawdown = (peak - current_price) / peak
				if drawdown >= self.trailing_stop_drawdown:
					exit_sig = self._make_exit_signal(
						code,
						reason=f"移动止盈: 最高浮盈{peak/entry_price-1:.1%} 回撤{drawdown:.1%}",
						signal_type=SignalType.EXIT,
					)
					if exit_sig:
						signals.append(exit_sig)
						self._clear_holding(code)
						self._stopped_today.add(code)
						logger.info(f"移动止盈触发: {code} 高点{peak:.2f} 现价{current_price:.2f}")
		return signals

	def _clear_holding(self, code: str) -> None:
		"""清理持仓相关状态"""
		self._current_holdings.pop(code, None)
		self._entry_prices.pop(code, None)
		self._peak_highs.pop(code, None)

	# =========================================================================
	# 调仓主逻辑
	# =========================================================================
	def _run_rebalance(self) -> List[TradingSignal]:
		signals: List[TradingSignal] = []

		# 预热检查
		max_days = max((len(df) for df in self._data_cache.values()), default=0)
		if max_days < self.min_history:
			if not self._warmup_warned:
				self._warmup_warned = True
				logger.info(f"预热期: {max_days}/{self.min_history}天")
			return signals

		# Step1: 动量排名
		rankings = self._calc_momentum_rankings()
		if not rankings:
			logger.warning("无有效动量排名，跳过调仓")
			return signals

		# Step2: 绝对动量基准（统一使用对数回归口径）
		cash_score = self._calc_log_regression_momentum(self.CASH_ANCHOR) or 0.0

		# Step3: 确定防御资产
		defense_code = self._get_defense_asset(cash_score)

		# Step4: 生成目标仓位
		n_candidates = min(self.max_holdings, len(rankings))
		raw_slots: Dict[str, float] = {}

		for i in range(n_candidates):
			code, score = rankings[i]
			# 当日已止损/止盈 → 退守防御
			if code in self._stopped_today:
				raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
				continue
			# 开盘暴跌过滤（默认关闭）
			if self.use_open_crash_filter and self._is_open_crash(code):
				raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
				continue
			# 数据新鲜度检查
			if not self._is_fresh(code):
				raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
				continue
			# 绝对动量门
			if self.use_absolute_momentum and score <= cash_score:
				raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
				continue
			# 入选
			raw_slots[code] = raw_slots.get(code, 0.0) + 1.0

		# 兜底：全被过滤则全仓防御
		if sum(raw_slots.values()) <= 0:
			raw_slots = {defense_code: 1.0}

		# Step5: 计算目标权重
		target_weights = self._calc_target_weights(raw_slots)

		# Step6: 对比旧持仓生成信号
		old_holdings = self._current_holdings.copy()
		old_codes = set(old_holdings.keys())
		new_codes = set(target_weights.keys())

		# 退出不再持有的标的
		for code in old_codes - new_codes:
			exit_sig = self._make_exit_signal(code, reason="调仓退出")
			if exit_sig:
				signals.append(exit_sig)

		# 新建仓标的
		for code in new_codes - old_codes:
			if self._get_price(code) <= 0:
				continue
			entry_sig = self._make_entry_signal(code, target_weights[code], reason="调仓建仓")
			if entry_sig:
				signals.append(entry_sig)

		# 权重调整（仅差额调整，不全平全买）
		for code in old_codes & new_codes:
			old_w = old_holdings.get(code, 0.0)
			new_w = target_weights.get(code, 0.0)
			if old_w <= 0:
				continue
			rel_change = abs(new_w - old_w) / old_w
			if rel_change > _WEIGHT_CHANGE_THRESHOLD:
				# 先平旧仓，再建新仓（兼容框架信号模式）
				exit_sig = self._make_exit_signal(code, reason=f"权重调整: {old_w:.1%}→{new_w:.1%}")
				if exit_sig:
					signals.append(exit_sig)
				entry_sig = self._make_entry_signal(code, new_w, reason=f"权重调整")
				if entry_sig:
					signals.append(entry_sig)

		# 更新持仓状态
		self._current_holdings = target_weights.copy()
		# 【关键修复】仅新建仓标的写入入场价，已有持仓永不重置
		for code in new_codes:
			if code not in old_codes:
				price = self._get_price(code)
				if price > 0:
					self._entry_prices[code] = price
					self._peak_highs[code] = price
			else:
				# 已有持仓更新当日高点
				current_price = self._get_price(code)
				if current_price > self._peak_highs.get(code, 0):
					self._peak_highs[code] = current_price

		hold_str = ", ".join(f"{c}({w:.1%})" for c, w in target_weights.items())
		logger.info(f"调仓完成: 持仓=[{hold_str}] 信号={len(signals)}条")
		return signals

	def _calc_target_weights(self, raw_slots: Dict[str, float]) -> Dict[str, float]:
		total_slots = sum(raw_slots.values())
		target_weights: Dict[str, float] = {}
		for code, slots in raw_slots.items():
			w = slots / total_slots
			target_weights[code] = min(w, self.max_single_weight)

		# 处理单标上限截断后的权重再分配
		total_w = sum(target_weights.values())
		if 0 < total_w < 1.0:
			excess = 1.0 - total_w
			uncapped = [c for c in target_weights if target_weights[c] < self.max_single_weight]
			if uncapped:
				add = excess / len(uncapped)
				for c in uncapped:
					target_weights[c] = min(target_weights[c] + add, self.max_single_weight)
		return target_weights

	# =========================================================================
	# 动量计算（核心修复+改造）
	# =========================================================================
	def _calc_momentum_rankings(self) -> List[Tuple[str, float]]:
		# 美股双标处理（当前池内仅一只，保留结构）
		us_code = self._pick_us_etf()
		effective_pool = []
		for code in self.ASSET_POOL:
			if code in self.US_PAIR:
				if code == us_code:
					effective_pool.append(code)
			else:
				effective_pool.append(code)

		results = []
		for code in effective_pool:
			score = self._calc_log_regression_momentum(code)
			if score is not None:
				results.append((code, score))

		results.sort(key=lambda x: x[1], reverse=True)
		if self.verbose_logging:
			logger.info(f"动量排名: {[(c, f'{r:.2%}') for c, r in results[:3]]}")
		return results

	def _calc_log_regression_momentum(self, code: str) -> Optional[float]:
		"""
		【核心修复+改造】
		1. 正确跳过skip_window，修复原版区间错误
		2. R²仅作过滤，不乘积削弱收益，保留强趋势的高弹性
		3. 尾端跳水从直接剔除改为扣分制
		"""
		df = self._data_cache.get(code)
		if df is None:
			return None

		needed = self.momentum_window + self.skip_window
		if len(df) < needed:
			return None

		closes = df["close"].values.astype(np.float64)

		# 【修复】正确跳过最近skip_window天
		start_idx = -(self.momentum_window + self.skip_window)
		end_idx = -self.skip_window if self.skip_window > 0 else None
		valid = closes[start_idx:end_idx]

		# 数据有效性检查
		valid = valid[(valid > 0) & ~np.isnan(valid)]
		if len(valid) < self.momentum_window * 0.8:  # 至少80%有效数据
			return None

		try:
			log_prices = np.log(valid)
			n = len(log_prices)
			x = np.arange(n)
			weights = np.linspace(1, 2, n)  # 线性加权，近期权重更高
			slope, intercept = np.polyfit(x, log_prices, 1, w=weights)
			annualized = float(np.exp(slope * 250) - 1)

			# 计算R²
			residuals = log_prices - (slope * x + intercept)
			ss_res = float(np.sum(weights * residuals ** 2))
			y_mean = float(np.mean(log_prices))
			ss_tot = float(np.sum(weights * (log_prices - y_mean) ** 2))
			r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

			# 异常值过滤
			if annualized > 5.0 or annualized < -0.8:
				return None

			# 【改造】R²仅作过滤，不乘积
			if r2 < self.r2_filter_threshold:
				return None

			# 尾端跳水惩罚（近3日单日跌幅超过阈值，得分打折）
			if len(closes) >= 4:
				recent_daily = np.diff(closes[-4:]) / closes[-4:-1]
				if np.any(recent_daily < self.crash_penalty_threshold):
					annualized *= self.crash_penalty_factor

			return annualized
		except Exception as e:
			logger.debug(f"动量计算异常 {code}: {e}")
			return None

	def _pick_us_etf(self) -> Optional[str]:
		best_code = None
		best_avg = -1.0
		for code in self.US_PAIR:
			df = self._data_cache.get(code)
			if df is None or len(df) < 20:
				continue
			col = "amount" if "amount" in df.columns else "volume"
			avg_val = float(np.mean(df[col].values.astype(np.float64)[-20:]))
			if avg_val > best_avg:
				best_avg = avg_val
				best_code = code
		return best_code

	def _get_defense_asset(self, cash_score: float) -> str:
		defense_score = self._calc_log_regression_momentum(self.DEFENSE_ASSET)
		if defense_score is not None and defense_score > cash_score:
			return self.DEFENSE_ASSET
		return self.CASH_ANCHOR

	# =========================================================================
	# 辅助工具函数
	# =========================================================================
	def _is_open_crash(self, code: str) -> bool:
		df = self._data_cache.get(code)
		if df is None or len(df) < 2 or "open" not in df.columns:
			return False
		today_open = float(df["open"].iloc[-1])
		prev_close = float(df["close"].iloc[-2])
		if today_open <= 0 or prev_close <= 0:
			return False
		return (today_open - prev_close) / prev_close < -0.03

	def _is_fresh(self, code: str) -> bool:
		last_date = self._cache_last_date.get(code, "")
		return bool(last_date) and last_date == self._last_trade_date

	def _append_data(self, ts_code: str, bar: BarData) -> None:
		bar_date = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
		# 时序守卫
		last = self._cache_last_date.get(ts_code)
		if last and bar_date and bar_date <= last:
			df_old = self._data_cache.get(ts_code)
			if df_old is not None and "trade_date" in df_old.columns:
				kept = df_old[df_old["trade_date"].astype(str).str[:10] < bar_date]
				self._data_cache[ts_code] = kept.reset_index(drop=True)
				self._cache_last_date[ts_code] = str(kept["trade_date"].iloc[-1])[:10] if len(kept) else ""
			else:
				self._data_cache.pop(ts_code, None)
				self._cache_last_date.pop(ts_code, None)

		if ts_code not in self._data_cache:
			self._data_cache[ts_code] = pd.DataFrame(
				columns=["close", "volume", "amount", "open", "high", "low"]
			)

		new_row = pd.DataFrame([{
			"close": bar.close,
			"volume": bar.volume,
			"amount": getattr(bar, "amount", 0.0),
			"open": getattr(bar, "open", bar.close),
			"high": getattr(bar, "high", bar.close),
			"low": getattr(bar, "low", bar.close),
		}])
		self._data_cache[ts_code] = pd.concat([self._data_cache[ts_code], new_row], ignore_index=True)
		if bar_date:
			self._cache_last_date[ts_code] = bar_date

		# 限制缓存大小
		max_rows = self.momentum_window * 3 + 100
		if len(self._data_cache[ts_code]) > max_rows:
			self._data_cache[ts_code] = self._data_cache[ts_code].tail(max_rows).reset_index(drop=True)

	def _get_price(self, code: str) -> float:
		df = self._data_cache.get(code)
		if df is not None and len(df) > 0:
			val = float(df["close"].iloc[-1])
			return 0.0 if np.isnan(val) else val
		return 0.0

	# =========================================================================
	# 信号生成
	# =========================================================================
	def _make_entry_signal(self, ts_code: str, weight: float, reason: str = "") -> Optional[TradingSignal]:
		price = self._get_price(ts_code)
		if price <= 0:
			return None
		sig = TradingSignal(
			id=str(uuid.uuid4()),
			strategy_id=self.name,
			strategy_name=self.name,
			ts_code=ts_code,
			signal_type=SignalType.ENTRY,
			direction=SignalDirection.LONG,
			price=price,
			quantity=0,
			amount=1.0,
			confidence=0.85,
			reason=f"{ts_code}: {reason}",
			timestamp=datetime.now(),
		)
		sig.weight = weight
		return sig

	def _make_exit_signal(self, ts_code: str, reason: str = "", signal_type: SignalType = SignalType.EXIT) -> Optional[TradingSignal]:
		price = self._get_price(ts_code)
		if price <= 0:
			return None
		return TradingSignal(
			id=str(uuid.uuid4()),
			strategy_id=self.name,
			strategy_name=self.name,
			ts_code=ts_code,
			signal_type=signal_type,
			direction=SignalDirection.CLOSE_LONG,
			price=price,
			quantity=0,
			amount=0.0,
			confidence=0.9,
			reason=f"{ts_code}: {reason}",
			timestamp=datetime.now(),
		)

	# =========================================================================
	# 参数校验
	# =========================================================================
	def _validate_params(self) -> List[str]:
		errors = []
		if not (10 <= self.momentum_window <= 126):
			errors.append(f"momentum_window应在[10, 126]")
		if not (1 <= self.skip_window <= 10):
			errors.append(f"skip_window应在[1, 10]")
		if not (1 <= self.max_holdings <= 3):
			errors.append(f"激进版max_holdings建议[1, 3]")
		if not (0.3 <= self.max_single_weight <= 1.0):
			errors.append(f"max_single_weight应在[0.3, 1.0]")
		if not (-0.15 <= self.stop_loss <= -0.03):
			errors.append(f"stop_loss应在[-15%, -3%]")
		required_min = self.momentum_window + self.skip_window
		if self.min_history < required_min:
			errors.append(f"min_history必须≥{required_min}")
		return errors

	# =========================================================================
	# 查询接口
	# =========================================================================
	def get_holdings(self) -> List[str]:
		return sorted(self._current_holdings.keys())

	def get_parameters(self) -> dict:
		return {
			"strategy_version": "V2-Aggressive",
			"momentum_window": self.momentum_window,
			"skip_window": self.skip_window,
			"max_holdings": self.max_holdings,
			"max_single_weight": self.max_single_weight,
			"stop_loss": self.stop_loss,
			"trailing_stop_start": self.trailing_stop_start,
			"trailing_stop_drawdown": self.trailing_stop_drawdown,
			"use_absolute_momentum": self.use_absolute_momentum,
			"rebalance_frequency": self.rebalance_frequency,
			"asset_pool_size": len(self.ASSET_POOL),
			"current_holding_count": len(self._current_holdings),
		}