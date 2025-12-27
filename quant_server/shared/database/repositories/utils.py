# -*- coding: utf-8 -*-
"""
数据库工具函数
位置：shared/database/repositories/utils.py
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union, Type, TypeVar
from datetime import date, datetime, timedelta
from decimal import Decimal
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, insert, update, delete, func, and_, or_, not_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Result
from sqlalchemy.sql.selectable import Select

from .types import PaginationParams, PaginationResult, RepositoryResult

T = TypeVar('T')
logger = logging.getLogger(__name__)


# ==================== 数据库会话管理 ====================

@asynccontextmanager
async def get_db_session (
		session_maker: async_sessionmaker[AsyncSession]
):
	"""获取数据库会话的上下文管理器"""
	session = session_maker()
	try:
		yield session
		await session.commit()
	except Exception as e:
		await session.rollback()
		raise e
	finally:
		await session.close()


async def execute_with_session (
		session_maker: async_sessionmaker[AsyncSession],
		func,
		*args,
		**kwargs
) -> Any:
	"""在数据库会话中执行函数"""
	async with get_db_session(session_maker) as session:
		return await func(session, *args, **kwargs)


# ==================== 查询构建工具 ====================

def build_select_query (
		model: Type[T],
		filters: Optional[List[Any]] = None,
		order_by: Optional[Any] = None,
		limit: Optional[int] = None,
		offset: Optional[int] = None,
		distinct_on: Optional[Any] = None
) -> Select:
	"""构建SELECT查询"""
	query = select(model)

	if distinct_on:
		query = query.distinct(distinct_on)

	if filters:
		query = query.where(and_(*filters))

	if order_by:
		query = query.order_by(order_by)

	if offset is not None:
		query = query.offset(offset)

	if limit is not None:
		query = query.limit(limit)

	return query


def build_count_query (
		model: Type[T],
		filters: Optional[List[Any]] = None,
		distinct_column: Optional[Any] = None
) -> Select:
	"""构建COUNT查询"""
	if distinct_column:
		query = select(func.count(distinct_column))
	else:
		query = select(func.count()).select_from(model)

	if filters:
		query = query.where(and_(*filters))

	return query


def build_exists_query (
		model: Type[T],
		filters: Optional[List[Any]] = None
) -> Select:
	"""构建EXISTS查询"""
	query = select(1).select_from(model)

	if filters:
		query = query.where(and_(*filters))

	return query.limit(1)


def build_pagination_query (
		query: Select,
		pagination: PaginationParams
) -> Select:
	"""为查询添加分页"""
	if pagination.order_by:
		# 这里需要根据字段名动态获取列
		# 实际使用中需要根据具体模型调整
		pass

	return query.offset(
		pagination.get_offset()
	).limit(
		pagination.get_limit()
	)


# ==================== 结果处理工具 ====================

async def execute_query (
		session: AsyncSession,
		query: Select
) -> Result:
	"""执行查询并返回结果"""
	try:
		return await session.execute(query)
	except SQLAlchemyError as e:
		logger.error(f"查询执行失败: {e}")
		raise


async def fetch_one (
		session: AsyncSession,
		query: Select
) -> Optional[Any]:
	"""获取单条记录"""
	result = await execute_query(session, query)
	return result.scalar_one_or_none()


async def fetch_all (
		session: AsyncSession,
		query: Select
) -> List[Any]:
	"""获取所有记录"""
	result = await execute_query(session, query)
	return result.scalars().all()


async def fetch_paginated (
		session: AsyncSession,
		query: Select,
		count_query: Select,
		pagination: PaginationParams
) -> PaginationResult[Any]:
	"""获取分页结果"""
	# 获取总数
	count_result = await execute_query(session, count_query)
	total = count_result.scalar() or 0

	# 获取分页数据
	paginated_query = build_pagination_query(query, pagination)
	items_result = await execute_query(session, paginated_query)
	items = items_result.scalars().all()

	return PaginationResult.create(
		items=items,
		total=total,
		page=pagination.page,
		page_size=pagination.page_size
	)


async def fetch_dict (
		session: AsyncSession,
		query: Select
) -> List[Dict[str, Any]]:
	"""获取字典格式的结果"""
	result = await execute_query(session, query)
	rows = result.all()

	return [
		{key: value for key, value in row._mapping.items()}
		for row in rows
	]


async def fetch_scalar (
		session: AsyncSession,
		query: Select
) -> Optional[Any]:
	"""获取标量值"""
	result = await execute_query(session, query)
	return result.scalar()


# ==================== 批量操作工具 ====================

async def batch_insert (
		session: AsyncSession,
		model: Type[T],
		data_list: List[Dict[str, Any]],
		return_ids: bool = False
) -> Union[List[T], List[int]]:
	"""批量插入数据"""
	if not data_list:
		return []

	try:
		# 使用bulk_insert_mappings提高性能
		await session.execute(
			insert(model),
			data_list
		)
		await session.flush()

		if return_ids:
			# 获取插入的ID（需要数据库支持RETURNING）
			# 这里只是一个示例，实际实现需要根据数据库调整
			pass

		# 重新查询插入的数据
		# 这里只是一个简单实现，实际可能需要更复杂的逻辑
		return []

	except SQLAlchemyError as e:
		logger.error(f"批量插入失败: {e}")
		await session.rollback()
		raise


async def batch_update (
		session: AsyncSession,
		model: Type[T],
		data_list: List[Dict[str, Any]],
		match_fields: List[str]
) -> List[T]:
	"""批量更新数据"""
	if not data_list:
		return []

	updated_items = []

	for data in data_list:
		# 构建过滤条件
		filters = []
		for field in match_fields:
			if field in data:
				filters.append(getattr(model, field) == data[field])

		if not filters:
			continue

		# 执行更新
		update_data = {k: v for k, v in data.items() if k not in match_fields}

		if update_data:
			stmt = update(model).where(and_(*filters)).values(**update_data)
			await session.execute(stmt)

	await session.flush()
	return updated_items


async def batch_upsert (
		session: AsyncSession,
		model: Type[T],
		data_list: List[Dict[str, Any]],
		match_fields: List[str],
		update_excluded: Optional[List[str]] = None
) -> List[T]:
	"""批量插入或更新数据"""
	if not data_list:
		return []

	upserted_items = []

	for data in data_list:
		# 构建过滤条件
		filters = []
		for field in match_fields:
			if field in data:
				filters.append(getattr(model, field) == data[field])

		if not filters:
			continue

		# 检查是否已存在
		exists_query = build_exists_query(model, filters)
		exists = await fetch_scalar(session, exists_query)

		if exists:
			# 更新现有记录
			update_data = {k: v for k, v in data.items() if k not in match_fields}

			if update_excluded:
				for field in update_excluded:
					update_data.pop(field, None)

			if update_data:
				stmt = update(model).where(and_(*filters)).values(**update_data)
				await session.execute(stmt)
		else:
			# 插入新记录
			stmt = insert(model).values(**data)
			await session.execute(stmt)

	await session.flush()
	return upserted_items


async def batch_delete (
		session: AsyncSession,
		model: Type[T],
		filters: List[Any],
		soft_delete: bool = True,
		soft_delete_field: str = 'is_deleted'
) -> int:
	"""批量删除数据"""
	if soft_delete and hasattr(model, soft_delete_field):
		# 软删除
		stmt = update(model).where(and_(*filters)).values(
			**{soft_delete_field: 1}
		)
	else:
		# 硬删除
		stmt = delete(model).where(and_(*filters))

	result = await session.execute(stmt)
	await session.flush()

	return result.rowcount or 0


# ==================== 数据转换工具 ====================

def model_to_dict (
		instance: Any,
		exclude: Optional[List[str]] = None,
		include: Optional[List[str]] = None
) -> Dict[str, Any]:
	"""将模型实例转换为字典"""
	if exclude is None:
		exclude = []
	if include is None:
		include = []

	result = {}

	for column in instance.__table__.columns:
		column_name = column.name

		# 应用包含/排除规则
		if include and column_name not in include:
			continue
		if exclude and column_name in exclude:
			continue

		value = getattr(instance, column_name)

		# 处理特殊类型
		if isinstance(value, datetime):
			result[column_name] = value.isoformat()
		elif isinstance(value, date):
			result[column_name] = value.isoformat()
		elif isinstance(value, Decimal):
			result[column_name] = float(value)
		elif hasattr(value, '__dict__'):
			# 处理关联对象
			result[column_name] = model_to_dict(value)
		else:
			result[column_name] = value

	return result


def dict_to_model (
		model: Type[T],
		data: Dict[str, Any],
		exclude: Optional[List[str]] = None
) -> T:
	"""将字典转换为模型实例"""
	if exclude is None:
		exclude = []

	filtered_data = {
		k: v for k, v in data.items()
		if k not in exclude and hasattr(model, k)
	}

	return model(**filtered_data)


def rows_to_dict_list (
		rows: List[Any],
		exclude: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
	"""将行列表转换为字典列表"""
	return [model_to_dict(row, exclude=exclude) for row in rows]


def result_to_repository_result (
		result: Any,
		error: Optional[str] = None,
		total: Optional[int] = None
) -> RepositoryResult[Any]:
	"""将结果转换为RepositoryResult"""
	if error:
		return RepositoryResult.error_result(error)
	else:
		return RepositoryResult.success_result(result, total)


# ==================== 日期时间工具 ====================

def ensure_date (value: Any) -> Optional[date]:
	"""确保值为日期类型"""
	if value is None:
		return None

	if isinstance(value, date):
		return value

	if isinstance(value, datetime):
		return value.date()

	if isinstance(value, str):
		try:
			return datetime.fromisoformat(value).date()
		except ValueError:
			try:
				return datetime.strptime(value, '%Y-%m-%d').date()
			except ValueError:
				return None

	return None


def ensure_datetime (value: Any) -> Optional[datetime]:
	"""确保值为日期时间类型"""
	if value is None:
		return None

	if isinstance(value, datetime):
		return value

	if isinstance(value, date):
		return datetime.combine(value, datetime.min.time())

	if isinstance(value, str):
		try:
			return datetime.fromisoformat(value)
		except ValueError:
			try:
				return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
			except ValueError:
				try:
					return datetime.strptime(value, '%Y-%m-%d')
				except ValueError:
					return None

	return None


def get_date_range (
		start_date: Optional[date] = None,
		end_date: Optional[date] = None,
		days: Optional[int] = None
) -> Tuple[date, date]:
	"""获取日期范围"""
	today = datetime.now().date()

	if start_date is None:
		if days is not None:
			start_date = today - timedelta(days=days - 1)
		else:
			start_date = today - timedelta(days=30)  # 默认30天

	if end_date is None:
		end_date = today

	return start_date, end_date


def get_datetime_range (
		start_time: Optional[datetime] = None,
		end_time: Optional[datetime] = None,
		hours: Optional[int] = None
) -> Tuple[datetime, datetime]:
	"""获取日期时间范围"""
	now = datetime.now()

	if start_time is None:
		if hours is not None:
			start_time = now - timedelta(hours=hours)
		else:
			start_time = now - timedelta(days=1)  # 默认24小时

	if end_time is None:
		end_time = now

	return start_time, end_time


# ==================== 字符串工具 ====================

def safe_like (value: str) -> str:
	"""安全地构建LIKE查询值"""
	# 转义SQL LIKE特殊字符
	value = value.replace('%', '\\%')
	value = value.replace('_', '\\_')
	value = value.replace('\\', '\\\\')

	return f"%{value}%"


def build_search_conditions (
		model: Type[T],
		keyword: str,
		search_fields: List[str]
) -> List[Any]:
	"""构建搜索条件"""
	conditions = []

	for field in search_fields:
		if hasattr(model, field):
			conditions.append(
				getattr(model, field).like(safe_like(keyword))
			)

	return conditions


def camel_to_snake (name: str) -> str:
	"""将驼峰命名转换为蛇形命名"""
	import re
	name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
	return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def snake_to_camel (name: str) -> str:
	"""将蛇形命名转换为驼峰命名"""
	components = name.split('_')
	return components[0] + ''.join(x.title() for x in components[1:])


# ==================== 验证工具 ====================

def validate_filters (
		model: Type[T],
		filters: Dict[str, Any]
) -> Tuple[List[Any], List[str]]:
	"""验证过滤器"""
	valid_filters = []
	errors = []

	for field, value in filters.items():
		if hasattr(model, field):
			valid_filters.append(getattr(model, field) == value)
		else:
			errors.append(f"字段 '{field}' 不存在于模型中")

	return valid_filters, errors


def validate_sort (
		model: Type[T],
		sort_by: str,
		descending: bool = False
) -> Optional[Any]:
	"""验证排序字段"""
	if hasattr(model, sort_by):
		column = getattr(model, sort_by)
		return column.desc() if descending else column.asc()

	return None


# ==================== 缓存工具 ====================

class QueryCache:
	"""查询缓存"""

	def __init__ (self, cache_provider=None, ttl: int = 300):
		self.cache_provider = cache_provider
		self.ttl = ttl
		self._local_cache = {}

	async def get (self, key: str) -> Optional[Any]:
		"""获取缓存值"""
		# 先检查本地缓存
		if key in self._local_cache:
			value, expiry = self._local_cache[key]
			if datetime.now() < expiry:
				return value

		# 检查外部缓存
		if self.cache_provider:
			try:
				value = await self.cache_provider.get(key)
				if value is not None:
					# 更新本地缓存
					self._local_cache[key] = (
						value,
						datetime.now() + timedelta(seconds=self.ttl)
					)
				return value
			except Exception as e:
				logger.warning(f"缓存获取失败: {e}")

		return None

	async def set (self, key: str, value: Any) -> bool:
		"""设置缓存值"""
		# 更新本地缓存
		self._local_cache[key] = (
			value,
			datetime.now() + timedelta(seconds=self.ttl)
		)

		# 更新外部缓存
		if self.cache_provider:
			try:
				await self.cache_provider.set(key, value, ex=self.ttl)
				return True
			except Exception as e:
				logger.warning(f"缓存设置失败: {e}")
				return False

		return True

	async def delete (self, key: str) -> bool:
		"""删除缓存值"""
		# 删除本地缓存
		self._local_cache.pop(key, None)

		# 删除外部缓存
		if self.cache_provider:
			try:
				await self.cache_provider.delete(key)
				return True
			except Exception as e:
				logger.warning(f"缓存删除失败: {e}")
				return False

		return True

	def clear_local (self) -> None:
		"""清空本地缓存"""
		self._local_cache.clear()

	def generate_key (
			self,
			prefix: str,
			*args,
			**kwargs
	) -> str:
		"""生成缓存键"""
		key_parts = [prefix]

		for arg in args:
			key_parts.append(str(arg))

		for k, v in sorted(kwargs.items()):
			key_parts.append(f"{k}:{v}")

		return ":".join(key_parts)


# ==================== 错误处理工具 ====================

class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "REPOSITORY_ERROR"):
		self.message = message
		self.code = code
		super().__init__(self.message)


class NotFoundError(RepositoryError):
	"""未找到异常"""

	def __init__ (self, entity: str, identifier: Any):
		super().__init__(
			f"{entity} with identifier {identifier} not found",
			"NOT_FOUND"
		)


class AlreadyExistsError(RepositoryError):
	"""已存在异常"""

	def __init__ (self, entity: str, identifier: Any):
		super().__init__(
			f"{entity} with identifier {identifier} already exists",
			"ALREADY_EXISTS"
		)


class ValidationError(RepositoryError):
	"""验证异常"""

	def __init__ (self, message: str, errors: Optional[List[str]] = None):
		super().__init__(message, "VALIDATION_ERROR")
		self.errors = errors or []


async def handle_repository_operation (
		operation,
		*args,
		**kwargs
) -> RepositoryResult[Any]:
	"""处理Repository操作，统一错误处理"""
	try:
		result = await operation(*args, **kwargs)
		return RepositoryResult.success_result(result)
	except NotFoundError as e:
		return RepositoryResult.error_result(str(e))
	except AlreadyExistsError as e:
		return RepositoryResult.error_result(str(e))
	except ValidationError as e:
		return RepositoryResult.error_result(str(e))
	except SQLAlchemyError as e:
		logger.error(f"数据库操作失败: {e}")
		return RepositoryResult.error_result("数据库操作失败")
	except Exception as e:
		logger.error(f"未知错误: {e}")
		return RepositoryResult.error_result("内部服务器错误")


# ==================== 导出所有工具 ====================

__all__ = [
	# 数据库会话管理
	"get_db_session",
	"execute_with_session",

	# 查询构建工具
	"build_select_query",
	"build_count_query",
	"build_exists_query",
	"build_pagination_query",

	# 结果处理工具
	"execute_query",
	"fetch_one",
	"fetch_all",
	"fetch_paginated",
	"fetch_dict",
	"fetch_scalar",

	# 批量操作工具
	"batch_insert",
	"batch_update",
	"batch_upsert",
	"batch_delete",

	# 数据转换工具
	"model_to_dict",
	"dict_to_model",
	"rows_to_dict_list",
	"result_to_repository_result",

	# 日期时间工具
	"ensure_date",
	"ensure_datetime",
	"get_date_range",
	"get_datetime_range",

	# 字符串工具
	"safe_like",
	"build_search_conditions",
	"camel_to_snake",
	"snake_to_camel",

	# 验证工具
	"validate_filters",
	"validate_sort",

	# 缓存工具
	"QueryCache",

	# 错误处理工具
	"RepositoryError",
	"NotFoundError",
	"AlreadyExistsError",
	"ValidationError",
	"handle_repository_operation",
]