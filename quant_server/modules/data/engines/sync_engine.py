"""
数据同步引擎
负责管理数据从外部源同步到内部数据库的完整流程

业务范围：
1. 定时同步：根据调度规则自动同步数据
2. 手动同步：响应用户请求进行同步
3. 增量同步：只同步变更数据
4. 全量同步：同步所有数据

引擎职责：
1. 管理同步任务队列和状态
2. 协调多个数据源的同步过程
3. 处理同步失败和重试逻辑
4. 监控同步进度和性能
5. 发布同步相关事件

依赖服务：
- DataSyncService: 执行具体的同步逻辑
- Repository: 数据访问
- 外部数据源适配器

设计原则：
1. 状态驱动：每个同步任务都有明确的状态流转
2. 容错处理：支持失败重试和断点续传
3. 资源控制：限制并发同步任务数量
4. 进度跟踪：实时报告同步进度
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from dataclasses import dataclass, field

from quant_server.core.engines.base import EngineBase, EngineStatus
from quant_server.core.events import EventPriority
from quant_server.modules.data.events import (
	DataSyncStartedEvent,
	DataSyncProgressEvent,
	DataSyncCompletedEvent,
	DataSyncFailedEvent,
	DataEventType,
	DataSyncType,
)
from quant_server.modules.data.services.sync_service import DataSyncService

logger = logging.getLogger(__name__)


class SyncTaskStatus(str, Enum):
	"""同步任务状态枚举"""
	PENDING = "pending"  # 等待执行
	PREPARING = "preparing"  # 准备中
	DOWNLOADING = "downloading"  # 下载数据
	PROCESSING = "processing"  # 处理数据
	SAVING = "saving"  # 保存数据
	COMPLETED = "completed"  # 已完成
	FAILED = "failed"  # 已失败
	CANCELLED = "cancelled"  # 已取消
	RETRYING = "retrying"  # 重试中


@dataclass
class SyncTaskConfig:
	"""同步任务配置"""
	sync_type: DataSyncType = DataSyncType.FULL
	data_sources: List[str] = field(default_factory=list)  # 数据源列表
	symbols: Optional[List[str]] = None  # 指定标的
	date_range: Optional[Dict[str, str]] = None  # 日期范围
	batch_size: int = 1000  # 批量大小
	max_retries: int = 3  # 最大重试次数
	priority: int = EventPriority.NORMAL  # 任务优先级
	callback_url: Optional[str] = None  # 回调URL


@dataclass
class SyncTaskProgress:
	"""同步任务进度"""
	total_items: int = 0
	processed_items: int = 0
	failed_items: int = 0
	current_item: str = ""
	current_step: str = ""
	progress_percentage: float = 0.0
	start_time: Optional[datetime] = None
	estimated_remaining: Optional[float] = None  # 秒


@dataclass
class SyncTaskResult:
	"""同步任务结果"""
	success: bool = False
	total_records: int = 0
	inserted_records: int = 0
	updated_records: int = 0
	failed_records: int = 0
	error_message: Optional[str] = None
	duration_seconds: float = 0.0
	summary: Dict[str, Any] = field(default_factory=dict)


class DataSyncEngine(EngineBase):
	"""
	数据同步引擎
	管理数据同步任务的执行和状态

	状态流转：
	PENDING → PREPARING → DOWNLOADING → PROCESSING → SAVING → COMPLETED
							↓              ↓             ↓
						  RETRYING      RETRYING     RETRYING
							↓              ↓             ↓
						   FAILED        FAILED        FAILED

	使用示例：
		engine = DataSyncEngine(event_engine, main_engine)
		await engine.start()

		# 启动同步任务
		task_id = await engine.start_sync_task(
			sync_type=DataSyncType.DAILY,
			data_sources=["tushare", "baostock"]
		)

		# 查询任务状态
		status = await engine.get_task_status(task_id)

		# 停止任务
		await engine.cancel_task(task_id)
	"""

	def __init__ (
			self,
			event_engine,
			main_engine,
			sync_service: Optional[DataSyncService] = None,
			max_concurrent_tasks: int = 3,
			task_timeout_seconds: int = 3600,
			name: str = "DataSyncEngine",
			**kwargs
	):
		"""
		初始化数据同步引擎

		Args:
			event_engine: 事件引擎实例
			main_engine: 主引擎实例
			sync_service: 数据同步服务实例
			max_concurrent_tasks: 最大并发任务数
			task_timeout_seconds: 任务超时时间（秒）
			name: 引擎名称
			**kwargs: 其他引擎参数
		"""
		super().__init__(
			event_engine=event_engine,
			main_engine=main_engine,
			name=name,
			**kwargs
		)

		# 服务依赖
		self.sync_service = sync_service

		# 配置参数
		self.max_concurrent_tasks = max_concurrent_tasks
		self.task_timeout_seconds = task_timeout_seconds

		# 任务管理
		self.tasks: Dict[str, Dict[str, Any]] = {}  # task_id -> 任务信息
		self.task_queue: asyncio.Queue = asyncio.Queue()
		self.active_tasks: Set[str] = set()  # 活跃任务ID集合
		self.task_counter = 0

		# 统计信息
		self.stats = {
			"total_tasks": 0,
			"completed_tasks": 0,
			"failed_tasks": 0,
			"cancelled_tasks": 0,
			"total_records": 0,
			"total_duration": 0.0,
			"last_sync_time": None,
		}

		logger.info(f"初始化数据同步引擎: {name}")

	async def on_start (self):
		"""引擎启动时调用"""
		await super().on_start()

		# 注册事件处理器
		await self._register_event_handlers()

		# 启动任务处理循环
		self._task_processor_task = asyncio.create_task(
			self._process_task_queue()
		)

		logger.info(f"数据同步引擎 {self.name} 已启动")

	async def on_stop (self):
		"""引擎停止时调用"""
		# 停止任务处理循环
		if hasattr(self, '_task_processor_task'):
			self._task_processor_task.cancel()
			try:
				await self._task_processor_task
			except asyncio.CancelledError:
				pass

		# 取消所有运行中的任务
		for task_id in list(self.active_tasks):
			await self.cancel_task(task_id)

		await super().on_stop()
		logger.info(f"数据同步引擎 {self.name} 已停止")

	async def _register_event_handlers (self):
		"""注册事件处理器"""
		# 注册外部触发的事件
		self.event_engine.register(
			DataEventType.SYNC_STARTED,
			self._on_external_sync_started
		)

		# 注册系统事件
		self.event_engine.register(
			"system.heartbeat",
			self._on_heartbeat
		)

	async def _on_external_sync_started (self, event):
		"""处理外部触发的同步开始事件"""
		try:
			data = event.data
			task_id = data.get("task_id")
			sync_type = data.get("sync_type", "daily")

			if task_id and task_id not in self.tasks:
				# 创建新任务
				await self.start_sync_task(
					sync_type=sync_type,
					custom_task_id=task_id,
					config=data.get("config", {})
				)
		except Exception as e:
			logger.error(f"处理外部同步事件失败: {e}", exc_info=True)

	async def _on_heartbeat (self, event):
		"""处理心跳事件，执行监控和清理"""
		try:
			# 检查超时任务
			await self._check_timeout_tasks()

			# 清理已完成的任务
			await self._cleanup_completed_tasks()
		except Exception as e:
			logger.error(f"处理心跳事件失败: {e}", exc_info=True)

	async def _process_task_queue (self):
		"""处理任务队列的主循环"""
		logger.info("数据同步任务处理循环已启动")

		while self.status == EngineStatus.RUNNING:
			try:
				# 从队列获取任务
				task_info = await asyncio.wait_for(
					self.task_queue.get(),
					timeout=1.0
				)

				task_id = task_info.get("task_id")
				if not task_id:
					logger.warning("从队列获取到无效任务")
					continue

				# 检查并发限制
				if len(self.active_tasks) >= self.max_concurrent_tasks:
					logger.warning(f"达到并发任务限制 ({self.max_concurrent_tasks})，任务 {task_id} 等待中")
					# 放回队列等待
					await self.task_queue.put(task_info)
					await asyncio.sleep(5)
					continue

				# 执行任务
				self.active_tasks.add(task_id)
				asyncio.create_task(
					self._execute_sync_task(task_info)
				)

			except asyncio.TimeoutError:
				# 队列为空，继续循环
				continue
			except asyncio.CancelledError:
				logger.info("任务处理循环被取消")
				break
			except Exception as e:
				logger.error(f"任务处理循环异常: {e}", exc_info=True)
				await asyncio.sleep(1)

		logger.info("数据同步任务处理循环已停止")

	async def start_sync_task (
			self,
			sync_type: Union[str, DataSyncType],
			data_sources: Optional[List[str]] = None,
			symbols: Optional[List[str]] = None,
			date_range: Optional[Dict[str, str]] = None,
			config: Optional[Dict[str, Any]] = None,
			custom_task_id: Optional[str] = None
	) -> str:
		"""
		启动数据同步任务

		Args:
			sync_type: 同步类型（daily/hourly/minute等）
			data_sources: 数据源列表
			symbols: 指定标的列表
			date_range: 日期范围 {start: "2023-01-01", end: "2023-12-31"}
			config: 额外配置
			custom_task_id: 自定义任务ID

		Returns:
			任务ID

		Raises:
			ValueError: 参数无效
			RuntimeError: 引擎未运行
		"""
		if self.status != EngineStatus.RUNNING:
			raise RuntimeError(f"引擎 {self.name} 未运行")

		# 参数验证
		if isinstance(sync_type, str):
			sync_type = DataSyncType(sync_type.lower())

		# 生成任务ID
		task_id = custom_task_id or self._generate_task_id(sync_type)

		# 创建任务配置
		task_config = SyncTaskConfig(
			sync_type=sync_type,
			data_sources=data_sources or ["tushare"],
			symbols=symbols,
			date_range=date_range,
			**(config or {})
		)

		# 创建任务记录
		self.tasks[task_id] = {
			"task_id": task_id,
			"config": task_config,
			"status": SyncTaskStatus.PENDING,
			"progress": SyncTaskProgress(),
			"result": None,
			"created_at": datetime.now(),
			"updated_at": datetime.now(),
			"error_count": 0,
			"retry_count": 0,
		}

		# 添加到队列
		await self.task_queue.put(self.tasks[task_id])

		# 更新统计
		self.stats["total_tasks"] += 1

		# 发布任务开始事件
		await self.event_engine.put(
			DataSyncStartedEvent(
				sync_type=sync_type.value,
				source=self.name,
				data={
					"task_id": task_id,
					"config": self._config_to_dict(task_config),
					"queue_position": self.task_queue.qsize(),
				}
			)
		)

		logger.info(f"创建同步任务: {task_id} ({sync_type.value})")
		return task_id

	async def _execute_sync_task (self, task_info: Dict[str, Any]):
		"""执行同步任务"""
		task_id = task_info["task_id"]
		config = task_info["config"]

		try:
			# 更新任务状态
			await self._update_task_status(task_id, SyncTaskStatus.PREPARING)

			# 执行同步
			result = await self._perform_sync(task_id, config)

			# 更新任务结果
			task_info["result"] = result
			task_info["status"] = SyncTaskStatus.COMPLETED if result.success else SyncTaskStatus.FAILED
			task_info["updated_at"] = datetime.now()

			# 发布完成事件
			if result.success:
				await self._publish_sync_completed(task_id, config, result)
				self.stats["completed_tasks"] += 1
			else:
				await self._publish_sync_failed(task_id, config, result)
				self.stats["failed_tasks"] += 1

			# 更新统计
			self.stats["total_records"] += result.total_records
			self.stats["total_duration"] += result.duration_seconds
			self.stats["last_sync_time"] = datetime.now()

		except asyncio.CancelledError:
			# 任务被取消
			logger.info(f"同步任务被取消: {task_id}")
			await self._update_task_status(task_id, SyncTaskStatus.CANCELLED)
		except Exception as e:
			# 任务执行失败
			logger.error(f"同步任务执行失败: {task_id}, 错误: {e}", exc_info=True)

			# 检查是否需要重试
			should_retry = await self._should_retry_task(task_id)
			if should_retry:
				await self._retry_task(task_id)
			else:
				await self._mark_task_failed(task_id, str(e))

		finally:
			# 清理活跃任务集合
			self.active_tasks.discard(task_id)
			self.task_queue.task_done()

	async def _perform_sync (
			self,
			task_id: str,
			config: SyncTaskConfig
	) -> SyncTaskResult:
		"""执行具体的同步逻辑"""
		start_time = datetime.now()
		result = SyncTaskResult()

		try:
			if not self.sync_service:
				raise RuntimeError("同步服务未配置")

			# 执行同步
			sync_result = await self.sync_service.sync_data(
				sync_type=config.sync_type.value,
				data_sources=config.data_sources,
				symbols=config.symbols,
				date_range=config.date_range,
				batch_size=config.batch_size
			)

			# 构建结果
			result.success = True
			result.total_records = sync_result.get("total_records", 0)
			result.inserted_records = sync_result.get("inserted_records", 0)
			result.updated_records = sync_result.get("updated_records", 0)
			result.failed_records = sync_result.get("failed_records", 0)
			result.summary = sync_result.get("summary", {})

		except Exception as e:
			logger.error(f"同步执行失败: {e}", exc_info=True)
			result.success = False
			result.error_message = str(e)

		finally:
			# 计算持续时间
			result.duration_seconds = (datetime.now() - start_time).total_seconds()

		return result

	async def _update_task_status (
			self,
			task_id: str,
			status: SyncTaskStatus,
			progress: Optional[SyncTaskProgress] = None
	):
		"""更新任务状态"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		task_info["status"] = status
		task_info["updated_at"] = datetime.now()

		if progress:
			task_info["progress"] = progress

		# 发布进度事件
		if status in [SyncTaskStatus.DOWNLOADING, SyncTaskStatus.PROCESSING, SyncTaskStatus.SAVING]:
			await self._publish_sync_progress(task_id, progress)

	async def _publish_sync_progress (
			self,
			task_id: str,
			progress: Optional[SyncTaskProgress] = None
	):
		"""发布同步进度事件"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		config = task_info["config"]

		progress_data = progress or task_info.get("progress", SyncTaskProgress())

		await self.event_engine.put(
			DataSyncProgressEvent(
				sync_type=config.sync_type.value,
				progress=progress_data.progress_percentage,
				current_item=progress_data.current_item,
				total_items=progress_data.total_items,
				processed_items=progress_data.processed_items,
				source=self.name,
				data={
					"task_id": task_id,
					"current_step": progress_data.current_step,
					"estimated_remaining": progress_data.estimated_remaining,
				}
			)
		)

	async def _publish_sync_completed (
			self,
			task_id: str,
			config: SyncTaskConfig,
			result: SyncTaskResult
	):
		"""发布同步完成事件"""
		await self.event_engine.put(
			DataSyncCompletedEvent(
				sync_type=config.sync_type.value,
				record_count=result.total_records,
				duration_seconds=result.duration_seconds,
				success=True,
				summary={
					"inserted": result.inserted_records,
					"updated": result.updated_records,
					"failed": result.failed_records,
					**result.summary
				},
				source=self.name,
				data={
					"task_id": task_id,
					"config": self._config_to_dict(config),
				}
			)
		)

	async def _publish_sync_failed (
			self,
			task_id: str,
			config: SyncTaskConfig,
			result: SyncTaskResult
	):
		"""发布同步失败事件"""
		await self.event_engine.put(
			DataSyncFailedEvent(
				sync_type=config.sync_type.value,
				error_message=result.error_message or "未知错误",
				error_details=None,
				retry_count=0,  # 可以从任务信息中获取
				source=self.name,
				data={
					"task_id": task_id,
					"config": self._config_to_dict(config),
				}
			)
		)

	async def cancel_task (self, task_id: str) -> bool:
		"""取消同步任务"""
		if task_id not in self.tasks:
			return False

		task_info = self.tasks[task_id]
		task_info["status"] = SyncTaskStatus.CANCELLED
		task_info["updated_at"] = datetime.now()

		# 如果任务在活跃集合中，标记为取消
		if task_id in self.active_tasks:
			# TODO: 实际取消正在运行的任务
			self.active_tasks.discard(task_id)

		self.stats["cancelled_tasks"] += 1

		logger.info(f"取消同步任务: {task_id}")
		return True

	async def get_task_status (self, task_id: str) -> Optional[Dict[str, Any]]:
		"""获取任务状态"""
		if task_id not in self.tasks:
			return None

		task_info = self.tasks[task_id].copy()

		# 计算已运行时间
		created_at = task_info["created_at"]
		if isinstance(created_at, str):
			created_at = datetime.fromisoformat(created_at)

		duration = (datetime.now() - created_at).total_seconds()

		# 构建状态响应
		status = {
			"task_id": task_id,
			"status": task_info["status"],
			"progress": task_info.get("progress", {}),
			"config": self._config_to_dict(task_info["config"]),
			"created_at": created_at.isoformat(),
			"updated_at": task_info["updated_at"].isoformat() if isinstance(task_info["updated_at"], datetime) else
			task_info["updated_at"],
			"duration_seconds": duration,
			"is_active": task_id in self.active_tasks,
			"result": task_info.get("result"),
		}

		return status

	async def get_engine_status (self) -> Dict[str, Any]:
		"""获取引擎状态"""
		base_status = await super().get_engine_status()

		engine_status = {
			**base_status,
			"tasks": {
				"total": len(self.tasks),
				"active": len(self.active_tasks),
				"pending": self.task_queue.qsize(),
				"completed": self.stats["completed_tasks"],
				"failed": self.stats["failed_tasks"],
				"cancelled": self.stats["cancelled_tasks"],
			},
			"stats": self.stats.copy(),
			"config": {
				"max_concurrent_tasks": self.max_concurrent_tasks,
				"task_timeout_seconds": self.task_timeout_seconds,
			},
		}

		return engine_status

	async def _should_retry_task (self, task_id: str) -> bool:
		"""判断任务是否需要重试"""
		if task_id not in self.tasks:
			return False

		task_info = self.tasks[task_id]
		config = task_info["config"]

		# 检查重试次数
		if task_info["retry_count"] >= config.max_retries:
			return False

		# 检查任务是否可重试
		if task_info["status"] in [SyncTaskStatus.CANCELLED, SyncTaskStatus.COMPLETED]:
			return False

		return True

	async def _retry_task (self, task_id: str):
		"""重试任务"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		task_info["retry_count"] += 1
		task_info["status"] = SyncTaskStatus.RETRYING
		task_info["updated_at"] = datetime.now()

		# 重新加入队列
		await self.task_queue.put(task_info)

		logger.info(f"重试任务: {task_id} (第{task_info['retry_count']}次)")

	async def _mark_task_failed (self, task_id: str, error_message: str):
		"""标记任务失败"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		config = task_info["config"]

		task_info["status"] = SyncTaskStatus.FAILED
		task_info["updated_at"] = datetime.now()

		# 发布失败事件
		await self.event_engine.put(
			DataSyncFailedEvent(
				sync_type=config.sync_type.value,
				error_message=error_message,
				error_details=None,
				retry_count=task_info["retry_count"],
				source=self.name,
				data={
					"task_id": task_id,
					"config": self._config_to_dict(config),
				}
			)
		)

		self.stats["failed_tasks"] += 1
		logger.error(f"标记任务失败: {task_id}, 错误: {error_message}")

	async def _check_timeout_tasks (self):
		"""检查超时任务"""
		current_time = datetime.now()

		for task_id in list(self.active_tasks):
			task_info = self.tasks.get(task_id)
			if not task_info:
				continue

			# 计算任务运行时间
			start_time = task_info.get("start_time", task_info["created_at"])
			if isinstance(start_time, str):
				start_time = datetime.fromisoformat(start_time)

			duration = (current_time - start_time).total_seconds()

			# 检查是否超时
			if duration > self.task_timeout_seconds:
				logger.warning(f"任务超时: {task_id} (运行了{duration:.0f}秒)")

				# 标记为失败
				await self._mark_task_failed(
					task_id,
					f"任务超时 (运行了{duration:.0f}秒，超过{self.task_timeout_seconds}秒限制)"
				)

				# 从活跃任务中移除
				self.active_tasks.discard(task_id)

	async def _cleanup_completed_tasks (self):
		"""清理已完成的任务"""
		tasks_to_remove = []
		cleanup_threshold = timedelta(hours=24)  # 24小时后清理

		for task_id, task_info in self.tasks.items():
			if task_id in self.active_tasks:
				continue

			status = task_info["status"]
			updated_at = task_info["updated_at"]
			if isinstance(updated_at, str):
				updated_at = datetime.fromisoformat(updated_at)

			# 清理已完成或失败超过24小时的任务
			if status in [SyncTaskStatus.COMPLETED, SyncTaskStatus.FAILED, SyncTaskStatus.CANCELLED]:
				if datetime.now() - updated_at > cleanup_threshold:
					tasks_to_remove.append(task_id)

		# 移除任务
		for task_id in tasks_to_remove:
			self.tasks.pop(task_id, None)

		if tasks_to_remove:
			logger.debug(f"清理了 {len(tasks_to_remove)} 个旧任务")

	def _generate_task_id (self, sync_type: DataSyncType) -> str:
		"""生成任务ID"""
		self.task_counter += 1
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		return f"sync_{sync_type.value}_{timestamp}_{self.task_counter:06d}"

	def _config_to_dict (self, config: SyncTaskConfig) -> Dict[str, Any]:
		"""将配置转换为字典"""
		return {
			"sync_type": config.sync_type.value,
			"data_sources": config.data_sources,
			"symbols": config.symbols,
			"date_range": config.date_range,
			"batch_size": config.batch_size,
			"max_retries": config.max_retries,
			"priority": config.priority,
		}


# 导出引擎类
__all__ = ["DataSyncEngine"]