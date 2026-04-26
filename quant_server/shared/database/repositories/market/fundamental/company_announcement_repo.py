# -*- coding: utf-8 -*-
"""
公司公告数据仓库（非时序数据）
继承BaseRepository，常规CRUD操作
位置：quant_server/shared/database/repositories/market/fundamental/company_announcement_repo.py
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.data_models import CompanyAnnouncement
from quant_server.shared.database.repositories.base.repository_base import BaseRepository


class CompanyAnnouncementRepository(BaseRepository[CompanyAnnouncement]):
	"""公司公告数据Repository - 继承BaseRepository，非时序数据"""

	def __init__ (self, session: AsyncSession):
		"""初始化公司公告仓库"""
		super().__init__(session, CompanyAnnouncement)

	# ==================== 业务查询方法 ====================

	async def get_by_ts_code (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			announcement_type: Optional[str] = None,
			limit: int = 100
	) -> List[CompanyAnnouncement]:
		"""
		根据股票代码获取公告

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			announcement_type: 公告类型
			limit: 返回数量限制

		Returns:
			公告列表
		"""
		filters: Dict[str, Any] = {"ts_code": ts_code}

		if announcement_type:
			filters["announcement_type"] = announcement_type

		# 日期范围过滤在数据库层面完成
		if start_date:
			filters["announcement_date__gte"] = start_date
		if end_date:
			filters["announcement_date__lte"] = end_date

		return await self.get_many(limit=limit, **filters)

	async def get_by_announcement_date (
			self,
			announcement_date: date,
			ts_codes: Optional[List[str]] = None,
			announcement_type: Optional[str] = None,
			limit: int = 1000
	) -> List[CompanyAnnouncement]:
		"""
		根据公告日期获取公告

		Args:
			announcement_date: 公告日期
			ts_codes: 股票代码列表（可选）
			announcement_type: 公告类型（可选）
			limit: 返回数量限制

		Returns:
			公告列表
		"""
		filters: Dict[str, Any] = {"announcement_date": announcement_date}

		if announcement_type:
			filters["announcement_type"] = announcement_type

		if ts_codes:
			# 使用in查询，避免循环查询
			filters["ts_code__in"] = ts_codes

		return await self.get_many(limit=limit, **filters)

	async def get_latest_announcements (
			self,
			ts_code: str,
			limit: int = 10
	) -> List[CompanyAnnouncement]:
		"""
		获取最新公告

		Args:
			ts_code: 股票代码
			limit: 返回数量限制

		Returns:
			最新公告列表
		"""
		query = select(CompanyAnnouncement).where(
			CompanyAnnouncement.ts_code == ts_code
		).order_by(
			desc(CompanyAnnouncement.announcement_date)
		).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def search_by_keyword (
			self,
			keyword: str,
			ts_code: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 50
	) -> List[CompanyAnnouncement]:
		"""
		根据关键词搜索公告

		Args:
			keyword: 搜索关键词
			ts_code: 股票代码（可选）
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）
			limit: 返回数量限制

		Returns:
			搜索结果列表
		"""
		query = select(CompanyAnnouncement).where(
			or_(
				CompanyAnnouncement.title.like(f"%{keyword}%"),
				CompanyAnnouncement.content.like(f"%{keyword}%")
			)
		)

		if ts_code:
			query = query.where(CompanyAnnouncement.ts_code == ts_code)

		if start_date:
			query = query.where(CompanyAnnouncement.announcement_date >= start_date)

		if end_date:
			query = query.where(CompanyAnnouncement.announcement_date <= end_date)

		query = query.order_by(desc(CompanyAnnouncement.announcement_date)).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_announcement_types (self, ts_code: str) -> List[str]:
		"""
		获取股票的公告类型列表

		Args:
			ts_code: 股票代码

		Returns:
			公告类型列表
		"""
		query = select(CompanyAnnouncement.announcement_type).distinct().where(
			CompanyAnnouncement.ts_code == ts_code
		)

		result = await self.session.execute(query)
		return [row[0] for row in result.fetchall() if row[0]]

	async def get_annual_reports (
			self,
			ts_code: str,
			years: Optional[List[int]] = None
	) -> List[CompanyAnnouncement]:
		"""
		获取年报

		Args:
			ts_code: 股票代码
			years: 年份列表（可选）

		Returns:
			年报列表
		"""
		query = select(CompanyAnnouncement).where(
			and_(
				CompanyAnnouncement.ts_code == ts_code,
				CompanyAnnouncement.announcement_type == "年报"
			)
		)

		if years:
			# 在数据库层面进行年份过滤
			year_conditions = []
			for year in years:
				start_date = datetime(year, 1, 1).date()
				end_date = datetime(year, 12, 31).date()
				year_conditions.append(
					and_(
						CompanyAnnouncement.announcement_date >= start_date,
						CompanyAnnouncement.announcement_date <= end_date
					)
				)
			query = query.where(or_(*year_conditions))

		query = query.order_by(desc(CompanyAnnouncement.announcement_date))
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_performance_forecasts (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[CompanyAnnouncement]:
		"""
		获取业绩预告

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			业绩预告列表
		"""
		filters: Dict[str, Any] = {
			"ts_code": ts_code,
			"announcement_type": "业绩预告"
		}

		# 日期范围过滤在数据库层面完成
		if start_date:
			filters["announcement_date__gte"] = start_date
		if end_date:
			filters["announcement_date__lte"] = end_date

		return await self.get_many(**filters)

	async def get_major_events (
			self,
			ts_code: str,
			event_types: Optional[List[str]] = None,
			limit: int = 50
	) -> List[CompanyAnnouncement]:
		"""
		获取重大事项公告

		Args:
			ts_code: 股票代码
			event_types: 事件类型列表（重大合同、资产重组、股权变动等）
			limit: 返回数量限制

		Returns:
			重大事项公告列表
		"""
		query = select(CompanyAnnouncement).where(
			and_(
				CompanyAnnouncement.ts_code == ts_code,
				CompanyAnnouncement.announcement_type == "重大事项"
			)
		)

		if event_types:
			# 进一步按事件类型过滤
			event_type_conditions = []
			for event_type in event_types:
				event_type_conditions.append(
					CompanyAnnouncement.title.like(f"%{event_type}%")
				)
			if event_type_conditions:
				query = query.where(or_(*event_type_conditions))

		query = query.order_by(desc(CompanyAnnouncement.announcement_date)).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_dividend_announcements (
			self,
			ts_code: str,
			year: Optional[int] = None
	) -> List[CompanyAnnouncement]:
		"""
		获取分红公告

		Args:
			ts_code: 股票代码
			year: 年份（可选）

		Returns:
			分红公告列表
		"""
		query = select(CompanyAnnouncement).where(
			and_(
				CompanyAnnouncement.ts_code == ts_code,
				CompanyAnnouncement.announcement_type == "利润分配"
			)
		)

		if year:
			# 在数据库层面进行年份过滤
			start_date = datetime(year, 1, 1).date()
			end_date = datetime(year, 12, 31).date()
			query = query.where(
				and_(
					CompanyAnnouncement.announcement_date >= start_date,
					CompanyAnnouncement.announcement_date <= end_date
				)
			)

		query = query.order_by(desc(CompanyAnnouncement.announcement_date))
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_announcement_statistics (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		获取公告统计信息

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			统计信息字典
		"""
		# 查询各种类型的公告数量
		query = text("""
            SELECT announcement_type, COUNT(*) as count
            FROM company_announcements
            WHERE ts_code = :ts_code
              AND announcement_date >= :start_date
              AND announcement_date <= :end_date
            GROUP BY announcement_type
            ORDER BY count DESC
        """)

		result = await self.session.execute(
			query,
			{"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
		)
		type_counts = result.fetchall()

		# 计算总公告数
		total_query = select(func.count()).where(
			and_(
				CompanyAnnouncement.ts_code == ts_code,
				CompanyAnnouncement.announcement_date >= start_date,
				CompanyAnnouncement.announcement_date <= end_date
			)
		)
		total_result = await self.session.execute(total_query)
		total = total_result.scalar() or 0

		# 获取最新公告日期
		latest_query = select(func.max(CompanyAnnouncement.announcement_date)).where(
			CompanyAnnouncement.ts_code == ts_code
		)
		latest_result = await self.session.execute(latest_query)
		latest_date = latest_result.scalar()

		return {
			"ts_code": ts_code,
			"period": {"start": start_date, "end": end_date},
			"total_count": total,
			"latest_announcement_date": latest_date,
			"type_distribution": [
				{"type": row[0], "count": row[1]}
				for row in type_counts
			]
		}

	async def get_announcement_calendar (
			self,
			start_date: date,
			end_date: date,
			announcement_types: Optional[List[str]] = None,
			ts_codes: Optional[List[str]] = None,
			limit_per_day: int = 50
	) -> Dict[date, List[CompanyAnnouncement]]:
		"""
		获取公告日历

		Args:
			start_date: 开始日期
			end_date: 结束日期
			announcement_types: 公告类型列表
			ts_codes: 股票代码列表
			limit_per_day: 每天最多返回数量

		Returns:
			按日期分组的公告字典
		"""
		# 构建查询条件
		filters: Dict[str, Any] = {"announcement_date__gte": start_date, "announcement_date__lte": end_date}

		if announcement_types:
			filters["announcement_type__in"] = announcement_types

		if ts_codes:
			filters["ts_code__in"] = ts_codes

		# 一次性查询所有符合条件的公告
		all_announcements = await self.get_many(**filters)

		# 按日期分组
		calendar = {}
		for announcement in all_announcements:
			ann_date = announcement.announcement_date.date()
			if ann_date not in calendar:
				calendar[ann_date] = []
			calendar[ann_date].append(announcement)

		# 对每天的数据进行排序和限制
		for date_key in calendar:
			calendar[date_key].sort(key=lambda x: x.importance_level, reverse=True)
			calendar[date_key] = calendar[date_key][:limit_per_day]

		return calendar

	# ==================== 批量操作 ====================

	async def batch_upsert_announcements (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[CompanyAnnouncement]:
		"""
		批量插入或更新公告记录

		Args:
			data_list: 数据列表

		Returns:
			更新后的公告记录列表
		"""
		return await self.batch_upsert(
			match_fields=["ts_code", "announcement_date", "title"],
			data_list=data_list
		)

	async def delete_old_announcements (
			self,
			before_date: date,
			ts_code: Optional[str] = None
	) -> int:
		"""
		删除指定日期之前的公告

		Args:
			before_date: 截止日期
			ts_code: 股票代码（可选）

		Returns:
			删除的记录数
		"""
		filters: Dict[str, Any] = {"announcement_date__lt": before_date}

		if ts_code:
			filters["ts_code"] = ts_code

		return await self.delete_by(**filters)
