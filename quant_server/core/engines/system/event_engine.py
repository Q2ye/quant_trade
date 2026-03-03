"""
事件引擎
系统的消息总线和事件驱动框架，负责事件的发布、订阅、路由和处理

核心功能：
1. 异步事件队列管理和优先级调度
2. 事件类型注册和处理器管理
3. 事件广播和多播支持
4. 事件历史记录和重放
5. 事件性能监控和统计

事件引擎是系统的"神经系统"，连接所有组件并协调它们的通信。
"""

import asyncio
import logging
import heapq
import time
import uuid
from typing import Dict, Any, List, Optional, Callable, Deque
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque

# 导入统一类型定义
from ..types.entities import Event as EventEntity
from ..types.enums import (
    ComponentStatus,
    PriorityLevel,
    EngineType
)

# 导入引擎基类
from ..base.engine_base import EngineBase, EngineConfigEntity

logger = logging.getLogger(__name__)


@dataclass(order=True)
class QueuedEvent:
    """队列事件（用于优先级队列）"""

    priority: str  # 优先级
    timestamp: float  # 入队时间戳（用于相同优先级排序）
    event: EventEntity = field(compare=False)  # 事件对象（不参与排序）

    def __init__(self, event: EventEntity):
        """初始化队列事件

        Args:
            event: 事件对象
        """
        self.priority = event.priority if hasattr(event, 'priority') else PriorityLevel.NORMAL.value
        self.timestamp = time.time()
        self.event = event


@dataclass
class EventHandler:
    """事件处理器包装"""

    handler_id: str  # 处理器ID
    event_type: str  # 事件类型
    handler: Callable  # 处理器函数
    is_async: bool  # 是否为异步函数
    priority: int = PriorityLevel.NORMAL.value  # 处理器优先级
    enabled: bool = True  # 是否启用
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    call_count: int = 0  # 调用次数
    last_called: Optional[datetime] = None  # 最后调用时间

    async def call(self, event: EventEntity) -> Any:
        """调用处理器

        Args:
            event: 事件对象

        Returns:
            Any: 处理器返回值

        Raises:
            Exception: 处理器执行异常
        """
        if not self.enabled:
            return None

        try:
            self.call_count += 1
            self.last_called = datetime.now()

            if self.is_async:
                return await self.handler(event)
            else:
                # 在事件循环中执行同步函数
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.handler, event)

        except Exception as e:
            logger.error(f"事件处理器执行失败: {self.handler_id}, 事件: {event.event_type}, 错误: {e}")
            raise


@dataclass
class EventStatistics:
    """事件统计"""

    total_events: int = 0  # 总事件数
    processed_events: int = 0  # 已处理事件数
    failed_events: int = 0  # 处理失败事件数
    avg_processing_time_ms: float = 0.0  # 平均处理时间（毫秒）
    max_queue_size: int = 0  # 最大队列大小
    current_queue_size: int = 0  # 当前队列大小
    event_type_counts: Dict[str, int] = field(default_factory=dict)  # 事件类型统计
    handler_counts: Dict[str, int] = field(default_factory=dict)  # 处理器统计
    last_reset_time: datetime = field(default_factory=datetime.now)  # 上次重置时间

    def reset(self) -> None:
        """重置统计"""
        self.total_events = 0
        self.processed_events = 0
        self.failed_events = 0
        self.avg_processing_time_ms = 0.0
        self.max_queue_size = 0
        self.current_queue_size = 0
        self.event_type_counts.clear()
        self.handler_counts.clear()
        self.last_reset_time = datetime.now()


