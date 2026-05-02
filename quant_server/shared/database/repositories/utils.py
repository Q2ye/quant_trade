# -*- coding: utf-8 -*-
"""
数据库工具函数库

位置：quant_server/shared/database/repositories/utils.py

功能分类：
1. 数据库会话管理
2. 查询构建工具
3. 结果处理工具
4. 批量操作工具
5. 数据转换工具
6. 日期时间工具
7. 字符串工具
8. 验证工具
9. 缓存工具
10. 错误处理工具
"""

import logging
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union, Callable

from sqlalchemy import select, insert, update, delete, func, and_
from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.selectable import Select

from .types import (
	PaginationParams,
	PaginationResult,
	RepositoryResult,
	FilterCondition,
	SortCondition
)

T = TypeVar('T')
logger = logging.getLogger(__name__)


# ==================== 数据库会话管理 ====================

@asynccontextmanager
async def get_db_session (session_maker: async_sessionmaker[AsyncSession]):
	"""
	获取数据库会话的上下文管理器

	Args:
		session_maker: 会话工厂

	Yields:
		AsyncSession: 数据库会话

	Example:
		async with get_db_session(session_maker) as session:
			result = await session.execute(query)
	"""
	session = session_maker()
	try:
		yield session
		await session.commit()
	except Exception as e:
		await session.rollback()
		logger.error(f"数据库操作失败: {e}")
		raise
	finally:
		await session.close()


async def execute_with_session (session_maker: async_sessionmaker[AsyncSession],
								operation: Callable, *args, **kwargs) -> Any:
	"""
	在数据库会话中执行函数

	Args:
		session_maker: 会话工厂
		operation: 要执行的函数
		*args: 函数参数
		**kwargs: 函数关键字参数

	Returns:
		Any: 函数执行结果
	"""
	async with get_db_session(session_maker) as session:
		return await operation(session, *args, **kwargs)


def transactional (fn: Callable) -> Callable:
	"""
	事务装饰器

	Args:
		fn: 被装饰的函数

	Returns:
		Callable: 装饰后的函数
	"""

	@wraps(fn)
	async def wrapper (self, *args, **kwargs):
		# 这里假设self有session属性
		try:
			result = await fn(self, *args, **kwargs)
			await self.session.commit()
			return result
		except Exception:
			await self.session.rollback()
			raise

	return wrapper


# ==================== 查询构建工具 ====================

def build_select_query (model: Type[T], filters: Optional[List[Any]] = None,
                        order_by: Optional[Any] = None, limit: Optional[int] = None,
                        offset: Optional[int] = None, distinct_on: Optional[Any] = None,
                        columns: Optional[List[Any]] = None) -> Select:
	"""
	构建SELECT查询

	Args:
		model: SQLAlchemy模型类
		filters: 过滤条件列表
		order_by: 排序条件
		limit: 限制数量
		offset: 偏移量
		distinct_on: 去重字段
		columns: 选择字段列表

	Returns:
		Select: 查询对象
	"""
	# 选择指定字段或全部字段
	if columns:
		query = select(*columns)
	else:
		query = select(model)

	# 去重
	if distinct_on:
		query = query.distinct(distinct_on)

	# 应用过滤条件
	if filters:
		query = query.where(and_(*filters))

	# 应用排序
	if order_by:
		query = query.order_by(order_by)

	# 应用分页
	if offset is not None:
		query = query.offset(offset)

	if limit is not None:
		query = query.limit(limit)

	return query


def build_count_query (model: Type[T], filters: Optional[List[Any]] = None,
                       distinct_column: Optional[Any] = None) -> Select:
	"""
	构建COUNT查询

	Args:
		model: SQLAlchemy模型类
		filters: 过滤条件列表
		distinct_column: 去重字段

	Returns:
		Select: 计数查询对象
	"""
	if distinct_column:
		query = select(func.count(distinct_column))
	else:
		query = select(func.count()).select_from(model)

	if filters:
		query = query.where(and_(*filters))

	return query


def build_exists_query (model: Type[T], filters: Optional[List[Any]] = None) -> Select:
	"""
	构建EXISTS查询

	Args:
		model: SQLAlchemy模型类
		filters: 过滤条件列表

	Returns:
		Select: 存在性查询对象
	"""
	query = select(1).select_from(model)

	if filters:
		query = query.where(and_(*filters))

	return query.limit(1)


