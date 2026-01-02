"""
趋势指标模块
提供移动平均线、MACD、抛物线SAR等趋势判断指标
使用场景：趋势识别、趋势跟踪、趋势反转判断
"""

import numpy as np
import pandas as pd
from typing import Union, List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import warnings


class MovingAverageType(Enum):
	"""移动平均线类型枚举"""
	SIMPLE = "SMA"  # 简单移动平均
	EXPONENTIAL = "EMA"  # 指数移动平均
	WEIGHTED = "WMA"  # 加权移动平均
	HULL = "HMA"  # 赫尔移动平均


@dataclass
class MovingAverage:
	"""移动平均线结果"""
	values: np.ndarray
	type: MovingAverageType
	period: int
	signal_line: Optional[np.ndarray] = None  # 用于双重移动平均


@dataclass
class EMACalculator:
	"""EMA计算器（高效实现）"""
	period: int
	alpha: float
	previous_ema: Optional[float] = None

	def calculate_next (self, price: float) -> float:
		"""计算下一个EMA值"""
		if self.previous_ema is None:
			ema = price
		else:
			ema = self.alpha * price + (1 - self.alpha) * self.previous_ema
		self.previous_ema = ema
		return ema


@dataclass
class MACDResult:
	"""MACD指标结果"""
	macd_line: np.ndarray  # MACD线 = EMA(12) - EMA(26)
	signal_line: np.ndarray  # 信号线 = EMA(MACD, 9)
	histogram: np.ndarray  # 柱状图 = MACD - 信号线
	divergence: Optional[np.ndarray] = None  # 背离信号


@dataclass
class IchimokuCloud:
	"""一目均衡云结果"""
	tenkan_sen: np.ndarray  # 转换线（9日最高最低平均）
	kijun_sen: np.ndarray  # 基准线（26日最高最低平均）
	senkou_span_a: np.ndarray  # 先行带A（转换线+基准线）/2
	senkou_span_b: np.ndarray  # 先行带B（52日最高最低平均）
	chikou_span: np.ndarray  # 迟行线（26日前收盘价）


