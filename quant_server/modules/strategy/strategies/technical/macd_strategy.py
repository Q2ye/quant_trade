# -*- coding: utf-8 -*-
"""
MACD策略 (MACD Strategy)

策略逻辑：
- MACD金叉（DIFF从下方穿越DEA）时产生买入信号
- MACD死叉（DIFF从上方穿越DEA）时产生卖出信号
- MACD柱状图由负转正时也视为买入信号
- MACD柱状图由正转负时也视为卖出信号

策略参数：
- fast_period: 快速EMA周期（默认12）
- slow_period: 慢速EMA周期（默认26）
- signal_period: 信号线周期（默认9）
- position_ratio: 开仓比例（默认0.1）
"""
import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd

from modules.strategy.constants import (
	StrategyType,
	SignalDirection,
	SignalType,
)
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import (
	TechnicalStrategy,
	BarData,
)

logger = logging.getLogger(__name__)


class MACDStrategy(TechnicalStrategy):
	"""
	MACD策略

	基于MACD指标的交叉和柱状图变化来判断交易信号
	"""

	def __init__ (
			self,
			name: str = "MACD Strategy",
			strategy_type: StrategyType = StrategyType.TECHNICAL,
			parameters: Optional[dict] = None,
	):
		# 默认参数
		default_params = {
			"fast_period": 12,  # 快速EMA周期
			"slow_period": 26,  # 慢速EMA周期
			"signal_period": 9,  # 信号线周期
			"position_ratio": 0.1,  # 开仓比例
			"stop_loss": 0.05,  # 止损比例
			"take_profit": 0.15,  # 止盈比例
		}

		# 合并参数
		if parameters:
			default_params.update(parameters)

		super().__init__(
			name=name,
			strategy_type=strategy_type,
			parameters=default_params,
		)

		self.fast_period = default_params["fast_period"]
		self.slow_period = default_params["slow_period"]
		self.signal_period = default_params["signal_period"]
		self.position_ratio = default_params["position_ratio"]
		self.stop_loss = default_params["stop_loss"]
		self.take_profit = default_params["take_profit"]

		# 内部状态
		self._price_data: pd.DataFrame = pd.DataFrame()
		self._last_macd: float = 0.0  # 上一个MACD值

	def on_init (self) -> None:
		"""策略初始化"""
		logger.info(
			f"初始化MACD策略: fast={self.fast_period}, "
			f"slow={self.slow_period}, signal={self.signal_period}"
		)

	def on_bar (self, bar: BarData) -> List[TradingSignal]:
		"""
		收到K线数据时调用

		Args:
			bar: K线数据

		Returns:
			交易信号列表
		"""
		signals = []

		# 更新数据
		self._update_price_data(bar)

		# 检查数据是否足够
		min_required = max(self.fast_period, self.slow_period, self.signal_period) + 5
		if len(self._price_data) < min_required:
			return signals

		# 计算MACD
		df = self._price_data.copy()
		df["ema_fast"] = df["close"].ewm(span=self.fast_period, adjust=False).mean()
		df["ema_slow"] = df["close"].ewm(span=self.slow_period, adjust=False).mean()
		df["macd"] = df["ema_fast"] - df["ema_slow"]
		df["signal"] = df["macd"].ewm(span=self.signal_period, adjust=False).mean()
		df["histogram"] = df["macd"] - df["signal"]

		# 获取最新数据
		current_row = df.iloc[-1]
		prev_row = df.iloc[-2]
		prev_2_row = df.iloc[-3] if len(df) > 2 else None

		# 获取当前持仓
		current_position = self.get_position(bar.ts_code)

		# MACD交叉信号判断
		# 金叉：MACD从下方穿越信号线
		if (
				prev_row["macd"] <= prev_row["signal"]
				and current_row["macd"] > current_row["signal"]
		):
			if not current_position or current_position.side.value == "short":
				signal = self._create_signal(
					ts_code=bar.ts_code,
					direction=SignalDirection.LONG,
					signal_type=SignalType.ENTRY,
					price=bar.close,
					reason=(
						f"MACD金叉: DIFF={current_row['macd']:.4f}, "
						f"DEA={current_row['signal']:.4f}, "
						f"MACD柱={current_row['histogram']:.4f}"
					),
					confidence=0.85,
				)
				signals.append(signal)

		# 死叉：MACD从上方穿越信号线
		elif (
				prev_row["macd"] >= prev_row["signal"]
				and current_row["macd"] < current_row["signal"]
		):
			if current_position and current_position.side.value == "long":
				signal = self._create_signal(
					ts_code=bar.ts_code,
					direction=SignalDirection.CLOSE_LONG,
					signal_type=SignalType.EXIT,
					price=bar.close,
					reason=(
						f"MACD死叉: DIFF={current_row['macd']:.4f}, "
						f"DEA={current_row['signal']:.4f}"
					),
					confidence=0.85,
				)
				signals.append(signal)

		# MACD柱状图由负转正（零轴金叉）
		elif (
				prev_2_row is not None
				and prev_2_row["histogram"] < 0
				and prev_row["histogram"] < 0
				and current_row["histogram"] > 0
		):
			if not current_position:
				signal = self._create_signal(
					ts_code=bar.ts_code,
					direction=SignalDirection.LONG,
					signal_type=SignalType.ENTRY,
					price=bar.close,
					reason=f"MACD柱转零轴上: {current_row['histogram']:.4f}",
					confidence=0.7,
				)
				signals.append(signal)

		# MACD柱状图由正转负（零轴死叉）
		elif (
				prev_2_row is not None
				and prev_2_row["histogram"] > 0
				and prev_row["histogram"] > 0
				and current_row["histogram"] < 0
		):
			if current_position and current_position.side.value == "long":
				signal = self._create_signal(
					ts_code=bar.ts_code,
					direction=SignalDirection.CLOSE_LONG,
					signal_type=SignalType.EXIT,
					price=bar.close,
					reason=f"MACD柱转零轴下: {current_row['histogram']:.4f}",
					confidence=0.7,
				)
				signals.append(signal)

		# 止盈止损检查
		if current_position:
			pnl_rate = (bar.close - current_position.avg_cost) / current_position.avg_cost

			# 止损
			if pnl_rate <= -self.stop_loss:
				signal = self._create_signal(
					ts_code=bar.ts_code,
					direction=SignalDirection.CLOSE_LONG,
					signal_type=SignalType.STOP_LOSS,
					price=bar.close,
					reason=f"止损: 亏损{pnl_rate * 100:.1f}%",
					confidence=1.0,
				)
				signals.append(signal)

			# 止盈
			elif pnl_rate >= self.take_profit:
				signal = self._create_signal(
					ts_code=bar.ts_code,
					direction=SignalDirection.CLOSE_LONG,
					signal_type=SignalType.TAKE_PROFIT,
					price=bar.close,
					reason=f"止盈: 盈利{pnl_rate * 100:.1f}%",
					confidence=1.0,
				)
				signals.append(signal)

		# 更新上一个MACD值
		self._last_macd = current_row["macd"]

		return signals

	def _update_price_data (self, bar: BarData) -> None:
		"""更新价格数据"""
		# 创建新行
		new_row = pd.DataFrame([{
			"ts_code": bar.ts_code,
			"trade_date": bar.trade_date,
			"trade_time": bar.trade_time,
			"open": bar.open,
			"high": bar.high,
			"low": bar.low,
			"close": bar.close,
			"volume": bar.volume,
			"amount": bar.amount,
		}])

		# 追加到数据框
		self._price_data = pd.concat([self._price_data, new_row], ignore_index=True)

		# 保持数据量在合理范围
		max_bars = max(self.fast_period, self.slow_period, self.signal_period) * 3
		if len(self._price_data) > max_bars:
			self._price_data = self._price_data.tail(max_bars).reset_index(drop=True)

	def _create_signal (
			self,
			ts_code: str,
			direction: SignalDirection,
			signal_type: SignalType,
			price: float,
			reason: str,
			confidence: float = 1.0,
	) -> TradingSignal:
		"""创建交易信号"""
		# 计算数量
		quantity = 0
		if self.context:
			amount = self.context.available_capital * self.position_ratio
			quantity = int(amount / price / 100) * 100  # 整手交易
			quantity = max(quantity, 100)  # 最小100股

		signal = TradingSignal(
			id=f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
			strategy_id=self.context.strategy_id if self.context else 0,
			strategy_name=self.name,
			ts_code=ts_code,
			signal_type=signal_type,
			direction=direction,
			price=price,
			quantity=quantity,
			amount=price * quantity,
			confidence=confidence,
			reason=reason,
			timestamp=datetime.now(),
		)

		return signal

	def get_parameters (self) -> dict:
		"""获取策略参数"""
		return {
			"fast_period": self.fast_period,
			"slow_period": self.slow_period,
			"signal_period": self.signal_period,
			"position_ratio": self.position_ratio,
			"stop_loss": self.stop_loss,
			"take_profit": self.take_profit,
		}
