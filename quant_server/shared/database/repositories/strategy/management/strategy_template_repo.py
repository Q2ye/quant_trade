# -*- coding: utf-8 -*-
"""
策略模板表Repository
位置：shared/database/repositories/strategy/strategy_template_repo.py
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, between, case
from sqlalchemy.orm import joinedload, load_only

from quant_server.core.exceptions import ValidationError
from quant_server.shared.database.models.business_models import StrategyTemplate, SysUser
from quant_server.shared.database.repositories import NotFoundError
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError
from quant_server.shared.database.repositories.types import (
	RepositoryResult, PaginationParams, PaginationResult,
	FilterCondition, SortCondition, QueryParams
)


class StrategyTemplateRepository(BaseRepository[StrategyTemplate]):
	"""策略模板Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, StrategyTemplate)

	async def create_template (
			self,
			template_name: str,
			template_type: str,
			code_template: str,
			default_parameters: Dict[str, Any],
			description: Optional[str] = None,
			category: Optional[str] = None,
			is_public: bool = True,
			created_by: Optional[int] = None
	) -> StrategyTemplate:
		"""
		创建策略模板

		Args:
			template_name: 模板名称
			template_type: 模板类型（alpha/cta/ai/custom）
			code_template: 代码模板
			default_parameters: 默认参数
			description: 模板描述
			category: 分类
			is_public: 是否公开
			created_by: 创建人ID

		Returns:
			策略模板记录
		"""
		try:
			data = {
				"template_name": template_name,
				"template_type": template_type,
				"description": description,
				"code_template": code_template,
				"default_parameters": default_parameters or {},
				"category": category,
				"is_public": is_public,
				"created_by": created_by
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建策略模板失败: {str(e)}")

	async def get_by_type (
			self,
			template_type: str,
			is_public: Optional[bool] = None,
			category: Optional[str] = None,
			limit: int = 100
	) -> List[StrategyTemplate]:
		"""
		根据模板类型获取模板

		Args:
			template_type: 模板类型
			is_public: 是否公开
			category: 分类
			limit: 限制记录数

		Returns:
			策略模板列表
		"""
		try:
			query = select(self.model).where(
				self.model.template_type == template_type
			)

			if is_public is not None:
				query = query.where(self.model.is_public == is_public)
			if category:
				query = query.where(self.model.category == category)

			query = query.order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取模板类型记录失败: {str(e)}")

	async def get_public_templates (
			self,
			template_type: Optional[str] = None,
			category: Optional[str] = None,
			search_term: Optional[str] = None,
			limit: int = 100
	) -> List[StrategyTemplate]:
		"""
		获取公开模板

		Args:
			template_type: 模板类型
			category: 分类
			search_term: 搜索关键词
			limit: 限制记录数

		Returns:
			公开模板列表
		"""
		try:
			query = select(self.model).where(
				self.model.is_public == True
			)

			if template_type:
				query = query.where(self.model.template_type == template_type)
			if category:
				query = query.where(self.model.category == category)
			if search_term:
				query = query.where(
					or_(
						self.model.template_name.ilike(f"%{search_term}%"),
						self.model.description.ilike(f"%{search_term}%"),
						self.model.category.ilike(f"%{search_term}%")
					)
				)

			query = query.order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取公开模板失败: {str(e)}")

	async def get_by_creator (
			self,
			created_by: int,
			template_type: Optional[str] = None,
			is_public: Optional[bool] = None,
			limit: int = 100
	) -> List[StrategyTemplate]:
		"""
		根据创建人获取模板

		Args:
			created_by: 创建人ID
			template_type: 模板类型
			is_public: 是否公开
			limit: 限制记录数

		Returns:
			策略模板列表
		"""
		try:
			query = select(self.model).where(
				self.model.created_by == created_by
			)

			if template_type:
				query = query.where(self.model.template_type == template_type)
			if is_public is not None:
				query = query.where(self.model.is_public == is_public)

			query = query.order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取创建人模板失败: {str(e)}")

	async def get_popular_templates (
			self,
			days: int = 30,
			limit: int = 10
	) -> List[Dict[str, Any]]:
		"""
		获取热门模板（基于使用次数）

		Args:
			days: 天数
			limit: 限制记录数

		Returns:
			热门模板列表
		"""
		try:
			# 这里假设有策略表可以关联，实际中可能需要统计策略创建时使用的模板
			# 由于模型中没有直接关联，这里返回空列表或需要扩展
			# 这是一个占位符实现

			query = select(self.model).where(
				self.model.is_public == True
			).order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			templates = result.scalars().all()

			# 返回模板基本信息
			return [
				{
					"id": template.id,
					"template_name": template.template_name,
					"template_type": template.template_type,
					"category": template.category,
					"description": template.description,
					"created_at": template.created_at,
					"usage_count": 0  # 实际中需要从其他表统计
				}
				for template in templates
			]
		except Exception as e:
			raise RepositoryError(f"获取热门模板失败: {str(e)}")

	async def search_templates (
			self,
			keyword: str,
			template_type: Optional[str] = None,
			category: Optional[str] = None,
			is_public: Optional[bool] = None,
			limit: int = 50
	) -> List[StrategyTemplate]:
		"""
		搜索策略模板

		Args:
			keyword: 搜索关键词
			template_type: 模板类型
			category: 分类
			is_public: 是否公开
			limit: 限制记录数

		Returns:
			搜索结果列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.template_name.ilike(f"%{keyword}%"),
					self.model.description.ilike(f"%{keyword}%"),
					self.model.category.ilike(f"%{keyword}%"),
					self.model.template_type.ilike(f"%{keyword}%")
				)
			)

			if template_type:
				query = query.where(self.model.template_type == template_type)
			if category:
				query = query.where(self.model.category == category)
			if is_public is not None:
				query = query.where(self.model.is_public == is_public)

			query = query.order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索模板失败: {str(e)}")

	async def get_template_categories (
			self,
			template_type: Optional[str] = None,
			is_public: Optional[bool] = None
	) -> List[str]:
		"""
		获取模板分类列表

		Args:
			template_type: 模板类型
			is_public: 是否公开

		Returns:
			分类列表
		"""
		try:
			query = select(
				func.distinct(self.model.category)
			).where(
				self.model.category.isnot(None)
			)

			if template_type:
				query = query.where(self.model.template_type == template_type)
			if is_public is not None:
				query = query.where(self.model.is_public == is_public)

			query = query.order_by(
				self.model.category
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			return [row[0] for row in rows if row[0]]
		except Exception as e:
			raise RepositoryError(f"获取模板分类失败: {str(e)}")

	async def get_template_statistics (
			self,
			created_by: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取模板统计信息

		Args:
			created_by: 创建人ID

		Returns:
			模板统计信息
		"""
		try:
			query = select(
				func.count().label("total_templates"),
				func.count(
					case([(self.model.is_public == True, 1)], else_=None)
				).label("public_templates"),
				func.count(
					case([(self.model.is_public == False, 1)], else_=None)
				).label("private_templates"),
				self.model.template_type
			)

			if created_by:
				query = query.where(self.model.created_by == created_by)

			query = query.group_by(
				self.model.template_type
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			total_templates = 0
			public_templates = 0
			private_templates = 0
			templates_by_type = {}

			for row in rows:
				total_templates += row.total_templates or 0
				public_templates += row.public_templates or 0
				private_templates += row.private_templates or 0

				template_type = row.template_type
				templates_by_type[template_type] = {
					"total": row.total_templates or 0,
					"public": row.public_templates or 0,
					"private": row.private_templates or 0
				}

			return {
				"total_templates": total_templates,
				"public_templates": public_templates,
				"private_templates": private_templates,
				"templates_by_type": templates_by_type,
				"categories_count": len(await self.get_template_categories())
			}
		except Exception as e:
			raise RepositoryError(f"获取模板统计失败: {str(e)}")

	async def clone_template (
			self,
			template_id: int,
			new_template_name: str,
			new_description: Optional[str] = None,
			is_public: Optional[bool] = None,
			created_by: Optional[int] = None
	) -> Optional[StrategyTemplate]:
		"""
		克隆模板

		Args:
			template_id: 模板ID
			new_template_name: 新模板名称
			new_description: 新描述
			is_public: 是否公开
			created_by: 创建人ID

		Returns:
			克隆的模板
		"""
		try:
			template = await self.get(template_id)
			if not template:
				raise NotFoundError(f"模板不存在: {template_id}")

			# 检查是否有权限克隆（公开模板或自己的模板）
			if not template.is_public and created_by and template.created_by != created_by:
				raise ValidationError("没有权限克隆此模板")

			data = {
				"template_name": new_template_name,
				"template_type": template.template_type,
				"description": new_description or template.description,
				"code_template": template.code_template,
				"default_parameters": template.default_parameters,
				"category": template.category,
				"is_public": is_public if is_public is not None else template.is_public,
				"created_by": created_by or template.created_by
			}

			return await self.create(data)
		except Exception as e:
			if isinstance(e, (NotFoundError, ValidationError)):
				raise e
			raise RepositoryError(f"克隆模板失败: {str(e)}")