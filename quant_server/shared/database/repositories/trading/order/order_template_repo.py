# -*- coding: utf-8 -*-
"""
订单模板仓库 - 提供订单模板数据的统一访问接口

基于BaseRepository实现，提供订单模板相关的CRUD操作和业务查询方法
位置：quant_server/shared/database/repositories/trading/order/order_template_repository.py

设计原则：
1. 纯数据访问：只做CRUD，不做业务逻辑
2. 继承BaseRepository：复用基础CRUD操作
3. 模板管理：支持模板分类和默认模板管理
4. 用户隔离：确保用户只能访问自己的模板
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, and_, or_, func, desc, asc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from quant_server.shared.database.models.business_models import OrderTemplate
from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.repositories.types import (
	RepositoryError
)


class OrderTemplateRepository(BaseRepository[OrderTemplate]):
	"""订单模板仓库 - 订单模板数据访问层"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化订单模板仓库

		Args:
			session: 数据库会话
		"""
		super().__init__(session, OrderTemplate)

	# ==================== 业务查询方法 ====================

	async def get_by_template_id (self, template_id: str, with_user: bool = False) -> Optional[OrderTemplate]:
		"""
		根据模板ID获取订单模板

		Args:
			template_id: 模板ID
			with_user: 是否加载用户信息

		Returns:
			订单模板对象或None
		"""
		try:
			query = select(OrderTemplate).where(OrderTemplate.id == template_id)

			if with_user:
				query = query.options(joinedload(OrderTemplate.user))

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取订单模板失败: {str(e)}")

	async def get_by_user_id (
			self,
			user_id: str,
			template_type: Optional[str] = None,
			is_default: Optional[bool] = None,
			skip: int = 0,
			limit: int = 100,
			order_by: str = "created_at_desc"
	) -> List[OrderTemplate]:
		"""
		根据用户ID获取订单模板

		Args:
			user_id: 用户ID
			template_type: 模板类型过滤
			is_default: 是否默认模板过滤
			skip: 跳过记录数
			limit: 限制记录数
			order_by: 排序方式

		Returns:
			订单模板列表
		"""
		try:
			filters = [OrderTemplate.user_id == user_id]

			if template_type:
				filters.append(OrderTemplate.template_type == template_type)
			if is_default is not None:
				filters.append(OrderTemplate.is_default == is_default)

			# 构建排序
			order_clause = self._build_order_by(order_by)

			query = (
				select(OrderTemplate)
				.where(and_(*filters))
				.order_by(*order_clause)
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取用户订单模板失败: {str(e)}")

	async def get_by_template_name (
			self,
			user_id: str,
			template_name: str
	) -> Optional[OrderTemplate]:
		"""
		根据模板名称获取订单模板

		Args:
			user_id: 用户ID
			template_name: 模板名称

		Returns:
			订单模板对象或None
		"""
		try:
			query = select(OrderTemplate).where(
				and_(
					OrderTemplate.user_id == user_id,
					OrderTemplate.template_name == template_name
				)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取模板名称订单模板失败: {str(e)}")

	async def get_default_template (
			self,
			user_id: str,
			template_type: Optional[str] = None
	) -> Optional[OrderTemplate]:
		"""
		获取用户的默认订单模板

		Args:
			user_id: 用户ID
			template_type: 模板类型过滤

		Returns:
			默认订单模板对象或None
		"""
		try:
			filters = [
				OrderTemplate.user_id == user_id,
				OrderTemplate.is_default == True
			]

			if template_type:
				filters.append(OrderTemplate.template_type == template_type)

			query = select(OrderTemplate).where(and_(*filters))

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取默认订单模板失败: {str(e)}")

	async def get_templates_by_type (
			self,
			user_id: str,
			template_type: str,
			skip: int = 0,
			limit: int = 100
	) -> List[OrderTemplate]:
		"""
		根据模板类型获取订单模板

		Args:
			user_id: 用户ID
			template_type: 模板类型
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			订单模板列表
		"""
		try:
			query = (
				select(OrderTemplate)
				.where(
					and_(
						OrderTemplate.user_id == user_id,
						OrderTemplate.template_type == template_type
					)
				)
				.order_by(
					desc(OrderTemplate.is_default),
					desc(OrderTemplate.updated_at)
				)
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取类型订单模板失败: {str(e)}")

	async def search_templates (
			self,
			user_id: str,
			search_term: str,
			template_type: Optional[str] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[OrderTemplate]:
		"""
		搜索订单模板

		Args:
			user_id: 用户ID
			search_term: 搜索关键词
			template_type: 模板类型过滤
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			订单模板列表
		"""
		try:
			filters = [OrderTemplate.user_id == user_id]

			# 添加搜索条件
			if search_term:
				filters.append(
					or_(
						OrderTemplate.template_name.ilike(f"%{search_term}%"),
						OrderTemplate.description.ilike(f"%{search_term}%")
					)
				)

			if template_type:
				filters.append(OrderTemplate.template_type == template_type)

			query = (
				select(OrderTemplate)
				.where(and_(*filters))
				.order_by(
					desc(OrderTemplate.is_default),
					desc(OrderTemplate.updated_at)
				)
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"搜索订单模板失败: {str(e)}")

	async def get_recent_templates (
			self,
			user_id: str,
			days: int = 30,
			template_type: Optional[str] = None,
			limit: int = 50
	) -> List[OrderTemplate]:
		"""
		获取最近使用的订单模板

		Args:
			user_id: 用户ID
			days: 天数
			template_type: 模板类型过滤
			limit: 限制记录数

		Returns:
			最近使用的订单模板列表
		"""
		try:
			cutoff_time = datetime.now() - timedelta(days=days)

			filters = [
				OrderTemplate.user_id == user_id,
				OrderTemplate.updated_at >= cutoff_time
			]

			if template_type:
				filters.append(OrderTemplate.template_type == template_type)

			query = (
				select(OrderTemplate)
				.where(and_(*filters))
				.order_by(desc(OrderTemplate.updated_at))
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取最近订单模板失败: {str(e)}")

	async def get_template_categories (
			self,
			user_id: str
	) -> List[str]:
		"""
		获取用户的模板分类

		Args:
			user_id: 用户ID

		Returns:
			模板分类列表
		"""
		try:
			query = (
				select(func.distinct(OrderTemplate.template_type))
				.where(OrderTemplate.user_id == user_id)
				.order_by(OrderTemplate.template_type)
			)

			result = await self.session.execute(query)
			return [row[0] for row in result.all()]

		except Exception as e:
			raise RepositoryError(f"获取模板分类失败: {str(e)}")

	# ==================== 模板统计方法 ====================

	async def get_template_statistics (
			self,
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取模板统计信息

		Args:
			user_id: 用户ID

		Returns:
			模板统计信息字典
		"""
		try:
			# 总模板数
			total_query = select(func.count()).select_from(OrderTemplate).where(
				OrderTemplate.user_id == user_id
			)
			total_result = await self.session.execute(total_query)
			total_templates = total_result.scalar() or 0

			# 按类型统计
			type_stats_query = (
				select(
					OrderTemplate.template_type,
					func.count(OrderTemplate.id).label('count'),
					func.sum(case((OrderTemplate.is_default == True, 1), else_=0)).label('default_count')
				)
				.where(OrderTemplate.user_id == user_id)
				.group_by(OrderTemplate.template_type)
			)

			type_stats_result = await self.session.execute(type_stats_query)
			type_stats_rows = type_stats_result.all()

			type_stats = {}
			for row in type_stats_rows:
				type_stats[row.template_type] = {
					'count': row.count or 0,
					'default_count': row.default_count or 0
				}

			# 默认模板数
			default_query = select(func.count()).select_from(OrderTemplate).where(
				and_(
					OrderTemplate.user_id == user_id,
					OrderTemplate.is_default == True
				)
			)
			default_result = await self.session.execute(default_query)
			default_templates = default_result.scalar() or 0

			# 最近更新
			recent_update = await self.session.execute(
				select(func.max(OrderTemplate.updated_at))
				.where(OrderTemplate.user_id == user_id)
			)
			last_updated = recent_update.scalar()

			return {
				'total_templates': total_templates,
				'default_templates': default_templates,
				'type_stats': type_stats,
				'last_updated': last_updated,
				'type_count': len(type_stats)
			}

		except Exception as e:
			raise RepositoryError(f"获取模板统计失败: {str(e)}")

	async def get_template_usage_summary (
			self,
			user_id: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取模板使用情况摘要

		Args:
			user_id: 用户ID
			start_date: 开始时间
			end_date: 结束时间

		Returns:
			模板使用情况摘要字典
		"""
		try:
			# 这里可以扩展，如果模板有使用记录的话
			# 目前先返回基本信息

			filters = [OrderTemplate.user_id == user_id]

			if start_date:
				filters.append(OrderTemplate.updated_at >= start_date)
			if end_date:
				filters.append(OrderTemplate.updated_at <= end_date)

			# 活跃模板数（最近30天更新过）
			thirty_days_ago = datetime.now() - timedelta(days=30)
			active_query = select(func.count()).select_from(OrderTemplate).where(
				and_(
					OrderTemplate.user_id == user_id,
					OrderTemplate.updated_at >= thirty_days_ago
				)
			)
			active_result = await self.session.execute(active_query)
			active_templates = active_result.scalar() or 0

			# 模板创建时间分布
			creation_stats = await self.session.execute(
				select(
					func.count(OrderTemplate.id).label('count'),
					func.min(OrderTemplate.created_at).label('oldest'),
					func.max(OrderTemplate.created_at).label('newest')
				)
				.where(and_(*filters))
			)

			creation_row = creation_stats.first()

			return {
				'active_templates': active_templates,
				'total_in_period': creation_row.count or 0,
				'oldest_template': creation_row.oldest,
				'newest_template': creation_row.newest
			}

		except Exception as e:
			raise RepositoryError(f"获取模板使用摘要失败: {str(e)}")

	# ==================== 模板操作方法 ====================

	async def set_default_template (
			self,
			user_id: str,
			template_id: str,
			template_type: Optional[str] = None
	) -> bool:
		"""
		设置默认模板

		Args:
			user_id: 用户ID
			template_id: 模板ID
			template_type: 模板类型（如果指定，则只设置该类型的默认模板）

		Returns:
			是否成功
		"""
		try:
			# 验证模板存在且属于该用户
			template = await self.get_by_template_id(template_id)
			if not template or template.user_id != user_id:
				return False

			# 开始事务
			await self.session.begin()

			try:
				# 首先取消同类型的所有默认模板
				reset_filters = [
					OrderTemplate.user_id == user_id,
					OrderTemplate.is_default == True
				]

				if template_type:
					reset_filters.append(OrderTemplate.template_type == template_type)
				elif template.template_type:
					reset_filters.append(OrderTemplate.template_type == template.template_type)

				reset_query = (
					update(OrderTemplate)
					.where(and_(*reset_filters))
					.values(is_default=False, updated_at=datetime.now())
				)
				await self.session.execute(reset_query)

				# 设置新默认模板
				set_query = (
					update(OrderTemplate)
					.where(OrderTemplate.id == template_id)
					.values(is_default=True, updated_at=datetime.now())
				)
				await self.session.execute(set_query)

				await self.session.commit()
				return True

			except Exception:
				await self.session.rollback()
				raise

		except Exception as e:
			raise RepositoryError(f"设置默认模板失败: {str(e)}")

	async def duplicate_template (
			self,
			user_id: str,
			template_id: str,
			new_template_name: str,
			new_description: Optional[str] = None
	) -> Optional[OrderTemplate]:
		"""
		复制模板

		Args:
			user_id: 用户ID
			template_id: 模板ID
			new_template_name: 新模板名称
			new_description: 新模板描述

		Returns:
			复制的模板对象或None
		"""
		try:
			# 获取原模板
			original_template = await self.get_by_template_id(template_id)
			if not original_template or original_template.user_id != user_id:
				return None

			# 检查新模板名称是否已存在
			existing_template = await self.get_by_template_name(user_id, new_template_name)
			if existing_template:
				raise RepositoryError(f"模板名称 '{new_template_name}' 已存在")

			# 创建新模板
			now = datetime.now()
			new_template_data = {
				'template_name': new_template_name,
				'user_id': user_id,
				'template_type': original_template.template_type,
				'parameters': original_template.parameters.copy() if original_template.parameters else {},
				'is_default': False,  # 复制的不设为默认
				'description': new_description or original_template.description or f"复制自: {original_template.template_name}",
				'created_at': now,
				'updated_at': now
			}

			new_template = await self.create(new_template_data)
			return new_template

		except Exception as e:
			raise RepositoryError(f"复制模板失败: {str(e)}")

	async def update_template_parameters (
			self,
			user_id: str,
			template_id: str,
			parameters: Dict[str, Any],
			description: Optional[str] = None
	) -> Optional[OrderTemplate]:
		"""
		更新模板参数

		Args:
			user_id: 用户ID
			template_id: 模板ID
			parameters: 新参数
			description: 新描述

		Returns:
			更新后的模板对象或None
		"""
		try:
			# 验证模板存在且属于该用户
			template = await self.get_by_template_id(template_id)
			if not template or template.user_id != user_id:
				return None

			update_data: Dict[str, Any] = {
				'parameters': parameters,
				'updated_at': datetime.now()
			}

			if description is not None:
				update_data['description'] = description

			updated_template = await self.update(template_id, update_data)
			return updated_template

		except Exception as e:
			raise RepositoryError(f"更新模板参数失败: {str(e)}")

	async def batch_delete_templates (
			self,
			user_id: str,
			template_ids: List[str]
	) -> int:
		"""
		批量删除模板

		Args:
			user_id: 用户ID
			template_ids: 模板ID列表

		Returns:
			删除的模板数
		"""
		try:
			if not template_ids:
				return 0

			# 验证所有模板都属于该用户
			templates = await self.get_many(
				and_(
					OrderTemplate.id.in_(template_ids),
					OrderTemplate.user_id == user_id
				)
			)

			if len(templates) != len(template_ids):
				raise RepositoryError("部分模板不存在或不属于该用户")

			# 检查是否包含默认模板
			default_templates = [t for t in templates if t.is_default]
			if default_templates:
				raise RepositoryError("不能删除默认模板，请先设置其他模板为默认")

			# 批量删除
			deleted_count = 0
			for template in templates:
				success = await self.delete(template.id)
				if success:
					deleted_count += 1

			return deleted_count

		except Exception as e:
			raise RepositoryError(f"批量删除模板失败: {str(e)}")

	# ==================== 模板导入导出方法 ====================

	async def export_template (
			self,
			user_id: str,
			template_id: str
	) -> Optional[Dict[str, Any]]:
		"""
		导出模板

		Args:
			user_id: 用户ID
			template_id: 模板ID

		Returns:
			模板导出数据字典或None
		"""
		try:
			template = await self.get_by_template_id(template_id, with_user=True)
			if not template or template.user_id != user_id:
				return None

			export_data = {
				'template_name': template.template_name,
				'template_type': template.template_type,
				'parameters': template.parameters,
				'description': template.description,
				'export_time': datetime.now().isoformat(),
				'export_version': '1.0',
				'metadata': {
					'original_id': template.id,
					'original_user_id': template.user_id,
					'original_username': template.user.username if template.user else None,
					'created_at': template.created_at.isoformat() if template.created_at else None,
					'updated_at': template.updated_at.isoformat() if template.updated_at else None
				}
			}

			return export_data

		except Exception as e:
			raise RepositoryError(f"导出模板失败: {str(e)}")

	async def import_template (
			self,
			user_id: str,
			import_data: Dict[str, Any],
			template_name: Optional[str] = None,
			is_default: bool = False
	) -> Optional[OrderTemplate]:
		"""
		导入模板

		Args:
			user_id: 用户ID
			import_data: 导入数据
			template_name: 模板名称（如果为空则使用导入数据中的名称）
			is_default: 是否设为默认模板

		Returns:
			导入的模板对象或None
		"""
		try:
			# 验证导入数据
			required_fields = ['template_name', 'template_type', 'parameters']
			for field in required_fields:
				if field not in import_data:
					raise RepositoryError(f"导入数据缺少必要字段: {field}")

			# 确定模板名称
			final_template_name = template_name or import_data['template_name']

			# 检查模板名称是否已存在
			existing_template = await self.get_by_template_name(user_id, final_template_name)
			if existing_template:
				# 如果存在，则生成新名称
				counter = 1
				while True:
					new_name = f"{final_template_name}_{counter}"
					existing = await self.get_by_template_name(user_id, new_name)
					if not existing:
						final_template_name = new_name
						break
					counter += 1

			# 创建模板
			now = datetime.now()
			template_data = {
				'template_name': final_template_name,
				'user_id': user_id,
				'template_type': import_data['template_type'],
				'parameters': import_data['parameters'],
				'is_default': is_default,
				'description': import_data.get('description', f"从导入数据创建: {import_data['template_name']}"),
				'created_at': now,
				'updated_at': now
			}

			new_template = await self.create(template_data)

			# 如果需要设为默认模板
			if is_default and new_template.template_type:
				await self.set_default_template(user_id, new_template.id, new_template.template_type)

			return new_template

		except Exception as e:
			raise RepositoryError(f"导入模板失败: {str(e)}")

	# ==================== 辅助方法 ====================

	@staticmethod
	def _build_order_by (order_by: str) -> List:
		"""
		构建排序子句

		Args:
			order_by: 排序字符串，格式：field_[asc/desc]

		Returns:
			排序子句列表
		"""
		order_mappings = {
			'template_name_asc': [asc(OrderTemplate.template_name)],
			'template_name_desc': [desc(OrderTemplate.template_name)],
			'created_at_asc': [asc(OrderTemplate.created_at)],
			'created_at_desc': [desc(OrderTemplate.created_at)],
			'updated_at_asc': [asc(OrderTemplate.updated_at)],
			'updated_at_desc': [desc(OrderTemplate.updated_at)],
			'template_type_asc': [asc(OrderTemplate.template_type)],
			'template_type_desc': [desc(OrderTemplate.template_type)],
		}

		return order_mappings.get(order_by, [desc(OrderTemplate.updated_at)])

	async def get_template_summary (self) -> Dict[str, Any]:
		"""
		获取模板数据摘要

		Returns:
			模板数据摘要字典
		"""
		try:
			# 总模板数
			total_templates = await self.count()

			# 今日新增模板数
			today = datetime.now().date()
			today_query = select(func.count()).select_from(OrderTemplate).where(
				and_(
					OrderTemplate.created_at >= today,
					OrderTemplate.created_at < today + timedelta(days=1)
				)
			)
			today_result = await self.session.execute(today_query)
			today_templates = today_result.scalar() or 0

			# 默认模板数
			default_query = select(func.count()).select_from(OrderTemplate).where(
				OrderTemplate.is_default == True
			)
			default_result = await self.session.execute(default_query)
			default_templates = default_result.scalar() or 0

			# 涉及用户数
			user_count = await self.session.execute(
				select(func.count(func.distinct(OrderTemplate.user_id)))
			)
			user_count_value = user_count.scalar() or 0

			# 模板类型统计
			type_stats = await self.session.execute(
				select(
					OrderTemplate.template_type,
					func.count(OrderTemplate.id).label('count')
				)
				.group_by(OrderTemplate.template_type)
			)

			type_dict = {}
			for row in type_stats.all():
				type_dict[row.template_type] = row.count

			# 日期范围
			date_range = await self.session.execute(
				select(
					func.min(OrderTemplate.created_at),
					func.max(OrderTemplate.created_at)
				)
			)
			min_time, max_time = date_range.first()

			return {
				'total_templates': total_templates,
				'today_templates': today_templates,
				'default_templates': default_templates,
				'user_count': user_count_value,
				'type_stats': type_dict,
				'type_count': len(type_dict),
				'date_range': {
					'min_time': min_time,
					'max_time': max_time
				}
			}

		except Exception as e:
			raise RepositoryError(f"获取模板摘要失败: {str(e)}")