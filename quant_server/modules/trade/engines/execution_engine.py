# execution_engine.py   # 订单执行引擎

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from quant_server.core.engines.types.enums import EngineType
from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.system import EventEngine
from quant_server.modules.trade.adapters.broker_adapter import BrokerAdapter
from quant_server.modules.trade.engines.position_engine import PositionEngine
from quant_server.modules.trade.engines.risk_engine import RiskEngine


class ExecutionEngine(EngineBase):
	"""订单执行引擎"""

	def __init__ (
			self,
			config: Dict[str, Any],
			broker_adapter: BrokerAdapter,
			position_engine: PositionEngine,
			risk_engine: RiskEngine,
			event_engine: Optional[EventEngine] = None
	):
		# 导入 EngineConfig 类
		from quant_server.core.engines.types.entities import EngineConfig
		
		# 创建 EngineConfig 实例
		config_obj = EngineConfig(
			name=config.get("name", "execution_engine"),
			engine_type="execution_engine",
			dependencies=config.get("dependencies", []),
			max_retries=config.get("max_retries", 3),
			retry_delay=config.get("retry_delay", 1.0),
			config=config
		)
		
		super().__init__(config=config_obj, event_engine=event_engine)
		self.broker_adapter = broker_adapter
		self.position_engine = position_engine
		self.risk_engine = risk_engine
		self.orders = {}
		self.trades = []

	@property
	def engine_type(self) -> EngineType:
		"""获取引擎类型"""
		return EngineType.EXECUTION_ENGINE

	async def _on_initialize(self) -> None:
		"""引擎特定的初始化逻辑"""
		pass

	async def _on_start(self) -> None:
		"""引擎特定的启动逻辑"""
		# 连接券商
		await self.broker_adapter.connect()
		print("执行引擎启动成功")

	async def _on_stop(self) -> None:
		"""引擎特定的停止逻辑"""
		# 断开券商连接
		await self.broker_adapter.disconnect()
		print("执行引擎停止成功")

	async def _on_force_stop(self) -> None:
		"""引擎特定的强制停止逻辑"""
		await self.broker_adapter.disconnect()

	def _validate_config(self) -> None:
		"""验证配置"""
		pass

	async def _check_dependencies(self) -> None:
		"""检查依赖"""
		pass

	async def _start_background_tasks(self) -> None:
		"""启动后台任务"""
		pass

	async def _stop_background_tasks(self) -> None:
		"""停止后台任务"""
		pass

	async def _monitoring_loop(self) -> None:
		"""监控循环"""
		pass

	async def stop (self, force: bool = False, timeout: float = 30.0) -> bool:
		"""停止执行引擎"""
		return await super().stop(force=force, timeout=timeout)

	async def execute_order (self, order_data: Dict[str, Any]) -> Dict[str, Any]:
		"""执行订单"""
		try:
			# 发送订单到券商
			order = await self.broker_adapter.send_order(order_data)

			# 保存订单
			self.orders[order["order_id"]] = order

			# 如果订单成交，更新持仓
			if order["status"] == "filled":
				await self.position_engine.update_position()

			# 记录交易
			if "filled_quantity" in order and order["filled_quantity"] > 0:
				trade = {
					"trade_id": str(uuid.uuid4()),
					"order_id": order["order_id"],
					"ts_code": order["ts_code"],
					"direction": order["direction"],
					"price": order["filled_price"],
					"quantity": order["filled_quantity"],
					"trade_time": datetime.now().isoformat()
				}
				self.trades.append(trade)

			return order
		except Exception as e:
			print(f"执行订单失败: {str(e)}")
			return {
				"order_id": str(uuid.uuid4()),
				"status": "failed",
				"error": str(e)
			}

	async def cancel_order (self, order_id: str) -> bool:
		"""取消订单"""
		try:
			result = await self.broker_adapter.cancel_order(order_id)
			if result and order_id in self.orders:
				self.orders[order_id]["status"] = "cancelled"
			return result
		except Exception as e:
			print(f"取消订单失败: {str(e)}")
			return False

	async def get_order_status (self, order_id: str) -> Dict[str, Any]:
		"""获取订单状态"""
		try:
			status = await self.broker_adapter.get_order_status(order_id)
			if order_id in self.orders:
				self.orders[order_id].update(status)
			return status
		except Exception as e:
			print(f"获取订单状态失败: {str(e)}")
			return {}

	def get_order (self, order_id: str) -> Optional[Dict[str, Any]]:
		"""获取订单信息"""
		return self.orders.get(order_id)

	def get_orders (self, status: Optional[str] = None) -> List[Dict[str, Any]]:
		"""获取订单列表"""
		orders = list(self.orders.values())
		if status:
			orders = [order for order in orders if order.get("status") == status]
		return orders

	def get_trades (self) -> List[Dict[str, Any]]:
		"""获取交易记录"""
		return self.trades

	def get_trades_by_symbol (self, ts_code: str) -> List[Dict[str, Any]]:
		"""根据股票代码获取交易记录"""
		return [trade for trade in self.trades if trade.get("ts_code") == ts_code]

	async def execute_signal (self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
		"""执行信号"""
		# 检查信号是否符合风控规则
		is_valid, message = await self.risk_engine.check_signal(signal_data)
		if not is_valid:
			return {
				"success": False,
				"message": message
			}

		# 生成订单数据
		order_data = {
			"ts_code": signal_data.get("ts_code"),
			"direction": signal_data.get("direction"),
			"price": signal_data.get("price"),
			"quantity": signal_data.get("quantity"),
			"order_type": signal_data.get("order_type", "limit")
		}

		# 执行订单
		order = await self.execute_order(order_data)

		return {
			"success": order.get("status") == "filled",
			"order": order,
			"message": "信号执行完成"
		}