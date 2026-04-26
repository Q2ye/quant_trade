"""
事件引擎实现
基于发布-订阅模式的事件分发系统

设计特点：
1. 异步处理：支持同步和异步事件处理
2. 优先级队列：支持按优先级处理事件
3. 线程安全：支持多线程环境
4. 可扩展：支持过滤器、转换器等扩展
5. 监控支持：提供事件处理统计信息
"""

import asyncio
import logging
import queue
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import (
	Any, Callable, Dict, List, Optional, Set, Union,
	TypeVar
)

from .base import BaseEvent
from .framework import EventFilter, EventTransformer, EventHandler, ConcreteEventHandler
from .types import EventPriority

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseEvent)


class EventHandlerRegistry:
	"""
	事件处理器注册表
	管理事件类型到处理器的映射
	"""

	def __init__ (self):
		self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
		self._wildcard_handlers: List[EventHandler] = []
		self._handler_count = 0

	def get_handler_count (self) -> int:
		"""获取注册的处理器数量

		Returns:
			int: 处理器数量
		"""
		return self._handler_count

	def register (
			self,
			event_type: str,
			handler: Union[Callable, EventHandler],
			priority: int = 0
	) -> str:
		"""
		注册事件处理器

		Args:
			event_type: 事件类型，支持通配符(*)
			handler: 处理器函数或EventHandler实例
			priority: 处理器优先级，数值越大优先级越高

		Returns:
			处理器ID，用于取消注册
		"""
		handler_id = f"handler_{self._handler_count}"
		self._handler_count += 1

		if isinstance(handler, Callable) and not isinstance(handler, EventHandler):
			handler = ConcreteEventHandler(handler, priority=priority, handler_id=handler_id)
		elif isinstance(handler, EventHandler):
			handler.handler_id = handler_id
			handler.priority = priority

		if event_type == "*":
			self._wildcard_handlers.append(handler)
		else:
			self._handlers[event_type].append(handler)
			# 按优先级排序
			self._handlers[event_type].sort(key=lambda h: h.priority, reverse=True)

		logger.debug(f"注册处理器: {handler_id} -> {event_type}")
		return handler_id

	def unregister (self, handler_id: str) -> bool:
		"""取消注册处理器"""
		# 从特定事件类型中移除
		for event_type, handlers in self._handlers.items():
			for i, handler in enumerate(handlers):
				if handler.handler_id == handler_id:
					handlers.pop(i)
					logger.debug(f"取消注册处理器: {handler_id} from {event_type}")
					return True

		# 从通配符处理器中移除
		for i, handler in enumerate(self._wildcard_handlers):
			if handler.handler_id == handler_id:
				self._wildcard_handlers.pop(i)
				logger.debug(f"取消注册通配符处理器: {handler_id}")
				return True

		return False

	def get_handlers (self, event_type: str) -> List[EventHandler]:
		"""获取指定事件类型的处理器"""
		specific_handlers = self._handlers.get(event_type, [])
		return specific_handlers + self._wildcard_handlers

	def clear (self) -> None:
		"""清空所有处理器"""
		self._handlers.clear()
		self._wildcard_handlers.clear()
		logger.debug("清空所有事件处理器")


class EventQueue:
	"""
	事件队列
	支持优先级的事件队列实现
	"""

	def __init__ (self, maxsize: int = 10000):
		self._queues = {
			EventPriority.CRITICAL: queue.PriorityQueue(maxsize),
			EventPriority.HIGH: queue.PriorityQueue(maxsize),
			EventPriority.NORMAL: queue.PriorityQueue(maxsize),
			EventPriority.LOW: queue.PriorityQueue(maxsize),
		}
		self._size = 0
		self._lock = threading.RLock()

	def put (self, event: BaseEvent, priority: Optional[int] = None) -> None:
		"""添加事件到队列"""
		if priority is None:
			priority = event.metadata.priority

		# 确保优先级在有效范围内
		priority = max(EventPriority.LOW, min(priority, EventPriority.CRITICAL))

		# 使用时间戳作为第二优先级，确保FIFO
		timestamp = time.time()

		with self._lock:
			self._queues[priority].put((priority, timestamp, event))
			self._size += 1

	def get (self, block: bool = True, timeout: Optional[float] = None) -> BaseEvent:
		"""从队列获取事件（按优先级顺序）"""
		with self._lock:
			for priority in [EventPriority.CRITICAL, EventPriority.HIGH,
			                 EventPriority.NORMAL, EventPriority.LOW]:
				try:
					_, _, event = self._queues[priority].get(block=False)
					self._size -= 1
					return event
				except queue.Empty:
					continue

		# 所有队列都为空，如果需要阻塞则等待
		if block:
			# 使用条件变量等待事件
			return self._get_with_timeout(timeout)
		else:
			raise queue.Empty()

	def _get_with_timeout (self, timeout: Optional[float]) -> BaseEvent:
		"""带超时的获取"""
		start_time = time.time()
		while True:
			try:
				return self.get(block=False)
			except queue.Empty:
				pass

			# 检查超时
			if timeout is not None and time.time() - start_time > timeout:
				raise queue.Empty()

			# 短暂休眠避免CPU忙等
			time.sleep(0.01)

	def qsize (self) -> int:
		"""队列大小"""
		return self._size

	def empty (self) -> bool:
		"""队列是否为空"""
		return self._size == 0

	def clear (self) -> None:
		"""清空队列"""
		with self._lock:
			for q in self._queues.values():
				while not q.empty():
					try:
						q.get_nowait()
					except queue.Empty:
						pass
			self._size = 0


