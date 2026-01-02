"""
日志上下文管理器 - 提供日志上下文跟踪和管理功能

职责：
1. 上下文传播（跨线程、跨协程、跨请求）
2. 上下文存储（请求ID、用户ID、会话ID等）
3. 上下文继承（父子上下文关系）
4. 上下文清理（自动清理过期上下文）
5. 上下文查询（按条件查询上下文信息）

设计原则：
1. 线程安全：支持多线程和异步环境
2. 可扩展：支持自定义上下文类型
3. 高性能：轻量级上下文管理
4. 一致性：确保上下文在所有日志中保持一致
5. 可追踪：支持上下文链追踪

注意：Python 3.7+ 使用contextvars，旧版本使用threading.local
"""

import threading
import asyncio
import contextvars
import uuid
import time
from typing import Dict, List, Any, Optional, Union, Callable, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import weakref
from collections import defaultdict
import inspect
import functools


class ContextType(Enum):
	"""上下文类型枚举"""
	REQUEST = "request"  # 请求上下文
	SESSION = "session"  # 会话上下文
	USER = "user"  # 用户上下文
	TASK = "task"  # 任务上下文
	TRANSACTION = "transaction"  # 事务上下文
	CORRELATION = "correlation"  # 关联上下文
	CUSTOM = "custom"  # 自定义上下文


@dataclass
class ContextEntry:
	"""上下文条目"""
	key: str  # 键
	value: Any  # 值
	context_type: ContextType  # 上下文类型
	created_at: float  # 创建时间戳
	expires_at: Optional[float] = None  # 过期时间戳
	metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

	def is_expired (self) -> bool:
		"""检查是否过期"""
		if self.expires_at is None:
			return False
		return time.time() > self.expires_at

	def time_to_live (self) -> Optional[float]:
		"""获取剩余存活时间（秒）"""
		if self.expires_at is None:
			return None
		ttl = self.expires_at - time.time()
		return max(0, ttl) if ttl > 0 else 0


@dataclass
class ContextSnapshot:
	"""上下文快照"""
	context_id: str  # 上下文ID
	entries: Dict[str, ContextEntry]  # 上下文条目
	parent_id: Optional[str] = None  # 父上下文ID
	created_at: float = field(default_factory=time.time)  # 创建时间
	metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"context_id": self.context_id,
			"parent_id": self.parent_id,
			"created_at": self.created_at,
			"entries": {k: asdict(v) for k, v in self.entries.items()},
			"metadata": self.metadata
		}

	def get_value (self, key: str, default: Any = None) -> Any:
		"""获取值"""
		entry = self.entries.get(key)
		return entry.value if entry else default


class ContextStorage:
	"""上下文存储基类"""

	def get (self, key: str) -> Optional[Any]:
		"""获取上下文值"""
		raise NotImplementedError

	def set (self, key: str, value: Any, **kwargs):
		"""设置上下文值"""
		raise NotImplementedError

	def delete (self, key: str):
		"""删除上下文值"""
		raise NotImplementedError

	def clear (self):
		"""清除所有上下文"""
		raise NotImplementedError

	def get_all (self) -> Dict[str, Any]:
		"""获取所有上下文"""
		raise NotImplementedError

	def get_snapshot (self) -> ContextSnapshot:
		"""获取上下文快照"""
		raise NotImplementedError

	def restore_snapshot (self, snapshot: ContextSnapshot):
		"""恢复上下文快照"""
		raise NotImplementedError


