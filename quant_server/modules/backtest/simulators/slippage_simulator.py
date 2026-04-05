# -*- coding: utf-8 -*-
"""
滑点模拟器

负责模拟交易滑点
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)


class SlippageSimulator:
	"""
	滑点模拟器

	负责模拟交易滑点
	"""

	def __init__ (self, fixed_slippage: float = 0.0001, variable_slippage: float = 0.0001, volume_factor: float = 1e-6):
		"""
		初始化滑点模拟器

		Args:
			fixed_slippage: 固定滑点
			variable_slippage: 可变滑点系数
			volume_factor: 交易量影响因子
		"""
		self.fixed_slippage = fixed_slippage
		self.variable_slippage = variable_slippage
		self.volume_factor = volume_factor

	def calculate_slippage (self, side: str, volume: float, current_price: float, market_volume: float = 1e6) -> float:
		"""
		计算滑点

		Args:
			side: 交易方向 (buy/sell)
			volume: 交易量
			current_price: 当前价格
			market_volume: 市场交易量

		Returns:
			滑点值（正数表示价格上升，负数表示价格下降）
		"""
		try:
			# 计算滑点
			# 固定滑点
			fixed_slippage = self.fixed_slippage

			# 可变滑点（基于交易量）
			variable_slippage = self.variable_slippage * (volume / market_volume) ** 0.5

			# 总滑点
			total_slippage = fixed_slippage + variable_slippage

			# 根据交易方向调整滑点
			if side == "buy":
				# 买入时价格上升
				slippage = total_slippage
			else:
				# 卖出时价格下降
				slippage = -total_slippage

			# 添加随机噪声
			noise = np.random.normal(0, total_slippage * 0.1)
			slippage += noise

			return slippage
		except Exception as e:
			logger.error(f"计算滑点失败: {str(e)}")
			return 0