class EventEngine:
	"""
	同步事件引擎
	基于线程的事件引擎，支持同步事件处理
	"""

	def __init__ (
			self,
			name: str = "EventEngine",
			max_workers: int = 10,
			max_queue_size: int = 10000,
			auto_start: bool = True
	):
		self.name = name
		self.max_workers = max_workers
		self.max_queue_size = max_queue_size

		# 核心组件
		self._queue = EventQueue(maxsize=max_queue_size)
		self._registry = EventHandlerRegistry()
		self._filters: List[EventFilter] = []
		self._transformers: List[EventTransformer] = []

		# 运行时状态
		self._running = False
		self._thread: Optional[threading.Thread] = None
		self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"{name}_Worker")

		# 统计信息
		self._stats: Dict[str, Union[int, Optional[datetime]]] = {
			"events_processed": 0,
			"events_failed": 0,
			"events_dropped": 0,
			"handlers_executed": 0,
			"start_time": None,
			"last_event_time": None,
		}

		logger.info(f"初始化事件引擎: {name}")

		if auto_start:
			self.start()

	def start (self) -> None:
		"""启动事件引擎"""
		if self._running:
			logger.warning(f"事件引擎 {self.name} 已经在运行")
			return

		self._running = True
		self._thread = threading.Thread(
			target=self._run_loop,
			name=f"{self.name}_Main",
			daemon=True
		)
		self._thread.start()
		self._stats["start_time"] = datetime.now()

		logger.info(f"启动事件引擎: {self.name}")

	def stop (self, timeout: float = 5.0) -> None:
		"""停止事件引擎"""
		if not self._running:
			return

		logger.info(f"停止事件引擎: {self.name}")
		self._running = False

		# 等待处理线程结束
		if self._thread and self._thread.is_alive():
			self._thread.join(timeout=timeout)
			if self._thread.is_alive():
				logger.warning(f"事件引擎 {self.name} 停止超时")

		# 关闭线程池
		self._executor.shutdown(wait=True)

		logger.info(f"事件引擎 {self.name} 已停止")

	def _run_loop (self) -> None:
		"""事件处理主循环"""
		logger.debug(f"事件引擎 {self.name} 主循环开始")

		while self._running:
			try:
				# 从队列获取事件
				event = self._queue.get(block=True, timeout=0.1)

				# 处理事件
				self._process_event(event)

			except queue.Empty:
				# 队列为空，继续循环
				continue
			except Exception as e:
				logger.error(f"事件引擎主循环异常: {e}", exc_info=True)
				# 避免因异常导致循环退出
				time.sleep(0.1)

		logger.debug(f"事件引擎 {self.name} 主循环结束")

	def _process_event (self, event: BaseEvent) -> None:
		"""处理单个事件"""
		try:
			# 标记事件开始处理
			event.mark_processing()

			# 应用过滤器
			for event_filter in self._filters:
				if not event_filter.filter(event):
					logger.debug(f"事件 {event.event_id} 被过滤器 {event_filter.name} 过滤")
					event.mark_processed(success=False, error="Event filtered")
					self._stats["events_dropped"] += 1
					return

			# 应用转换器
			for transformer in self._transformers:
				event = transformer.transform(event)

			# 获取处理器
			handlers = self._registry.get_handlers(event.event_type)

			if not handlers:
				logger.debug(f"事件 {event.event_id} 没有处理器")
				event.mark_processed(success=True)
				self._stats["events_processed"] += 1
				return

			# 执行处理器
			for handler in handlers:
				try:
					# 提交到线程池执行
					future = self._executor.submit(handler.execute, event)

					# 可以添加回调处理结果
					future.add_done_callback(
						lambda f: self._handle_handler_result(f, handler)
					)

					self._stats["handlers_executed"] += 1

				except Exception as e:
					logger.error(f"处理器 {handler.handler_id} 提交失败: {e}", exc_info=True)

			event.mark_processed(success=True)
			self._stats["events_processed"] += 1
			self._stats["last_event_time"] = datetime.now()

		except Exception as e:
			logger.error(f"处理事件 {event.event_id} 失败: {e}", exc_info=True)
			event.mark_processed(success=False, error=str(e))
			self._stats["events_failed"] += 1

	@staticmethod
	def _handle_handler_result (future: Future, handler: EventHandler) -> None:
		"""处理处理器执行结果"""
		try:
			result = future.result()
			logger.debug(f"处理器 {handler.handler_id} 执行完成: {result}")
		except Exception as e:
			logger.error(f"处理器 {handler.handler_id} 执行失败: {e}", exc_info=True)

	def put (self, event: BaseEvent, priority: Optional[int] = None) -> bool:
		"""
		发布事件

		Args:
			event: 事件对象
			priority: 覆盖事件优先级

		Returns:
			bool: 是否成功加入队列
		"""
		if not self._running:
			logger.warning(f"事件引擎 {self.name} 未运行，事件 {event.event_id} 被丢弃")
			return False

		try:
			self._queue.put(event, priority)
			logger.debug(f"发布事件: {event.event_id} ({event.event_type})")
			return True
		except queue.Full:
			logger.warning(f"事件队列已满，事件 {event.event_id} 被丢弃")
			self._stats["events_dropped"] += 1
			return False

	def register (
			self,
			event_type: str,
			handler: Union[Callable, EventHandler],
			priority: int = 0
	) -> str:
		"""注册事件处理器"""
		return self._registry.register(event_type, handler, priority)

	def unregister (self, handler_id: str) -> bool:
		"""取消注册处理器"""
		return self._registry.unregister(handler_id)

	def add_filter (self, event_filter: EventFilter) -> None:
		"""添加事件过滤器"""
		self._filters.append(event_filter)
		logger.debug(f"添加事件过滤器: {event_filter.name}")

	def add_transformer (self, transformer: EventTransformer) -> None:
		"""添加事件转换器"""
		self._transformers.append(transformer)
		logger.debug(f"添加事件转换器: {transformer.name}")

	def get_stats (self) -> Dict[str, Any]:
		"""获取统计信息"""
		stats = self._stats.copy()
		stats.update({
			"queue_size": self._queue.qsize(),
			"is_running": self._running,
			"uptime": (datetime.now() - (self._stats["start_time"] or datetime.now())).total_seconds() if self._stats[
				"start_time"] else 0,
			"handler_count": self._registry.get_handler_count(),
		})
		return stats

	def clear_queue (self) -> None:
		"""清空事件队列"""
		self._queue.clear()
		logger.info(f"清空事件引擎 {self.name} 队列")

	def __enter__ (self):
		"""上下文管理器入口"""
		self.start()
		return self

	def __exit__ (self, exc_type, exc_val, exc_tb):
		"""上下文管理器出口"""
		self.stop()


