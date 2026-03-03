"""
缓存管理模块

提供统一的缓存接口，支持内存缓存和Redis缓存两种实现，
支持多种序列化方式，并提供缓存装饰器。
"""

from .base import CacheBase, CacheError, CacheKeyError
from .redis_cache import RedisCache
from .memory_cache import MemoryCache
from .cache_manager import CacheManager
from .serializers import (
	SerializerBase,
	PickleSerializer,
	JSONSerializer,
	MsgPackSerializer,
	CompressedSerializer
)
from .decorators import cache_result, cached_property

__all__ = [
	# 缓存基类和异常
	"CacheBase",
	"CacheError",
	"CacheKeyError",

	# 具体实现
	"RedisCache",
	"MemoryCache",
	"CacheManager",

	# 序列化器
	"SerializerBase",
	"PickleSerializer",
	"JSONSerializer",
	"MsgPackSerializer",
	"CompressedSerializer",

	# 装饰器
	"cache_result",
	"cached_property",
]