# quant_server/api/dependencies/event_engine.py
"""
事件引擎依赖模块

提供FastAPI依赖注入的事件引擎功能，基于核心层的事件框架。
支持事件发布、订阅、异步处理、事件总线管理等。

Author: 量化交易系统团队
Version: 1.0.0
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, Callable, Coroutine
from contextlib import asynccontextmanager
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from quant_server.core.engines.types.enums import ComponentStatus

from fastapi import Depends

from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.engines.system.engine_registry import EngineRegistry
from quant_server.core.engines.types import Event
from quant_server.core.exceptions.event_exceptions import EventException

logger = logging.getLogger(__name__)


class EventPriority(Enum):
	"""事件优先级"""
	LOW = 1
	NORMAL = 2
	HIGH = 3
	CRITICAL = 4


@dataclass
class EventContext:
	"""事件上下文信息"""
	event_id: str
	event_type: str
	source: str
	timestamp: datetime
	priority: EventPriority
	metadata: Dict[str, Any]


class EventEngineDependencies:
	"""事件引擎依赖管理类"""

	def __init__ (self):
		"""初始化事件引擎依赖"""
		self._event_engine: Optional[EventEngine] = None
		self._message_bus = None
		self._engine_registry: Optional[EngineRegistry] = None
		self._is_initialized = False
		self._event_handlers: Dict[str, List[Callable]] = {}
		logger.info("事件引擎依赖初始化完成")

	async def initialize (self) -> bool:
		"""
		初始化事件引擎依赖

		Returns:
			bool: 初始化是否成功
		"""
		try:
			# 获取事件引擎实例（通过引擎注册表）
			self._engine_registry = EngineRegistry()
			engine_record = self._engine_registry.get_engine_record("event_engine")

			if not engine_record or not engine_record.engine:
				logger.warning("事件引擎未在注册表中找到，尝试创建新实例")
				# 创建默认配置
				from quant_server.core.engines.types.entities import EngineConfig
				config = EngineConfig(
					name="default_event_engine",
					engine_type="event",
					config={
						"max_workers": 10,
						"queue_size": 10000
					}
				)
				self._event_engine = EventEngine(config)
			else:
				self._event_engine = engine_record.engine

			# 初始化消息总线（可选）
			try:
				from quant_server.shared.messaging.message_bus import MessageBus
				self._message_bus = MessageBus()
				await self._message_bus.initialize()
				logger.info("消息总线初始化成功")
			except Exception as e:
				logger.warning(f"消息总线初始化失败，跳过: {str(e)}")
				self._message_bus = None

			# 标记为已初始化
			self._is_initialized = True
			logger.info("事件引擎依赖初始化成功")

			# 注册系统事件处理器（必须在初始化完成后）
			try:
				await self._register_system_handlers()
			except Exception as e:
				logger.error(f"系统处理器注册失败: {str(e)}")

			# 发布系统启动事件
			await self.publish_system_event(
				event_type="SYSTEM_STARTED",
				data={"module": "event_engine_deps"},
				priority=EventPriority.NORMAL
			)

			return True

		except Exception as e:
			logger.error(f"事件引擎依赖初始化失败: {str(e)}", exc_info=True)
			return False

	@property
	def event_engine (self) -> EventEngine:
		"""
		获取事件引擎实例

		Returns:
			EventEngine: 事件引擎实例

		Raises:
			EventException: 事件引擎未初始化
		"""
		if not self._event_engine:
			raise EventException("事件引擎实例不存在")
		if not self._is_initialized:
			raise EventException("事件引擎未初始化完成")
		return self._event_engine

	async def get_event_engine (self) -> EventEngine:
		"""
		获取事件引擎依赖

		Returns:
			EventEngine: 事件引擎实例
		"""
		if not self._is_initialized:
			# 尝试初始化
			success = await self.initialize()
			if not success:
				raise EventException("事件引擎初始化失败")

		return self.event_engine

	async def publish_event (
			self,
			event_type: str,
			data: Dict[str, Any],
			priority: EventPriority = EventPriority.NORMAL,
			source: str = "api",
			metadata: Optional[Dict[str, Any]] = None
	) -> str:
		"""
		发布事件

		Args:
			event_type: 事件类型
			data: 事件数据
			priority: 事件优先级
			source: 事件源
			metadata: 事件元数据

		Returns:
			str: 事件ID
		"""
		try:
			event = Event(
				event_id=str(uuid.uuid4()),
				event_type=event_type,
				source=source,
				data=data,
				timestamp=datetime.utcnow(),
				metadata=metadata or {}
			)

			# 设置优先级
			event.metadata["priority"] = priority.value

            # 确保事件引擎已启动
			if not self._event_engine or self._event_engine.record.status != ComponentStatus.RUNNING:
				await self._event_engine.start()

			event_id = await self.event_engine.put(event)

			logger.debug(
				f"事件发布成功: {event_type} (ID: {event_id}, "
				f"优先级: {priority.name}, 源: {source})"
			)

			return event_id

		except Exception as e:
			logger.error(f"事件发布失败: {event_type}, 错误: {str(e)}")
			raise EventException(f"事件发布失败: {str(e)}")

	async def publish_system_event (
			self,
			event_type: str,
			data: Dict[str, Any],
			priority: EventPriority = EventPriority.NORMAL
	) -> str:
		"""
		发布系统事件

		Args:
			event_type: 事件类型
			data: 事件数据
			priority: 事件优先级

		Returns:
			str: 事件ID
		"""
		return await self.publish_event(
			event_type=f"SYSTEM_{event_type}",
			data=data,
			priority=priority,
			source="system",
			metadata={"system_event": True}
		)

	async def subscribe (
			self,
			event_type: str,
			handler: Callable[[Event], Coroutine[Any, Any, None]],
			filter_fn: Optional[Callable[[Event], bool]] = None
	) -> str:
		"""
		订阅事件

		Args:
			event_type: 事件类型
			handler: 事件处理函数
			filter_fn: 事件过滤函数

		Returns:
			str: 订阅ID
		"""
		subscription_id = await self.event_engine.subscribe(
			event_type=event_type,
			handler=handler,
			filter_fn=filter_fn
		)

		# 记录订阅
		if event_type not in self._event_handlers:
			self._event_handlers[event_type] = []
		self._event_handlers[event_type].append(handler)

		logger.debug(f"事件订阅成功: {event_type} (订阅ID: {subscription_id})")

		return subscription_id

	async def unsubscribe (self, subscription_id: str) -> bool:
		"""
		取消订阅

		Args:
			subscription_id: 订阅ID

		Returns:
			bool: 是否成功取消
		"""
		success = await self.event_engine.unsubscribe(subscription_id)

		if success:
			logger.debug(f"事件取消订阅成功: {subscription_id}")
		else:
			logger.warning(f"事件取消订阅失败: {subscription_id}")

		return success

	async def wait_for_event (
			self,
			event_type: str,
			timeout: float = 30.0,
			filter_fn: Optional[Callable[[Event], bool]] = None
	) -> Optional[Event]:
		"""
		等待特定事件

		Args:
			event_type: 事件类型
			timeout: 超时时间（秒）
			filter_fn: 事件过滤函数

		Returns:
			Optional[Event]: 接收到的事件，超时返回None
		"""
		try:
			event = await self.event_engine.wait_for_event(
				event_type=event_type,
				timeout=timeout,
				filter_fn=filter_fn
			)

			if event:
				logger.debug(f"成功等待到事件: {event_type}")
			else:
				logger.debug(f"等待事件超时: {event_type}")

			return event

		except asyncio.TimeoutError:
			logger.warning(f"等待事件超时: {event_type}")
			return None
		except Exception as e:
			logger.error(f"等待事件失败: {event_type}, 错误: {str(e)}")
			return None

	async def get_event_stats (self) -> Dict[str, Any]:
		"""
		获取事件引擎统计信息

		Returns:
			Dict[str, Any]: 统计信息
		"""
		try:
			stats = await self.event_engine.get_stats()

			# 添加依赖层的统计
			stats["dependencies"] = {
				"initialized": self._is_initialized,
				"event_handlers": {
					event_type: len(handlers)
					for event_type, handlers in self._event_handlers.items()
				},
				"message_bus_connected": self._message_bus.initialized
				if self._message_bus else False
			}

			return stats

		except Exception as e:
			logger.error(f"获取事件统计失败: {str(e)}")
			return {"error": str(e)}

	async def _register_system_handlers (self):
		"""注册系统事件处理器"""
		# 注册事件引擎错误处理器
		await self.subscribe(
			event_type="EVENT_ENGINE_ERROR",
			handler=self._handle_event_engine_error,
			filter_fn=lambda e: e.data.get("severity") == "error"
		)

		# 注册系统警告处理器
		await self.subscribe(
			event_type="SYSTEM_WARNING",
			handler=self._handle_system_warning
		)

		logger.debug("系统事件处理器注册完成")

	async def _handle_event_engine_error (self, event: Event):
		"""处理事件引擎错误"""
		error_data = event.data
		logger.error(
			f"事件引擎错误: {error_data.get('message')} "
			f"(源: {error_data.get('source')})"
		)

		# 可以在这里添加错误上报逻辑
		if self._message_bus:
			await self._message_bus.publish(
				topic="system.errors",
				message={
					"type": "event_engine_error",
					"data": error_data,
					"timestamp": datetime.utcnow().isoformat()
				}
			)

	async def _handle_system_warning (self, event: Event):
		"""处理系统警告"""
		warning_data = event.data
		logger.warning(
			f"系统警告: {warning_data.get('message')} "
			f"(模块: {warning_data.get('module')})"
		)

	async def close (self):
		"""关闭事件引擎依赖"""
		try:
			# 取消所有订阅
			for event_type, handlers in list(self._event_handlers.items()):
				for handler in handlers:
					# 这里需要实现根据handler找到subscription_id的逻辑
					# 简化处理：直接清空
					pass

			self._event_handlers.clear()

			# 关闭消息总线
			if self._message_bus:
				await self._message_bus.close()

			self._is_initialized = False
			logger.info("事件引擎依赖已关闭")

		except Exception as e:
			logger.error(f"关闭事件引擎依赖失败: {str(e)}")


# 创建全局事件引擎依赖实例
_event_engine_deps = EventEngineDependencies()

# 导出依赖函数
get_event_engine = _event_engine_deps.get_event_engine
publish_event = _event_engine_deps.publish_event
publish_system_event = _event_engine_deps.publish_system_event
subscribe = _event_engine_deps.subscribe
unsubscribe = _event_engine_deps.unsubscribe
wait_for_event = _event_engine_deps.wait_for_event
get_event_stats = _event_engine_deps.get_event_stats

# 导出类型注解
EventEngineDep = Depends(get_event_engine)

# 导出事件优先级枚举
EventPriority = EventPriority


async def initialize_event_engine () -> bool:
	"""
	初始化事件引擎依赖（应用启动时调用）

	Returns:
		bool: 初始化是否成功
	"""
	return await _event_engine_deps.initialize()


async def close_event_engine ():
	"""关闭事件引擎依赖（应用关闭时调用）"""
	await _event_engine_deps.close()


@asynccontextmanager
async def event_context (
		event_type: str,
		source: str = "api",
		metadata: Optional[Dict[str, Any]] = None
):
	"""
	事件上下文管理器

	自动记录事件开始和结束

	Args:
		event_type: 事件类型
		source: 事件源
		metadata: 事件元数据

	Yields:
		EventContext: 事件上下文
	"""
	event_context = EventContext(
		event_id=f"ctx_{datetime.utcnow().timestamp()}",
		event_type=event_type,
		source=source,
		timestamp=datetime.utcnow(),
		priority=EventPriority.NORMAL,
		metadata=metadata or {}
	)

	# 发布开始事件
	start_event_id = await publish_event(
		event_type=f"{event_type}_STARTED",
		data={"context": event_context.__dict__},
		source=source,
		metadata={"context_id": event_context.event_id}
	)

	try:
		yield event_context

		# 发布成功事件
		await publish_event(
			event_type=f"{event_type}_COMPLETED",
			data={
				"context": event_context.__dict__,
				"status": "success"
			},
			source=source,
			metadata={
				"context_id": event_context.event_id,
				"start_event_id": start_event_id
			}
		)

	except Exception as e:
		# 发布失败事件
		await publish_event(
			event_type=f"{event_type}_FAILED",
			data={
				"context": event_context.__dict__,
				"status": "error",
				"error": str(e)
			},
			source=source,
			metadata={
				"context_id": event_context.event_id,
				"start_event_id": start_event_id
			}
		)
		raise