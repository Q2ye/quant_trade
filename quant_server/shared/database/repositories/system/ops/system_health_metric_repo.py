# -*- coding: utf-8 -*-
"""
系统健康指标表Repository
位置：shared/database/repositories/system/system_health_metric_repo.py
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.system_models import SystemHealthMetric
from quant_server.shared.database.repositories import RepositoryError
from quant_server.shared.database.repositories.base import BaseRepository


class SystemHealthMetricRepository(BaseRepository[SystemHealthMetric]):
	"""系统健康指标Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, SystemHealthMetric)

	async def record_metric (
			self,
			component: str,
			metric_name: str,
			metric_value: float,
			metric_unit: Optional[str] = None,
			severity: str = "info"
	) -> SystemHealthMetric:
		"""
		记录系统健康指标

		Args:
			component: 组件名称（cpu, memory, disk, network, database）
			metric_name: 指标名称
			metric_value: 指标值
			metric_unit: 单位
			severity: 严重程度（info, warning, error, critical）

		Returns:
			系统健康指标记录
		"""
		try:
			data = {
				"component": component,
				"metric_name": metric_name,
				"metric_value": metric_value,
				"metric_unit": metric_unit,
				"severity": severity
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"记录系统健康指标失败: {str(e)}")

	async def record_cpu_metric (
			self,
			cpu_percent: float,
			severity: str = "info"
	) -> SystemHealthMetric:
		"""
		记录CPU指标

		Args:
			cpu_percent: CPU使用率
			severity: 严重程度

		Returns:
			CPU指标记录
		"""
		return await self.record_metric(
			component="cpu",
			metric_name="cpu_usage",
			metric_value=cpu_percent,
			metric_unit="%",
			severity=severity
		)

	async def record_memory_metric (
			self,
			memory_percent: float,
			severity: str = "info"
	) -> SystemHealthMetric:
		"""
		记录内存指标

		Args:
			memory_percent: 内存使用率
			severity: 严重程度

		Returns:
			内存指标记录
		"""
		return await self.record_metric(
			component="memory",
			metric_name="memory_usage",
			metric_value=memory_percent,
			metric_unit="%",
			severity=severity
		)

	async def record_disk_metric (
			self,
			disk_percent: float,
			severity: str = "info"
	) -> SystemHealthMetric:
		"""
		记录磁盘指标

		Args:
			disk_percent: 磁盘使用率
			severity: 严重程度

		Returns:
			磁盘指标记录
		"""
		return await self.record_metric(
			component="disk",
			metric_name="disk_usage",
			metric_value=disk_percent,
			metric_unit="%",
			severity=severity
		)

	async def record_database_metric (
			self,
			query_time_ms: float,
			connection_count: int,
			severity: str = "info"
	) -> List[SystemHealthMetric]:
		"""
		记录数据库指标

		Args:
			query_time_ms: 查询时间（毫秒）
			connection_count: 连接数
			severity: 严重程度

		Returns:
			数据库指标记录列表
		"""
		try:
			metrics = []

			# 记录查询时间
			query_metric = await self.record_metric(
				component="database",
				metric_name="query_time",
				metric_value=query_time_ms,
				metric_unit="ms",
				severity=severity
			)
			metrics.append(query_metric)

			# 记录连接数
			connection_metric = await self.record_metric(
				component="database",
				metric_name="connection_count",
				metric_value=float(connection_count),
				metric_unit="count",
				severity=severity
			)
			metrics.append(connection_metric)

			return metrics
		except Exception as e:
			raise RepositoryError(f"记录数据库指标失败: {str(e)}")

	async def get_latest_metrics (
			self,
			component: Optional[str] = None,
			metric_name: Optional[str] = None,
			limit: int = 100
	) -> List[SystemHealthMetric]:
		"""
		获取最新指标记录

		Args:
			component: 组件名称
			metric_name: 指标名称
			limit: 限制记录数

		Returns:
			系统健康指标列表
		"""
		try:
			query = select(self.model)

			if component:
				query = query.where(self.model.component == component)
			if metric_name:
				query = query.where(self.model.metric_name == metric_name)

			query = query.order_by(desc(self.model.collected_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取最新指标失败: {str(e)}")

	async def get_metrics_by_time_range (
			self,
			start_date: datetime,
			end_date: datetime,
			component: Optional[str] = None,
			metric_name: Optional[str] = None
	) -> List[SystemHealthMetric]:
		"""
		获取时间范围内的指标记录

		Args:
			start_date: 开始时间
			end_date: 结束时间
			component: 组件名称
			metric_name: 指标名称

		Returns:
			系统健康指标列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.collected_at >= start_date,
					self.model.collected_at <= end_date
				)
			)

			if component:
				query = query.where(self.model.component == component)
			if metric_name:
				query = query.where(self.model.metric_name == metric_name)

			query = query.order_by(asc(self.model.collected_at))

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取时间范围指标失败: {str(e)}")

	async def get_metric_statistics (
			self,
			component: str,
			metric_name: str,
			start_date: datetime,
			end_date: datetime,
			interval_minutes: int = 5
	) -> List[Dict[str, Any]]:
		"""
		获取指标统计信息（按时间间隔聚合）

		Args:
			component: 组件名称
			metric_name: 指标名称
			start_date: 开始时间
			end_date: 结束时间
			interval_minutes: 时间间隔（分钟）

		Returns:
			统计结果列表
		"""
		try:
			# 计算时间桶
			interval_seconds = interval_minutes * 60
			time_bucket = func.floor(
				func.unix_timestamp(self.model.collected_at) / interval_seconds
			) * interval_seconds

			query = select(
				func.from_unixtime(time_bucket).label("time_bucket"),
				func.avg(self.model.metric_value).label("avg_value"),
				func.max(self.model.metric_value).label("max_value"),
				func.min(self.model.metric_value).label("min_value"),
				func.count().label("sample_count")
			).where(
				and_(
					self.model.component == component,
					self.model.metric_name == metric_name,
					self.model.collected_at >= start_date,
					self.model.collected_at <= end_date
				)
			).group_by(
				"time_bucket"
			).order_by(
				"time_bucket"
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			return [
				{
					"time_bucket": row.time_bucket,
					"avg_value": float(row.avg_value or 0),
					"max_value": float(row.max_value or 0),
					"min_value": float(row.min_value or 0),
					"sample_count": row.sample_count
				}
				for row in rows
			]
		except Exception as e:
			raise RepositoryError(f"获取指标统计失败: {str(e)}")

	async def get_system_health_summary (
			self,
			hours: int = 24
	) -> Dict[str, Any]:
		"""
		获取系统健康摘要

		Args:
			hours: 小时数

		Returns:
			系统健康摘要
		"""
		try:
			start_date = datetime.now() - timedelta(hours=hours)

			summary: Dict[str, Any] = {
				"time_range": {
					"start": start_date,
					"end": datetime.now()
				},
				"metrics": {},
				"severity_summary": {
					"info": 0,
					"warning": 0,
					"error": 0,
					"critical": 0
				}
			}

			# 获取各种指标的最新值
			components = ["cpu", "memory", "disk", "network", "database"]

			for component in components:
				# 获取该类型的最新指标
				latest_query = select(self.model).where(
					and_(
						self.model.component == component,
						self.model.collected_at >= start_date
					)
				).order_by(
					desc(self.model.collected_at)
				).limit(1)

				result = await self.session.execute(latest_query)
				latest_metric = result.scalar_one_or_none()

				if latest_metric:
					summary["metrics"][component] = {
						"latest_value": float(latest_metric.metric_value),
						"metric_unit": latest_metric.metric_unit,
						"severity": latest_metric.severity,
						"collected_at": latest_metric.collected_at
					}

			# 获取状态统计
			severity_query = select(
				self.model.severity,
				func.count().label("count")
			).where(
				self.model.collected_at >= start_date
			).group_by(
				self.model.severity
			)

			severity_result = await self.session.execute(severity_query)
			for row in severity_result.fetchall():
				if row.severity in summary["severity_summary"]:
					summary["severity_summary"][row.severity] = row.count

			return summary
		except Exception as e:
			raise RepositoryError(f"获取系统健康摘要失败: {str(e)}")

	async def get_warning_metrics (
			self,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 100
	) -> List[SystemHealthMetric]:
		"""
		获取警告和严重指标

		Args:
			start_date: 开始时间
			end_date: 结束时间
			limit: 限制记录数

		Returns:
			警告和严重指标列表
		"""
		try:
			query = select(self.model).where(
				self.model.severity.in_(["warning", "error", "critical"])
			)

			if start_date:
				query = query.where(self.model.collected_at >= start_date)
			if end_date:
				query = query.where(self.model.collected_at <= end_date)

			query = query.order_by(desc(self.model.collected_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取警告指标失败: {str(e)}")

	async def cleanup_old_metrics (self, days_to_keep: int = 7) -> int:
		"""
		清理旧指标记录

		Args:
			days_to_keep: 保留天数

		Returns:
			删除的记录数
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days_to_keep)

			query = select(self.model).where(
				self.model.collected_at < cutoff_date
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