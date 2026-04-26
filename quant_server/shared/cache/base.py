"""
缓存基类和异常定义
"""

import abc
import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Callable, Dict, List


class CacheError(Exception):
	"""缓存基础异常"""
	pass


class CacheKeyError(CacheError):
	"""缓存键错误"""
	pass


class CacheMissError(CacheError):
	"""缓存未命中"""
	pass


class CacheExpiredError(CacheError):
	"""缓存已过期"""
	pass


class CacheStrategy(Enum):
	"""缓存策略枚举"""
	WRITE_THROUGH = "write_through"  # 写穿透
	WRITE_BACK = "write_back"  # 写回
	WRITE_AROUND = "write_around"  # 写绕过
	READ_THROUGH = "read_through"  # 读穿透
	CACHE_ASIDE = "cache_aside"  # 旁路缓存


class CacheEntry:
	"""缓存条目"""

	def __init__ (
			self,
			value: Any,
			created_at: Optional[datetime] = None,
			expires_at: Optional[datetime] = None,
			tags: Optional[List[str]] = None,
			metadata: Optional[Dict[str, Any]] = None
	):
		self.value = value
		self.created_at = created_at or datetime.now()
		self.expires_at = expires_at
		self.tags = tags or []
		self.metadata = metadata or {}

	@property
	def is_expired (self) -> bool:
		"""检查是否过期"""
		if self.expires_at is None:
			return False
		return datetime.now() > self.expires_at

	@property
	def ttl (self) -> Optional[float]:
		"""获取剩余生存时间（秒）"""
		if self.expires_at is None:
			return None
		remaining = (self.expires_at - datetime.now()).total_seconds()
		return max(0.0, remaining)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"value": self.value,
			"created_at": self.created_at.isoformat() if self.created_at else None,
			"expires_at": self.expires_at.isoformat() if self.expires_at else None,
			"tags": self.tags,
			"metadata": self.metadata
		}


class CacheBase(abc.ABC):
	"""缓存基类"""

	def __init__ (
			self,
			namespace: str = "default",
			default_ttl: Optional[int] = None,
			key_prefix: str = "",
			serializer: Optional[Any] = None
	):
		self.namespace = namespace
		self.default_ttl = default_ttl
		self.key_prefix = key_prefix or namespace
		self.serializer = serializer

	def _make_key (self, key: str) -> str:
		"""生成完整的缓存键"""
		if not key:
			raise CacheKeyError("Cache key cannot be empty")

		# 添加命名空间前缀
		full_key = f"{self.key_prefix}:{key}"

		# 如果键过长，使用MD5哈希
		if len(full_key) > 250:
			full_key = f"{self.key_prefix}:{hashlib.md5(key.encode()).hexdigest()}"

		return full_key

	def _ensure_serializer (self):
		"""确保序列化器存在"""
		if self.serializer is None:
			raise CacheError("Serializer is not set")

	@abc.abstractmethod
	async def get (self, key: str, default: Any = None) -> Any:
		"""获取缓存值"""
		pass

	@abc.abstractmethod
	async def set (
			self,
			key: str,
			value: Any,
			ttl: Optional[int] = None,
			tags: Optional[List[str]] = None
	) -> bool:
		"""设置缓存值"""
		pass

	@abc.abstractmethod
	async def delete (self, key: str) -> bool:
		"""删除缓存值"""
		pass

	@abc.abstractmethod
	async def exists (self, key: str) -> bool:
		"""检查键是否存在"""
		pass

	@abc.abstractmethod
	async def clear (self) -> bool:
		"""清除所有缓存"""
		pass

	@abc.abstractmethod
	async def get_many (self, keys: List[str]) -> Dict[str, Any]:
		"""批量获取缓存值"""
		pass

	@abc.abstractmethod
	async def set_many (
			self,
			items: Dict[str, Any],
			ttl: Optional[int] = None
	) -> bool:
		"""批量设置缓存值"""
		pass

	async def get_or_set (
			self,
			key: str,
			default_func: Callable,
			ttl: Optional[int] = None
	) -> Any:
		"""获取缓存，如果不存在则设置"""
		value = await self.get(key)
		if value is None:
			value = default_func()
			await self.set(key, value, ttl)
		return value

	async def increment (self, key: str, amount: int = 1) -> int:
		"""原子递增"""
		value = await self.get(key, 0)
		new_value = value + amount
		await self.set(key, new_value)
		return new_value

	async def decrement (self, key: str, amount: int = 1) -> int:
		"""原子递减"""
		return await self.increment(key, -amount)

	@abc.abstractmethod
	async def delete_by_tags (self, tags: List[str]) -> int:
		"""根据标签删除缓存"""
		pass

	@abc.abstractmethod
	async def get_stats (self) -> Dict[str, Any]:
		"""获取缓存统计信息"""
		pass

	async def ping (self) -> bool:
		"""检查缓存是否可用"""
		try:
			await self.set("__ping__", 1, 1)
			value = await self.get("__ping__")
			await self.delete("__ping__")
			return value == 1
		except (CacheError, ConnectionError, TimeoutError):
			return False