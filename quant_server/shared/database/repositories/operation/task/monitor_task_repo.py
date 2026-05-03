# -*- coding: utf-8 -*-
"""
监控任务Repository
负责MonitorTask表的数据访问操作

位置：shared/database/repositories/operation/task/monitor_task_repo.py

继承自BaseRepository，提供监控任务的配置和管理功能
包括任务调度、状态更新、运行统计等
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, asc, cast, Integer

from shared.database.models.business_models import MonitorTask
from shared.database.repositories.base.repository_base import BaseRepository


async def _is_task_due (task: MonitorTask, current_time: datetime) -> bool:
	"""
	检查任务是否到了执行时间

	Args:
		task: 监控任务
		current_time: 当前时间

	Returns:
		bool: 是否到了执行时间
	"""
	if not task.is_active:
		return False

	# 如果没有最后运行时间，任务需要运行
	if task.last_run_at is None:
		return True

	schedule_config = task.schedule_config or {}

	# 获取调度间隔（默认为5分钟）
	interval_minutes = schedule_config.get('interval_minutes', 5)

	# 计算下次运行时间
	next_run_time = task.last_run_at + timedelta(minutes=interval_minutes)

	return current_time >= next_run_time


class MonitorTaskRepository(BaseRepository[MonitorTask]):
	"""
	监控任务Repository
	继承自BaseRepository，提供监控任务的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化监控任务Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, MonitorTask)

	async def create_monitor_task (
			self,
			task_name: str,
			task_type: str,
			target_type: str,
			schedule_config: Dict[str, Any],
			check_config: Dict[str, Any],
			target_id: Optional[str] = None,
			alert_config: Optional[Dict[str, Any]] = None,
			is_active: bool = True,
			**kwargs
	) -> MonitorTask:
		"""
		创建监控任务

		Args:
			task_name: 任务名称
			task_type: 任务类型（system/strategy/data/trade）
			target_type: 监控目标类型
			schedule_config: 调度配置
			check_config: 检查配置
			target_id: 监控目标ID（可选）
			alert_config: 报警配置（可选）
			is_active: 是否激活
			**kwargs: 其他字段

		Returns:
			MonitorTask: 创建的监控任务对象
		"""
		try:
			task_data = {
				'task_name': task_name,
				'task_type': task_type,
				'target_type': target_type,
				'target_id': target_id,
				'schedule_config': schedule_config,
				'check_config': check_config,
				'alert_config': alert_config or {},
				'is_active': bool(is_active)
			}

			# 添加其他字段
			task_data.update(kwargs)

			return await self.create(task_data)
		except Exception as e:
			raise ValueError(f"创建监控任务失败: {str(e)}")

	async def get_active_tasks (
			self,
			task_type: Optional[str] = None,
			target_type: Optional[str] = None
	) -> List[MonitorTask]:
		"""
		获取活跃的监控任务

		Args:
			task_type: 任务类型过滤（可选）
			target_type: 目标类型过滤（可选）

		Returns:
			List[MonitorTask]: 活跃任务列表
		"""
		try:
			# 使用明确的类型转换
			filters: Dict[str, Any] = {'is_active': True}

			if task_type is not None:
				filters['task_type'] = str(task_type)
			if target_type is not None:
				filters['target_type'] = str(target_type)

			return await self.get_all(**filters)
		except Exception as e:
			raise ValueError(f"获取活跃任务失败: {str(e)}")

	async def get_tasks_due_for_execution (
			self,
			max_concurrent: int = 10
	) -> List[MonitorTask]:
		"""
		获取需要执行的任务（基于调度配置）

		Args:
			max_concurrent: 最大并发任务数

		Returns:
			List[MonitorTask]: 需要执行的任务列表
		"""
		try:
			# 获取所有活跃任务
			tasks = await self.get_active_tasks()

			due_tasks = []
			now = datetime.now()

			for task in tasks:
				# 检查是否到了执行时间
				if await _is_task_due(task, now):
					due_tasks.append(task)

				if len(due_tasks) >= max_concurrent:
					break

			return due_tasks
		except Exception as e:
			raise ValueError(f"获取待执行任务失败: {str(e)}")

	async def update_last_run (
			self,
			task_id: str,
			success: bool = True,
			next_run_at: Optional[datetime] = None
	) -> bool:
		"""
		更新任务最后运行时间

		Args:
			task_id: 任务ID
			success: 是否运行成功（保留参数以备未来使用）
			next_run_at: 下次运行时间（可选）

		Returns:
			bool: 更新是否成功
		"""
		try:
			update_data = {
				'last_run_at': datetime.now()
			}

			if next_run_at:
				update_data['next_run_at'] = next_run_at

			# 记录成功状态到运行日志中（可扩展）
			# 当前success参数保留以备未来记录运行状态使用

			result = await self.update(task_id, update_data)
			return result is not None
		except Exception as e:
			raise ValueError(f"更新任务运行时间失败: {str(e)}")

	async def calculate_next_run_time (
			self,
			task_id: str,
			current_time: Optional[datetime] = None
	) -> Optional[datetime]:
		"""
		计算任务的下次运行时间

		Args:
			task_id: 任务ID
			current_time: 当前时间（可选）

		Returns:
			Optional[datetime]: 下次运行时间
		"""
		try:
			task = await self.get(task_id)

			if task is None or not task.is_active:
				return None

			current_time = current_time or datetime.now()
			schedule_config = task.schedule_config or {}

			# 获取调度间隔（默认为5分钟）
			interval_minutes = schedule_config.get('interval_minutes', 5)

			if task.last_run_at is not None:
				# 基于最后运行时间计算
				next_run = task.last_run_at + timedelta(minutes=interval_minutes)

				# 如果下次运行时间已经过去，使用当前时间+间隔
				if next_run < current_time:
					next_run = current_time + timedelta(minutes=interval_minutes)
			else:
				# 从未运行过，立即运行
				next_run = current_time

			return next_run
		except Exception as e:
			raise ValueError(f"计算下次运行时间失败: {str(e)}")

	async def update_task_schedule (
			self,
			task_id: str,
			schedule_config: Optional[Dict[str, Any]] = None,
			is_active: Optional[bool] = None
	) -> Optional[MonitorTask]:
		"""
		更新任务调度配置

		Args:
			task_id: 任务ID
			schedule_config: 新的调度配置（可选）
			is_active: 是否激活（可选）

		Returns:
			Optional[MonitorTask]: 更新后的任务对象
		"""
		try:
			update_data = {}

			if schedule_config is not None:
				update_data['schedule_config'] = schedule_config

			if is_active is not None:
				update_data['is_active'] = bool(is_active)

			return await self.update(task_id, update_data)
		except Exception as e:
			raise ValueError(f"更新任务调度失败: {str(e)}")

	async def get_tasks_by_target (
			self,
			target_type: str,
			target_id: str
	) -> List[MonitorTask]:
		"""
		获取指定监控目标的监控任务

		Args:
			target_type: 目标类型
			target_id: 目标ID

		Returns:
			List[MonitorTask]: 监控任务列表
		"""
		try:
			return await self.get_all(
				target_type=target_type,
				target_id=target_id,
				is_active=True
			)
		except Exception as e:
			raise ValueError(f"获取目标监控任务失败: {str(e)}")

	async def search_tasks (
			self,
			keyword: str,
			task_type: Optional[str] = None,
			only_active: bool = True,
			limit: int = 50
	) -> List[MonitorTask]:
		"""
		搜索监控任务

		Args:
			keyword: 搜索关键词
			task_type: 任务类型过滤（可选）
			only_active: 是否只搜索活跃任务
			limit: 限制记录数

		Returns:
			List[MonitorTask]: 搜索结果的监控任务列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.task_name.ilike(f'%{keyword}%'),
					self.model.target_type.ilike(f'%{keyword}%'),
					self.model.target_id.ilike(f'%{keyword}%') if self.model.target_id else False
				)
			)

			if task_type:
				query = query.where(self.model.task_type == task_type)

			if only_active:
				query = query.where(self.model.is_active == True)

			query = query.limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise ValueError(f"搜索监控任务失败: {str(e)}")

	async def get_task_statistics (self) -> Dict[str, Any]:
		"""
		获取监控任务统计

		Returns:
			Dict[str, Any]: 任务统计信息
		"""
		try:
			# 统计各类型任务数量
			query = select(
				self.model.task_type,
				func.count(self.model.id).label('count'),
				func.sum(
					cast(self.model.is_active, Integer)
				).label('active_count'),
				func.max(self.model.last_run_at).label('last_run_max'),
				func.min(self.model.last_run_at).label('last_run_min')
			).group_by(self.model.task_type)

			result = await self.session.execute(query)

			stats = {
				'total': 0,
				'active': 0,
				'inactive': 0,
				'by_type': {}
			}

			for row in result.all():
				task_type, count, active_count, last_run_max, last_run_min = row
				stats['by_type'][task_type] = {
					'total': count,
					'active': active_count,
					'inactive': count - active_count,
					'last_run_max': last_run_max,
					'last_run_min': last_run_min
				}
				stats['total'] += count
				stats['active'] += active_count

			stats['inactive'] = stats['total'] - stats['active']

			return stats
		except Exception as e:
			raise ValueError(f"获取任务统计失败: {str(e)}")

	async def get_tasks_with_issues (
			self,
			hours: int = 24
	) -> List[MonitorTask]:
		"""
		获取有问题的监控任务（长时间未运行）

		Args:
			hours: 时间阈值（小时）

		Returns:
			List[MonitorTask]: 有问题的任务列表
		"""
		try:
			time_threshold = datetime.now() - timedelta(hours=hours)

			query = select(self.model).where(
				and_(
					self.model.is_active == True,
					or_(
						self.model.last_run_at.is_(None),
						self.model.last_run_at < time_threshold
					)
				)
			).order_by(asc(self.model.last_run_at))

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise ValueError(f"获取有问题任务失败: {str(e)}")

	async def deactivate_task (self, task_id: str) -> bool:
		"""
		停用监控任务

		Args:
			task_id: 任务ID

		Returns:
			bool: 停用是否成功
		"""
		try:
			result = await self.update(task_id, {'is_active': False})
			return result is not None
		except Exception as e:
			raise ValueError(f"停用监控任务失败: {str(e)}")