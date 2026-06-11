# -*- coding: utf-8 -*-
"""
数据同步任务Repository
提供数据同步任务记录的统一访问接口

位置：shared/database/repositories/operation/task/data_sync_task_repo.py

设计原则：
1. 纯数据访问层，不做业务逻辑
2. 一表一Repository，对应DataSyncTask模型
3. 方法名明确表示数据操作类型
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, case, desc

from shared.database.repositories.base.repository_base import BaseRepository
from shared.database.repositories.types import RepositoryResult
from shared.database.models.business_models import DataSyncTask


class DataSyncTaskRepository(BaseRepository[DataSyncTask]):
	"""数据同步任务Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化数据同步任务Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, DataSyncTask)

	# ==================== 基础查询方法 ====================

	async def get_by_task_type (
			self,
			task_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100
	) -> List[DataSyncTask]:
		"""
		根据任务类型获取同步任务

		Args:
			task_type: 任务类型
			start_date: 开始日期
			end_date: 结束日期
			limit: 返回数量限制

		Returns:
			数据同步任务列表
		"""
		query = select(self.model).where(self.model.task_type == task_type)

		if start_date:
			# 转换为datetime包含时间部分
			query = query.where(self.model.start_time >= datetime.combine(start_date, datetime.min.time()))
		if end_date:
			# 转换为datetime包含时间部分
			query = query.where(self.model.start_time <= datetime.combine(end_date, datetime.max.time()))

		query = query.order_by(desc(self.model.start_time)).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_by_status (
			self,
			status: str,
			task_type: Optional[str] = None,
			hours: int = 24
	) -> List[DataSyncTask]:
		"""
		根据状态获取同步任务

		Args:
			status: 任务状态
			task_type: 任务类型筛选
			hours: 时间范围（小时）

		Returns:
			数据同步任务列表
		"""
		cutoff_time = datetime.now() - timedelta(hours=hours)

		query = select(self.model).where(
			and_(
				self.model.status == status,
				self.model.start_time >= cutoff_time
			)
		)

		if task_type:
			query = query.where(self.model.task_type == task_type)

		query = query.order_by(desc(self.model.start_time))

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_running_tasks (self) -> List[DataSyncTask]:
		"""
		获取正在运行的任务

		Returns:
			运行中的任务列表
		"""
		return await self.get_by_status('running')

	async def get_by_user_id (
			self,
			user_id: str,
			limit: int = 20,
			offset: int = 0,
			status: Optional[str] = None,
			group: Optional[str] = None,
			parent_only: bool = False,
	) -> List[DataSyncTask]:
		"""
		根据用户ID获取同步任务（支持服务端分页）

		Args:
			user_id: 用户ID
			limit: 每页数量
			offset: 偏移量
			status: 任务状态筛选（可选，WHERE 过滤）
			group: 分组筛选（可选，匹配 task_type）
			parent_only: True 时只返回根任务（parent_task_id IS NULL）

		Returns:
			数据同步任务列表
		"""
		query = select(self.model).where(self.model.user_id == user_id)

		if status:
			query = query.where(self.model.status == status)

		if parent_only:
			query = query.where(self.model.parent_task_id.is_(None))

		query = query.order_by(desc(self.model.created_at)).limit(limit).offset(offset)

		result = await self.session.execute(query)
		tasks = result.scalars().all()

		# 内存中按 group 过滤（group → task_type 映射由 handler 处理）
		if group:
			tasks = [t for t in tasks if t.task_type == group or t.parent_task_id]

		return tasks

	async def get_children (self, parent_task_id: str) -> List[DataSyncTask]:
		"""获取某个父任务的所有子任务"""
		query = select(self.model).where(self.model.parent_task_id == parent_task_id)
		query = query.order_by(self.model.created_at.asc())
		result = await self.session.execute(query)
		return result.scalars().all()

	async def count_by_user (self, user_id: str, status: Optional[str] = None) -> int:
		"""统计用户的根任务总数（parent_task_id IS NULL，用于分页）"""
		query = select(func.count(self.model.id)).where(
			self.model.user_id == user_id,
			self.model.parent_task_id.is_(None),
		)
		if status:
			query = query.where(self.model.status == status)
		result = await self.session.execute(query)
		return result.scalar() or 0

	async def get_recent_tasks (
			self,
			hours: int = 24,
			task_type: Optional[str] = None
	) -> List[DataSyncTask]:
		"""
		获取最近N小时的任务

		Args:
			hours: 小时数
			task_type: 任务类型筛选

		Returns:
			最近的任务列表
		"""
		cutoff_time = datetime.now() - timedelta(hours=hours)

		query = select(self.model).where(
			self.model.start_time >= cutoff_time
		)

		if task_type:
			query = query.where(self.model.task_type == task_type)

		query = query.order_by(desc(self.model.start_time))

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_today_tasks (self, task_type: Optional[str] = None) -> List[DataSyncTask]:
		"""
		获取今日任务

		Args:
			task_type: 任务类型筛选

		Returns:
			今日任务列表
		"""
		today = datetime.now().date()
		tomorrow = today + timedelta(days=1)

		today_start = datetime.combine(today, datetime.min.time())
		tomorrow_start = datetime.combine(tomorrow, datetime.min.time())

		query = select(self.model).where(
			and_(
				self.model.start_time >= today_start,
				self.model.start_time < tomorrow_start
			)
		)

		if task_type:
			query = query.where(self.model.task_type == task_type)

		query = query.order_by(desc(self.model.start_time))

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_task (
			self,
			task_type: str,
			status: Optional[str] = None
	) -> Optional[DataSyncTask]:
		"""
		获取最新的任务

		Args:
			task_type: 任务类型
			status: 状态筛选

		Returns:
			最新的任务对象或None
		"""
		query = select(self.model).where(
			self.model.task_type == task_type
		)

		if status:
			query = query.where(self.model.status == status)

		query = query.order_by(desc(self.model.start_time)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	# ==================== 统计分析方法 ====================

	async def get_task_statistics (
			self,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			task_type: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取任务统计信息

		Args:
			start_date: 开始日期
			end_date: 结束日期
			task_type: 任务类型筛选

		Returns:
			统计信息字典
		"""
		# 构建过滤条件
		filters = []
		if start_date:
			filters.append(self.model.start_time >= datetime.combine(start_date, datetime.min.time()))
		if end_date:
			filters.append(self.model.start_time <= datetime.combine(end_date, datetime.max.time()))
		if task_type:
			filters.append(self.model.task_type == task_type)

		where_clause = and_(*filters) if filters else True

		# 总任务数
		total_count = await self.count(*filters) if filters else await self.count()

		# 按状态统计
		status_stats_query = select(
			self.model.status,
			func.count(self.model.id).label('count'),
			func.sum(self.model.total_records).label('total_records')
		).where(
			where_clause
		).group_by(
			self.model.status
		).order_by(
			func.count(self.model.id).desc()
		)

		status_stats_result = await self.session.execute(status_stats_query)
		status_stats_dict = {}
		for row in status_stats_result.all():
			status_stats_dict[row.status] = {
				'count': row.count,
				'total_records': row.total_records or 0
			}

		# 按任务类型统计
		type_stats_query = select(
			self.model.task_type,
			func.count(self.model.id).label('count'),
			func.sum(self.model.total_records).label('total_records'),
			func.avg(
				func.extract('epoch', self.model.end_time - self.model.start_time)
			).label('avg_duration')
		).where(
			and_(
				where_clause,
				self.model.end_time.isnot(None),
				self.model.start_time.isnot(None)
			)
		).group_by(
			self.model.task_type
		).order_by(
			func.count(self.model.id).desc()
		)

		type_stats_result = await self.session.execute(type_stats_query)
		type_stats_list = []
		for row in type_stats_result.all():
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
			'success_rate': round(success_rate, 2),
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
		"""
		获取任务持续时间统计

		Args:
			task_type: 任务类型筛选
			days: 天数

		Returns:
			持续时间统计信息
		"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		start_datetime = datetime.combine(start_date, datetime.min.time())
		end_datetime = datetime.combine(end_date, datetime.max.time())

		query = select(
			func.date(self.model.start_time).label('date'),
			self.model.task_type,
			func.avg(
				func.extract('epoch', self.model.end_time - self.model.start_time)
			).label('avg_duration'),
			func.count(self.model.id).label('count')
		).where(
			and_(
				self.model.start_time >= start_datetime,
				self.model.start_time <= end_datetime,
				self.model.end_time.isnot(None),
				self.model.status == 'completed'
			)
		)

		if task_type:
			query = query.where(self.model.task_type == task_type)

		query = query.group_by(
			func.date(self.model.start_time),
			self.model.task_type
		).order_by(
			func.date(self.model.start_time).asc()
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

	# ==================== 任务操作方法 ====================

	async def create_running_task (
			self,
			task_type: str,
			parameters: Optional[Dict[str, Any]] = None
	) -> Optional[DataSyncTask]:
		"""
		创建运行中的任务

		Args:
			task_type: 任务类型
			parameters: 任务参数

		Returns:
			创建的任务对象或None
		"""
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
			task_id: str,
			total_records: int = 0,
			error_message: Optional[str] = None
	) -> bool:
		"""
		完成任务

		Args:
			task_id: 任务ID
			total_records: 总记录数
			error_message: 错误信息

		Returns:
			是否成功
		"""
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
			task_id: str,
			total_records: int,
			status: Optional[int] = None
	) -> bool:
		"""
		更新任务进度

		Args:
			task_id: 任务ID
			total_records: 总记录数
			status: 状态

		Returns:
			是否成功
		"""
		update_data = {'total_records': total_records}

		if status:
			update_data['status'] = status

		result = await self.update(task_id, update_data)
		return result is not None

	async def fail_task (
			self,
			task_id: str,
			error_message: str
	) -> bool:
		"""
		标记任务失败

		Args:
			task_id: 任务ID
			error_message: 错误信息

		Returns:
			是否成功
		"""
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
		"""
		获取失败的任务

		Args:
			hours: 小时数
			task_type: 任务类型筛选

		Returns:
			失败任务列表
		"""
		return await self.get_by_status('failed', task_type, hours)

	# ==================== 性能分析方法 ====================

	async def get_task_success_rate (
			self,
			task_type: str,
			days: int = 30
	) -> Dict[str, Any]:
		"""
		获取任务成功率

		Args:
			task_type: 任务类型
			days: 天数

		Returns:
			成功率统计信息
		"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		start_datetime = datetime.combine(start_date, datetime.min.time())
		end_datetime = datetime.combine(end_date, datetime.max.time())

		result = await self.session.execute(
			select(
				func.count(self.model.id).label('total'),
				func.sum(
					case(
						(self.model.status == 'completed', 1),
						else_=0
					)
				).label('success'),
				func.sum(
					case(
						(self.model.status == 'failed', 1),
						else_=0
					)
				).label('failed')
			).where(
				and_(
					self.model.task_type == task_type,
					self.model.start_time >= start_datetime,
					self.model.start_time <= end_datetime
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
			'success_rate': round(success_rate, 2)
		}

	# ==================== 清理方法 ====================

	async def delete_old_tasks (
			self,
			days: int = 90,
			keep_successful: bool = True
	) -> int:
		"""
		删除旧任务记录

		Args:
			days: 天数
			keep_successful: 是否保留成功记录

		Returns:
			删除的记录数
		"""
		cutoff_time = datetime.now() - timedelta(days=days)

		filters = [self.model.start_time < cutoff_time]

		if keep_successful:
			filters.append(self.model.status != 'completed')

		# 获取要删除的记录
		query = select(self.model.id).where(and_(*filters))

		result = await self.session.execute(query)
		old_task_ids = [row[0] for row in result.all()]

		# 批量删除
		deleted_count = 0
		for task_id in old_task_ids:
			success = await self.delete(task_id, soft=False)
			if success:
				deleted_count += 1

		return deleted_count

	# ==================== 摘要方法 ====================

	async def get_by_task_id(self, task_id: str) -> RepositoryResult[Optional[DataSyncTask]]:
		"""
		根据任务ID获取同步任务

		Args:
			task_id: 任务ID（如 sync_abc12345）

		Returns:
			RepositoryResult: 包含数据同步任务对象的查询结果
		"""
		try:
			# 直接按task_id字段查询
			query = select(self.model).where(self.model.task_id == task_id)
			result = await self.session.execute(query)
			task = result.scalar_one_or_none()

			if task:
				return RepositoryResult(
					success=True,
					data=task,
				)
			else:
				return RepositoryResult(
					success=False,
					error=f"数据同步任务不存在: {task_id}",
				)
		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)

	async def get_task_summary (self) -> Dict[str, Any]:
		"""
		获取同步任务数据摘要

		Returns:
			任务摘要信息
		"""
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
		type_dist_query = select(
			self.model.task_type,
			func.count(self.model.id).label('count')
		).group_by(
			self.model.task_type
		).order_by(
			func.count(self.model.id).desc()
		)

		type_dist_result = await self.session.execute(type_dist_query)
		type_stats = {row.task_type: row.count for row in type_dist_result.all()}

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