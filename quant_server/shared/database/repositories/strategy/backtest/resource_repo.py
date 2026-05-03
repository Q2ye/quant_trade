# shared/database/repositories/strategy/backtest/resource_repo.py
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, delete

from shared.database.models.business_models import BacktestResourceUsage
from shared.database.repositories.base import BaseRepository


class BacktestResourceUsageRepository(BaseRepository[BacktestResourceUsage]):
	"""回测资源使用数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestResourceUsage)

	async def get_task_resource_usage (self, task_id: str,
	                                   resource_type: Optional[str] = None) -> List[BacktestResourceUsage]:
		"""获取回测任务的资源使用记录"""
		query = select(self.model).where(self.model.task_id == task_id)

		if resource_type:
			query = query.where(self.model.resource_type == resource_type)

		query = query.order_by(self.model.recorded_at)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_resource_summary (self, task_id: str) -> Dict[str, Any]:
		"""获取资源使用汇总统计"""
		# 按资源类型统计
		type_query = (
			select(
				self.model.resource_type,
				func.count().label('count'),
				func.min(self.model.metric_value).label('min_value'),
				func.max(self.model.metric_value).label('max_value'),
				func.avg(self.model.metric_value).label('avg_value'),
				func.max(self.model.recorded_at).label('last_recorded')
			)
			.where(self.model.task_id == task_id)
			.group_by(self.model.resource_type)
		)

		type_result = await self.session.execute(type_query)
		type_stats = {}

		for row in type_result.all():
			type_stats[row.resource_type] = {
				"count": row.count,
				"min_value": float(row.min_value or 0),
				"max_value": float(row.max_value or 0),
				"avg_value": float(row.avg_value or 0),
				"last_recorded": row.last_recorded
			}

		# 获取峰值使用情况
		peak_query = (
			select(self.model)
			.where(self.model.task_id == task_id)
			.order_by(desc(self.model.metric_value))
			.limit(5)
		)

		peak_result = await self.session.execute(peak_query)
		peak_usage = [
			{
				"resource_type": record.resource_type,
				"metric_name": record.metric_name,
				"metric_value": float(record.metric_value),
				"recorded_at": record.recorded_at
			}
			for record in peak_result.scalars().all()
		]

		return {
			"type_statistics": type_stats,
			"peak_usage": peak_usage
		}

	async def get_resource_timeline (self, task_id: str, resource_type: str,
	                                 metric_name: str, interval_minutes: int = 5) -> List[Dict[str, Any]]:
		"""获取资源使用时间线（按时间间隔聚合）"""
		# 计算时间间隔
		interval_seconds = interval_minutes * 60

		timeline_query = (
			select(
				func.date_trunc('second',
				                func.to_timestamp(
					                func.floor(
						                func.extract('epoch', self.model.recorded_at) / interval_seconds
					                ) * interval_seconds
				                )
				                ).label('time_bucket'),
				func.avg(self.model.metric_value).label('avg_value'),
				func.min(self.model.metric_value).label('min_value'),
				func.max(self.model.metric_value).label('max_value')
			)
			.where(
				and_(
					self.model.task_id == task_id,
					self.model.resource_type == resource_type,
					self.model.metric_name == metric_name
				)
			)
			.group_by('time_bucket')
			.order_by('time_bucket')
		)

		result = await self.session.execute(timeline_query)

		timeline = []
		for row in result.all():
			timeline.append({
				"timestamp": row.time_bucket,
				"avg_value": float(row.avg_value or 0),
				"min_value": float(row.min_value or 0),
				"max_value": float(row.max_value or 0)
			})

		return timeline

	async def record_resource_usage (self, task_id: str, resource_type: str,
	                                 metric_name: str, metric_value: float,
	                                 unit: Optional[str] = None) -> BacktestResourceUsage:
		"""记录资源使用情况"""
		now = datetime.now()

		usage_record = self.model(
			task_id=task_id,
			resource_type=resource_type,
			metric_name=metric_name,
			metric_value=metric_value,
			unit=unit,
			recorded_at=now,
			created_at=now
		)

		self.session.add(usage_record)
		await self.session.flush()

		return usage_record

	async def batch_record_resource_usage (self, task_id: str, usage_data: List[Dict[str, Any]]) -> int:
		"""批量记录资源使用情况"""
		now = datetime.now()
		instances = []

		for data in usage_data:
			# 确保task_id一致
			data['task_id'] = task_id
			data['recorded_at'] = data.get('recorded_at', now)
			data['created_at'] = now

			instance = self.model(**data)
			instances.append(instance)

		self.session.add_all(instances)
		await self.session.flush()
		return len(instances)

	async def get_system_resource_trends (self, days: int = 7) -> Dict[str, Any]:
		"""获取系统资源使用趋势"""
		cutoff_date = datetime.now() - timedelta(days=days)

		# 按天统计各资源类型的使用情况
		trend_query = (
			select(
				func.date(self.model.recorded_at).label('record_date'),
				self.model.resource_type,
				func.avg(self.model.metric_value).label('avg_usage')
			)
			.where(self.model.recorded_at >= cutoff_date)
			.group_by(func.date(self.model.recorded_at), self.model.resource_type)
			.order_by(func.date(self.model.recorded_at).desc(), self.model.resource_type)
		)

		result = await self.session.execute(trend_query)

		trends = {}
		for row in result.all():
			date_str = row.record_date.strftime('%Y-%m-%d')
			if date_str not in trends:
				trends[date_str] = {}

			trends[date_str][row.resource_type] = float(row.avg_usage or 0)

		# 统计资源类型分布
		type_dist_query = (
			select(
				self.model.resource_type,
				func.count().label('record_count'),
				func.avg(self.model.metric_value).label('avg_usage')
			)
			.where(self.model.recorded_at >= cutoff_date)
			.group_by(self.model.resource_type)
		)

		type_result = await self.session.execute(type_dist_query)
		type_distribution = [
			{
				"resource_type": row.resource_type,
				"record_count": row.record_count,
				"avg_usage": float(row.avg_usage or 0)
			}
			for row in type_result.all()
		]

		return {
			"trends": trends,
			"type_distribution": type_distribution,
			"analysis_period": f"Last {days} days"
		}

	async def cleanup_old_records (self, days: int = 30) -> int:
		"""清理指定天数前的资源使用记录"""
		cutoff_date = datetime.now() - timedelta(days=days)

		stmt = (
			delete(self.model)
			.where(self.model.recorded_at < cutoff_date)
		)

		result = await self.session.execute(stmt) #type:ignore
		return result.rowcount or 0