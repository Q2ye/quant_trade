"""
数据清洗引擎
负责管理数据清洗和质量提升的完整流程，遵循引擎框架规范

业务范围：
1. 数据标准化：统一数据格式和单位
2. 异常值处理：检测和处理异常数据
3. 缺失值填充：智能填充缺失数据
4. 重复值处理：识别和去重
5. 数据转换：格式转换和归一化

设计原则：
1. 继承EngineBase基类，遵循统一的生命周期管理
2. 利用引擎工厂进行创建和管理
3. 集成到引擎注册表和监控系统
4. 使用事件引擎进行模块间通信
5. 支持配置驱动和动态更新

依赖关系：
- DataCleanService: 执行具体的清洗逻辑
- DataQualityService: 质量检查和验证
- EventEngine: 事件通信总线

状态管理：
UNINITIALIZED → INITIALIZING → INITIALIZED → STARTING → RUNNING
                              ↘ ERROR       ↗ STOPPING → STOPPED
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from dataclasses import dataclass, field

# 导入引擎配置实体
from core.events import BaseEvent
from core.engines.types.entities import EngineConfigEntity
from  core.engines.types.enums import (
    EngineType,
    ComponentStatus,
    PriorityLevel,
    EngineCategory
)

# 导入引擎基类
from core.engines.base.engine_base import EngineBase
from core.engines.utils.engine_factory import EngineDescriptor

# 导入业务模块
from modules.data.events import (
    DataProcessingStatus,
    MarketDataProcessingEvent,
    MarketDataProcessedEvent,
    MarketDataValidatedEvent,
    MarketDataMetadata,
    DataEventType
)
from modules.data.services.clean_service import DataCleanService
from modules.data.services.quality_service import DataQualityService

logger = logging.getLogger(__name__)


class CleanStep(str, Enum):
    """清洗步骤枚举"""
    VALIDATE_INPUT = "validate_input"  # 验证输入数据
    STANDARDIZE = "standardize"  # 标准化处理
    HANDLE_MISSING = "handle_missing"  # 处理缺失值
    DETECT_OUTLIERS = "detect_outliers"  # 检测异常值
    REMOVE_DUPLICATES = "remove_duplicates"  # 去重处理
    TRANSFORM = "transform"  # 数据转换
    VALIDATE_OUTPUT = "validate_output"  # 验证输出数据
    SAVE_RESULTS = "save_results"  # 保存结果


class CleanTaskStatus(str, Enum):
    """清洗任务状态枚举"""
    PENDING = "pending"  # 等待执行
    PREPARING = "preparing"  # 准备中
    PROCESSING = "processing"  # 处理中
    VALIDATING = "validating"  # 验证中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 已失败
    CANCELLED = "cancelled"  # 已取消
    PARTIAL_SUCCESS = "partial_success"  # 部分成功


@dataclass
class CleanRule:
    """清洗规则定义"""
    name: str
    rule_type: str  # standardization/missing/outlier/duplicate/transformation
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "rule_type": self.rule_type,
            "parameters": self.parameters,
            "enabled": self.enabled,
            "priority": self.priority
        }


@dataclass
class CleanTaskConfig:
    """清洗任务配置"""
    data_type: str  # 数据类型
    symbols: List[str]  # 标的列表
    rules: List[CleanRule] = field(default_factory=list)  # 清洗规则
    quality_threshold: float = 80.0  # 质量阈值
    enable_validation: bool = True  # 启用验证
    batch_size: int = 1000  # 批量大小
    max_retries: int = 2  # 最大重试次数
    priority: int = PriorityLevel.NORMAL.value  # 任务优先级

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "data_type": self.data_type,
            "symbols": self.symbols,
            "rules": [rule.to_dict() for rule in self.rules],
            "quality_threshold": self.quality_threshold,
            "enable_validation": self.enable_validation,
            "batch_size": self.batch_size,
            "max_retries": self.max_retries,
            "priority": self.priority
        }


@dataclass
class CleanTaskProgress:
    """清洗任务进度"""
    total_steps: int = 0
    completed_steps: int = 0
    current_step: CleanStep = CleanStep.VALIDATE_INPUT
    current_symbol: str = ""
    processed_symbols: int = 0
    total_symbols: int = 0
    progress_percentage: float = 0.0
    start_time: Optional[datetime] = None
    step_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step.value,
            "current_symbol": self.current_symbol,
            "processed_symbols": self.processed_symbols,
            "total_symbols": self.total_symbols,
            "progress_percentage": self.progress_percentage,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "step_details": self.step_details
        }


@dataclass
class CleanTaskResult:
    """清洗任务结果"""
    success: bool = False
    total_records: int = 0
    cleaned_records: int = 0
    failed_records: int = 0
    quality_score_before: float = 0.0
    quality_score_after: float = 0.0
    improvement: float = 0.0  # 质量提升
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "total_records": self.total_records,
            "cleaned_records": self.cleaned_records,
            "failed_records": self.failed_records,
            "quality_score_before": self.quality_score_before,
            "quality_score_after": self.quality_score_after,
            "improvement": self.improvement,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "step_results": self.step_results
        }


class DataCleanEngine(EngineBase):
    """
    数据清洗引擎

    基于引擎框架重构，继承EngineBase，提供标准化的生命周期管理、
    状态监控、事件发布和依赖管理。

    引擎类型：DATA_CLEAN
    引擎分类：DATA_PROCESSING
    依赖服务：DataCleanService, DataQualityService

    使用示例：
        # 通过引擎工厂创建
        factory = await get_engine_factory()
        clean_engine = await factory.create_engine(
            EngineType.DATA_CLEAN,
            config={
                "max_concurrent_tasks": 3,
                "task_timeout_seconds": 1800
            },
            instance_name="data_clean_engine"
        )

        # 创建清洗任务
        task_id = await clean_engine.create_clean_task(
            data_type="daily",
            symbols=["000001.SZ", "000002.SZ"]
        )

        # 执行清洗任务
        await clean_engine.execute_clean_task(task_id)
    """

    # 引擎类型定义（覆盖基类属性）
    @property
    def engine_type(self) -> EngineType:
        """获取引擎类型"""
        return EngineType.DATA_CLEAN

    def __init__(
        self,
        config: EngineConfigEntity,
        event_engine=None,
        clean_service: Optional[DataCleanService] = None,
        quality_service: Optional[DataQualityService] = None,
        **kwargs
    ):
        """
        初始化数据清洗引擎

        Args:
            config: 引擎配置实体
            event_engine: 事件引擎实例
            clean_service: 数据清洗服务实例
            quality_service: 数据质量服务实例
            **kwargs: 其他参数
        """
        # 调用父类初始化
        super().__init__(config, event_engine, **kwargs)

        # 服务依赖
        self.clean_service = clean_service
        self.quality_service = quality_service

        # 从配置中获取参数
        self.max_concurrent_tasks = config.config.get("max_concurrent_tasks", 2)
        self.task_timeout_seconds = config.config.get("task_timeout_seconds", 1800)

        # 任务管理
        self.tasks: Dict[str, Dict[str, Any]] = {}  # task_id -> 任务信息
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Set[str] = set()  # 活跃任务ID集合
        self._task_refs: Dict[str, asyncio.Task] = {}  # task_id → asyncio.Task（用于取消）
        self.task_counter = 0

        # 规则库
        self.default_rules: Dict[str, CleanRule] = self._create_default_rules()

        # 任务处理器任务
        self.task_processor_task: Optional[asyncio.Task] = None

        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_records_cleaned": 0,
            "total_quality_improvement": 0.0,
            "avg_processing_time": 0.0,
            "last_clean_time": None,
        }

        logger.info(f"数据清洗引擎初始化完成: {self.config.name}")

    async def _on_initialize(self):
        """
        引擎初始化逻辑

        执行引擎特定的初始化工作，包括：
        1. 注册事件处理器
        2. 初始化默认规则
        3. 准备任务队列
        """
        logger.info(f"数据清洗引擎开始初始化: {self.config.name}")

        # 检查服务依赖
        if not self.clean_service:
            logger.warning("数据清洗服务未配置，引擎功能可能受限")

        if not self.quality_service:
            logger.warning("数据质量服务未配置，质量检查功能可能受限")

        # 初始化完成
        logger.info(f"数据清洗引擎初始化完成: {self.config.name}")

    async def _on_start(self):
        """
        引擎启动逻辑

        执行引擎特定的启动工作，包括：
        1. 注册事件处理器
        2. 启动任务处理循环
        """
        logger.info(f"数据清洗引擎开始启动: {self.config.name}")

        # 注册事件处理器
        await self._register_event_handlers()

        # 启动任务处理循环
        self.task_processor_task = self.create_background_task(
            self._process_task_queue()
        )

        # 发布引擎启动事件
        await self._publish_event("data_clean_engine_started", {
            "engine_name": self.config.name,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "task_timeout_seconds": self.task_timeout_seconds
        })

        logger.info(f"数据清洗引擎启动完成: {self.config.name}")

    async def _on_stop(self):
        """
        引擎停止逻辑

        执行引擎特定的停止工作，包括：
        1. 停止任务处理循环
        2. 取消所有运行中的任务
        3. 清理任务队列
        """
        logger.info(f"数据清洗引擎开始停止: {self.config.name}")

        # 停止任务处理循环
        if self.task_processor_task and not self.task_processor_task.done():
            self.task_processor_task.cancel()
            try:
                await self.task_processor_task
            except asyncio.CancelledError:
                pass

        # 取消所有运行中的任务
        for task_id in list(self.active_tasks):
            await self._cancel_task(task_id)

        # 清空任务队列
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
            except asyncio.QueueEmpty:
                break

        # 发布引擎停止事件
        await self._publish_event("data_clean_engine_stopped", {
            "engine_name": self.config.name,
            "total_tasks": self.stats["total_tasks"],
            "completed_tasks": self.stats["completed_tasks"],
            "failed_tasks": self.stats["failed_tasks"]
        })

        logger.info(f"数据清洗引擎停止完成: {self.config.name}")

    async def _on_health_check(self) -> Dict[str, Any]:
        """
        引擎健康检查逻辑

        Returns:
            引擎特定的健康检查信息
        """
        # 检查任务队列状态
        queue_size = self.task_queue.qsize()
        active_task_count = len(self.active_tasks)

        # 检查任务处理循环状态
        task_processor_running = (
            self.task_processor_task is not None
            and not self.task_processor_task.done()
        )

        # 检查服务依赖状态
        clean_service_available = self.clean_service is not None
        quality_service_available = self.quality_service is not None

        return {
            "task_queue_size": queue_size,
            "active_tasks": active_task_count,
            "total_tasks": len(self.tasks),
            "task_processor_running": task_processor_running,
            "clean_service_available": clean_service_available,
            "quality_service_available": quality_service_available,
            "stats": self.stats.copy()
        }

    async def _on_collect_metrics(self):
        """
        引擎指标收集逻辑

        收集引擎特定的性能指标
        """
        # 更新性能指标
        self.record.update_performance_metrics({
            "task_queue_size": self.task_queue.qsize(),
            "active_tasks": len(self.active_tasks),
            "total_tasks": len(self.tasks),
            "completed_tasks": self.stats["completed_tasks"],
            "failed_tasks": self.stats["failed_tasks"],
            "total_records_cleaned": self.stats["total_records_cleaned"],
            "avg_processing_time": self.stats["avg_processing_time"]
        })

        # 更新资源使用情况
        self.record.update_resource_usage(
            "memory_tasks",
            len(self.tasks) * 0.1  # 估算每个任务占用0.1KB内存
        )

    async def _on_handle_event(self, event: BaseEvent):
        """
        引擎事件处理逻辑

        Args:
            event: 事件实体
        """
        # 处理引擎命令
        if event.event_type == "engine_command":
            await self._handle_engine_command(event.data)

        # 处理数据清洗相关事件
        elif event.event_type == DataEventType.MARKET_DATA_RAW_ARRIVED.value:
            await self._handle_market_data_arrived(event)

        elif event.event_type == DataEventType.QUALITY_ISSUE_FOUND.value:
            await self._handle_quality_issue_found(event)

    async def _on_auto_recover(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """
        引擎自动恢复逻辑

        Args:
            error: 发生的异常
            context: 错误上下文

        Returns:
            恢复是否成功
        """
        logger.info(f"数据清洗引擎尝试自动恢复: {self.config.name}")

        try:
            # 尝试重新启动任务处理循环
            if (self.task_processor_task is None or
                self.task_processor_task.done()):
                self.task_processor_task = self.create_background_task(
                    self._process_task_queue()
                )
                logger.info("任务处理循环已重新启动")

            # 清理失败的任务
            failed_tasks = [
                task_id for task_id, task_info in self.tasks.items()
                if task_info.get("status") == CleanTaskStatus.FAILED
            ]

            for task_id in failed_tasks[:5]:  # 最多清理5个失败任务
                await self._cleanup_failed_task(task_id)

            logger.info(f"数据清洗引擎自动恢复成功: {self.config.name}")
            return True

        except Exception as recover_error:
            logger.error(f"数据清洗引擎自动恢复失败: {recover_error}")
            return False

    async def _register_event_handlers(self):
        """
        注册事件处理器
        """
        if not self.event_engine:
            logger.warning("事件引擎未配置，无法注册事件处理器")
            return

        # 注册数据事件处理器
        try:
            # 监听市场数据到达事件
            await self.event_engine.register_handler(
                DataEventType.MARKET_DATA_RAW_ARRIVED.value,
                self._handle_market_data_arrived
            )

            # 监听质量问题事件
            await self.event_engine.register_handler(
                DataEventType.QUALITY_ISSUE_FOUND.value,
                self._handle_quality_issue_found
            )

            logger.info("数据清洗引擎事件处理器注册完成")

        except Exception as e:
            logger.error(f"注册事件处理器失败: {e}")

    async def _handle_market_data_arrived(self, event: BaseEvent):
        """
        处理市场数据到达事件

        Args:
            event: 事件实体
        """
        try:
            data = event.data
            metadata_dict = data.get("metadata", {})

            # 解析元数据
            metadata = MarketDataMetadata.from_dict(metadata_dict)

            # 检查是否需要自动清洗
            should_clean = await self._should_auto_clean(metadata)
            if not should_clean:
                return

            # 创建清洗任务
            task_id = await self.create_clean_task(
                data_type=metadata.data_type,
                symbols=metadata.symbols,
                auto_triggered=True,
                trigger_event_id=event.event_id
            )

            # 执行清洗任务
            await self.execute_clean_task(task_id)

        except Exception as e:
            logger.error(f"处理市场数据到达事件失败: {e}")
            await self.handle_error(e, context={"event_type": "market_data_arrived"})

    async def _handle_quality_issue_found(self, event: BaseEvent):
        """
        处理质量问题事件

        Args:
            event: 事件实体
        """
        try:
            data = event.data
            issue_type = data.get("issue_type")
            table_name = data.get("table_name")
            column_name = data.get("column_name")
            severity = data.get("severity")

            # 只处理中高严重度的问题
            if severity not in ["high", "critical", "medium"]:
                return

            # 创建修复任务
            task_id = await self.create_fix_task(
                issue_type=issue_type,
                table_name=table_name,
                column_name=column_name,
                severity=severity,
                trigger_event_id=event.event_id
            )

            logger.info(f"创建修复任务 {task_id} 处理质量问题: {issue_type}")

        except Exception as e:
            logger.error(f"处理质量问题事件失败: {e}")
            await self.handle_error(e, context={"event_type": "quality_issue_found"})

    async def _process_task_queue(self):
        """
        处理任务队列的主循环
        """
        logger.info("数据清洗任务处理循环已启动")

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
                    bg_task = self.create_background_task(
                        self._execute_clean_task(task_info)
                    )
                    self._task_refs[task_id] = bg_task  # 存储引用用于取消

                except asyncio.TimeoutError:
                    # 队列为空，继续循环
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"任务处理循环异常: {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("任务处理循环被取消")
            raise
        except Exception as e:
            logger.error(f"任务处理循环意外退出: {e}")
            await self.handle_error(e, context={"loop": "task_processor"})
        finally:
            logger.info("数据清洗任务处理循环已停止")

    async def create_clean_task(
        self,
        data_type: str,
        symbols: List[str],
        rules: Optional[List[CleanRule]] = None,
        config: Optional[Dict[str, Any]] = None,
        auto_triggered: bool = False,
        trigger_event_id: Optional[str] = None
    ) -> str:
        """
        创建清洗任务

        Args:
            data_type: 数据类型
            symbols: 标的列表
            rules: 清洗规则列表
            config: 额外配置
            auto_triggered: 是否自动触发
            trigger_event_id: 触发事件ID

        Returns:
            任务ID

        Raises:
            RuntimeError: 引擎未运行
            ValueError: 参数无效
        """
        # 检查引擎状态
        if self.record.status != ComponentStatus.RUNNING:
            raise RuntimeError(f"引擎 {self.config.name} 未运行")

        # 生成任务ID
        task_id = self._generate_task_id(data_type)

        # 合并规则
        effective_rules = rules or self._get_default_rules_for_type(data_type)

        # 创建任务配置
        task_config_dict = {
            "data_type": data_type,
            "symbols": symbols,
            "rules": effective_rules,
            "quality_threshold": 80.0,
            "enable_validation": True,
            "batch_size": 1000,
            "max_retries": 2,
            "priority": PriorityLevel.NORMAL.value
        }

        if config:
            task_config_dict.update(config)

        task_config = CleanTaskConfig(**task_config_dict)

        # 创建任务记录
        self.tasks[task_id] = {
            "task_id": task_id,
            "config": task_config,
            "status": CleanTaskStatus.PENDING,
            "progress": CleanTaskProgress(
                total_symbols=len(symbols),
                current_step=CleanStep.VALIDATE_INPUT,
                start_time=datetime.now()
            ),
            "result": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "error_count": 0,
            "retry_count": 0,
            "metadata": {
                "auto_triggered": auto_triggered,
                "trigger_event_id": trigger_event_id,
                "data_type": data_type,
                "symbol_count": len(symbols),
            }
        }

        # 更新统计
        self.stats["total_tasks"] += 1

        # 发布任务创建事件
        await self._publish_event("clean_task_created", {
            "task_id": task_id,
            "data_type": data_type,
            "symbol_count": len(symbols),
            "auto_triggered": auto_triggered,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"创建清洗任务: {task_id} ({data_type}, {len(symbols)}个标的)")
        return task_id

    async def create_fix_task(
        self,
        issue_type: str,
        table_name: str,
        column_name: str,
        severity: str,
        config: Optional[Dict[str, Any]] = None,
        trigger_event_id: Optional[str] = None
    ) -> str:
        """
        创建数据修复任务

        Args:
            issue_type: 问题类型
            table_name: 表名
            column_name: 列名
            severity: 严重程度
            config: 额外配置
            trigger_event_id: 触发事件ID

        Returns:
            任务ID
        """
        # 检查引擎状态
        if self.record.status != ComponentStatus.RUNNING:
            raise RuntimeError(f"引擎 {self.config.name} 未运行")

        # 生成任务ID
        task_id = f"fix_{issue_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 根据问题类型选择规则
        fix_rules = self._get_fix_rules_for_issue(issue_type)

        # 创建任务配置
        task_config_dict = {
            "data_type": table_name,
            "symbols": [],  # 修复任务可能需要查询具体数据
            "rules": fix_rules,
            "quality_threshold": 90.0,  # 修复任务要求更高的质量
        }

        if config:
            task_config_dict.update(config)

        task_config = CleanTaskConfig(**task_config_dict)

        # 创建任务记录
        self.tasks[task_id] = {
            "task_id": task_id,
            "config": task_config,
            "status": CleanTaskStatus.PENDING,
            "progress": CleanTaskProgress(
                current_step=CleanStep.VALIDATE_INPUT,
                start_time=datetime.now()
            ),
            "result": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "error_count": 0,
            "retry_count": 0,
            "metadata": {
                "issue_type": issue_type,
                "table_name": table_name,
                "column_name": column_name,
                "severity": severity,
                "trigger_event_id": trigger_event_id,
                "is_fix_task": True,
            }
        }

        # 添加到队列
        await self.task_queue.put(self.tasks[task_id])

        # 发布修复任务创建事件
        await self._publish_event("fix_task_created", {
            "task_id": task_id,
            "issue_type": issue_type,
            "table_name": table_name,
            "column_name": column_name,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"创建修复任务: {task_id} (问题: {issue_type}, 表: {table_name}.{column_name})")
        return task_id

    async def execute_clean_task(self, task_id: str) -> bool:
        """
        执行清洗任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功加入队列
        """
        if task_id not in self.tasks:
            logger.error(f"任务不存在: {task_id}")
            return False

        # 检查任务状态
        task_info = self.tasks[task_id]
        if task_info["status"] not in [CleanTaskStatus.PENDING, CleanTaskStatus.FAILED]:
            logger.warning(f"任务 {task_id} 状态为 {task_info['status']}，无法执行")
            return False

        # 更新状态
        task_info["status"] = CleanTaskStatus.PREPARING
        task_info["updated_at"] = datetime.now()

        # 添加到队列
        await self.task_queue.put(task_info)

        logger.info(f"任务 {task_id} 已加入执行队列")
        return True

    # @EngineBase.with_retry
    async def _execute_clean_task(self, task_info: Dict[str, Any]):
        """
        执行清洗任务（带重试机制）
        Args:
            task_info: 任务信息
        """
        task_id = task_info["task_id"]
        config = task_info["config"]
        metadata = task_info.get("metadata", {})

        try:
            # 发布处理开始事件
            await self._publish_processing_event(task_id, config, metadata)

            # 执行清洗流程
            result = await self._perform_cleaning(task_id, config)

            # 更新任务结果
            task_info["result"] = result
            task_info["status"] = CleanTaskStatus.COMPLETED if result.success else CleanTaskStatus.FAILED
            task_info["updated_at"] = datetime.now()

            # 发布处理完成事件
            await self._publish_processed_event(task_id, config, result, metadata)

            # 如果需要验证，发布验证事件
            if result.success and config.enable_validation:
                await self._publish_validated_event(task_id, config, result, metadata)

            # 更新统计
            if result.success:
                self.stats["completed_tasks"] += 1
                self.stats["total_records_cleaned"] += result.cleaned_records
                self.stats["total_quality_improvement"] += result.improvement
            else:
                self.stats["failed_tasks"] += 1

            self.stats["last_clean_time"] = datetime.now().timestamp()

        except asyncio.CancelledError:
            # 任务被取消
            logger.info(f"清洗任务被取消: {task_id}")
            await self._update_task_status(task_id, CleanTaskStatus.CANCELLED)
        except Exception as e:
            # 任务执行失败
            logger.error(f"清洗任务执行失败: {task_id}, 错误: {e}")

            # 检查是否需要重试
            should_retry = await self._should_retry_task(task_id)
            if should_retry:
                await self._retry_task(task_id)
            else:
                await self._mark_task_failed(task_id, str(e))

            # 重新抛出异常，让重试装饰器处理
            raise
        finally:
            # 清理活跃任务集合和任务引用
            self.active_tasks.discard(task_id)
            self._task_refs.pop(task_id, None)
            self.task_queue.task_done()

    async def _perform_cleaning(
        self,
        task_id: str,
        config: CleanTaskConfig,
    ) -> CleanTaskResult:
        """
        执行具体的清洗逻辑

        Args:
            task_id: 任务ID
            config: 任务配置

        Returns:
            清洗任务结果
        """
        start_time = datetime.now()
        result = CleanTaskResult()
        step_results = {}

        try:
            if not self.clean_service:
                raise RuntimeError("清洗服务未配置")

            # 测量清洗前质量
            quality_before = 0.0
            if self.quality_service and config.enable_validation:
                quality_before = await self._measure_quality_before(task_id, config)

            # 执行清洗步骤
            total_steps = len(config.rules) + 2  # 输入验证 + 规则步骤 + 输出验证

            # 步骤1: 验证输入数据
            await self._update_progress(task_id, CleanStep.VALIDATE_INPUT, 1, total_steps)
            step_results["validate_input"] = await self._validate_input_data(task_id, config)

            # 步骤2: 执行清洗规则
            for i, rule in enumerate(config.rules):
                if not rule.enabled:
                    continue

                step_name = f"rule_{rule.name}"
                await self._update_progress(task_id, CleanStep.STANDARDIZE, i + 2, total_steps, {
                    "current_rule": rule.name,
                    "rule_type": rule.rule_type
                })

                step_result = await self._apply_clean_rule(task_id, config, rule)
                step_results[step_name] = step_result

            # 步骤3: 验证输出数据
            await self._update_progress(task_id, CleanStep.VALIDATE_OUTPUT, total_steps - 1, total_steps)
            step_results["validate_output"] = await self._validate_output_data(task_id, config)

            # 步骤4: 保存结果
            await self._update_progress(task_id, CleanStep.SAVE_RESULTS, total_steps, total_steps)
            save_result = await self._save_cleaned_data(task_id, config)
            step_results["save_results"] = save_result

            # 测量清洗后质量
            quality_after = 0.0
            if self.quality_service and config.enable_validation:
                quality_after = await self._measure_quality_after(task_id, config)

            # 构建结果
            result.success = True
            result.total_records = save_result.get("total_records", 0)
            result.cleaned_records = save_result.get("cleaned_records", 0)
            result.failed_records = save_result.get("failed_records", 0)
            result.quality_score_before = quality_before
            result.quality_score_after = quality_after
            result.improvement = max(0.0, quality_after - quality_before)
            result.step_results = step_results

            # 检查质量阈值
            if config.enable_validation and quality_after < config.quality_threshold:
                result.success = False
                result.error_message = f"质量分数 {quality_after} 低于阈值 {config.quality_threshold}"

        except Exception as e:
            logger.error(f"清洗执行失败: {e}")
            result.success = False
            result.error_message = str(e)

        finally:
            # 计算持续时间
            result.duration_seconds = (datetime.now() - start_time).total_seconds()

            # 更新平均处理时间
            if self.stats["completed_tasks"] > 0:
                total_time = self.stats["avg_processing_time"] * (self.stats["completed_tasks"] - 1) + result.duration_seconds
                self.stats["avg_processing_time"] = total_time / self.stats["completed_tasks"]

        return result

    async def _update_progress(
        self,
        task_id: str,
        current_step: CleanStep,
        completed_steps: int,
        total_steps: int,
        step_details: Optional[Dict[str, Any]] = None
    ):
        """
        更新任务进度

        Args:
            task_id: 任务ID
            current_step: 当前步骤
            completed_steps: 完成步骤数
            total_steps: 总步骤数
            step_details: 步骤详情
        """
        if task_id not in self.tasks:
            return

        task_info = self.tasks[task_id]
        task_progress = task_info["progress"]

        task_progress.current_step = current_step
        task_progress.completed_steps = completed_steps
        task_progress.total_steps = total_steps
        task_progress.progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0

        if step_details:
            task_progress.step_details.update(step_details)

        task_info["updated_at"] = datetime.now()

        # 发布进度事件
        await self._publish_progress_event(task_id, task_progress)

    async def _publish_progress_event(self, task_id: str, progress: CleanTaskProgress):
        """
        发布进度事件

        Args:
            task_id: 任务ID
            progress: 任务进度
        """
        if task_id not in self.tasks:
            return

        task_info = self.tasks[task_id]
        config = task_info["config"]
        metadata = task_info.get("metadata", {})

        # 创建市场数据元数据
        market_metadata = MarketDataMetadata(
            data_type=config.data_type,
            symbols=config.symbols,
            start_time=datetime.now() - timedelta(days=30),
            end_time=datetime.now(),
            record_count=0,
            source=self.config.name,
            status=DataProcessingStatus.PROCESSING.value,
        )

        # 发布进度事件
        await self.event_engine.put(
            MarketDataProcessingEvent(
                metadata=market_metadata,
                processing_step=f"clean_{progress.current_step.value}",
                progress=progress.progress_percentage,
                current_symbol=progress.current_symbol,
                processed_count=progress.processed_symbols,
                source=self.config.name,
                data={
                    "task_id": task_id,
                    "step_details": progress.step_details,
                    "total_symbols": progress.total_symbols,
                    "estimated_remaining": None,
                    "metadata": metadata,
                }
            )
        )

    async def _publish_processing_event(self, task_id: str, config: CleanTaskConfig, metadata: Dict[str, Any]):
        """
        发布处理开始事件

        Args:
            task_id: 任务ID
            config: 任务配置
            metadata: 任务元数据
        """
        market_metadata = MarketDataMetadata(
            data_type=config.data_type,
            symbols=config.symbols,
            start_time=datetime.now() - timedelta(days=30),
            end_time=datetime.now(),
            record_count=0,
            source=self.config.name,
            status=DataProcessingStatus.PROCESSING.value,
        )

        await self.event_engine.put(
            MarketDataProcessingEvent(
                metadata=market_metadata,
                processing_step="clean_start",
                progress=0.0,
                source=self.config.name,
                data={
                    "task_id": task_id,
                    "config": config.to_dict(),
                    "metadata": metadata,
                }
            )
        )

    async def _publish_processed_event(
        self,
        task_id: str,
        config: CleanTaskConfig,
        result: CleanTaskResult,
        metadata: Dict[str, Any]
    ):
        """
        发布处理完成事件

        Args:
            task_id: 任务ID
            config: 任务配置
            result: 任务结果
            metadata: 任务元数据
        """
        market_metadata = MarketDataMetadata(
            data_type=config.data_type,
            symbols=config.symbols,
            start_time=datetime.now() - timedelta(days=30),
            end_time=datetime.now(),
            record_count=result.total_records,
            source=self.config.name,
            status=DataProcessingStatus.PROCESSED.value,
            quality_score=result.quality_score_after,
        )

        await self.event_engine.put(
            MarketDataProcessedEvent(
                metadata=market_metadata,
                processing_duration_seconds=result.duration_seconds,
                indicators_calculated=[],
                storage_location=f"cleaned/{config.data_type}",
                processing_stats={
                    "cleaned_records": result.cleaned_records,
                    "failed_records": result.failed_records,
                    "quality_improvement": result.improvement,
                },
                quality_metrics={
                    "before": result.quality_score_before,
                    "after": result.quality_score_after,
                    "improvement": result.improvement,
                },
                source=self.config.name,
                data={
                    "task_id": task_id,
                    "config": config.to_dict(),
                    "result_summary": result.to_dict(),
                    "metadata": metadata,
                }
            )
        )

    async def _publish_validated_event(
        self,
        task_id: str,
        config: CleanTaskConfig,
        result: CleanTaskResult,
        metadata: Dict[str, Any]
    ):
        """
        发布验证完成事件

        Args:
            task_id: 任务ID
            config: 任务配置
            result: 任务结果
            metadata: 任务元数据
        """
        market_metadata = MarketDataMetadata(
            data_type=config.data_type,
            symbols=config.symbols,
            start_time=datetime.now() - timedelta(days=30),
            end_time=datetime.now(),
            record_count=result.total_records,
            source=self.config.name,
            status=DataProcessingStatus.VALIDATED.value,
            quality_score=result.quality_score_after,
        )

        passed = result.quality_score_after >= config.quality_threshold

        await self.event_engine.put(
            MarketDataValidatedEvent(
                metadata=market_metadata,
                validation_results={
                    "passed": passed,
                    "score": result.quality_score_after,
                    "threshold": config.quality_threshold,
                },
                quality_score=result.quality_score_after,
                validation_rules_applied=["quality_check"],
                passed=passed,
                issues_found=[] if passed else [{
                    "type": "quality_below_threshold",
                    "message": f"质量分数 {result.quality_score_after} 低于阈值 {config.quality_threshold}",
                    "severity": "medium"
                }],
                source=self.config.name,
                data={
                    "task_id": task_id,
                    "config": config.to_dict(),
                    "result_summary": result.to_dict(),
                    "metadata": metadata,
                }
            )
        )

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消清洗任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        return await self._cancel_task(task_id)

    async def _cancel_task(self, task_id: str) -> bool:
        """
        内部方法：取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        if task_id not in self.tasks:
            return False

        task_info = self.tasks[task_id]
        task_info["status"] = CleanTaskStatus.CANCELLED
        task_info["updated_at"] = datetime.now()

        # 如果任务在活跃集合中，标记为取消
        if task_id in self.active_tasks:
            # 通过 asyncio.Task.cancel() 实际中断正在运行的任务
            # _execute_clean_task 的 except CancelledError 处理器会清理状态
            self.active_tasks.discard(task_id)
            bg_task = self._task_refs.pop(task_id, None)
            if bg_task and not bg_task.done():
                bg_task.cancel()
                logger.info(f"已发送取消信号给清洗任务: {task_id}")

        # 发布任务取消事件
        await self._publish_event("clean_task_cancelled", {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"取消清洗任务: {task_id}")
        return True

    async def get_task_result(self, task_id: str) -> Optional[CleanTaskResult]:
        """
        获取任务结果

        Args:
            task_id: 任务ID

        Returns:
            任务结果，如果不存在则返回None
        """
        if task_id not in self.tasks:
            return None

        task_info = self.tasks[task_id]
        return task_info.get("result")

    async def get_engine_status(self) -> Dict[str, Any]:
        """
        获取引擎状态信息（覆盖基类方法）

        Returns:
            引擎状态信息
        """
        base_status = self.record.to_dict()

        # 计算平均处理时间
        avg_time = 0.0
        if self.stats["completed_tasks"] > 0:
            avg_time = self.stats["avg_processing_time"]

        # 添加引擎特定状态
        engine_status = {
            **base_status,
            "tasks": {
                "total": len(self.tasks),
                "active": len(self.active_tasks),
                "pending": self.task_queue.qsize(),
                "completed": self.stats["completed_tasks"],
                "failed": self.stats["failed_tasks"],
            },
            "stats": {
                **self.stats,
                "avg_processing_time": round(avg_time, 2),
            },
            "config": {
                "max_concurrent_tasks": self.max_concurrent_tasks,
                "task_timeout_seconds": self.task_timeout_seconds,
                "default_rules_count": len(self.default_rules),
            },
        }

        return engine_status

    # ==================== 私有辅助方法 ====================

    @staticmethod
    def _create_default_rules() -> Dict[str, CleanRule]:
        """创建默认清洗规则"""
        return {
            "standardize_price": CleanRule(
                name="standardize_price",
                rule_type="standardization",
                parameters={"decimal_places": 2, "unit": "yuan"},
                enabled=True,
                priority=10
            ),
            "handle_missing_price": CleanRule(
                name="handle_missing_price",
                rule_type="missing",
                parameters={"method": "forward_fill", "limit": 5},
                enabled=True,
                priority=20
            ),
            "detect_price_outliers": CleanRule(
                name="detect_price_outliers",
                rule_type="outlier",
                parameters={"method": "iqr", "threshold": 3.0},
                enabled=True,
                priority=30
            ),
            "remove_duplicate_records": CleanRule(
                name="remove_duplicate_records",
                rule_type="duplicate",
                parameters={"subset": ["symbol", "date"], "keep": "first"},
                enabled=True,
                priority=40
            ),
        }

    def _get_default_rules_for_type(self, data_type: str) -> List[CleanRule]:
        """根据数据类型获取默认规则"""
        # 所有数据类型都使用基础规则
        base_rules = ["standardize_price", "remove_duplicate_records"]

        # 根据数据类型添加特定规则
        if data_type == "daily":
            base_rules.extend(["handle_missing_price", "detect_price_outliers"])
        elif data_type in ["1min", "5min", "15min"]:
            base_rules.append("handle_missing_price")

        return [self.default_rules[rule_name] for rule_name in base_rules if rule_name in self.default_rules]

    @staticmethod
    def _get_fix_rules_for_issue(issue_type: str) -> List[CleanRule]:
        """根据问题类型获取修复规则"""
        fix_rules_map = {
            "missing_value": [
                CleanRule(
                    name="fix_missing_values",
                    rule_type="missing",
                    parameters={"method": "interpolate", "limit": 10},
                    enabled=True,
                    priority=100
                )
            ],
            "outlier": [
                CleanRule(
                    name="fix_outliers",
                    rule_type="outlier",
                    parameters={"method": "winsorize", "limits": [0.01, 0.99]},
                    enabled=True,
                    priority=100
                )
            ],
            "duplicate": [
                CleanRule(
                    name="fix_duplicates",
                    rule_type="duplicate",
                    parameters={"subset": None, "keep": "first"},
                    enabled=True,
                    priority=100
                )
            ],
            "inconsistent_format": [
                CleanRule(
                    name="fix_format",
                    rule_type="standardization",
                    parameters={"format_rules": {}},
                    enabled=True,
                    priority=100
                )
            ],
        }

        return fix_rules_map.get(issue_type, [])

    @staticmethod
    async def _should_auto_clean(metadata: MarketDataMetadata) -> bool:
        """判断是否应该自动清洗"""
        # 暂时对所有原始数据都进行清洗
        if metadata.status == DataProcessingStatus.RAW.value:
            return True

        # 如果数据质量评分低于阈值，也需要清洗
        if metadata.quality_score < 80.0:
            return True

        return False

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
        if task_info["status"] in [CleanTaskStatus.CANCELLED, CleanTaskStatus.COMPLETED]:
            return False

        return True

    async def _retry_task(self, task_id: str):
        """重试任务"""
        if task_id not in self.tasks:
            return

        task_info = self.tasks[task_id]
        task_info["retry_count"] += 1
        task_info["status"] = CleanTaskStatus.PENDING
        task_info["updated_at"] = datetime.now()

        # 重新加入队列
        await self.task_queue.put(task_info)

        # 发布任务重试事件
        await self._publish_event("clean_task_retried", {
            "task_id": task_id,
            "retry_count": task_info["retry_count"],
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"重试任务: {task_id} (第{task_info['retry_count']}次)")

    async def _mark_task_failed(self, task_id: str, error_message: str):
        """标记任务失败"""
        if task_id not in self.tasks:
            return

        task_info = self.tasks[task_id]

        task_info["status"] = CleanTaskStatus.FAILED
        task_info["updated_at"] = datetime.now()

        self.stats["failed_tasks"] += 1

        # 发布任务失败事件
        await self._publish_event("clean_task_failed", {
            "task_id": task_id,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        })

        logger.error(f"标记任务失败: {task_id}, 错误: {error_message}")

    async def _cleanup_failed_task(self, task_id: str):
        """清理失败任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.debug(f"清理失败任务: {task_id}")

    async def _update_task_status(self, task_id: str, status: CleanTaskStatus):
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            self.tasks[task_id]["updated_at"] = datetime.now()

    def _generate_task_id(self, data_type: str) -> str:
        """生成任务ID"""
        self.task_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"clean_{data_type}_{timestamp}_{self.task_counter:06d}"

    # ==================== 具体的清洗步骤实现 ====================

    async def _measure_quality_before(self, _task_id: str, config: CleanTaskConfig) -> float:
        """测量清洗前质量"""
        try:
            if not self.quality_service:
                return 0.0

            # 根据数据类型调用质量检查服务
            data_type = config.data_type
            result = await self.quality_service.check_data_quality(data_type)
            
            # 解析质量分数
            if result.get("success", False):
                quality_metrics = result.get("result", {})
                return quality_metrics.get("overall_score", 0.0)
            
            return 0.0
        except Exception as e:
            logger.error(f"测量清洗前质量失败: {e}")
            return 0.0

    async def _validate_input_data(self, task_id: str, config: CleanTaskConfig) -> Dict[str, Any]:
        """验证输入数据 — 通过质量服务进行前置检查"""
        try:
            if not self.clean_service:
                return {"status": "valid", "records_checked": 0, "issues_found": []}

            if self.quality_service:
                quality_result = await self.quality_service.check_data_quality(
                    data_type=config.data_type,
                    start_date=getattr(config, "start_date", None),
                    end_date=getattr(config, "end_date", None),
                    ts_code=getattr(config, "ts_code", None),
                )
                return {
                    "status": "valid" if quality_result.get("success") else "issues_found",
                    "records_checked": quality_result.get("result", {}).get("total_records", 0),
                    "issues_found": quality_result.get("result", {}).get("issues", []),
                    "quality_score": quality_result.get("result", {}).get("overall_score", 0),
                }

            return {"status": "valid", "records_checked": 0, "issues_found": []}
        except Exception as e:
            logger.error(f"输入数据验证失败: {e}")
            return {"status": "error", "records_checked": 0, "issues_found": [], "error": str(e)}
    async def _apply_clean_rule(self, task_id: str, config: CleanTaskConfig, rule: CleanRule) -> Dict[str, Any]:
        """应用清洗规则 — 通过清洗服务执行具体规则"""
        try:
            if not self.clean_service:
                return {"rule": rule.name, "status": "skipped", "records_processed": 0, "changes_made": 0, "errors": ["清洗服务未配置"]}

            # 根据规则类型映射到清洗服务的检查方法
            check_methods = {
                "missing_data": "_check_missing_data",
                "duplicate_data": "_check_duplicate_data",
                "outlier_detection": "_check_outliers",
                "invalid_symbols": "_check_invalid_stock_symbols",
                "missing_info": "_check_missing_stock_info",
            }
            method_name = check_methods.get(rule.rule_type) if hasattr(rule, "rule_type") else None

            if method_name and hasattr(self.clean_service, method_name):
                check_fn = getattr(self.clean_service, method_name)
                issues = await check_fn()
                return {
                    "rule": rule.name,
                    "status": "applied",
                    "records_processed": len(issues) if issues else 0,
                    "changes_made": 0,
                    "issues_found": len(issues) if issues else 0,
                    "errors": [],
                }

            return {
                "rule": rule.name,
                "status": "applied",
                "records_processed": 0,
                "changes_made": 0,
                "errors": [f"规则类型 {getattr(rule, 'rule_type', 'unknown')} 无对应检查方法"],
            }
        except Exception as e:
            logger.error(f"应用清洗规则失败: {e}")
            return {"rule": rule.name, "status": "error", "records_processed": 0, "changes_made": 0, "errors": [str(e)]}
    async def _validate_output_data(self, task_id: str, config: CleanTaskConfig) -> Dict[str, Any]:
        """验证输出数据 — 通过质量服务进行后置检查"""
        try:
            if not self.quality_service:
                return {"status": "valid", "records_checked": 0, "issues_found": []}

            quality_result = await self.quality_service.check_data_quality(
                data_type=config.data_type,
                start_date=getattr(config, "start_date", None),
                end_date=getattr(config, "end_date", None),
                ts_code=getattr(config, "ts_code", None),
            )
            return {
                "status": "valid" if quality_result.get("success") else "issues_found",
                "records_checked": quality_result.get("result", {}).get("total_records", 0),
                "issues_found": quality_result.get("result", {}).get("issues", []),
                "quality_score": quality_result.get("result", {}).get("overall_score", 0),
            }
        except Exception as e:
            logger.error(f"输出数据验证失败: {e}")
            return {"status": "error", "records_checked": 0, "issues_found": [], "error": str(e)}
    async def _save_cleaned_data(self, task_id: str, config: CleanTaskConfig) -> Dict[str, Any]:
        """保存清洗后的数据 — 通过清洗服务应用清洗结果"""
        try:
            if not self.clean_service:
                return {
                    "status": "skipped",
                    "total_records": 0,
                    "cleaned_records": 0,
                    "failed_records": 0,
                    "storage_location": f"cleaned/{config.data_type}",
                }

            apply_result = await self.clean_service.apply_cleaning_results(
                clean_id=task_id,
                apply_rules=[r.name for r in config.rules] if config.rules else None,
                dry_run=False,
            )
            total = apply_result.get("total_issues", 0)
            applied = apply_result.get("applied_count", 0)
            failed = apply_result.get("failed_count", 0)

            await self.clean_service._clean_cache_after_cleaning(config.data_type)

            return {
                "status": "saved",
                "total_records": total,
                "cleaned_records": applied,
                "failed_records": failed,
                "storage_location": f"cleaned/{config.data_type}",
                "apply_id": apply_result.get("apply_id"),
            }
        except Exception as e:
            logger.error(f"保存清洗数据失败: {e}")
            return {
                "status": "error",
                "total_records": 0,
                "cleaned_records": 0,
                "failed_records": 0,
                "storage_location": f"cleaned/{config.data_type}",
                "error": str(e),
            }
    async def _measure_quality_after(self, _task_id: str, config: CleanTaskConfig) -> float:
        """测量清洗后质量"""
        try:
            if not self.quality_service:
                return 0.0

            # 根据数据类型调用质量检查服务
            data_type = config.data_type
            result = await self.quality_service.check_data_quality(data_type)
            
            # 解析质量分数
            if result.get("success", False):
                quality_metrics = result.get("result", {})
                return quality_metrics.get("overall_score", 0.0)
            
            return 0.0
        except Exception as e:
            logger.error(f"测量清洗后质量失败: {e}")
            return 0.0


# ==================== 引擎描述符注册 ====================

def register_data_clean_engine(factory):
    """
    注册数据清洗引擎到引擎工厂

    Args:
        factory: 引擎工厂实例
    """
    # 创建引擎描述符
    descriptor = EngineDescriptor(
        engine_type=EngineType.DATA_CLEAN,
        engine_class=DataCleanEngine,
        name="data_clean_engine",
        description="数据清洗引擎，负责管理数据清洗和质量提升的完整流程",
        version="1.0.0",
        category=EngineCategory.DATA,
        dependencies=[
            EngineType.EVENT,  # 依赖事件引擎
        ],
        config_schema={
            "required": [],
            "default": {
                "max_concurrent_tasks": 2,
                "task_timeout_seconds": 1800,
                "auto_start": True,
                "max_retries": 3,
                "health_check_interval": 60,
                "graceful_shutdown_timeout": 30
            }
        },
        tags=["data", "cleaning", "quality", "processing"]
    )

    # 注册引擎
    try:
        factory.register_engine(descriptor)
        logger.info(f"数据清洗引擎已注册: {descriptor.name}")
    except ValueError as e:
        logger.warning(f"数据清洗引擎注册失败: {e}")


# ==================== 便捷函数 ====================

async def create_data_clean_engine(
    config: Optional[Dict[str, Any]] = None,
    instance_name: Optional[str] = None,
    clean_service: Optional[DataCleanService] = None,
    quality_service: Optional[DataQualityService] = None
) -> DataCleanEngine:
    """
    创建数据清洗引擎（便捷函数）

    Args:
        config: 引擎配置
        instance_name: 实例名称
        clean_service: 数据清洗服务
        quality_service: 数据质量服务

    Returns:
        数据清洗引擎实例
    """
    from core.engines.utils.engine_factory import create_engine

    # 创建引擎
    engine = await create_engine(
        engine_type=EngineType.DATA_CLEAN,
        config=config,
        instance_name=instance_name
    )

    # 设置服务依赖
    if clean_service:
        engine.clean_service = clean_service

    if quality_service:
        engine.quality_service = quality_service

    return engine  # type: ignore[return-value]


async def get_data_clean_engine(instance_name: str = "data_clean_engine") -> Optional[DataCleanEngine]:
    """
    获取数据清洗引擎实例（便捷函数）

    Args:
        instance_name: 实例名称

    Returns:
        数据清洗引擎实例，如果不存在则返回None
    """
    from core.engines.utils.engine_factory import get_engine

    engine = await get_engine(instance_name)
    if engine and isinstance(engine, DataCleanEngine):
        return engine

    return None


# 导出
__all__ = [
    "DataCleanEngine",
    "CleanStep",
    "CleanTaskStatus",
    "CleanRule",
    "CleanTaskConfig",
    "CleanTaskProgress",
    "CleanTaskResult",
    "register_data_clean_engine",
    "create_data_clean_engine",
    "get_data_clean_engine"
]