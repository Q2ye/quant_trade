# quant_server/shared/database/repositories/system/ops/scheduled_task_repo.py
"""
定时任务调度Repository

处理系统定时任务的数据访问，支持任务调度、执行记录管理等功能
"""

from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text, Integer
from sqlalchemy.dialects.postgresql import JSONB

from quant_server.shared.database.models import ScheduledTask
from quant_server.shared.database.repositories.base import BaseRepository, PaginationParams, PaginationResult
from quant_server.shared.database.repositories.types import (
	FilterCondition, SortCondition, QueryParams, TimeRange,
	FilterOperator, CacheConfig, CacheStrategy
)


class TaskType(str, Enum):
	"""任务类型枚举"""
	CRON = "cron"  # Cron表达式任务
	INTERVAL = "interval"  # 间隔任务
	DATE = "date"  # 指定时间任务
	MANUAL = "manual"  # 手动任务


class TaskStatus(str, Enum):
	"""任务状态枚举"""
	PENDING = "pending"  # 等待执行
	RUNNING = "running"  # 执行中
	SUCCESS = "success"  # 执行成功
	FAILED = "failed"  # 执行失败
	SKIPPED = "skipped"  # 跳过执行
	CANCELLED = "cancelled"  # 已取消


class TaskModule(str, Enum):
	"""任务模块枚举"""
	DATA = "data"  # 数据模块
	STRATEGY = "strategy"  # 策略模块
	TRADE = "trade"  # 交易模块
	BACKTEST = "backtest"  # 回测模块
	ACCOUNT = "account"  # 账户模块
	ANALYSIS = "analysis"  # 分析模块
	MONITOR = "monitor"  # 监控模块
	SYSTEM = "system"  # 系统模块
	MAINTENANCE = "maintenance"  # 系统维护