def build_pagination_query (query: Select, pagination: PaginationParams) -> Select:
	"""
	为查询添加分页

	Args:
		query: 原始查询对象
		pagination: 分页参数

	Returns:
		Select: 分页查询对象
	"""
	# 这里可以根据order_by动态获取排序字段
	# 实际使用中需要根据具体模型调整
	return query.offset(
		pagination.get_offset()
	).limit(
		pagination.get_limit()
	)


def build_filter_conditions (model: Type[T],
                             filter_conditions: List[FilterCondition]) -> List[Any]:
	"""
	构建SQLAlchemy过滤条件

	Args:
		model: SQLAlchemy模型类
		filter_conditions: 过滤条件列表

	Returns:
		List[Any]: SQLAlchemy过滤条件列表
	"""
	conditions = []

	for filter_cond in filter_conditions:
		field = getattr(model, filter_cond.field, None)
		if not field:
			continue

		operator = filter_cond.operator
		value = filter_cond.value

		if operator == "eq":
			conditions.append(field == value)
		elif operator == "ne":
			conditions.append(field != value)
		elif operator == "gt":
			conditions.append(field > value)
		elif operator == "ge":
			conditions.append(field >= value)
		elif operator == "lt":
			conditions.append(field < value)
		elif operator == "le":
			conditions.append(field <= value)
		elif operator == "like":
			conditions.append(field.like(f"%{value}%"))
		elif operator == "ilike":
			conditions.append(field.ilike(f"%{value}%"))
		elif operator == "in":
			conditions.append(field.in_(value))
		elif operator == "not_in":
			conditions.append(field.notin_(value))
		elif operator == "is_null":
			conditions.append(field.is_(None))
		elif operator == "not_null":
			conditions.append(field.isnot(None))
		elif operator == "between" and isinstance(value, (list, tuple)) and len(value) == 2:
			conditions.append(field.between(value[0], value[1]))

	return conditions


def apply_sorting (query: Select, model: Type[T],
                   sort_conditions: List[SortCondition]) -> Select:
	"""
	应用排序条件到查询

	Args:
		query: 原始查询对象
		model: SQLAlchemy模型类
		sort_conditions: 排序条件列表

	Returns:
		Select: 排序后的查询对象
	"""
	from sqlalchemy import asc, desc

	order_clauses = []

	for sort_cond in sort_conditions:
		field = getattr(model, sort_cond.field, None)
		if field:
			order_clauses.append(
				desc(field) if sort_cond.descending else asc(field)
			)

	if order_clauses:
		query = query.order_by(*order_clauses)

	return query


# ==================== 结果处理工具 ====================

async def execute_query (session: AsyncSession, query: Select) -> Result:
	"""
	执行查询并返回结果

	Args:
		session: 数据库会话
		query: 查询对象

	Returns:
		Result: SQLAlchemy结果对象

	Raises:
		SQLAlchemyError: 数据库操作异常
	"""
	try:
		return await session.execute(query)
	except SQLAlchemyError as e:
		logger.error(f"查询执行失败: {e}")
		raise


async def fetch_one (session: AsyncSession, query: Select) -> Optional[Any]:
	"""
	获取单条记录

	Args:
		session: 数据库会话
		query: 查询对象

	Returns:
		Optional[Any]: 单条记录或None
	"""
	result = await execute_query(session, query)
	return result.scalar_one_or_none()


async def fetch_all (session: AsyncSession, query: Select) -> List[Any]:
	"""
	获取所有记录

	Args:
		session: 数据库会话
		query: 查询对象

	Returns:
		List[Any]: 记录列表
	"""
	result = await execute_query(session, query)
	return result.scalars().all()


async def fetch_paginated (session: AsyncSession, query: Select,
                           count_query: Select, pagination: PaginationParams) -> PaginationResult[Any]:
	"""
	获取分页结果

	Args:
		session: 数据库会话
		query: 数据查询对象
		count_query: 计数查询对象
		pagination: 分页参数

	Returns:
		PaginationResult[Any]: 分页结果
	"""
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


