"""
动量指标模块
提供RSI、随机指标、威廉指标等动量震荡指标
使用场景：超买超卖判断、动量确认、背离分析
"""

import numpy as np
import pandas as pd
from typing import Union, List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import warnings


@dataclass
class RSICalculator:
	"""RSI计算器（状态保持）"""
	period: int
	avg_gain: Optional[float] = None
	avg_loss: Optional[float] = None

	def calculate_next (self, price_change: float) -> float:
		"""计算下一个RSI值"""
		if self.avg_gain is None or self.avg_loss is None:
			# 初始化
			gain = max(price_change, 0)
			loss = abs(min(price_change, 0))
			self.avg_gain = gain
			self.avg_loss = loss
		else:
			# 更新平均值
			gain = max(price_change, 0)
			loss = abs(min(price_change, 0))
			self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
			self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period

		# 计算RSI
		if self.avg_loss == 0:
			return 100.0
		rs = self.avg_gain / self.avg_loss
		rsi = 100 - (100 / (1 + rs))
		return rsi


@dataclass
class StochasticResult:
	"""随机指标结果"""
	k_line: np.ndarray  # %K线（快速随机指标）
	d_line: np.ndarray  # %D线（%K的移动平均）
	slow_k: Optional[np.ndarray] = None  # 慢速%K
	slow_d: Optional[np.ndarray] = None  # 慢速%D


@dataclass
class MomentumResult:
	"""动量指标结果"""
	values: np.ndarray
	signal_line: Optional[np.ndarray] = None


