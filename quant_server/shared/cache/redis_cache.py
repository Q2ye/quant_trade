"""
Redis缓存实现
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict

import redis.asyncio as redis

from .base import CacheBase, CacheEntry, CacheError
from .serializers import SerializerBase, PickleSerializer


class RedisCache(CacheBase):
	"""Redis缓存实现"""

	def __init__ (
			self,
			namespace: str = "default",
			default_ttl: Optional[int] = 3600,
			key_prefix: str = "",
			serializer: Optional[SerializerBase] = None,
			**redis_kwargs
	):
		super().__init__(namespace, default_ttl, key_prefix, serializer)
		self.redis_kwargs = redis_kwargs
		self._client: Optional[redis.Redis] = None
		self._connection_pool: Optional[redis.ConnectionPool] = None

		# 默认使用Pickle序列化器
		if serializer is None:
			self.serializer = PickleSerializer()

	@property
	def client (self) -> redis.Redis:
		"""获取Redis客户端"""
		if self._client is None:
			self._connect()
		return self._client

	def _connect (self):
		"""连接Redis"""
		if self._connection_pool is None:
			self._connection_pool = redis.ConnectionPool(**self.redis_kwargs)

		self._client = redis.Redis(
			connection_pool=self._connection_pool,
			decode_responses=False  # 不自动解码，由序列化器处理
		)

	async def _ensure_connected (self):
		"""确保已连接"""
		if self._client is None:
			self._connect()

		# 测试连接
		if self._client is not None:
			try:
				await self._client.ping()
			except redis.ConnectionError:
				self._connect()
				if self._client is not None:
					await self._client.ping()

	async def _serialize_value (self, value: Any) -> bytes:
		"""序列化值"""
		self._ensure_serializer()
		return self.serializer.serialize(value)

	async def _deserialize_value (self, data: bytes) -> Any:
		"""反序列化值"""
		self._ensure_serializer()
		return self.serializer.deserialize(data)

	async def _serialize_entry (self, entry: CacheEntry) -> bytes:
		"""序列化缓存条目"""
		entry_dict = entry.to_dict()
		# 序列化值
		entry_dict["value"] = await self._serialize_value(entry.value)
		return json.dumps(entry_dict).encode()

	async def _deserialize_entry (self, data: bytes) -> CacheEntry:
		"""反序列化缓存条目"""
		entry_dict = json.loads(data.decode())
		# 反序列化值
		entry_dict["value"] = await self._deserialize_value(entry_dict["value"])

		# 转换时间字段
		if entry_dict["created_at"]:
			entry_dict["created_at"] = datetime.fromisoformat(entry_dict["created_at"])
		if entry_dict["expires_at"]:
			entry_dict["expires_at"] = datetime.fromisoformat(entry_dict["expires_at"])

		return CacheEntry(**entry_dict)

	async def get (self, key: str, default: Any = None) -> Any:
		"""获取缓存值"""
		try:
			await self._ensure_connected()
			cache_key = self._make_key(key)

			# 获取缓存数据
			data = await self.client.get(cache_key)
			if data is None:
				return default

			# 反序列化缓存条目
			entry = await self._deserialize_entry(data)

			# 检查是否过期
			if entry.is_expired:
				await self.delete(key)
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
			await self._ensure_connected()
			cache_key = self._make_key(key)

			# 创建缓存条目
			expires_at = None
			if ttl is not None:
				expires_at = datetime.now() + timedelta(seconds=ttl)
			elif self.default_ttl is not None:
				expires_at = datetime.now() + timedelta(seconds=self.default_ttl)

			entry = CacheEntry(value=value, expires_at=expires_at, tags=tags)

			# 序列化并存储
			data = await self._serialize_entry(entry)

			# 计算过期时间（秒）
			expire_seconds = None
			if expires_at:
				expire_seconds = int((expires_at - datetime.now()).total_seconds())

			# 存储到Redis
			if expire_seconds and expire_seconds > 0:
				await self.client.setex(cache_key, expire_seconds, data)
			else:
				await self.client.set(cache_key, data)

			# 如果有关联标签，建立反向索引
			if tags:
				await self._add_key_to_tags(cache_key, tags)

			return True

		except Exception as e:
			raise CacheError(f"Failed to set cache key {key}: {str(e)}")

	async def delete (self, key: str) -> bool:
		"""删除缓存值"""
		try:
			await self._ensure_connected()
			cache_key = self._make_key(key)

			# 获取标签以便清理反向索引
			data = await self.client.get(cache_key)
			if data:
				try:
					entry = await self._deserialize_entry(data)
					if entry.tags:
						await self._remove_key_from_tags(cache_key, entry.tags)
				except (json.JSONDecodeError, redis.RedisError):
					pass

			# 删除缓存键
			result = await self.client.delete(cache_key)
			return result > 0

		except Exception as e:
			raise CacheError(f"Failed to delete cache key {key}: {str(e)}")

	async def exists (self, key: str) -> bool:
		"""检查键是否存在"""
		try:
			await self._ensure_connected()
			cache_key = self._make_key(key)
			return await self.client.exists(cache_key) > 0
		except Exception as e:
			raise CacheError(f"Failed to check existence of key {key}: {str(e)}")

	async def clear (self) -> bool:
		"""清除所有缓存"""
		try:
			await self._ensure_connected()
			pattern = f"{self.key_prefix}:*"
			keys = await self.client.keys(pattern)
			if keys:
				await self.client.delete(*keys)

			# 同时清理标签索引
			tag_pattern = f"_tags:{self.key_prefix}:*"
			tag_keys = await self.client.keys(tag_pattern)
			if tag_keys:
				await self.client.delete(*tag_keys)

			return True

		except Exception as e:
			raise CacheError(f"Failed to clear cache: {str(e)}")

	async def delete_pattern (self, pattern: str) -> int:
		"""根据模式删除匹配的缓存键"""
		try:
			await self._ensure_connected()

			# 生成完整的模式
			full_pattern = f"{self.key_prefix}:{pattern}"

			# 查找匹配的键
			keys = await self.client.keys(full_pattern)
			if not keys:
				return 0

			# 批量删除匹配的键
			count = len(keys)
			await self.client.delete(*keys)

			return count

		except Exception as e:
			raise CacheError(f"Failed to delete cache pattern {pattern}: {str(e)}")

	async def get_many (self, keys: List[str]) -> Dict[str, Any]:
		"""批量获取缓存值"""
		try:
			await self._ensure_connected()
			cache_keys = [self._make_key(key) for key in keys]

			# 批量获取
			values = await self.client.mget(cache_keys)

			result = {}
			for key, value in zip(keys, values):
				if value is None:
					result[key] = None
					continue

				try:
					entry = await self._deserialize_entry(value)
					if entry.is_expired:
						await self.delete(key)
						result[key] = None
					else:
						result[key] = entry.value
				except (json.JSONDecodeError, redis.RedisError):
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
			await self._ensure_connected()

			# 准备管道
			async with self.client.pipeline() as pipe:
				for key, value in items.items():
					cache_key = self._make_key(key)

					# 创建缓存条目
					expires_at = None
					if ttl is not None:
						expires_at = datetime.now() + timedelta(seconds=ttl)
					elif self.default_ttl is not None:
						expires_at = datetime.now() + timedelta(seconds=self.default_ttl)

					entry = CacheEntry(value=value, expires_at=expires_at)
					data = await self._serialize_entry(entry)

					# 计算过期时间
					expire_seconds = None
					if expires_at:
						expire_seconds = int((expires_at - datetime.now()).total_seconds())

					if expire_seconds and expire_seconds > 0:
						pipe.setex(cache_key, expire_seconds, data)
					else:
						pipe.set(cache_key, data)

				# 执行批量操作
				await pipe.execute()
				return True

		except Exception as e:
			raise CacheError(f"Failed to set multiple cache items: {str(e)}")

	async def _add_key_to_tags (self, cache_key: str, tags: List[str]):
		"""将键添加到标签索引"""
		try:
			for tag in tags:
				tag_key = f"_tags:{self.key_prefix}:{tag}"
				await self.client.sadd(tag_key, cache_key)
		except redis.RedisError:
			pass

	async def _remove_key_from_tags (self, cache_key: str, tags: List[str]):
		"""从标签索引中移除键"""
		try:
			for tag in tags:
				tag_key = f"_tags:{self.key_prefix}:{tag}"
				await self.client.srem(tag_key, cache_key)
		except redis.RedisError:
			pass

	async def delete_by_tags (self, tags: List[str]) -> int:
		"""根据标签删除缓存"""
		try:
			await self._ensure_connected()

			keys_to_delete = set()

			# 收集所有需要删除的键
			for tag in tags:
				tag_key = f"_tags:{self.key_prefix}:{tag}"
				tag_keys = await self.client.smembers(tag_key)
				keys_to_delete.update(tag_keys)

				# 删除标签索引
				await self.client.delete(tag_key)

			# 删除所有相关的缓存键
			if keys_to_delete:
				await self.client.delete(*keys_to_delete)
				return len(keys_to_delete)

			return 0

		except Exception as e:
			raise CacheError(f"Failed to delete cache by tags: {str(e)}")

	async def get_stats (self) -> Dict[str, Any]:
		"""获取缓存统计信息"""
		try:
			await self._ensure_connected()

			# 获取Redis信息
			info = await self.client.info()

			# 计算当前命名空间的键数量
			pattern = f"{self.key_prefix}:*"
			keys = await self.client.keys(pattern)

			stats = {
				"namespace": self.namespace,
				"key_count": len(keys),
				"redis_version": info.get("redis_version", "unknown"),
				"used_memory": info.get("used_memory_human", "unknown"),
				"connected_clients": info.get("connected_clients", 0),
				"uptime": info.get("uptime_in_seconds", 0),
				"is_alive": True,
			}

			return stats

		except Exception as e:
			return {
				"namespace": self.namespace,
				"error": str(e),
				"is_alive": False,
			}

	async def close (self):
		"""关闭连接"""
		try:
			if self._client is not None:
				await self._client.close()
				self._client = None
			if self._connection_pool is not None:
				await self._connection_pool.disconnect()
				self._connection_pool = None
		except (redis.RedisError, Exception):
			pass

	async def flush_all (self):
		"""清空整个Redis数据库"""
		try:
			await self._ensure_connected()
			await self.client.flushall()
			return True
		except redis.RedisError as e:
			raise CacheError(f"Failed to flush Redis: {str(e)}")