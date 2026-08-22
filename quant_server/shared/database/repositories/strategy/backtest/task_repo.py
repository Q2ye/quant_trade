# shared/database/repositories/strategy/backtest/task_repo.py
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, desc
from sqlalchemy.sql import func

from shared.database.models.business_models import BacktestTask
from shared.database.repositories.base import BaseRepository


class BacktestTaskRepository(BaseRepository[BacktestTask]):
	"""回测任务数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestTask)

	async def get_by_task_id (self, task_id: str) -> Optional[BacktestTask]:
		"""根据任务ID获取回测任务"""
		query = select(self.model).where(self.model.id == task_id)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_user_tasks (self, user_id: str, skip: int = 0, limit: int = 50,
	                          status: Optional[str] = None) -> List[BacktestTask]:
		"""获取用户的所有回测任务"""
		query = select(self.model).where(self.model.user_id == user_id)

		if status:
			query = query.where(self.model.status == status)

		query = query.order_by(desc(self.model.created_at)).offset(skip).limit(limit)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_strategy_tasks (self, strategy_id: str, skip: int = 0, limit: int = 50) -> List[BacktestTask]:
		"""获取策略的所有回测任务"""
		query = select(self.model).where(self.model.strategy_id == strategy_id)
		query = query.order_by(desc(self.model.created_at)).offset(skip).limit(limit)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def update_status (self, task_id: str, status: str, progress: Optional[float] = None,
	                         error_message: Optional[str] = None) -> bool:
		"""更新回测任务状态"""
		update_data: Dict[str, Any] = {
			"status": status,
			"updated_at": datetime.now()
		}

		if progress is not None:
			update_data["progress"] = progress

		if error_message is not None:
			update_data["error_message"] = error_message

		if status == "running" and "started_at" not in update_data:
			update_data["started_at"] = datetime.now()
		elif status == "completed" and "completed_at" not in update_data:
			update_data["completed_at"] = datetime.now()

		stmt = (
			update(self.model)
			.where(self.model.id == task_id)
			.values(**update_data)
		)

		result = await self.session.execute(stmt)
		return result.rowcount > 0

	async def update_result (self, task_id: str, result: Dict[str, Any]) -> bool:
		"""更新回测结果"""
		stmt = (
			update(self.model)
			.where(self.model.id == task_id)
			.values(
				result=result,
				updated_at=datetime.now()
			)
		)

		result = await self.session.execute(stmt)
		return result.rowcount > 0

	async def get_pending_tasks (self, limit: int = 10) -> List[BacktestTask]:
		"""获取待处理的回测任务"""
		query = (
			select(self.model)
			.where(self.model.status == "pending")
			.order_by(self.model.created_at)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_running_tasks (self) -> List[BacktestTask]:
		"""获取正在运行的回测任务"""
		query = (
			select(self.model)
			.where(self.model.status == "running")
			.order_by(self.model.started_at)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def count_by_user (self, user_id: str) -> Dict[str, int]:
		"""统计用户回测任务数量"""
		# 按状态统计
		query = (
			select(self.model.status, func.count().label('count'))
			.where(self.model.user_id == user_id)
			.group_by(self.model.status)
		)

		result = await self.session.execute(query)
		status_counts = {row.status: row.count for row in result.all()}

		# 总数量
		total_query = select(func.count()).where(self.model.user_id == user_id)
		total_result = await self.session.execute(total_query)
		total = total_result.scalar() or 0

		return {
			"total": total,
			**status_counts
		}

	async def delete_old_tasks (self, days: int = 30) -> int:
		"""删除指定天数前的完成/失败任务"""
		cutoff_date = datetime.now().replace(tzinfo=None) - timedelta(days=days)

		stmt = (
			delete(self.model)
			.where(
				and_(
					self.model.status.in_(["completed", "failed", "cancelled"]),
					self.model.created_at < cutoff_date
				)
			)
		)

		result = await self.session.execute(stmt) # type: ignore
		return result.rowcount or 0

	async def get_list (self, filters: Dict[str, Any], page: int = 1, page_size: int = 20) -> Tuple[List[BacktestTask], int]:
		"""获取任务列表（带分页）"""
		# 构建查询
		query = select(self.model)

		# 应用过滤条件
		for key, value in filters.items():
			if hasattr(self.model, key):
				query = query.where(getattr(self.model, key) == value)

		# 计算总数
		total_query = select(func.count()).select_from(query.subquery())
		total_result = await self.session.execute(total_query)
		total = total_result.scalar() or 0

		# 应用排序（最新在前，2026-08-19 修复：此前无 order_by 导致顺序不确定）
		query = query.order_by(self.model.created_at.desc())

		# 应用分页
		offset = (page - 1) * page_size
		query = query.offset(offset).limit(page_size)

		# 执行查询
		result = await self.session.execute(query)
		tasks = result.scalars().all()

		return tasks, total