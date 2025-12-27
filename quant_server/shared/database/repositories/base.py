# -*- coding: utf-8 -*-
"""
# Repository基类 - 统一数据访问接口
# 基于异步SQLAlchemy实现，支持CRUD操作和分页查询
# 位置：quant_server/shared/database/repositories/base.py
"""

# shared/database/repositories/base.py
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import joinedload

T = TypeVar('T')


class BaseRepository(Generic[T]):
	"""Repository基类 - 纯数据访问，无业务逻辑"""

	def __init__ (self, session: AsyncSession, model: Type[T]):
		"""
		初始化Repository

		Args:
			session: 数据库会话
			model: SQLAlchemy模型类
		"""
		self.session = session
		self.model = model

	# ==================== 基本CRUD操作 ====================

	async def get (self, id: int) -> Optional[T]:
		"""
		根据ID获取单条记录

		Args:
			id: 记录ID

		Returns:
			记录对象或None
		"""
		result = await self.session.execute(
			select(self.model).where(self.model.id == id)
		)
		return result.scalar_one_or_none()

	async def get_by (self, **filters) -> Optional[T]:
		"""
		根据条件获取单条记录

		Args:
			filters: 过滤条件

		Returns:
			记录对象或None
		"""
		query = select(self.model)

		for attr, value in filters.items():
			if hasattr(self.model, attr):
				query = query.where(getattr(self.model, attr) == value)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_many (
			self,
			skip: int = 0,
			limit: int = 100,
			**filters
	) -> List[T]:
		"""
		获取多条记录

		Args:
			skip: 跳过记录数
			limit: 限制记录数
			filters: 过滤条件

		Returns:
			记录列表
		"""
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

	async def get_all (self, **filters) -> List[T]:
		"""
		获取所有记录

		Args:
			filters: 过滤条件

		Returns:
			记录列表
		"""
		query = select(self.model)

		for attr, value in filters.items():
			if hasattr(self.model, attr):
				query = query.where(getattr(self.model, attr) == value)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create (self, data: Dict[str, Any]) -> T:
		"""
		创建记录

		Args:
			data: 记录数据

		Returns:
			创建的记录对象
		"""
		# 自动添加时间戳
		if hasattr(self.model, 'created_at'):
			data['created_at'] = data.get('created_at', datetime.now())
		if hasattr(self.model, 'updated_at'):
			data['updated_at'] = data.get('updated_at', datetime.now())

		instance = self.model(**data)
		self.session.add(instance)
		await self.session.flush()
		return instance

	async def batch_create (self, data_list: List[Dict[str, Any]]) -> List[T]:
		"""
		批量创建记录

		Args:
			data_list: 记录数据列表

		Returns:
			创建的记录对象列表
		"""
		instances = []
		for data in data_list:
			# 自动添加时间戳
			if hasattr(self.model, 'created_at'):
				data['created_at'] = data.get('created_at', datetime.now())
			if hasattr(self.model, 'updated_at'):
				data['updated_at'] = data.get('updated_at', datetime.now())

			instance = self.model(**data)
			self.session.add(instance)
			instances.append(instance)

		await self.session.flush()
		return instances

	async def update (self, id: int, data: Dict[str, Any]) -> Optional[T]:
		"""
		更新记录

		Args:
			id: 记录ID
			data: 更新数据

		Returns:
			更新后的记录对象或None
		"""
		# 自动更新时间戳
		if hasattr(self.model, 'updated_at'):
			data['updated_at'] = data.get('updated_at', datetime.now())

		# 执行更新
		await self.session.execute(
			update(self.model)
			.where(self.model.id == id)
			.values(**data)
		)

		# 返回更新后的记录
		return await self.get(id)

	async def update_by (self, filters: Dict[str, Any], data: Dict[str, Any]) -> int:
		"""
		根据条件更新多条记录

		Args:
			filters: 过滤条件
			data: 更新数据

		Returns:
			更新的记录数
		"""
		# 自动更新时间戳
		if hasattr(self.model, 'updated_at'):
			data['updated_at'] = data.get('updated_at', datetime.now())

		# 构建查询
		query = update(self.model)

		for attr, value in filters.items():
			if hasattr(self.model, attr):
				query = query.where(getattr(self.model, attr) == value)

		# 执行更新
		result = await self.session.execute(query.values(**data))
		return result.rowcount

	async def delete (self, id: int, soft: bool = True) -> bool:
		"""
		删除记录

		Args:
			id: 记录ID
			soft: 是否软删除

		Returns:
			是否成功
		"""
		if soft and hasattr(self.model, 'is_deleted'):
			# 软删除
			await self.session.execute(
				update(self.model)
				.where(self.model.id == id)
				.values(is_deleted=1, updated_at=datetime.now())
			)
		else:
			# 硬删除
			await self.session.execute(
				delete(self.model).where(self.model.id == id)
			)

		return True

	async def delete_by (self, **filters) -> int:
		"""
		根据条件删除记录

		Args:
			filters: 过滤条件

		Returns:
			删除的记录数
		"""
		query = delete(self.model)

		for attr, value in filters.items():
			if hasattr(self.model, attr):
				query = query.where(getattr(self.model, attr) == value)

		result = await self.session.execute(query)
		return result.rowcount

	# ==================== 查询方法 ====================

	async def count (self, **filters) -> int:
		"""
		统计记录数

		Args:
			filters: 过滤条件

		Returns:
			记录数
		"""
		query = select(func.count()).select_from(self.model)

		for attr, value in filters.items():
			if hasattr(self.model, attr):
				query = query.where(getattr(self.model, attr) == value)

		result = await self.session.execute(query)
		return result.scalar()

	async def exists (self, **filters) -> bool:
		"""
		检查记录是否存在

		Args:
			filters: 过滤条件

		Returns:
			是否存在
		"""
		query = select(self.model.id)

		for attr, value in filters.items():
			if hasattr(self.model, attr):
				query = query.where(getattr(self.model, attr) == value)

		query = query.limit(1)
		result = await self.session.execute(query)
		return result.scalar_one_or_none() is not None

	async def get_with_related (
			self,
			id: int,
			related_models: List[str] = None
	) -> Optional[T]:
		"""
		获取记录及其关联数据

		Args:
			id: 记录ID
			related_models: 关联模型列表

		Returns:
			记录对象或None
		"""
		query = select(self.model)

		if related_models:
			for relation in related_models:
				if hasattr(self.model, relation):
					query = query.options(joinedload(getattr(self.model, relation)))

		query = query.where(self.model.id == id)

		result = await self.session.execute(query)
		return result.unique().scalar_one_or_none()

	# ==================== 批量操作 ====================

	async def upsert (
			self,
			match_fields: List[str],
			data: Dict[str, Any],
			update_fields: List[str] = None
	) -> T:
		"""
		插入或更新记录

		Args:
			match_fields: 匹配字段
			data: 数据
			update_fields: 更新字段（None表示更新所有字段）

		Returns:
			记录对象
		"""
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

	async def batch_upsert (
			self,
			match_fields: List[str],
			data_list: List[Dict[str, Any]],
			update_fields: List[str] = None
	) -> List[T]:
		"""
		批量插入或更新

		Args:
			match_fields: 匹配字段
			data_list: 数据列表
			update_fields: 更新字段

		Returns:
			记录对象列表
		"""
		results = []

		for data in data_list:
			result = await self.upsert(match_fields, data, update_fields)
			results.append(result)

		return results