async def fetch_dict (session: AsyncSession, query: Select) -> List[Dict[str, Any]]:
	"""
	获取字典格式的结果

	Args:
		session: 数据库会话
		query: 查询对象

	Returns:
		List[Dict[str, Any]]: 字典列表
	"""
	result = await execute_query(session, query)
	rows = result.all()

	return [
		{key: value for key, value in row._asdict().items()}
		for row in rows
	]


async def fetch_scalar (session: AsyncSession, query: Select) -> Optional[Any]:
	"""
	获取标量值

	Args:
		session: 数据库会话
		query: 查询对象

	Returns:
		Optional[Any]: 标量值或None
	"""
	result = await execute_query(session, query)
	return result.scalar()


# ==================== 批量操作工具 ====================

async def batch_insert (session: AsyncSession, model: Type[T],
                        data_list: List[Dict[str, Any]],
                        return_ids: bool = False) -> Union[List[T], List[int]]:
	"""
	批量插入数据

	Args:
		session: 数据库会话
		model: SQLAlchemy模型类
		data_list: 数据列表
		return_ids: 是否返回ID

	Returns:
		Union[List[T], List[int]]: 插入的记录或ID列表
	"""
	if not data_list:
		return []

	try:
		# 添加时间戳
		now = datetime.now()
		for data in data_list:
			if hasattr(model, 'created_at'):
				data['created_at'] = data.get('created_at', now)
			if hasattr(model, 'updated_at'):
				data['updated_at'] = data.get('updated_at', now)

		# 执行批量插入
		await session.execute(
			insert(model),
			data_list
		)
		await session.flush()

		# 获取插入的ID（需要数据库支持RETURNING）
		if return_ids:
			# 这里只是一个示例，实际实现需要根据数据库调整
			# 可能需要执行额外的查询来获取ID
			pass

		# 重新查询插入的数据
		# 这里只是一个简单实现，实际可能需要更复杂的逻辑
		return []

	except SQLAlchemyError as e:
		logger.error(f"批量插入失败: {e}")
		await session.rollback()
		raise


async def batch_update (session: AsyncSession, model: Type[T],
                        data_list: List[Dict[str, Any]],
                        match_fields: List[str]) -> List[T]:
	"""
	批量更新数据

	Args:
		session: 数据库会话
		model: SQLAlchemy模型类
		data_list: 数据列表
		match_fields: 匹配字段

	Returns:
		List[T]: 更新后的记录列表
	"""
	if not data_list:
		return []

	updated_items = []

	try:
		# 添加更新时间戳
		now = datetime.now()
		for data in data_list:
			if hasattr(model, 'updated_at'):
				data['updated_at'] = data.get('updated_at', now)

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

	except SQLAlchemyError as e:
		logger.error(f"批量更新失败: {e}")
		await session.rollback()
		raise


async def batch_upsert (session: AsyncSession, model: Type[T],
                        data_list: List[Dict[str, Any]],
                        match_fields: List[str],
                        update_excluded: Optional[List[str]] = None) -> List[T]:
	"""
	批量插入或更新数据

	Args:
		session: 数据库会话
		model: SQLAlchemy模型类
		data_list: 数据列表
		match_fields: 匹配字段
		update_excluded: 排除更新字段

	Returns:
		List[T]: 操作后的记录列表
	"""
	if not data_list:
		return []

	upserted_items = []

	try:
		for data in data_list:
			# 添加时间戳
			now = datetime.now()
			if hasattr(model, 'created_at'):
				data.setdefault('created_at', now)
			if hasattr(model, 'updated_at'):
				data['updated_at'] = data.get('updated_at', now)

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
				await session.execute(stmt)  # type: ignore[union-attr]

		await session.flush()
		return upserted_items

	except SQLAlchemyError as e:
		logger.error(f"批量插入或更新失败: {e}")
		await session.rollback()
		raise


async def batch_delete (session: AsyncSession, model: Type[T],
                        filters: List[Any], soft_delete: bool = True,
                        soft_delete_field: str = 'is_deleted') -> int:
	"""
	批量删除数据

	Args:
		session: 数据库会话
		model: SQLAlchemy模型类
		filters: 过滤条件
		soft_delete: 是否软删除
		soft_delete_field: 软删除字段名

	Returns:
		int: 删除的记录数
	"""
	if soft_delete and hasattr(model, soft_delete_field):
		# 软删除
		stmt = update(model).where(and_(*filters)).values(
			**{soft_delete_field: True, 'updated_at': datetime.now()}
		)
	else:
		# 硬删除
		stmt = delete(model).where(and_(*filters))

	result = await session.execute(stmt)
	await session.flush()

	return result.rowcount or 0


