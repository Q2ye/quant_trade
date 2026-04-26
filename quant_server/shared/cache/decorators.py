"""
缓存装饰器模块
提供函数结果缓存和属性缓存装饰器
"""

import asyncio
import functools
import hashlib
import inspect
import json
from typing import Callable, Optional, List

from .base import CacheError
from .cache_manager import get_cache_manager


def _make_cache_key (
		func: Callable,
		args: tuple,
		kwargs: dict,
		prefix: str = "",
		key_func: Optional[Callable] = None
) -> str:
	"""生成缓存键"""
	if key_func is not None:
		return key_func(*args, **kwargs)

	# 获取函数信息
	func_name = func.__name__
	module_name = getattr(func, '__module__', 'unknown')

	# 序列化参数
	try:
		args_str = json.dumps(args, default=str, sort_keys=True)
		kwargs_str = json.dumps(kwargs, default=str, sort_keys=True)
	except TypeError:
		# 如果不能序列化，使用repr
		args_str = repr(args)
		kwargs_str = repr(kwargs)

	# 创建键字符串
	key_parts = [
		prefix,
		module_name,
		func_name,
		args_str,
		kwargs_str
	]
	key_str = ":".join(str(part) for part in key_parts if part)

	# 如果键过长，使用哈希
	if len(key_str) > 200:
		key_str = hashlib.md5(key_str.encode()).hexdigest()

	return key_str


def cache_result (
		cache_name: Optional[str] = None,
		ttl: Optional[int] = None,
		key_prefix: str = "cache",
		key_func: Optional[Callable] = None,
		tags: Optional[List[str]] = None,
		condition: Optional[Callable] = None,
		cache_errors: bool = False,
		cache_none: bool = True
):
	"""
	缓存函数结果的装饰器

	Args:
		cache_name: 缓存名称，如果为None则使用默认缓存
		ttl: 缓存生存时间（秒）
		key_prefix: 缓存键前缀
		key_func: 自定义缓存键生成函数
		tags: 缓存标签
		condition: 缓存条件函数，返回True时才缓存
		cache_errors: 是否缓存异常结果
		cache_none: 是否缓存None结果
	"""

	def decorator (func):
		if inspect.iscoroutinefunction(func):
			@functools.wraps(func)
			async def async_wrapper (*args, **kwargs):
				# 获取缓存管理器
				cache_manager = get_cache_manager()

				# 生成缓存键
				cache_key = _make_cache_key(func, args, kwargs, key_prefix, key_func)

				# 尝试从缓存获取
				try:
					cached_value = await cache_manager.get(cache_key, cache_name)
					if cached_value is not None:
						return cached_value
				except CacheError:
					# 缓存获取失败，直接执行函数
					pass

				# 执行函数
				try:
					result = await func(*args, **kwargs)

					# 检查是否应该缓存
					should_cache = True
					if condition is not None:
						should_cache = condition(result, *args, **kwargs)

					if not cache_none and result is None:
						should_cache = False

					# 缓存结果
					if should_cache:
						try:
							await cache_manager.set(
								cache_key,
								result,
								cache_name,
								ttl,
								tags
							)
						except CacheError:
							# 缓存设置失败，忽略错误
							pass

					return result

				except Exception as e:
					if cache_errors:
						try:
							await cache_manager.set(
								cache_key,
								{"__error__": str(e)},
								cache_name,
								ttl,
								tags
							)
						except CacheError:
							pass
					raise

			return async_wrapper

		else:
			@functools.wraps(func)
			def sync_wrapper (*args, **kwargs):
				# 获取缓存管理器
				cache_manager = get_cache_manager()

				# 生成缓存键
				cache_key = _make_cache_key(func, args, kwargs, key_prefix, key_func)

				# 尝试从缓存获取
				try:
					# 同步函数中异步获取缓存（需要运行事件循环）
					try:
						loop = asyncio.get_event_loop()
					except RuntimeError:
						loop = asyncio.new_event_loop()
						asyncio.set_event_loop(loop)

					cached_value = loop.run_until_complete(
						cache_manager.get(cache_key, cache_name)
					)
					if cached_value is not None:
						return cached_value
				except CacheError:
					# 缓存获取失败，直接执行函数
					pass

				# 执行函数
				try:
					result = func(*args, **kwargs)

					# 检查是否应该缓存
					should_cache = True
					if condition is not None:
						should_cache = condition(result, *args, **kwargs)

					if not cache_none and result is None:
						should_cache = False

					# 缓存结果
					if should_cache:
						try:
							loop = asyncio.get_event_loop()
							loop.run_until_complete(
								cache_manager.set(
									cache_key,
									result,
									cache_name,
									ttl,
									tags
								)
							)
						except (CacheError, RuntimeError):
							# 缓存设置失败，忽略错误
							pass

					return result

				except Exception as e:
					if cache_errors:
						try:
							loop = asyncio.get_event_loop()
							loop.run_until_complete(
								cache_manager.set(
									cache_key,
									{"__error__": str(e)},
									cache_name,
									ttl,
									tags
								)
							)
						except (CacheError, RuntimeError):
							pass
					raise

			return sync_wrapper

	return decorator


