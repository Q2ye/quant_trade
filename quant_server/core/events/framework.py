"""
事件框架工具类
提供事件处理器、过滤器、转换器等工具类

设计原则：
1. 可组合：工具类可以组合使用
2. 可配置：支持配置参数
3. 可扩展：支持自定义实现
4. 类型安全：提供类型提示
"""

import inspect
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .base import BaseEvent
from .types import EventPriority

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseEvent)
E = TypeVar("E", bound=BaseEvent)


class EventHandler(ABC):
	"""
	事件处理器基类
	封装事件处理逻辑，支持同步和异步处理
	"""

	def __init__ (
			self,
			func: Callable,
			name: Optional[str] = None,
			priority: int = 0,
			handler_id: Optional[str] = None,
			enabled: bool = True,
			timeout: Optional[float] = None,
	):
		"""
		初始化事件处理器

		Args:
			func: 处理函数，可以接受事件对象或事件数据
			name: 处理器名称，用于日志和监控
			priority: 处理器优先级（在同类型处理器中）
			handler_id: 处理器ID，用于标识和取消注册
			enabled: 是否启用处理器
			timeout: 处理超时时间（秒），None表示不超时
		"""
		self.func = func
		self.name = name or func.__name__
		self.priority = priority
		self.handler_id = handler_id or f"{self.name}_{id(self)}"
		self.enabled = enabled
		self.timeout = timeout

		# 统计信息
		self._call_count = 0
		self._success_count = 0
		self._error_count = 0
		self._total_time = 0.0

		# 确定函数签名
		self._sig = inspect.signature(func)
		self._expects_event = self._check_expects_event()

	def _check_expects_event (self) -> bool:
		"""检查函数是否接受事件对象作为参数"""
		params = list(self._sig.parameters.values())
		if not params:
			return False

		first_param = params[0]
		# 检查参数类型注解
		if first_param.annotation != inspect.Parameter.empty:
			annotation_str = str(first_param.annotation)
			return "BaseEvent" in annotation_str or "Event" in annotation_str

		# 根据参数名猜测
		param_name = first_param.name.lower()
		return param_name in ["event", "evt", "e"]

	def execute (self, event: BaseEvent) -> Any:
		"""
		执行处理器（同步）

		Args:
			event: 事件对象

		Returns:
			处理结果

		Raises:
			Exception: 处理过程中发生异常
		"""
		if not self.enabled:
			logger.debug(f"处理器 {self.name} 被禁用，跳过")
			return None

		import time
		start_time = time.time()
		self._call_count += 1

		try:
			# 根据函数签名传递参数
			if self._expects_event:
				result = self.func(event)
			else:
				# 传递事件数据
				result = self.func(event.data)

			# 记录成功
			self._success_count += 1
			elapsed = time.time() - start_time
			self._total_time += elapsed

			logger.debug(f"处理器 {self.name} 执行成功，耗时: {elapsed:.3f}s")
			return result

		except Exception as e:
			# 记录失败
			self._error_count += 1
			elapsed = time.time() - start_time
			self._total_time += elapsed

			logger.error(f"处理器 {self.name} 执行失败: {e}", exc_info=True)
			raise

	async def execute_async (self, event: BaseEvent) -> Any:
		"""
		执行处理器（异步）

		Args:
			event: 事件对象

		Returns:
			处理结果

		Raises:
			Exception: 处理过程中发生异常
		"""
		if not self.enabled:
			logger.debug(f"处理器 {self.name} 被禁用，跳过")
			return None

		import time
		start_time = time.time()
		self._call_count += 1

		try:
			# 检查是否为协程函数
			if inspect.iscoroutinefunction(self.func):
				# 异步函数
				if self._expects_event:
					result = await self.func(event)
				else:
					result = await self.func(event.data)
			else:
				# 同步函数
				if self._expects_event:
					result = self.func(event)
				else:
					result = self.func(event.data)

			# 记录成功
			self._success_count += 1
			elapsed = time.time() - start_time
			self._total_time += elapsed

			logger.debug(f"处理器 {self.name} 执行成功，耗时: {elapsed:.3f}s")
			return result

		except Exception as e:
			# 记录失败
			self._error_count += 1
			elapsed = time.time() - start_time
			self._total_time += elapsed

			logger.error(f"处理器 {self.name} 执行失败: {e}", exc_info=True)
			raise

	def get_stats (self) -> Dict[str, Any]:
		"""获取处理器统计信息"""
		avg_time = self._total_time / self._call_count if self._call_count > 0 else 0
		success_rate = (self._success_count / self._call_count * 100) if self._call_count > 0 else 0

		return {
			"name": self.name,
			"handler_id": self.handler_id,
			"call_count": self._call_count,
			"success_count": self._success_count,
			"error_count": self._error_count,
			"success_rate": round(success_rate, 2),
			"total_time": round(self._total_time, 3),
			"avg_time": round(avg_time, 3),
			"enabled": self.enabled,
			"priority": self.priority,
		}

	def __call__ (self, event: BaseEvent) -> Any:
		"""使处理器可调用"""
		return self.execute(event)

	def __str__ (self) -> str:
		"""字符串表示"""
		return f"EventHandler(name={self.name}, id={self.handler_id}, priority={self.priority})"


