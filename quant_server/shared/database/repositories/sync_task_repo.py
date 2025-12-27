# -*- coding: utf-8 -*-
"""
数据同步任务仓库
提供数据同步任务记录的统一访问接口
位置：shared/database/repositories/sync_task_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, between

from .base import BaseRepository
from quant_server.shared.database.models.business_models import DataSyncTask


class SyncTaskRepository:
	"""数据同步任务Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, DataSyncTask)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> DataSyncTask:
		"""创建同步任务记录"""
		return await self.base_repo.create(data)

	async def get (self, id: int) -> Optional[DataSyncTask]:
		"""根据ID获取同步任务记录"""
		return await self.base_repo.get(id)

	async def update (self, id: int, data: Dict[str, Any]) -> Optional[DataSyncTask]:
		"""更新同步任务记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: int, soft: bool = True) -> bool:
		"""删除同步任务记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, *filters) -> Optional[DataSyncTask]:
		"""根据条件获取单个同步任务记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[DataSyncTask]:
		"""根据条件获取多个同步任务记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计同步任务记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def get_by_task_type (
			self,
			task_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100
	) -> List[DataSyncTask]:
		"""根据任务类型获取同步任务"""
		filters = [DataSyncTask.task_type == task_type]

		if start_date:
			filters.append(DataSyncTask.start_time >= start_date)
		if end_date:
			filters.append(DataSyncTask.start_time <= end_date)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=DataSyncTask.start_time.desc()
		)

	async def get_by_status (
			self,
			status: str,
			task_type: Optional[str] = None,
			hours: int = 24
	) -> List[DataSyncTask]:
		"""根据状态获取同步任务"""
		cutoff_time = datetime.now() - timedelta(hours=hours)

		filters = [
			DataSyncTask.status == status,
			DataSyncTask.start_time >= cutoff_time
		]

		if task_type:
			filters.append(DataSyncTask.task_type == task_type)

		return await self.get_many(
			*filters,
			order_by=DataSyncTask.start_time.desc()
		)

	async def get_running_tasks (self) -> List[DataSyncTask]:
		"""获取正在运行的任务"""
		return await self.get_by_status('running')

	async def get_recent_tasks (
			self,
			hours: int = 24,
			task_type: Optional[str] = None
	) -> List[DataSyncTask]:
		"""获取最近N小时的任务"""
		cutoff_time = datetime.now() - timedelta(hours=hours)

		filters = [DataSyncTask.start_time >= cutoff_time]

		if task_type:
			filters.append(DataSyncTask.task_type == task_type)

		return await self.get_many(
			*filters,
			order_by=DataSyncTask.start_time.desc()
		)

	async def get_today_tasks (self, task_type: Optional[str] = None) -> List[DataSyncTask]:
		"""获取今日任务"""
		today = datetime.now().date()
		tomorrow = today + timedelta(days=1)

		filters = [
			DataSyncTask.start_time >= today,
			DataSyncTask.start_time < tomorrow
		]

		if task_type:
			filters.append(DataSyncTask.task_type == task_type)

		return await self.get_many(
			*filters,
			order_by=DataSyncTask.start_time.desc()
		)

	async def get_latest_task (
			self,
			task_type: str,
			status: Optional[str] = None
	) -> Optional[DataSyncTask]:
		"""获取最新的任务"""
		query = select(DataSyncTask).where(
			DataSyncTask.task_type == task_type
		)

		if status:
			query = query.where(DataSyncTask.status == status)

		query = query.order_by(DataSyncTask.start_time.desc()).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_task_statistics (
			self,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			task_type: Optional[str] = None
	) -> Dict[str, Any]:
		"""获取任务统计信息"""
		filters = []
		if start_date:
			filters.append(DataSyncTask.start_time >= start_date)
		if end_date:
			filters.append(DataSyncTask.start_time <= end_date)
		if task_type:
			filters.append(DataSyncTask.task_type == task_type)

		where_clause = and_(*filters) if filters else True

		# 总任务数
		total_count = await self.count(*filters) if filters else await self.count()

		# 按状态统计
		status_stats = await self.session.execute(
			select(
				DataSyncTask.status,
				func.count(DataSyncTask.id).label('count'),
				func.sum(DataSyncTask.total_records).label('total_records')
			).where(
				where_clause
			).group_by(
				DataSyncTask.status
			).order_by(
				func.count(DataSyncTask.id).desc()
			)
		)

		status_stats_dict = {}
		for row in status_stats.all():
			status_stats_dict[row.status] = {
				'count': row.count,
				'total_records': row.total_records or 0
			}

		# 按任务类型统计
		type_stats = await self.session.execute(
			select(
				DataSyncTask.task_type,
				func.count(DataSyncTask.id).label('count'),
				func.sum(DataSyncTask.total_records).label('total_records'),
				func.avg(
					func.extract('epoch', DataSyncTask.end_time - DataSyncTask.start_time)
				).label('avg_duration')
			).where(
				and_(
					where_clause,
					DataSyncTask.end_time.isnot(None),
					DataSyncTask.start_time.isnot(None)
				)
			).group_by(
				DataSyncTask.task_type
			).order_by(
				func.count(DataSyncTask.id).desc()
			)
		)

		type_stats_list = []
		for row in type_stats.all():
			type_stats_list.append({
				'task_type': row.task_type,
				'count': row.count,
				'total_records': row.total_records or 0,
				'avg_duration': float(row.avg_duration) if row.avg_duration else 0
			})

		# 成功率
		success_count = status_stats_dict.get('completed', {}).get('count', 0)
		failed_count = status_stats_dict.get('failed', {}).get('count', 0)
		success_rate = success_count / total_count * 100 if total_count > 0 else 0

		# 总同步记录数
		total_records = sum(
			stats.get('total_records', 0)
			for stats in status_stats_dict.values()
		)

		return {
			'total_count': total_count,
			'success_count': success_count,
			'failed_count': failed_count,
			'success_rate': success_rate,
			'total_records': total_records,
			'status_stats': status_stats_dict,
			'type_stats': type_stats_list,
			'start_date': start_date,
			'end_date': end_date
		}

	async def get_task_duration_statistics (
			self,
			task_type: Optional[str] = None,
			days: int = 30
	) -> Dict[str, Any]:
		"""获取任务持续时间统计"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		query = select(
			func.date(DataSyncTask.start_time).label('date'),
			DataSyncTask.task_type,
			func.avg(
				func.extract('epoch', DataSyncTask.end_time - DataSyncTask.start_time)
			).label('avg_duration'),
			func.count(DataSyncTask.id).label('count')
		).where(
			and_(
				DataSyncTask.start_time >= start_date,
				DataSyncTask.end_time.isnot(None),
				DataSyncTask.status == 'completed'
			)
		)

		if task_type:
			query = query.where(DataSyncTask.task_type == task_type)

		query = query.group_by(
			func.date(DataSyncTask.start_time),
			DataSyncTask.task_type
		).order_by(
			func.date(DataSyncTask.start_time).asc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		# 按日期组织数据
		date_dict = {}
		for row in rows:
			date_str = row.date.strftime('%Y-%m-%d')
			if date_str not in date_dict:
				date_dict[date_str] = {
					'date': row.date,
					'total_duration': 0,
					'total_count': 0,
					'by_type': {}
				}

			duration = float(row.avg_duration) if row.avg_duration else 0
			date_dict[date_str]['by_type'][row.task_type] = {
				'avg_duration': duration,
				'count': row.count
			}
			date_dict[date_str]['total_duration'] += duration * row.count
			date_dict[date_str]['total_count'] += row.count

		# 计算总体平均
		for date_str in date_dict:
			if date_dict[date_str]['total_count'] > 0:
				date_dict[date_str]['avg_duration'] = (
						date_dict[date_str]['total_duration'] / date_dict[date_str]['total_count']
				)

		return {
			'duration_stats': list(date_dict.values()),
			'days': days,
			'task_type': task_type or 'all'
		}

	async def create_running_task (
			self,
			task_type: str,
			parameters: Optional[Dict[str, Any]] = None
	) -> Optional[DataSyncTask]:
		"""创建运行中的任务"""
		task_data = {
			'task_type': task_type,
			'status': 'running',
			'start_time': datetime.now(),
			'parameters': parameters or {},
			'total_records': 0
		}

		return await self.create(task_data)

	async def complete_task (
			self,
			task_id: int,
			total_records: int = 0,
			error_message: Optional[str] = None
	) -> bool:
		"""完成任务"""
		update_data = {
			'status': 'completed' if not error_message else 'failed',
			'end_time': datetime.now(),
			'total_records': total_records
		}

		if error_message:
			update_data['error_message'] = error_message

		result = await self.update(task_id, update_data)
		return result is not None

	async def update_task_progress (
			self,
			task_id: int,
			total_records: int,
			status: Optional[str] = None
	) -> bool:
		"""更新任务进度"""
		update_data = {'total_records': total_records}

		if status:
			update_data['status'] = status

		result = await self.update(task_id, update_data)
		return result is not None

	async def fail_task (
			self,
			task_id: int,
			error_message: str
	) -> bool:
		"""标记任务失败"""
		update_data = {
			'status': 'failed',
			'end_time': datetime.now(),
			'error_message': error_message
		}

		result = await self.update(task_id, update_data)
		return result is not None

	async def get_failed_tasks (
			self,
			hours: int = 24,
			task_type: Optional[str] = None
	) -> List[DataSyncTask]:
		"""获取失败的任务"""
		return await self.get_by_status('failed', task_type, hours)

	async def get_task_success_rate (
			self,
			task_type: str,
			days: int = 30
	) -> Dict[str, Any]:
		"""获取任务成功率"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		result = await self.session.execute(
			select(
				func.count(DataSyncTask.id).label('total'),
				func.sum(case([(DataSyncTask.status == 'completed', 1)], else_=0)).label('success'),
				func.sum(case([(DataSyncTask.status == 'failed', 1)], else_=0)).label('failed')
			).where(
				and_(
					DataSyncTask.task_type == task_type,
					DataSyncTask.start_time >= start_date,
					DataSyncTask.start_time <= end_date
				)
			)
		)

		row = result.first()
		if not row:
			return {
				'task_type': task_type,
				'days': days,
				'total': 0,
				'success': 0,
				'failed': 0,
				'success_rate': 0
			}

		total = row.total or 0
		success = row.success or 0
		failed = row.failed or 0
		success_rate = success / total * 100 if total > 0 else 0

		return {
			'task_type': task_type,
			'days': days,
			'total': total,
			'success': success,
			'failed': failed,
			'success_rate': success_rate
		}

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[DataSyncTask]:
		"""批量创建同步任务记录"""
		return await self.base_repo.batch_create(data_list)

	async def delete_old_tasks (
			self,
			days: int = 90,
			keep_successful: bool = True
	) -> int:
		"""删除旧任务记录"""
		cutoff_time = datetime.now() - timedelta(days=days)

		filters = [DataSyncTask.start_time < cutoff_time]

		if keep_successful:
			filters.append(DataSyncTask.status != 'completed')

		# 获取要删除的记录
		query = select(DataSyncTask.id).where(and_(*filters))

		result = await self.session.execute(query)
		old_task_ids = [row[0] for row in result.all()]

		# 批量删除
		deleted_count = 0
		for task_id in old_task_ids:
			success = await self.delete(task_id, soft=False)
			if success:
				deleted_count += 1

		return deleted_count

	async def get_task_summary (self) -> Dict[str, Any]:
		"""获取同步任务数据摘要"""
		# 今日统计
		today_tasks = await self.get_today_tasks()
		today_stats = {
			'total': len(today_tasks),
			'running': sum(1 for t in today_tasks if t.status == 'running'),
			'completed': sum(1 for t in today_tasks if t.status == 'completed'),
			'failed': sum(1 for t in today_tasks if t.status == 'failed'),
			'total_records': sum(t.total_records or 0 for t in today_tasks)
		}

		# 最近7天统计
		week_stats = await self.get_task_statistics(
			start_date=datetime.now().date() - timedelta(days=7)
		)

		# 正在运行的任务
		running_tasks = await self.get_running_tasks()

		# 最近失败的任务
		failed_tasks = await self.get_failed_tasks(hours=24)

		# 任务类型分布
		type_dist = await self.session.execute(
			select(
				DataSyncTask.task_type,
				func.count(DataSyncTask.id).label('count')
			).group_by(
				DataSyncTask.task_type
			).order_by(
				func.count(DataSyncTask.id).desc()
			)
		)

		type_stats = {row.task_type: row.count for row in type_dist.all()}

		return {
			'today': today_stats,
			'last_7_days': week_stats,
			'running_tasks': [
				{
					'id': t.id,
					'task_type': t.task_type,
					'start_time': t.start_time,
					'total_records': t.total_records
				}
				for t in running_tasks[:10]  # 只显示前10个
			],
			'recent_failed_tasks': [
				{
					'id': t.id,
					'task_type': t.task_type,
					'start_time': t.start_time,
					'error_message': t.error_message
				}
				for t in failed_tasks[:10]  # 只显示前10个
			],
			'type_distribution': type_stats,
			'total_task_types': len(type_stats)
		}