# -*- coding: utf-8 -*-
"""
数据同步引擎重构版
基于核心引擎框架，实现统一的生命周期管理、事件驱动通信和配置驱动

设计原则：
1. 继承EngineBase基类，遵循统一的生命周期管理
2. 使用EngineFactory进行创建和管理
3. 通过EventEngine实现事件驱动通信
4. 支持依赖注入和配置驱动
5. 提供完整的监控和健康检查
6. 任务管理集成到引擎生命周期中
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from dataclasses import dataclass, field

# 导入核心框架
from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.types.entities import EngineConfigEntity
from quant_server.core.engines.types.enums import (
    EngineType,
    ComponentStatus,
    PriorityLevel,
    EngineErrorLevel,
    ResourceType
)

# 导入事件系统
from quant_server.core.engines.types.entities import EventEntity
from quant_server.core.engines.system.event_engine import EventEngine

# 导入数据同步相关
from quant_server.modules.data.events import (
    DataEventType,
)
from quant_server.modules.data.events.types import DataSyncType
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
    priority: int = PriorityLevel.NORMAL  # 任务优先级
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
    数据同步引擎重构版

    基于EngineBase基类，遵循统一的生命周期管理
    通过EngineFactory创建和管理，支持配置驱动和依赖注入

    主要功能：
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

    状态流转：
    PENDING → PREPARING → DOWNLOADING → PROCESSING → SAVING → COMPLETED
                            ↓              ↓             ↓
                          RETRYING      RETRYING     RETRYING
                            ↓              ↓             ↓
                           FAILED        FAILED        FAILED
    """

    # 引擎类型定义
    engine_type = EngineType.DATA_SYNC

    def __init__(
        self,
        config: EngineConfigEntity,
        event_engine: Optional[EventEngine] = None,
        resource_pool=None,
        sync_service: Optional[DataSyncService] = None
    ):
        """
        初始化数据同步引擎

        Args:
            config: 引擎配置实体
            event_engine: 事件引擎实例
            resource_pool: 资源池管理器
            sync_service: 数据同步服务实例（依赖注入）
        """
        super().__init__(config, event_engine, resource_pool)

        # 服务依赖注入
        self.sync_service = sync_service

        # 从配置中获取引擎特定参数
        engine_config = config.config or {}
        self.max_concurrent_tasks = engine_config.get("max_concurrent_tasks", 3)
        self.task_timeout_seconds = engine_config.get("task_timeout_seconds", 3600)
        self.default_data_sources = engine_config.get("default_data_sources", ["tushare"])
        self.cleanup_interval_hours = engine_config.get("cleanup_interval_hours", 24)

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

        # 后台任务
        self._task_processor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(f"数据同步引擎初始化: {config.name}")

    # ==================== 抽象方法实现 ====================

    async def _on_initialize(self):
        """
        引擎初始化逻辑

        初始化引擎内部状态，验证依赖服务，注册事件处理器
        """
        # 验证同步服务依赖
        if not self.sync_service:
            logger.warning("数据同步服务未配置，将使用默认实现")
            # 可以在这里创建默认的同步服务实例

        # 初始化任务队列
        self.task_queue = asyncio.Queue()
        self.active_tasks.clear()
        self.tasks.clear()

        # 注册事件处理器
        await self._register_event_handlers()

        logger.info(f"数据同步引擎初始化完成: {self.config.name}")

    async def _on_start(self):
        """
        引擎启动逻辑

        启动任务处理循环和后台清理任务
        """
        # 启动任务处理循环
        self._task_processor_task = asyncio.create_task(
            self._process_task_queue(),
            name=f"{self.config.name}_task_processor"
        )

        # 启动后台清理任务
        self._cleanup_task = asyncio.create_task(
            self._periodic_cleanup(),
            name=f"{self.config.name}_cleanup"
        )

        logger.info(f"数据同步引擎已启动: {self.config.name}")

    async def _on_stop(self):
        """
        引擎停止逻辑

        停止所有运行中的任务，清理资源
        """
        # 停止任务处理循环
        if self._task_processor_task:
            self._task_processor_task.cancel()
            try:
                await self._task_processor_task
            except asyncio.CancelledError:
                pass
            self._task_processor_task = None

        # 停止后台清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # 取消所有运行中的任务
        for task_id in list(self.active_tasks):
            await self._cancel_task_internal(task_id)

        # 清空任务队列
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
            except asyncio.QueueEmpty:
                break

        logger.info(f"数据同步引擎已停止: {self.config.name}")

    async def _on_health_check(self) -> Dict[str, Any]:
        """
        引擎健康检查

        检查引擎运行状态、任务队列状态、依赖服务状态等

        Returns:
            引擎特定的健康检查信息
        """
        health_info = {
            "task_queue_size": self.task_queue.qsize(),
            "active_tasks": len(self.active_tasks),
            "total_tasks": len(self.tasks),
            "stats": self.stats.copy(),
            "sync_service_available": self.sync_service is not None,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }

        # 检查同步服务健康状态
        if self.sync_service and hasattr(self.sync_service, 'health_check'):
            try:
                sync_service_health = await self.sync_service.health_check()
                health_info["sync_service_health"] = sync_service_health
            except Exception as e:
                health_info["sync_service_health"] = {"error": str(e)}

        return health_info

    async def _on_collect_metrics(self):
        """
        收集引擎性能指标

        收集任务处理指标、队列指标、性能指标等
        """
        metrics = {
            "task_queue_size": self.task_queue.qsize(),
            "active_tasks": len(self.active_tasks),
            "total_tasks": len(self.tasks),
            "completed_tasks": self.stats["completed_tasks"],
            "failed_tasks": self.stats["failed_tasks"],
            "cancelled_tasks": self.stats["cancelled_tasks"],
            "total_records": self.stats["total_records"],
            "avg_duration_per_task": (
                self.stats["total_duration"] / self.stats["completed_tasks"]
                if self.stats["completed_tasks"] > 0 else 0
            ),
        }

        # 更新引擎性能指标
        self.record.update_performance_metrics(metrics)

        # 更新资源使用情况
        self.record.update_resource_usage(ResourceType.TASK_QUEUE, len(self.active_tasks))
        self.record.update_resource_usage(ResourceType.QUEUE_LENGTH, self.task_queue.qsize())

    async def _on_handle_event(self, event: EventEntity):
        """
        处理引擎特定事件

        Args:
            event: 事件实体
        """
        # 处理数据同步相关事件
        if event.event_type == DataEventType.SYNC_STARTED:
            await self._on_external_sync_started(event)
        elif event.event_type == "system.heartbeat":
            await self._on_heartbeat(event)
        elif event.event_type == "engine_command":
            await self._handle_engine_command(event.data)

    async def _on_auto_recover(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """
        自动恢复逻辑

        Args:
            error: 发生的异常
            context: 错误上下文

        Returns:
            恢复是否成功
        """
        logger.info(f"尝试自动恢复数据同步引擎: {self.config.name}")

        try:
            # 重启任务处理循环
            if self._task_processor_task and self._task_processor_task.done():
                self._task_processor_task = asyncio.create_task(
                    self._process_task_queue(),
                    name=f"{self.config.name}_task_processor_recovered"
                )

            # 重启后台清理任务
            if self._cleanup_task and self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(
                    self._periodic_cleanup(),
                    name=f"{self.config.name}_cleanup_recovered"
                )

            # 清理异常任务
            for task_id in list(self.active_tasks):
                task_info = self.tasks.get(task_id)
                if task_info and task_info.get("status") in [SyncTaskStatus.FAILED, SyncTaskStatus.CANCELLED]:
                    self.active_tasks.discard(task_id)

            logger.info(f"数据同步引擎自动恢复成功: {self.config.name}")
            return True

        except Exception as recover_error:
            logger.error(f"数据同步引擎自动恢复失败: {recover_error}")
            return False

    # ==================== 事件处理器 ====================

    async def _register_event_handlers(self):
        """注册事件处理器"""
        if not self.event_engine:
            logger.warning("事件引擎未配置，跳过事件处理器注册")
            return

        # 注册数据同步开始事件
        self.event_engine.register(
            DataEventType.SYNC_STARTED,
            self._on_external_sync_started
        )

        # 注册系统心跳事件
        self.event_engine.register(
            "system.heartbeat",
            self._on_heartbeat
        )

        # 注册引擎命令事件
        self.event_engine.register(
            "engine_command",
            self._on_handle_event
        )

        logger.debug(f"数据同步引擎事件处理器注册完成: {self.config.name}")

    async def _on_external_sync_started(self, event):
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

    # noinspection PyUnusedLocal
    async def _on_heartbeat(self, event):
        """处理心跳事件，执行监控和清理"""
        try:
            # 检查超时任务
            await self._check_timeout_tasks()

            # 收集指标
            await self._collect_metrics()

        except Exception as e:
            logger.error(f"处理心跳事件失败: {e}", exc_info=True)

    # ==================== 任务处理循环 ====================

    async def _process_task_queue(self):
        """处理任务队列的主循环"""
        logger.info(f"数据同步任务处理循环已启动: {self.config.name}")

        try:
            while self.record.status == ComponentStatus.RUNNING:
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
                        logger.debug(f"达到并发任务限制 ({self.max_concurrent_tasks})，任务 {task_id} 等待中")
                        # 放回队列等待
                        await self.task_queue.put(task_info)
                        await asyncio.sleep(5)
                        continue

                    # 执行任务
                    self.active_tasks.add(task_id)
                    self.create_background_task(
                        self._execute_sync_task(task_info)
                    )

                except asyncio.TimeoutError:
                    # 队列为空，继续循环
                    continue
                except asyncio.CancelledError:
                    logger.info(f"任务处理循环被取消: {self.config.name}")
                    break
                except Exception as e:
                    logger.error(f"任务处理循环异常: {e}", exc_info=True)
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"任务处理循环意外退出: {e}")
        finally:
            logger.info(f"数据同步任务处理循环已停止: {self.config.name}")

    async def _execute_sync_task(self, task_info: Dict[str, Any]):
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
            self.stats["last_sync_time"] = datetime.now().timestamp()

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

    async def _perform_sync(
        self,
        task_id: str,
        config: SyncTaskConfig
    ) -> SyncTaskResult:
        """执行具体地同步逻辑"""
        start_time = datetime.now()
        result = SyncTaskResult()

        try:
            if not self.sync_service:
                raise RuntimeError("同步服务未配置")

            # 发布下载开始事件
            await self._update_task_status(task_id, SyncTaskStatus.DOWNLOADING)

            # 执行同步
            # 从date_range中提取start_date和end_date
            start_date = config.date_range.get('start') if config.date_range else None
            end_date = config.date_range.get('end') if config.date_range else None
            
            # 导入DataType枚举
            from quant_server.modules.data.constants import DataType
            
            sync_result = await self.sync_service.sync_market_data(
                data_type=DataType(config.sync_type.value),
                start_date=start_date,
                end_date=end_date,
                ts_codes=config.symbols,
                batch_size=config.batch_size
            )

            # 构建结果
            result.success = sync_result.get("success", True)
            sync_result_data = sync_result.get("result", {})
            result.total_records = sync_result_data.get("total_items", 0)
            result.inserted_records = sync_result_data.get("records_added", 0)
            result.updated_records = sync_result_data.get("records_updated", 0)
            result.failed_records = sync_result_data.get("records_failed", 0)
            result.summary = sync_result_data

            # 发布处理完成事件
            await self._update_task_status(task_id, SyncTaskStatus.PROCESSING)

        except Exception as e:
            logger.error(f"同步执行失败: {e}", exc_info=True)
            result.success = False
            result.error_message = str(e)

            # 记录错误
            await self.handle_error(
                e,
                EngineErrorLevel.ERROR,
                {
                    "task_id": task_id,
                    "sync_type": config.sync_type.value,
                    "data_sources": config.data_sources
                }
            )

        finally:
            # 计算持续时间
            result.duration_seconds = (datetime.now() - start_time).total_seconds()

            # 更新任务进度
            progress = SyncTaskProgress(
                total_items=result.total_records,
                processed_items=result.total_records - result.failed_records,
                failed_items=result.failed_records,
                progress_percentage=100.0 if result.success else 0.0,
                start_time=start_time,
                estimated_remaining=0.0
            )
            await self._update_task_status(task_id, SyncTaskStatus.SAVING, progress)

        return result

    # ==================== 任务管理 ====================

    async def start_sync_task(
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
        if self.record.status != ComponentStatus.RUNNING:
            raise RuntimeError(f"引擎 {self.config.name} 未运行")

        # 参数验证
        if isinstance(sync_type, str):
            sync_type = DataSyncType(sync_type.lower())

        # 生成任务ID
        task_id = custom_task_id or self._generate_task_id(sync_type)

        # 创建任务配置
        task_config = SyncTaskConfig(
            sync_type=sync_type,
            data_sources=data_sources or self.default_data_sources,
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
            "start_time": None,
        }

        # 添加到队列
        await self.task_queue.put(self.tasks[task_id])

        # 更新统计
        self.stats["total_tasks"] += 1

        # 发布任务开始事件
        await self._publish_event("data_sync_started", {
            "task_id": task_id,
            "sync_type": sync_type.value,
            "config": self._config_to_dict(task_config),
            "queue_position": self.task_queue.qsize(),
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"创建同步任务: {task_id} ({sync_type.value})")
        return task_id

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消同步任务

        Args:
            task_id: 任务ID

        Returns:
            取消是否成功
        """
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

        # 发布任务取消事件
        await self._publish_event("data_sync_cancelled", {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"取消同步任务: {task_id}")
        return True

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息，不存在时返回None
        """
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
            "updated_at": task_info["updated_at"].isoformat() if isinstance(task_info["updated_at"], datetime) else task_info["updated_at"],
            "duration_seconds": duration,
            "is_active": task_id in self.active_tasks,
            "result": task_info.get("result"),
            "error_count": task_info.get("error_count", 0),
            "retry_count": task_info.get("retry_count", 0),
        }

        return status

    async def get_all_tasks(self, include_completed: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务

        Args:
            include_completed: 是否包含已完成的任务

        Returns:
            任务字典
        """
        tasks = {}
        for task_id, task_info in self.tasks.items():
            if not include_completed and task_info["status"] in [SyncTaskStatus.COMPLETED, SyncTaskStatus.FAILED]:
                continue
            tasks[task_id] = await self.get_task_status(task_id)

        return tasks

    # ==================== 状态更新和事件发布 ====================

    async def _update_task_status(
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

        if status == SyncTaskStatus.PREPARING:
            task_info["start_time"] = datetime.now()

        if progress:
            task_info["progress"] = progress

        # 发布进度事件
        if status in [SyncTaskStatus.DOWNLOADING, SyncTaskStatus.PROCESSING, SyncTaskStatus.SAVING]:
            await self._publish_sync_progress(task_id, progress)

    async def _publish_sync_progress(
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

        # 使用事件引擎发布事件
        await self._publish_event("data_sync_progress", {
            "task_id": task_id,
            "sync_type": config.sync_type.value,
            "progress": progress_data.progress_percentage,
            "current_item": progress_data.current_item,
            "total_items": progress_data.total_items,
            "processed_items": progress_data.processed_items,
            "current_step": progress_data.current_step,
            "estimated_remaining": progress_data.estimated_remaining,
            "timestamp": datetime.now().isoformat()
        })

    async def _publish_sync_completed(
        self,
        task_id: str,
        config: SyncTaskConfig,
        result: SyncTaskResult
    ):
        """发布同步完成事件"""
        await self._publish_event("data_sync_completed", {
            "task_id": task_id,
            "sync_type": config.sync_type.value,
            "record_count": result.total_records,
            "duration_seconds": result.duration_seconds,
            "success": True,
            "summary": {
                "inserted": result.inserted_records,
                "updated": result.updated_records,
                "failed": result.failed_records,
                **result.summary
            },
            "config": self._config_to_dict(config),
            "timestamp": datetime.now().isoformat()
        })

    async def _publish_sync_failed(
        self,
        task_id: str,
        config: SyncTaskConfig,
        result: SyncTaskResult
    ):
        """发布同步失败事件"""
        await self._publish_event("data_sync_failed", {
            "task_id": task_id,
            "sync_type": config.sync_type.value,
            "error_message": result.error_message or "未知错误",
            "error_details": None,
            "retry_count": self.tasks[task_id].get("retry_count", 0) if task_id in self.tasks else 0,
            "config": self._config_to_dict(config),
            "timestamp": datetime.now().isoformat()
        })

    # ==================== 重试和错误处理 ====================

    async def _should_retry_task(self, task_id: str) -> bool:
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

    async def _retry_task(self, task_id: str):
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

    async def _mark_task_failed(self, task_id: str, error_message: str):
        """标记任务失败"""
        if task_id not in self.tasks:
            return

        task_info = self.tasks[task_id]
        config = task_info["config"]

        task_info["status"] = SyncTaskStatus.FAILED
        task_info["updated_at"] = datetime.now()

        # 发布失败事件
        await self._publish_sync_failed(
            task_id,
            config,
            SyncTaskResult(success=False, error_message=error_message)
        )

        self.stats["failed_tasks"] += 1
        logger.error(f"标记任务失败: {task_id}, 错误: {error_message}")

    async def _cancel_task_internal(self, task_id: str):
        """内部取消任务逻辑"""
        if task_id not in self.tasks:
            return

        task_info = self.tasks[task_id]
        task_info["status"] = SyncTaskStatus.CANCELLED
        task_info["updated_at"] = datetime.now()

        # 如果任务在活跃集合中，移除
        self.active_tasks.discard(task_id)

        logger.debug(f"内部取消任务: {task_id}")

    # ==================== 监控和清理 ====================

    async def _check_timeout_tasks(self):
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

    async def _periodic_cleanup(self):
        """定期清理任务"""
        cleanup_interval = self.cleanup_interval_hours * 3600  # 转换为秒

        try:
            while self.record.status == ComponentStatus.RUNNING:
                await asyncio.sleep(cleanup_interval)
                await self._cleanup_completed_tasks()
        except asyncio.CancelledError:
            logger.info(f"后台清理任务被取消: {self.config.name}")
        except Exception as e:
            logger.error(f"后台清理任务异常: {e}")

    async def _cleanup_completed_tasks(self):
        """清理已完成的任务"""
        tasks_to_remove = []
        cleanup_threshold = timedelta(hours=self.cleanup_interval_hours)

        for task_id, task_info in self.tasks.items():
            if task_id in self.active_tasks:
                continue

            status = task_info["status"]
            updated_at = task_info["updated_at"]
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)

            # 清理已完成或失败超过指定时间的任务
            if status in [SyncTaskStatus.COMPLETED, SyncTaskStatus.FAILED, SyncTaskStatus.CANCELLED]:
                if datetime.now() - updated_at > cleanup_threshold:
                    tasks_to_remove.append(task_id)

        # 移除任务
        for task_id in tasks_to_remove:
            self.tasks.pop(task_id, None)

        if tasks_to_remove:
            logger.debug(f"清理了 {len(tasks_to_remove)} 个旧任务")

    # ==================== 工具方法 ====================

    def _generate_task_id(self, sync_type: DataSyncType) -> str:
        """生成任务ID"""
        self.task_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"sync_{sync_type.value}_{timestamp}_{self.task_counter:06d}"

    @staticmethod
    def _config_to_dict(config: SyncTaskConfig) -> Dict[str, Any]:
        """将配置转换为字典"""
        return {
            "sync_type": config.sync_type.value,
            "data_sources": config.data_sources,
            "symbols": config.symbols,
            "date_range": config.date_range,
            "batch_size": config.batch_size,
            "max_retries": config.max_retries,
            "priority": config.priority,
            "callback_url": config.callback_url,
        }

    async def _handle_engine_command(self, command_data: Dict[str, Any]):
        """
        处理引擎命令

        Args:
            command_data: 命令数据
        """
        command = command_data.get("command")

        if command == "get_tasks":
            # 返回任务列表
            include_completed = command_data.get("include_completed", False)
            tasks = await self.get_all_tasks(include_completed)
            await self._publish_event("engine_command_response", {
                "command": "get_tasks",
                "tasks": tasks,
                "total_tasks": len(tasks)
            })

        elif command == "get_stats":
            # 返回统计信息
            stats = {
                "engine_stats": self.stats,
                "queue_size": self.task_queue.qsize(),
                "active_tasks": len(self.active_tasks),
                "total_tasks": len(self.tasks),
            }
            await self._publish_event("engine_command_response", {
                "command": "get_stats",
                "stats": stats
            })

        elif command == "cancel_task":
            # 取消任务
            task_id = command_data.get("task_id")
            if task_id:
                success = await self.cancel_task(task_id)
                await self._publish_event("engine_command_response", {
                    "command": "cancel_task",
                    "task_id": task_id,
                    "success": success
                })

    def get_engine_status(self) -> Dict[str, Any]:
        """
        获取引擎状态

        Returns:
            引擎状态信息
        """
        base_status = super().get_status_info()

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
                "default_data_sources": self.default_data_sources,
                "cleanup_interval_hours": self.cleanup_interval_hours,
            },
        }

        return engine_status


# ==================== 引擎工厂注册 ====================

def register_data_sync_engine(factory):
    """
    注册数据同步引擎到引擎工厂

    Args:
        factory: 引擎工厂实例
    """
    from quant_server.core.engines.utils.engine_factory import EngineDescriptor
    from quant_server.core.engines.types.enums import EngineType, EngineCategory

    descriptor = EngineDescriptor(
        engine_type=EngineType.DATA_SYNC,
        engine_class=DataSyncEngine,
        name="data_sync_engine",
        description="数据同步引擎，负责管理数据从外部源同步到内部数据库的完整流程",
        version="1.0.0",
        category=EngineCategory.DATA,
        dependencies=[
            EngineType.EVENT,  # 依赖事件引擎
        ],
        config_schema={
            "required": [],
            "default": {
                "max_concurrent_tasks": 3,
                "task_timeout_seconds": 3600,
                "default_data_sources": ["tushare"],
                "cleanup_interval_hours": 24,
                "auto_start": True,
                "max_retries": 3,
                "health_check_interval": 60,
                "graceful_shutdown_timeout": 30,
            },
            "properties": {
                "max_concurrent_tasks": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "最大并发任务数"
                },
                "task_timeout_seconds": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 86400,
                    "description": "任务超时时间（秒）"
                },
                "default_data_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "默认数据源列表"
                },
                "cleanup_interval_hours": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 720,
                    "description": "清理间隔（小时）"
                },
            }
        },
        tags=["data", "sync", "batch", "etl"]
    )

    try:
        factory.register_engine(descriptor)
        logger.info("数据同步引擎已注册到工厂")
        return True
    except ValueError as e:
        logger.warning(f"数据同步引擎注册失败: {e}")
        return False


# ==================== 便捷函数 ====================

async def create_data_sync_engine(
    name: str = "data_sync_engine",
    config: Optional[Dict[str, Any]] = None,
    sync_service: Optional[DataSyncService] = None,
    event_engine: Optional[EventEngine] = None
) -> DataSyncEngine:
    """
    创建数据同步引擎（便捷函数）

    Args:
        name: 引擎名称
        config: 引擎配置
        sync_service: 数据同步服务
        event_engine: 事件引擎

    Returns:
        数据同步引擎实例
    """
    from quant_server.core.engines.utils.engine_factory import create_engine
    from quant_server.core.engines.types.enums import EngineType

    # 准备配置
    engine_config = config or {}
    if sync_service:
        engine_config["sync_service"] = sync_service

    # 创建引擎
    engine = await create_engine(
        engine_type=EngineType.DATA_SYNC,
        config=engine_config,
        instance_name=name
    )

    # 注入依赖（如果提供了）
    if sync_service:
        engine.sync_service = sync_service
    if event_engine:
        engine.event_engine = event_engine

    # 类型断言，确保返回类型为DataSyncEngine
    return engine  # type: ignore[return-value]


async def start_sync_task(
    engine_name: str = "data_sync_engine",
    sync_type: Union[str, DataSyncType] = DataSyncType.FULL,
    **kwargs
) -> Optional[str]:
    """
    启动同步任务（便捷函数）

    Args:
        engine_name: 引擎名称
        sync_type: 同步类型
        **kwargs: 其他参数传递给start_sync_task

    Returns:
        任务ID，失败时返回None
    """
    from quant_server.core.engines.utils.engine_factory import get_engine

    try:
        engine = await get_engine(engine_name)
        if not engine or not isinstance(engine, DataSyncEngine):
            logger.error(f"找不到数据同步引擎: {engine_name}")
            return None

        return await engine.start_sync_task(sync_type=sync_type, **kwargs)
    except Exception as e:
        logger.error(f"启动同步任务失败: {e}")
        return None


# 导出
__all__ = [
    "DataSyncEngine",
    "SyncTaskStatus",
    "SyncTaskConfig",
    "SyncTaskProgress",
    "SyncTaskResult",
    "register_data_sync_engine",
    "create_data_sync_engine",
    "start_sync_task",
]