class ConcreteEventHandler(EventHandler):
	"""
	具体的事件处理器实现
	用于直接实例化的事件处理器
	"""
	pass


class DecoratedEventHandler(EventHandler):
	"""
	装饰器创建的事件处理器
	用于将普通函数装饰为事件处理器
	"""

	@classmethod
	def create (cls, event_type: str, priority: int = 0, **kwargs):
		"""
		创建装饰器

		Args:
			event_type: 事件类型
			priority: 处理器优先级
			**kwargs: 其他EventHandler参数

		Returns:
			装饰器函数
		"""

		def decorator (func):
			# 创建处理器
			handler = cls(func, priority=priority, **kwargs)
			# 存储处理器信息，用于后续注册
			if not hasattr(func, 'event_handlers'):
				func.event_handlers = []
			func.event_handlers.append((event_type, handler))

			@wraps(func)
			def wrapper (*args, **wrapper_kwargs):
				return func(*args, **wrapper_kwargs)

			return wrapper

		return decorator


class EventFilter(ABC):
	"""
	事件过滤器基类
	用于过滤不需要处理的事件
	"""

	def __init__ (self, name: Optional[str] = None):
		self.name = name or self.__class__.__name__

	@abstractmethod
	def filter (self, event: BaseEvent) -> bool:
		"""
		过滤事件

		Args:
			event: 事件对象

		Returns:
			bool: True表示通过过滤，False表示被过滤
		"""
		pass


class EventTypeFilter(EventFilter):
	"""事件类型过滤器"""

	def __init__ (self, allowed_types: List[str], name: str = "EventTypeFilter"):
		"""
		初始化类型过滤器

		Args:
			allowed_types: 允许的事件类型列表
			name: 过滤器名称
		"""
		super().__init__(name)
		self.allowed_types = set(allowed_types)

	def filter (self, event: BaseEvent) -> bool:
		"""检查事件类型是否在允许列表中"""
		return event.event_type in self.allowed_types

	def add_type (self, event_type: str) -> None:
		"""添加允许的事件类型"""
		self.allowed_types.add(event_type)

	def remove_type (self, event_type: str) -> None:
		"""移除允许的事件类型"""
		self.allowed_types.discard(event_type)


class EventPriorityFilter(EventFilter):
	"""事件优先级过滤器"""

	def __init__ (
			self,
			min_priority: int = EventPriority.LOW,
			max_priority: int = EventPriority.CRITICAL,
			name: str = "EventPriorityFilter"
	):
		"""
		初始化优先级过滤器

		Args:
			min_priority: 最低优先级（包含）
			max_priority: 最高优先级（包含）
			name: 过滤器名称
		"""
		super().__init__(name)
		self.min_priority = min_priority
		self.max_priority = max_priority

	def filter (self, event: BaseEvent) -> bool:
		"""检查事件优先级是否在范围内"""
		return self.min_priority <= event.metadata.priority <= self.max_priority


class EventSourceFilter(EventFilter):
	"""事件源过滤器"""

	def __init__ (self, allowed_sources: List[str], name: str = "EventSourceFilter"):
		"""
		初始化源过滤器

		Args:
			allowed_sources: 允许的事件源列表
			name: 过滤器名称
		"""
		super().__init__(name)
		self.allowed_sources = set(allowed_sources)

	def filter (self, event: BaseEvent) -> bool:
		"""检查事件源是否在允许列表中"""
		return event.metadata.source in self.allowed_sources


class CompositeFilter(EventFilter):
	"""组合过滤器"""

	def __init__ (self, filters: List[EventFilter], name: str = "CompositeFilter"):
		"""
		初始化组合过滤器

		Args:
			filters: 过滤器列表
			name: 过滤器名称
		"""
		super().__init__(name)
		self.filters = filters

	def filter (self, event: BaseEvent) -> bool:
		"""所有过滤器都必须通过"""
		for event_filter in self.filters:
			if not event_filter.filter(event):
				return False
		return True


