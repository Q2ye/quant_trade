# quant_server/shared/database/repositories/operation/workflow/workflow_log_repo.py
"""
WorkflowLogRepository - 工作流执行日志数据访问仓库

基于 BaseRepository 实现，提供对 workflow_logs 表的 CRUD 操作
位置：quant_server/shared/database/repositories/operation/workflow/workflow_log_repo.py

表说明：workflow_logs 表存储工作流执行历史记录，支持执行跟踪和审计

设计原则：
1. 纯数据访问：只做 CRUD，不做业务逻辑
2. 异步支持：完全异步化设计
3. 类型安全：使用泛型确保类型一致性
4. 查询优化：提供时间范围查询和统计方法
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, desc, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import WorkflowLog
from shared.database.repositories.base import BaseRepository


class WorkflowLogRepository(BaseRepository[WorkflowLog]):
	"""
	工作流日志仓库类

	继承自 BaseRepository，提供对 WorkflowLog 模型的专用数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化 WorkflowLogRepository

		Args:
			session: 数据库会话，提供数据访问上下文
		"""
		super().__init__(session, WorkflowLog)

	# ==================== 专用查询方法 ====================

	async def get_by_workflow_id (self, workflow_id: str) -> List[WorkflowLog]:
		"""
		根据工作流ID获取执行日志

		Args:
			workflow_id: 工作流ID

		Returns:
			工作流执行日志列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.workflow_id == workflow_id)
				.order_by(desc(self.model.started_at))
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取工作流日志失败: {str(e)}")

	async def get_by_execution_id (self, execution_id: str) -> Optional[WorkflowLog]:
		"""
		根据执行ID获取日志

		Args:
			execution_id: 执行ID

		Returns:
			工作流执行日志对象或None
		"""
		try:
			query = select(self.model).where(self.model.execution_id == execution_id)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取执行日志失败: {str(e)}")

	async def get_latest_execution (self, workflow_id: str) -> Optional[WorkflowLog]:
		"""
		获取工作流的最新执行记录

		Args:
			workflow_id: 工作流ID

		Returns:
			最新执行记录或None
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.workflow_id == workflow_id)
				.order_by(desc(self.model.started_at))
				.limit(1)
			)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取最新执行记录失败: {str(e)}")

	async def get_by_status (self, status: str, limit: int = 100) -> List[WorkflowLog]:
		"""
		根据状态获取执行日志

		Args:
			status: 执行状态
			limit: 返回记录数限制

		Returns:
			执行日志列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.status == status)
				.order_by(desc(self.model.started_at))
				.limit(limit)
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取状态日志失败: {str(e)}")

	async def get_by_time_range (
			self,
			start_time: datetime,
			end_time: datetime,
			workflow_id: Optional[str] = None
	) -> List[WorkflowLog]:
		"""
		根据时间范围获取执行日志

		Args:
			start_time: 开始时间
			end_time: 结束时间
			workflow_id: 可选的工作流ID

		Returns:
			时间范围内的执行日志列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.started_at >= start_time,
					self.model.started_at <= end_time
				)
			)

			if workflow_id:
				query = query.where(self.model.workflow_id == workflow_id)

			query = query.order_by(desc(self.model.started_at))
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取时间范围日志失败: {str(e)}")

	async def get_recent_executions (
			self,
			days: int = 7,
			workflow_id: Optional[str] = None
	) -> List[WorkflowLog]:
		"""
		获取最近N天的执行记录

		Args:
			days: 最近天数
			workflow_id: 可选的工作流ID

		Returns:
			最近执行记录列表
		"""
		try:
			end_time = datetime.now()
			start_time = end_time - timedelta(days=days)

			return await self.get_by_time_range(start_time, end_time, workflow_id)
		except Exception as e:
			raise RepositoryError(f"获取最近执行记录失败: {str(e)}")

	async def get_failed_executions (
			self,
			workflow_id: Optional[str] = None,
			limit: int = 100
	) -> List[WorkflowLog]:
		"""
		获取失败的执行记录

		Args:
			workflow_id: 可选的工作流ID
			limit: 返回记录数限制

		Returns:
			失败执行记录列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.status == 'failed')
				.order_by(desc(self.model.started_at))
				.limit(limit)
			)

			if workflow_id:
				query = query.where(self.model.workflow_id == workflow_id)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取失败执行记录失败: {str(e)}")

	async def get_successful_executions (
			self,
			workflow_id: Optional[str] = None,
			limit: int = 100
	) -> List[WorkflowLog]:
		"""
		获取成功的执行记录

		Args:
			workflow_id: 可选的工作流ID
			limit: 返回记录数限制

		Returns:
			成功执行记录列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.status == 'completed')
				.order_by(desc(self.model.started_at))
				.limit(limit)
			)

			if workflow_id:
				query = query.where(self.model.workflow_id == workflow_id)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取成功执行记录失败: {str(e)}")

	async def get_execution_stats (self, workflow_id: str) -> Dict[str, Any]:
		"""
		获取工作流执行统计信息

		Args:
			workflow_id: 工作流ID

		Returns:
			执行统计信息
		"""
		try:
			# 获取所有执行记录
			logs = await self.get_by_workflow_id(workflow_id)

			if not logs:
				return {
					'total_executions': 0,
					'successful': 0,
					'failed': 0,
					'average_duration_ms': 0,
					'last_execution': None,
					'success_rate': 0.0
				}

			# 统计信息
			total = len(logs)
			successful = sum(1 for log in logs if log.status == 'completed')
			failed = sum(1 for log in logs if log.status == 'failed')

			# 计算平均耗时（只计算已完成且有耗时的记录）
			completed_logs = [log for log in logs if log.status == 'completed' and log.duration_ms]
			avg_duration = (
				sum(log.duration_ms for log in completed_logs) / len(completed_logs)
				if completed_logs else 0
			)

			# 最近一次执行
			last_execution = max(logs, key=lambda x: x.started_at)

			# 成功率
			success_rate = successful / total if total > 0 else 0.0

			return {
				'total_executions': total,
				'successful': successful,
				'failed': failed,
				'average_duration_ms': round(avg_duration, 2),
				'last_execution': {
					'execution_id': last_execution.execution_id,
					'status': last_execution.status,
					'started_at': last_execution.started_at,
					'duration_ms': last_execution.duration_ms
				},
				'success_rate': round(success_rate, 4)
			}
		except Exception as e:
			raise RepositoryError(f"获取执行统计失败: {str(e)}")

	async def get_daily_stats (
			self,
			start_date: datetime,
			end_date: datetime
	) -> List[Dict[str, Any]]:
		"""
		获取每日执行统计

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			每日统计列表
		"""
		try:
			# 按日期分组统计
			query = (
				select([
					func.date(self.model.started_at).label('execution_date'),
					func.count().label('total'),
					func.sum(func.case([(self.model.status == 'completed', 1)], else_=0)).label('successful'),
					func.sum(func.case([(self.model.status == 'failed', 1)], else_=0)).label('failed'),
					func.avg(self.model.duration_ms).label('avg_duration')
				])
				.where(
					and_(
						self.model.started_at >= start_date,
						self.model.started_at <= end_date
					)
				)
				.group_by(func.date(self.model.started_at))
				.order_by(desc(func.date(self.model.started_at)))
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			stats = []
			for row in rows:
				stats.append({
					'date': row.execution_date,
					'total': row.total or 0,
					'successful': row.successful or 0,
					'failed': row.failed or 0,
					'avg_duration_ms': round(row.avg_duration or 0, 2),
					'success_rate': round((row.successful or 0) / (row.total or 1), 4)
				})

			return stats
		except Exception as e:
			raise RepositoryError(f"获取每日统计失败: {str(e)}")

	async def cleanup_old_logs (self, days_to_keep: int = 90) -> int:
		"""
		清理旧的执行日志

		Args:
			days_to_keep: 保留天数

		Returns:
			删除的记录数
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days_to_keep)

			stmt = delete(self.model).where(self.model.started_at < cutoff_date)
			result = await self.session.execute(stmt)  # type: ignore

			return result.rowcount or 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧日志失败: {str(e)}")


class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "WORKFLOW_LOG_REPOSITORY_ERROR"):
		self.message = message
		self.code = code
		super().__init__(self.message)
