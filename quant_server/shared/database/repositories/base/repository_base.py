# -*- coding: utf-8 -*-
"""
Repository基类 - 统一数据访问接口

基于异步SQLAlchemy实现，支持CRUD操作和分页查询
位置：quant_server/shared/database/repositories/base.py

设计原则：
1. 纯数据访问：只做CRUD，不做业务逻辑
2. 统一接口：所有Repository继承自BaseRepository基类
3. 异步支持：完全异步化设计，支持高并发
4. 类型安全：使用泛型确保类型一致性
"""

from datetime import datetime, date
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any

import pandas as pd
from sqlalchemy import select, delete, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import Select

from ..types import (
	PaginationParams,
	PaginationResult,
	FilterCondition,
	SortCondition
)

# 泛型类型变量，用于表示模型类型
T = TypeVar('T')


class BaseRepository(Generic[T]):
	"""Repository基类 - 纯数据访问，无业务逻辑"""

	def __init__ (self, session: AsyncSession, model: Type[T]):
		"""
		初始化Repository

		Args:
			session: 数据库会话，提供数据访问上下文
			model: SQLAlchemy模型类，定义数据表结构
		"""
		self.session = session
		self.model = model

	# ==================== 辅助方法 ====================

	@staticmethod
	def _convert_to_datetime (value: Any) -> Optional[datetime]:
		"""
		将各种日期时间格式转换为Python datetime对象
		用于处理来自Pandas、外部API等不同来源的日期值

		Args:
			value: 需要转换的值（可以是pandas Timestamp、datetime、date、字符串等）

		Returns:
			转换后的datetime对象，如果无法转换则返回None
		"""
		if value is None:
			return None

		if isinstance(value, datetime):
			return value

		if isinstance(value, pd.Timestamp):
			return value.to_pydatetime()

		if isinstance(value, date):
			return datetime.combine(value, datetime.min.time())

		if isinstance(value, str):
			try:
				# 尝试解析ISO格式字符串
				return pd.to_datetime(value).to_pydatetime()
			except (ValueError, TypeError):
				return None

		# 无法转换
		return None

	def _convert_record_datetime (self, data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		转换记录中的日期时间字段
		自动检测并转换常见日期时间字段

		Args:
			data: 原始记录字典

		Returns:
			转换后的记录字典
		"""
		# 定义需要检查的日期时间字段
		datetime_fields = ['trade_date', 'start_date', 'end_date', 'calc_time',
		                   'created_at', 'updated_at', 'started_at', 'completed_at',
		                   'stopped_at', 'timestamp', 'event_time', 'start_time', 'end_time']

		converted = data.copy()
		for field in datetime_fields:
			if field in converted and converted[field] is not None:
				converted[field] = self._convert_to_datetime(converted[field])

		return converted

	# ==================== 基本CRUD操作 ====================

	async def get (self, id: Any, with_related: bool = False,
	               related_fields: List[str] = None) -> Optional[T]:
		"""
		根据ID获取单条记录

		Args:
			id: 记录ID
			with_related: 是否加载关联数据
			related_fields: 需要加载的关联字段列表

		Returns:
			记录对象或None（如果不存在）
		"""
		try:
			query = select(self.model).where(self.model.id == id)

			# 加载关联数据
			if with_related and related_fields:
				for field in related_fields:
					if hasattr(self.model, field):
						query = query.options(joinedload(getattr(self.model, field)))

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取记录失败: {str(e)}")

	async def get_by (self, **filters) -> Optional[T]:
		"""
		根据条件获取单条记录

		Args:
			**filters: 过滤条件，键值对形式

		Returns:
			记录对象或None
		"""
		try:
			query = select(self.model)

			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"按条件获取记录失败: {str(e)}")

	async def get_many(self, skip: int = 0, limit: int = 100,
	                    **filters) -> List[T]:
		"""
		获取多条记录（带分页）

		Args:
			skip: 跳过记录数，用于分页
			limit: 限制记录数，用于分页
			**filters: 过滤条件

		Returns:
			记录列表
		"""
		try:
			query = select(self.model)

			# 应用过滤条件
			for attr, value in filters.items():
				if hasattr(self.model, attr):
					if isinstance(value, (list, tuple)):
						query = query.where(getattr(self.model, attr).in_(value))
					else:
						query = query.where(getattr(self.model, attr) == value)

			# 分页
			query = query.offset(skip).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取多条记录失败: {str(e)}")

	async def get_all (self, **filters) -> List[T]:
		"""
		获取所有记录

		Args:
			**filters: 过滤条件

		Returns:
			记录列表
		"""
		try:
			query = select(self.model)

			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取所有记录失败: {str(e)}")

	async def create (self, data: Dict[str, Any]) -> T:
		"""
		创建新记录

		Args:
			data: 记录数据，字典形式

		Returns:
			创建的记录对象
		"""
		try:
			# 转换日期时间字段
			data = self._convert_record_datetime(data)

			# 自动添加时间戳
			now = datetime.now()
			if hasattr(self.model, 'created_at'):
				data['created_at'] = data.get('created_at', now)
			if hasattr(self.model, 'updated_at'):
				data['updated_at'] = data.get('updated_at', now)

			# 创建实例
			instance = self.model(**data)
			self.session.add(instance)
			await self.session.flush()

			return instance

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"创建记录失败: {str(e)}")

	async def batch_create (self, data_list: List[Dict[str, Any]]) -> List[T]:
		"""
		批量创建记录

		Args:
			data_list: 记录数据列表

		Returns:
			创建的记录对象列表
		"""
		try:
			instances = []
			now = datetime.now()

			for data in data_list:
				# 转换日期时间字段
				data = self._convert_record_datetime(data)

				# 自动添加时间戳
				if hasattr(self.model, 'created_at'):
					data['created_at'] = data.get('created_at', now)
				if hasattr(self.model, 'updated_at'):
					data['updated_at'] = data.get('updated_at', now)

				instance = self.model(**data)
				self.session.add(instance)
				instances.append(instance)

			await self.session.flush()
			return instances

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量创建记录失败: {str(e)}")

	async def update (self, id: Any, data: Dict[str, Any]) -> Optional[T]:
		"""
		更新记录

		Args:
			id: 记录ID
			data: 更新数据

		Returns:
			更新后的记录对象或None
		"""
		try:
			# 转换日期时间字段
			data = self._convert_record_datetime(data)

			# 自动更新时间戳
			if hasattr(self.model, 'updated_at'):
				data['updated_at'] = data.get('updated_at', datetime.now())

			# 执行更新
			from sqlalchemy import update as sql_update
			stmt = sql_update(self.model)
			stmt = stmt.where(self.model.id == id)
			stmt = stmt.values(**data)

			await self.session.execute(stmt)

			# 返回更新后的记录
			return await self.get(id)

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"更新记录失败: {str(e)}")

	async def update_by (self, filters: Dict[str, Any], data: Dict[str, Any]) -> int:
		"""
		根据条件更新多条记录

		Args:
			filters: 过滤条件
			data: 更新数据

		Returns:
			更新的记录数
		"""
		try:
			# 自动更新时间戳
			if hasattr(self.model, 'updated_at'):
				data['updated_at'] = data.get('updated_at', datetime.now())

			# 构建查询
			from sqlalchemy import update as sql_update
			query = sql_update(self.model)

			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			# 执行更新
			query = query.values(**data)
			result = await self.session.execute(query) # type:ignore
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"按条件更新记录失败: {str(e)}")

	# ==================== 批量 upsert ====================

	async def bulk_upsert (self, records: List[Dict[str, Any]], chunk_size: int = 1000) -> int:
		"""
		批量 upsert（INSERT ... ON CONFLICT DO UPDATE），自动从 model 提取冲突键和更新列。
		与 batch_upsert(match_fields, data_list) 不同，本方法只需传 records，自动推断冲突键。

		Args:
			records: 记录列表（dict 格式）
			chunk_size: 每批记录数，防 PostgreSQL 32767 参数上限

		Returns:
			int: 写入记录数
		"""
		if not records:
			return 0

		from sqlalchemy.dialects.postgresql import insert as pg_insert
		from sqlalchemy import UniqueConstraint

		# --- 提取冲突键（缓存，1μs） ---
		cache_key = '_bulk_upsert_conflict_cols'
		if not hasattr(self, cache_key):
			conflict_cols = None
			# 1. 从 __table_args__ 的 UniqueConstraint 提取
			for arg in getattr(self.model, '__table_args__', ()):
				if isinstance(arg, UniqueConstraint):
					conflict_cols = [c.name for c in arg.columns]
					break
			# 2. 回退到非 id 的 PrimaryKey（如 index_daily 的 (ts_code,trade_date)）
			if not conflict_cols:
				pk = [c.name for c in self.model.__table__.primary_key]
				if pk != ['id']:
					conflict_cols = pk
			# 3. 最后尝试常见业务键
			if not conflict_cols:
				for keys in (['ts_code', 'trade_date'], ['ts_code', 'end_date'],
				             ['ts_code', 'ann_date'], ['ts_code']):
					if all(hasattr(self.model, k) for k in keys):
						conflict_cols = list(keys)
						break
			if not conflict_cols:
				raise ValueError(f"无法确定 upsert 冲突键: {self.model.__tablename__}")
			setattr(self, cache_key, conflict_cols)

		conflict_cols = getattr(self, cache_key)

		# --- 提取更新列（排除 PK 和 created_at，缓存） ---
		cache_key2 = '_bulk_upsert_update_cols'
		if not hasattr(self, cache_key2):
			exclude = set(conflict_cols) | {'created_at'}
			update_cols = [c.name for c in self.model.__table__.columns
			               if c.name not in exclude and not c.primary_key]
			setattr(self, cache_key2, update_cols)

		update_cols = getattr(self, cache_key2)

		# --- 分批写入 ---
		total = 0
		for i in range(0, len(records), chunk_size):
			chunk = records[i:i + chunk_size]
			stmt = pg_insert(self.model).values(chunk)
			stmt = stmt.on_conflict_do_update(
				index_elements=conflict_cols,
				set_={c: getattr(stmt.excluded, c) for c in update_cols}
			)
			result = await self.session.execute(stmt)
			total += result.rowcount
		return total

	async def delete (self, id: Any, soft: bool = True) -> bool:
		"""
		删除记录

		Args:
			id: 记录ID
			soft: 是否软删除

		Returns:
			是否成功
		"""
		try:
			if soft and hasattr(self.model, 'is_deleted'):
				# 软删除
				from sqlalchemy import update as sql_update
				stmt = sql_update(self.model)
				stmt = stmt.where(self.model.id == id)
				stmt = stmt.values(is_deleted=True, updated_at=datetime.now())
				await self.session.execute(stmt)
			else:
				# 硬删除
				from sqlalchemy import delete as sql_delete
				stmt = sql_delete(self.model)
				stmt = stmt.where(self.model.id == id)
				await self.session.execute(stmt) # type:ignore

			await self.session.flush()
			return True

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"删除记录失败: {str(e)}")

	async def delete_by (self, **filters) -> int:
		"""
		根据条件删除记录

		Args:
			**filters: 过滤条件

		Returns:
			删除的记录数
		"""
		try:
			query = delete(self.model)

			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"按条件删除记录失败: {str(e)}")

	# ==================== 查询方法 ====================

	async def count (self, **filters) -> int:
		"""
		统计记录数

		Args:
			**filters: 过滤条件

		Returns:
			记录数
		"""
		try:
			query = select(func.count()).select_from(self.model)

			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			result = await self.session.execute(query)
			return result.scalar() or 0

		except Exception as e:
			raise RepositoryError(f"统计记录数失败: {str(e)}")

	async def count_by (self, **filters) -> int:
		"""
		根据条件统计记录数（支持高级过滤）

		Args:
			**filters: 过滤条件，支持特殊语法：
			- field__between: 范围查询，值为(start, end)元组
			- 其他: 等值查询

		Returns:
			记录数
		"""
		try:
			query = select(func.count()).select_from(self.model)

			for attr, value in filters.items():
				# 处理特殊语法
				if '__between' in attr:
					field_name = attr.split('__between')[0]
					if hasattr(self.model, field_name) and isinstance(value, (list, tuple)) and len(value) == 2:
						start, end = value
						query = query.where(getattr(self.model, field_name).between(start, end))
				elif hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			result = await self.session.execute(query)
			return result.scalar() or 0

		except Exception as e:
			raise RepositoryError(f"按条件统计记录数失败: {str(e)}")

	async def exists (self, **filters) -> bool:
		"""
		检查记录是否存在

		Args:
			**filters: 过滤条件

		Returns:
			是否存在
		"""
		try:
			query = select(self.model.id).limit(1)

			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			result = await self.session.execute(query)
			return result.scalar_one_or_none() is not None

		except Exception as e:
			raise RepositoryError(f"检查记录是否存在失败: {str(e)}")

	async def paginate (self, pagination: PaginationParams,
	                    filters: List[FilterCondition] = None,
	                    sorts: List[SortCondition] = None) -> PaginationResult[T]:
		"""
		分页查询

		Args:
			pagination: 分页参数
			filters: 过滤条件列表
			sorts: 排序条件列表

		Returns:
			分页结果
		"""
		try:
			# 构建基础查询
			query = select(self.model)

			# 应用过滤条件
			if filters:
				filter_conditions = []
				for filter_cond in filters:
					field = getattr(self.model, filter_cond.field, None)
					if field:
						if filter_cond.operator == "eq":
							filter_conditions.append(field == filter_cond.value)
						elif filter_cond.operator == "gt":
							filter_conditions.append(field > filter_cond.value)
						elif filter_cond.operator == "lt":
							filter_conditions.append(field < filter_cond.value)
						elif filter_cond.operator == "in":
							filter_conditions.append(field.in_(filter_cond.value))
						elif filter_cond.operator == "like":
							filter_conditions.append(field.like(f"%{filter_cond.value}%"))

				if filter_conditions:
					query = query.where(and_(*filter_conditions))

			# 应用排序条件
			if sorts:
				order_clauses = []
				for sort_cond in sorts:
					field = getattr(self.model, sort_cond.field, None)
					if field:
						order_clauses.append(
							desc(field) if sort_cond.descending else asc(field)
						)

				if order_clauses:
					query = query.order_by(*order_clauses)

			# 获取总数
			count_query = select(func.count()).select_from(query.subquery())
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 获取分页数据
			result = await self.session.execute(query)
			items = result.scalars().all()

			return PaginationResult.create(
				items=items,
				total=total,
				page=pagination.page,
				page_size=pagination.page_size
			)

		except Exception as e:
			raise RepositoryError(f"分页查询失败: {str(e)}")

	# ==================== 批量操作 ====================

	async def upsert (self, match_fields: List[str], data: Dict[str, Any],
	                  update_fields: List[str] = None) -> T:
		"""
		插入或更新记录

		Args:
			match_fields: 匹配字段，用于检查记录是否存在
			data: 数据
			update_fields: 更新字段列表（None表示更新所有字段）

		Returns:
			记录对象
		"""
		try:
			# 构建匹配条件
			match_filters = {}
			for field in match_fields:
				if field in data:
					match_filters[field] = data[field]

			# 检查是否存在
			existing = await self.get_by(**match_filters)

			if existing:
				# 更新现有记录
				update_data = data.copy()

				# 如果指定了更新字段，只更新这些字段
				if update_fields:
					update_data = {k: v for k, v in update_data.items() if k in update_fields}

				return await self.update(existing.id, update_data)
			else:
				# 创建新记录
				return await self.create(data)

		except Exception as e:
			raise RepositoryError(f"插入或更新记录失败: {str(e)}")

	async def batch_upsert (self, match_fields: List[str],
	                        data_list: List[Dict[str, Any]],
	                        update_fields: List[str] = None) -> List[T]:
		"""
		批量插入或更新

		Args:
			match_fields: 匹配字段
			data_list: 数据列表
			update_fields: 更新字段

		Returns:
			记录对象列表
		"""
		try:
			results = []

			for data in data_list:
				result = await self.upsert(match_fields, data, update_fields)
				results.append(result)

			return results

		except Exception as e:
			raise RepositoryError(f"批量插入或更新失败: {str(e)}")

	# ==================== 自定义查询 ====================

	def build_query (self) -> Select:
		"""
		构建基础查询对象

		Returns:
			查询对象，可以继续添加条件
		"""
		return select(self.model)

	async def execute_query (self, query: Select) -> List[T]:
		"""
		执行自定义查询

		Args:
			query: 自定义查询对象

		Returns:
			查询结果列表
		"""
		try:
			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"执行自定义查询失败: {str(e)}")

	async def execute_scalar (self, query: Select) -> Any:
		"""
		执行标量查询

		Args:
			query: 查询对象

		Returns:
			标量结果
		"""
		try:
			result = await self.session.execute(query)
			return result.scalar()

		except Exception as e:
			raise RepositoryError(f"执行标量查询失败: {str(e)}")

	# ==================== 事务支持 ====================

	async def begin_transaction (self):
		"""
		开始事务
		"""
		await self.session.begin()

	async def commit (self):
		"""
		提交事务
		"""
		await self.session.commit()

	async def rollback (self):
		"""
		回滚事务
		"""
		await self.session.rollback()


class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "REPOSITORY_ERROR"):
		"""
		初始化异常

		Args:
			message: 错误信息
			code: 错误码
		"""
		self.message = message
		self.code = code
		super().__init__(self.message)