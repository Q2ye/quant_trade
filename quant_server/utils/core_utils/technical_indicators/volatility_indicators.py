"""
波动率指标模块
提供布林带、ATR、凯尔特纳通道等波动率测量指标
使用场景：波动率分析、波动率交易、风险管理
"""

import numpy as np
import pandas as pd
from typing import Union, List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import warnings


class VolatilityRegime(Enum):
	"""波动率状态枚举"""
	LOW = "low_volatility"  # 低波动率
	NORMAL = "normal_volatility"  # 正常波动率
	HIGH = "high_volatility"  # 高波动率
	EXPANDING = "expanding"  # 波动率扩张
	CONTRACTING = "contracting"  # 波动率收缩


@dataclass
class BollingerBands:
	"""布林带结果"""
	middle_band: np.ndarray  # 中轨（移动平均）
	upper_band: np.ndarray  # 上轨
	lower_band: np.ndarray  # 下轨
	bandwidth: np.ndarray  # 带宽（(上轨-下轨)/中轨）
	percent_b: np.ndarray  # %B指标（价格在布林带中的位置）


@dataclass
class ATRResult:
	"""平均真实波幅结果"""
	atr_values: np.ndarray  # ATR序列
	percent_atr: np.ndarray  # ATR占价格的百分比


@dataclass
class KeltnerChannels:
	"""凯尔特纳通道结果"""
	middle_line: np.ndarray  # 中线（EMA）
	upper_channel: np.ndarray  # 上通道
	lower_channel: np.ndarray  # 下通道


