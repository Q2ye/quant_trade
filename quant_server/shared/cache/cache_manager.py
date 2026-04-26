"""
缓存管理器
支持多级缓存和统一的缓存管理
"""

from typing import Any, Optional, List, Dict, Callable

from .base import CacheBase, CacheError
from .memory_cache import MemoryCache
from .redis_cache import RedisCache


class CacheManager:
	"""缓存管理器"""

	def __init__ (self, config: Optional[Dict[str, Any]] = None):
		self.config = config or {}
		self._caches: Dict[str, CacheBase] = {}
		self._default_cache: Optional[str] = None
		self._multi_level_caches: Dict[str, Dict[str, Any]] = {}

	def register_cache (
			self,
			name: str,
			cache: CacheBase,
			is_default: bool = False
	):
		"""注册缓存"""
		self._caches[name] = cache

		if is_default or self._default_cache is None:
			self._default_cache = name

	def create_redis_cache (
			self,
			name: str = "redis",
			is_default: bool = True,
			**kwargs
	) -> RedisCache:
		"""创建Redis缓存"""
		redis_config = self.config.get("redis", {})
		redis_config.update(kwargs)

		cache = RedisCache(**redis_config)
		self.register_cache(name, cache, is_default)
		return cache

	def create_memory_cache (
			self,
			name: str = "memory",
			is_default: bool = False,
			**kwargs
	) -> MemoryCache:
		"""创建内存缓存"""
		memory_config = self.config.get("memory", {})
		memory_config.update(kwargs)

		cache = MemoryCache(**memory_config)
		self.register_cache(name, cache, is_default)
		return cache

	def create_multi_level_cache (
			self,
			name: str,
			levels: List[str],
			read_through: bool = True
	):
		"""创建多级缓存"""
		if not levels:
			raise CacheError("Multi-level cache requires at least one level")

		for level in levels:
			if level not in self._caches:
				raise CacheError(f"Cache level '{level}' is not registered")

		self._multi_level_caches[name] = {
			"levels": levels,
			"read_through": read_through
		}

	def get_cache (self, name: Optional[str] = None) -> CacheBase:
		"""获取缓存实例"""
		if name is None:
			name = self._default_cache

		if name is None:
			raise CacheError("No default cache configured")

		if name not in self._caches:
			raise CacheError(f"Cache '{name}' is not registered")

		return self._caches[name]

	async def get (
			self,
			key: str,
			cache_name: Optional[str] = None,
			default: Any = None
	) -> Any:
		"""从缓存获取值"""
		cache = self.get_cache(cache_name)
		return await cache.get(key, default)

	async def set (
			self,
			key: str,
			value: Any,
			cache_name: Optional[str] = None,
			ttl: Optional[int] = None,
			tags: Optional[List[str]] = None
	):
		"""设置缓存值"""
		cache = self.get_cache(cache_name)
		await cache.set(key, value, ttl, tags)

	async def get_multi_level (
			self,
			key: str,
			cache_name: str,
			loader: Optional[Callable] = None,
			ttl: Optional[int] = None
		) -> Any:
		"""从多级缓存获取值"""
		if cache_name not in self._multi_level_caches:
			raise CacheError(f"Multi-level cache '{cache_name}' is not configured")

		config: Dict[str, Any] = self._multi_level_caches[cache_name]
		levels: List[str] = config["levels"]
		read_through: bool = config["read_through"]

		# 逐级查找
		for level_name in levels:
			level_cache = self._caches[level_name]
			value = await level_cache.get(key)

			if value is not None:
				# 更新更高级别的缓存（缓存穿透）
				for higher_level in levels[:levels.index(level_name)]:
					higher_cache = self._caches[higher_level]
					await higher_cache.set(key, value, ttl)
				return value

		# 所有缓存都未命中
		if loader is not None and read_through:
			# 读穿透：从数据源加载
			value = loader()

			# 设置所有级别的缓存
			for level_name in levels:
				level_cache = self._caches[level_name]
				await level_cache.set(key, value, ttl)

			return value

		return None

	async def set_multi_level (
			self,
			key: str,
			value: Any,
			cache_name: str,
			ttl: Optional[int] = None,
			tags: Optional[List[str]] = None
		):
		"""设置多级缓存值"""
		if cache_name not in self._multi_level_caches:
			raise CacheError(f"Multi-level cache '{cache_name}' is not configured")

		levels: List[str] = self._multi_level_caches[cache_name]["levels"]

		# 设置所有级别的缓存
		for level_name in levels:
			level_cache = self._caches[level_name]
			await level_cache.set(key, value, ttl, tags)

	async def delete (
			self,
			key: str,
			cache_name: Optional[str] = None
	) -> bool:
		"""删除缓存值"""
		cache = self.get_cache(cache_name)
		return await cache.delete(key)

	async def delete_multi_level (
			self,
			key: str,
			cache_name: str
		) -> bool:
		"""删除多级缓存值"""
		if cache_name not in self._multi_level_caches:
			raise CacheError(f"Multi-level cache '{cache_name}' is not configured")

		levels: List[str] = self._multi_level_caches[cache_name]["levels"]
		results = []

		for level_name in levels:
			level_cache = self._caches[level_name]
			result = await level_cache.delete(key)
			results.append(result)

		return any(results)

	async def clear_all (self):
		"""清除所有缓存"""
		for cache in self._caches.values():
			await cache.clear()

	async def get_all_stats (self) -> Dict[str, Any]:
		"""获取所有缓存的统计信息"""
		stats = {}

		for name, cache in self._caches.items():
			try:
				cache_stats = await cache.get_stats()
				stats[name] = cache_stats
			except Exception as e:
				stats[name] = {"error": str(e)}

		return stats

	async def health_check (self) -> Dict[str, bool]:
		"""健康检查"""
		results = {}

		for name, cache in self._caches.items():
			try:
				is_alive = await cache.ping()
				results[name] = is_alive
			except (CacheError, Exception):
				results[name] = False

		return results

	async def close_all (self):
		"""关闭所有缓存连接"""
		for cache in self._caches.values():
			if hasattr(cache, 'close'):
				await cache.close()


# 全局缓存管理器实例
_cache_manager: Optional[CacheManager] = None


def get_cache_manager () -> CacheManager:
	"""获取全局缓存管理器"""
	global _cache_manager
	if _cache_manager is None:
		_cache_manager = CacheManager()
	return _cache_manager


def init_cache_manager (config: Dict[str, Any]) -> CacheManager:
	"""初始化全局缓存管理器"""
	global _cache_manager
	_cache_manager = CacheManager(config)
	return _cache_manager