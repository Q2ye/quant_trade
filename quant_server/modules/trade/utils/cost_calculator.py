# cost_calculator.py   # 成本计算器

from typing import Dict, Any, Optional


class CostCalculator:
	"""成本计算器类"""

	def __init__ (self, config: Optional[Dict[str, Any]] = None):
		"""
		初始化成本计算器

		Args:
			config: 成本计算配置
		"""
		self.config = config or {}
		# 默认费率配置
		self.default_rates = {
			"commission_rate": 0.0003,  # 佣金费率
			"min_commission": 5,  # 最低佣金
			"stamp_duty_rate": 0.001,  # 印花税费率
			"transfer_fee_rate": 0.00002,  # 过户费费率
			"min_transfer_fee": 1,  # 最低过户费
		}
		# 合并配置
		self.rates = {**self.default_rates, **self.config.get("rates", {})}

	def calculate_trade_cost (self, direction: str, price: float, quantity: int, ts_code: str = None) -> Dict[
		str, float]:
		"""
		计算交易成本

		Args:
			direction: 交易方向，buy 或 sell
			price: 交易价格
			quantity: 交易数量
			ts_code: 股票代码（可选）

		Returns:
			Dict[str, float]: 成本明细
		"""
		# 计算成交金额
		amount = price * quantity

		# 计算佣金
		commission = amount * self.rates["commission_rate"]
		commission = max(commission, self.rates["min_commission"])

		# 计算过户费（仅上海股票）
		transfer_fee = 0
		if ts_code and ts_code.endswith("SH"):
			transfer_fee = amount * self.rates["transfer_fee_rate"]
			transfer_fee = max(transfer_fee, self.rates["min_transfer_fee"])

		# 计算印花税（仅卖出）
		stamp_duty = 0
		if direction == "sell":
			stamp_duty = amount * self.rates["stamp_duty_rate"]

		# 计算总成本
		total_cost = commission + transfer_fee + stamp_duty

		return {
			"amount": amount,
			"commission": commission,
			"transfer_fee": transfer_fee,
			"stamp_duty": stamp_duty,
			"total_cost": total_cost
		}

	@staticmethod
	def calculate_position_cost(current_price: float, quantity: int, average_cost: float) -> Dict[str, float]:
		"""
		计算持仓成本

		Args:
			current_price: 当前价格
			quantity: 持仓数量
			average_cost: 平均成本

		Returns:
			Dict[str, float]: 持仓成本明细
		"""
		# 计算当前市值
		market_value = current_price * quantity

		# 计算持仓成本
		position_cost = average_cost * quantity

		# 计算盈亏
		profit_loss = market_value - position_cost

		# 计算盈亏比例
		profit_loss_ratio = 0
		if position_cost > 0:
			profit_loss_ratio = (profit_loss / position_cost) * 100

		return {
			"market_value": market_value,
			"position_cost": position_cost,
			"profit_loss": profit_loss,
			"profit_loss_ratio": profit_loss_ratio,
			"average_cost": average_cost,
			"current_price": current_price,
			"quantity": quantity
		}

	def calculate_batch_trade_cost (self, trades: list) -> Dict[str, float]:
		"""
		计算批量交易成本

		Args:
			trades: 交易列表，每个元素包含 direction, price, quantity, ts_code

		Returns:
			Dict[str, float]: 总成本明细
		"""
		total_amount = 0
		total_commission = 0
		total_transfer_fee = 0
		total_stamp_duty = 0
		total_cost = 0

		for trade in trades:
			cost = self.calculate_trade_cost(
				direction=trade.get("direction"),
				price=trade.get("price"),
				quantity=trade.get("quantity"),
				ts_code=trade.get("ts_code")
			)
			total_amount += cost["amount"]
			total_commission += cost["commission"]
			total_transfer_fee += cost["transfer_fee"]
			total_stamp_duty += cost["stamp_duty"]
			total_cost += cost["total_cost"]

		return {
			"total_amount": total_amount,
			"total_commission": total_commission,
			"total_transfer_fee": total_transfer_fee,
			"total_stamp_duty": total_stamp_duty,
			"total_cost": total_cost
		}