class VolatilityIndicators:
	"""
	波动率指标计算器
	提供各种波动率测量指标的计算
	"""

	def __init__ (self, default_period: int = 20):
		"""
		初始化波动率指标计算器

		Args:
			default_period: 默认计算周期
		"""
		self.default_period = default_period

	def bollinger_bands (self, prices: Union[List[float], np.ndarray, pd.Series],
	                     period: Optional[int] = None,
	                     num_std: float = 2.0) -> BollingerBands:
		"""
		计算布林带 (Bollinger Bands)

		使用场景：
		- 识别波动率水平（带宽）
		- 判断超买超卖（价格触及上下轨）
		- 识别波动率挤压（带宽收缩）
		- 适合趋势和反转策略

		Args:
			prices: 价格序列
			period: 移动平均周期（默认20）
			num_std: 标准差倍数（默认2）

		Returns:
			BollingerBands: 布林带结果
		"""
		if period is None:
			period = self.default_period

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < period:
			raise ValueError(f"数据长度({len(prices)})必须大于周期({period})")

		n = len(prices)

		# 计算中轨（简单移动平均）
		middle_band = np.full(n, np.nan)
		upper_band = np.full(n, np.nan)
		lower_band = np.full(n, np.nan)
		bandwidth = np.full(n, np.nan)
		percent_b = np.full(n, np.nan)

		for i in range(period - 1, n):
			window = prices[i - period + 1:i + 1]

			# 移动平均
			ma = np.mean(window)
			middle_band[i] = ma

			# 标准差
			std = np.std(window, ddof=1)

			# 上下轨
			upper_band[i] = ma + num_std * std
			lower_band[i] = ma - num_std * std

			# 带宽
			bandwidth[i] = (upper_band[i] - lower_band[i]) / ma

			# %B指标
			if upper_band[i] != lower_band[i]:
				percent_b[i] = (prices[i] - lower_band[i]) / (upper_band[i] - lower_band[i])
			else:
				percent_b[i] = 0.5

		return BollingerBands(
			middle_band=middle_band,
			upper_band=upper_band,
			lower_band=lower_band,
			bandwidth=bandwidth,
			percent_b=percent_b
		)

	def average_true_range (self, high: Union[List[float], np.ndarray, pd.Series],
	                        low: Union[List[float], np.ndarray, pd.Series],
	                        close: Union[List[float], np.ndarray, pd.Series],
	                        period: Optional[int] = None) -> ATRResult:
		"""
		计算平均真实波幅 (ATR)

		使用场景：
		- 衡量市场波动率
		- 设置止损止盈（基于ATR）
		- 判断市场波动性变化
		- 适合所有市场环境

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			period: ATR周期（默认14）

		Returns:
			ATRResult: ATR结果
		"""
		if period is None:
			period = 14  # ATR常用14周期

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(close)

		# 计算真实波幅
		true_range = np.zeros(n)
		true_range[0] = high[0] - low[0]

		for i in range(1, n):
			tr1 = high[i] - low[i]
			tr2 = abs(high[i] - close[i - 1])
			tr3 = abs(low[i] - close[i - 1])
			true_range[i] = max(tr1, tr2, tr3)

		# 计算ATR
		atr_values = np.full(n, np.nan)
		percent_atr = np.full(n, np.nan)

		# 第一个ATR：简单平均
		atr_values[period - 1] = np.mean(true_range[:period])

		# 后续ATR：Wilder平滑
		for i in range(period, n):
			atr_values[i] = (atr_values[i - 1] * (period - 1) + true_range[i]) / period

		# 计算ATR占价格的百分比
		for i in range(period - 1, n):
			if close[i] > 0:
				percent_atr[i] = atr_values[i] / close[i] * 100

		return ATRResult(
			atr_values=atr_values,
			percent_atr=percent_atr
		)

	def keltner_channels (self, high: Union[List[float], np.ndarray, pd.Series],
	                      low: Union[List[float], np.ndarray, pd.Series],
	                      close: Union[List[float], np.ndarray, pd.Series],
	                      ema_period: int = 20,
	                      atr_period: int = 10,
	                      atr_multiplier: float = 2.0) -> KeltnerChannels:
		"""
		计算凯尔特纳通道 (Keltner Channels)

		使用场景：
		- 类似布林带，但使用ATR而不是标准差
		- 识别趋势方向和强度
		- 判断突破信号
		- 适合趋势跟踪策略

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			ema_period: EMA周期（默认20）
			atr_period: ATR周期（默认10）
			atr_multiplier: ATR倍数（默认2）

		Returns:
			KeltnerChannels: 凯尔特纳通道结果
		"""
		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)

		n = len(close)

		# 计算中线的EMA
		from .trend_indicators import exponential_moving_average
		middle_line = exponential_moving_average(close, ema_period)

		# 计算ATR
		atr_result = self.average_true_range(high, low, close, atr_period)
		atr_values = atr_result.atr_values

		# 计算上下通道
		upper_channel = np.full(n, np.nan)
		lower_channel = np.full(n, np.nan)

		for i in range(ema_period - 1, n):
			if not np.isnan(middle_line[i]) and not np.isnan(atr_values[i]):
				upper_channel[i] = middle_line[i] + atr_multiplier * atr_values[i]
				lower_channel[i] = middle_line[i] - atr_multiplier * atr_values[i]

		return KeltnerChannels(
			middle_line=middle_line,
			upper_channel=upper_channel,
			lower_channel=lower_channel
		)

	def donchian_channels (self, high: Union[List[float], np.ndarray, pd.Series],
	                       low: Union[List[float], np.ndarray, pd.Series],
	                       period: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
		"""
		计算唐奇安通道 (Donchian Channels)

		使用场景：
		- 识别突破交易机会
		- 判断支撑阻力位
		- 海龟交易法则的核心指标
		- 适合趋势突破策略

		Args:
			high: 最高价序列
			low: 最低价序列
			period: 通道周期（默认20）

		Returns:
			Tuple[np.ndarray, np.ndarray]: (上通道，下通道)
		"""
		if period is None:
			period = self.default_period

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)

		n = len(high)

		upper_channel = np.full(n, np.nan)
		lower_channel = np.full(n, np.nan)

		for i in range(period - 1, n):
			upper_channel[i] = np.max(high[i - period + 1:i + 1])
			lower_channel[i] = np.min(low[i - period + 1:i + 1])

		return upper_channel, lower_channel

	def standard_deviation_bands (self, prices: Union[List[float], np.ndarray, pd.Series],
	                              period: Optional[int] = None,
	                              num_std: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
		"""
		计算标准差带 (Standard Deviation Bands)

		使用场景：
		- 类似布林带但使用固定标准差倍数
		- 识别统计意义上的异常值
		- 判断价格是否过度偏离
		- 适合均值回归策略

		Args:
			prices: 价格序列
			period: 计算周期（默认20）
			num_std: 标准差倍数（默认1）

		Returns:
			Tuple[np.ndarray, np.ndarray]: (上带，下带)
		"""
		if period is None:
			period = self.default_period

		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		n = len(prices)

		upper_band = np.full(n, np.nan)
		lower_band = np.full(n, np.nan)

		for i in range(period - 1, n):
			window = prices[i - period + 1:i + 1]
			mean = np.mean(window)
			std = np.std(window, ddof=1)

			upper_band[i] = mean + num_std * std
			lower_band[i] = mean - num_std * std

		return upper_band, lower_band

	def volatility_regime (self, prices: Union[List[float], np.ndarray, pd.Series],
	                       short_period: int = 10,
	                       long_period: int = 30,
	                       threshold_low: float = 0.1,
	                       threshold_high: float = 0.3) -> np.ndarray:
		"""
		判断波动率状态

		使用场景：
		- 识别市场波动率状态
		- 根据波动率调整交易策略
		- 风险管理（高波动率时降低仓位）

		Args:
			prices: 价格序列
			short_period: 短期波动率周期
			long_period: 长期波动率周期
			threshold_low: 低波动率阈值
			threshold_high: 高波动率阈值

		Returns:
			np.ndarray: 波动率状态序列（字符串枚举）
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		n = len(prices)

		# 计算收益率
		returns = np.diff(prices) / prices[:-1]
		returns = np.concatenate([[0], returns])  # 对齐长度

		# 计算波动率（收益率标准差）
		short_vol = np.full(n, np.nan)
		long_vol = np.full(n, np.nan)

		for i in range(short_period - 1, n):
			short_vol[i] = np.std(returns[i - short_period + 1:i + 1], ddof=1)

		for i in range(long_period - 1, n):
			long_vol[i] = np.std(returns[i - long_period + 1:i + 1], ddof=1)

		# 判断波动率状态
		regime = np.full(n, VolatilityRegime.NORMAL.value, dtype=object)

		for i in range(max(short_period, long_period) - 1, n):
			if not np.isnan(short_vol[i]) and not np.isnan(long_vol[i]):
				# 波动率水平
				if short_vol[i] < threshold_low:
					regime[i] = VolatilityRegime.LOW.value
				elif short_vol[i] > threshold_high:
					regime[i] = VolatilityRegime.HIGH.value

				# 波动率变化趋势
				if short_vol[i] > long_vol[i] * 1.2:
					regime[i] = VolatilityRegime.EXPANDING.value
				elif short_vol[i] < long_vol[i] * 0.8:
					regime[i] = VolatilityRegime.CONTRACTING.value

		return regime

	def bollinger_squeeze (self, prices: Union[List[float], np.ndarray, pd.Series],
	                       bb_period: int = 20,
	                       bb_std: float = 2.0,
	                       kc_period: int = 20,
	                       kc_atr_multiplier: float = 1.5,
	                       squeeze_threshold: float = 0.5, high=None, low=None) -> np.ndarray:
		"""
		判断布林带挤压 (Bollinger Band Squeeze)

		使用场景：
		- 识别低波动率时期（挤压）
		- 预测波动率扩张（突破）
		- 寻找大行情前的准备阶段
		- 适合突破策略

		Args:
			prices: 价格序列
			bb_period: 布林带周期
			bb_std: 布林带标准差倍数
			kc_period: 凯尔特纳通道周期
			kc_atr_multiplier: 凯尔特纳通道ATR倍数
			squeeze_threshold: 挤压阈值

		Returns:
			np.ndarray: 布尔序列（True=挤压状态）
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		n = len(prices)

		# 计算布林带带宽
		bb_result = self.bollinger_bands(prices, bb_period, bb_std)
		bb_bandwidth = bb_result.bandwidth

		# 基于价格序列估算最高价/最低价（无OHLC数据时的降级方案）
		# 用前日收盘价 ± ATR估算当日高低价
		if high is None or low is None:
			logger.warning("bollinger_squeeze: 未提供high/low数据，使用价格序列估算，精度可能下降")
			# 先用简易方法估算初始高低价
			est_high = prices * 1.01
			est_low = prices * 0.99
			# 二次迭代：基于初步ATR refine估算
			prelim_atr = np.full(n, np.nan)
			for i in range(1, n):
				tr_val = max(est_high[i] - est_low[i],
				             abs(est_high[i] - prices[i - 1]),
				             abs(est_low[i] - prices[i - 1]))
				prelim_atr[i] = tr_val if i == 1 else (prelim_atr[i - 1] * (kc_period - 1) + tr_val) / kc_period
			# 用ATR估算更合理的高低范围
			atr_est = np.nanmean(prelim_atr)
			est_high = prices + atr_est * 0.5 if not np.isnan(atr_est) else prices * 1.01
			est_low = prices - atr_est * 0.5 if not np.isnan(atr_est) else prices * 0.99
		else:
			est_high = high
			est_low = low

		from .trend_indicators import exponential_moving_average

		# 中线（EMA）
		kc_middle = exponential_moving_average(prices, kc_period)

		# 计算ATR
		atr = np.full(n, np.nan)
		for i in range(1, n):
			tr = max(est_high[i] - est_low[i],
			         abs(est_high[i] - prices[i - 1]),
			         abs(est_low[i] - prices[i - 1]))
			if i == 1:
				atr[i] = tr
			else:
				atr[i] = (atr[i - 1] * (kc_period - 1) + tr) / kc_period

		# 凯尔特纳通道带宽
		kc_bandwidth = np.full(n, np.nan)
		for i in range(kc_period - 1, n):
			if not np.isnan(kc_middle[i]) and not np.isnan(atr[i]):
				kc_bandwidth[i] = (kc_atr_multiplier * atr[i]) / kc_middle[i] * 2

		# 判断挤压状态
		squeeze = np.full(n, False, dtype=bool)

		for i in range(max(bb_period, kc_period) - 1, n):
			if not np.isnan(bb_bandwidth[i]) and not np.isnan(kc_bandwidth[i]):
				# 布林带带宽小于凯尔特纳通道带宽 * 阈值
				if bb_bandwidth[i] < kc_bandwidth[i] * squeeze_threshold:
					squeeze[i] = True

		return squeeze


# 便捷函数
def bollinger_bands (prices: Union[List[float], np.ndarray, pd.Series],
                     period: int = 20,
                     num_std: float = 2.0) -> BollingerBands:
	"""计算布林带"""
	return VolatilityIndicators().bollinger_bands(prices, period, num_std)


def average_true_range (high: Union[List[float], np.ndarray, pd.Series],
                        low: Union[List[float], np.ndarray, pd.Series],
                        close: Union[List[float], np.ndarray, pd.Series],
                        period: int = 14) -> ATRResult:
	"""计算平均真实波幅"""
	return VolatilityIndicators().average_true_range(high, low, close, period)


def keltner_channels (high: Union[List[float], np.ndarray, pd.Series],
                      low: Union[List[float], np.ndarray, pd.Series],
                      close: Union[List[float], np.ndarray, pd.Series],
                      ema_period: int = 20,
                      atr_period: int = 10,
                      atr_multiplier: float = 2.0) -> KeltnerChannels:
	"""计算凯尔特纳通道"""
	return VolatilityIndicators().keltner_channels(
		high, low, close, ema_period, atr_period, atr_multiplier)


def donchian_channels (high: Union[List[float], np.ndarray, pd.Series],
                       low: Union[List[float], np.ndarray, pd.Series],
                       period: int = 20) -> Tuple[np.ndarray, np.ndarray]:
	"""计算唐奇安通道"""
	return VolatilityIndicators().donchian_channels(high, low, period)


def standard_deviation_bands (prices: Union[List[float], np.ndarray, pd.Series],
                              period: int = 20,
                              num_std: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
	"""计算标准差带"""
	return VolatilityIndicators().standard_deviation_bands(prices, period, num_std)


def volatility_regime (prices: Union[List[float], np.ndarray, pd.Series],
                       short_period: int = 10,
                       long_period: int = 30) -> np.ndarray:
	"""判断波动率状态"""
	return VolatilityIndicators().volatility_regime(prices, short_period, long_period)


def bollinger_squeeze (prices: Union[List[float], np.ndarray, pd.Series],
                       bb_period: int = 20,
                       bb_std: float = 2.0) -> np.ndarray:
	"""判断布林带挤压"""
	return VolatilityIndicators().bollinger_squeeze(prices, bb_period, bb_std)