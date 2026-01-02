"""
成交量指标模块
提供OBV、VWAP、MFI等成交量分析指标
使用场景：量价分析、资金流向判断、趋势确认
"""

import numpy as np
import pandas as pd
from typing import Union, List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import warnings


@dataclass
class VolumeProfile:
	"""成交量分布"""
	price_levels: np.ndarray
	volume_at_price: np.ndarray
	vwap: float  # 成交量加权平均价格
	poc: float  # 成交量最大点 (Point of Control)
	value_area: Tuple[float, float]  # 价值区间


@dataclass
class VolumeAnalysis:
	"""成交量分析结果"""
	volume_trend: np.ndarray  # 成交量趋势
	volume_ratio: np.ndarray  # 成交量比率
	accumulation: np.ndarray  # 累积分布
	money_flow: np.ndarray  # 资金流向


class VolumeIndicators:
	"""
	成交量指标计算器
	提供各种成交量分析指标的计算
	"""

	def __init__ (self, default_period: int = 14):
		"""
		初始化成交量指标计算器

		Args:
			default_period: 默认计算周期
		"""
		self.default_period = default_period

	def on_balance_volume (self, close: Union[List[float], np.ndarray, pd.Series],
	                       volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
		"""
		计算能量潮指标 (OBV)

		使用场景：
		- 判断资金流向（OBV上升表示资金流入）
		- 确认价格趋势（价涨量增为健康上涨）
		- 识别背离信号（价格新高但OBV未新高）
		- 适合趋势确认

		Args:
			close: 收盘价序列
			volume: 成交量序列

		Returns:
			np.ndarray: OBV序列
		"""
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		if len(close) != len(volume):
			raise ValueError("收盘价和成交量序列长度必须相同")

		n = len(close)
		obv = np.zeros(n)

		obv[0] = volume[0]

		for i in range(1, n):
			if close[i] > close[i - 1]:
				# 价格上涨，成交量计入OBV
				obv[i] = obv[i - 1] + volume[i]
			elif close[i] < close[i - 1]:
				# 价格下跌，成交量从OBV中减去
				obv[i] = obv[i - 1] - volume[i]
			else:
				# 价格不变，OBV不变
				obv[i] = obv[i - 1]

		return obv

	def volume_weighted_average_price (self,
	                                   high: Union[List[float], np.ndarray, pd.Series],
	                                   low: Union[List[float], np.ndarray, pd.Series],
	                                   close: Union[List[float], np.ndarray, pd.Series],
	                                   volume: Union[List[float], np.ndarray, pd.Series],
	                                   period: Optional[int] = None) -> np.ndarray:
		"""
		计算成交量加权平均价格 (VWAP)

		使用场景：
		- 日内交易的重要参考指标
		- 判断机构平均成本
		- 识别支撑阻力位
		- 适合日内和短线交易

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			volume: 成交量序列
			period: VWAP周期（通常为当日或特定时段）

		Returns:
			np.ndarray: VWAP序列
		"""
		if period is None:
			period = len(high)  # 默认使用所有数据

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(close)

		# 计算典型价格
		typical_price = (high + low + close) / 3

		# 计算VWAP
		vwap = np.full(n, np.nan)

		for i in range(period - 1, n):
			start_idx = max(0, i - period + 1)
			window_tp = typical_price[start_idx:i + 1]
			window_vol = volume[start_idx:i + 1]

			# 成交量加权平均
			vwap[i] = np.sum(window_tp * window_vol) / np.sum(window_vol)

		return vwap

	def accumulation_distribution_line (self,
	                                    high: Union[List[float], np.ndarray, pd.Series],
	                                    low: Union[List[float], np.ndarray, pd.Series],
	                                    close: Union[List[float], np.ndarray, pd.Series],
	                                    volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
		"""
		计算累积分布线 (A/D Line)

		使用场景：
		- 类似OBV，但考虑价格区间
		- 更精确的资金流向分析
		- 确认价格趋势
		- 识别背离

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			volume: 成交量序列

		Returns:
			np.ndarray: A/D线序列
		"""
		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(close)

		# 计算资金流乘数
		money_flow_multiplier = np.zeros(n)
		for i in range(n):
			if high[i] != low[i]:
				money_flow_multiplier[i] = ((close[i] - low[i]) - (high[i] - close[i])) / (high[i] - low[i])

		# 计算资金流量
		money_flow_volume = money_flow_multiplier * volume

		# 计算累积分布线
		ad_line = np.zeros(n)
		ad_line[0] = money_flow_volume[0]

		for i in range(1, n):
			ad_line[i] = ad_line[i - 1] + money_flow_volume[i]

		return ad_line

	def chaikin_money_flow (self,
	                        high: Union[List[float], np.ndarray, pd.Series],
	                        low: Union[List[float], np.ndarray, pd.Series],
	                        close: Union[List[float], np.ndarray, pd.Series],
	                        volume: Union[List[float], np.ndarray, pd.Series],
	                        period: Optional[int] = None) -> np.ndarray:
		"""
		计算蔡金资金流 (CMF)

		使用场景：
		- 衡量资金流入流出的强度
		- 判断买卖压力
		- 确认突破的有效性
		- 适合短线交易

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			volume: 成交量序列
			period: CMF周期（默认20）

		Returns:
			np.ndarray: CMF序列（-1到+1）
		"""
		if period is None:
			period = self.default_period

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(close)

		# 计算资金流乘数
		money_flow_multiplier = np.zeros(n)
		for i in range(n):
			if high[i] != low[i]:
				money_flow_multiplier[i] = ((close[i] - low[i]) - (high[i] - close[i])) / (high[i] - low[i])

		# 计算资金流量
		money_flow_volume = money_flow_multiplier * volume

		# 计算CMF
		cmf = np.full(n, np.nan)

		for i in range(period - 1, n):
			sum_mfv = np.sum(money_flow_volume[i - period + 1:i + 1])
			sum_vol = np.sum(volume[i - period + 1:i + 1])

			if sum_vol > 0:
				cmf[i] = sum_mfv / sum_vol

		return cmf

	def money_flow_index (self,
	                      high: Union[List[float], np.ndarray, pd.Series],
	                      low: Union[List[float], np.ndarray, pd.Series],
	                      close: Union[List[float], np.ndarray, pd.Series],
	                      volume: Union[List[float], np.ndarray, pd.Series],
	                      period: Optional[int] = None) -> np.ndarray:
		"""
		计算资金流量指数 (MFI)

		使用场景：
		- 类似RSI，但加入成交量因素
		- 识别超买超卖（通常80以上超买，20以下超卖）
		- 判断资金流向
		- 适合量价分析

		Args:
			high: 最高价序列
			low: 最低价序列
			close: 收盘价序列
			volume: 成交量序列
			period: MFI周期（默认14）

		Returns:
			np.ndarray: MFI序列（0-100）
		"""
		if period is None:
			period = self.default_period

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(close)

		# 计算典型价格
		typical_price = (high + low + close) / 3

		# 计算原始资金流
		raw_money_flow = typical_price * volume

		# 计算正向和负向资金流
		positive_flow = np.zeros(n)
		negative_flow = np.zeros(n)

		for i in range(1, n):
			if typical_price[i] > typical_price[i - 1]:
				positive_flow[i] = raw_money_flow[i]
			elif typical_price[i] < typical_price[i - 1]:
				negative_flow[i] = raw_money_flow[i]

		# 计算MFI
		mfi = np.full(n, np.nan)

		for i in range(period, n):
			sum_positive = np.sum(positive_flow[i - period + 1:i + 1])
			sum_negative = np.sum(negative_flow[i - period + 1:i + 1])

			if sum_negative > 0:
				money_ratio = sum_positive / sum_negative
				mfi[i] = 100 - (100 / (1 + money_ratio))
			else:
				mfi[i] = 100  # 如果负向流为0，MFI为100

		return mfi

	def ease_of_movement (self,
	                      high: Union[List[float], np.ndarray, pd.Series],
	                      low: Union[List[float], np.ndarray, pd.Series],
	                      volume: Union[List[float], np.ndarray, pd.Series],
	                      period: Optional[int] = None) -> np.ndarray:
		"""
		计算简易波动指标 (EOM)

		使用场景：
		- 衡量价格变动的容易程度
		- 识别低成交量下的价格变动
		- 判断趋势强度
		- 适合波动性分析

		Args:
			high: 最高价序列
			low: 最低价序列
			volume: 成交量序列
			period: EOM周期（默认14）

		Returns:
			np.ndarray: EOM序列
		"""
		if period is None:
			period = self.default_period

		if isinstance(high, (list, pd.Series)):
			high = np.array(high)
		if isinstance(low, (list, pd.Series)):
			low = np.array(low)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(high)

		# 计算中点移动距离和成交量比例
		distance_moved = np.zeros(n)
		box_ratio = np.zeros(n)

		for i in range(1, n):
			# 中点移动距离
			midpoint_move = (high[i] + low[i]) / 2 - (high[i - 1] + low[i - 1]) / 2

			# 价格区间
			high_low_range = high[i] - low[i]

			# 成交量调整
			if volume[i] > 0 and high_low_range > 0:
				distance_moved[i] = midpoint_move
				box_ratio[i] = (volume[i] / 10000) / high_low_range

		# 计算EOM
		eom = np.full(n, np.nan)

		for i in range(period, n):
			sum_distance = np.sum(distance_moved[i - period + 1:i + 1])
			sum_box_ratio = np.sum(box_ratio[i - period + 1:i + 1])

			if sum_box_ratio > 0:
				eom[i] = sum_distance / sum_box_ratio

		return eom

	def volume_price_trend (self,
	                        close: Union[List[float], np.ndarray, pd.Series],
	                        volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
		"""
		计算量价趋势指标 (VPT)

		使用场景：
		- 类似OBV，但使用百分比变化
		- 更敏感的量价关系分析
		- 确认趋势强度
		- 识别背离

		Args:
			close: 收盘价序列
			volume: 成交量序列

		Returns:
			np.ndarray: VPT序列
		"""
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(close)

		vpt = np.zeros(n)
		vpt[0] = volume[0]

		for i in range(1, n):
			if close[i - 1] > 0:
				price_change_percent = (close[i] - close[i - 1]) / close[i - 1] * 100
				vpt[i] = vpt[i - 1] + volume[i] * price_change_percent

		return vpt

	def negative_volume_index (self,
	                           close: Union[List[float], np.ndarray, pd.Series],
	                           volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
		"""
		计算负成交量指标 (NVI)

		使用场景：
		- 识别聪明资金行为（低成交量时的价格变动）
		- 判断长期趋势
		- 与PVI（正成交量指标）结合使用
		- 适合长期投资

		Args:
			close: 收盘价序列
			volume: 成交量序列

		Returns:
			np.ndarray: NVI序列
		"""
		if isinstance(close, (list, pd.Series)):
			close = np.array(close)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(close)

		nvi = np.zeros(n)
		nvi[0] = 1000  # 初始值

		for i in range(1, n):
			if volume[i] < volume[i - 1]:
				# 成交量下降，更新NVI
				nvi[i] = nvi[i - 1] * (1 + (close[i] - close[i - 1]) / close[i - 1])
			else:
				# 成交量未下降，NVI不变
				nvi[i] = nvi[i - 1]

		return nvi

	def volume_confirmation (self, prices: Union[List[float], np.ndarray, pd.Series],
	                         volume: Union[List[float], np.ndarray, pd.Series],
	                         ma_period: int = 20) -> np.ndarray:
		"""
		判断成交量确认

		使用场景：
		- 确认价格趋势的有效性
		- 识别虚假突破
		- 判断趋势强度
		- 适合趋势确认

		Args:
			prices: 价格序列
			volume: 成交量序列
			ma_period: 移动平均周期

		Returns:
			np.ndarray: 布尔序列（True=成交量确认）
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(prices)

		from .trend_indicators import simple_moving_average
		price_ma = simple_moving_average(prices, ma_period)
		volume_ma = simple_moving_average(volume, ma_period)

		confirmation = np.full(n, False, dtype=bool)

		for i in range(ma_period - 1, n):
			if not np.isnan(price_ma[i]) and not np.isnan(volume_ma[i]):
				# 价格上涨且成交量放大
				if prices[i] > price_ma[i] and volume[i] > volume_ma[i]:
					confirmation[i] = True
				# 价格下跌且成交量放大
				elif prices[i] < price_ma[i] and volume[i] > volume_ma[i]:
					confirmation[i] = True

		return confirmation

	def volume_divergence (self, prices: Union[List[float], np.ndarray, pd.Series],
	                       volume: Union[List[float], np.ndarray, pd.Series],
	                       lookback_period: int = 10) -> np.ndarray:
		"""
		判断成交量背离

		使用场景：
		- 识别趋势反转信号
		- 判断顶部和底部
		- 预警趋势衰竭
		- 适合反转策略

		Args:
			prices: 价格序列
			volume: 成交量序列
			lookback_period: 回看周期

		Returns:
			np.ndarray: 背离信号序列（1=看跌背离，-1=看涨背离，0=无背离）
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		n = len(prices)

		divergence = np.zeros(n, dtype=int)

		for i in range(lookback_period, n):
			# 最近的价格和成交量
			recent_prices = prices[i - lookback_period:i + 1]
			recent_volume = volume[i - lookback_period:i + 1]

			# 找到价格和成交量的极值点
			price_high_idx = np.argmax(recent_prices)
			price_low_idx = np.argmin(recent_prices)
			volume_high_idx = np.argmax(recent_volume)
			volume_low_idx = np.argmin(recent_volume)

			# 看跌背离：价格新高但成交量未新高
			if price_high_idx == lookback_period and volume_high_idx != lookback_period:
				if recent_volume[-1] < recent_volume[volume_high_idx]:
					divergence[i] = 1  # 看跌背离

			# 看涨背离：价格新低但成交量未新低
			if price_low_idx == lookback_period and volume_low_idx != lookback_period:
				if recent_volume[-1] > recent_volume[volume_low_idx]:
					divergence[i] = -1  # 看涨背离

		return divergence

	def create_volume_profile (self,
	                           prices: Union[List[float], np.ndarray, pd.Series],
	                           volume: Union[List[float], np.ndarray, pd.Series],
	                           num_bins: int = 20) -> VolumeProfile:
		"""
		创建成交量分布

		使用场景：
		- 分析成交量在不同价格区间的分布
		- 识别支撑阻力位（高成交量区域）
		- 判断市场成本结构
		- 适合日内和短线交易

		Args:
			prices: 价格序列
			volume: 成交量序列
			num_bins: 价格区间数量

		Returns:
			VolumeProfile: 成交量分布
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)
		if isinstance(volume, (list, pd.Series)):
			volume = np.array(volume)

		# 创建价格区间
		min_price = np.min(prices)
		max_price = np.max(prices)
		price_bins = np.linspace(min_price, max_price, num_bins)

		# 计算每个价格区间的成交量
		volume_at_price = np.zeros(num_bins)

		for i in range(len(prices)):
			# 找到价格所属的区间
			bin_idx = np.digitize(prices[i], price_bins) - 1
			bin_idx = max(0, min(bin_idx, num_bins - 1))
			volume_at_price[bin_idx] += volume[i]

		# 计算VWAP
		vwap = np.sum(prices * volume) / np.sum(volume)

		# 找到成交量最大点 (POC)
		poc_idx = np.argmax(volume_at_price)
		poc = price_bins[poc_idx]

		# 计算价值区间（成交量最大的70%区域）
		sorted_indices = np.argsort(volume_at_price)[::-1]
		cumulative_volume = 0
		total_volume = np.sum(volume_at_price)
		target_volume = total_volume * 0.7

		value_area_indices = []
		for idx in sorted_indices:
			cumulative_volume += volume_at_price[idx]
			value_area_indices.append(idx)
			if cumulative_volume >= target_volume:
				break

		value_area_prices = price_bins[value_area_indices]
		value_area = (np.min(value_area_prices), np.max(value_area_prices))

		return VolumeProfile(
			price_levels=price_bins,
			volume_at_price=volume_at_price,
			vwap=vwap,
			poc=poc,
			value_area=value_area
		)


# 便捷函数
def on_balance_volume (close: Union[List[float], np.ndarray, pd.Series],
                       volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
	"""计算能量潮指标"""
	return VolumeIndicators().on_balance_volume(close, volume)


def volume_weighted_average_price (high: Union[List[float], np.ndarray, pd.Series],
                                   low: Union[List[float], np.ndarray, pd.Series],
                                   close: Union[List[float], np.ndarray, pd.Series],
                                   volume: Union[List[float], np.ndarray, pd.Series],
                                   period: Optional[int] = None) -> np.ndarray:
	"""计算成交量加权平均价格"""
	return VolumeIndicators().volume_weighted_average_price(high, low, close, volume, period)


def accumulation_distribution_line (high: Union[List[float], np.ndarray, pd.Series],
                                    low: Union[List[float], np.ndarray, pd.Series],
                                    close: Union[List[float], np.ndarray, pd.Series],
                                    volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
	"""计算累积分布线"""
	return VolumeIndicators().accumulation_distribution_line(high, low, close, volume)


def chaikin_money_flow (high: Union[List[float], np.ndarray, pd.Series],
                        low: Union[List[float], np.ndarray, pd.Series],
                        close: Union[List[float], np.ndarray, pd.Series],
                        volume: Union[List[float], np.ndarray, pd.Series],
                        period: int = 20) -> np.ndarray:
	"""计算蔡金资金流"""
	return VolumeIndicators().chaikin_money_flow(high, low, close, volume, period)


def money_flow_index (high: Union[List[float], np.ndarray, pd.Series],
                      low: Union[List[float], np.ndarray, pd.Series],
                      close: Union[List[float], np.ndarray, pd.Series],
                      volume: Union[List[float], np.ndarray, pd.Series],
                      period: int = 14) -> np.ndarray:
	"""计算资金流量指数"""
	return VolumeIndicators().money_flow_index(high, low, close, volume, period)


def ease_of_movement (high: Union[List[float], np.ndarray, pd.Series],
                      low: Union[List[float], np.ndarray, pd.Series],
                      volume: Union[List[float], np.ndarray, pd.Series],
                      period: int = 14) -> np.ndarray:
	"""计算简易波动指标"""
	return VolumeIndicators().ease_of_movement(high, low, volume, period)


def volume_price_trend (close: Union[List[float], np.ndarray, pd.Series],
                        volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
	"""计算量价趋势指标"""
	return VolumeIndicators().volume_price_trend(close, volume)


def negative_volume_index (close: Union[List[float], np.ndarray, pd.Series],
                           volume: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
	"""计算负成交量指标"""
	return VolumeIndicators().negative_volume_index(close, volume)


def volume_confirmation (prices: Union[List[float], np.ndarray, pd.Series],
                         volume: Union[List[float], np.ndarray, pd.Series],
                         ma_period: int = 20) -> np.ndarray:
	"""判断成交量确认"""
	return VolumeIndicators().volume_confirmation(prices, volume, ma_period)


def volume_divergence (prices: Union[List[float], np.ndarray, pd.Series],
                       volume: Union[List[float], np.ndarray, pd.Series],
                       lookback_period: int = 10) -> np.ndarray:
	"""判断成交量背离"""
	return VolumeIndicators().volume_divergence(prices, volume, lookback_period)


def create_volume_profile (prices: Union[List[float], np.ndarray, pd.Series],
                           volume: Union[List[float], np.ndarray, pd.Series],
                           num_bins: int = 20) -> VolumeProfile:
	"""创建成交量分布"""
	return VolumeIndicators().create_volume_profile(prices, volume, num_bins)