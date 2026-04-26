# -*- coding: utf-8 -*-
"""
均值回归策略
基于均值回归原理的Alpha策略，适用于震荡市
"""

import logging
from typing import Dict, List, Optional, Any

import numpy as np

from quant_server.core.engines.types.entities import BarData
from quant_server.modules.strategy.constants import StrategyType, SignalDirection, SignalType
from quant_server.modules.strategy.models import TradingSignal
from quant_server.modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
	"""
	均值回归策略类

	基于均值回归原理，当价格偏离均值一定幅度时进行反向交易：
	- 当价格低于均值一定幅度时买入
	- 当价格高于均值一定幅度时卖出
	- 支持布林带、RSI、Z-Score等多种均值回归指标
	"""

	def __init__ (
			self,
			name: str,
			strategy_type: StrategyType = StrategyType.MEAN_REVERSION,
			parameters: Optional[Dict[str, Any]] = None
	):
		"""
		初始化均值回归策略

		Args:
			name: 策略名称
			strategy_type: 策略类型
			parameters: 策略参数
		"""
		super().__init__(name, strategy_type, parameters)

		# 策略参数
		self.lookback_period = self.parameters.get('lookback_period', 20)
		self.std_dev_threshold = self.parameters.get('std_dev_threshold', 2.0)
		self.rsi_period = self.parameters.get('rsi_period', 14)
		self.rsi_oversold = self.parameters.get('rsi_oversold', 30)
		self.rsi_overbought = self.parameters.get('rsi_overbought', 70)
		self.position_size = self.parameters.get('position_size', 0.1)
		self.stop_loss = self.parameters.get('stop_loss', 0.05)
		self.take_profit = self.parameters.get('take_profit', 0.1)

		# 数据缓存
		self.price_history: Dict[str, List[float]] = {}
		self.entry_prices: Dict[str, float] = {}
		self.position_directions: Dict[str, SignalDirection] = {}

		# 技术指标缓存
		self.ma_cache: Dict[str, float] = {}
		self.std_cache: Dict[str, float] = {}
		self.rsi_cache: Dict[str, float] = {}

		logger.info(f"均值回归策略初始化: {name}")

	def on_init (self) -> None:
		"""策略初始化"""
		logger.info(f"均值回归策略 {self.name} 初始化")

		# 验证参数
		if self.lookback_period <= 0:
			raise ValueError("回看周期必须大于0")

		if self.std_dev_threshold <= 0:
			raise ValueError("标准差阈值必须大于0")

		if self.rsi_oversold >= self.rsi_overbought:
			raise ValueError("RSI超卖阈值必须小于超买阈值")

	def on_start (self) -> None:
		"""策略启动"""
		logger.info(f"均值回归策略 {self.name} 启动")

	def on_stop (self) -> None:
		"""策略停止"""
		logger.info(f"均值回归策略 {self.name} 停止")

		# 清理缓存
		self.price_history.clear()
		self.entry_prices.clear()
		self.position_directions.clear()
		self.ma_cache.clear()
		self.std_cache.clear()
		self.rsi_cache.clear()

	def on_bar (self, bar: BarData) -> List[TradingSignal]:
		"""
		处理K线数据，生成交易信号

		Args:
			bar: K线数据

		Returns:
			交易信号列表
		"""
		signals = []

		try:
			# 更新价格历史
			self._update_price_history(bar)

			# 检查是否已有持仓
			has_position = bar.ts_code in self.position_directions

			if has_position:
				# 检查止损止盈
				exit_signal = self._check_exit_conditions(bar)
				if exit_signal:
					signals.append(exit_signal)
			else:
				# 检查入场条件
				entry_signal = self._check_entry_conditions(bar)
				if entry_signal:
					signals.append(entry_signal)

		except Exception as e:
			logger.error(f"均值回归策略处理K线数据失败: {e}")

		return signals

	def _update_price_history (self, bar: BarData) -> None:
		"""
		更新价格历史数据

		Args:
			bar: K线数据
		"""
		if bar.ts_code not in self.price_history:
			self.price_history[bar.ts_code] = []

		# 添加最新价格
		self.price_history[bar.ts_code].append(bar.close)

		# 保持历史数据长度
		if len(self.price_history[bar.ts_code]) > self.lookback_period:
			self.price_history[bar.ts_code].pop(0)

		# 计算技术指标
		if len(self.price_history[bar.ts_code]) >= self.lookback_period:
			prices = np.array(self.price_history[bar.ts_code])

			# 计算移动平均和标准差
			self.ma_cache[bar.ts_code] = float(np.mean(prices))
			self.std_cache[bar.ts_code] = float(np.std(prices))

			# 计算RSI
			self.rsi_cache[bar.ts_code] = self._calculate_rsi(prices)

	def _calculate_rsi (self, prices: np.ndarray) -> float:
		"""
		计算RSI指标

		Args:
			prices: 价格序列

		Returns:
			RSI值
		"""
		if len(prices) < self.rsi_period + 1:
			return 50.0  # 默认值

		# 计算价格变化
		deltas = np.diff(prices)

		# 分离上涨和下跌
		gains = np.where(deltas > 0, deltas, 0)
		losses = np.where(deltas < 0, -deltas, 0)

		# 计算平均增益和平均损失
		avg_gain = np.mean(gains[-self.rsi_period:])
		avg_loss = np.mean(losses[-self.rsi_period:])

		if avg_loss == 0:
			return 100.0 if avg_gain > 0 else 50.0

		# 计算RSI
		rs = avg_gain / avg_loss
		rsi = 100 - (100 / (1 + rs))

		return float(rsi)

	def _check_entry_conditions (self, bar: BarData) -> Optional[TradingSignal]:
		"""
		检查入场条件

		Args:
			bar: K线数据

		Returns:
			入场信号或None
		"""
		if bar.ts_code not in self.ma_cache:
			return None

		current_price = bar.close
		ma = self.ma_cache[bar.ts_code]
		std = self.std_cache[bar.ts_code]
		rsi = self.rsi_cache.get(bar.ts_code, 50)

		# 计算Z-Score（价格偏离均值的标准差倍数）
		if std > 0:
			z_score = (current_price - ma) / std
		else:
			z_score = 0

		# 入场条件1：价格低于均值2个标准差，且RSI超卖
		if z_score < -self.std_dev_threshold and rsi < self.rsi_oversold:
			return self._create_entry_signal(bar, SignalDirection.LONG, "价格低于均值2个标准差且RSI超卖")

		# 入场条件2：价格高于均值2个标准差，且RSI超买
		if z_score > self.std_dev_threshold and rsi > self.rsi_overbought:
			return self._create_entry_signal(bar, SignalDirection.SHORT, "价格高于均值2个标准差且RSI超买")

		# 入场条件3：RSI极端超卖
		if rsi < 20:
			return self._create_entry_signal(bar, SignalDirection.LONG, "RSI极端超卖")

		# 入场条件4：RSI极端超买
		if rsi > 80:
			return self._create_entry_signal(bar, SignalDirection.SHORT, "RSI极端超买")

		return None

	def _create_entry_signal (self, bar: BarData, direction: SignalDirection, reason: str) -> TradingSignal:
		"""
		创建入场信号

		Args:
			bar: K线数据
			direction: 交易方向
			reason: 入场原因

		Returns:
			交易信号
		"""
		import uuid

		# 计算置信度
		confidence = self._calculate_entry_confidence(bar, direction)

		signal = TradingSignal(
			id=str(uuid.uuid4()),
			strategy_id=self.name,
			strategy_name=self.name,
			ts_code=bar.ts_code,
			signal_type=SignalType.ENTRY,
			direction=direction,
			price=bar.close,
			confidence=confidence,
			reason=reason,
			timestamp=bar.trade_time
		)

		# 记录入场价格和方向
		self.entry_prices[bar.ts_code] = bar.close
		self.position_directions[bar.ts_code] = direction

		logger.info(f"均值回归策略 {self.name} 生成入场信号: {bar.ts_code} {direction.value} {reason}")

		return signal

	def _calculate_entry_confidence (self, bar: BarData, direction: SignalDirection) -> float:
		"""
		计算入场置信度

		Args:
			bar: K线数据
			direction: 交易方向

		Returns:
			置信度(0-1)
		"""
		if bar.ts_code not in self.ma_cache:
			return 0.5

		current_price = bar.close
		ma = self.ma_cache[bar.ts_code]
		std = self.std_cache[bar.ts_code]
		rsi = self.rsi_cache.get(bar.ts_code, 50)

		# 基于Z-Score计算置信度
		if std > 0:
			z_score = abs(current_price - ma) / std
			z_confidence = min(z_score / self.std_dev_threshold, 1.0)
		else:
			z_confidence = 0.5

		# 基于RSI计算置信度
		if direction == SignalDirection.LONG:
			rsi_confidence = (self.rsi_oversold - rsi) / self.rsi_oversold
		else:
			rsi_confidence = (rsi - self.rsi_overbought) / (100 - self.rsi_overbought)

		rsi_confidence = max(0, min(rsi_confidence, 1))

		# 综合置信度
		confidence = (z_confidence + rsi_confidence) / 2

		return min(confidence, 0.95)  # 限制最大置信度

	def _check_exit_conditions (self, bar: BarData) -> Optional[TradingSignal]:
		"""
		检查出场条件

		Args:
			bar: K线数据

		Returns:
			出场信号或None
		"""
		if bar.ts_code not in self.entry_prices:
			return None

		current_price = bar.close
		entry_price = self.entry_prices[bar.ts_code]
		direction = self.position_directions[bar.ts_code]

		# 计算收益率
		if direction == SignalDirection.LONG:
			pnl_rate = (current_price - entry_price) / entry_price
		else:
			pnl_rate = (entry_price - current_price) / entry_price

		# 止损条件
		if pnl_rate < -self.stop_loss:
			return self._create_exit_signal(bar, "止损")

		# 止盈条件
		if pnl_rate > self.take_profit:
			return self._create_exit_signal(bar, "止盈")

		# 均值回归条件：价格回到均值附近
		if bar.ts_code in self.ma_cache:
			ma = self.ma_cache[bar.ts_code]
			price_deviation = abs(current_price - ma) / ma

			if price_deviation < 0.01:  # 价格回到均值1%以内
				return self._create_exit_signal(bar, "价格回归均值")

		# RSI回归中性条件
		if bar.ts_code in self.rsi_cache:
			rsi = self.rsi_cache[bar.ts_code]

			if (direction == SignalDirection.LONG and rsi > 50) or \
					(direction == SignalDirection.SHORT and rsi < 50):
				return self._create_exit_signal(bar, "RSI回归中性")

		return None

	def _create_exit_signal (self, bar: BarData, reason: str) -> TradingSignal:
		"""
		创建出场信号

		Args:
			bar: K线数据
			reason: 出场原因

		Returns:
			交易信号
		"""
		import uuid

		# 确定出场方向（与入场方向相反）
		if bar.ts_code in self.position_directions:
			entry_direction = self.position_directions[bar.ts_code]

			if entry_direction == SignalDirection.LONG:
				exit_direction = SignalDirection.CLOSE_LONG
			else:
				exit_direction = SignalDirection.CLOSE_SHORT
		else:
			exit_direction = SignalDirection.NONE

		signal = TradingSignal(
			id=str(uuid.uuid4()),
			strategy_id=self.name,
			strategy_name=self.name,
			ts_code=bar.ts_code,
			signal_type=SignalType.EXIT,
			direction=exit_direction,
			price=bar.close,
			confidence=0.9,
			reason=reason,
			timestamp=bar.trade_time
		)

		# 清理持仓记录
		if bar.ts_code in self.entry_prices:
			del self.entry_prices[bar.ts_code]
		if bar.ts_code in self.position_directions:
			del self.position_directions[bar.ts_code]

		logger.info(f"均值回归策略 {self.name} 生成出场信号: {bar.ts_code} {exit_direction.value} {reason}")

		return signal

	def get_strategy_status (self) -> Dict[str, Any]:
		"""
		获取策略状态

		Returns:
			策略状态字典
		"""
		return {
			'strategy_name': self.name,
			'position_count': len(self.position_directions),
			'lookback_period': self.lookback_period,
			'std_dev_threshold': self.std_dev_threshold,
			'rsi_period': self.rsi_period,
			'current_positions': list(self.position_directions.keys())
		}