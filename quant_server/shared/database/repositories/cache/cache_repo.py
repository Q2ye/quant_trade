# -*- coding: utf-8 -*-
"""
缓存数据仓库（二级缓存）
位置：quant_server/shared/database/repositories/cache_repo.py
职责：管理缓存数据，提供二级缓存功能
注意：这里实现的是数据库级别的缓存，用于持久化缓存数据
     内存缓存应使用Redis等外部缓存系统
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CacheEntry:
	"""缓存条目实体类"""

	def __init__ (self, key: str, value: Any, ttl: int = 3600, tags: List[str] = None):
		"""
		初始化缓存条目

		Args:
			key: 缓存键
			value: 缓存值
			ttl: 存活时间（秒）
			tags: 标签列表
		"""
		self.key = key
		self.value = value
		self.created_at = datetime.now()
		self.expires_at = self.created_at + timedelta(seconds=ttl)
		self.tags = tags or []
		self.hit_count = 0
		self.last_accessed = self.created_at

	def is_expired (self) -> bool:
		"""检查是否过期"""
		return datetime.now() > self.expires_at

	def touch (self):
		"""更新访问时间"""
		self.last_accessed = datetime.now()
		self.hit_count += 1


class CacheRepository:
	"""缓存数据仓库 - 负责缓存数据的管理和访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		# 内存缓存（一级缓存）
		self._memory_cache: Dict[str, CacheEntry] = {}
		self._tag_index: Dict[str, List[str]] = {}

	# ==================== 内存缓存操作（一级缓存） ====================

	async def memory_get (self, key: str) -> Optional[Any]:
		"""
		从内存缓存获取数据

		Args:
			key: 缓存键

		Returns:
			缓存值或None
		"""
		if key not in self._memory_cache:
			return None

		entry = self._memory_cache[key]

		# 检查是否过期
		if entry.is_expired():
			del self._memory_cache[key]
			# 清理标签索引
			for tag in entry.tags:
				if tag in self._tag_index and key in self._tag_index[tag]:
					self._tag_index[tag].remove(key)
			return None

		# 更新访问统计
		entry.touch()
		return entry.value

	async def memory_set (
			self,
			key: str,
			value: Any,
			ttl: int = 3600,
			tags: List[str] = None
	) -> bool:
		"""
		设置内存缓存

		Args:
			key: 缓存键
			value: 缓存值
			ttl: 存活时间（秒）
			tags: 标签列表

		Returns:
			是否成功
		"""
		entry = CacheEntry(key, value, ttl, tags)
		self._memory_cache[key] = entry

		# 更新标签索引
		if tags:
			for tag in tags:
				if tag not in self._tag_index:
					self._tag_index[tag] = []
				if key not in self._tag_index[tag]:
					self._tag_index[tag].append(key)

		return True

	async def memory_delete (self, key: str) -> bool:
		"""
		删除内存缓存

		Args:
			key: 缓存键

		Returns:
			是否成功
		"""
		if key in self._memory_cache:
			entry = self._memory_cache[key]
			# 清理标签索引
			for tag in entry.tags:
				if tag in self._tag_index and key in self._tag_index[tag]:
					self._tag_index[tag].remove(key)
			del self._memory_cache[key]
			return True
		return False

	async def memory_delete_by_tag (self, tag: str) -> int:
		"""
		根据标签删除内存缓存

		Args:
			tag: 标签

		Returns:
			删除的缓存项数量
		"""
		if tag not in self._tag_index:
			return 0

		deleted_count = 0
		for key in self._tag_index[tag]:
			if key in self._memory_cache:
				del self._memory_cache[key]
				deleted_count += 1

		del self._tag_index[tag]
		return deleted_count

	async def memory_clear (self) -> int:
		"""
		清空内存缓存

		Returns:
			清理的缓存项数量
		"""
		count = len(self._memory_cache)
		self._memory_cache.clear()
		self._tag_index.clear()
		return count

	async def memory_stats (self) -> Dict[str, Any]:
		"""
		获取内存缓存统计信息

		Returns:
			统计信息字典
		"""
		total_size = len(self._memory_cache)
		total_hits = sum(entry.hit_count for entry in self._memory_cache.values())

		# 按标签统计
		tag_stats = {}
		for tag, keys in self._tag_index.items():
			tag_stats[tag] = len(keys)

		# 按TTL分布
		ttl_distribution = {
			"under_1min": 0,
			"1min_10min": 0,
			"10min_1hour": 0,
			"1hour_1day": 0,
			"over_1day": 0
		}

		for entry in self._memory_cache.values():
			ttl_seconds = (entry.expires_at - entry.created_at).total_seconds()
			if ttl_seconds < 60:
				ttl_distribution["under_1min"] += 1
			elif ttl_seconds < 600:
				ttl_distribution["1min_10min"] += 1
			elif ttl_seconds < 3600:
				ttl_distribution["10min_1hour"] += 1
			elif ttl_seconds < 86400:
				ttl_distribution["1hour_1day"] += 1
			else:
				ttl_distribution["over_1day"] += 1

		return {
			"total_entries": total_size,
			"total_hits": total_hits,
			"memory_usage_bytes": self._estimate_memory_usage(),
			"tag_statistics": tag_stats,
			"ttl_distribution": ttl_distribution
		}

	def _estimate_memory_usage (self) -> int:
		"""估算内存使用量"""
		import sys
		total_size = 0
		for key, entry in self._memory_cache.items():
			total_size += sys.getsizeof(key)
			total_size += sys.getsizeof(entry)
			total_size += sys.getsizeof(entry.value)
		return total_size

	# ==================== 数据库缓存操作（二级缓存） ====================

	async def db_get (self, cache_key: str) -> Optional[Dict[str, Any]]:
		"""
		从数据库缓存获取数据

		Args:
			cache_key: 缓存键

		Returns:
			缓存数据或None
		"""
		# 这里假设有一个数据库缓存表，根据实际情况调整
		query = text("""
                     SELECT value, expires_at, hit_count
                     FROM cache_store
                     WHERE key = :key
                       AND (expires_at IS NULL OR expires_at > NOW())
		             """)

		result = await self.session.execute(query, {"key": cache_key})
		row = result.fetchone()

		if row:
			# 更新命中计数
			update_query = text("""
                                UPDATE cache_store
                                SET hit_count     = hit_count + 1,
                                    last_accessed = NOW()
                                WHERE key = :key
			                    """)
			await self.session.execute(update_query, {"key": cache_key})

			return {
				"value": row.value,
				"expires_at": row.expires_at,
				"hit_count": row.hit_count
			}

		return None

	async def db_set (
			self,
			cache_key: str,
			value: Any,
			ttl: int = 3600,
			tags: List[str] = None
	) -> bool:
		"""
		设置数据库缓存

		Args:
			cache_key: 缓存键
			value: 缓存值（需要可序列化）
			ttl: 存活时间（秒）
			tags: 标签列表

		Returns:
			是否成功
		"""
		import json
		from datetime import datetime, timedelta

		expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
		tags_json = json.dumps(tags) if tags else None

		# 使用upsert模式
		upsert_query = text("""
                            INSERT INTO cache_store (key, value, expires_at, tags, created_at, hit_count)
                            VALUES (:key, :value, :expires_at, :tags, NOW(), 0)
                            ON CONFLICT (key)
                                DO UPDATE SET value      = EXCLUDED.value,
                                              expires_at = EXCLUDED.expires_at,
                                              tags       = EXCLUDED.tags,
                                              updated_at = NOW(),
                                              hit_count  = cache_store.hit_count
		                    """)

		await self.session.execute(
			upsert_query,
			{
				"key": cache_key,
				"value": json.dumps(value),
				"expires_at": expires_at,
				"tags": tags_json
			}
		)

		return True

	async def db_delete (self, cache_key: str) -> bool:
		"""
		删除数据库缓存

		Args:
			cache_key: 缓存键

		Returns:
			是否成功
		"""
		delete_query = text("DELETE FROM cache_store WHERE key = :key")
		result = await self.session.execute(delete_query, {"key": cache_key})
		return result.rowcount > 0

	async def db_clear_expired (self) -> int:
		"""
		清理过期缓存

		Returns:
			清理的缓存项数量
		"""
		clear_query = text("DELETE FROM cache_store WHERE expires_at <= NOW()")
		result = await self.session.execute(clear_query)
		return result.rowcount

	async def db_clear_by_pattern (self, pattern: str) -> int:
		"""
		根据模式清理缓存

		Args:
			pattern: SQL LIKE模式

		Returns:
			清理的缓存项数量
		"""
		clear_query = text("DELETE FROM cache_store WHERE key LIKE :pattern")
		result = await self.session.execute(clear_query, {"pattern": f"%{pattern}%"})
		return result.rowcount

	async def db_get_stats (self) -> Dict[str, Any]:
		"""
		获取数据库缓存统计信息

		Returns:
			统计信息字典
		"""
		stats_query = text("""
                           SELECT COUNT(*)                                            as total_count,
                                  SUM(CASE WHEN expires_at > NOW() THEN 1 ELSE 0 END) as active_count,
                                  SUM(hit_count)                                      as total_hits,
                                  AVG(hit_count)                                      as avg_hits,
                                  MIN(created_at)                                     as oldest_entry,
                                  MAX(last_accessed)                                  as last_accessed
                           FROM cache_store
		                   """)

		result = await self.session.execute(stats_query)
		row = result.fetchone()

		if row:
			return {
				"total_entries": row.total_count or 0,
				"active_entries": row.active_count or 0,
				"total_hits": row.total_hits or 0,
				"average_hits": float(row.avg_hits or 0),
				"oldest_entry": row.oldest_entry,
				"last_accessed": row.last_accessed
			}

		return {}

	# ==================== 混合缓存操作 ====================

	async def get (
			self,
			key: str,
			use_memory: bool = True,
			use_db: bool = False
	) -> Optional[Any]:
		"""
		获取缓存数据（支持多级缓存）

		Args:
			key: 缓存键
			use_memory: 是否使用内存缓存
			use_db: 是否使用数据库缓存

		Returns:
			缓存值或None
		"""
		# 首先尝试内存缓存
		if use_memory:
			value = await self.memory_get(key)
			if value is not None:
				return value

		# 然后尝试数据库缓存
		if use_db:
			cached_data = await self.db_get(key)
			if cached_data:
				# 将数据库缓存加载到内存缓存
				if use_memory:
					await self.memory_set(key, cached_data["value"])
				return cached_data["value"]

		return None

	async def set (
			self,
			key: str,
			value: Any,
			ttl: int = 3600,
			tags: List[str] = None,
			use_memory: bool = True,
			use_db: bool = False
	) -> bool:
		"""
		设置缓存数据（支持多级缓存）

		Args:
			key: 缓存键
			value: 缓存值
			ttl: 存活时间（秒）
			tags: 标签列表
			use_memory: 是否设置内存缓存
			use_db: 是否设置数据库缓存

		Returns:
			是否成功
		"""
		success = True

		if use_memory:
			success = success and await self.memory_set(key, value, ttl, tags)

		if use_db:
			success = success and await self.db_set(key, value, ttl, tags)

		return success

	async def delete (
			self,
			key: str,
			use_memory: bool = True,
			use_db: bool = False
	) -> bool:
		"""
		删除缓存数据

		Args:
			key: 缓存键
			use_memory: 是否删除内存缓存
			use_db: 是否删除数据库缓存

		Returns:
			是否成功
		"""
		success = True

		if use_memory:
			success = success and await self.memory_delete(key)

		if use_db:
			success = success and await self.db_delete(key)

		return success

	async def clear_all (self) -> Dict[str, int]:
		"""
		清空所有缓存

		Returns:
			各层缓存清理数量
		"""
		memory_count = await self.memory_clear()
		db_count = await self.db_clear_expired()

		return {
			"memory_cleared": memory_count,
			"db_cleared": db_count
		}
