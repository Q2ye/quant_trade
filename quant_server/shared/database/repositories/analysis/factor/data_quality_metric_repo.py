# -*- coding: utf-8 -*-
"""
数据质量指标历史表Repository
位置：shared/database/repositories/market/data_quality_metric_repo.py
"""
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func, desc, asc, case
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import DataQualityMetric
from shared.database.repositories.base import BaseRepository, RepositoryError


class DataQualityMetricRepository(BaseRepository[DataQualityMetric]):
	"""数据质量指标历史Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, DataQualityMetric)

	async def record_metric (
			self,
			metric_date: date,
			data_type: str,
			metric_name: str,
			metric_value: float,
			target_value: Optional[float] = None,
			status: str = "normal"
	) -> DataQualityMetric:
		"""
		记录数据质量指标

		Args:
			metric_date: 指标日期
			data_type: 数据类型
			metric_name: 指标名称
			metric_value: 指标值
			target_value: 目标值
			status: 状态（normal/warning/critical）

		Returns:
			数据质量指标记录
		"""
		try:
			data = {
				"metric_date": metric_date,
				"data_type": data_type,
				"metric_name": metric_name,
				"metric_value": metric_value,
				"target_value": target_value,
				"status": status
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"记录数据质量指标失败: {str(e)}")

	async def record_completeness_metric (
			self,
			metric_date: date,
			data_type: str,
			completeness_percentage: float,
			target_percentage: float = 99.0
	) -> DataQualityMetric:
		"""
		记录完整性指标

		Args:
			metric_date: 指标日期
			data_type: 数据类型
			completeness_percentage: 完整性百分比
			target_percentage: 目标百分比

		Returns:
			数据质量指标记录
		"""
		status = "normal"
		if completeness_percentage < target_percentage - 5:
			status = "critical"
		elif completeness_percentage < target_percentage:
			status = "warning"

		return await self.record_metric(
			metric_date=metric_date,
			data_type=data_type,
			metric_name="completeness",
			metric_value=completeness_percentage,
			target_value=target_percentage,
			status=status
		)

	async def record_accuracy_metric (
			self,
			metric_date: date,
			data_type: str,
			accuracy_percentage: float,
			target_percentage: float = 99.5
	) -> DataQualityMetric:
		"""
		记录准确性指标

		Args:
			metric_date: 指标日期
			data_type: 数据类型
			accuracy_percentage: 准确性百分比
			target_percentage: 目标百分比

		Returns:
			数据质量指标记录
		"""
		status = "normal"
		if accuracy_percentage < target_percentage - 1:
			status = "critical"
		elif accuracy_percentage < target_percentage:
			status = "warning"

		return await self.record_metric(
			metric_date=metric_date,
			data_type=data_type,
			metric_name="accuracy",
			metric_value=accuracy_percentage,
			target_value=target_percentage,
			status=status
		)

	async def record_timeliness_metric (
			self,
			metric_date: date,
			data_type: str,
			timeliness_hours: float,
			target_hours: float = 1.0
	) -> DataQualityMetric:
		"""
		记录及时性指标

		Args:
			metric_date: 指标日期
			data_type: 数据类型
			timeliness_hours: 及时性小时数
			target_hours: 目标小时数

		Returns:
			数据质量指标记录
		"""
		status = "normal"
		if timeliness_hours > target_hours * 3:
			status = "critical"
		elif timeliness_hours > target_hours:
			status = "warning"

		return await self.record_metric(
			metric_date=metric_date,
			data_type=data_type,
			metric_name="timeliness",
			metric_value=timeliness_hours,
			target_value=target_hours,
			status=status
		)

	async def get_by_date_range (
			self,
			start_date: date,
			end_date: date,
			data_type: Optional[str] = None,
			metric_name: Optional[str] = None,
			status: Optional[str] = None
	) -> List[DataQualityMetric]:
		"""
		根据日期范围获取指标

		Args:
			start_date: 开始日期
			end_date: 结束日期
			data_type: 数据类型
			metric_name: 指标名称
			status: 状态

		Returns:
			数据质量指标列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.metric_date >= start_date,
					self.model.metric_date <= end_date
				)
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)
			if metric_name:
				query = query.where(self.model.metric_name == metric_name)
			if status:
				query = query.where(self.model.status == status)

			query = query.order_by(
				desc(self.model.metric_date),
				asc(self.model.data_type),
				asc(self.model.metric_name)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取日期范围指标失败: {str(e)}")

	async def get_latest_metrics (
			self,
			data_type: Optional[str] = None,
			metric_name: Optional[str] = None,
			limit: int = 100
	) -> List[DataQualityMetric]:
		"""
		获取最新指标

		Args:
			data_type: 数据类型
			metric_name: 指标名称
			limit: 限制记录数

		Returns:
			数据质量指标列表
		"""
		try:
			query = select(self.model)

			if data_type:
				query = query.where(self.model.data_type == data_type)
			if metric_name:
				query = query.where(self.model.metric_name == metric_name)

			query = query.order_by(desc(self.model.metric_date)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取最新指标失败: {str(e)}")

	async def get_metric_summary (
			self,
			start_date: date,
			end_date: date,
			data_type: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取指标摘要

		Args:
			start_date: 开始日期
			end_date: 结束日期
			data_type: 数据类型

		Returns:
			指标摘要
		"""
		try:
			query = select(
				func.count().label("total_metrics"),
				func.avg(self.model.metric_value).label("avg_metric_value"),
				func.min(self.model.metric_value).label("min_metric_value"),
				func.max(self.model.metric_value).label("max_metric_value"),
				self.model.metric_name,
				self.model.data_type
			).where(
				and_(
					self.model.metric_date >= start_date,
					self.model.metric_date <= end_date
				)
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)

			query = query.group_by(
				self.model.metric_name,
				self.model.data_type
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			summary: Dict[str, Any] = {
				"time_range": {
					"start_date": start_date,
					"end_date": end_date
				},
				"total_metrics": 0,
				"metrics_by_name": {},
				"metrics_by_type": {}
			}

			for row in rows:
				summary["total_metrics"] += row.total_metrics or 0

				metric_name = row.metric_name
				data_type_val = row.data_type

				# 按指标名称统计
				if metric_name not in summary["metrics_by_name"]:
					summary["metrics_by_name"][metric_name] = {
						"total": 0,
						"avg_value": 0.0,
						"min_value": 0.0,
						"max_value": 0.0,
						"data_types": set()
					}

				# 使用中间变量避免类型检查错误
				metric_dict = summary["metrics_by_name"][metric_name]
				metric_dict["total"] += row.total_metrics or 0
				metric_dict["avg_value"] = round(float(row.avg_metric_value or 0), 2)
				metric_dict["min_value"] = round(float(row.min_metric_value or 0), 2)
				metric_dict["max_value"] = round(float(row.max_metric_value or 0), 2)
				metric_dict["data_types"].add(data_type_val)

				# 按数据类型统计
				if data_type_val not in summary["metrics_by_type"]:
					summary["metrics_by_type"][data_type_val] = {
						"total": 0,
						"metrics": {}
					}

				summary["metrics_by_type"][data_type_val]["total"] += row.total_metrics or 0
				summary["metrics_by_type"][data_type_val]["metrics"][metric_name] = {
					"avg_value": round(float(row.avg_metric_value or 0), 2),
					"min_value": round(float(row.min_metric_value or 0), 2),
					"max_value": round(float(row.max_metric_value or 0), 2)
				}

			# 转换集合为列表
			for metric_name_key, data in summary["metrics_by_name"].items():
				data["data_types"] = list(data["data_types"])

			return summary
		except Exception as e:
			raise RepositoryError(f"获取指标摘要失败: {str(e)}")

	async def get_metric_trend (
			self,
			metric_name: str,
			data_type: str,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取指标趋势

		Args:
			metric_name: 指标名称
			data_type: 数据类型
			days: 天数

		Returns:
			指标趋势列表
		"""
		try:
			end_date = date.today()
			start_date = end_date - timedelta(days=days)

			query = select(
				self.model.metric_date,
				self.model.metric_value,
				self.model.target_value,
				self.model.status
			).where(
				and_(
					self.model.metric_name == metric_name,
					self.model.data_type == data_type,
					self.model.metric_date >= start_date,
					self.model.metric_date <= end_date
				)
			).order_by(
				asc(self.model.metric_date)
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			trend_data = []
			for row in rows:
				trend_data.append({
					"metric_date": row.metric_date,
					"metric_value": float(row.metric_value),
					"target_value": float(row.target_value) if row.target_value else None,
					"status": row.status,
					"deviation": round(float(row.metric_value) - (float(row.target_value) if row.target_value else 0),
					                   2)
				})

			return trend_data
		except Exception as e:
			raise RepositoryError(f"获取指标趋势失败: {str(e)}")

	async def get_status_distribution (
			self,
			start_date: date,
			end_date: date,
			data_type: Optional[str] = None,
			metric_name: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取状态分布

		Args:
			start_date: 开始日期
			end_date: 结束日期
			data_type: 数据类型
			metric_name: 指标名称

		Returns:
			状态分布
		"""
		try:
			query = select(
				self.model.status,
				func.count().label("count"),
				func.avg(self.model.metric_value).label("avg_value")
			).where(
				and_(
					self.model.metric_date >= start_date,
					self.model.metric_date <= end_date
				)
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)
			if metric_name:
				query = query.where(self.model.metric_name == metric_name)

			query = query.group_by(
				self.model.status
			).order_by(
				desc("count")
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			total_count = 0
			status_distribution = {}

			for row in rows:
				status = row.status
				count = row.count or 0
				total_count += count

				status_distribution[status] = {
					"count": count,
					"percentage": 0,  # 稍后计算
					"avg_value": round(float(row.avg_value or 0), 2)
				}

			# 计算百分比
			for status, data in status_distribution.items():
				data["percentage"] = round((data["count"] / total_count * 100), 2) if total_count > 0 else 0

			return {
				"total_count": total_count,
				"status_distribution": status_distribution,
				"time_range": {
					"start_date": start_date,
					"end_date": end_date
				}
			}
		except Exception as e:
			raise RepositoryError(f"获取状态分布失败: {str(e)}")

	async def get_warning_metrics (
			self,
			days: int = 7,
			data_type: Optional[str] = None
	) -> List[DataQualityMetric]:
		"""
		获取警告和严重指标

		Args:
			days: 天数
			data_type: 数据类型

		Returns:
			警告和严重指标列表
		"""
		try:
			start_date = date.today() - timedelta(days=days)

			query = select(self.model).where(
				and_(
					self.model.metric_date >= start_date,
					self.model.status.in_(["warning", "critical"])
				)
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)

			query = query.order_by(
					desc(self.model.metric_date),
					desc(
						case(
							(self.model.status == "critical", 2),
							(self.model.status == "warning", 1),
							else_=0
						)
					)
				)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取警告指标失败: {str(e)}")

	async def get_comparison_with_target (
			self,
			start_date: date,
			end_date: date,
			data_type: Optional[str] = None,
			metric_name: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取与目标值的对比

		Args:
			start_date: 开始日期
			end_date: 结束日期
			data_type: 数据类型
			metric_name: 指标名称

		Returns:
			与目标值的对比
		"""
		try:
			query = select(
				func.avg(self.model.metric_value).label("avg_actual"),
				func.avg(self.model.target_value).label("avg_target"),
				func.count(
						case((self.model.metric_value >= self.model.target_value, 1), else_=None)
					).label("met_target_count"),
				func.count().label("total_count"),
				self.model.data_type,
				self.model.metric_name
			).where(
				and_(
					self.model.metric_date >= start_date,
					self.model.metric_date <= end_date,
					self.model.target_value.isnot(None)
				)
			)

			if data_type:
				query = query.where(self.model.data_type == data_type)
			if metric_name:
				query = query.where(self.model.metric_name == metric_name)

			query = query.group_by(
				self.model.data_type,
				self.model.metric_name
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			comparison_results = []
			overall_stats = {
				"total_metrics": 0,
				"met_target_count": 0,
				"avg_actual_vs_target_diff": 0.0
			}

			for row in rows:
				total_count = row.total_count or 0
				met_target_count = row.met_target_count or 0
				avg_actual = float(row.avg_actual or 0)
				avg_target = float(row.avg_target or 0)
				diff = avg_actual - avg_target

				comparison_results.append({
					"data_type": row.data_type,
					"metric_name": row.metric_name,
					"avg_actual": round(avg_actual, 2),
					"avg_target": round(avg_target, 2),
					"difference": round(diff, 2),
					"met_target_count": met_target_count,
					"total_count": total_count,
					"met_target_percentage": round((met_target_count / total_count * 100), 2) if total_count > 0 else 0
				})

				overall_stats["total_metrics"] += total_count
				overall_stats["met_target_count"] += met_target_count

			overall_stats["met_target_percentage"] = round(
				(overall_stats["met_target_count"] / overall_stats["total_metrics"] * 100), 2
			) if overall_stats["total_metrics"] > 0 else 0

			# 计算平均差异
			if comparison_results:
				total_diff = sum(item["difference"] for item in comparison_results)
				overall_stats["avg_actual_vs_target_diff"] = round(total_diff / len(comparison_results), 2)

			return {
				"overall_stats": overall_stats,
				"comparison_results": comparison_results,
				"time_range": {
					"start_date": start_date,
					"end_date": end_date
				}
			}
		except Exception as e:
			raise RepositoryError(f"获取目标对比失败: {str(e)}")

	async def cleanup_old_metrics (self, days_to_keep: int = 365) -> int:
		"""
		清理旧指标

		Args:
			days_to_keep: 保留天数

		Returns:
			删除的指标数
		"""
		try:
			cutoff_date = date.today() - timedelta(days=days_to_keep)

			query = select(self.model).where(
				self.model.metric_date < cutoff_date
			)
			result = await self.session.execute(query)
			old_metrics = result.scalars().all()

			if old_metrics:
				for metric in old_metrics:
					await self.session.delete(metric)
				await self.session.flush()

			return len(old_metrics)
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧指标失败: {str(e)}")