def cached_property (
		cache_name: Optional[str] = None,
		ttl: Optional[int] = None,
		key_prefix: str = "property"
):
	"""
	缓存属性装饰器

	Args:
		cache_name: 缓存名称
		ttl: 缓存生存时间（秒）
		key_prefix: 缓存键前缀
	"""

	class CachedProperty:
		def __init__ (self, func):
			self.func = func
			self.__doc__ = func.__doc__
			self.name = func.__name__

		def __get__ (self, obj, objtype=None):
			if obj is None:
				return self

			# 生成缓存键
			cache_key = f"{key_prefix}:{obj.__class__.__name__}:{self.name}:{id(obj)}"

			# 获取缓存管理器
			cache_manager = get_cache_manager()

			# 尝试从缓存获取
			try:
				loop = asyncio.get_event_loop()
			except RuntimeError:
				loop = asyncio.new_event_loop()
				asyncio.set_event_loop(loop)

			try:
				cached_value = loop.run_until_complete(
					cache_manager.get(cache_key, cache_name)
				)
				if cached_value is not None:
					return cached_value
			except CacheError:
				# 缓存获取失败，直接计算
				pass

			# 计算属性值
			value = self.func(obj)

			# 缓存结果
			try:
				loop.run_until_complete(
					cache_manager.set(cache_key, value, cache_name, ttl)
				)
			except (CacheError, RuntimeError):
				# 缓存设置失败，忽略错误
				pass

			return value

		async def clear_cache (self, obj):
			"""清除属性缓存"""
			cache_key = f"{key_prefix}:{obj.__class__.__name__}:{self.name}:{id(obj)}"
			cache_manager = get_cache_manager()
			await cache_manager.delete(cache_key, cache_name)

	return CachedProperty


def invalidate_cache (
		cache_name: Optional[str] = None,
		key_prefix: str = "cache",
		key_func: Optional[Callable] = None
):
	"""
	使缓存失效的装饰器

	用于装饰会修改数据的函数，调用后使相关缓存失效
	"""

	def decorator (func):
		if inspect.iscoroutinefunction(func):
			@functools.wraps(func)
			async def async_wrapper (*args, **kwargs):
				# 先执行函数
				result = await func(*args, **kwargs)

				# 生成缓存键并删除
				cache_manager = get_cache_manager()
				cache_key = _make_cache_key(func, args, kwargs, key_prefix, key_func)

				try:
					await cache_manager.delete(cache_key, cache_name)
				except CacheError:
					pass

				return result

			return async_wrapper

		else:
			@functools.wraps(func)
			def sync_wrapper (*args, **kwargs):
				# 先执行函数
				result = func(*args, **kwargs)

				# 生成缓存键并删除
				cache_manager = get_cache_manager()
				cache_key = _make_cache_key(func, args, kwargs, key_prefix, key_func)

				try:
					loop = asyncio.get_event_loop()
					loop.run_until_complete(
						cache_manager.delete(cache_key, cache_name)
					)
				except (CacheError, RuntimeError):
					pass

				return result

			return sync_wrapper

	return decorator


def cache_by_tags (tags: List[str], cache_name: Optional[str] = None):
	"""
	根据标签管理缓存的装饰器

	可以用于批量删除具有特定标签的缓存
	"""

	def decorator (func):
		@functools.wraps(func)
		async def async_wrapper (*args, **kwargs):
			# 获取缓存管理器
			cache_manager = get_cache_manager()

			# 执行函数
			result = await func(*args, **kwargs)

			# 删除具有指定标签的缓存
			try:
				cache = cache_manager.get_cache(cache_name)
				await cache.delete_by_tags(tags)
			except CacheError:
				pass

			return result

		@functools.wraps(func)
		def sync_wrapper (*args, **kwargs):
			# 获取缓存管理器
			cache_manager = get_cache_manager()

			# 执行函数
			result = func(*args, **kwargs)

			# 删除具有指定标签的缓存
			try:
				loop = asyncio.get_event_loop()
				cache = cache_manager.get_cache(cache_name)
				loop.run_until_complete(cache.delete_by_tags(tags))
			except (CacheError, RuntimeError):
				pass

			return result

		if inspect.iscoroutinefunction(func):
			return async_wrapper
		else:
			return sync_wrapper

	return decorator