class TrendIndicators:
	"""
	趋势指标计算器
	提供各种趋势识别指标的计算
	"""

	def __init__ (self, default_period: int = 20):
		"""
		初始化趋势指标计算器

		Args:
			default_period: 默认计算周期
		"""
		self.default_period = default_period

	def simple_moving_average (self, prices: Union[List[float], np.ndarray, pd.Series],
	                           period: Optional[int] = None) -> np.ndarray:
		"""
		计算简单移动平均线 (SMA)

		使用场景：
		- 趋势方向判断：价格在SMA之上为上涨趋势，之下为下跌趋势
		- 支撑阻力位：SMA可作为动态支撑阻力
		- 多空分界线：常用20、50、200日SMA作为多空分界

		Args:
			prices: 价格序列
			period: 移动平均周期

		Returns:
			np.ndarray: SMA序列
		"""
		if period is None:
			period = self.default_period

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period:
			raise ValueError(f"数据长度({len(prices)})必须大于等于周期({period})")

		sma = np.full(len(prices), np.nan)

		# 使用卷积计算移动平均，效率更高
		weights = np.ones(period) / period
		sma[period - 1:] = np.convolve(prices, weights, mode='valid')

		return sma

	def exponential_moving_average (self, prices: Union[List[float], np.ndarray, pd.Series],
	                                period: Optional[int] = None) -> np.ndarray:
		"""
		计算指数移动平均线 (EMA)

		使用场景：
		- 比SMA更灵敏，能更快反映价格变化
		- 适合短期交易和快速趋势判断
		- 常用于MACD计算

		Args:
			prices: 价格序列
			period: EMA周期

		Returns:
			np.ndarray: EMA序列
		"""
		if period is None:
			period = self.default_period

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period:
			raise ValueError(f"数据长度({len(prices)})必须大于等于周期({period})")

		# 平滑系数
		alpha = 2 / (period + 1)

		ema = np.full(len(prices), np.nan)

		# 第一个EMA使用SMA
		sma = np.mean(prices[:period])
		ema[period - 1] = sma

		# 递归计算后续EMA
		for i in range(period, len(prices)):
			ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]

		return ema

	def weighted_moving_average (self, prices: Union[List[float], np.ndarray, pd.Series],
	                             period: Optional[int] = None) -> np.ndarray:
		"""
		计算加权移动平均线 (WMA)

		使用场景：
		- 给予近期数据更高权重，比SMA更灵敏
		- 适合捕捉短期趋势变化
		- 用于趋势确认和交易信号

		Args:
			prices: 价格序列
			period: 加权周期

		Returns:
			np.ndarray: WMA序列
		"""
		if period is None:
			period = self.default_period

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period:
			raise ValueError(f"数据长度({len(prices)})必须大于等于周期({period})")

		wma = np.full(len(prices), np.nan)

		# 创建权重数组（线性递减）
		weights = np.arange(1, period + 1)
		weights = weights / weights.sum()

		# 计算加权移动平均
		for i in range(period - 1, len(prices)):
			window = prices[i - period + 1:i + 1]
			wma[i] = np.dot(window, weights)

		return wma

	def hull_moving_average (self, prices: Union[List[float], np.ndarray, pd.Series],
	                         period: Optional[int] = None) -> np.ndarray:
		"""
		计算赫尔移动平均线 (HMA)

		使用场景：
		- 减少滞后性，比传统移动平均更快
		- 适合趋势跟踪和突破策略
		- 减少市场噪音干扰

		Args:
			prices: 价格序列
			period: HMA周期

		Returns:
			np.ndarray: HMA序列
		"""
		if period is None:
			period = self.default_period

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period:
			raise ValueError(f"数据长度({len(prices)})必须大于等于周期({period})")

		# 计算半周期和平方根周期
		half_period = int(period / 2)
		sqrt_period = int(np.sqrt(period))

		if half_period < 1:
			half_period = 1
		if sqrt_period < 1:
			sqrt_period = 1

		# 第一步：计算周期为half_period的WMA
		wma1 = self.weighted_moving_average(prices, half_period)

		# 第二步：计算周期为period的WMA
		wma2 = self.weighted_moving_average(prices, period)

		# 第三步：计算2 * WMA(half_period) - WMA(period)
		raw_hma = 2 * wma1 - wma2

		# 第四步：对结果应用WMA，周期为sqrt_period
		hma = np.full(len(prices), np.nan)

		for i in range(sqrt_period - 1, len(prices)):
			if i >= period - 1:
				window = raw_hma[i - sqrt_period + 1:i + 1]
				if not np.any(np.isnan(window)):
					hma[i] = self.weighted_moving_average(window, sqrt_period)[-1]

		return hma

	def moving_average_convergence_divergence (self,
	                                           prices: Union[List[float], np.ndarray, pd.Series],
	                                           fast_period: int = 12,
	                                           slow_period: int = 26,
	                                           signal_period: int = 9) -> MACDResult:
		"""
		计算MACD指标

		使用场景：
		- 趋势强度和方向判断
		- 寻找买入卖出信号（金叉死叉）
		- 识别背离信号（价格新高但MACD未新高）
		- 适合中短期趋势分析

		Args:
			prices: 价格序列
			fast_period: 快线周期（通常12）
			slow_period: 慢线周期（通常26）
			signal_period: 信号线周期（通常9）

		Returns:
			MACDResult: MACD指标结果
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		# 计算快速EMA和慢速EMA
		fast_ema = self.exponential_moving_average(prices, fast_period)
		slow_ema = self.exponential_moving_average(prices, slow_period)

		# 计算MACD线
		macd_line = fast_ema - slow_ema

		# 计算信号线（MACD的EMA）
		signal_line = self.exponential_moving_average(macd_line[~np.isnan(macd_line)], signal_period)

		# 对齐长度
		valid_macd = macd_line[~np.isnan(macd_line)]
		if len(signal_line) < len(valid_macd):
			signal_line = np.concatenate([np.full(len(valid_macd) - len(signal_line), np.nan), signal_line])

		# 计算柱状图
		histogram = macd_line.copy()
		valid_idx = ~np.isnan(macd_line)
		histogram[valid_idx] = macd_line[valid_idx] - signal_line[:np.sum(valid_idx)]

		# 重新对齐信号线到原始长度
		full_signal_line = np.full_like(macd_line, np.nan)
		valid_count = np.sum(valid_idx)
		full_signal_line[valid_idx] = signal_line[-valid_count:] if len(signal_line) >= valid_count else signal_line

		return MACDResult(
			macd_line=macd_line,
			signal_line=full_signal_line,
			histogram=histogram
		)

	def parabolic_sar (self, high: Union[List[float], np.ndarray, pd.Series],
	                   low: Union[List[float], np.ndarray, pd.Series],
	                   acceleration_factor: float = 0.02,
	                   max_acceleration: float = 0.2) -> np.ndarray:
		"""
		计算抛物线转向指标 (Parabolic SAR)

		使用场景：
		- 趋势跟踪止损指标
		- 判断趋势反转点
		- 设置动态止损位
		- 适合趋势明显的市场

		Args:
			high: 最高价序列
			low: 最低价序列
			acceleration_factor: 加速因子初始值
			max_acceleration: 最大加速因子

		Returns:
			np.ndarray: SAR序列
		"""
		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)

		if len(high) != len(low):
			raise ValueError("最高价和最低价序列长度必须相同")

		if len(high) < 2:
			raise ValueError("数据长度必须至少为2")

		sar = np.full(len(high), np.nan)

		# 初始值
		sar[0] = low[0] if high[1] > high[0] else high[0]

		# 趋势方向（1=上升，-1=下降）
		trend = 1 if high[1] > high[0] else -1

		# 极值点
		ep = high[1] if trend == 1 else low[1]
		af = acceleration_factor

		for i in range(1, len(high)):
			# 计算当前SAR
			if trend == 1:
				sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
				# 检查是否反转
				if low[i] < sar[i]:
					trend = -1
					sar[i] = ep
					ep = low[i]
					af = acceleration_factor
				else:
					# 更新极值点
					if high[i] > ep:
						ep = high[i]
						af = min(af + acceleration_factor, max_acceleration)
			else:
				sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
				# 检查是否反转
				if high[i] > sar[i]:
					trend = 1
					sar[i] = ep
					ep = high[i]
					af = acceleration_factor
				else:
					# 更新极值点
					if low[i] < ep:
						ep = low[i]
						af = min(af + acceleration_factor, max_acceleration)

		return sar

	def ichimoku_cloud (self, high: Union[List[float], np.ndarray, pd.Series],
	                    low: Union[List[float], np.ndarray, pd.Series],
	                    close: Union[List[float], np.ndarray, pd.Series],
	                    tenkan_period: int = 9,
	                    kijun_period: int = 26,
	                    senkou_b_period: int = 52,
	                    displacement: int = 26) -> IchimokuCloud:
		"""
		计算一目均衡云指标

		使用场景：
		- 综合判断趋势、支撑阻力、动能
		- 识别关键的支撑阻力区域（云层）
		- 判断买卖信号（转换线突破基准线）
		- 适合日线及以上周期的趋势分析

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			tenkan_period: 转换线周期（默认9）
			kijun_period: 基准线周期（默认26）
			senkou_b_period: 先行带B周期（默认52）
			displacement: 位移周期（默认26）

		Returns:
			IchimokuCloud: 一目均衡云结果
		"""
		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(high)

		# 计算转换线（Tenkan-sen）：(9日最高+9日最低)/2
		tenkan_sen = np.full(n, np.nan)
		for i in range(tenkan_period - 1, n):
			high_window = high[i - tenkan_period + 1:i + 1]
			low_window = low[i - tenkan_period + 1:i + 1]
			tenkan_sen[i] = (np.max(high_window) + np.min(low_window)) / 2

		# 计算基准线（Kijun-sen）：(26日最高+26日最低)/2
		kijun_sen = np.full(n, np.nan)
		for i in range(kijun_period - 1, n):
			high_window = high[i - kijun_period + 1:i + 1]
			low_window = low[i - kijun_period + 1:i + 1]
			kijun_sen[i] = (np.max(high_window) + np.min(low_window)) / 2

		# 计算先行带A（Senkou Span A）：(转换线+基准线)/2，前移26期
		senkou_span_a = np.full(n + displacement, np.nan)
		for i in range(n):
			if not np.isnan(tenkan_sen[i]) and not np.isnan(kijun_sen[i]):
				senkou_span_a[i + displacement] = (tenkan_sen[i] + kijun_sen[i]) / 2

		# 计算先行带B（Senkou Span B）：(52日最高+52日最低)/2，前移26期
		senkou_span_b = np.full(n + displacement, np.nan)
		for i in range(senkou_b_period - 1, n):
			high_window = high[i - senkou_b_period + 1:i + 1]
			low_window = low[i - senkou_b_period + 1:i + 1]
			senkou_span_b[i + displacement] = (np.max(high_window) + np.min(low_window)) / 2

		# 计算迟行线（Chikou Span）：收盘价后移26期
		chikou_span = np.full(n, np.nan)
		for i in range(n):
			if i >= displacement:
				chikou_span[i - displacement] = close[i]

		# 截断到原始长度
		senkou_span_a = senkou_span_a[:n]
		senkou_span_b = senkou_span_b[:n]

		return IchimokuCloud(
			tenkan_sen=tenkan_sen,
			kijun_sen=kijun_sen,
			senkou_span_a=senkou_span_a,
			senkou_span_b=senkou_span_b,
			chikou_span=chikou_span
		)

	def vortex_indicator (self, high: Union[List[float], np.ndarray, pd.Series],
	                      low: Union[List[float], np.ndarray, pd.Series],
	                      close: Union[List[float], np.ndarray, pd.Series],
	                      period: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
		"""
		计算涡流指标 (Vortex Indicator)

		使用场景：
		- 识别趋势方向和强度
		- 判断趋势开始和结束
		- 确认趋势反转信号
		- 适合趋势跟踪策略

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			period: 计算周期

		Returns:
			Tuple[np.ndarray, np.ndarray]: (正向涡流VI+, 负向涡流VI-)
		"""
		if period is None:
			period = self.default_period

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(high)

		# 计算真实波动范围
		tr = np.zeros(n)
		tr[0] = high[0] - low[0]
		for i in range(1, n):
			tr[i] = max(
				high[i] - low[i],
				abs(high[i] - close[i - 1]),
				abs(low[i] - close[i - 1])
			)

		# 计算正向和负向移动
		vm_plus = np.zeros(n)
		vm_minus = np.zeros(n)

		for i in range(1, n):
			vm_plus[i] = abs(high[i] - low[i - 1])
			vm_minus[i] = abs(low[i] - high[i - 1])

		# 计算涡流指标
		vi_plus = np.full(n, np.nan)
		vi_minus = np.full(n, np.nan)

		for i in range(period, n):
			sum_vm_plus = np.sum(vm_plus[i - period + 1:i + 1])
			sum_vm_minus = np.sum(vm_minus[i - period + 1:i + 1])
			sum_tr = np.sum(tr[i - period + 1:i + 1])

			if sum_tr > 0:
				vi_plus[i] = sum_vm_plus / sum_tr
				vi_minus[i] = sum_vm_minus / sum_tr

		return vi_plus, vi_minus

	def moving_average_crossover (self, prices: Union[List[float], np.ndarray, pd.Series],
	                              fast_period: int = 10,
	                              slow_period: int = 30) -> np.ndarray:
		"""
		移动平均线交叉信号

		使用场景：
		- 生成买入卖出信号（金叉买入，死叉卖出）
		- 判断趋势转换
		- 确认趋势方向

		Args:
			prices: 价格序列
			fast_period: 快速移动平均周期
			slow_period: 慢速移动平均周期

		Returns:
			np.ndarray: 信号序列（1=买入，-1=卖出，0=无信号）
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		fast_ma = self.simple_moving_average(prices, fast_period)
		slow_ma = self.simple_moving_average(prices, slow_period)

		signals = np.zeros(len(prices))

		for i in range(1, len(prices)):
			if not np.isnan(fast_ma[i]) and not np.isnan(slow_ma[i]):
				# 金叉：快线上穿慢线
				if fast_ma[i - 1] <= slow_ma[i - 1] and fast_ma[i] > slow_ma[i]:
					signals[i] = 1  # 买入信号
				# 死叉：快线下穿慢线
				elif fast_ma[i - 1] >= slow_ma[i - 1] and fast_ma[i] < slow_ma[i]:
					signals[i] = -1  # 卖出信号

		return signals

	def trend_direction (self, prices: Union[List[float], np.ndarray, pd.Series],
	                     ma_period: int = 20) -> np.ndarray:
		"""
		判断趋势方向

		使用场景：
		- 量化趋势状态（上涨、下跌、震荡）
		- 趋势跟踪策略的入场条件
		- 多空判断

		Args:
			prices: 价格序列
			ma_period: 移动平均周期

		Returns:
			np.ndarray: 趋势方向序列（1=上涨，-1=下跌，0=无趋势）
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		ma = self.simple_moving_average(prices, ma_period)

		trend = np.zeros(len(prices))

		for i in range(1, len(prices)):
			if not np.isnan(ma[i]):
				# 价格在均线上方且上涨
				if prices[i] > ma[i] and prices[i] > prices[i - 1]:
					trend[i] = 1
				# 价格在均线下方且下跌
				elif prices[i] < ma[i] and prices[i] < prices[i - 1]:
					trend[i] = -1
				# 保持前一期趋势
				else:
					trend[i] = trend[i - 1]

		return trend


# 便捷函数
def simple_moving_average (prices: Union[List[float], np.ndarray, pd.Series],
                           period: int = 20) -> np.ndarray:
	"""计算简单移动平均线"""
	return TrendIndicators().simple_moving_average(prices, period)


def exponential_moving_average (prices: Union[List[float], np.ndarray, pd.Series],
                                period: int = 20) -> np.ndarray:
	"""计算指数移动平均线"""
	return TrendIndicators().exponential_moving_average(prices, period)


def weighted_moving_average (prices: Union[List[float], np.ndarray, pd.Series],
                             period: int = 20) -> np.ndarray:
	"""计算加权移动平均线"""
	return TrendIndicators().weighted_moving_average(prices, period)


def hull_moving_average (prices: Union[List[float], np.ndarray, pd.Series],
                         period: int = 20) -> np.ndarray:
	"""计算赫尔移动平均线"""
	return TrendIndicators().hull_moving_average(prices, period)


def moving_average_convergence_divergence (prices: Union[List[float], np.ndarray, pd.Series],
                                           fast_period: int = 12,
                                           slow_period: int = 26,
                                           signal_period: int = 9) -> MACDResult:
	"""计算MACD指标"""
	return TrendIndicators().moving_average_convergence_divergence(
		prices, fast_period, slow_period, signal_period)


def parabolic_sar (high: Union[List[float], np.ndarray, pd.Series],
                   low: Union[List[float], np.ndarray, pd.Series],
                   acceleration_factor: float = 0.02,
                   max_acceleration: float = 0.2) -> np.ndarray:
	"""计算抛物线转向指标"""
	return TrendIndicators().parabolic_sar(high, low, acceleration_factor, max_acceleration)


def ichimoku_cloud (high: Union[List[float], np.ndarray, pd.Series],
                    low: Union[List[float], np.ndarray, pd.Series],
                    close: Union[List[float], np.ndarray, pd.Series],
                    tenkan_period: int = 9,
                    kijun_period: int = 26,
                    senkou_b_period: int = 52,
                    displacement: int = 26) -> IchimokuCloud:
	"""计算一目均衡云指标"""
	return TrendIndicators().ichimoku_cloud(
		high, low, close, tenkan_period, kijun_period, senkou_b_period, displacement)


def vortex_indicator (high: Union[List[float], np.ndarray, pd.Series],
                      low: Union[List[float], np.ndarray, pd.Series],
                      close: Union[List[float], np.ndarray, pd.Series],
                      period: int = 20) -> Tuple[np.ndarray, np.ndarray]:
	"""计算涡流指标"""
	return TrendIndicators().vortex_indicator(high, low, close, period)


def moving_average_crossover (prices: Union[List[float], np.ndarray, pd.Series],
                              fast_period: int = 10,
                              slow_period: int = 30) -> np.ndarray:
	"""移动平均线交叉信号"""
	return TrendIndicators().moving_average_crossover(prices, fast_period, slow_period)


def trend_direction (prices: Union[List[float], np.ndarray, pd.Series],
                     ma_period: int = 20) -> np.ndarray:
	"""判断趋势方向"""
	return TrendIndicators().trend_direction(prices, ma_period)