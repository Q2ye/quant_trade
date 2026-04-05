# -*- coding: utf-8 -*-
"""
市场模拟器

负责模拟市场环境
"""
import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketSimulator:
	"""
	市场模拟器

	负责模拟市场环境
	"""

	def __init__ (self):
		"""
		初始化市场模拟器
		"""
		pass

	def simulate_market (self, market_data: pd.DataFrame) -> pd.DataFrame:
		"""
		模拟市场环境

		Args:
			market_data: 原始市场数据

		Returns:
			模拟后的市场数据
		"""
		try:
			# 复制原始数据
			simulated_data = market_data.copy()

			# 添加市场噪声
			simulated_data = self._add_market_noise(simulated_data)

			# 模拟市场流动性
			simulated_data = self._simulate_liquidity(simulated_data)

			return simulated_data
		except Exception as e:
			logger.error(f"模拟市场环境失败: {str(e)}")
			return market_data

	@staticmethod
	def _add_market_noise (market_data: pd.DataFrame) -> pd.DataFrame:
		"""
		添加市场噪声

		Args:
			market_data: 市场数据

		Returns:
			添加噪声后的市场数据
		"""
		# 为价格添加小幅度随机噪声
		for col in ['open', 'high', 'low', 'close']:
			if col in market_data.columns:
				# 计算价格波动率
				volatility = market_data[col].std()
				# 添加噪声（标准差为波动率的1%）
				noise = np.random.normal(0, volatility * 0.01, len(market_data))
				market_data[col] += noise

		return market_data

	@staticmethod
	def _simulate_liquidity (market_data: pd.DataFrame) -> pd.DataFrame:
		"""
		模拟市场流动性

		Args:
			market_data: 市场数据

		Returns:
			模拟流动性后的市场数据
		"""
		# 计算成交量的波动率
		if 'volume' in market_data.columns:
			volume_volatility = market_data['volume'].std()
			# 添加成交量噪声
			volume_noise = np.random.normal(0, volume_volatility * 0.1, len(market_data))
			market_data['volume'] = market_data['volume'] + volume_noise
			# 确保成交量不为负
			market_data['volume'] = market_data['volume'].apply(lambda x: max(0, x))

		return market_data

	@staticmethod
	def get_price (market_data: pd.DataFrame, symbol: str, timestamp: Any) -> float:
		"""
		获取指定时间的价格

		Args:
			market_data: 市场数据
			symbol: 标的代码
			timestamp: 时间戳

		Returns:
			价格
		"""
		try:
			# 这里简单返回收盘价，实际可能需要更复杂的逻辑
			if not market_data.empty:
				# 使用 .iloc[-1, market_data.columns.get_loc('close')] 确保获取标量值
				close_col_index = market_data.columns.get_loc('close')
				price = market_data.iloc[-1, close_col_index]
				return float(price) if price is not None else 0.0
			return 0.0
		except Exception as e:
			logger.error(f"获取价格失败: {str(e)}")
			return 0.0