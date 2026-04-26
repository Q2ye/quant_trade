# order_validator.py   # 订单验证器

from typing import Dict, Any, Optional, Tuple


class OrderValidator:
	"""订单验证器类"""

	def __init__ (self, config: Optional[Dict[str, Any]] = None):
		"""
		初始化订单验证器

		Args:
			config: 验证配置
		"""
		self.config = config or {}
		# 默认验证规则
		self.default_rules = {
			"min_price": 0.01,  # 最小价格
			"max_price": 10000,  # 最大价格
			"min_quantity": 100,  # 最小数量（A股100股为1手）
			"max_quantity": 1000000,  # 最大数量
			"max_amount": 10000000,  # 最大金额
			"allowed_directions": ["buy", "sell"],  # 允许的交易方向
			"allowed_order_types": ["limit", "market"],  # 允许的订单类型
		}
		# 合并配置
		self.rules = {**self.default_rules, **self.config.get("rules", {})}

	def validate_order (self, order_data: Dict[str, Any]) -> Tuple[bool, str]:
		"""
		验证订单数据

		Args:
			order_data: 订单数据

		Returns:
			Tuple[bool, str]: (是否有效, 错误信息)
		"""
		# 验证必填字段
		required_fields = ["ts_code", "direction", "price", "quantity"]
		for field in required_fields:
			if field not in order_data:
				return False, f"缺少必填字段: {field}"

		# 验证股票代码
		ts_code = order_data.get("ts_code")
		if not isinstance(ts_code, str) or len(ts_code) < 6:
			return False, "股票代码无效"

		# 验证交易方向
		direction = order_data.get("direction")
		if direction not in self.rules["allowed_directions"]:
			return False, f"交易方向无效，允许的方向: {self.rules['allowed_directions']}"

		# 验证价格
		price = order_data.get("price")
		if not isinstance(price, (int, float)) or price < self.rules["min_price"] or price > self.rules["max_price"]:
			return False, f"价格无效，范围: {self.rules['min_price']} - {self.rules['max_price']}"

		# 验证数量
		quantity = order_data.get("quantity")
		if not isinstance(quantity, int) or quantity < self.rules["min_quantity"] or quantity > self.rules[
			"max_quantity"]:
			return False, f"数量无效，范围: {self.rules['min_quantity']} - {self.rules['max_quantity']}"

		# 验证数量是否为100的倍数（A股）
		if quantity % 100 != 0:
			return False, "数量必须是100的倍数"

		# 验证金额
		amount = price * quantity
		if amount > self.rules["max_amount"]:
			return False, f"金额超过限制: {self.rules['max_amount']}"

		# 验证订单类型
		order_type = order_data.get("order_type", "limit")
		if order_type not in self.rules["allowed_order_types"]:
			return False, f"订单类型无效，允许的类型: {self.rules['allowed_order_types']}"

		# 验证其他可选字段
		if "client_order_id" in order_data:
			client_order_id = order_data["client_order_id"]
			if not isinstance(client_order_id, str):
				return False, "客户端订单ID必须是字符串"

		if "time_in_force" in order_data:
			time_in_force = order_data["time_in_force"]
			allowed_time_in_force = ["GTC", "DAY", "IOC", "FOK"]
			if time_in_force not in allowed_time_in_force:
				return False, f"时间有效期无效，允许的值: {allowed_time_in_force}"

		return True, "订单验证通过"

	def validate_batch_orders (self, orders: list) -> Tuple[bool, list]:
		"""
		批量验证订单

		Args:
			orders: 订单列表

		Returns:
			Tuple[bool, list]: (是否全部有效, 错误信息列表)
		"""
		errors = []
		all_valid = True

		for i, order in enumerate(orders):
			is_valid, message = self.validate_order(order)
			if not is_valid:
				all_valid = False
				errors.append(f"订单 {i + 1}: {message}")

		return all_valid, errors

	@staticmethod
	def validate_signal(signal_data: Dict[str, Any]) -> Tuple[bool, str]:
		"""
		验证信号数据

		Args:
			signal_data: 信号数据

		Returns:
			Tuple[bool, str]: (是否有效, 错误信息)
		"""
		# 验证必填字段
		required_fields = ["ts_code", "direction", "price", "quantity"]
		for field in required_fields:
			if field not in signal_data:
				return False, f"信号缺少必填字段: {field}"

		# 验证股票代码
		ts_code = signal_data.get("ts_code")
		if not isinstance(ts_code, str) or len(ts_code) < 6:
			return False, "股票代码无效"

		# 验证交易方向
		direction = signal_data.get("direction")
		if direction not in ["buy", "sell"]:
			return False, "交易方向无效，只允许 buy 或 sell"

		# 验证价格
		price = signal_data.get("price")
		if not isinstance(price, (int, float)) or price <= 0:
			return False, "价格必须大于0"

		# 验证数量
		quantity = signal_data.get("quantity")
		if not isinstance(quantity, int) or quantity <= 0:
			return False, "数量必须大于0"

		# 验证其他可选字段
		if "strategy_id" in signal_data:
			strategy_id = signal_data["strategy_id"]
			if not isinstance(strategy_id, (str, int)):
				return False, "策略ID必须是字符串或整数"

		if "signal_id" in signal_data:
			signal_id = signal_data["signal_id"]
			if not isinstance(signal_id, (str, int)):
				return False, "信号ID必须是字符串或整数"

		return True, "信号验证通过"
