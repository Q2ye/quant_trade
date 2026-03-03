# -*- coding: utf-8 -*-
"""
数据质量检查记录表Repository
"""
from typing import Optional, List, Dict, Any
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, asc

from quant_server.shared.database.models.business_models import DataQualityCheck
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError


class DataQualityCheckRepository(BaseRepository[DataQualityCheck]):
	"""数据质量检查记录Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, DataQualityCheck)

	async def create_quality_check (
			self,
			check_type: str,
			data_type: str,
			check_date: date,
			total_records: int,
			valid_records: int,
			invalid_records: int,
			missing_records: int = 0,
			duplicate_records: int = 0,
			check_results: Dict[str, Any] = None,
			status: str = "completed",
			checked_by: Optional[str] = None
	) -> DataQualityCheck:
		"""
		创建数据质量检查记录

		Args:
			check_type: 检查类型（daily/batch/adhoc）
			data_type: 数据类型（stock_daily/stock_minutes/financial）
			check_date: 检查日期
			total_records: 总记录数
			valid_records: 有效记录数
			invalid_records: 无效记录数
			missing_records: 缺失记录数
			duplicate_records: 重复记录数
			check_results: 检查结果
			status: 检查状态
			checked_by: 检查人/系统

		Returns:
			数据质量检查记录
		"""
		try:
			# 计算质量指标
			quality_score = (valid_records / total_records * 100) if total_records > 0 else 0

			data = {
				"check_type": check_type,
				"data_type": data_type,
				"check_date": check_date,
				"total_records": total_records,
				"valid_records": valid_records,
				"invalid_records": invalid_records,
				"missing_records": missing_records,
				"duplicate_records": duplicate_records,
				"check_results": check_results or {},
				"status": status,
				"checked_by": checked_by
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建数据质量检查记录失败: {str(e)}")

	async def get_by_check_date (
			self,
			check_date: date,
			data_type: Optional[str] = None,
			check_type: Optional[str] = None
	) -> List[DataQualityCheck]:
		"""
		根据检查日期获取记录

		Args:
			check_date: 检查日期
			data_type: 数据类型
			check_type: 检查类型

		Returns:
			数据质量检查记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.check_date == check_date
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)
			if check_type:
				query = query.where(self.model.check_type == check_type)

			query = query.order_by(desc(self.model.created_at))

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取检查日期记录失败: {str(e)}")

	async def get_by_data_type (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100
	) -> List[DataQualityCheck]:
		"""
		根据数据类型获取记录

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			数据质量检查记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.data_type == data_type
			)

			if start_date:
				query = query.where(self.model.check_date >= start_date)
			if end_date:
				query = query.where(self.model.check_date <= end_date)

			query = query.order_by(desc(self.model.check_date)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取数据类型记录失败: {str(e)}")

	async def get_latest_checks (
			self,
			data_type: Optional[str] = None,
			check_type: Optional[str] = None,
			limit: int = 50
	) -> List[DataQualityCheck]:
		"""
		获取最新的检查记录

		Args:
			data_type: 数据类型
			check_type: 检查类型
			limit: 限制记录数

		Returns:
			数据质量检查记录列表
		"""
		try:
			query = select(self.model)

			if data_type:
				query = query.where(self.model.data_type == data_type)
			if check_type:
				query = query.where(self.model.check_type == check_type)

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取最新检查记录失败: {str(e)}")

	async def get_quality_statistics (
			self,
			start_date: date,
			end_date: date,
			data_type: Optional[str] = None,
			check_type: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取质量统计信息

		Args:
			start_date: 开始日期
			end_date: 结束日期
			data_type: 数据类型
			check_type: 检查类型

		Returns:
			质量统计信息
		"""
		try:
			query = select(
				func.count().label("total_checks"),
				func.sum(self.model.total_records).label("total_records_checked"),
				func.sum(self.model.valid_records).label("total_valid_records"),
				func.sum(self.model.invalid_records).label("total_invalid_records"),
				func.sum(self.model.missing_records).label("total_missing_records"),
				func.sum(self.model.duplicate_records).label("total_duplicate_records")
			).where(
				and_(
					self.model.check_date >= start_date,
					self.model.check_date <= end_date,
					self.model.status == "completed"
				)
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)
			if check_type:
				query = query.where(self.model.check_type == check_type)

			result = await self.session.execute(query)
			row = result.fetchone()

			if not row:
				return {
					"total_checks": 0,
					"total_records_checked": 0,
					"total_valid_records": 0,
					"total_invalid_records": 0,
					"total_missing_records": 0,
					"total_duplicate_records": 0,
					"overall_quality_score": 0.0
				}

			total_records = row.total_records_checked or 0
			total_valid = row.total_valid_records or 0
			overall_quality_score = (total_valid / total_records * 100) if total_records > 0 else 0

			return {
				"total_checks": row.total_checks or 0,
				"total_records_checked": total_records,
				"total_valid_records": total_valid,
				"total_invalid_records": row.total_invalid_records or 0,
				"total_missing_records": row.total_missing_records or 0,
				"total_duplicate_records": row.total_duplicate_records or 0,
				"overall_quality_score": round(overall_quality_score, 2)
			}
		except Exception as e:
			raise RepositoryError(f"获取质量统计信息失败: {str(e)}")

	async def get_daily_quality_summary (
			self,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取每日质量摘要

		Args:
			days: 天数

		Returns:
			每日质量摘要列表
		"""
		try:
			end_date = date.today()
			start_date = end_date - timedelta(days=days)

			query = select(
				self.model.check_date,
				self.model.data_type,
				func.count().label("check_count"),
				func.sum(self.model.total_records).label("total_records"),
				func.sum(self.model.valid_records).label("valid_records"),
				func.avg(
					func.cast(self.model.valid_records, func.FLOAT) /
					func.cast(self.model.total_records, func.FLOAT) * 100
				).label("avg_quality_score")
			).where(
				and_(
					self.model.check_date >= start_date,
					self.model.check_date <= end_date,
					self.model.status == "completed"
				)
			).group_by(
				self.model.check_date,
				self.model.data_type
			).order_by(
				desc(self.model.check_date)
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			return [
				{
					"check_date": row.check_date,
					"data_type": row.data_type,
					"check_count": row.check_count,
					"total_records": row.total_records or 0,
					"valid_records": row.valid_records or 0,
					"avg_quality_score": round(float(row.avg_quality_score or 0), 2)
				}
				for row in rows
			]
		except Exception as e:
			raise RepositoryError(f"获取每日质量摘要失败: {str(e)}")

	async def get_data_type_quality_comparison (
			self,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取数据类型质量对比

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			数据类型质量对比列表
		"""
		try:
			query = select(
				self.model.data_type,
				func.count().label("check_count"),
				func.sum(self.model.total_records).label("total_records"),
				func.sum(self.model.valid_records).label("valid_records"),
				func.sum(self.model.invalid_records).label("invalid_records"),
				func.sum(self.model.missing_records).label("missing_records"),
				func.sum(self.model.duplicate_records).label("duplicate_records"),
				func.avg(
					func.cast(self.model.valid_records, func.FLOAT) /
					func.cast(self.model.total_records, func.FLOAT) * 100
				).label("avg_quality_score")
			).where(
				and_(
					self.model.check_date >= start_date,
					self.model.check_date <= end_date,
					self.model.status == "completed"
				)
			).group_by(
				self.model.data_type
			).order_by(
				desc("avg_quality_score")
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			return [
				{
					"data_type": row.data_type,
					"check_count": row.check_count,
					"total_records": row.total_records or 0,
					"valid_records": row.valid_records or 0,
					"invalid_records": row.invalid_records or 0,
					"missing_records": row.missing_records or 0,
					"duplicate_records": row.duplicate_records or 0,
					"avg_quality_score": round(float(row.avg_quality_score or 0), 2),
					"valid_rate": round((row.valid_records or 0) / (row.total_records or 1) * 100, 2),
					"invalid_rate": round((row.invalid_records or 0) / (row.total_records or 1) * 100, 2)
				}
				for row in rows
			]
		except Exception as e:
			raise RepositoryError(f"获取数据类型质量对比失败: {str(e)}")

	async def get_failed_checks (
			self,
			days: int = 7
	) -> List[DataQualityCheck]:
		"""
		获取失败的检查记录

		Args:
			days: 天数

		Returns:
			失败的检查记录列表
		"""
		try:
			start_date = date.today() - timedelta(days=days)

			query = select(self.model).where(
				and_(
					self.model.check_date >= start_date,
					self.model.status != "completed"
				)
			).order_by(
				desc(self.model.created_at)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取失败检查记录失败: {str(e)}")

	async def get_low_quality_checks (
			self,
			quality_threshold: float = 95.0,
			days: int = 7
	) -> List[DataQualityCheck]:
		"""
		获取低质量检查记录

		Args:
			quality_threshold: 质量阈值（百分比）
			days: 天数

		Returns:
			低质量检查记录列表
		"""
		try:
			start_date = date.today() - timedelta(days=days)

			# 使用子查询计算质量分数
			subquery = select(
				self.model.id,
				(self.model.valid_records / self.model.total_records * 100).label("quality_score")
			).where(
				self.model.check_date >= start_date
			).subquery()

			query = select(self.model).join(
				subquery,
				self.model.id == subquery.c.id
			).where(
				subquery.c.quality_score < quality_threshold
			).order_by(
				asc(subquery.c.quality_score)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取低质量检查记录失败: {str(e)}")

	async def cleanup_old_records (self, days_to_keep: int = 365) -> int:
		"""
		清理旧记录

		Args:
			days_to_keep: 保留天数

		Returns:
			删除的记录数
		"""
		try:
			cutoff_date = date.today() - timedelta(days=days_to_keep)

			query = select(self.model).where(
				self.model.check_date < cutoff_date
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