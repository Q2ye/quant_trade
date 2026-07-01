# execution_engine.py   # 订单执行引擎

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from core.engines import EngineConfigEntity
from core.engines.types.enums import EngineType
from core.engines.base.engine_base import EngineBase
from core.engines.system import EventEngine
from modules.trade.adapters.broker_adapter import BrokerAdapter
from modules.trade.engines.position_engine import PositionEngine
from modules.trade.engines.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class ExecutionEngine(EngineBase):
	"""订单执行引擎"""

	def __init__ (
			self,
			config: Dict[str, Any],
			broker_adapter: BrokerAdapter,
			position_engine: PositionEngine,
			risk_engine: RiskEngine,
			event_engine: Optional[EventEngine] = None,
			trade_manager=None,  # v2.4: TradeManager 引用
			session_factory=None  # v2.4: DB session factory，用于订单持久化
	):
		config_obj = EngineConfigEntity(
			name=config.get("name", "execution_engine"),
			engine_type="execution_engine",
			dependencies=config.get("dependencies", []),
			max_retries=config.get("max_retries", 3),
			retry_delay=config.get("retry_delay", 1.0),
			config=config
		)

		super().__init__(config=config_obj, event_engine=event_engine)

		# v2.4: BrokerAdapter 回退保护 — 防止抽象类实例化崩溃
		if broker_adapter is None:
			from modules.trade.adapters.sim_adapter import SimBrokerAdapter
			logger.warning("ExecutionEngine: 未注入具体 BrokerAdapter，回退为 SimBrokerAdapter")
			self.broker_adapter = SimBrokerAdapter(config={
				"initial_capital": config.get("initial_capital", 1000000),
				"simulated": True
			})
		else:
			self.broker_adapter = broker_adapter

		self.position_engine = position_engine
		self.risk_engine = risk_engine
		self.trade_manager = trade_manager  # v2.4: 用于 SIMULATED_TRADING 检查
		self.session_factory = session_factory  # v2.4: 用于订单 DB 持久化
		self.orders = {}
		self.trades = []

	@property
	def engine_type(self) -> EngineType:
		"""获取引擎类型"""
		return EngineType.EXECUTION_ENGINE

	async def _on_initialize(self) -> None:
		"""引擎特定的初始化逻辑"""
		logger.info("ExecutionEngine 初始化完成")

	async def _on_start(self) -> None:
		"""引擎特定的启动逻辑 — 连接券商适配器 + v2.3 恢复在途订单"""
		await self.broker_adapter.connect()
		await self._recover_pending_orders()
		logger.info("ExecutionEngine 启动成功，券商已连接")

	async def _recover_pending_orders(self) -> None:
		"""v2.4: 重启后从 DB + 券商适配器恢复在途订单

		优先 DB（数据最完整），券商适配器作为补充。
		"""
		recovered = 0
		# 第一源：DB
		if self.session_factory:
			try:
				from shared.database.repositories.trading.order import OrderRepository
				async with self.session_factory() as session:
					repo = OrderRepository(session)
					pending = await repo.get_by_status("submitted")
					for order in pending:
						od = order.to_dict() if hasattr(order, 'to_dict') else order
						oid = od.get("order_id", "")
						if oid:
							self.orders[oid] = od
							recovered += 1
				if recovered:
					logger.info(f"ExecutionEngine 从 DB 恢复 {recovered} 个在途订单")
			except Exception as e:
				logger.warning(f"ExecutionEngine DB 恢复失败（不阻断启动）: {e}")

		# 第二源：券商适配器
		try:
			if hasattr(self.broker_adapter, "get_pending_orders"):
				pending = await self.broker_adapter.get_pending_orders()
				if pending:
					for order in pending:
						oid = order.get("order_id", "")
						if oid and oid not in self.orders:
							self.orders[oid] = order
							recovered += 1
					logger.info(f"ExecutionEngine 从券商恢复 {len(pending)} 个在途订单")
		except Exception as e:
			logger.warning(f"ExecutionEngine 券商恢复失败（不阻断启动）: {e}")

	async def _on_stop(self) -> None:
		"""引擎特定的停止逻辑 — 断开券商连接"""
		await self.broker_adapter.disconnect()
		logger.info("ExecutionEngine 已停止，券商已断开")

	async def _on_force_stop(self) -> None:
		"""引擎特定的强制停止逻辑"""
		await self.broker_adapter.disconnect()
		logger.warning("ExecutionEngine 强制停止")

	def _validate_config(self) -> None:
		"""验证必要配置项"""
		if "name" not in self.config.config:
			logger.warning("ExecutionEngine 缺少配置项: name")

	async def _check_dependencies(self) -> None:
		"""检查依赖"""
		if self.broker_adapter is None:
			raise RuntimeError("ExecutionEngine 依赖 BrokerAdapter，但未注入")
		if self.position_engine is None:
			raise RuntimeError("ExecutionEngine 依赖 PositionEngine，但未注入")
		if self.risk_engine is None:
			raise RuntimeError("ExecutionEngine 依赖 RiskEngine，但未注入")

	async def _start_background_tasks(self) -> None:
		"""启动后台任务（订单状态轮询、超时检测）"""
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
		"""执行订单 — v2.4: 强制检查 SIMULATED_TRADING 安全开关"""
		try:
			# v2.4: 安全红线 — 模拟模式下绝不向券商发送真实订单
			is_simulated = True  # 默认安全
			if self.trade_manager and hasattr(self.trade_manager, 'is_simulated_trading'):
				is_simulated = self.trade_manager.is_simulated_trading()

			if is_simulated:
				# 模拟直接成交，不经过券商
				oid = order_data.get("order_id", str(uuid.uuid4()))
				order_data["order_id"] = oid
				order_data["status"] = "filled"
				order_data["filled_volume"] = order_data.get("volume", 0)
				order_data["filled_price"] = order_data.get("price", 0)
				order_data["filled_amount"] = order_data.get("filled_volume", 0) * order_data.get("filled_price", 0)
				self.orders[oid] = order_data
				logger.info(f"[SIM] 模拟交易成交: order_id={oid}, ts_code={order_data.get('ts_code')}, "
				            f"direction={order_data.get('direction')}, volume={order_data.get('volume')}")

				# 模拟模式也更新持仓和触发结算
				if order_data["status"] == "filled":
					await self.position_engine.update_position()
					await self._trigger_settlement_after_trade(order_data)

				if "filled_quantity" in order_data and order_data["filled_quantity"] > 0:
					trade = {
						"trade_id": str(uuid.uuid4()),
						"order_id": order_data["order_id"],
						"ts_code": order_data["ts_code"],
						"direction": order_data["direction"],
						"price": order_data["filled_price"],
						"quantity": order_data["filled_quantity"],
						"trade_time": datetime.now().isoformat()
					}
					self.trades.append(trade)

				return order_data

			# 真实交易路径 — 发送订单到券商
			logger.warning(f"[LIVE] 真实交易模式：发送订单至券商: order_id={order_data.get('order_id')}")
			order = await self.broker_adapter.send_order(order_data)

			# 保存订单
			self.orders[order["order_id"]] = order

			# 如果订单成交，更新持仓 + 触发结算
			if order["status"] == "filled":
				await self.position_engine.update_position()
				await self._trigger_settlement_after_trade(order)

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

			# v2.4: DB 持久化（非阻塞 — 失败不影响交易执行）
			if self.session_factory:
				try:
					async with self.session_factory() as session:
						from shared.database.repositories.trading.order import OrderRepository
						order_repo = OrderRepository(session)
						await order_repo.create(order)
						if trade:
							await order_repo.session.commit()
					logger.debug(f"订单已持久化到 DB: {order.get('order_id')}")
				except Exception as pe:
					logger.warning(f"订单 DB 持久化失败（不影响交易）: {pe}")

			return order
		except Exception as e:
			logger.exception(f"执行订单失败: order_id={order_data.get('order_id')}, ts_code={order_data.get('ts_code')}")
			# 发布订单失败事件
			if self.event_engine:
				try:
					from modules.trade.events.order_events import OrderFailedEvent
					await self.event_engine.put(OrderFailedEvent(
						order_id=order_data.get("order_id", "unknown"),
						reason=str(e),
						timestamp=datetime.now()
					))
				except Exception:
					pass
			return {
				"order_id": order_data.get("order_id", str(uuid.uuid4())),
				"status": "failed",
				"error": str(e)
			}

	async def _trigger_settlement_after_trade(self, order: Dict[str, Any]) -> None:
		"""成交后发布结算事件，驱动日终快照写入"""
		try:
			if self.event_engine:
				from datetime import date as _date
				from modules.account.events.settlement_events import AccountSettlementStartedEvent

				await self.event_engine.put(AccountSettlementStartedEvent(
					settlement_date=_date.today(),
					settlement_type="daily",
					account_ids=[order.get("account_id")] if order.get("account_id") else [],
				))
				logger.debug(f"已发布成交后结算事件: order={order.get('order_id')}")
		except Exception:
			logger.warning("发布成交后结算事件失败（非致命）", exc_info=True)

	async def cancel_order (self, order_id: str) -> bool:
		"""取消订单"""
		try:
			result = await self.broker_adapter.cancel_order(order_id)
			if result and order_id in self.orders:
				self.orders[order_id]["status"] = "cancelled"
			return result
		except Exception as e:
			logger.exception(f"取消订单失败: order_id={order_id}")
			return False

	async def get_order_status (self, order_id: str) -> Dict[str, Any]:
		"""获取订单状态"""
		try:
			status = await self.broker_adapter.get_order_status(order_id)
			if order_id in self.orders:
				self.orders[order_id].update(status)
			return status
		except Exception as e:
			logger.exception(f"获取订单状态失败: order_id={order_id}")
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