class AsyncEventEngine(EventEngine):
	"""
	异步事件引擎
	基于asyncio的异步事件引擎
	"""

	def __init__ (
			self,
			name: str = "AsyncEventEngine",
			max_queue_size: int = 10000,
			auto_start: bool = True
	):
		super().__init__(name=name, max_workers=1, max_queue_size=max_queue_size, auto_start=False)

		# 异步特定组件
		self._async_queue = asyncio.Queue(maxsize=max_queue_size)
		self._async_tasks: Set[asyncio.Task] = set()
		self._loop: Optional[asyncio.AbstractEventLoop] = None

		if auto_start:
			self.start()

	async def put_async (self, event: BaseEvent, priority: Optional[int] = None) -> bool:
		"""异步发布事件

		Args:
			event: 事件对象
			priority: 优先级（被忽略，异步队列不支持优先级）
		
		Returns:
			bool: 是否成功发布
		"""
		# 异步队列不支持优先级，使用事件自身的优先级
		_ = priority  # 避免未使用参数警告
		if not self._running:
			logger.warning(f"异步事件引擎 {self.name} 未运行，事件 {event.event_id} 被丢弃")
			return False

		try:
			# 异步队列不支持优先级，使用事件自身的优先级
			await self._async_queue.put(event)
			logger.debug(f"异步发布事件: {event.event_id} ({event.event_type})")
			return True
		except asyncio.QueueFull:
			logger.warning(f"异步事件队列已满，事件 {event.event_id} 被丢弃")
			self._stats["events_dropped"] += 1
			return False

	def put (self, event: BaseEvent, priority: Optional[int] = None) -> bool:
		"""同步发布事件（包装为异步）"""
		if self._loop and self._loop.is_running():
			# 在事件循环中调度
			asyncio.run_coroutine_threadsafe(
				self.put_async(event, priority),
				self._loop
			)
			return True
		else:
			logger.warning("事件循环未运行，使用同步队列")
			return super().put(event, priority)

	async def _run_async_loop (self) -> None:
		"""异步事件处理主循环"""
		logger.debug(f"异步事件引擎 {self.name} 主循环开始")

		while self._running:
			try:
				# 异步获取事件
				event = await asyncio.wait_for(self._async_queue.get(), timeout=0.1)

				# 异步处理事件
				await self._process_event_async(event)

			except asyncio.TimeoutError:
				# 队列为空，继续循环
				continue
			except Exception as e:
				logger.error(f"异步事件引擎主循环异常: {e}", exc_info=True)
				await asyncio.sleep(0.1)

		logger.debug(f"异步事件引擎 {self.name} 主循环结束")

	async def _process_event_async (self, event: BaseEvent) -> None:
		"""异步处理单个事件"""
		try:
			# 标记事件开始处理
			event.mark_processing()

			# 应用过滤器
			for event_filter in self._filters:
				if not event_filter.filter(event):
					logger.debug(f"事件 {event.event_id} 被过滤器 {event_filter.name} 过滤")
					event.mark_processed(success=False, error="Event filtered")
					self._stats["events_dropped"] += 1
					return

			# 应用转换器
			for transformer in self._transformers:
				event = transformer.transform(event)

			# 获取处理器
			handlers = self._registry.get_handlers(event.event_type)

			if not handlers:
				logger.debug(f"事件 {event.event_id} 没有处理器")
				event.mark_processed(success=True)
				self._stats["events_processed"] += 1
				return

			# 异步执行处理器
			tasks = []
			for handler in handlers:
				try:
					if asyncio.iscoroutinefunction(handler.func):
						# 异步处理器
						task = asyncio.create_task(handler.execute_async(event))
						tasks.append(task)
						self._async_tasks.add(task)
						task.add_done_callback(self._async_tasks.discard)
					else:
						# 同步处理器，在线程池中执行
						future = self._executor.submit(handler.execute, event)
						future.add_done_callback(
							lambda f: self._handle_handler_result(f, handler)
						)

					self._stats["handlers_executed"] += 1

				except Exception as e:
					logger.error(f"处理器 {handler.handler_id} 提交失败: {e}", exc_info=True)

			# 等待所有异步任务完成
			if tasks:
				await asyncio.gather(*tasks, return_exceptions=True)

			event.mark_processed(success=True)
			self._stats["events_processed"] += 1
			self._stats["last_event_time"] = datetime.now()

		except Exception as e:
			logger.error(f"处理事件 {event.event_id} 失败: {e}", exc_info=True)
			event.mark_processed(success=False, error=str(e))
			self._stats["events_failed"] += 1

	def start (self) -> None:
		"""启动异步事件引擎"""
		if self._running:
			logger.warning(f"异步事件引擎 {self.name} 已经在运行")
			return

		self._running = True
		self._loop = asyncio.new_event_loop()

		# 在新线程中启动事件循环
		self._thread = threading.Thread(
			target=self._run_event_loop,
			name=f"{self.name}_AsyncLoop",
			daemon=True
		)
		self._thread.start()
		self._stats["start_time"] = datetime.now()

		logger.info(f"启动异步事件引擎: {self.name}")

	def _run_event_loop (self) -> None:
		"""运行事件循环"""
		asyncio.set_event_loop(self._loop)
		try:
			self._loop.run_until_complete(self._run_async_loop())
		finally:
			self._loop.close()

	async def stop_async (self, timeout: float = 5.0) -> None:
		"""异步停止事件引擎"""
		if not self._running:
			return

		logger.info(f"停止异步事件引擎: {self.name}")
		self._running = False

		# 等待所有任务完成
		if self._async_tasks:
			await asyncio.wait(self._async_tasks, timeout=timeout)

		# 关闭线程池
		self._executor.shutdown(wait=True)

		logger.info(f"异步事件引擎 {self.name} 已停止")

	def stop (self, timeout: float = 5.0) -> None:
		"""同步停止事件引擎"""
		if self._loop and self._loop.is_running():
			# 在事件循环中调度停止
			future = asyncio.run_coroutine_threadsafe(
				self.stop_async(timeout),
				self._loop
			)
			try:
				future.result(timeout=timeout + 1)
			except Exception as e:
				logger.error(f"停止异步事件引擎失败: {e}")
		else:
			super().stop(timeout)

	async def __aenter__ (self):
		"""异步上下文管理器入口"""
		self.start()
		return self

	async def __aexit__ (self, exc_type, exc_val, exc_tb):
		"""异步上下文管理器出口"""
		await self.stop_async()