class ThreadLocalContextStorage(ContextStorage):
	"""线程本地上下文存储（线程安全）"""

	def __init__ (self):
		self._local = threading.local()

	def _ensure_context (self):
		"""确保上下文字典存在"""
		if not hasattr(self._local, 'context'):
			self._local.context = {}
			self._local.context_id = str(uuid.uuid4())
			self._local.parent_id = None
			self._local.created_at = time.time()
			self._local.metadata = {}

	def get (self, key: str) -> Optional[Any]:
		"""获取上下文值"""
		self._ensure_context()
		return self._local.context.get(key)

	def set (self, key: str, value: Any, **kwargs):
		"""设置上下文值"""
		self._ensure_context()
		self._local.context[key] = value

		# 更新元数据
		if 'context_type' in kwargs:
			if not hasattr(self._local, 'entry_metadata'):
				self._local.entry_metadata = {}
			if key not in self._local.entry_metadata:
				self._local.entry_metadata[key] = {}
			self._local.entry_metadata[key]['context_type'] = kwargs['context_type']

	def delete (self, key: str):
		"""删除上下文值"""
		self._ensure_context()
		if key in self._local.context:
			del self._local.context[key]

		# 删除元数据
		if hasattr(self._local, 'entry_metadata') and key in self._local.entry_metadata:
			del self._local.entry_metadata[key]

	def clear (self):
		"""清除所有上下文"""
		if hasattr(self._local, 'context'):
			del self._local.context
		if hasattr(self._local, 'entry_metadata'):
			del self._local.entry_metadata
		if hasattr(self._local, 'context_id'):
			del self._local.context_id
		if hasattr(self._local, 'parent_id'):
			del self._local.parent_id
		if hasattr(self._local, 'created_at'):
			del self._local.created_at
		if hasattr(self._local, 'metadata'):
			del self._local.metadata

	def get_all (self) -> Dict[str, Any]:
		"""获取所有上下文"""
		self._ensure_context()
		return self._local.context.copy()

	def get_snapshot (self) -> ContextSnapshot:
		"""获取上下文快照"""
		self._ensure_context()

		# 创建上下文条目
		entries = {}
		for key, value in self._local.context.items():
			# 获取元数据
			context_type = ContextType.CUSTOM
			if hasattr(self._local, 'entry_metadata') and key in self._local.entry_metadata:
				type_str = self._local.entry_metadata[key].get('context_type')
				if type_str:
					try:
						context_type = ContextType(type_str)
					except ValueError:
						context_type = ContextType.CUSTOM

			entry = ContextEntry(
				key=key,
				value=value,
				context_type=context_type,
				created_at=time.time()
			)
			entries[key] = entry

		return ContextSnapshot(
			context_id=getattr(self._local, 'context_id', str(uuid.uuid4())),
			entries=entries,
			parent_id=getattr(self._local, 'parent_id', None),
			created_at=getattr(self._local, 'created_at', time.time()),
			metadata=getattr(self._local, 'metadata', {})
		)

	def restore_snapshot (self, snapshot: ContextSnapshot):
		"""恢复上下文快照"""
		self.clear()

		# 恢复基本属性
		self._local.context_id = snapshot.context_id
		self._local.parent_id = snapshot.parent_id
		self._local.created_at = snapshot.created_at
		self._local.metadata = snapshot.metadata

		# 恢复上下文值
		self._local.context = {}
		self._local.entry_metadata = {}

		for key, entry in snapshot.entries.items():
			self._local.context[key] = entry.value
			self._local.entry_metadata[key] = {
				'context_type': entry.context_type.value,
				'created_at': entry.created_at
			}


class ContextVarStorage(ContextStorage):
	"""ContextVar上下文存储（支持异步）"""

	def __init__ (self):
		# 使用ContextVar存储上下文
		self._context_var = contextvars.ContextVar('log_context', default={})
		self._metadata_var = contextvars.ContextVar('log_context_metadata', default={})

		# 固定属性（每个上下文实例独立）
		self._context_id_var = contextvars.ContextVar('context_id', default=str(uuid.uuid4()))
		self._parent_id_var = contextvars.ContextVar('parent_id', default=None)
		self._created_at_var = contextvars.ContextVar('created_at', default=time.time())

	def get (self, key: str) -> Optional[Any]:
		"""获取上下文值"""
		context = self._context_var.get()
		return context.get(key)

	def set (self, key: str, value: Any, **kwargs):
		"""设置上下文值"""
		# 获取当前上下文
		context = self._context_var.get().copy()
		metadata = self._metadata_var.get().copy()

		# 更新值
		context[key] = value

		# 更新元数据
		if 'context_type' in kwargs:
			if key not in metadata:
				metadata[key] = {}
			metadata[key]['context_type'] = kwargs['context_type']

		# 设置回ContextVar
		self._context_var.set(context)
		self._metadata_var.set(metadata)

	def delete (self, key: str):
		"""删除上下文值"""
		context = self._context_var.get().copy()
		metadata = self._metadata_var.get().copy()

		if key in context:
			del context[key]

		if key in metadata:
			del metadata[key]

		self._context_var.set(context)
		self._metadata_var.set(metadata)

	def clear (self):
		"""清除所有上下文"""
		self._context_var.set({})
		self._metadata_var.set({})
		self._context_id_var.set(str(uuid.uuid4()))
		self._parent_id_var.set(None)
		self._created_at_var.set(time.time())

	def get_all (self) -> Dict[str, Any]:
		"""获取所有上下文"""
		return self._context_var.get().copy()

	def get_snapshot (self) -> ContextSnapshot:
		"""获取上下文快照"""
		context = self._context_var.get()
		metadata = self._metadata_var.get()

		# 创建上下文条目
		entries = {}
		for key, value in context.items():
			# 获取元数据
			context_type = ContextType.CUSTOM
			if key in metadata and 'context_type' in metadata[key]:
				type_str = metadata[key]['context_type']
				try:
					context_type = ContextType(type_str)
				except ValueError:
					context_type = ContextType.CUSTOM

			entry = ContextEntry(
				key=key,
				value=value,
				context_type=context_type,
				created_at=time.time()
			)
			entries[key] = entry

		return ContextSnapshot(
			context_id=self._context_id_var.get(),
			entries=entries,
			parent_id=self._parent_id_var.get(),
			created_at=self._created_at_var.get(),
			metadata=metadata.get('_global', {})
		)

	def restore_snapshot (self, snapshot: ContextSnapshot):
		"""恢复上下文快照"""
		# 恢复上下文值
		context = {}
		metadata = {'_global': snapshot.metadata}

		for key, entry in snapshot.entries.items():
			context[key] = entry.value
			if key not in metadata:
				metadata[key] = {}
			metadata[key]['context_type'] = entry.context_type.value

		# 设置回ContextVar
		self._context_var.set(context)
		self._metadata_var.set(metadata)
		self._context_id_var.set(snapshot.context_id)
		self._parent_id_var.set(snapshot.parent_id)
		self._created_at_var.set(snapshot.created_at)


