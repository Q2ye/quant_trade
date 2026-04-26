# -*- coding: utf-8 -*-
"""
上市公司管理层数据仓库
提供公司管理层信息的统一访问接口
位置：shared/database/repositories/market/governance/manager_repository.py

设计原则：
1. 继承BaseRepository基类：获得标准CRUD功能
2. 纯数据访问：只做CRUD，不做业务逻辑
3. 按业务领域组织：专门处理管理层相关数据查询
"""

from datetime import date
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.data_models import StkManager
from quant_server.shared.database.repositories.base import BaseRepository


class ManagerRepository(BaseRepository[StkManager]):
	"""上市公司管理层数据Repository - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化管理层Repository

		Args:
			session: 数据库会话，提供数据访问上下文
		"""
		super().__init__(session, StkManager)

	# ==================== 基础CRUD操作 ====================
	# 继承自BaseRepository，包含：get, create, update, delete, get_by, get_many, get_all, count, exists等

	# ==================== 业务查询方法 ====================

	async def get_by_ts_code (
			self,
			ts_code: str,
			lev: Optional[str] = None,
			limit: int = 100
	) -> List[StkManager]:
		"""
		根据股票代码获取管理层记录

		Args:
			ts_code: 股票代码
			lev: 职位（可选）
			limit: 返回记录数限制

		Returns:
			管理层记录列表
		"""
		filters = [self.model.ts_code == ts_code]

		if lev:
			filters.append(self.model.lev == lev)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=self.model.begin_date.desc()
		)

	async def get_by_manager_name (
			self,
			name: str,
			fuzzy: bool = True,
			limit: int = 50
	) -> List[StkManager]:
		"""
		根据管理层姓名获取记录

		Args:
			name: 姓名
			fuzzy: 是否模糊匹配
			limit: 返回记录数限制

		Returns:
			管理层记录列表
		"""
		if fuzzy:
			filters = [self.model.name.like(f"%{name}%")]
		else:
			filters = [self.model.name == name]

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=self.model.begin_date.desc()
		)

	async def get_by_position (
			self,
			lev: str,
			ts_codes: Optional[List[str]] = None,
			limit: int = 100
	) -> List[StkManager]:
		"""
		根据职位获取管理层记录

		Args:
			lev: 职位名称
			ts_codes: 股票代码列表（可选）
			limit: 返回记录数限制

		Returns:
			管理层记录列表
		"""
		filters: List[any] = [self.model.lev == lev]

		if ts_codes:
			filters.append(self.model.ts_code.in_(ts_codes))

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=self.model.begin_date.desc()
		)

	async def get_current_managers (
			self,
			ts_code: str,
			date_point: Optional[date] = None
	) -> List[StkManager]:
		"""
		获取指定日期的在职管理层

		Args:
			ts_code: 股票代码
			date_point: 日期点（默认当前日期）

		Returns:
			在职管理层记录列表
		"""
		if date_point is None:
			date_point = date.today()

		# 查询条件：任命日期早于等于指定日期，且离任日期为空或晚于指定日期
		filters = [
			self.model.ts_code == ts_code,
			self.model.begin_date <= date_point,
			or_(
				self.model.end_date.is_(None),
				self.model.end_date > date_point
			)
		]

		return await self.get_many(
			*filters,
			order_by=self.model.lev.asc()
		)

	async def get_manager_history (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[StkManager]:
		"""
		获取管理层历史记录

		Args:
			ts_code: 股票代码
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）

		Returns:
			管理层历史记录列表
		"""
		filters = [self.model.ts_code == ts_code]

		if start_date:
			filters.append(
				or_(
					self.model.end_date.is_(None),
					self.model.end_date >= start_date
				)
			)

		if end_date:
			filters.append(self.model.begin_date <= end_date)

		return await self.get_many(
			*filters,
			order_by=self.model.begin_date.desc()
		)

	async def get_managers_by_date_range (
			self,
			start_date: date,
			end_date: date,
			lev: Optional[str] = None,
			ts_codes: Optional[List[str]] = None
	) -> List[StkManager]:
		"""
		根据日期范围获取管理层记录

		Args:
			start_date: 开始日期
			end_date: 结束日期
			lev: 职位（可选）
			ts_codes: 股票代码列表（可选）

		Returns:
			管理层记录列表
		"""
		filters = [
			self.model.begin_date <= end_date,
			or_(
				self.model.end_date.is_(None),
				self.model.end_date >= start_date
			)
		]

		if lev:
			filters.append(self.model.lev == lev)

		if ts_codes:
			filters.append(self.model.ts_code.in_(ts_codes))

		return await self.get_many(
			*filters,
			order_by=self.model.begin_date.desc()
		)

	async def get_top_companies_by_manager_count (
			self,
			lev: Optional[str] = None,
			top_n: int = 20
	) -> List[Dict[str, Any]]:
		"""
		获取管理层数量最多的公司

		Args:
			lev: 职位（可选）
			top_n: 返回数量

		Returns:
			公司管理层统计列表
		"""
		query = select(
			self.model.ts_code,
			func.count(self.model.id).label('manager_count'),
			func.count(distinct(self.model.name)).label('unique_manager_count')
		)

		if lev:
			query = query.where(self.model.lev == lev)

		query = query.group_by(
			self.model.ts_code
		).order_by(
			func.count(self.model.id).desc()
		).limit(top_n)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row.ts_code,
				'manager_count': row.manager_count,
				'unique_manager_count': row.unique_manager_count
			}
			for row in rows
		]

	async def get_manager_statistics (
			self,
			ts_code: Optional[str] = None,
			lev: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取管理层统计信息

		Args:
			ts_code: 股票代码（可选）
			lev: 职位（可选）

		Returns:
			管理层统计信息
		"""
		query = select(
			func.count(self.model.id).label('total_count'),
			func.count(distinct(self.model.ts_code)).label('company_count'),
			func.count(distinct(self.model.name)).label('unique_manager_count')
		)

		filters = []
		if ts_code:
			filters.append(self.model.ts_code == ts_code)
		if lev:
			filters.append(self.model.lev == lev)

		if filters:
			query = query.where(and_(*filters))

		result = await self.session.execute(query)
		row = result.first()

		if not row:
			return {}

		return {
			'ts_code': ts_code,
			'lev': lev,
			'total_count': row.total_count or 0,
			'company_count': row.company_count or 0,
			'unique_manager_count': row.unique_manager_count or 0
		}

	async def get_education_statistics (
			self,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取管理层教育背景统计

		Args:
			ts_code: 股票代码（可选）

		Returns:
			教育背景统计信息
		"""
		query = select(
			self.model.edu,
			func.count(self.model.id).label('count')
		)

		if ts_code:
			query = query.where(self.model.ts_code == ts_code)

		query = query.group_by(
			self.model.edu
		).order_by(
			func.count(self.model.id).desc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		return {
			'ts_code': ts_code,
			'education_stats': [
				{
					'education': row.edu or '未知',
					'count': row.count or 0
				}
				for row in rows
			]
		}

	async def get_gender_statistics (
			self,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取管理层性别统计

		Args:
			ts_code: 股票代码（可选）

		Returns:
			性别统计信息
		"""
		query = select(
			self.model.gender,
			func.count(self.model.id).label('count')
		)

		if ts_code:
			query = query.where(self.model.ts_code == ts_code)

		query = query.group_by(
			self.model.gender
		).order_by(
			func.count(self.model.id).desc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		return {
			'ts_code': ts_code,
			'gender_stats': [
				{
					'gender': row.gender or '未知',
					'count': row.count or 0
				}
				for row in rows
			]
		}

	async def get_lev_distribution (
			self,
			ts_code: str
	) -> List[Dict[str, Any]]:
		"""
		获取职位分布

		Args:
			ts_code: 股票代码

		Returns:
			职位分布列表
		"""
		query = select(
			self.model.lev,
			func.count(self.model.id).label('count'),
			func.avg(
				func.extract('year', func.age(self.model.end_date, self.model.begin_date))
			).label('avg_tenure_years')
		).where(
			self.model.ts_code == ts_code
		).group_by(
			self.model.lev
		).order_by(
			func.count(self.model.id).desc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'lev': row.lev,
				'count': row.count or 0,
				'avg_tenure_years': float(row.avg_tenure_years) if row.avg_tenure_years else None
			}
			for row in rows
		]

	async def get_manager_tenure_statistics (
			self,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取管理层任期统计

		Args:
			ts_code: 股票代码（可选）

		Returns:
			任期统计信息
		"""
		# 只统计已离任的管理层（有离任日期）
		query = select(
			func.avg(
				func.extract('year', func.age(self.model.end_date, self.model.begin_date))
			).label('avg_tenure_years'),
			func.min(
				func.extract('year', func.age(self.model.end_date, self.model.begin_date))
			).label('min_tenure_years'),
			func.max(
				func.extract('year', func.age(self.model.end_date, self.model.begin_date))
			).label('max_tenure_years'),
			func.count(self.model.id).label('count')
		).where(
			self.model.end_date.isnot(None)
		)

		if ts_code:
			query = query.where(self.model.ts_code == ts_code)

		result = await self.session.execute(query)
		row = result.first()

		if not row:
			return {}

		return {
			'ts_code': ts_code,
			'avg_tenure_years': float(row.avg_tenure_years) if row.avg_tenure_years else None,
			'min_tenure_years': float(row.min_tenure_years) if row.min_tenure_years else None,
			'max_tenure_years': float(row.max_tenure_years) if row.max_tenure_years else None,
			'count': row.count or 0
		}

	async def search_managers (
			self,
			keyword: str,
			fields: List[str] = None,
			limit: int = 50
	) -> List[StkManager]:
		"""
		搜索管理层信息

		Args:
			keyword: 关键词
			fields: 搜索字段列表（默认搜索姓名和职位）
			limit: 返回记录数限制

		Returns:
			管理层记录列表
		"""
		if fields is None:
			fields = ['manager_name', 'lev', 'education', 'background']

		filters = []
		for field in fields:
			if hasattr(self.model, field):
				filters.append(getattr(self.model, field).like(f"%{keyword}%"))

		if not filters:
			return []

		return await self.get_many(
			or_(*filters),
			limit=limit,
			order_by=self.model.begin_date.desc()
		)

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[StkManager]:
		"""
		批量创建管理层记录

		Args:
			data_list: 管理层记录数据列表

		Returns:
			创建的StkManager对象列表
		"""
		return await super().batch_create(data_list)

	async def batch_upsert (
			self,
			match_fields: List[str],
			data_list: List[Dict[str, Any]],
			update_fields: List[str] = None
	) -> List[StkManager]:
		"""
		批量插入或更新管理层记录

		Args:
			match_fields: 匹配字段，用于判断记录是否存在
			data_list: 管理层记录数据列表
			update_fields: 更新字段列表

		Returns:
			StkManager对象列表
		"""
		return await super().batch_upsert(match_fields, data_list, update_fields)

	async def get_manager_summary (self) -> Dict[str, Any]:
		"""
		获取管理层数据摘要

		Returns:
			数据摘要信息
		"""
		# 总记录数
		total_count = await self.count()

		# 涉及公司数量
		company_count = await self.session.execute(
			select(func.count(func.distinct(self.model.ts_code)))
		)
		company_count_value = company_count.scalar() or 0

		# 涉及管理层人数
		unique_manager_count = await self.session.execute(
			select(func.count(func.distinct(self.model.name)))
		)
		unique_manager_count_value = unique_manager_count.scalar() or 0

		# 职位类型数量
		lev_count = await self.session.execute(
			select(func.count(func.distinct(self.model.lev)))
		)
		lev_count_value = lev_count.scalar() or 0



		# 教育背景分布（前10）
		education_dist = await self.session.execute(
			select(
				self.model.edu,
				func.count(self.model.id).label('count')
			).group_by(
				self.model.edu
			).order_by(
				func.count(self.model.id).desc()
			).limit(10)
		)

		education_stats = [
			{
				'education': row.edu or '未知',
				'count': row.count or 0
			}
			for row in education_dist.all()
		]

		# 性别分布
		gender_dist = await self.session.execute(
			select(
				self.model.gender,
				func.count(self.model.id).label('count')
			).group_by(
				self.model.gender
			).order_by(
				func.count(self.model.id).desc()
			)
		)

		gender_stats = [
			{
				'gender': row.gender or '未知',
				'count': row.count or 0
			}
			for row in gender_dist.all()
		]

		return {
			'total_count': total_count,
			'company_count': company_count_value,
			'unique_manager_count': unique_manager_count_value,
			'lev_count': lev_count_value,
			'education_stats': education_stats,
			'gender_stats': gender_stats
		}