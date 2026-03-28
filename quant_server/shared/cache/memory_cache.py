"""
内存缓存实现
"""

import asyncio
import fnmatch
import threading
import time
from typing import Any, Optional, List, Dict, Tuple
from collections import OrderedDict
from datetime import datetime, timedelta

from .base import CacheBase, CacheEntry, CacheError
from .serializers import SerializerBase


class MemoryCache(CacheBase):
	"""内存缓存实现（LRU缓存）"""

	def __init__ (
			self,
			namespace: str = "default",
			default_ttl: Optional[int] = 3600,
			key_prefix: str = "",
			serializer: Optional[SerializerBase] = None,
			max_size: int = 10000,
			cleanup_interval: int = 300
	):
		super().__init__(namespace, default_ttl, key_prefix, serializer)
		self.max_size = max_size
		self.cleanup_interval = cleanup_interval

		# 使用OrderedDict实现LRU缓存
		self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
		self._lock = threading.RLock()
		self._tag_index: Dict[str, set] = {}

		# 启动清理线程
		self._cleanup_thread = None
		self._stop_cleanup = threading.Event()
		self._start_cleanup_thread()

	def _start_cleanup_thread (self):
		"""启动清理线程"""
		if self.cleanup_interval > 0:
			self._cleanup_thread = threading.Thread(
				target=self._cleanup_loop,
				daemon=True,
				name=f"MemoryCacheCleanup-{self.namespace}"
			)
			self._cleanup_thread.start()

	def _cleanup_loop (self):
		"""清理循环"""
		while not self._stop_cleanup.is_set():
			time.sleep(self.cleanup_interval)
			self._cleanup_expired()

	def _cleanup_expired (self):
		"""清理过期缓存"""
		with self._lock:
			expired_keys = []
			now = datetime.now()

			for key, entry in self._cache.items():
				if entry.is_expired:
					expired_keys.append(key)

			for key in expired_keys:
				self._delete_unsafe(key)

	def _delete_unsafe (self, key: str):
		"""不安全删除（无锁）"""
		if key in self._cache:
			entry = self._cache.pop(key)
			# 清理标签索引
			for tag in entry.tags:
				if tag in self._tag_index:
					self._tag_index[tag].discard(key)
					if not self._tag_index[tag]:
						del self._tag_index[tag]

	def _evict_if_necessary (self):
		"""如果需要则驱逐旧缓存"""
		if len(self._cache) > self.max_size:
			# 移除最旧的条目
			key = next(iter(self._cache))
			self._delete_unsafe(key)

	def _get_entry (self, key: str) -> Optional[CacheEntry]:
		"""获取缓存条目"""
		with self._lock:
			if key not in self._cache:
				return None

			entry = self._cache[key]

			# 检查是否过期
			if entry.is_expired:
				self._delete_unsafe(key)
				return None

			# 移动到最近使用的位置
			self._cache.move_to_end(key)
			return entry

	async def get (self, key: str, default: Any = None) -> Any:
		"""获取缓存值"""
		try:
			cache_key = self._make_key(key)
			entry = self._get_entry(cache_key)

			if entry is None:
				return default

			return entry.value

		except Exception as e:
			raise CacheError(f"Failed to get cache key {key}: {str(e)}")

	async def set (
			self,
			key: str,
			value: Any,
			ttl: Optional[int] = None,
			tags: Optional[List[str]] = None
	) -> bool:
		"""设置缓存值"""
		try:
			cache_key = self._make_key(key)

			with self._lock:
				# 删除旧缓存（如果存在）
				if cache_key in self._cache:
					old_entry = self._cache[cache_key]
					for tag in old_entry.tags:
						if tag in self._tag_index:
							self._tag_index[tag].discard(cache_key)

				# 创建新缓存条目
				expires_at = None
				if ttl is not None:
					expires_at = datetime.now() + timedelta(seconds=ttl)
				elif self.default_ttl is not None:
					expires_at = datetime.now() + timedelta(seconds=self.default_ttl)

				entry = CacheEntry(value=value, expires_at=expires_at, tags=tags or [])

				# 存储缓存
				self._cache[cache_key] = entry
				self._cache.move_to_end(cache_key)

				# 更新标签索引
				for tag in entry.tags:
					if tag not in self._tag_index:
						self._tag_index[tag] = set()
					self._tag_index[tag].add(cache_key)

				# 检查是否需要驱逐
				self._evict_if_necessary()

			return True

		except Exception as e:
			raise CacheError(f"Failed to set cache key {key}: {str(e)}")

	async def delete (self, key: str) -> bool:
		"""删除缓存值"""
		try:
			cache_key = self._make_key(key)

			with self._lock:
				if cache_key in self._cache:
					self._delete_unsafe(cache_key)
					return True
				return False

		except Exception as e:
			raise CacheError(f"Failed to delete cache key {key}: {str(e)}")

	async def exists (self, key: str) -> bool:
		"""检查键是否存在"""
		try:
			cache_key = self._make_key(key)

			with self._lock:
				if cache_key not in self._cache:
					return False

				entry = self._cache[cache_key]
				if entry.is_expired:
					self._delete_unsafe(cache_key)
					return False

				return True

		except Exception as e:
			raise CacheError(f"Failed to check existence of key {key}: {str(e)}")

	async def clear (self) -> bool:
		"""清除所有缓存"""
		try:
			with self._lock:
				self._cache.clear()
				self._tag_index.clear()
			return True

		except Exception as e:
			raise CacheError(f"Failed to clear cache: {str(e)}")

	async def get_many (self, keys: List[str]) -> Dict[str, Any]:
		"""批量获取缓存值"""
		try:
			result = {}

			with self._lock:
				for key in keys:
					cache_key = self._make_key(key)

					if cache_key in self._cache:
						entry = self._cache[cache_key]

						if entry.is_expired:
							self._delete_unsafe(cache_key)
							result[key] = None
						else:
							result[key] = entry.value
							self._cache.move_to_end(cache_key)
					else:
						result[key] = None

			return result

		except Exception as e:
			raise CacheError(f"Failed to get multiple cache keys: {str(e)}")

	async def set_many (
			self,
			items: Dict[str, Any],
			ttl: Optional[int] = None
	) -> bool:
		"""批量设置缓存值"""
		try:
			with self._lock:
				for key, value in items.items():
					cache_key = self._make_key(key)

					# 删除旧缓存
					if cache_key in self._cache:
						old_entry = self._cache[cache_key]
						for tag in old_entry.tags:
							if tag in self._tag_index:
								self._tag_index[tag].discard(cache_key)

					# 创建新条目
					expires_at = None
					if ttl is not None:
						expires_at = datetime.now() + timedelta(seconds=ttl)
					elif self.default_ttl is not None:
						expires_at = datetime.now() + timedelta(seconds=self.default_ttl)

					entry = CacheEntry(value=value, expires_at=expires_at)

					# 存储
					self._cache[cache_key] = entry
					self._cache.move_to_end(cache_key)

				# 检查是否需要驱逐
				while len(self._cache) > self.max_size:
					key = next(iter(self._cache))
					self._delete_unsafe(key)

			return True

		except Exception as e:
			raise CacheError(f"Failed to set multiple cache items: {str(e)}")

	async def delete_by_tags (self, tags: List[str]) -> int:
		"""根据标签删除缓存"""
		try:
			deleted_count = 0

			with self._lock:
				for tag in tags:
					if tag in self._tag_index:
						keys_to_delete = list(self._tag_index[tag])
						for key in keys_to_delete:
							if key in self._cache:
								self._delete_unsafe(key)
								deleted_count += 1

						del self._tag_index[tag]

			return deleted_count

		except Exception as e:
			raise CacheError(f"Failed to delete cache by tags: {str(e)}")

	async def delete_pattern (self, pattern: str) -> int:
		"""根据模式删除匹配的缓存键"""
		try:
			deleted_count = 0

			# 生成完整的模式（与RedisCache保持一致）
			full_pattern = f"{self.key_prefix}:{pattern}"

			with self._lock:
				# 查找匹配的键
				keys_to_delete = []
				for key in self._cache.keys():
					# 将pattern转换为fnmatch模式
					# 支持 * 和 ? 通配符
					if fnmatch.fnmatch(key, full_pattern):
						keys_to_delete.append(key)

				# 删除匹配的键
				for key in keys_to_delete:
					self._delete_unsafe(key)
					deleted_count += 1

			return deleted_count

		except Exception as e:
			raise CacheError(f"Failed to delete cache pattern {pattern}: {str(e)}")

	async def get_stats (self) -> Dict[str, Any]:
		"""获取缓存统计信息"""
		try:
			with self._lock:
				total_size = len(self._cache)

				# 计算过期缓存数量
				expired_count = 0
				now = datetime.now()
				for entry in self._cache.values():
					if entry.is_expired:
						expired_count += 1

				# 计算平均TTL
				total_ttl = 0
				valid_entries = 0
				for entry in self._cache.values():
					if not entry.is_expired and entry.ttl is not None:
						total_ttl += entry.ttl
						valid_entries += 1

				avg_ttl = total_ttl / valid_entries if valid_entries > 0 else 0

				stats = {
					"namespace": self.namespace,
					"total_size": total_size,
					"expired_count": expired_count,
					"tag_count": len(self._tag_index),
					"avg_ttl": avg_ttl,
					"max_size": self.max_size,
					"cleanup_interval": self.cleanup_interval,
					"is_alive": True,
				}

				return stats

		except Exception as e:
			return {
				"namespace": self.namespace,
				"error": str(e),
				"is_alive": False,
			}

	def stop_cleanup (self):
		"""停止清理线程"""
		self._stop_cleanup.set()
		if self._cleanup_thread:
			self._cleanup_thread.join(timeout=5)

	def __del__ (self):
		"""析构函数"""
		self.stop_cleanup()