class LogContextManager:
	"""
	日志上下文管理器

	提供统一的上下文管理接口，支持线程和异步环境
	"""

	_instance = None
	_lock = threading.Lock()

	def __new__ (cls):
		with cls._lock:
			if cls._instance is None:
				cls._instance = super().__new__(cls)
				cls._instance._initialized = False
			return cls._instance

	def __init__ (self, storage_type: str = "auto"):
		if self._initialized:
			return

		# 根据Python版本选择存储类型
		if storage_type == "auto":
			# 自动选择最佳存储
			try:
				# 检查是否支持contextvars（Python 3.7+）
				import sys
				if sys.version_info >= (3, 7):
					storage_type = "contextvar"
				else:
					storage_type = "threadlocal"
			except:
				storage_type = "threadlocal"

		if storage_type == "contextvar":
			self.storage = ContextVarStorage()
		elif storage_type == "threadlocal":
			self.storage = ThreadLocalContextStorage()
		else:
			raise ValueError(f"不支持的存储类型: {storage_type}")

		# 上下文链管理
		self._context_chain: Dict[str, ContextSnapshot] = {}
		self._cleanup_thread = None
		self._cleanup_running = False

		self._initialized = True

	def get (self, key: str, default: Any = None) -> Any:
		"""获取上下文值"""
		return self.storage.get(key) or default

	def set (self, key: str, value: Any, **kwargs):
		"""设置上下文值"""
		self.storage.set(key, value, **kwargs)

	def update (self, **kwargs):
		"""批量设置上下文值"""
		for key, value in kwargs.items():
			self.storage.set(key, value)

	def delete (self, key: str):
		"""删除上下文值"""
		self.storage.delete(key)

	def clear (self):
		"""清除所有上下文"""
		self.storage.clear()

	def get_all (self) -> Dict[str, Any]:
		"""获取所有上下文"""
		return self.storage.get_all()

	def get_context_id (self) -> str:
		"""获取当前上下文ID"""
		# 从快照获取上下文ID
		snapshot = self.storage.get_snapshot()
		return snapshot.context_id

	def create_child_context (self, inherit: bool = True, **kwargs) -> str:
		"""
		创建子上下文

		Args:
			inherit: 是否继承父上下文
			**kwargs: 要设置的上下文值

		Returns:
			str: 子上下文ID
		"""
		# 保存当前上下文快照
		parent_snapshot = self.storage.get_snapshot()
		parent_id = parent_snapshot.context_id

		# 保存到上下文链
		self._context_chain[parent_id] = parent_snapshot

		# 创建新的上下文
		child_id = str(uuid.uuid4())

		# 清除当前上下文或继承
		if inherit:
			# 继承父上下文
			child_snapshot = ContextSnapshot(
				context_id=child_id,
				entries=parent_snapshot.entries.copy(),
				parent_id=parent_id,
				created_at=time.time(),
				metadata=parent_snapshot.metadata.copy()
			)
		else:
			# 全新上下文
			child_snapshot = ContextSnapshot(
				context_id=child_id,
				entries={},
				parent_id=parent_id,
				created_at=time.time(),
				metadata={}
			)

		# 恢复子上下文
		self.storage.restore_snapshot(child_snapshot)

		# 设置新值
		if kwargs:
			self.update(**kwargs)

		return child_id

	def switch_to_context (self, context_id: str) -> bool:
		"""
		切换到指定上下文

		Args:
			context_id: 上下文ID

		Returns:
			bool: 是否切换成功
		"""
		if context_id in self._context_chain:
			snapshot = self._context_chain[context_id]
			self.storage.restore_snapshot(snapshot)
			return True
		return False

	def get_parent_context (self) -> Optional[ContextSnapshot]:
		"""获取父上下文"""
		snapshot = self.storage.get_snapshot()
		if snapshot.parent_id:
			return self._context_chain.get(snapshot.parent_id)
		return None

	def get_context_chain (self) -> List[ContextSnapshot]:
		"""获取上下文链"""
		chain = []
		current = self.storage.get_snapshot()

		while current:
			chain.append(current)
			if current.parent_id and current.parent_id in self._context_chain:
				current = self._context_chain[current.parent_id]
			else:
				break

		return list(reversed(chain))  # 从根到当前

	def bind_to_request (self, request_id: str = None, **kwargs):
		"""绑定到请求上下文"""
		if request_id is None:
			request_id = f"req_{uuid.uuid4().hex[:16]}"

		self.update(
			request_id=request_id,
			context_type=ContextType.REQUEST.value,
			**kwargs
		)

	def bind_to_user (self, user_id: str, **kwargs):
		"""绑定到用户上下文"""
		self.update(
			user_id=user_id,
			context_type=ContextType.USER.value,
			**kwargs
		)

	def bind_to_session (self, session_id: str = None, **kwargs):
		"""绑定到会话上下文"""
		if session_id is None:
			session_id = f"ses_{uuid.uuid4().hex[:16]}"

		self.update(
			session_id=session_id,
			context_type=ContextType.SESSION.value,
			**kwargs
		)

	def bind_to_correlation (self, correlation_id: str = None, **kwargs):
		"""绑定到关联上下文"""
		if correlation_id is None:
			correlation_id = f"corr_{uuid.uuid4().hex[:16]}"

		self.update(
			correlation_id=correlation_id,
			context_type=ContextType.CORRELATION.value,
			**kwargs
		)

	# 装饰器支持
	def context_decorator (self, **context_kwargs):
		"""上下文装饰器"""

		def decorator (func):
			@functools.wraps(func)
			def wrapper (*args, **kwargs):
				# 创建子上下文
				child_id = self.create_child_context(inherit=True, **context_kwargs)
				try:
					result = func(*args, **kwargs)
					return result
				finally:
					# 切换回父上下文
					snapshot = self.storage.get_snapshot()
					if snapshot.parent_id:
						self.switch_to_context(snapshot.parent_id)

			return wrapper

		return decorator

	def async_context_decorator (self, **context_kwargs):
		"""异步上下文装饰器"""

		def decorator (func):
			@functools.wraps(func)
			async def wrapper (*args, **kwargs):
				# 创建子上下文
				child_id = self.create_child_context(inherit=True, **context_kwargs)
				try:
					result = await func(*args, **kwargs)
					return result
				finally:
					# 切换回父上下文
					snapshot = self.storage.get_snapshot()
					if snapshot.parent_id:
						self.switch_to_context(snapshot.parent_id)

			return wrapper

		return decorator

	# 上下文管理器支持
	def context_manager (self, **context_kwargs):
		"""上下文管理器"""
		return LogContextManagerInstance(self, **context_kwargs)

	# 清理过期上下文
	def start_cleanup (self, interval: int = 300, max_age: int = 3600):
		"""启动上下文清理线程"""
		if self._cleanup_running:
			return

		self._cleanup_running = True
		self._cleanup_thread = threading.Thread(
			target=self._cleanup_worker,
			args=(interval, max_age),
			daemon=True,
			name="ContextCleanup"
		)
		self._cleanup_thread.start()

	def stop_cleanup (self):
		"""停止上下文清理"""
		self._cleanup_running = False
		if self._cleanup_thread:
			self._cleanup_thread.join(timeout=5)
			self._cleanup_thread = None

	def _cleanup_worker (self, interval: int, max_age: int):
		"""清理工作线程"""
		while self._cleanup_running:
			time.sleep(interval)
			self._cleanup_expired_contexts(max_age)

	def _cleanup_expired_contexts (self, max_age: int):
		"""清理过期上下文"""
		current_time = time.time()
		expired_keys = []

		for context_id, snapshot in self._context_chain.items():
			age = current_time - snapshot.created_at
			if age > max_age:
				expired_keys.append(context_id)

		for key in expired_keys:
			del self._context_chain[key]

	def get_stats (self) -> Dict[str, Any]:
		"""获取统计信息"""
		return {
			"total_contexts": len(self._context_chain),
			"current_context_id": self.get_context_id(),
			"storage_type": self.storage.__class__.__name__
		}