class MomentumIndicators:
	"""
	动量指标计算器
	提供各种动量震荡指标的计算
	"""

	def __init__ (self, default_period: int = 14):
		"""
		初始化动量指标计算器

		Args:
			default_period: 默认计算周期
		"""
		self.default_period = default_period

	def relative_strength_index (self, prices: Union[List[float], np.ndarray, pd.Series],
	                             period: Optional[int] = None) -> np.ndarray:
		"""
		计算相对强弱指标 (RSI)

		使用场景：
		- 识别超买超卖区域（通常70以上超买，30以下超卖）
		- 寻找背离信号（价格新高但RSI未新高）
		- 判断趋势强度
		- 适合震荡市和反转策略

		Args:
			prices: 价格序列
			period: RSI周期（默认14）

		Returns:
			np.ndarray: RSI序列（0-100）
		"""
		if period is None:
			period = self.default_period

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period + 1:
			raise ValueError(f"数据长度({len(prices)})必须大于周期({period})")

		# 计算价格变化
		price_changes = np.diff(prices)

		# 初始化
		gains = np.where(price_changes > 0, price_changes, 0)
		losses = np.where(price_changes < 0, -price_changes, 0)

		# 计算初始平均值
		avg_gain = np.mean(gains[:period])
		avg_loss = np.mean(losses[:period])

		rsi = np.full(len(prices), np.nan)

		# 计算第一个RSI
		if avg_loss == 0:
			rsi[period] = 100
		else:
			rs = avg_gain / avg_loss
			rsi[period] = 100 - (100 / (1 + rs))

		# 计算后续RSI
		for i in range(period + 1, len(prices)):
			gain = max(price_changes[i - 1], 0)
			loss = abs(min(price_changes[i - 1], 0))

			# 平滑更新
			avg_gain = (avg_gain * (period - 1) + gain) / period
			avg_loss = (avg_loss * (period - 1) + loss) / period

			if avg_loss == 0:
				rsi[i] = 100
			else:
				rs = avg_gain / avg_loss
				rsi[i] = 100 - (100 / (1 + rs))

		return rsi

	def stochastic_oscillator (self, high: Union[List[float], np.ndarray, pd.Series],
	                           low: Union[List[float], np.ndarray, pd.Series],
	                           close: Union[List[float], np.ndarray, pd.Series],
	                           k_period: int = 14,
	                           d_period: int = 3,
	                           slow_k: bool = False) -> StochasticResult:
		"""
		计算随机指标 (Stochastic Oscillator)

		使用场景：
		- 识别超买超卖（通常80以上超买，20以下超卖）
		- 寻找背离信号
		- 判断趋势反转
		- 适合短期交易和波段操作

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			k_period: %K周期（默认14）
			d_period: %D周期（默认3）
			slow_k: 是否使用慢速随机指标

		Returns:
			StochasticResult: 随机指标结果
		"""
		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(close)

		# 计算%K线
		k_line = np.full(n, np.nan)

		for i in range(k_period - 1, n):
			highest_high = np.max(high[i - k_period + 1:i + 1])
			lowest_low = np.min(low[i - k_period + 1:i + 1])

			if highest_high != lowest_low:
				k_line[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
			else:
				k_line[i] = 50  # 特殊情况

		# 计算%D线（%K的简单移动平均）
		d_line = np.full(n, np.nan)
		for i in range(k_period + d_period - 2, n):
			d_line[i] = np.nanmean(k_line[i - d_period + 1:i + 1])

		# 慢速随机指标
		slow_k_line = None
		slow_d_line = None

		if slow_k:
			# 慢速%K = 快速%D
			slow_k_line = d_line.copy()

			# 慢速%D = 慢速%K的移动平均
			slow_d_line = np.full(n, np.nan)
			for i in range(k_period + 2 * d_period - 3, n):
				slow_d_line[i] = np.nanmean(slow_k_line[i - d_period + 1:i + 1])

		return StochasticResult(
			k_line=k_line,
			d_line=d_line,
			slow_k=slow_k_line,
			slow_d=slow_d_line
		)

	def williams_percent_r (self, high: Union[List[float], np.ndarray, pd.Series],
	                        low: Union[List[float], np.ndarray, pd.Series],
	                        close: Union[List[float], np.ndarray, pd.Series],
	                        period: Optional[int] = None) -> np.ndarray:
		"""
		计算威廉指标 (Williams %R)

		使用场景：
		- 识别超买超卖（通常-20以上超买，-80以下超卖）
		- 与RSI互补使用
		- 短期反转信号
		- 适合短线交易

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			period: 计算周期（默认14）

		Returns:
			np.ndarray: 威廉指标序列（-100到0）
		"""
		if period is None:
			period = self.default_period

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(close)
		williams_r = np.full(n, np.nan)

		for i in range(period - 1, n):
			highest_high = np.max(high[i - period + 1:i + 1])
			lowest_low = np.min(low[i - period + 1:i + 1])

			if highest_high != lowest_low:
				williams_r[i] = -100 * (highest_high - close[i]) / (highest_high - lowest_low)
			else:
				williams_r[i] = -50  # 特殊情况

		return williams_r

	def commodity_channel_index (self, high: Union[List[float], np.ndarray, pd.Series],
	                             low: Union[List[float], np.ndarray, pd.Series],
	                             close: Union[List[float], np.ndarray, pd.Series],
	                             period: Optional[int] = None) -> np.ndarray:
		"""
		计算商品通道指数 (CCI)

		使用场景：
		- 识别超买超卖（通常+100以上超买，-100以下超卖）
		- 判断趋势强度和方向
		- 寻找趋势反转信号
		- 适合趋势跟踪和反转策略

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			period: CCI周期（默认20）

		Returns:
			np.ndarray: CCI序列
		"""
		if period is None:
			period = 20  # CCI常用20周期

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(close)

		# 计算典型价格
		typical_price = (high + low + close) / 3

		cci = np.full(n, np.nan)

		for i in range(period - 1, n):
			# 计算移动平均
			ma = np.mean(typical_price[i - period + 1:i + 1])

			# 计算平均偏差
			mean_deviation = np.mean(np.abs(typical_price[i - period + 1:i + 1] - ma))

			if mean_deviation > 0:
				cci[i] = (typical_price[i] - ma) / (0.015 * mean_deviation)
			else:
				cci[i] = 0

		return cci

	def rate_of_change (self, prices: Union[List[float], np.ndarray, pd.Series],
	                    period: Optional[int] = None) -> np.ndarray:
		"""
		计算变动率指标 (ROC)

		使用场景：
		- 测量价格变化的速度
		- 识别动量变化
		- 判断趋势加速或减速
		- 适合动量策略

		Args:
			prices: 价格序列
			period: ROC周期（默认12）

		Returns:
			np.ndarray: ROC序列（百分比）
		"""
		if period is None:
			period = 12  # ROC常用12周期

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period:
			raise ValueError(f"数据长度({len(prices)})必须大于周期({period})")

		roc = np.full(len(prices), np.nan)

		for i in range(period, len(prices)):
			if prices[i - period] != 0:
				roc[i] = 100 * (prices[i] - prices[i - period]) / prices[i - period]
			else:
				roc[i] = 0

		return roc

	def momentum_oscillator (self, prices: Union[List[float], np.ndarray, pd.Series],
	                         period: Optional[int] = None) -> np.ndarray:
		"""
		计算动量振荡器 (Momentum Oscillator)

		使用场景：
		- 简单直接的价格动量测量
		- 零轴交叉信号（上穿零轴买入，下穿零轴卖出）
		- 适合趋势识别

		Args:
			prices: 价格序列
			period: 动量周期（默认10）

		Returns:
			np.ndarray: 动量值序列
		"""
		if period is None:
			period = 10

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period:
			raise ValueError(f"数据长度({len(prices)})必须大于周期({period})")

		momentum = np.full(len(prices), np.nan)

		for i in range(period, len(prices)):
			momentum[i] = prices[i] - prices[i - period]

		return momentum

	def awesome_oscillator (self, high: Union[List[float], np.ndarray, pd.Series],
	                        low: Union[List[float], np.ndarray, pd.Series],
	                        fast_period: int = 5,
	                        slow_period: int = 34) -> np.ndarray:
		"""
		计算动量震荡指标 (Awesome Oscillator)

		使用场景：
		- 零轴交叉判断多空
		- 碟形模式识别（Saucer）
		- 双峰模式识别（Twin Peaks）
		- 适合波段操作

		Args:
			high: 最高价序列
			low: 最低价序列
			fast_period: 快速周期（默认5）
			slow_period: 慢速周期（默认34）

		Returns:
			np.ndarray: 动量震荡值
		"""
		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)

		n = len(high)

		# 计算中点价格
		midpoint = (high + low) / 2

		# 计算快速和慢速SMA
		fast_sma = np.full(n, np.nan)
		slow_sma = np.full(n, np.nan)

		for i in range(slow_period - 1, n):
			if i >= fast_period - 1:
				fast_sma[i] = np.mean(midpoint[i - fast_period + 1:i + 1])
			slow_sma[i] = np.mean(midpoint[i - slow_period + 1:i + 1])

		# 计算Awesome Oscillator
		ao = np.full(n, np.nan)
		for i in range(slow_period - 1, n):
			if not np.isnan(fast_sma[i]) and not np.isnan(slow_sma[i]):
				ao[i] = fast_sma[i] - slow_sma[i]

		return ao

	def ultimate_oscillator (self, high: Union[List[float], np.ndarray, pd.Series],
	                         low: Union[List[float], np.ndarray, pd.Series],
	                         close: Union[List[float], np.ndarray, pd.Series],
	                         period1: int = 7,
	                         period2: int = 14,
	                         period3: int = 28,
	                         weight1: float = 4.0,
	                         weight2: float = 2.0,
	                         weight3: float = 1.0) -> np.ndarray:
		"""
		计算终极震荡指标 (Ultimate Oscillator)

		使用场景：
		- 结合多个时间周期的动量
		- 减少市场噪音
		- 识别更可靠的反转信号
		- 适合中短期交易

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			period1: 第一周期（默认7）
			period2: 第二周期（默认14）
			period3: 第三周期（默认28）
			weight1: 第一权重（默认4）
			weight2: 第二权重（默认2）
			weight3: 第三权重（默认1）

		Returns:
			np.ndarray: 终极震荡指标序列（0-100）
		"""
		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(close)

		# 计算买入压力和真实波幅
		buying_pressure = np.zeros(n)
		true_range = np.zeros(n)

		for i in range(1, n):
			buying_pressure[i] = close[i] - min(low[i], close[i - 1])
			true_range[i] = max(
				high[i] - low[i],
				abs(high[i] - close[i - 1]),
				abs(low[i] - close[i - 1])
			)

		# 计算三个周期的平均值
		avg1 = np.full(n, np.nan)
		avg2 = np.full(n, np.nan)
		avg3 = np.full(n, np.nan)

		for i in range(max(period1, period2, period3) - 1, n):
			if i >= period1 - 1:
				sum_bp1 = np.sum(buying_pressure[i - period1 + 1:i + 1])
				sum_tr1 = np.sum(true_range[i - period1 + 1:i + 1])
				avg1[i] = sum_bp1 / sum_tr1 if sum_tr1 > 0 else 0

			if i >= period2 - 1:
				sum_bp2 = np.sum(buying_pressure[i - period2 + 1:i + 1])
				sum_tr2 = np.sum(true_range[i - period2 + 1:i + 1])
				avg2[i] = sum_bp2 / sum_tr2 if sum_tr2 > 0 else 0

			if i >= period3 - 1:
				sum_bp3 = np.sum(buying_pressure[i - period3 + 1:i + 1])
				sum_tr3 = np.sum(true_range[i - period3 + 1:i + 1])
				avg3[i] = sum_bp3 / sum_tr3 if sum_tr3 > 0 else 0

		# 计算终极震荡指标
		uo = np.full(n, np.nan)
		total_weight = weight1 + weight2 + weight3

		for i in range(max(period1, period2, period3) - 1, n):
			if not np.isnan(avg1[i]) and not np.isnan(avg2[i]) and not np.isnan(avg3[i]):
				uo[i] = 100 * (weight1 * avg1[i] + weight2 * avg2[i] + weight3 * avg3[i]) / total_weight

		return uo

	def is_overbought (self, indicator_values: Union[List[float], np.ndarray, pd.Series],
	                   overbought_level: float = 70.0) -> np.ndarray:
		"""
		判断是否超买

		使用场景：
		- RSI、随机指标等超买判断
		- 风险控制
		- 获利了结信号

		Args:
			indicator_values: 指标值序列（如RSI）
			overbought_level: 超买阈值

		Returns:
			np.ndarray: 布尔序列（True=超买）
		"""
		if isinstance(indicator_values, (list, pd.Series)):
			indicator_values = np.array(indicator_values)

		return indicator_values > overbought_level

	def is_oversold (self, indicator_values: Union[List[float], np.ndarray, pd.Series],
	                 oversold_level: float = 30.0) -> np.ndarray:
		"""
		判断是否超卖

		使用场景：
		- RSI、随机指标等超卖判断
		- 买入机会识别
		- 抄底信号

		Args:
			indicator_values: 指标值序列（如RSI）
			oversold_level: 超卖阈值

		Returns:
			np.ndarray: 布尔序列（True=超卖）
		"""
		if isinstance(indicator_values, (list, pd.Series)):
			indicator_values = np.array(indicator_values)

		return indicator_values < oversold_level


