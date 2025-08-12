import time
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, Dict, List
from collections import defaultdict


class Event:
    """事件对象"""

    def __init__(self, type: str, data: Any = None):
        self.type = type
        self.data = data

    def __repr__(self):
        return f"Event<{self.type}>: {self.data}"


class EventEngine:
    """事件引擎（增强版）"""

    def __init__(self, interval: int = 1):
        self._interval = interval
        self._queue = Queue()
        self._active = False
        self._thread = Thread(target=self._run, daemon=True)
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._general_handlers: List[Callable] = []
        self._timer_handlers: Dict[str, Callable] = {}
        self._timer_count = 0

    def _run(self):
        """引擎运行主循环"""
        while self._active:
            try:
                # 处理定时任务
                self._process_timers()

                # 处理事件队列
                event = self._queue.get(block=True, timeout=1)
                self._process(event)
            except Empty:
                continue
            except Exception as e:
                print(f"事件引擎运行异常: {e}")

    def _process_timers(self):
        """处理定时任务"""
        current_time = time.time()
        for timer_id, (interval, last_run, handler) in list(self._timer_handlers.items()):
            if current_time - last_run >= interval:
                try:
                    handler()
                except Exception as e:
                    print(f"定时任务执行异常: {e}")
                self._timer_handlers[timer_id] = Any(interval, current_time, handler)

    def _process(self, event: Event):
        """处理事件"""
        # 特定类型事件处理
        for handler in self._handlers[event.type]:
            try:
                handler(event)
            except Exception as e:
                print(f"事件处理异常 [{event.type}]: {e}")

        # 通用事件处理
        for handler in self._general_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"通用事件处理异常: {e}")

    def start(self):
        """启动引擎"""
        if not self._active:
            self._active = True
            self._thread.start()
            print("事件引擎已启动")

    def stop(self):
        """停止引擎"""
        if self._active:
            self._active = False
            if self._thread.is_alive():
                self._thread.join(timeout=5)
            print("事件引擎已停止")

    def register(self, type: str, handler: Callable):
        """注册事件处理函数"""
        self._handlers[type].append(handler)

    def unregister(self, type: str, handler: Callable):
        """注销事件处理函数"""
        if type in self._handlers and handler in self._handlers[type]:
            self._handlers[type].remove(handler)

    def register_general(self, handler: Callable):
        """注册通用事件处理函数"""
        self._general_handlers.append(handler)

    def unregister_general(self, handler: Callable):
        """注销通用事件处理函数"""
        if handler in self._general_handlers:
            self._general_handlers.remove(handler)

    def put(self, event: Event):
        """放入事件"""
        self._queue.put(event)

    def register_timer(self, interval: float, handler: Callable) -> str:
        """注册定时任务"""
        timer_id = f"timer_{self._timer_count}"
        self._timer_count += 1
        self._timer_handlers[timer_id] = Any(interval, time.time(), handler)
        return timer_id

    def unregister_timer(self, timer_id: str):
        """注销定时任务"""
        if timer_id in self._timer_handlers:
            del self._timer_handlers[timer_id]

    def is_active(self) -> bool:
        """检查引擎是否运行中"""
        return self._active