class LogContextManagerInstance:
	"""日志上下文管理器实例（用于with语句）"""

	def __init__ (self, manager: LogContextManager, **context_kwargs):
		self.manager = manager
		self.context_kwargs = context_kwargs
		self.child_context_id = None

	def __enter__ (self):
		self.child_context_id = self.manager.create_child_context(
			inherit=True,
			**self.context_kwargs
		)
		return self.manager

	def __exit__ (self, exc_type, exc_val, exc_tb):
		# 切换回父上下文
		snapshot = self.manager.storage.get_snapshot()
		if snapshot.parent_id:
			self.manager.switch_to_context(snapshot.parent_id)


# 便捷函数
_context_manager = None


def get_context_manager () -> LogContextManager:
	"""获取上下文管理器（单例）"""
	global _context_manager
	if _context_manager is None:
		_context_manager = LogContextManager()
	return _context_manager


def get_context () -> Dict[str, Any]:
	"""获取当前上下文（便捷函数）"""
	return get_context_manager().get_all()


def set_context (key: str, value: Any, **kwargs):
	"""设置上下文值（便捷函数）"""
	get_context_manager().set(key, value, **kwargs)


def update_context (**kwargs):
	"""批量设置上下文值（便捷函数）"""
	get_context_manager().update(**kwargs)