# 便捷函数
def relative_strength_index (prices: Union[List[float], np.ndarray, pd.Series],
                             period: int = 14) -> np.ndarray:
	"""计算相对强弱指标"""
	return MomentumIndicators().relative_strength_index(prices, period)


def stochastic_oscillator (high: Union[List[float], np.ndarray, pd.Series],
                           low: Union[List[float], np.ndarray, pd.Series],
                           close: Union[List[float], np.ndarray, pd.Series],
                           k_period: int = 14,
                           d_period: int = 3,
                           slow_k: bool = False) -> StochasticResult:
	"""计算随机指标"""
	return MomentumIndicators().stochastic_oscillator(high, low, close, k_period, d_period, slow_k)


def williams_percent_r (high: Union[List[float], np.ndarray, pd.Series],
                        low: Union[List[float], np.ndarray, pd.Series],
                        close: Union[List[float], np.ndarray, pd.Series],
                        period: int = 14) -> np.ndarray:
	"""计算威廉指标"""
	return MomentumIndicators().williams_percent_r(high, low, close, period)


def commodity_channel_index (high: Union[List[float], np.ndarray, pd.Series],
                             low: Union[List[float], np.ndarray, pd.Series],
                             close: Union[List[float], np.ndarray, pd.Series],
                             period: int = 20) -> np.ndarray:
	"""计算商品通道指数"""
	return MomentumIndicators().commodity_channel_index(high, low, close, period)


