# data_sync/services/status_manager.py
"""
同步状态管理器 - 负责管理全局同步状态
"""
from datetime import datetime
from typing import Dict, Any, Optional
import threading
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SyncStatus(str, Enum):
	"""同步状态枚举"""
	IDLE = "idle"  # 空闲
	INITIALIZING = "initializing"  # 初始化
	VALIDATING = "validating"  # 验证中
	RUNNING = "running"  # 运行中
	PROCESSING = "processing"  # 处理中
	COMPLETED = "completed"  # 完成
	ERROR = "error"  # 错误
	CANCELLED = "cancelled"  # 已取消


@dataclass
class SyncTask:
	"""同步任务信息"""
	task_id: str
	data_types: list
	priority: int
	start_time: datetime
	end_time: Optional[datetime] = None
	status: SyncStatus = SyncStatus.IDLE
	progress: int = 0
	current_task: Optional[str] = None
	results: Dict[str, Any] = field(default_factory=dict)
	error: Optional[str] = None
	total_tasks: int = 0
	completed_tasks: int = 0


class SyncStatusManager:
	"""同步状态管理器 - 线程安全"""

	def __init__ (self):
		self._lock = threading.RLock()
		self._current_task: Optional[SyncTask] = None
		self._task_history: Dict[str, SyncTask] = {}
		self._max_history_size = 100  # 保留最近100个任务

	@property
	def is_running (self) -> bool:
		"""是否有任务正在运行"""
		with self._lock:
			if self._current_task is None:
				return False
			return self._current_task.status in [SyncStatus.RUNNING, SyncStatus.PROCESSING]

	def create_task (self, task_id: str, data_types: list, priority: int = 2) -> SyncTask:
		"""创建新同步任务"""
		with self._lock:
			# 如果有任务正在运行，检查是否可以创建新任务
			if self.is_running and priority > 1:  # 非高优先级任务需等待
				raise RuntimeError("已有任务正在运行，请等待或取消当前任务")

			# 创建新任务
			task = SyncTask(
				task_id=task_id,
				data_types=data_types,
				priority=priority,
				start_time=datetime.now(),
				status=SyncStatus.INITIALIZING,
				total_tasks=len(data_types)
			)

			# 如果有运行中的任务且新任务优先级更高，则取消当前任务
			if self._current_task and priority < self._current_task.priority:
				logger.warning(f"高优先级任务{task_id}中断当前任务{self._current_task.task_id}")
				self._cancel_current_task()

			self._current_task = task
			self._task_history[task_id] = task

			# 清理历史记录
			if len(self._task_history) > self._max_history_size:
				old_tasks = sorted(self._task_history.items(),
				                   key=lambda x: x[1].start_time)[:len(self._task_history) - self._max_history_size]
				for old_task_id, _ in old_tasks:
					del self._task_history[old_task_id]

			return task

	def update_task_progress (self, task_id: str, **kwargs):
		"""更新任务进度"""
		with self._lock:
			task = self._get_task(task_id)
			if not task:
				return

			for key, value in kwargs.items():
				if hasattr(task, key):
					setattr(task, key, value)

			# 自动计算进度
			if task.total_tasks > 0:
				task.progress = int((task.completed_tasks / task.total_tasks) * 100)

			logger.debug(f"任务{task_id}进度更新: {task.progress}%")

	def complete_task (self, task_id: str, results: Dict[str, Any] = None):
		"""标记任务完成"""
		with self._lock:
			task = self._get_task(task_id)
			if not task:
				return

			task.status = SyncStatus.COMPLETED
			task.end_time = datetime.now()
			task.progress = 100
			task.completed_tasks = task.total_tasks

			if results:
				task.results = results

			logger.info(f"任务{task_id}完成，耗时: {task.end_time - task.start_time}")

	def fail_task (self, task_id: str, error: str):
		"""标记任务失败"""
		with self._lock:
			task = self._get_task(task_id)
			if not task:
				return

			task.status = SyncStatus.ERROR
			task.end_time = datetime.now()
			task.error = error

			logger.error(f"任务{task_id}失败: {error}")

	def cancel_task (self, task_id: str):
		"""取消任务"""
		with self._lock:
			task = self._get_task(task_id)
			if not task:
				return

			task.status = SyncStatus.CANCELLED
			task.end_time = datetime.now()

			logger.info(f"任务{task_id}已取消")

	def _cancel_current_task (self):
		"""取消当前运行的任务"""
		if self._current_task and self.is_running:
			self.cancel_task(self._current_task.task_id)

	def _get_task (self, task_id: str) -> Optional[SyncTask]:
		"""获取任务"""
		if self._current_task and self._current_task.task_id == task_id:
			return self._current_task
		return self._task_history.get(task_id)

	def get_current_status (self) -> Dict[str, Any]:
		"""获取当前状态"""
		with self._lock:
			if not self._current_task:
				return self._get_idle_status()

			elapsed_time = 0
			estimated_remaining = 0

			if self._current_task.start_time:
				elapsed_time = int((datetime.now() - self._current_task.start_time).total_seconds())

				if self._current_task.progress > 0 and self.is_running:
					estimated_remaining = int((elapsed_time / self._current_task.progress) *
					                          (100 - self._current_task.progress))

			return {
				"task_id": self._current_task.task_id,
				"is_running": self.is_running,
				"status": self._current_task.status.value,
				"progress": self._current_task.progress,
				"current_task": self._current_task.current_task,
				"results": self._current_task.results,
				"error": self._current_task.error,
				"total_tasks": self._current_task.total_tasks,
				"completed_tasks": self._current_task.completed_tasks,
				"elapsed_time": elapsed_time,
				"estimated_remaining": estimated_remaining,
				"start_time": self._current_task.start_time,
				"end_time": self._current_task.end_time
			}

	@staticmethod
	def _get_idle_status () -> Dict[str, Any]:
		"""获取空闲状态"""
		return {
			"is_running": False,
			"status": SyncStatus.IDLE.value,
			"progress": 0,
			"total_tasks": 0,
			"completed_tasks": 0,
			"elapsed_time": 0,
			"estimated_remaining": 0
		}