def clear_context ():
	"""清除上下文（便捷函数）"""
	get_context_manager().clear()


def bind_request_context (request_id: str = None, **kwargs):
	"""绑定请求上下文（便捷函数）"""
	get_context_manager().bind_to_request(request_id, **kwargs)


def bind_user_context (user_id: str, **kwargs):
	"""绑定用户上下文（便捷函数）"""
	get_context_manager().bind_to_user(user_id, **kwargs)


def bind_session_context (session_id: str = None, **kwargs):
	"""绑定会话上下文（便捷函数）"""
	get_context_manager().bind_to_session(session_id, **kwargs)


def create_child_context (inherit: bool = True, **kwargs) -> str:
	"""创建子上下文（便捷函数）"""
	return get_context_manager().create_child_context(inherit, **kwargs)


# 装饰器便捷函数
def with_context (**context_kwargs):
	"""上下文装饰器（便捷函数）"""
	return get_context_manager().context_decorator(**context_kwargs)


def with_async_context (**context_kwargs):
	"""异步上下文装饰器（便捷函数）"""
	return get_context_manager().async_context_decorator(**context_kwargs)


# 上下文感知的函数包装器
class ContextAwareFunction:
	"""上下文感知函数包装器"""

	def __init__ (self, func, context_keys: List[str] = None):
		self.func = func
		self.context_keys = context_keys or []
		functools.update_wrapper(self, func)

	def __call__ (self, *args, **kwargs):
		# 获取当前上下文
		context = get_context()

		# 提取需要的上下文值
		context_values = {}
		for key in self.context_keys:
			if key in context:
				context_values[key] = context[key]

		# 将上下文值添加到kwargs
		if context_values:
			kwargs['_context'] = context_values

		# 调用原函数
		return self.func(*args, **kwargs)

	async def __call_async__ (self, *args, **kwargs):
		# 异步版本
		context = get_context()

		context_values = {}
		for key in self.context_keys:
			if key in context:
				context_values[key] = context[key]

		if context_values:
			kwargs['_context'] = context_values

		# 调用原异步函数
		if asyncio.iscoroutinefunction(self.func):
			return await self.func(*args, **kwargs)
		else:
			return self.func(*args, **kwargs)


