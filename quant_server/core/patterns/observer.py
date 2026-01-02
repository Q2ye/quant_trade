"""
观察者模式实现

定义对象间的一对多依赖关系，当一个对象状态改变时，所有依赖它的对象都会收到通知并自动更新。
在量化交易系统中，这是事件驱动架构的核心模式。

典型应用场景：
1. 事件引擎：主题-观察者模式
2. 行情订阅：当行情更新时通知所有策略
3. 信号监听：策略信号通知交易引擎
4. 状态监控：系统状态变化通知监控模块
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable, Optional
from weakref import WeakKeyDictionary, WeakSet
import asyncio


class Observer(ABC):
	"""
	观察者接口

	所有观察者必须实现此接口。
	"""

	@abstractmethod
	async def update (self, subject: Any, event: str, data: Dict[str, Any]) -> None:
		"""
		接收主题通知

		Args:
			subject: 主题对象
			event: 事件类型
			data: 事件数据
		"""
		pass

	@abstractmethod
	def get_observer_id (self) -> str:
		"""获取观察者唯一标识"""
		pass


class Observable:
	"""
	可观察对象（主题）

	维护观察者列表，并在状态变化时通知所有观察者。
	"""

	def __init__ (self, name: Optional[str] = None):
		"""
		初始化可观察对象

		Args:
			name: 对象名称（用于调试）
		"""
		self._name = name or self.__class__.__name__
		self._observers = WeakSet()  # 弱引用，防止内存泄漏
		self._event_handlers = {}  # 特定事件处理器
		self._lock = asyncio.Lock()

	def attach (self, observer: Observer, events: Optional[List[str]] = None) -> None:
		"""
		附加观察者

		Args:
			observer: 观察者实例
			events: 关注的事件列表（None表示关注所有事件）
		"""
		self._observers.add(observer)
		if events:
			for event in events:
				if event not in self._event_handlers:
					self._event_handlers[event] = WeakSet()
				self._event_handlers[event].add(observer)

	def detach (self, observer: Observer) -> None:
		"""移除观察者"""
		self._observers.discard(observer)
		for handlers in self._event_handlers.values():
			handlers.discard(observer)

	async def notify (self, event: str, data: Dict[str, Any]) -> None:
		"""
		通知所有观察者

		Args:
			event: 事件类型
			data: 事件数据
		"""
		async with self._lock:
			# 获取需要通知的观察者
			observers_to_notify = set()

			# 特定事件观察者
			if event in self._event_handlers:
				observers_to_notify.update(self._event_handlers[event])

			# 所有事件观察者
			for observer in self._observers:
				if observer not in self._event_handlers or event not in self._event_handlers:
					observers_to_notify.add(observer)

			# 异步通知所有观察者
			tasks = []
			for observer in observers_to_notify:
				tasks.append(
					asyncio.create_task(
						observer.update(self, event, data)
					)
				)

			if tasks:
				await asyncio.gather(*tasks, return_exceptions=True)

	def get_observer_count (self) -> int:
		"""获取观察者数量"""
		return len(self._observers)

	def get_event_observers (self, event: str) -> List[str]:
		"""获取关注特定事件的观察者ID列表"""
		if event not in self._event_handlers:
			return []
		return [obs.get_observer_id() for obs in self._event_handlers[event]]