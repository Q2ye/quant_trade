# -*- coding: utf-8 -*-
"""
策略模板表Repository
位置：shared/database/repositories/strategy/strategy_template_repo.py
"""
from typing import Optional, List, Dict, Any

from sqlalchemy import select, or_, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ValidationError
from shared.database.models.business_models import StrategyTemplate
from shared.database.repositories.utils import NotFoundError
from shared.database.repositories.base import BaseRepository, RepositoryError


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

	@staticmethod
	def _calculate_time_score(created_at, cutoff_date) -> float:
		"""
		计算时间评分：创建时间越近，分数越高
		
		Args:
			created_at: 模板创建时间
			cutoff_date: 截止日期
		
		Returns:
			时间评分（0-1之间）
		"""
		try:
			from datetime import datetime
			
			# 计算创建时间与截止时间的差值（天数）
			time_diff = (created_at - cutoff_date).total_seconds() / (24 * 3600)
			total_days = (datetime.now() - cutoff_date).total_seconds() / (24 * 3600)
			
			# 归一化到0-1 范围：越接近现在，分数越高
			if total_days <= 0:
				return 1.0
			
			score = time_diff / total_days
			return max(0.0, min(1.0, score))
		except (ValueError, TypeError, AttributeError):
			return 0.5  # 默认评分

	@staticmethod
	def _calculate_type_score(template_type: str) -> float:
		"""
		计算模板类型权重：不同类型的模板有不同的受欢迎程度
		
		Args:
			template_type: 模板类型
		
		Returns:
			类型评分（0-1之间）
		"""
		# todo  根据实际业务需求调整不同类型模板的权重
		type_weights = {
			"alpha": 0.9,    # Alpha策略通常更受欢迎
			"cta": 0.8,      # CTA策略
			"ai": 0.95,      # AI策略可能更受欢迎
			"custom": 0.7,   # 自定义模板
			"ml": 0.9,       # 机器学习策略
			"dl": 0.95,      # 深度学习策略
		}
		
		return type_weights.get(template_type, 0.7)

	@staticmethod
	def _calculate_update_score(created_at, updated_at) -> float:
		"""
		计算更新频率评分：最近更新的模板更受欢迎
		
		Args:
			created_at: 创建时间
			updated_at: 更新时间
		
		Returns:
			更新评分（0-1之间）
		"""
		try:
			from datetime import datetime
			
			# 如果创建时间和更新时间相同，说明没有更新过
			if created_at == updated_at:
				return 0.3  # 基础评分
			
			# 计算更新时间与创建时间的差值（天数）
			update_diff = (updated_at - created_at).total_seconds() / (24 * 3600)
			
			# 如果更新时间在创建后7天内，认为更新频率较高
			if update_diff <= 7:
				return 0.9
			elif update_diff <= 30:
				return 0.7
			else:
				return 0.5
		except (ValueError, TypeError, AttributeError):
			return 0.5  # 默认评分

	async def get_popular_templates (
			self,
			days: int = 30,
			limit: int = 10
	) -> List[Dict[str, Any]]:
		"""
		获取热门模板（基于综合热度评分）

		Args:
			days: 天数（用于时间范围筛选）
			limit: 限制记录数

		Returns:
			热门模板列表，包含热度评分
		"""
		try:
			# 计算模板热度评分（在没有直接使用统计的情况下）
			# 热度评分 = 创建时间权重 + 更新频率权重 + 模板类型权重
			
			# 获取指定时间范围内的模板
			from datetime import datetime, timedelta
			from sqlalchemy import and_
			
			cutoff_date = datetime.now() - timedelta(days=days)
			
			# 构建基础查询：获取公开模板
			query = select(self.model).where(
				and_(
					self.model.is_public == True,
					self.model.created_at >= cutoff_date
				)
			)

			result = await self.session.execute(query)
			templates = result.scalars().all()

			if not templates:
				return []

			# 计算每个模板的热度评分
			template_scores = []
			
			for template in templates:
				# 基础评分：创建时间越近，分数越高
				time_score = self._calculate_time_score(template.created_at, cutoff_date)
				
				# 模板类型权重：不同类型的模板可能有不同的受欢迎程度
				type_score = self._calculate_type_score(template.template_type)
				
				# 更新频率权重：最近更新的模板更受欢迎
				update_score = self._calculate_update_score(template.created_at, template.updated_at)
				
				# 综合热度评分
				total_score = time_score * 0.5 + type_score * 0.3 + update_score * 0.2
				
				template_scores.append({
					"template": template,
					"score": total_score
				})

			# 按热度评分排序并限制数量
			template_scores.sort(key=lambda x: x["score"], reverse=True)
			top_templates = template_scores[:limit]

			# 返回包含热度评分的模板信息
			return [
				{
					"id": item["template"].id,
					"template_name": item["template"].template_name,
					"template_type": item["template"].template_type,
					"category": item["template"].category,
					"description": item["template"].description,
					"created_at": item["template"].created_at,
					"updated_at": item["template"].updated_at,
					"popularity_score": round(item["score"], 4),
					"usage_count": 0  # 实际中需要从其他表统计
				}
				for item in top_templates
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
					case((self.model.is_public == True, 1), else_=None)
				).label("public_templates"),
				func.count(
					case((self.model.is_public == False, 1), else_=None)
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
			template_id: str,
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
				raise NotFoundError("策略模板", template_id)

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

	async def get_by_id (self, template_id: str) -> Optional[StrategyTemplate]:
		"""
		根据ID获取模板

		Args:
			template_id: 模板ID

		Returns:
			模板对象或None
		"""
		return await self.get(template_id)

	async def get_paginated (
			self,
			page: int = 1,
			page_size: int = 20,
			template_type: Optional[str] = None,
			category: Optional[str] = None,
			is_public: Optional[bool] = None,
			search_term: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		分页获取模板列表

		Args:
			page: 页码
			page_size: 每页大小
			template_type: 模板类型
			category: 分类
			is_public: 是否公开
			search_term: 搜索关键词

		Returns:
			分页结果，包含items和total
		"""
		try:
			query = select(self.model)

			# 应用过滤条件
			if template_type:
				query = query.where(self.model.template_type == template_type)
			if category:
				query = query.where(self.model.category == category)
			if is_public is not None:
				query = query.where(self.model.is_public == is_public)
			if search_term:
				query = query.where(
					or_(
						self.model.template_name.ilike(f"%{search_term}%"),
						self.model.description.ilike(f"%{search_term}%"),
						self.model.category.ilike(f"%{search_term}%")
					)
				)

			# 计算总数
			count_query = select(func.count()).select_from(query.subquery())
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页和排序
			query = query.order_by(
				desc(self.model.created_at)
			).offset((page - 1) * page_size).limit(page_size)

			result = await self.session.execute(query)
			items = result.scalars().all()

			return {
				"items": items,
				"total": total,
				"page": page,
				"page_size": page_size
			}
		except Exception as e:
			raise RepositoryError(f"分页获取模板失败: {str(e)}")