def context_aware (context_keys: List[str] = None):
	"""上下文感知装饰器"""

	def decorator (func):
		if asyncio.iscoroutinefunction(func):
			# 异步函数
			@functools.wraps(func)
			async def wrapper (*args, **kwargs):
				context = get_context()

				context_values = {}
				for key in context_keys or []:
					if key in context:
						context_values[key] = context[key]

				if context_values:
					kwargs['_context'] = context_values

				return await func(*args, **kwargs)
		else:
			# 同步函数
			@functools.wraps(func)
			def wrapper (*args, **kwargs):
				context = get_context()

				context_values = {}
				for key in context_keys or []:
					if key in context:
						context_values[key] = context[key]

				if context_values:
					kwargs['_context'] = context_values

				return func(*args, **kwargs)

		return wrapper

	return decorator


# 上下文过滤器
class ContextFilter:
	"""上下文过滤器"""

	def __init__ (self, include_keys: List[str] = None,
	              exclude_keys: List[str] = None):
		self.include_keys = set(include_keys) if include_keys else None
		self.exclude_keys = set(exclude_keys) if exclude_keys else None

	def filter (self, context: Dict[str, Any]) -> Dict[str, Any]:
		"""过滤上下文"""
		filtered = {}

		for key, value in context.items():
			# 检查包含规则
			if self.include_keys and key not in self.include_keys:
				continue

			# 检查排除规则
			if self.exclude_keys and key in self.exclude_keys:
				continue

			filtered[key] = value

		return filtered

	def __call__ (self, context: Dict[str, Any]) -> Dict[str, Any]:
		return self.filter(context)


# 使用示例
if __name__ == "__main__":
	print("=== 日志上下文管理器示例 ===")

	# 1. 基本使用
	print("\n1. 基本使用:")
	manager = get_context_manager()

	manager.set("request_id", "req_123", context_type=ContextType.REQUEST.value)
	manager.set("user_id", "user_456", context_type=ContextType.USER.value)

	print(f"当前上下文: {manager.get_all()}")
	print(f"请求ID: {manager.get('request_id')}")
	print(f"上下文ID: {manager.get_context_id()}")

	# 2. 创建子上下文
	print("\n2. 创建子上下文:")
	child_id = manager.create_child_context(inherit=True, operation="process_data")

	print(f"子上下文ID: {child_id}")
	print(f"子上下文: {manager.get_all()}")

	# 3. 上下文链
	print("\n3. 上下文链:")
	chain = manager.get_context_chain()
	print(f"上下文链长度: {len(chain)}")

	# 4. 切换回父上下文
	print("\n4. 切换回父上下文:")
	parent_snapshot = manager.get_parent_context()
	if parent_snapshot:
		manager.switch_to_context(parent_snapshot.context_id)
		print(f"切换后的上下文: {manager.get_all()}")

	# 5. 装饰器使用
	print("\n5. 装饰器使用:")


	@with_context(operation="decorated_function", source="decorator")
	def test_function ():
		print(f"函数内上下文: {get_context()}")


	test_function()

	# 6. 异步装饰器
	print("\n6. 异步装饰器:")


	@with_async_context(operation="async_function", source="async_decorator")
	async def async_test ():
		print(f"异步函数内上下文: {get_context()}")


	import asyncio

	asyncio.run(async_test())

	# 7. 上下文管理器
	print("\n7. 上下文管理器:")
	with manager.context_manager(operation="with_statement", temp_value="temp"):
		print(f"with语句内上下文: {manager.get_all()}")

	print(f"with语句后上下文: {manager.get_all()}")

	# 8. 上下文感知函数
	print("\n8. 上下文感知函数:")


	@context_aware(["request_id", "user_id"])
	def context_aware_function (arg1, **kwargs):
		print(f"参数: {arg1}")
		print(f"上下文值: {kwargs.get('_context')}")


	context_aware_function("test")

	# 9. 绑定上下文
	print("\n9. 绑定上下文:")
	bind_request_context("req_new_789")
	bind_user_context("user_new_012")

	print(f"绑定后的上下文: {get_context()}")

	# 10. 清理上下文
	print("\n10. 清理上下文:")
	clear_context()
	print(f"清理后的上下文: {get_context()}")

	# 11. 统计信息
	print("\n11. 统计信息:")
	stats = manager.get_stats()
	print(f"统计: {stats}")

	# 12. 启动清理线程
	print("\n12. 启动清理线程:")
	manager.start_cleanup(interval=10, max_age=30)  # 每10秒清理一次超过30秒的上下文
	time.sleep(1)  # 给清理线程一点时间启动

	print("示例完成")
	manager.stop_cleanup()