class ScheduledTaskRepository(BaseRepository[ScheduledTask]):
	"""定时任务调度Repository"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化定时任务Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, ScheduledTask)
		# 缓存配置：定时任务数据变化不频繁，适合缓存
		self.cache_config = CacheConfig(
			strategy=CacheStrategy.REDIS,
			ttl=300,  # 5分钟缓存
			prefix="scheduled_tasks:"
		)

	async def get_by_task_name (self, task_name: str) -> Optional[ScheduledTask]:
		"""
		根据任务名称获取任务

		Args:
			task_name: 任务名称

		Returns:
			任务对象或None
		"""
		try:
			query = select(ScheduledTask).where(
				and_(
					ScheduledTask.task_name == task_name,
					ScheduledTask.is_deleted == False
				)
			)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise self._create_repository_error(f"获取任务失败: {str(e)}")

	async def get_active_tasks (self) -> List[ScheduledTask]:
		"""
		获取所有激活的任务

		Returns:
			激活任务列表
		"""
		try:
			query = select(ScheduledTask).where(
				and_(
					ScheduledTask.is_active == True,
					ScheduledTask.is_deleted == False
				)
			).order_by(ScheduledTask.next_run_at.asc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise self._create_repository_error(f"获取激活任务失败: {str(e)}")

	async def get_tasks_by_module (self, module: TaskModule, active_only: bool = True) -> List[ScheduledTask]:
		"""
		根据模块获取任务

		Args:
			module: 模块名称
			active_only: 是否只获取激活任务

		Returns:
			任务列表
		"""
		try:
			query = select(ScheduledTask).where(
				ScheduledTask.task_module == module.value
			)

			if active_only:
				query = query.where(ScheduledTask.is_active == True)

			query = query.where(ScheduledTask.is_deleted == False)
			query = query.order_by(ScheduledTask.task_name)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise self._create_repository_error(f"获取模块任务失败: {str(e)}")

	async def get_tasks_due_for_execution (self, max_tasks: int = 10) -> List[ScheduledTask]:
		"""
		获取待执行的任务（下次执行时间已到）

		Args:
			max_tasks: 最大获取数量

		Returns:
			待执行任务列表
		"""
		try:
			now = datetime.now()
			query = select(ScheduledTask).where(
				and_(
					ScheduledTask.is_active == True,
					ScheduledTask.is_deleted == False,
					ScheduledTask.next_run_at <= now
				)
			).order_by(ScheduledTask.next_run_at.asc()).limit(max_tasks)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise self._create_repository_error(f"获取待执行任务失败: {str(e)}")

	async def update_task_status (
			self,
			task_id: str,
			status: TaskStatus,
			run_duration: Optional[int] = None,
			error_message: Optional[str] = None
	) -> bool:
		"""
		更新任务状态

		Args:
			task_id: 任务ID
			status: 任务状态
			run_duration: 运行时长（秒）
			error_message: 错误信息

		Returns:
			是否成功
		"""
		try:
			update_data = {
				"last_run_at": datetime.now(),
				"last_run_result": status.value,
				"updated_at": datetime.now()
			}

			if run_duration is not None:
				update_data["last_run_duration"] = run_duration

			# 更新统计信息
			if status == TaskStatus.SUCCESS:
				update_data["success_runs"] = ScheduledTask.success_runs + 1
			elif status in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
				update_data["failed_runs"] = ScheduledTask.failed_runs + 1

			update_data["total_runs"] = ScheduledTask.total_runs + 1

			# 如果是手动任务，重置激活状态
			if status == TaskStatus.SUCCESS and self.task_type == TaskType.MANUAL:
				update_data["is_active"] = False

			await self.update(task_id, update_data)
			return True

		except Exception as e:
			await self.session.rollback()
			raise self._create_repository_error(f"更新任务状态失败: {str(e)}")

	async def schedule_next_run (self, task_id: str, next_run_at: datetime) -> bool:
		"""
		安排下一次运行时间

		Args:
			task_id: 任务ID
			next_run_at: 下次运行时间

		Returns:
			是否成功
		"""
		try:
			update_data = {
				"next_run_at": next_run_at,
				"updated_at": datetime.now()
			}

			await self.update(task_id, update_data)
			return True

		except Exception as e:
			await self.session.rollback()
			raise self._create_repository_error(f"安排下次运行失败: {str(e)}")

	async def activate_task (self, task_id: str, next_run_at: Optional[datetime] = None) -> bool:
		"""
		激活任务

		Args:
			task_id: 任务ID
			next_run_at: 下次运行时间（可选）

		Returns:
			是否成功
		"""
		try:
			update_data = {
				"is_active": True,
				"updated_at": datetime.now()
			}

			if next_run_at:
				update_data["next_run_at"] = next_run_at

			await self.update(task_id, update_data)
			return True

		except Exception as e:
			await self.session.rollback()
			raise self._create_repository_error(f"激活任务失败: {str(e)}")

	async def deactivate_task (self, task_id: str) -> bool:
		"""
		停用任务

		Args:
			task_id: 任务ID

		Returns:
			是否成功
		"""
		try:
			update_data = {
				"is_active": False,
				"next_run_at": None,
				"updated_at": datetime.now()
			}

			await self.update(task_id, update_data)
			return True

		except Exception as e:
			await self.session.rollback()
			raise self._create_repository_error(f"停用任务失败: {str(e)}")

	async def get_task_statistics (self, time_range: Optional[TimeRange] = None) -> Dict[str, Any]:
		"""
		获取任务统计信息

		Args:
			time_range: 时间范围（可选）

		Returns:
			统计信息字典
		"""
		try:
			# 基础查询
			query = select(
				func.count().label("total_tasks"),
				func.sum(func.cast(ScheduledTask.is_active, Integer)).label("active_tasks"),
				func.sum(ScheduledTask.total_runs).label("total_runs"),
				func.sum(ScheduledTask.success_runs).label("total_success"),
				func.sum(ScheduledTask.failed_runs).label("total_failed"),
				func.avg(ScheduledTask.last_run_duration).label("avg_duration")
			).where(ScheduledTask.is_deleted == False)

			# 应用时间范围过滤
			if time_range:
				query = query.where(
					and_(
						ScheduledTask.last_run_at >= time_range.start,
						ScheduledTask.last_run_at <= time_range.end
					)
				)

			result = await self.session.execute(query)
			stats = result.first()

			# 按模块统计
			module_query = select(
				ScheduledTask.task_module,
				func.count().label("count"),
				func.sum(func.cast(ScheduledTask.is_active, Integer)).label("active_count")
			).where(ScheduledTask.is_deleted == False).group_by(ScheduledTask.task_module)

			module_result = await self.session.execute(module_query)
			module_stats = {row.task_module: {"total": row.count, "active": row.active_count}
			                for row in module_result}

			# 按任务类型统计
			type_query = select(
				ScheduledTask.task_type,
				func.count().label("count")
			).where(ScheduledTask.is_deleted == False).group_by(ScheduledTask.task_type)

			type_result = await self.session.execute(type_query)
			type_stats = {row.task_type: row.count for row in type_result}

			# 成功率计算
			total_runs = stats.total_runs or 0
			total_success = stats.total_success or 0
			success_rate = (total_success / total_runs * 100) if total_runs > 0 else 0

			return {
				"total_tasks": stats.total_tasks or 0,
				"active_tasks": stats.active_tasks or 0,
				"inactive_tasks": (stats.total_tasks or 0) - (stats.active_tasks or 0),
				"total_runs": total_runs,
				"total_success": total_success,
				"total_failed": stats.total_failed or 0,
				"success_rate": round(success_rate, 2),
				"avg_duration": round(stats.avg_duration or 0, 2),
				"by_module": module_stats,
				"by_type": type_stats,
				"time_range": time_range.to_dict() if time_range else None
			}

		except Exception as e:
			raise self._create_repository_error(f"获取任务统计失败: {str(e)}")

	async def get_failed_tasks (
			self,
			days: int = 7,
			limit: int = 50
	) -> List[ScheduledTask]:
		"""
		获取最近失败的任务

		Args:
			days: 最近天数
			limit: 限制数量

		Returns:
			失败任务列表
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days)

			query = select(ScheduledTask).where(
				and_(
					ScheduledTask.is_deleted == False,
					ScheduledTask.last_run_at >= cutoff_date,
					ScheduledTask.last_run_result == TaskStatus.FAILED.value
				)
			).order_by(ScheduledTask.last_run_at.desc()).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise self._create_repository_error(f"获取失败任务失败: {str(e)}")

	async def search_tasks (
			self,
			keyword: Optional[str] = None,
			module: Optional[TaskModule] = None,
			task_type: Optional[TaskType] = None,
			is_active: Optional[bool] = None,
			pagination: Optional[PaginationParams] = None
	) -> PaginationResult[ScheduledTask]:
		"""
		搜索任务

		Args:
			keyword: 关键词搜索（任务名称）
			module: 模块过滤
			task_type: 任务类型过滤
			is_active: 激活状态过滤
			pagination: 分页参数

		Returns:
			分页结果
		"""
		try:
			query = select(ScheduledTask).where(ScheduledTask.is_deleted == False)

			# 应用过滤条件
			if keyword:
				query = query.where(ScheduledTask.task_name.ilike(f"%{keyword}%"))

			if module:
				query = query.where(ScheduledTask.task_module == module.value)

			if task_type:
				query = query.where(ScheduledTask.task_type == task_type.value)

			if is_active is not None:
				query = query.where(ScheduledTask.is_active == is_active)

			# 计数查询
			count_query = select(func.count()).select_from(query.subquery())
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			if pagination:
				query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 排序
			query = query.order_by(
				ScheduledTask.is_active.desc(),
				ScheduledTask.next_run_at.asc(),
				ScheduledTask.task_name
			)

			result = await self.session.execute(query)
			items = result.scalars().all()

			if pagination:
				return PaginationResult.create(
					items=items,
					total=total,
					page=pagination.page,
					page_size=pagination.page_size
				)
			else:
				return PaginationResult.create(
					items=items,
					total=total,
					page=1,
					page_size=total
				)

		except Exception as e:
			raise self._create_repository_error(f"搜索任务失败: {str(e)}")

	async def bulk_update_schedule (
			self,
			task_ids: List[str],
			schedule_config: Dict[str, Any]
	) -> int:
		"""
		批量更新任务调度配置

		Args:
			task_ids: 任务ID列表
			schedule_config: 调度配置

		Returns:
			更新的任务数量
		"""
		try:
			query = update(ScheduledTask).where(
				and_(
					ScheduledTask.id.in_(task_ids),
					ScheduledTask.is_deleted == False
				)
			).values(
				schedule_config=schedule_config,
				updated_at=datetime.now()
			)

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise self._create_repository_error(f"批量更新调度配置失败: {str(e)}")

	async def cleanup_old_tasks (self, days_to_keep: int = 90) -> int:
		"""
		清理旧的软删除任务

		Args:
			days_to_keep: 保留天数

		Returns:
			清理的任务数量
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days_to_keep)

			query = delete(ScheduledTask).where(
				and_(
					ScheduledTask.is_deleted == True,
					ScheduledTask.updated_at < cutoff_date
				)
			)

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise self._create_repository_error(f"清理旧任务失败: {str(e)}")

	def _create_repository_error (self, message: str) -> Exception:
		"""创建Repository异常"""
		from quant_server.shared.database.repositories.base import RepositoryError
		return RepositoryError(f"[ScheduledTaskRepository] {message}")