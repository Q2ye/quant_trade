# core/event_engine.py
import time
import logging
from queue import Empty, Queue
from threading import Thread, Lock
from typing import Any, Callable, Dict, List, Tuple
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class Event:
    """事件对象"""

    def __init__(self, event_type: str, data: Any = None, source: str = None, priority: int = 0):
        self.type = event_type
        self.data = data
        self.source = source  # 事件来源
        self.priority = priority  # 事件优先级
        self.timestamp = datetime.now()

    def __repr__(self):
        return f"Event<{self.type}> from {self.source} at {self.timestamp}: {self.data}"


class PriorityQueue:
    """优先级队列实现"""

    def __init__(self):
        self._queues = {
            0: Queue(),  # 低优先级
            1: Queue(),  # 中优先级
            2: Queue()  # 高优先级
        }
        self._lock = Lock()

    def put(self, event: Event):
        """将事件放入队列"""
        with self._lock:
            priority = min(max(event.priority, 0), 2)  # 确保优先级在0-2之间
            self._queues[priority].put(event)

    def get(self, block=True, timeout=None):
        """从队列中获取事件（按优先级顺序）"""
        with self._lock:
            # 先检查高优先级队列
            for priority in [2, 1, 0]:
                try:
                    return self._queues[priority].get(block=False)
                except Empty:
                    continue

            # 如果所有队列都为空且需要阻塞
            if block:
                # 使用条件变量等待新事件
                # 简化实现：轮流检查每个队列
                start_time = time.time()
                while True:
                    for priority in [2, 1, 0]:
                        try:
                            return self._queues[priority].get(block=False)
                        except Empty:
                            continue

                    # 检查是否超时
                    if timeout and (time.time() - start_time) >= timeout:
                        raise Empty

                    # 短暂休眠避免CPU占用过高
                    time.sleep(0.01)
            else:
                raise Empty


class EventEngine:
    """事件引擎（增强版）"""

    def __init__(self, interval: int = 1, max_workers: int = 10):
        self._interval = interval
        self._queue = PriorityQueue()
        self._active = False
        self._thread = Thread(target=self._run, daemon=True)
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._general_handlers: List[Callable] = []
        self._timer_handlers: Dict[str, Tuple[float, float, Callable]] = {}  # (interval, last_run, handler)
        self._timer_count = 0
        self._max_workers = max_workers
        self._worker_pool = []
        self._lock = Lock()

    def _run(self):
        """引擎运行主循环"""
        # 创建工作线程池
        for i in range(self._max_workers):
            worker = Thread(target=self._worker_loop, daemon=True, name=f"EventWorker-{i}")
            worker.start()
            self._worker_pool.append(worker)

        logger.info(f"事件引擎已启动，工作线程数: {self._max_workers}")

        while self._active:
            try:
                # 处理定时任务
                self._process_timers()

                # 短暂休眠避免CPU占用过高
                time.sleep(self._interval)
            except Exception as e:
                logger.error(f"事件引擎运行异常: {e}", exc_info=True)

    def _worker_loop(self):
        """工作线程循环"""
        while self._active:
            try:
                # 从队列获取事件
                event = self._queue.get(block=True, timeout=1)
                # 处理事件
                self._process(event)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"工作线程处理事件异常: {e}", exc_info=True)

    def _process_timers(self):
        """处理定时任务"""
        current_time = time.time()
        for timer_id, (interval, last_run, handler) in list(self._timer_handlers.items()):
            if current_time - last_run >= interval:
                try:
                    # 执行定时任务
                    handler()
                except Exception as e:
                    logger.error(f"定时任务执行异常: {e}", exc_info=True)
                # 更新最后执行时间
                self._timer_handlers[timer_id] = (interval, current_time, handler)

    def _process(self, event: Event):
        """处理事件"""
        # 特定类型事件处理
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"事件处理异常 [{event.type}]: {e}", exc_info=True)

        # 通用事件处理
        for handler in self._general_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"通用事件处理异常: {e}", exc_info=True)

    def start(self):
        """启动引擎"""
        if not self._active:
            self._active = True
            self._thread.start()
            logger.info("事件引擎已启动")

    def stop(self):
        """停止引擎"""
        if self._active:
            self._active = False
            if self._thread.is_alive():
                self._thread.join(timeout=5)
            logger.info("事件引擎已停止")

    def register(self, event_type: str, handler: Callable):
        """注册事件处理函数"""
        with self._lock:
            self._handlers[event_type].append(handler)
            logger.debug(f"注册事件处理函数: {event_type} -> {handler.__name__}")

    def unregister(self, event_type: str, handler: Callable):
        """注销事件处理函数"""
        with self._lock:
            if event_type in self._handlers and handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                logger.debug(f"注销事件处理函数: {event_type} -> {handler.__name__}")

    def register_general(self, handler: Callable):
        """注册通用事件处理函数"""
        with self._lock:
            self._general_handlers.append(handler)
            logger.debug(f"注册通用事件处理函数: {handler.__name__}")

    def unregister_general(self, handler: Callable):
        """注销通用事件处理函数"""
        with self._lock:
            if handler in self._general_handlers:
                self._general_handlers.remove(handler)
                logger.debug(f"注销通用事件处理函数: {handler.__name__}")

    def put(self, event: Event):
        """放入事件"""
        self._queue.put(event)
        logger.debug(f"事件入队: {event}")

    def register_timer(self, interval: float, handler: Callable) -> str:
        """注册定时任务"""
        with self._lock:
            timer_id = f"timer_{self._timer_count}"
            self._timer_count += 1
            self._timer_handlers[timer_id] = (interval, time.time(), handler)
            logger.debug(f"注册定时任务: {timer_id}, 间隔: {interval}秒")
            return timer_id

    def unregister_timer(self, timer_id: str):
        """注销定时任务"""
        with self._lock:
            if timer_id in self._timer_handlers:
                del self._timer_handlers[timer_id]
                logger.debug(f"注销定时任务: {timer_id}")

    def is_active(self) -> bool:
        """检查引擎是否运行中"""
        return self._active

    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        with self._lock:
            return {
                "active": self._active,
                "event_types": list(self._handlers.keys()),
                "handlers_count": sum(len(handlers) for handlers in self._handlers.values()),
                "general_handlers_count": len(self._general_handlers),
                "timers_count": len(self._timer_handlers),
                "worker_count": len(self._worker_pool)
            }