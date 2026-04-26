# -*- coding: utf-8 -*-
"""
数据修复记录表Repository
位置：shared/database/repositories/market/data_fix_record_repo.py
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import DataFixRecord
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError


class DataFixRecordRepository(BaseRepository[DataFixRecord]):
	"""数据修复记录Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, DataFixRecord)

	async def create_fix_record (
			self,
			data_type: str,
			fix_type: str,
			records_fixed: int,
			fix_details: Dict[str, Any],
			quality_check_id: Optional[int] = None,
			fix_status: str = "completed",
			fixed_by: Optional[str] = None
	) -> DataFixRecord:
		"""
		创建数据修复记录

		Args:
			data_type: 数据类型
			fix_type: 修复类型（missing/duplicate/invalid）
			records_fixed: 修复记录数
			fix_details: 修复详情
			quality_check_id: 质量检查ID
			fix_status: 修复状态
			fixed_by: 修复人/系统

		Returns:
			数据修复记录
		"""
		try:
			data = {
				"quality_check_id": quality_check_id,
				"data_type": data_type,
				"fix_type": fix_type,
				"records_fixed": records_fixed,
				"fix_details": fix_details or {},
				"fix_status": fix_status,
				"fixed_by": fixed_by
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建数据修复记录失败: {str(e)}")

	async def get_by_quality_check_id (
			self,
			quality_check_id: str
	) -> List[DataFixRecord]:
		"""
		根据质量检查ID获取修复记录

		Args:
			quality_check_id: 质量检查ID

		Returns:
			数据修复记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.quality_check_id == quality_check_id
			).order_by(
				desc(self.model.fix_date)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取质量检查修复记录失败: {str(e)}")

	async def get_by_data_type (
			self,
			data_type: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 100
	) -> List[DataFixRecord]:
		"""
		根据数据类型获取修复记录

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			数据修复记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.data_type == data_type
			)

			if start_date:
				query = query.where(self.model.fix_date >= start_date)
			if end_date:
				query = query.where(self.model.fix_date <= end_date)

			query = query.order_by(desc(self.model.fix_date)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取数据类型修复记录失败: {str(e)}")

	async def get_by_fix_type (
			self,
			fix_type: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> List[DataFixRecord]:
		"""
		根据修复类型获取记录

		Args:
			fix_type: 修复类型
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			数据修复记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.fix_type == fix_type
			)

			if start_date:
				query = query.where(self.model.fix_date >= start_date)
			if end_date:
				query = query.where(self.model.fix_date <= end_date)

			query = query.order_by(desc(self.model.fix_date))

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取修复类型记录失败: {str(e)}")

	async def get_fix_statistics (
			self,
			start_date: datetime,
			end_date: datetime,
			data_type: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取修复统计信息

		Args:
			start_date: 开始日期
			end_date: 结束日期
			data_type: 数据类型

		Returns:
			修复统计信息
		"""
		try:
			query = select(
				func.count().label("total_fixes"),
				func.sum(self.model.records_fixed).label("total_records_fixed"),
				self.model.fix_type,
				self.model.data_type
			).where(
				and_(
					self.model.fix_date >= start_date,
					self.model.fix_date <= end_date,
					self.model.fix_status == "completed"
				)
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)

			query = query.group_by(
				self.model.fix_type,
				self.model.data_type
			).order_by(
				desc("total_records_fixed")
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			total_fixes = 0
			total_records_fixed = 0
			fixes_by_type = {}
			fixes_by_data_type = {}

			for row in rows:
				total_fixes += row.total_fixes or 0
				total_records_fixed += row.total_records_fixed or 0

				# 按修复类型统计
				fix_type = row.fix_type
				if fix_type not in fixes_by_type:
					fixes_by_type[fix_type] = {
						"count": 0,
						"records_fixed": 0
					}
				fixes_by_type[fix_type]["count"] += row.total_fixes or 0
				fixes_by_type[fix_type]["records_fixed"] += row.total_records_fixed or 0

				# 按数据类型统计
				data_type_val = row.data_type
				if data_type_val not in fixes_by_data_type:
					fixes_by_data_type[data_type_val] = {
						"count": 0,
						"records_fixed": 0
					}
				fixes_by_data_type[data_type_val]["count"] += row.total_fixes or 0
				fixes_by_data_type[data_type_val]["records_fixed"] += row.total_records_fixed or 0

			return {
				"total_fixes": total_fixes,
				"total_records_fixed": total_records_fixed,
				"fixes_by_type": fixes_by_type,
				"fixes_by_data_type": fixes_by_data_type,
				"avg_records_per_fix": round(total_records_fixed / total_fixes, 2) if total_fixes > 0 else 0
			}
		except Exception as e:
			raise RepositoryError(f"获取修复统计信息失败: {str(e)}")

	async def get_recent_fix_trend (
			self,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取最近修复趋势

		Args:
			days: 天数

		Returns:
			修复趋势列表
		"""
		try:
			end_date = datetime.now()
			start_date = end_date - timedelta(days=days)

			# 按天分组统计
			date_format = func.date_format(self.model.fix_date, "%Y-%m-%d")

			query = select(
				date_format.label("fix_day"),
				func.count().label("fix_count"),
				func.sum(self.model.records_fixed).label("records_fixed"),
				self.model.fix_type
			).where(
				and_(
					self.model.fix_date >= start_date,
					self.model.fix_date <= end_date,
					self.model.fix_status == "completed"
				)
			).group_by(
				"fix_day",
				self.model.fix_type
			).order_by(
				asc("fix_day")
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			# 按日期组织数据
			trend_data = {}
			for row in rows:
				fix_day = row.fix_day
				if fix_day not in trend_data:
					trend_data[fix_day] = {
						"total_fixes": 0,
						"total_records_fixed": 0,
						"fixes_by_type": {}
					}

				trend_data[fix_day]["total_fixes"] += row.fix_count or 0
				trend_data[fix_day]["total_records_fixed"] += row.records_fixed or 0
				trend_data[fix_day]["fixes_by_type"][row.fix_type] = {
					"count": row.fix_count or 0,
					"records_fixed": row.records_fixed or 0
				}

			# 转换为列表格式
			trend_list = []
			for fix_day, data in sorted(trend_data.items()):
				trend_list.append({
					"fix_day": fix_day,
					"total_fixes": data["total_fixes"],
					"total_records_fixed": data["total_records_fixed"],
					"fixes_by_type": data["fixes_by_type"]
				})

			return trend_list
		except Exception as e:
			raise RepositoryError(f"获取修复趋势失败: {str(e)}")

	async def get_most_common_fix_types (
			self,
			start_date: datetime,
			end_date: datetime,
			limit: int = 10
	) -> List[Dict[str, Any]]:
		"""
		获取最常见的修复类型

		Args:
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			最常见修复类型列表
		"""
		try:
			query = select(
				self.model.fix_type,
				func.count().label("fix_count"),
				func.sum(self.model.records_fixed).label("total_records_fixed"),
				func.avg(self.model.records_fixed).label("avg_records_per_fix")
			).where(
				and_(
					self.model.fix_date >= start_date,
					self.model.fix_date <= end_date,
					self.model.fix_status == "completed"
				)
			).group_by(
				self.model.fix_type
			).order_by(
				desc("total_records_fixed")
			).limit(limit)

			result = await self.session.execute(query)
			rows = result.fetchall()

			return [
				{
					"fix_type": row.fix_type,
					"fix_count": row.fix_count or 0,
					"total_records_fixed": row.total_records_fixed or 0,
					"avg_records_per_fix": round(float(row.avg_records_per_fix or 0), 2),
					"percentage": round((row.total_records_fixed or 0) / (row.total_records_fixed or 1) * 100, 2)
				}
				for row in rows
			]
		except Exception as e:
			raise RepositoryError(f"获取最常见修复类型失败: {str(e)}")

	async def get_failed_fixes (
			self,
			days: int = 7
	) -> List[DataFixRecord]:
		"""
		获取失败的修复记录

		Args:
			days: 天数

		Returns:
			失败的修复记录列表
		"""
		try:
			start_date = datetime.now() - timedelta(days=days)

			query = select(self.model).where(
				and_(
					self.model.fix_date >= start_date,
					self.model.fix_status != "completed"
				)
			).order_by(
				desc(self.model.fix_date)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取失败修复记录失败: {str(e)}")

	async def cleanup_old_records (self, days_to_keep: int = 365) -> int:
		"""
		清理旧记录

		Args:
			days_to_keep: 保留天数

		Returns:
			删除的记录数
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days_to_keep)

			query = select(self.model).where(
				self.model.fix_date < cutoff_date
			)
			result = await self.session.execute(query)
			old_records = result.scalars().all()

			if old_records:
				for record in old_records:
					await self.session.delete(record)
				await self.session.flush()

			return len(old_records)
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧记录失败: {str(e)}")
