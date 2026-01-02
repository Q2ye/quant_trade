"""
引擎基类
提供所有引擎的统一生命周期管理、状态监控和资源管理基础框架

设计原则：
1. 统一的生命周期管理（start/stop/restart）
2. 标准化的状态管理（状态枚举、转换验证）
3. 依赖注入和依赖管理
4. 事件驱动的内部通信
5. 统一的错误处理和恢复机制
6. 标准化的监控接口

所有业务引擎（策略引擎、交易引擎、回测引擎等）都必须继承自此基类。
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, replace
from datetime import datetime
from contextlib import asynccontextmanager

# 导入统一类型定义
from ..types.entities import (
    EngineConfig as EngineConfigEntity,
    EngineMetrics as EngineMetricsEntity
)
from ..types.enums import (
    ComponentStatus,
    HealthStatus,
    PriorityLevel,
    EngineType,
    EngineErrorLevel
)

logger = logging.getLogger(__name__)


class EngineStatusValidator:
    """引擎状态验证器"""

    # 有效的状态转换
    _VALID_TRANSITIONS = {
        ComponentStatus.UNINITIALIZED: [ComponentStatus.INITIALIZING],
        ComponentStatus.INITIALIZING: [ComponentStatus.INITIALIZED, ComponentStatus.ERROR],
        ComponentStatus.INITIALIZED: [ComponentStatus.STARTING, ComponentStatus.STOPPED],
        ComponentStatus.STARTING: [ComponentStatus.RUNNING, ComponentStatus.ERROR],
        ComponentStatus.RUNNING: [ComponentStatus.STOPPING, ComponentStatus.ERROR, ComponentStatus.DEGRADED],
        ComponentStatus.STOPPING: [ComponentStatus.STOPPED, ComponentStatus.ERROR],
        ComponentStatus.STOPPED: [ComponentStatus.STARTING, ComponentStatus.UNINITIALIZED],
        ComponentStatus.ERROR: [ComponentStatus.STOPPED, ComponentStatus.STARTING],
        ComponentStatus.DEGRADED: [ComponentStatus.RUNNING, ComponentStatus.STOPPING, ComponentStatus.ERROR]
    }

    @staticmethod
    def is_valid_transition(current: ComponentStatus, next_status: ComponentStatus) -> bool:
        """检查状态转换是否有效

        Args:
            current: 当前状态
            next_status: 下一个状态

        Returns:
            bool: 转换是否有效
        """
        valid_transitions = EngineStatusValidator._VALID_TRANSITIONS.get(current, [])
        return next_status in valid_transitions


@dataclass
class EngineRecord:
    """引擎状态记录"""

    engine_id: str
    engine_name: str
    engine_type: EngineType
    status: ComponentStatus
    health: HealthStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    error_level: Optional[EngineErrorLevel] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def update_status(self, status: ComponentStatus, message: str = ""):
        """更新状态

        Args:
            status: 新状态
            message: 状态更新消息
        """
        self.status = status
        self.updated_at = datetime.now()
        self.metadata["last_status_change"] = {
            "timestamp": self.updated_at.isoformat(),
            "message": message
        }

    def update_health(self, health: HealthStatus, reason: str = ""):
        """更新健康状态

        Args:
            health: 新健康状态
            reason: 原因描述
        """
        self.health = health
        self.updated_at = datetime.now()
        self.metadata["last_health_change"] = {
            "timestamp": self.updated_at.isoformat(),
            "reason": reason
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "engine_id": self.engine_id,
            "engine_name": self.engine_name,
            "engine_type": self.engine_type.value,
            "status": self.status.value,
            "health": self.health.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_message": self.error_message,
            "error_level": self.error_level.value if self.error_level else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "uptime": self.get_uptime()
        }

    def get_uptime(self) -> float:
        """获取运行时长（秒）

        Returns:
            float: 运行时长（秒），未运行则为0
        """
        if self.start_time:
            if self.end_time:
                return (self.end_time - self.start_time).total_seconds()
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0


class EngineBase(ABC):
    """引擎基类 - 统一生命周期管理

    所有引擎的抽象基类，提供统一的生命周期管理、状态监控、依赖管理、
    错误处理和性能指标收集功能。

    设计模式：模板方法模式 + 观察者模式 + 状态模式

    Attributes:
        engine_id: 引擎唯一标识
        config: 引擎配置实体
        record: 引擎状态记录
        metrics: 性能指标实体
        dependencies: 依赖的引擎实例映射
        event_engine: 事件引擎引用
        monitoring_task: 监控任务句柄
    """

    def __init__(self, config: EngineConfigEntity, event_engine=None):
        """初始化引擎基类

        Args:
            config: 引擎配置实体
            event_engine: 事件引擎实例，用于发布引擎事件
        """
        # 生成唯一标识
        self.engine_id = f"{config.name}_{uuid.uuid4().hex[:8]}"

        # 核心属性
        self.config = config
        self.event_engine = event_engine

        # 状态管理
        self.record = EngineRecord(
            engine_id=self.engine_id,
            engine_name=config.name,
            engine_type=EngineType.CUSTOM,  # 子类需要设置具体类型
            status=ComponentStatus.UNINITIALIZED,
            health=HealthStatus.UNKNOWN
        )

        # 性能指标
        self.metrics = EngineMetricsEntity()

        # 依赖管理
        self.dependencies: Dict[str, 'EngineBase'] = {}

        # 异步任务管理
        self.monitoring_task: Optional[asyncio.Task] = None
        self.lock = asyncio.Lock()
        self.shutdown_event = asyncio.Event()

        logger.info(f"引擎初始化完成: {self.config.name} ({self.engine_id})")

    async def start(self) -> bool:
        """启动引擎

        完整的启动流程，包括依赖检查、状态转换、资源初始化和监控启动。
        支持自动重试机制，基于配置的重试策略。

        Returns:
            bool: 启动是否成功

        Raises:
            RuntimeError: 当引擎已经运行或依赖检查失败时
            Exception: 启动过程中发生的任何异常
        """
        async with self.lock:
            # 检查当前状态
            if self.record.status == ComponentStatus.RUNNING:
                logger.warning(f"引擎已在运行中: {self.config.name}")
                return True

            # 验证状态转换
            if not EngineStatusValidator.is_valid_transition(
                self.record.status, ComponentStatus.STARTING
            ):
                raise RuntimeError(
                    f"无效的状态转换: {self.record.status} -> STARTING"
                )

            # 更新状态
            self.record.update_status(ComponentStatus.STARTING, "开始启动引擎")
            logger.info(f"启动引擎: {self.config.name}")

            # 启动重试逻辑
            for attempt in range(self.config.max_retries + 1):
                try:
                    # 检查依赖
                    self._check_dependencies()

                    # 执行引擎特定的启动逻辑
                    await self._on_start()

                    # 记录启动时间
                    self.record.start_time = datetime.now()

                    # 更新状态
                    self.record.update_status(ComponentStatus.RUNNING, "引擎启动成功")
                    self.record.update_health(HealthStatus.HEALTHY, "启动成功")
                    self.record.error_message = None
                    self.record.error_level = None

                    # 启动监控任务
                    self.monitoring_task = asyncio.create_task(
                        self._monitoring_loop(),
                        name=f"engine_monitor_{self.config.name}"
                    )

                    # 发布启动事件
                    await self._publish_event("engine_started", {
                        "engine_id": self.engine_id,
                        "engine_name": self.config.name,
                        "start_time": self.record.start_time.isoformat(),
                        "config": self.config.to_dict()
                    })

                    logger.info(f"引擎启动成功: {self.config.name}")
                    return True

                except Exception as e:
                    self.record.error_message = str(e)
                    self.record.error_level = EngineErrorLevel.ERROR

                    if attempt < self.config.max_retries:
                        wait_time = self.config.retry_delay * (2 ** attempt)  # 指数退避
                        logger.warning(
                            f"引擎启动失败，将在 {wait_time:.1f} 秒后重试 "
                            f"({attempt + 1}/{self.config.max_retries}): {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        # 超过最大重试次数，标记为错误状态
                        self.record.update_status(ComponentStatus.ERROR, f"启动失败: {e}")
                        self.record.update_health(HealthStatus.FAILED, f"启动失败: {e}")

                        # 发布错误事件
                        await self._publish_event("engine_start_failed", {
                            "engine_id": self.engine_id,
                            "engine_name": self.config.name,
                            "error": str(e),
                            "attempts": attempt + 1
                        })

                        logger.error(f"引擎启动失败，超过最大重试次数: {self.config.name}, 错误: {e}")
                        raise

            return False

    async def stop(self, force: bool = False) -> bool:
        """停止引擎

        优雅停止引擎，首先尝试优雅停止，如果超时则强制停止。

        Args:
            force: 是否强制停止（跳过优雅停止）

        Returns:
            bool: 停止是否成功

        Raises:
            RuntimeError: 停止过程中发生错误
        """
        async with self.lock:
            # 检查当前状态
            if self.record.status == ComponentStatus.STOPPED:
                logger.info(f"引擎已经停止: {self.config.name}")
                return True

            # 验证状态转换（错误状态可以直接停止）
            if (self.record.status != ComponentStatus.ERROR and
                not EngineStatusValidator.is_valid_transition(
                    self.record.status, ComponentStatus.STOPPING
                )):
                raise RuntimeError(
                    f"无效的状态转换: {self.record.status} -> STOPPING"
                )

            # 更新状态
            previous_status = self.record.status
            self.record.update_status(ComponentStatus.STOPPING, "开始停止引擎")
            logger.info(f"停止引擎: {self.config.name}")

            try:
                # 停止监控任务
                if self.monitoring_task:
                    self.monitoring_task.cancel()
                    try:
                        await self.monitoring_task
                    except asyncio.CancelledError:
                        # 任务被取消是正常情况，重新抛出异常
                        raise
                    finally:
                        self.monitoring_task = None

                # 设置关闭事件
                self.shutdown_event.set()

                # 执行引擎特定的停止逻辑
                await self._on_stop()

                # 更新状态
                self.record.update_status(ComponentStatus.STOPPED, "引擎停止成功")
                self.record.end_time = datetime.now()

                # 计算运行时长
                uptime = self.record.get_uptime()

                # 更新指标 - 使用replace创建新实例
                self.metrics = replace(self.metrics, uptime=uptime)

                # 发布停止事件
                await self._publish_event("engine_stopped", {
                    "engine_id": self.engine_id,
                    "engine_name": self.config.name,
                    "previous_status": previous_status.value,
                    "uptime": uptime,
                    "end_time": self.record.end_time.isoformat(),
                    "metrics": self.metrics.to_dict()
                })

                logger.info(f"引擎停止成功: {self.config.name}, 运行时长: {uptime:.1f}秒")
                return True

            except Exception as e:
                self.record.update_status(ComponentStatus.ERROR, f"停止失败: {e}")
                self.record.update_health(HealthStatus.FAILED, f"停止失败: {e}")
                self.record.error_message = str(e)
                self.record.error_level = EngineErrorLevel.ERROR

                # 发布错误事件
                await self._publish_event("engine_stop_failed", {
                    "engine_id": self.engine_id,
                    "engine_name": self.config.name,
                    "error": str(e)
                })

                logger.error(f"引擎停止失败: {self.config.name}, 错误: {e}")
                raise

    async def restart(self) -> bool:
        """重启引擎

        先停止再启动，提供原子性的重启操作。

        Returns:
            bool: 重启是否成功
        """
        logger.info(f"重启引擎: {self.config.name}")

        try:
            # 先停止引擎
            await self.stop()

            # 重置关闭事件
            self.shutdown_event.clear()

            # 重置结束时间
            self.record.end_time = None

            # 再启动引擎
            return await self.start()

        except Exception as e:
            logger.error(f"引擎重启失败: {self.config.name}, 错误: {e}")
            raise

    def add_dependency(self, engine: 'EngineBase'):
        """添加引擎依赖

        Args:
            engine: 依赖的引擎实例
        """
        if engine.config.name in self.dependencies:
            logger.warning(f"引擎依赖已存在: {self.config.name} -> {engine.config.name}")
            return

        self.dependencies[engine.config.name] = engine
        logger.debug(f"添加引擎依赖: {self.config.name} -> {engine.config.name}")

    def remove_dependency(self, engine_name: str):
        """移除引擎依赖

        Args:
            engine_name: 依赖的引擎名称
        """
        if engine_name in self.dependencies:
            del self.dependencies[engine_name]
            logger.debug(f"移除引擎依赖: {self.config.name} -> {engine_name}")

    async def health_check(self) -> Dict[str, Any]:
        """执行健康检查

        检查引擎的健康状态，返回详细的健康信息。

        Returns:
            Dict[str, Any]: 健康检查结果，包括状态、指标和详细信息
        """
        health_info = {
            "engine_id": self.engine_id,
            "engine_name": self.config.name,
            "status": self.record.status.value,
            "health": self.record.health.value,
            "uptime": self.record.get_uptime(),
            "error_message": self.record.error_message,
            "error_level": self.record.error_level.value if self.record.error_level else None,
            "dependencies": list(self.dependencies.keys()),
            "metrics": self.metrics.to_dict(),
            "timestamp": datetime.now().isoformat()
        }

        # 检查依赖的健康状态
        dependency_health = {}
        for dep_name, dep_engine in self.dependencies.items():
            try:
                dep_health = await dep_engine.health_check()
                dependency_health[dep_name] = dep_health

                # 如果依赖不健康，本引擎也可能降级
                if (dep_health["health"] in [HealthStatus.UNHEALTHY.value, HealthStatus.FAILED.value] and
                    self.record.health == HealthStatus.HEALTHY):
                    self.record.update_health(HealthStatus.DEGRADED, f"依赖 {dep_name} 不健康")
                    health_info["health"] = HealthStatus.DEGRADED.value
            except Exception as e:
                dependency_health[dep_name] = {"error": str(e)}
                logger.warning(f"检查依赖健康状态失败: {dep_name}, 错误: {e}")

        health_info["dependency_health"] = dependency_health

        return health_info

    @abstractmethod
    async def _on_start(self):
        """引擎启动时的具体逻辑

        子类必须实现此方法，包含引擎特定的启动逻辑。
        例如：初始化资源、建立连接、启动内部循环等。
        """
        pass

    @abstractmethod
    async def _on_stop(self):
        """引擎停止时的具体逻辑

        子类必须实现此方法，包含引擎特定的停止逻辑。
        例如：释放资源、断开连接、清理临时数据等。
        """
        pass

    def _check_dependencies(self):
        """检查引擎依赖

        确保所有依赖的引擎都处于运行状态。
        如果依赖不满足，抛出异常。
        """
        missing_deps = []
        unhealthy_deps = []

        for dep_name in self.config.dependencies:
            if dep_name not in self.dependencies:
                missing_deps.append(dep_name)
                continue

            dep_engine = self.dependencies[dep_name]
            if dep_engine.record.status != ComponentStatus.RUNNING:
                unhealthy_deps.append(f"{dep_name}({dep_engine.record.status.value})")

        if missing_deps:
            raise RuntimeError(f"缺少依赖的引擎: {missing_deps}")

        if unhealthy_deps:
            raise RuntimeError(f"依赖引擎未运行: {unhealthy_deps}")

    async def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """发布事件到事件引擎

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if self.event_engine:
            try:
                from ..types.entities import Event

                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=event_type,
                    source=f"engine:{self.config.name}",
                    data=data,
                    priority=PriorityLevel.NORMAL.value
                )

                await self.event_engine.put(event)

                # 更新指标 - 使用replace创建新实例
                self.metrics = replace(
                    self.metrics,
                    processed_events=self.metrics.processed_events + 1,
                    last_success_time=datetime.now()
                )

            except Exception as e:
                logger.error(f"发布事件失败: {self.config.name}, 错误: {e}")
                self.metrics = replace(
                    self.metrics,
                    error_count=self.metrics.error_count + 1,
                    last_error_time=datetime.now()
                )

    async def _monitoring_loop(self):
        """监控循环

        定期执行健康检查和指标收集。
        在引擎停止时自动退出。
        """
        logger.debug(f"启动引擎监控循环: {self.config.name}")

        try:
            while self.record.status == ComponentStatus.RUNNING:
                try:
                    # 执行健康检查
                    health_info = await self.health_check()

                    # 发布健康状态事件
                    await self._publish_event("engine_health_check", health_info)

                    # 收集性能指标
                    await self._collect_metrics()

                    # 等待下次检查
                    await asyncio.sleep(self.config.health_check_interval)

                except asyncio.CancelledError:
                    # 任务被取消，正常退出，重新抛出异常
                    raise
                except Exception as e:
                    logger.error(f"监控循环异常: {self.config.name}, 错误: {e}")
                    await asyncio.sleep(self.config.health_check_interval)

        except asyncio.CancelledError:
            # 任务被取消是正常的，重新抛出异常
            raise
        except Exception as e:
            logger.error(f"监控循环意外退出: {self.config.name}, 错误: {e}")

    async def _collect_metrics(self):
        """收集性能指标

        子类可以重写此方法以收集特定指标。
        基类收集通用指标（如内存、CPU使用率）。
        """
        try:
            import psutil
            import os

            # 收集内存使用情况
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            # 收集CPU使用率
            cpu_percent = process.cpu_percent(interval=0.1)

            # 使用replace更新指标
            self.metrics = replace(
                self.metrics,
                memory_usage_mb=memory_info.rss / 1024 / 1024,  # 转换为MB
                cpu_percent=cpu_percent
            )

        except ImportError:
            # psutil不可用，跳过指标收集
            logger.debug("psutil未安装，跳过系统指标收集")
        except asyncio.CancelledError:
            # 任务被取消，重新抛出异常
            raise
        except Exception as e:
            logger.debug(f"收集指标失败: {self.config.name}, 错误: {e}")

    def get_status_info(self) -> Dict[str, Any]:
        """获取引擎状态信息

        Returns:
            Dict[str, Any]: 包含引擎完整状态信息的字典
        """
        return {
            "engine_id": self.engine_id,
            "engine_name": self.config.name,
            "engine_type": self.record.engine_type.value,
            "status": self.record.status.value,
            "health": self.record.health.value,
            "start_time": self.record.start_time.isoformat() if self.record.start_time else None,
            "end_time": self.record.end_time.isoformat() if self.record.end_time else None,
            "uptime": self.record.get_uptime(),
            "error_message": self.record.error_message,
            "error_level": self.record.error_level.value if self.record.error_level else None,
            "dependencies": list(self.dependencies.keys()),
            "metrics": self.metrics.to_dict(),
            "config": self.config.to_dict()
        }

    @asynccontextmanager
    async def safe_context(self):
        """安全上下文管理器

        确保在引擎运行状态下执行代码块，如果引擎停止则取消执行。

        Example:
            async with engine.safe_context():
                # 在这里执行需要引擎运行状态的操作
                await engine.process_data(events)
        """
        if self.record.status != ComponentStatus.RUNNING:
            raise RuntimeError(
                f"引擎未运行: {self.config.name}, 当前状态: {self.record.status.value}"
            )

        try:
            yield self
        except asyncio.CancelledError:
            # 如果引擎正在关闭，任务被取消是正常的
            if self.shutdown_event.is_set():
                logger.debug(f"引擎上下文被优雅取消: {self.config.name}")
                raise
            else:
                logger.warning(f"引擎上下文意外取消: {self.config.name}")
                raise
        except Exception as e:
            logger.error(f"引擎上下文执行异常: {self.config.name}, 错误: {e}")
            raise

    def __str__(self) -> str:
        """字符串表示

        Returns:
            str: 引擎的字符串表示
        """
        return (f"Engine({self.config.name}, "
                f"id={self.engine_id[:8]}, "
                f"status={self.record.status.value}, "
                f"health={self.record.health.value})")

    def __repr__(self) -> str:
        """详细表示

        Returns:
            str: 引擎的详细表示
        """
        return (f"EngineBase(name='{self.config.name}', "
                f"id='{self.engine_id}', "
                f"status={self.record.status}, "
                f"start_time={self.record.start_time})")