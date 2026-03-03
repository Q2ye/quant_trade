# quant_server/shared/database/repositories/analysis/performance/analysis_task_repository.py
"""
分析任务Repository
负责AnalysisTask表的数据访问操作

继承自BaseRepository，提供分析任务的管理功能
包括任务创建、状态跟踪、进度更新等业务方法
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, desc, asc
from sqlalchemy.orm import joinedload

from quant_server.shared.database.models.business_models import AnalysisTask
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class AnalysisTaskRepository(BaseRepository[AnalysisTask]):
	"""
	分析任务Repository
	继承自BaseRepository，提供分析任务的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化分析任务Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, AnalysisTask)

	async def create_analysis_task (
			self,
			task_name: str,
			analysis_type: str,
			parameters: Dict[str, Any],
			created_by: int,
			report_id: Optional[int] = None
	) -> AnalysisTask:
		"""
		创建分析任务

		Args:
			task_name: 任务名称
			analysis_type: 分析类型（performance/risk/attribution）
			parameters: 分析参数
			created_by: 创建人ID
			report_id: 关联的报告ID（可选）

		Returns:
			AnalysisTask: 创建的任务对象
		"""
		try:
			# 生成唯一的任务ID
			import uuid
			task_id = str(uuid.uuid4())

			task_data = {
				'task_id': task_id,
				'task_name': task_name,
				'analysis_type': analysis_type,
				'parameters': parameters,
				'status': 'pending',
				'progress': 0.0,
				'created_by': created_by,
				'report_id': report_id
			}

			return await self.create(task_data)
		except Exception as e:
			raise RepositoryError(f"创建分析任务失败: {str(e)}")

	async def get_task_by_task_id (
			self,
			task_id: str
	) -> Optional[AnalysisTask]:
		"""
		根据任务ID获取任务

		Args:
			task_id: 任务ID

		Returns:
			Optional[AnalysisTask]: 任务对象或None
		"""
		try:
			return await self.get_by(task_id=task_id)
		except Exception as e:
			raise RepositoryError(f"获取任务失败: {str(e)}")

	async def update_task_status (
			self,
			task_id: str,
			status: str,
			progress: Optional[float] = None,
			result: Optional[Dict[str, Any]] = None,
			error_message: Optional[str] = None
	) -> bool:
		"""
		更新任务状态

		Args:
			task_id: 任务ID
			status: 新状态（pending, running, completed, failed, cancelled）
			progress: 进度（0-1，可选）
			result: 分析结果（可选）
			error_message: 错误信息（可选）

		Returns:
			bool: 更新是否成功
		"""
		try:
			# 先根据task_id找到记录
			task = await self.get_by(task_id=task_id)

			if not task:
				return False

			update_data = {'status': status}

			if status == 'running' and not task.started_at:
				update_data['started_at'] = datetime.now()
			elif status in ['completed', 'failed', 'cancelled'] and not task.completed_at:
				update_data['completed_at'] = datetime.now()

			if progress is not None:
				update_data['progress'] = progress

			if result is not None:
				update_data['result'] = result

			if error_message is not None:
				update_data['error_message'] = error_message

			return await self.update(task.id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"更新任务状态失败: {str(e)}")

	async def start_task (
			self,
			task_id: str,
			progress: float = 0.0
	) -> bool:
		"""
		开始任务

		Args:
			task_id: 任务ID
			progress: 初始进度

		Returns:
			bool: 开始是否成功
		"""
		return await self.update_task_status(
			task_id, 'running', progress
		)

	async def update_task_progress (
			self,
			task_id: str,
			progress: float,
			intermediate_result: Optional[Dict[str, Any]] = None
	) -> bool:
		"""
		更新任务进度

		Args:
			task_id: 任务ID
			progress: 进度（0-1）
			intermediate_result: 中间结果（可选）

		Returns:
			bool: 更新是否成功
		"""
		try:
			task = await self.get_by(task_id=task_id)

			if not task:
				return False

			update_data = {'progress': progress}

			if intermediate_result is not None:
				# 合并中间结果
				current_result = task.result or {}
				if isinstance(current_result, dict) and isinstance(intermediate_result, dict):
					current_result.update(intermediate_result)
					update_data['result'] = current_result

			return await self.update(task.id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"更新任务进度失败: {str(e)}")

	async def complete_task (
			self,
			task_id: str,
			result: Dict[str, Any],
			report_id: Optional[int] = None
	) -> bool:
		"""
		完成任务

		Args:
			task_id: 任务ID
			result: 最终结果
			report_id: 关联的报告ID（可选）

		Returns:
			bool: 完成是否成功
		"""
		try:
			update_data = {
				'status': 'completed',
				'progress': 1.0,
				'result': result,
				'completed_at': datetime.now()
			}

			if report_id is not None:
				update_data['report_id'] = report_id

			task = await self.get_by(task_id=task_id)

			if not task:
				return False

			return await self.update(task.id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"完成任务失败: {str(e)}")

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
			bool: 标记是否成功
		"""
		return await self.update_task_status(
			task_id, 'failed', error_message=error_message
		)

	async def cancel_task (
			self,
			task_id: str,
			reason: Optional[str] = None
	) -> bool:
		"""
		取消任务

		Args:
			task_id: 任务ID
			reason: 取消原因（可选）

		Returns:
			bool: 取消是否成功
		"""
		return await self.update_task_status(
			task_id, 'cancelled', error_message=reason
		)

	async def get_user_tasks (
			self,
			user_id: int,
			analysis_type: Optional[str] = None,
			status: Optional[str] = None,
			limit: int = 100,
			offset: int = 0
	) -> Tuple[List[AnalysisTask], int]:
		"""
		获取用户的任务

		Args:
			user_id: 用户ID
			analysis_type: 分析类型过滤（可选）
			status: 状态过滤（可选）
			limit: 限制记录数
			offset: 偏移量

		Returns:
			Tuple[List[AnalysisTask], int]: 任务列表和总数
		"""
		try:
			conditions = [self.model.created_by == user_id]

			if analysis_type:
				conditions.append(self.model.analysis_type == analysis_type)

			if status:
				conditions.append(self.model.status == status)

			# 获取总数
			count_query = select(func.count()).select_from(self.model).where(
				and_(*conditions)
			)
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 获取数据
			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				desc(self.model.created_at)
			).offset(offset).limit(limit)

			result = await self.session.execute(query)
			tasks = result.scalars().all()

			return tasks, total
		except Exception as e:
			raise RepositoryError(f"获取用户任务失败: {str(e)}")

	async def get_running_tasks (
			self,
			analysis_type: Optional[str] = None,
			max_duration_hours: Optional[int] = None,
			limit: int = 50
	) -> List[AnalysisTask]:
		"""
		获取运行中的任务

		Args:
			analysis_type: 分析类型过滤（可选）
			max_duration_hours: 最大运行时长（小时，可选）
			limit: 限制记录数

		Returns:
			List[AnalysisTask]: 运行中的任务列表
		"""
		try:
			conditions = [self.model.status == 'running']

			if analysis_type:
				conditions.append(self.model.analysis_type == analysis_type)

			if max_duration_hours:
				time_threshold = datetime.now() - timedelta(hours=max_duration_hours)
				conditions.append(
					or_(
						self.model.started_at.is_(None),
						self.model.started_at < time_threshold
					)
				)

			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				asc(self.model.started_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取运行中任务失败: {str(e)}")

	async def get_pending_tasks (
			self,
			analysis_type: Optional[str] = None,
			limit: int = 100
	) -> List[AnalysisTask]:
		"""
		获取待处理的任务

		Args:
			analysis_type: 分析类型过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisTask]: 待处理任务列表
		"""
		try:
			conditions = [self.model.status == 'pending']

			if analysis_type:
				conditions.append(self.model.analysis_type == analysis_type)

			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				asc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取待处理任务失败: {str(e)}")

	async def get_task_statistics (
			self,
			days: Optional[int] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取任务统计信息

		Args:
			days: 时间范围（天数，可选）
			user_id: 用户ID过滤（可选）

		Returns:
			Dict[str, Any]: 任务统计信息
		"""
		try:
			# 构建基础查询
			query = select(
				self.model.analysis_type,
				self.model.status,
				func.count(self.model.id).label('count'),
				func.avg(self.model.progress).label('avg_progress')
			)

			conditions = []

			if days:
				time_threshold = datetime.now() - timedelta(days=days)
				conditions.append(self.model.created_at >= time_threshold)

			if user_id:
				conditions.append(self.model.created_by == user_id)

			if conditions:
				query = query.where(and_(*conditions))

			query = query.group_by(
				self.model.analysis_type,
				self.model.status
			)

			result = await self.session.execute(query)

			stats = {
				'total': 0,
				'by_type': {},
				'by_status': {
					'pending': 0,
					'running': 0,
					'completed': 0,
					'failed': 0,
					'cancelled': 0
				},
				'avg_duration': 0
			}

			for analysis_type, status, count, avg_progress in result.all():
				if analysis_type not in stats['by_type']:
					stats['by_type'][analysis_type] = {
						'total': 0,
						'by_status': {
							'pending': 0,
							'running': 0,
							'completed': 0,
							'failed': 0,
							'cancelled': 0
						}
					}

				stats['by_type'][analysis_type]['total'] += count
				stats['by_type'][analysis_type]['by_status'][status] = count

				stats['by_status'][status] += count
				stats['total'] += count

			# 计算平均时长（仅限已完成的任务）
			duration_query = select(
				func.avg(
					func.extract('epoch', self.model.completed_at - self.model.started_at)
				).label('avg_duration')
			).where(
				and_(
					self.model.status == 'completed',
					self.model.started_at.isnot(None),
					self.model.completed_at.isnot(None)
				)
			)

			if days:
				time_threshold = datetime.now() - timedelta(days=days)
				duration_query = duration_query.where(self.model.created_at >= time_threshold)

			if user_id:
				duration_query = duration_query.where(self.model.created_by == user_id)

			duration_result = await self.session.execute(duration_query)
			avg_duration = duration_result.scalar()

			if avg_duration:
				stats['avg_duration'] = float(avg_duration)

			return stats
		except Exception as e:
			raise RepositoryError(f"获取任务统计失败: {str(e)}")

	async def get_long_running_tasks (
			self,
			hours: int = 24
	) -> List[AnalysisTask]:
		"""
		获取长时间运行的任务

		Args:
			hours: 时间阈值（小时）

		Returns:
			List[AnalysisTask]: 长时间运行的任务列表
		"""
		try:
			time_threshold = datetime.now() - timedelta(hours=hours)

			query = select(self.model).where(
				and_(
					self.model.status == 'running',
					self.model.started_at.isnot(None),
					self.model.started_at < time_threshold
				)
			).order_by(
				asc(self.model.started_at)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取长时间运行任务失败: {str(e)}")

	async def search_tasks (
			self,
			keyword: str,
			analysis_type: Optional[str] = None,
			status: Optional[str] = None,
			created_by: Optional[int] = None,
			limit: int = 50
	) -> List[AnalysisTask]:
		"""
		搜索任务

		Args:
			keyword: 搜索关键词
			analysis_type: 分析类型过滤（可选）
			status: 状态过滤（可选）
			created_by: 创建人过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisTask]: 搜索结果的任务列表
		"""
		try:
			conditions = []

			if keyword:
				conditions.append(
					or_(
						self.model.task_name.ilike(f'%{keyword}%'),
						self.model.task_id.ilike(f'%{keyword}%')
					)
				)

			if analysis_type:
				conditions.append(self.model.analysis_type == analysis_type)

			if status:
				conditions.append(self.model.status == status)

			if created_by:
				conditions.append(self.model.created_by == created_by)

			query = select(self.model)

			if conditions:
				query = query.where(and_(*conditions))

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索任务失败: {str(e)}")

	async def get_tasks_with_report (
			self,
			report_id: int,
			include_cancelled: bool = False
	) -> List[AnalysisTask]:
		"""
		获取与报告关联的任务

		Args:
			report_id: 报告ID
			include_cancelled: 是否包含已取消的任务

		Returns:
			List[AnalysisTask]: 关联的任务列表
		"""
		try:
			conditions = [self.model.report_id == report_id]

			if not include_cancelled:
				conditions.append(self.model.status != 'cancelled')

			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				desc(self.model.created_at)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取报告关联任务失败: {str(e)}")

	async def cleanup_old_tasks (
			self,
			days: int = 90,
			keep_completed: bool = True
	) -> int:
		"""
		清理旧的任务

		Args:
			days: 保留天数
			keep_completed: 是否保留已完成的任务

		Returns:
			int: 删除的记录数
		"""
		try:
			time_threshold = datetime.now() - timedelta(days=days)

			conditions = [self.model.created_at < time_threshold]

			if keep_completed:
				# 只删除非完成状态的任务
				conditions.append(self.model.status != 'completed')

			query = delete(self.model).where(and_(*conditions))

			result = await self.session.execute(query)
			await self.session.commit()

			return result.rowcount or 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧任务失败: {str(e)}")