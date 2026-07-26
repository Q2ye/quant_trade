# -*- coding: utf-8 -*-
"""
成本模拟器

负责模拟交易成本
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class CostSimulator:
	"""
	成本模拟器

	负责模拟交易成本
	"""

	def __init__ (self, commission_rate: float = 0.0001, min_commission: float = 0.0, slippage_rate: float = 0.0001,
	              tax_rate: float = 0.001):
		"""
		初始化成本模拟器

		Args:
			commission_rate: 佣金费率
			min_commission: 最低佣金
			slippage_rate: 滑点费率
			tax_rate: 税率（卖出时收取）
		"""
		self.commission_rate = commission_rate
		self.min_commission = min_commission
		self.slippage_rate = slippage_rate
		self.tax_rate = tax_rate

	def calculate_cost (self, side: str, volume: float, price: float) -> Dict[str, float]:
		"""
		计算交易成本

		Args:
			side: 交易方向 (buy/sell)
			volume: 交易量
			price: 交易价格

		Returns:
			成本明细 {"commission": 佣金, "slippage": 滑点成本, "tax": 税费, "total": 总成本}
		"""
		try:
			# 计算成交额
			amount = volume * price

			# 计算佣金
			commission = amount * self.commission_rate
			commission = max(commission, self.min_commission)

			# 计算滑点成本
			slippage = amount * self.slippage_rate

			# 计算税费（卖出时收取）
			tax = amount * self.tax_rate if side == "sell" else 0

			# 计算总成本
			total = commission + slippage + tax

			return {
				"commission": commission,
				"slippage": slippage,
				"tax": tax,
				"total": total
			}
		except Exception as e:
			logger.error(f"计算交易成本失败: {str(e)}")
			return {
				"commission": 0,
				"slippage": 0,
				"tax": 0,
				"total": 0
			}
