# -*- coding: utf-8 -*-
"""
BasketRepository - 篮子管理数据访问层

基于BaseRepository实现，支持篮子的CRUD操作和篮子成分管理
位置：quant_server/shared/database/repositories/operation/basket/basket_repo.py

设计原则：
1. 继承BaseRepository，使用普通表模型（非超表）
2. 提供篮子特定业务查询方法
3. 支持篮子与篮子成分的关联操作
"""

from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, desc, asc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database.models.business_models import Basket
from shared.database.repositories.base.repository_base import BaseRepository, RepositoryError
from shared.database.repositories.types import (
	PaginationParams,
	PaginationResult,
	FilterCondition,
	SortCondition
)


class BasketRepository(BaseRepository[Basket]):
	"""篮子管理Repository - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化篮子Repository"""
		super().__init__(session, Basket)

	# ==================== 业务特定方法 ====================

	async def get_basket_with_items (self, basket_id: str) -> Optional[Basket]:
		"""
		获取篮子及所有成分股（预加载关联数据）

		Args:
			basket_id: 篮子ID

		Returns:
			篮子对象（包含items关联数据）或None

		Raises:
			RepositoryError: 查询失败时抛出
		"""
		try:
			query = (
				select(self.model)
				.options(selectinload(Basket.items))
				.where(self.model.id == basket_id)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取篮子及成分失败: {str(e)}")

	async def get_user_baskets (
			self,
			pagination: PaginationParams = None,
			filters: List[FilterCondition] = None,
			sorts: List[SortCondition] = None
	) -> PaginationResult[Basket]:
		"""
		分页查询篮子列表

		Args:
			pagination: 分页参数
			filters: 过滤条件
			sorts: 排序条件

		Returns:
			分页结果
		"""
		try:
			# 构建基础查询
			query = select(self.model).options(selectinload(Basket.items))

			# 应用过滤条件
			if filters:
				filter_conditions = []
				for filter_cond in filters:
					field = getattr(self.model, filter_cond.field, None)
					if field:
						if filter_cond.operator == "eq":
							filter_conditions.append(field == filter_cond.value)
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
			else:
				# 默认按更新时间倒序
				query = query.order_by(desc(self.model.updated_at))

			# 获取总数
			count_query = select(func.count()).select_from(query.subquery())
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			if pagination:
				query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 获取分页数据
			result = await self.session.execute(query)
			items = result.scalars().all()

			# 如果是分页查询，返回分页结果
			if pagination:
				return PaginationResult.create(
					items=items,
					total=total,
					page=pagination.page,
					page_size=pagination.page_size
				)
			else:
				# 非分页查询，返回所有数据
				return PaginationResult.create(
					items=items,
					total=total,
					page=1,
					page_size=total
				)

		except Exception as e:
			raise RepositoryError(f"查询用户篮子列表失败: {str(e)}")

	async def search_baskets (
			self,
			keyword: str,
			pagination: PaginationParams
	) -> PaginationResult[Basket]:
		"""
		搜索篮子（按名称或描述）

		Args:
			keyword: 搜索关键词
			pagination: 分页参数

		Returns:
			分页搜索结果
		"""
		try:
			# 构建搜索查询
			if hasattr(self.model, 'description'):
				query = select(self.model).options(selectinload(Basket.items)).where(
					or_(
						self.model.name.like(f"%{keyword}%"),
						self.model.description.like(f"%{keyword}%")
					)
				)
			else:
				query = select(self.model).options(selectinload(Basket.items)).where(
					self.model.name.like(f"%{keyword}%")
				)

			# 获取总数
			count_query = select(func.count()).select_from(self.model).where(
				or_(
					self.model.name.like(f"%{keyword}%"),
					self.model.description.like(f"%{keyword}%") if hasattr(self.model, 'description') else False
				)
			)

			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 获取搜索结果
			result = await self.session.execute(query)
			items = result.scalars().all()

			return PaginationResult.create(
				items=items,
				total=total,
				page=pagination.page,
				page_size=pagination.page_size
			)

		except Exception as e:
			raise RepositoryError(f"搜索篮子失败: {str(e)}")

	async def get_basket_by_name (self, name: str) -> Optional[Basket]:
		"""
		根据篮子名称获取篮子

		Args:
			name: 篮子名称

		Returns:
			篮子对象或None
		"""
		try:
			query = select(self.model).options(selectinload(Basket.items)).where(self.model.name == name)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"根据名称获取篮子失败: {str(e)}")

	async def count_items_in_basket (self, basket_id: str) -> int:
		"""
		统计篮子中的成分股数量

		Args:
			basket_id: 篮子ID

		Returns:
			成分股数量
		"""
		try:
			from .basket_item_repo import BasketItemRepository
			item_repo = BasketItemRepository(self.session)

			return await item_repo.count(basket_id=basket_id)

		except Exception as e:
			raise RepositoryError(f"统计篮子成分数量失败: {str(e)}")

	async def create_basket_with_items (
			self,
			basket_data: Dict[str, Any],
			items_data: List[Dict[str, Any]]
	) -> Basket:
		"""
		创建篮子及其成分股（事务操作）

		Args:
			basket_data: 篮子数据
			items_data: 成分股数据列表

		Returns:
			创建的篮子对象

		Raises:
			RepositoryError: 创建失败时抛出
		"""
		try:
			# 开始事务
			await self.begin_transaction()

			# 创建篮子
			basket = await self.create(basket_data)

			if items_data:
				# 创建篮子成分
				from .basket_item_repo import BasketItemRepository
				item_repo = BasketItemRepository(self.session)

				for item_data in items_data:
					item_data['basket_id'] = basket.id
					await item_repo.create(item_data)

			# 提交事务前刷新，确保数据可见
			await self.session.flush()

			# 重新加载篮子及关联数据（在同事务内）
			result = await self.get_basket_with_items(basket.id)

			# 提交事务
			await self.commit()

			return result

		except Exception as e:
			await self.rollback()
			raise RepositoryError(f"创建篮子及成分失败: {str(e)}")

	async def update_basket_with_items (
			self,
			basket_id: str,
			basket_data: Dict[str, Any],
			items_data: List[Dict[str, Any]] = None
	) -> Basket:
		"""
		更新篮子及其成分股（事务操作）

		Args:
			basket_id: 篮子ID
			basket_data: 篮子更新数据
			items_data: 成分股数据列表（None表示不更新成分）

		Returns:
			更新后的篮子对象

		Raises:
			RepositoryError: 更新失败时抛出
		"""
		try:
			# 开始事务
			await self.begin_transaction()

			# 更新篮子基本信息
			basket = await self.update(basket_id, basket_data)

			if items_data is not None:
				# 更新篮子成分
				from .basket_item_repo import BasketItemRepository
				item_repo = BasketItemRepository(self.session)

				# 删除现有成分
				await item_repo.delete_by(basket_id=basket_id)

				# 添加新成分
				for item_data in items_data:
					item_data['basket_id'] = basket_id
					await item_repo.create(item_data)

			# 提交前重新加载（确保在同事务内获取关联数据）
			await self.session.flush()
			result = await self.get_basket_with_items(basket.id)

			# 提交事务
			await self.commit()

			return result

		except Exception as e:
			await self.rollback()
			raise RepositoryError(f"更新篮子及成分失败: {str(e)}")

	async def delete_basket_with_items (self, basket_id: str, soft: bool = True) -> bool:
		"""
		删除篮子及其所有成分股（事务操作）

		Args:
			basket_id: 篮子ID
			soft: 是否软删除

		Returns:
			是否成功

		Raises:
			RepositoryError: 删除失败时抛出
		"""
		try:
			# 开始事务
			await self.begin_transaction()

			# 删除篮子成分
			from .basket_item_repo import BasketItemRepository
			item_repo = BasketItemRepository(self.session)
			await item_repo.delete_by(basket_id=basket_id)

			# 删除篮子
			success = await self.delete(basket_id, soft)

			# 提交事务
			await self.commit()

			return success

		except Exception as e:
			await self.rollback()
			raise RepositoryError(f"删除篮子及成分失败: {str(e)}")

	async def get_basket_summary (self, basket_id: str) -> Dict[str, Any]:
		"""
		获取篮子摘要信息（包含成分统计）

		Args:
			basket_id: 篮子ID

		Returns:
			篮子摘要信息字典
		"""
		try:
			# 获取篮子
			basket = await self.get(basket_id)
			if not basket:
				return {}

			# 获取成分统计
			from .basket_item_repo import BasketItemRepository
			item_repo = BasketItemRepository(self.session)

			items = await item_repo.get_all(basket_id=basket_id)

			# 计算权重统计
			total_weight = sum(item.weight for item in items)
			avg_weight = total_weight / len(items) if items else 0

			return {
				"basket_id": basket.id,
				"name": basket.name,
				"description": basket.description,
				"created_at": basket.created_at,
				"updated_at": basket.updated_at,
				"item_count": len(items),
				"total_weight": total_weight,
				"avg_weight": avg_weight,
				"items": [
					{
						"ts_code": item.ts_code,
						"weight": item.weight
					}
					for item in items
				]
			}

		except Exception as e:
			raise RepositoryError(f"获取篮子摘要失败: {str(e)}")