# ==================== 数据转换工具 ====================

def model_to_dict (instance: Any, exclude: Optional[List[str]] = None,
                   include: Optional[List[str]] = None) -> Dict[str, Any]:
	"""
	将模型实例转换为字典

	Args:
		instance: 模型实例
		exclude: 排除字段列表
		include: 包含字段列表

	Returns:
		Dict[str, Any]: 字典
	"""
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


def dict_to_model (model: Type[T], data: Dict[str, Any],
                   exclude: Optional[List[str]] = None) -> T:
	"""
	将字典转换为模型实例

	Args:
		model: SQLAlchemy模型类
		data: 数据字典
		exclude: 排除字段列表

	Returns:
		T: 模型实例
	"""
	if exclude is None:
		exclude = []

	filtered_data = {
		k: v for k, v in data.items()
		if k not in exclude and hasattr(model, k)
	}

	return model(**filtered_data)


def rows_to_dict_list (rows: List[Any], exclude: Optional[List[str]] = None) -> List[Dict[str, Any]]:
	"""
	将行列表转换为字典列表

	Args:
		rows: 行列表
		exclude: 排除字段列表

	Returns:
		List[Dict[str, Any]]: 字典列表
	"""
	return [model_to_dict(row, exclude=exclude) for row in rows]


def result_to_repository_result (result: Any, error: Optional[str] = None,
                                 total: Optional[int] = None) -> RepositoryResult[Any]:
	"""
	将结果转换为RepositoryResult

	Args:
		result: 结果数据
		error: 错误信息
		total: 总数

	Returns:
		RepositoryResult[Any]: Repository结果对象
	"""
	if error:
		return RepositoryResult.error_result(error)
	else:
		return RepositoryResult.success_result(result, total)


# ==================== 日期时间工具 ====================

def ensure_date (value: Any) -> Optional[date]:
	"""
	确保值为日期类型

	Args:
		value: 输入值

	Returns:
		Optional[date]: 日期对象或None
	"""
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
	"""
	确保值为日期时间类型

	Args:
		value: 输入值

	Returns:
		Optional[datetime]: 日期时间对象或None
	"""
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


def get_date_range (start_date: Optional[date] = None,
                    end_date: Optional[date] = None,
                    days: Optional[int] = None) -> Tuple[date, date]:
	"""
	获取日期范围

	Args:
		start_date: 开始日期
		end_date: 结束日期
		days: 天数

	Returns:
		Tuple[date, date]: (开始日期, 结束日期)
	"""
	today = datetime.now().date()

	if start_date is None:
		if days is not None:
			start_date = today - timedelta(days=days - 1)
		else:
			start_date = today - timedelta(days=30)  # 默认30天

	if end_date is None:
		end_date = today

	return start_date, end_date


def get_datetime_range (start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        hours: Optional[int] = None) -> Tuple[datetime, datetime]:
	"""
	获取日期时间范围

	Args:
		start_time: 开始时间
		end_time: 结束时间
		hours: 小时数

	Returns:
		Tuple[datetime, datetime]: (开始时间, 结束时间)
	"""
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
	"""
	安全地构建LIKE查询值

	Args:
		value: 原始字符串

	Returns:
		str: 安全的LIKE字符串
	"""
	# 转义SQL LIKE特殊字符
	value = value.replace('%', '\\%')
	value = value.replace('_', '\\_')
	value = value.replace('\\', '\\\\')

	return f"%{value}%"


def build_search_conditions (model: Type[T], keyword: str,
                             search_fields: List[str]) -> List[Any]:
	"""
	构建搜索条件

	Args:
		model: SQLAlchemy模型类
		keyword: 搜索关键词
		search_fields: 搜索字段列表

	Returns:
		List[Any]: 搜索条件列表
	"""
	conditions = []

	for field in search_fields:
		if hasattr(model, field):
			conditions.append(
				getattr(model, field).ilike(safe_like(keyword))
			)

	return conditions