class EventEngine(EngineBase):

    """事件引擎

    异步事件驱动引擎，支持优先级队列、事件广播、处理器管理和性能监控。
    采用多消费者模式，提高事件处理并发能力。

    Attributes:
        _event_queue: 事件优先级队列
        _event_handlers: 事件处理器映射 {event_type: List[EventHandler]}
        _general_handlers: 通用处理器列表
        _event_history: 事件历史记录
        _event_statistics: 事件统计
        _worker_tasks: 工作器任务列表
        _is_processing: 是否正在处理事件
        _queue_lock: 队列锁
        _handler_lock: 处理器锁
        _max_queue_size: 最大队列大小
        _max_workers: 最大工作器数量
        _worker_semaphore: 工作器信号量
        _timers: 定时器字典
    """

    def __init__(self, config: EngineConfigEntity, event_engine=None):
        """初始化事件引擎

        Args:
            config: 引擎配置实体
            event_engine: 父事件引擎（用于嵌套事件引擎）
        """
        super().__init__(config, event_engine)

        # 设置引擎类型
        self.record.engine_type = EngineType.EVENT

        # 事件队列
        self._event_queue: List[QueuedEvent] = []  # 堆队列
        self._queue_lock = asyncio.Lock()

        # 事件处理器
        self._event_handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._general_handlers: List[EventHandler] = []
        self._handler_lock = asyncio.Lock()

        # 事件历史
        self._event_history: Deque[EventEntity] = deque(maxlen=10000)  # 最多保存10000个事件
        self._event_statistics = EventStatistics()

        # 工作器配置
        self._worker_tasks: List[asyncio.Task] = []
        self._is_processing = False
        self._max_workers = config.config.get("max_workers", 10)
        self._max_queue_size = config.config.get("queue_size", 10000)
        self._worker_semaphore = asyncio.Semaphore(self._max_workers)

        # 定时器
        self._timers: Dict[str, asyncio.Task] = {}

        logger.info(f"事件引擎初始化完成，最大工作器: {self._max_workers}, 最大队列: {self._max_queue_size}")

    async def _on_initialize(self):
        """事件引擎初始化逻辑"""
        logger.info("初始化事件引擎组件")

    async def _on_start(self) -> None:
        """事件引擎启动逻辑"""
        logger.info("启动事件引擎")

        try:
            # 启动工作器
            await self._start_workers()

            # 启动统计定时器
            self._start_statistics_timer()

            logger.info(f"事件引擎启动完成，工作器数量: {self._max_workers}")

        except Exception as e:
            logger.error(f"事件引擎启动失败: {e}")
            raise

    async def _on_stop(self) -> None:
        """事件引擎停止逻辑"""
        logger.info("停止事件引擎")

        try:
            # 停止统计定时器
            self._stop_statistics_timer()

            # 停止所有定时器
            await self._stop_all_timers()

            # 停止工作器
            await self._stop_workers()

            # 清空队列
            await self._clear_queue()

            # 清理处理器
            await self._clear_handlers()

            logger.info("事件引擎停止完成")

        except Exception as e:
            logger.error(f"事件引擎停止失败: {e}")
            raise

    async def _start_workers(self) -> None:
        """启动工作器"""
        self._is_processing = True

        for i in range(self._max_workers):
            worker_task = asyncio.create_task(
                self._worker_loop(),
                name=f"EventWorker-{i}"
            )
            self._worker_tasks.append(worker_task)

        logger.debug(f"启动了 {self._max_workers} 个工作器")

    async def _stop_workers(self) -> None:
        """停止工作器"""
        self._is_processing = False

        # 取消所有工作器任务
        for task in self._worker_tasks:
            task.cancel()

        # 等待所有任务完成
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks.clear()

        logger.debug("所有工作器已停止")

    async def _clear_queue(self) -> None:
        """清空队列"""
        async with self._queue_lock:
            self._event_queue.clear()
            self._event_statistics.current_queue_size = 0

        logger.debug("事件队列已清空")

    async def _clear_handlers(self) -> None:
        """清理处理器"""
        async with self._handler_lock:
            self._event_handlers.clear()
            self._general_handlers.clear()

        logger.debug("事件处理器已清理")

    def _start_statistics_timer(self) -> None:
        """启动统计定时器"""
        # 每60秒更新一次统计
        self._create_timer(
            60.0,
            self._update_statistics,
            name="statistics_timer"
        )

        logger.debug("统计定时器已启动: statistics_timer")

    def _stop_statistics_timer(self) -> None:
        """停止统计定时器"""
        self._cancel_timer("statistics_timer")

    async def _worker_loop(self) -> None:
        """工作器循环"""
        worker_name = asyncio.current_task().get_name() if asyncio.current_task() else "UnknownWorker"
        logger.debug(f"工作器启动: {worker_name}")

        try:
            while self._is_processing:
                try:
                    # 获取事件（带超时）
                    event = await self._get_event(timeout=1.0)
                    if event:
                        # 处理事件
                        await self._process_event(event)

                except asyncio.CancelledError:
                    # 任务被取消，正常退出
                    break
                except Exception as e:
                    logger.error(f"工作器异常: {worker_name}, 错误: {e}")
                    await asyncio.sleep(0.1)  # 短暂休眠避免CPU占用过高

        except Exception as e:
            logger.error(f"工作器意外退出: {worker_name}, 错误: {e}")
        finally:
            logger.debug(f"工作器停止: {worker_name}")

    async def _get_event(self, timeout: float = 1.0) -> Optional[EventEntity]:
        """获取事件

        Args:
            timeout: 超时时间（秒）

        Returns:
            Optional[EventEntity]: 事件对象，超时返回None
        """
        start_time = time.time()

        while self._is_processing:
            async with self._queue_lock:
                # 检查队列是否为空
                if self._event_queue:
                    # 从堆中弹出优先级最高的事件
                    queued_event = heapq.heappop(self._event_queue)
                    self._event_statistics.current_queue_size = len(self._event_queue)

                    return queued_event.event

            # 检查是否超时
            if time.time() - start_time >= timeout:
                return None

            # 短暂休眠避免CPU占用过高
            await asyncio.sleep(0.01)

        return None

    async def _process_event(self, event: EventEntity) -> None:
        """处理事件

        Args:
            event: 事件对象
        """
        start_time = time.time()

        try:
            # 更新统计
            self._event_statistics.total_events += 1
            self._event_statistics.event_type_counts[event.event_type] = \
                self._event_statistics.event_type_counts.get(event.event_type, 0) + 1

            # 保存到历史
            self._event_history.append(event)

            # 获取事件处理器
            handlers = []
            async with self._handler_lock:
                # 获取特定类型的处理器
                if event.event_type in self._event_handlers:
                    handlers.extend(self._event_handlers[event.event_type])

                # 获取通用处理器
                handlers.extend(self._general_handlers)

            # 按优先级排序处理器
            handlers.sort(key=lambda h: h.priority, reverse=True)

            # 执行处理器
            if handlers:
                handler_tasks = []
                for handler in handlers:
                    handler_tasks.append(handler.call(event))

                # 并行执行处理器
                results = await asyncio.gather(*handler_tasks, return_exceptions=True)

                # 统计处理器调用
                for handler in handlers:
                    self._event_statistics.handler_counts[handler.handler_id] = \
                        self._event_statistics.handler_counts.get(handler.handler_id, 0) + 1

                # 检查是否有处理器失败
                failed_count = sum(1 for r in results if isinstance(r, Exception))
                if failed_count > 0:
                    self._event_statistics.failed_events += 1
                    logger.warning(f"事件处理有 {failed_count} 个处理器失败: {event.event_type}")

            # 更新统计
            processing_time = (time.time() - start_time) * 1000  # 转换为毫秒

            # 计算移动平均
            if self._event_statistics.processed_events == 0:
                self._event_statistics.avg_processing_time_ms = processing_time
            else:
                alpha = 0.1  # 平滑因子
                self._event_statistics.avg_processing_time_ms = \
                    alpha * processing_time + (1 - alpha) * self._event_statistics.avg_processing_time_ms

            self._event_statistics.processed_events += 1

            # 记录处理时间（如果超过阈值）
            if processing_time > 100:  # 超过100毫秒
                logger.debug(f"事件处理时间较长: {event.event_type}, 耗时: {processing_time:.1f}ms")

        except Exception as e:
            self._event_statistics.failed_events += 1
            logger.error(f"事件处理失败: {event.event_type}, 错误: {e}")

    async def put(self, event: EventEntity) -> None:
        """放入事件

        Args:
            event: 事件对象

        Raises:
            RuntimeError: 队列已满或引擎未运行
        """
        if self.record.status != ComponentStatus.RUNNING:
            raise RuntimeError("事件引擎未运行")

        async with self._queue_lock:
            # 检查队列大小
            if len(self._event_queue) >= self._max_queue_size:
                raise RuntimeError(f"事件队列已满: {self._max_queue_size}")

            # 创建队列事件
            queued_event = QueuedEvent(event)

            # 添加到优先级队列
            heapq.heappush(self._event_queue, queued_event)

            # 更新统计
            self._event_statistics.current_queue_size = len(self._event_queue)
            self._event_statistics.max_queue_size = max(
                self._event_statistics.max_queue_size,
                self._event_statistics.current_queue_size
            )

        logger.debug(f"事件入队: {event.event_type}, 优先级: {event.priority}")

    def register(self,
                 event_type: str,
                 handler: Callable,
                 priority: int = PriorityLevel.NORMAL.value,
                 handler_id: Optional[str] = None) -> str:
        """注册事件处理器

        Args:
            event_type: 事件类型
            handler: 处理器函数
            priority: 处理器优先级
            handler_id: 处理器ID（可选，自动生成）

        Returns:
            str: 处理器ID

        Raises:
            ValueError: 参数无效
        """
        if not callable(handler):
            raise ValueError("处理器必须是可调用对象")

        if not handler_id:
            handler_id = f"handler_{uuid.uuid4().hex[:8]}"

        # 检查是否为异步函数
        is_async = asyncio.iscoroutinefunction(handler)

        # 创建处理器包装
        handler_wrapper = EventHandler(
            handler_id=handler_id,
            event_type=event_type,
            handler=handler,
            is_async=is_async,
            priority=priority
        )

        async def _register() -> None:
            async with self._handler_lock:
                self._event_handlers[event_type].append(handler_wrapper)

        # 异步注册
        asyncio.create_task(_register())

        logger.debug(f"注册事件处理器: {event_type} -> {handler_id} (priority={priority})")

        return handler_id

    def unregister(self, event_type: str, handler_id: str) -> bool:
        """注销事件处理器

        Args:
            event_type: 事件类型
            handler_id: 处理器ID

        Returns:
            bool: 注销是否成功
        """
        async def _unregister() -> bool:
            async with self._handler_lock:
                if event_type in self._event_handlers:
                    handlers = self._event_handlers[event_type]

                    # 查找处理器
                    for i, handler in enumerate(handlers):
                        if handler.handler_id == handler_id:
                            handlers.pop(i)
                            logger.debug(f"注销事件处理器: {event_type} -> {handler_id}")
                            return True

            return False

        # 异步注销
        asyncio.create_task(_unregister())

        return True

    def register_general(self,
                        handler: Callable,
                        priority: int = PriorityLevel.NORMAL.value,
                        handler_id: Optional[str] = None) -> str:
        """注册通用处理器

        Args:
            handler: 处理器函数
            priority: 处理器优先级
            handler_id: 处理器ID（可选）

        Returns:
            str: 处理器ID
        """
        if not handler_id:
            handler_id = f"general_{uuid.uuid4().hex[:8]}"

        # 检查是否为异步函数
        is_async = asyncio.iscoroutinefunction(handler)

        # 创建处理器包装
        handler_wrapper = EventHandler(
            handler_id=handler_id,
            event_type="*",  # 通用处理器
            handler=handler,
            is_async=is_async,
            priority=priority
        )

        async def _register() -> None:
            async with self._handler_lock:
                self._general_handlers.append(handler_wrapper)

        # 异步注册
        asyncio.create_task(_register())

        logger.debug(f"注册通用处理器: {handler_id} (priority={priority})")

        return handler_id

    def unregister_general(self, handler_id: str) -> bool:
        """注销通用处理器

        Args:
            handler_id: 处理器ID

        Returns:
            bool: 注销是否成功
        """
        async def _unregister() -> bool:
            async with self._handler_lock:
                for i, handler in enumerate(self._general_handlers):
                    if handler.handler_id == handler_id:
                        self._general_handlers.pop(i)
                        logger.debug(f"注销通用处理器: {handler_id}")
                        return True

            return False

        # 异步注销
        asyncio.create_task(_unregister())

        return True

    def _create_timer(self,
                     interval: float,
                     callback: Callable,
                     name: Optional[str] = None) -> str:
        """创建定时器

        Args:
            interval: 间隔时间（秒）
            callback: 回调函数
            name: 定时器名称（可选）

        Returns:
            str: 定时器ID
        """
        if not name:
            name = f"timer_{uuid.uuid4().hex[:8]}"

        async def _timer_func() -> None:
            try:
                while self.record.status == ComponentStatus.RUNNING:
                    await asyncio.sleep(interval)

                    if self.record.status != ComponentStatus.RUNNING:
                        break

                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            # 在事件循环中执行同步函数
                            await asyncio.get_event_loop().run_in_executor(None, callback)
                    except Exception as e:
                        logger.error(f"定时器回调失败: {name}, 错误: {e}")
            except asyncio.CancelledError:
                # 定时器被取消，正常退出
                pass
            except Exception as e:
                logger.error(f"定时器异常: {name}, 错误: {e}")

        # 创建定时器任务
        timer_task = asyncio.create_task(_timer_func(), name=f"Timer-{name}")
        self._timers[name] = timer_task

        logger.debug(f"创建定时器: {name}, 间隔: {interval}秒")

        return name

    def _cancel_timer(self, timer_id: str) -> bool:
        """取消定时器

        Args:
            timer_id: 定时器ID

        Returns:
            bool: 取消是否成功
        """
        if timer_id in self._timers:
            timer_task = self._timers[timer_id]
            timer_task.cancel()
            del self._timers[timer_id]

            logger.debug(f"取消定时器: {timer_id}")
            return True

        return False

    async def _stop_all_timers(self) -> None:
        """停止所有定时器"""
        for timer_id, timer_task in list(self._timers.items()):
            timer_task.cancel()

        # 等待所有定时器停止
        if self._timers:
            await asyncio.gather(*self._timers.values(), return_exceptions=True)
            self._timers.clear()

        logger.debug("所有定时器已停止")

    async def _update_statistics(self) -> None:
        """更新统计信息"""
        # 这里可以添加定期统计更新逻辑
        # 例如：保存统计到数据库、生成报告等
        pass

    def get_queue_size(self) -> int:
        """获取队列大小

        Returns:
            int: 队列中的事件数量
        """
        return self._event_statistics.current_queue_size

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "total_events": self._event_statistics.total_events,
            "processed_events": self._event_statistics.processed_events,
            "failed_events": self._event_statistics.failed_events,
            "avg_processing_time_ms": self._event_statistics.avg_processing_time_ms,
            "max_queue_size": self._event_statistics.max_queue_size,
            "current_queue_size": self._event_statistics.current_queue_size,
            "event_type_counts": dict(self._event_statistics.event_type_counts),
            "handler_counts": dict(self._event_statistics.handler_counts),
            "last_reset_time": self._event_statistics.last_reset_time.isoformat(),
            "worker_count": len(self._worker_tasks),
            "timer_count": len(self._timers),
            "handler_count": (
                sum(len(handlers) for handlers in self._event_handlers.values()) +
                len(self._general_handlers)
            )
        }

    def reset_statistics(self) -> None:
        """重置统计"""
        self._event_statistics.reset()
        logger.debug("事件统计已重置")

    def get_event_history(self, limit: int = 100) -> List[EventEntity]:
        """获取事件历史

        Args:
            limit: 限制返回数量

        Returns:
            List[EventEntity]: 事件历史列表
        """
        return list(self._event_history)[-limit:] if self._event_history else []

    def get_handler_info(self, event_type: Optional[str] = None) -> Dict[str, Any]:
        """获取处理器信息

        Args:
            event_type: 事件类型（可选）

        Returns:
            Dict[str, Any]: 处理器信息
        """
        handlers_info = []

        if event_type:
            # 获取特定事件类型的处理器
            handlers = self._event_handlers.get(event_type, [])
            for handler in handlers:
                handlers_info.append({
                    "handler_id": handler.handler_id,
                    "event_type": handler.event_type,
                    "priority": handler.priority,
                    "enabled": handler.enabled,
                    "call_count": handler.call_count,
                    "last_called": handler.last_called.isoformat() if handler.last_called else None,
                    "created_at": handler.created_at.isoformat()
                })
        else:
            # 获取所有处理器
            for event_type_key, handlers in self._event_handlers.items():
                for handler in handlers:
                    handlers_info.append({
                        "handler_id": handler.handler_id,
                        "event_type": handler.event_type,
                        "priority": handler.priority,
                        "enabled": handler.enabled,
                        "call_count": handler.call_count,
                        "last_called": handler.last_called.isoformat() if handler.last_called else None,
                        "created_at": handler.created_at.isoformat()
                    })

            # 添加通用处理器
            for handler in self._general_handlers:
                handlers_info.append({
                    "handler_id": handler.handler_id,
                    "event_type": handler.event_type,
                    "priority": handler.priority,
                    "enabled": handler.enabled,
                    "call_count": handler.call_count,
                    "last_called": handler.last_called.isoformat() if handler.last_called else None,
                    "created_at": handler.created_at.isoformat()
                })

        return {
            "handler_count": len(handlers_info),
            "handlers": handlers_info
        }

    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息（扩展基类方法）

        Returns:
            Dict[str, Any]: 状态信息
        """
        base_info = super().get_status_info()

        # 添加事件引擎特定信息
        base_info.update({
            "queue_size": self.get_queue_size(),
            "max_queue_size": self._max_queue_size,
            "worker_count": self._max_workers,
            "active_workers": len(self._worker_tasks),
            "is_processing": self._is_processing,
            "timer_count": len(self._timers),
            "event_statistics": self.get_statistics()
        })

        return base_info


async def get_event_engine() -> Optional[EngineBase]:
    """获取全局事件引擎实例

    Returns:
        EventEngine: 事件引擎实例
    """
    from ..utils.engine_factory import get_engine_factory
    factory = await get_engine_factory()
    if factory:
        return await factory.get_engine("event_engine")
    return None