class EventTransformer(ABC):
	"""
	事件转换器基类
	用于转换事件格式或内容
	"""

	def __init__ (self, name: Optional[str] = None):
		self.name = name or self.__class__.__name__

	@abstractmethod
	def transform (self, event: BaseEvent) -> BaseEvent:
		"""
		转换事件

		Args:
			event: 原始事件

		Returns:
			BaseEvent: 转换后的事件
		"""
		pass


class EventEnricher(EventTransformer):
	"""事件丰富器，添加额外信息"""

	def __init__ (self, enrich_data: Dict[str, Any], name: str = "EventEnricher"):
		"""
		初始化事件丰富器

		Args:
			enrich_data: 要添加的数据
			name: 转换器名称
		"""
		super().__init__(name)
		self.enrich_data = enrich_data

	def transform (self, event: BaseEvent) -> BaseEvent:
		"""添加额外数据到事件"""
		event.data.update(self.enrich_data)
		return event


class EventLogger(EventHandler):
	"""事件日志处理器"""

	def __init__ (self, level: int = logging.INFO, name: str = "EventLogger"):
		"""
		初始化事件日志器

		Args:
			level: 日志级别
			name: 处理器名称
		"""
		super().__init__(self._log_event, name=name)
		self.level = level

	def _log_event (self, event: BaseEvent) -> None:
		"""记录事件"""
		logger.log(
			self.level,
			f"事件: {event.event_type} | 源: {event.metadata.source} | "
			f"ID: {event.event_id} | 优先级: {event.metadata.priority}"
		)


class EventMonitor(EventHandler):
	"""事件监控处理器"""

	def __init__ (self, name: str = "EventMonitor"):
		"""
		初始化事件监控器

		Args:
			name: 处理器名称
		"""
		super().__init__(self._monitor_event, name=name)
		self._event_counts = {}
		self._last_reset = None

	def _monitor_event (self, event: BaseEvent) -> None:
		"""监控事件统计"""
		event_type = event.event_type
		self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1

	def get_stats (self, reset: bool = False) -> Dict[str, Any]:
		"""获取监控统计"""
		stats = {
			"event_counts": self._event_counts.copy(),
			"total_events": sum(self._event_counts.values()),
			"unique_event_types": len(self._event_counts),
			"last_reset": self._last_reset,
		}

		if reset:
			self._event_counts.clear()
			self._last_reset = datetime.now()

		return stats


# 工具函数
def event_handler (
		event_type: str,
		priority: int = 0,
		name: Optional[str] = None,
		enabled: bool = True,
		timeout: Optional[float] = None,
):
	"""
	事件处理器装饰器

	Args:
		event_type: 事件类型
		priority: 处理器优先级
		name: 处理器名称
		enabled: 是否启用
		timeout: 处理超时

	Returns:
		装饰器函数
	"""

	def decorator (func):
		handler = ConcreteEventHandler(
		func=func,
		name=name,
		priority=priority,
		enabled=enabled,
		timeout=timeout,
	)

		# 存储处理器信息
		if not hasattr(func, 'event_handlers'):
			func.event_handlers = []
		func.event_handlers.append((event_type, handler))

		@wraps(func)
		def wrapper (*args, **wrapper_kwargs):
			return func(*args, **wrapper_kwargs)

		return wrapper

	return decorator


def async_event_handler (
		event_type: str,
		priority: int = 0,
		name: Optional[str] = None,
		enabled: bool = True,
		timeout: Optional[float] = None,
):
	"""
	异步事件处理器装饰器

	Args:
		event_type: 事件类型
		priority: 处理器优先级
		name: 处理器名称
		enabled: 是否启用
		timeout: 处理超时

	Returns:
		装饰器函数
	"""

	def decorator (func):
		if not inspect.iscoroutinefunction(func):
			raise TypeError(f"函数 {func.__name__} 必须是异步函数")

		handler = ConcreteEventHandler(
		func=func,
		name=name,
		priority=priority,
		enabled=enabled,
		timeout=timeout,
	)

		# 存储处理器信息
		if not hasattr(func, 'event_handlers'):
			func.event_handlers = []
		func.event_handlers.append((event_type, handler))

		@wraps(func)
		async def wrapper (*args, **wrapper_kwargs):
			return await func(*args, **wrapper_kwargs)

		return wrapper

	return decorator