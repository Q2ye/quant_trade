# quant_server/shared/database/repositories/operation/workflow/workflow_task_repo.py
"""
WorkflowTaskRepository - 工作流任务数据访问仓库

基于 BaseRepository 实现，提供对 workflow_tasks 表的 CRUD 操作
位置：quant_server/shared/database/repositories/operation/workflow/workflow_task_repo.py

表说明：workflow_tasks 表存储工作流任务实例，支持任务依赖和状态管理

设计原则：
1. 纯数据访问：只做 CRUD，不做业务逻辑
2. 异步支持：完全异步化设计
3. 类型安全：使用泛型确保类型一致性
4. 查询优化：提供工作流特定的查询方法
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import WorkflowTask
from shared.database.repositories.base import BaseRepository


class WorkflowTaskRepository(BaseRepository[WorkflowTask]):
	"""
	工作流任务仓库类

	继承自 BaseRepository，提供对 WorkflowTask 模型的专用数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化 WorkflowTaskRepository

		Args:
			session: 数据库会话，提供数据访问上下文
		"""
		super().__init__(session, WorkflowTask)

	# ==================== 专用查询方法 ====================

	async def get_by_workflow_id (self, workflow_id: str) -> List[WorkflowTask]:
		"""
		根据工作流ID获取所有任务

		Args:
			workflow_id: 工作流ID

		Returns:
			工作流任务列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.workflow_id == workflow_id)
				.order_by(self.model.created_at)
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取工作流任务失败: {str(e)}")

	async def get_by_workflow_and_task_id (self, workflow_id: str, task_id: str) -> Optional[WorkflowTask]:
		"""
		根据工作流ID和任务ID获取特定任务

		Args:
			workflow_id: 工作流ID
			task_id: 任务ID

		Returns:
			工作流任务对象或None
		"""
		try:
			query = (
				select(self.model)
				.where(
					and_(
						self.model.workflow_id == workflow_id,
						self.model.task_id == task_id
					)
				)
			)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取工作流任务失败: {str(e)}")

	async def get_pending_tasks (self, workflow_id: Optional[str] = None) -> List[WorkflowTask]:
		"""
		获取待处理的任务

		Args:
			workflow_id: 可选的特定工作流ID

		Returns:
			待处理任务列表
		"""
		try:
			query = select(self.model).where(self.model.status == 'pending')

			if workflow_id:
				query = query.where(self.model.workflow_id == workflow_id)

			query = query.order_by(self.model.created_at)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取待处理任务失败: {str(e)}")

	async def get_running_tasks (self, workflow_id: Optional[str] = None) -> List[WorkflowTask]:
		"""
		获取运行中的任务

		Args:
			workflow_id: 可选的特定工作流ID

		Returns:
			运行中任务列表
		"""
		try:
			query = select(self.model).where(self.model.status == 'running')

			if workflow_id:
				query = query.where(self.model.workflow_id == workflow_id)

			query = query.order_by(self.model.started_at)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取运行中任务失败: {str(e)}")

	async def get_completed_tasks (
			self,
			workflow_id: Optional[str] = None,
			limit: int = 100
	) -> List[WorkflowTask]:
		"""
		获取已完成的任务

		Args:
			workflow_id: 可选的特定工作流ID
			limit: 返回记录数限制

		Returns:
			已完成任务列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.status == 'completed')
				.order_by(self.model.completed_at.desc())
				.limit(limit)
			)

			if workflow_id:
				query = query.where(self.model.workflow_id == workflow_id)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取已完成任务失败: {str(e)}")

	async def get_failed_tasks (
			self,
			workflow_id: Optional[str] = None,
			limit: int = 100
	) -> List[WorkflowTask]:
		"""
		获取失败的任务

		Args:
			workflow_id: 可选的特定工作流ID
			limit: 返回记录数限制

		Returns:
			失败任务列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.status == 'failed')
				.order_by(self.model.updated_at.desc())
				.limit(limit)
			)

			if workflow_id:
				query = query.where(self.model.workflow_id == workflow_id)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取失败任务失败: {str(e)}")

	async def get_ready_tasks (self, workflow_id: str) -> List[WorkflowTask]:
		"""
		获取可执行的任务（状态为pending且依赖任务都已完成）

		Args:
			workflow_id: 工作流ID

		Returns:
			可执行任务列表
		"""
		try:
			# 先获取工作流中所有任务
			all_tasks = await self.get_by_workflow_id(workflow_id)

			# 构建任务映射
			task_map = {task.task_id: task for task in all_tasks}
			completed_tasks = set()
			ready_tasks = []

			# 遍历任务，检查依赖关系
			for task in all_tasks:
				if task.status == 'completed':
					completed_tasks.add(task.task_id)

			for task in all_tasks:
				if task.status == 'pending':
					dependencies = task.dependencies or []

					# 检查所有依赖是否都已完成
					all_deps_completed = all(
						dep in completed_tasks for dep in dependencies
					)

					if all_deps_completed:
						ready_tasks.append(task)

			return ready_tasks
		except Exception as e:
			raise RepositoryError(f"获取可执行任务失败: {str(e)}")

	async def update_task_status (
			self,
			workflow_id: str,
			task_id: str,
			status: str,
			result: Optional[Dict[str, Any]] = None,
			error_message: Optional[str] = None
	) -> Optional[WorkflowTask]:
		"""
		更新任务状态

		Args:
			workflow_id: 工作流ID
			task_id: 任务ID
			status: 新状态
			result: 任务结果（JSON格式）
			error_message: 错误信息

		Returns:
			更新后的任务对象
		"""
		try:
			update_data: Dict[str, Any] = {
				'status': status,
				'updated_at': datetime.now()
			}

			if status == 'running':
				update_data['started_at'] = datetime.now()
			elif status in ['completed', 'failed', 'cancelled']:
				update_data['completed_at'] = datetime.now()

			if result is not None:
				update_data['result'] = result

			if error_message is not None:
				update_data['error_message'] = error_message

			# 构建更新条件
			stmt = (
				update(self.model)
				.where(
					and_(
						self.model.workflow_id == workflow_id,
						self.model.task_id == task_id
					)
				)
				.values(**update_data)
			)

			await self.session.execute(stmt)

			# 返回更新后的任务
			return await self.get_by_workflow_and_task_id(workflow_id, task_id)
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"更新任务状态失败: {str(e)}")

	async def cancel_workflow_tasks (self, workflow_id: str) -> int:
		"""
		取消工作流的所有任务

		Args:
			workflow_id: 工作流ID

		Returns:
			取消的任务数
		"""
		try:
			# 只取消状态为 pending 或 running 的任务
			stmt = (
				update(self.model)
				.where(
					and_(
						self.model.workflow_id == workflow_id,
						self.model.status.in_(['pending', 'running'])
					)
				)
				.values(
					status='cancelled',
					completed_at=datetime.now(),
					updated_at=datetime.now()
				)
			)

			result = await self.session.execute(stmt)
			return result.rowcount or 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"取消工作流任务失败: {str(e)}")

	async def delete_workflow_tasks (self, workflow_id: str) -> int:
		"""
		删除工作流的所有任务

		Args:
			workflow_id: 工作流ID

		Returns:
			删除的任务数
		"""
		try:
			stmt = delete(self.model).where(self.model.workflow_id == workflow_id)
			result = await self.session.execute(stmt) # type: ignore
			return result.rowcount or 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"删除工作流任务失败: {str(e)}")

	async def get_workflow_progress (self, workflow_id: str) -> Dict[str, Any]:
		"""
		获取工作流进度统计

		Args:
			workflow_id: 工作流ID

		Returns:
			进度统计信息
		"""
		try:
			# 获取工作流所有任务
			tasks = await self.get_by_workflow_id(workflow_id)

			if not tasks:
				return {
					'total': 0,
					'completed': 0,
					'running': 0,
					'pending': 0,
					'failed': 0,
					'cancelled': 0,
					'progress': 0.0
				}

			# 统计各类状态的任务数
			total = len(tasks)
			status_counts = {
				'completed': 0,
				'running': 0,
				'pending': 0,
				'failed': 0,
				'cancelled': 0
			}

			for task in tasks:
				if task.status in status_counts:
					status_counts[task.status] += 1

			# 计算进度（已完成的比例）
			progress = status_counts['completed'] / total if total > 0 else 0.0

			return {
				'total': total,
				**status_counts,
				'progress': round(progress, 4)
			}
		except Exception as e:
			raise RepositoryError(f"获取工作流进度失败: {str(e)}")


class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "WORKFLOW_TASK_REPOSITORY_ERROR"):
		self.message = message
		self.code = code
		super().__init__(self.message)