def camel_to_snake (name: str) -> str:
	"""
	将驼峰命名转换为蛇形命名

	Args:
		name: 驼峰命名字符串

	Returns:
		str: 蛇形命名字符串
	"""
	name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
	return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def snake_to_camel (name: str) -> str:
	"""
	将蛇形命名转换为驼峰命名

	Args:
		name: 蛇形命名字符串

	Returns:
		str: 驼峰命名字符串
	"""
	components = name.split('_')
	return components[0] + ''.join(x.title() for x in components[1:])


# ==================== 验证工具 ====================

def validate_filters (model: Type[T], filters: Dict[str, Any]) -> Tuple[List[Any], List[str]]:
	"""
	验证过滤器

	Args:
		model: SQLAlchemy模型类
		filters: 过滤器字典

	Returns:
		Tuple[List[Any], List[str]]: (有效过滤器列表, 错误信息列表)
	"""
	valid_filters = []
	errors = []

	for field, value in filters.items():
		if hasattr(model, field):
			valid_filters.append(getattr(model, field) == value)
		else:
			errors.append(f"字段 '{field}' 不存在于模型中")

	return valid_filters, errors


def validate_sort (model: Type[T], sort_by: str,
                   descending: bool = False) -> Optional[Any]:
	"""
	验证排序字段

	Args:
		model: SQLAlchemy模型类
		sort_by: 排序字段名
		descending: 是否降序

	Returns:
		Optional[Any]: 排序条件或None
	"""
	if hasattr(model, sort_by):
		column = getattr(model, sort_by)
		from sqlalchemy import desc, asc
		return desc(column) if descending else asc(column)

	return None


# ==================== 缓存工具 ====================

class QueryCache:
	"""查询缓存管理器"""

	def __init__ (self, cache_provider=None, ttl: int = 300):
		"""
		初始化缓存管理器

		Args:
			cache_provider: 缓存提供者（如Redis客户端）
			ttl: 缓存生存时间（秒）
		"""
		self.cache_provider = cache_provider
		self.ttl = ttl
		self._local_cache = {}

	async def get (self, key: str) -> Optional[Any]:
		"""
		获取缓存值

		Args:
			key: 缓存键

		Returns:
			Optional[Any]: 缓存值或None
		"""
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
		"""
		设置缓存值

		Args:
			key: 缓存键
			value: 缓存值

		Returns:
			bool: 是否成功
		"""
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
		"""
		删除缓存值

		Args:
			key: 缓存键

		Returns:
			bool: 是否成功
		"""
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

	@staticmethod
	def generate_key (prefix: str, *args, **kwargs) -> str:
		"""
		生成缓存键

		Args:
			prefix: 键前缀
			*args: 位置参数
			**kwargs: 关键字参数

		Returns:
			str: 缓存键
		"""
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


async def handle_repository_operation (operation: Callable, *args, **kwargs) -> RepositoryResult[Any]:
	"""
	处理Repository操作，统一错误处理

	Args:
		operation: Repository操作函数
		*args: 函数参数
		**kwargs: 函数关键字参数

	Returns:
		RepositoryResult[Any]: 操作结果
	"""
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


# ==================== 事务工具 ====================

async def safe_commit (session: AsyncSession) -> bool:
	"""
	安全提交事务

	Args:
		session: 数据库会话

	Returns:
		bool: 是否成功
	"""
	try:
		await session.commit()
		return True
	except Exception as e:
		await session.rollback()
		logger.error(f"事务提交失败: {e}")
		return False


def convert_to_dict (obj: Any) -> Dict[str, Any]:
	"""
	将对象转换为字典

	Args:
		obj: 任意对象

	Returns:
		Dict[str, Any]: 字典
	"""
	if hasattr(obj, '__dict__'):
		return obj.__dict__.copy()
	elif isinstance(obj, tuple) and hasattr(obj, '_asdict'):  # namedtuple
		return obj._asdict()
	else:
		return {}


# ==================== 导出所有工具 ====================

__all__ = [
	# 数据库会话管理
	"get_db_session",
	"execute_with_session",
	"transactional",

	# 查询构建工具
	"build_select_query",
	"build_count_query",
	"build_exists_query",
	"build_pagination_query",
	"build_filter_conditions",
	"apply_sorting",

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

	# 事务工具
	"safe_commit",
	"convert_to_dict"
]
