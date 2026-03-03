# # -*- coding: utf-8 -*-
# """
# 公司公告数据仓库（非时序数据）
# 继承BaseRepository，常规CRUD操作
# 位置：quant_server/shared/database/repositories/market/fundamental/company_announcement_repo.py
# """
#
# from typing import List, Optional, Dict, Any, Tuple
# from datetime import date, datetime, timedelta
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_, or_, func, desc, asc, text
# from sqlalchemy.sql import Select
#
# from quant_server.shared.database.repositories.base.repository_base import BaseRepository
# from quant_server.shared.database.models.data_models import CompanyAnnouncement
#
#
# class CompanyAnnouncementRepository(BaseRepository[CompanyAnnouncement]):
# 	"""公司公告数据Repository - 继承BaseRepository，非时序数据"""
#
# 	def __init__ (self, session: AsyncSession):
# 		"""初始化公司公告仓库"""
# 		super().__init__(session, CompanyAnnouncement)
#
# 	# ==================== 业务查询方法 ====================
#
# 	async def get_by_ts_code (
# 			self,
# 			ts_code: str,
# 			start_date: Optional[date] = None,
# 			end_date: Optional[date] = None,
# 			announcement_type: Optional[str] = None,
# 			limit: int = 100
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		根据股票代码获取公告
#
# 		Args:
# 			ts_code: 股票代码
# 			start_date: 开始日期
# 			end_date: 结束日期
# 			announcement_type: 公告类型
# 			limit: 返回数量限制
#
# 		Returns:
# 			公告列表
# 		"""
# 		filters = {"ts_code": ts_code}
#
# 		if announcement_type:
# 			filters["announcement_type"] = announcement_type
#
# 		# 获取查询结果
# 		announcements = await self.get_many(limit=limit, **filters)
#
# 		# 过滤日期范围
# 		if start_date or end_date:
# 			filtered = []
# 			for ann in announcements:
# 				ann_date = ann.announcement_date
# 				if start_date and ann_date < start_date:
# 					continue
# 				if end_date and ann_date > end_date:
# 					continue
# 				filtered.append(ann)
# 			return filtered
#
# 		return announcements
#
# 	async def get_by_announcement_date (
# 			self,
# 			announcement_date: date,
# 			ts_codes: Optional[List[str]] = None,
# 			announcement_type: Optional[str] = None,
# 			limit: int = 1000
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		根据公告日期获取公告
#
# 		Args:
# 			announcement_date: 公告日期
# 			ts_codes: 股票代码列表（可选）
# 			announcement_type: 公告类型（可选）
# 			limit: 返回数量限制
#
# 		Returns:
# 			公告列表
# 		"""
# 		filters = {"announcement_date": announcement_date}
#
# 		if announcement_type:
# 			filters["announcement_type"] = announcement_type
#
# 		if ts_codes:
# 			# 使用in查询
# 			announcements = []
# 			for ts_code in ts_codes:
# 				filters_copy = filters.copy()
# 				filters_copy["ts_code"] = ts_code
# 				result = await self.get_many(limit=limit, **filters_copy)
# 				announcements.extend(result)
# 			return announcements
#
# 		return await self.get_many(limit=limit, **filters)
#
# 	async def get_latest_announcements (
# 			self,
# 			ts_code: str,
# 			limit: int = 10
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		获取最新公告
#
# 		Args:
# 			ts_code: 股票代码
# 			limit: 返回数量限制
#
# 		Returns:
# 			最新公告列表
# 		"""
# 		query = select(CompanyAnnouncement).where(
# 			CompanyAnnouncement.ts_code == ts_code
# 		).order_by(
# 			desc(CompanyAnnouncement.announcement_date)
# 		).limit(limit)
#
# 		result = await self.session.execute(query)
# 		return result.scalars().all()
#
# 	async def search_by_keyword (
# 			self,
# 			keyword: str,
# 			ts_code: Optional[str] = None,
# 			start_date: Optional[date] = None,
# 			end_date: Optional[date] = None,
# 			limit: int = 50
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		根据关键词搜索公告
#
# 		Args:
# 			keyword: 搜索关键词
# 			ts_code: 股票代码（可选）
# 			start_date: 开始日期（可选）
# 			end_date: 结束日期（可选）
# 			limit: 返回数量限制
#
# 		Returns:
# 			搜索结果列表
# 		"""
# 		query = select(CompanyAnnouncement).where(
# 			or_(
# 				CompanyAnnouncement.title.like(f"%{keyword}%"),
# 				CompanyAnnouncement.content.like(f"%{keyword}%")
# 			)
# 		)
#
# 		if ts_code:
# 			query = query.where(CompanyAnnouncement.ts_code == ts_code)
#
# 		if start_date:
# 			query = query.where(CompanyAnnouncement.announcement_date >= start_date)
#
# 		if end_date:
# 			query = query.where(CompanyAnnouncement.announcement_date <= end_date)
#
# 		query = query.order_by(desc(CompanyAnnouncement.announcement_date)).limit(limit)
#
# 		result = await self.session.execute(query)
# 		return result.scalars().all()
#
# 	async def get_announcement_types (self, ts_code: str) -> List[str]:
# 		"""
# 		获取股票的公告类型列表
#
# 		Args:
# 			ts_code: 股票代码
#
# 		Returns:
# 			公告类型列表
# 		"""
# 		query = select(CompanyAnnouncement.announcement_type).distinct().where(
# 			CompanyAnnouncement.ts_code == ts_code
# 		)
#
# 		result = await self.session.execute(query)
# 		return [row[0] for row in result.fetchall() if row[0]]
#
# 	async def get_annual_reports (
# 			self,
# 			ts_code: str,
# 			years: Optional[List[int]] = None
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		获取年报
#
# 		Args:
# 			ts_code: 股票代码
# 			years: 年份列表（可选）
#
# 		Returns:
# 			年报列表
# 		"""
# 		query = select(CompanyAnnouncement).where(
# 			and_(
# 				CompanyAnnouncement.ts_code == ts_code,
# 				CompanyAnnouncement.announcement_type == "年报"
# 			)
# 		)
#
# 		if years:
# 			# 按年份过滤
# 			filtered = []
# 			result = await self.session.execute(query)
# 			announcements = result.scalars().all()
#
# 			for ann in announcements:
# 				# 从标题或内容中提取年份
# 				import re
# 				year_match = re.search(r'\d{4}', ann.title or "")
# 				if year_match:
# 					year = int(year_match.group())
# 					if year in years:
# 						filtered.append(ann)
# 			return filtered
#
# 		query = query.order_by(desc(CompanyAnnouncement.announcement_date))
# 		result = await self.session.execute(query)
# 		return result.scalars().all()
#
# 	async def get_performance_forecasts (
# 			self,
# 			ts_code: str,
# 			start_date: Optional[date] = None,
# 			end_date: Optional[date] = None
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		获取业绩预告
#
# 		Args:
# 			ts_code: 股票代码
# 			start_date: 开始日期
# 			end_date: 结束日期
#
# 		Returns:
# 			业绩预告列表
# 		"""
# 		filters = {
# 			"ts_code": ts_code,
# 			"announcement_type": "业绩预告"
# 		}
#
# 		announcements = await self.get_many(**filters)
#
# 		# 过滤日期范围
# 		if start_date or end_date:
# 			filtered = []
# 			for ann in announcements:
# 				ann_date = ann.announcement_date
# 				if start_date and ann_date < start_date:
# 					continue
# 				if end_date and ann_date > end_date:
# 					continue
# 				filtered.append(ann)
# 			return filtered
#
# 		return announcements
#
# 	async def get_major_events (
# 			self,
# 			ts_code: str,
# 			event_types: Optional[List[str]] = None,
# 			limit: int = 50
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		获取重大事项公告
#
# 		Args:
# 			ts_code: 股票代码
# 			event_types: 事件类型列表（重大合同、资产重组、股权变动等）
# 			limit: 返回数量限制
#
# 		Returns:
# 			重大事项公告列表
# 		"""
# 		query = select(CompanyAnnouncement).where(
# 			and_(
# 				CompanyAnnouncement.ts_code == ts_code,
# 				CompanyAnnouncement.announcement_type == "重大事项"
# 			)
# 		)
#
# 		if event_types:
# 			# 进一步按事件类型过滤
# 			event_type_conditions = []
# 			for event_type in event_types:
# 				event_type_conditions.append(
# 					CompanyAnnouncement.title.like(f"%{event_type}%")
# 				)
# 			if event_type_conditions:
# 				query = query.where(or_(*event_type_conditions))
#
# 		query = query.order_by(desc(CompanyAnnouncement.announcement_date)).limit(limit)
#
# 		result = await self.session.execute(query)
# 		return result.scalars().all()
#
# 	async def get_dividend_announcements (
# 			self,
# 			ts_code: str,
# 			year: Optional[int] = None
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		获取分红公告
#
# 		Args:
# 			ts_code: 股票代码
# 			year: 年份（可选）
#
# 		Returns:
# 			分红公告列表
# 		"""
# 		query = select(CompanyAnnouncement).where(
# 			and_(
# 				CompanyAnnouncement.ts_code == ts_code,
# 				CompanyAnnouncement.announcement_type == "利润分配"
# 			)
# 		)
#
# 		result = await self.session.execute(query)
# 		announcements = result.scalars().all()
#
# 		if year:
# 			# 按年份过滤
# 			filtered = []
# 			import re
# 			for ann in announcements:
# 				# 从标题中提取年份
# 				year_match = re.search(r'\d{4}', ann.title or "")
# 				if year_match:
# 					announcement_year = int(year_match.group())
# 					if announcement_year == year:
# 						filtered.append(ann)
# 			return filtered
#
# 		return announcements
#
# 	async def get_announcement_statistics (
# 			self,
# 			ts_code: str,
# 			start_date: date,
# 			end_date: date
# 	) -> Dict[str, Any]:
# 		"""
# 		获取公告统计信息
#
# 		Args:
# 			ts_code: 股票代码
# 			start_date: 开始日期
# 			end_date: 结束日期
#
# 		Returns:
# 			统计信息字典
# 		"""
# 		# 查询各种类型的公告数量
# 		query = text("""
#             SELECT announcement_type, COUNT(*) as count
#             FROM company_announcements
#             WHERE ts_code = :ts_code
#               AND announcement_date >= :start_date
#               AND announcement_date <= :end_date
#             GROUP BY announcement_type
#             ORDER BY count DESC
#         """)
#
# 		result = await self.session.execute(
# 			query,
# 			{"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
# 		)
# 		type_counts = result.fetchall()
#
# 		# 计算总公告数
# 		total_query = select(func.count()).where(
# 			and_(
# 				CompanyAnnouncement.ts_code == ts_code,
# 				CompanyAnnouncement.announcement_date >= start_date,
# 				CompanyAnnouncement.announcement_date <= end_date
# 			)
# 		)
# 		total_result = await self.session.execute(total_query)
# 		total = total_result.scalar() or 0
#
# 		# 获取最新公告日期
# 		latest_query = select(func.max(CompanyAnnouncement.announcement_date)).where(
# 			CompanyAnnouncement.ts_code == ts_code
# 		)
# 		latest_result = await self.session.execute(latest_query)
# 		latest_date = latest_result.scalar()
#
# 		return {
# 			"ts_code": ts_code,
# 			"period": {"start": start_date, "end": end_date},
# 			"total_count": total,
# 			"latest_announcement_date": latest_date,
# 			"type_distribution": [
# 				{"type": row[0], "count": row[1]}
# 				for row in type_counts
# 			]
# 		}
#
# 	async def get_announcement_calendar (
# 			self,
# 			start_date: date,
# 			end_date: date,
# 			announcement_types: Optional[List[str]] = None,
# 			ts_codes: Optional[List[str]] = None,
# 			limit_per_day: int = 50
# 	) -> Dict[date, List[CompanyAnnouncement]]:
# 		"""
# 		获取公告日历
#
# 		Args:
# 			start_date: 开始日期
# 			end_date: 结束日期
# 			announcement_types: 公告类型列表
# 			ts_codes: 股票代码列表
# 			limit_per_day: 每天最多返回数量
#
# 		Returns:
# 			按日期分组的公告字典
# 		"""
# 		calendar = {}
# 		current_date = start_date
#
# 		while current_date <= end_date:
# 			filters = {"announcement_date": current_date}
#
# 			if announcement_types:
# 				# 获取该日期所有符合条件的公告
# 				announcements = []
# 				for ann_type in announcement_types:
# 					filters_copy = filters.copy()
# 					filters_copy["announcement_type"] = ann_type
# 					if ts_codes:
# 						# 如果指定了股票代码，需要分别查询
# 						for ts_code in ts_codes:
# 							filters_copy["ts_code"] = ts_code
# 							result = await self.get_many(limit=limit_per_day, **filters_copy)
# 							announcements.extend(result)
# 					else:
# 						result = await self.get_many(limit=limit_per_day, **filters_copy)
# 						announcements.extend(result)
# 			else:
# 				if ts_codes:
# 					announcements = []
# 					for ts_code in ts_codes:
# 						filters_copy = filters.copy()
# 						filters_copy["ts_code"] = ts_code
# 						result = await self.get_many(limit=limit_per_day, **filters_copy)
# 						announcements.extend(result)
# 				else:
# 					announcements = await self.get_many(limit=limit_per_day, **filters)
#
# 			if announcements:
# 				calendar[current_date] = announcements
#
# 			current_date += timedelta(days=1)
#
# 		return calendar
#
# 	# ==================== 批量操作 ====================
#
# 	async def batch_upsert_announcements (
# 			self,
# 			data_list: List[Dict[str, Any]]
# 	) -> List[CompanyAnnouncement]:
# 		"""
# 		批量插入或更新公告记录
#
# 		Args:
# 			data_list: 数据列表
#
# 		Returns:
# 			更新后的公告记录列表
# 		"""
# 		return await self.batch_upsert(
# 			match_fields=["ts_code", "announcement_date", "title"],
# 			data_list=data_list
# 		)
#
# 	async def delete_old_announcements (
# 			self,
# 			before_date: date,
# 			ts_code: Optional[str] = None
# 	) -> int:
# 		"""
# 		删除指定日期之前的公告
#
# 		Args:
# 			before_date: 截止日期
# 			ts_code: 股票代码（可选）
#
# 		Returns:
# 			删除的记录数
# 		"""
# 		filters = {"announcement_date__lt": before_date}
#
# 		if ts_code:
# 			filters["ts_code"] = ts_code
#
# 		return await self.delete_by(**filters)