def rate_of_change (prices: Union[List[float], np.ndarray, pd.Series],
                    period: int = 12) -> np.ndarray:
	"""计算变动率指标"""
	return MomentumIndicators().rate_of_change(prices, period)


def momentum_oscillator (prices: Union[List[float], np.ndarray, pd.Series],
                         period: int = 10) -> np.ndarray:
	"""计算动量振荡器"""
	return MomentumIndicators().momentum_oscillator(prices, period)


def awesome_oscillator (high: Union[List[float], np.ndarray, pd.Series],
                        low: Union[List[float], np.ndarray, pd.Series],
                        fast_period: int = 5,
                        slow_period: int = 34) -> np.ndarray:
	"""计算动量震荡指标"""
	return MomentumIndicators().awesome_oscillator(high, low, fast_period, slow_period)


def ultimate_oscillator (high: Union[List[float], np.ndarray, pd.Series],
                         low: Union[List[float], np.ndarray, pd.Series],
                         close: Union[List[float], np.ndarray, pd.Series],
                         period1: int = 7,
                         period2: int = 14,
                         period3: int = 28) -> np.ndarray:
	"""计算终极震荡指标"""
	return MomentumIndicators().ultimate_oscillator(
		high, low, close, period1, period2, period3)


def is_overbought (indicator_values: Union[List[float], np.ndarray, pd.Series],
                   overbought_level: float = 70.0) -> np.ndarray:
	"""判断是否超买"""
	return MomentumIndicators().is_overbought(indicator_values, overbought_level)


def is_oversold (indicator_values: Union[List[float], np.ndarray, pd.Series],
                 oversold_level: float = 30.0) -> np.ndarray:
	"""判断是否超卖"""
	return MomentumIndicators().is_oversold(indicator_values, oversold_level)