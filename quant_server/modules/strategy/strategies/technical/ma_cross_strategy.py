# -*- coding: utf-8 -*-
"""
双均线策略 (MA Cross Strategy)

策略逻辑：
- 当短期均线上穿长期均线时，产生买入信号（金叉）
- 当短期均线下穿长期均线时，产生卖出信号（死叉）

策略参数：
- fast_period: 短期均线周期（默认5）
- slow_period: 长期均线周期（默认20）
- volume_ma_period: 成交量均线周期（默认20）
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


class MACrossStrategy(TechnicalStrategy):
	"""
	双均线策略

	基于短期和长期均线的交叉来判断趋势方向
	"""

	def __init__ (
			self,
			name: str = "MA Cross Strategy",
			strategy_type: StrategyType = StrategyType.TECHNICAL,
			parameters: Optional[dict] = None,
	):
		# 默认参数
		default_params = {
			"fast_period": 5,  # 短期均线周期
			"slow_period": 20,  # 长期均线周期
			"volume_ma_period": 20,  # 成交量均线周期
			"min_volume": 1000000,  # 最小成交量
			"position_ratio": 0.1,  # 每次开仓比例
			"stop_loss": 0.05,  # v2.4: 止损比例
			"take_profit": 0.15,  # v2.4: 止盈比例
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
		self.volume_ma_period = default_params["volume_ma_period"]
		self.min_volume = default_params["min_volume"]
		self.position_ratio = default_params["position_ratio"]

		# 内部状态
		self._price_data: pd.DataFrame = pd.DataFrame()
		self._last_signal: Optional[str] = None  # 'long' or 'short'

	def on_init (self) -> None:
		"""策略初始化"""
		logger.info(f"初始化双均线策略: fast={self.fast_period}, slow={self.slow_period}")

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
		if len(self._price_data) < self.slow_period:
			return signals

		# 计算均线
		df = self._price_data.copy()
		df[f"ma_fast"] = df["close"].rolling(window=self.fast_period).mean()
		df[f"ma_slow"] = df["close"].rolling(window=self.slow_period).mean()
		df[f"volume_ma"] = df["volume"].rolling(window=self.volume_ma_period).mean()

		# 获取最新数据
		current_row = df.iloc[-1]
		prev_row = df.iloc[-2] if len(df) > 1 else None

		# 获取当前持仓
		current_position = self.get_position(bar.ts_code)

		# 交易信号判断
		if prev_row is not None:
			# 金叉：短期均线从下方穿过长期均线
			if (
					prev_row[f"ma_fast"] <= prev_row[f"ma_slow"]
					and current_row[f"ma_fast"] > current_row[f"ma_slow"]
			):
				# 检查成交量
				if current_row["volume"] > self.min_volume and current_row["volume"] > current_row["volume_ma"] * 0.5:
					if not current_position or current_position.side.value == "short":
						signal = self._create_signal(
							ts_code=bar.ts_code,
							direction=SignalDirection.LONG,
							signal_type=SignalType.ENTRY,
							price=bar.close,
							reason=f"金叉: MA{self.fast_period}={current_row[f'ma_fast']:.2f} > MA{self.slow_period}={current_row[f'ma_slow']:.2f}",
							confidence=0.8,
						)
						signals.append(signal)
						self._last_signal = "long"

			# 死叉：短期均线从上方穿过长期均线
			elif (
					prev_row[f"ma_fast"] >= prev_row[f"ma_slow"]
					and current_row[f"ma_fast"] < current_row[f"ma_slow"]
			):
				if current_position and current_position.side.value == "long":
					signal = self._create_signal(
						ts_code=bar.ts_code,
						direction=SignalDirection.CLOSE_LONG,
						signal_type=SignalType.EXIT,
						price=bar.close,
						reason=f"死叉: MA{self.fast_period}={current_row[f'ma_fast']:.2f} < MA{self.slow_period}={current_row[f'ma_slow']:.2f}",
						confidence=0.8,
					)
					signals.append(signal)
					self._last_signal = "short"

		# 止盈止损检查
		if current_position:
			pnl_rate = (bar.close - current_position.avg_cost) / current_position.avg_cost

			# 止损
			if pnl_rate <= -self.parameters.get("stop_loss", 0.05):  # 止损
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
			elif pnl_rate >= self.parameters.get("take_profit", 0.15):  # 止盈
				signal = self._create_signal(
					ts_code=bar.ts_code,
					direction=SignalDirection.CLOSE_LONG,
					signal_type=SignalType.TAKE_PROFIT,
					price=bar.close,
					reason=f"止盈: 盈利{pnl_rate * 100:.1f}%",
					confidence=1.0,
				)
				signals.append(signal)

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
		max_bars = self.slow_period * 3
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
			"volume_ma_period": self.volume_ma_period,
			"min_volume": self.min_volume,
			"position_ratio": self.position_ratio,
		}
