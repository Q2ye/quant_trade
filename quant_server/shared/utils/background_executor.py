# -*- coding: utf-8 -*-
"""
多池后台任务执行器 — BackgroundTaskExecutor

将回测/策略执行/数据同步从 asyncio 事件循环剥离到独立线程池。
每类任务使用独立池，实盘/回测资源隔离。

架构:
  sync-pool     — 数据同步（2 workers，可排队）
  strategy-pool — 策略执行（2 workers，1 reserved 给实盘日终）
  backtest-pool — 用户回测（3 workers，max_pending=10）
  system-pool   — 系统运维（1 worker）

跨线程 EventEngine 桥接:
  工作线程生成的事件通过 queue.Queue → 主线程 _bridge_pump() → EventEngine
  确保 asyncio.Lock 始终在主线程 event loop 中使用。

用法:
  executor = BackgroundTaskExecutor(pools_config, event_engine)
  await executor.start()

  # Fire-and-forget
  await executor.submit("backtest", task_id, coro_factory)

  # Blocking serial
  future = executor.submit_and_wait("strategy", task_id, coro_factory, priority=TaskPriority.CRITICAL)
  future.result(timeout=1800)
"""

import asyncio
import concurrent.futures
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# 类型定义
# =============================================================================


class TaskPriority(IntEnum):
    CRITICAL = 0   # 实盘日终策略 — 不可中断
    HIGH = 1       # 系统运维 — 孤儿恢复、健康检查
    NORMAL = 2     # 数据同步
    LOW = 3        # 手动触发 / 调试
    BACKGROUND = 4 # 回测、参数优化


class TaskStatus(IntEnum):
    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELLED = 4


@dataclass
class PoolConfig:
    """单个线程池的配置"""
    max_workers: int = 2
    reserved_workers: int = 0   # 保留给高优先级任务的线程数
    max_pending: int = 0        # 排队上限（0 = 无限制）
    task_timeout: int = 3600    # 秒


@dataclass
class TaskInfo:
    """任务追踪信息"""
    task_id: str
    pool: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    cancellable: bool = True
    future: Optional[concurrent.futures.Future] = None
    cancel_event: Optional["threading.Event"] = None
    submitted_at: float = field(default_factory=time.time)


# =============================================================================
# _WorkerPool — 单个线程池
# =============================================================================


class _WorkerPool:
    """单个线程池，管理同类任务的执行 + 线程安全"""

    def __init__(self, name: str, config: PoolConfig):
        self.name = name
        self.config = config
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=config.max_workers,
            thread_name_prefix=name,
        )
        # 并发控制
        self._semaphore = threading.BoundedSemaphore(config.max_workers)
        self._reserved_workers: int = config.reserved_workers
        self._total_workers: int = config.max_workers

        # 任务追踪（线程安全保护 — 单个锁覆盖所有读改操作）
        self._lock = threading.Lock()
        self._active: Dict[str, TaskInfo] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._pending_count: int = 0

    # ------------------------------------------------------------------
    # 提交
    # ------------------------------------------------------------------

    def submit(
        self,
        task_id: str,
        coro_factory: Callable[[], Coroutine],
        priority: TaskPriority = TaskPriority.NORMAL,
        cancellable: bool = True,
        bridge_queue: Optional["queue.Queue"] = None,
    ) -> TaskInfo:
        """提交任务（fire-and-forget）。返回 TaskInfo 用于追踪。"""
        info = TaskInfo(
            task_id=task_id, pool=self.name, status=TaskStatus.PENDING,
            priority=priority, cancellable=cancellable,
        )
        cancel_event = threading.Event()
        info.cancel_event = cancel_event

        # 单锁完成所有检查和注册
        with self._lock:
            if task_id in self._active:
                raise RuntimeError(f"任务 {task_id} 已在池 '{self.name}' 中")
            self._cancel_events[task_id] = cancel_event
            self._active[task_id] = info
            max_pending = self.config.max_pending
            if max_pending > 0:
                if self._pending_count >= max_pending:
                    info.status = TaskStatus.FAILED
                    self._cleanup_task(task_id)
                    raise RuntimeError(
                        f"Pool '{self.name}' is full ({max_pending} pending max)"
                    )
                self._pending_count += 1

        # 获取信号量（阻塞等待有空闲 worker）
        acquired = self._semaphore.acquire(timeout=0.1)
        if not acquired:
            def _retry_submit():
                try:
                    self._semaphore.acquire()
                    self._do_submit(info, coro_factory, cancel_event, bridge_queue)
                except Exception:
                    self._semaphore.release()
                    raise
            t = threading.Thread(target=_retry_submit, daemon=True, name=f"{self.name}-queue")
            t.start()
        else:
            self._do_submit(info, coro_factory, cancel_event, bridge_queue)

        return info

    def submit_and_wait(
        self,
        task_id: str,
        coro_factory: Callable[[], Coroutine],
        priority: TaskPriority = TaskPriority.NORMAL,
        cancellable: bool = True,
        bridge_queue: Optional["queue.Queue"] = None,
    ) -> concurrent.futures.Future:
        """提交任务并返回 Future。

        调用方使用 asyncio.wrap_future(future) 转换为可 await 对象，
        避免在主线程中调用 future.result() 阻塞事件循环。
        """
        info = TaskInfo(
            task_id=task_id, pool=self.name, status=TaskStatus.PENDING,
            priority=priority, cancellable=cancellable,
        )
        cancel_event = threading.Event()
        info.cancel_event = cancel_event

        with self._lock:
            self._cancel_events[task_id] = cancel_event
            self._active[task_id] = info

        # 通过信号量限制并发（非阻塞：用 timeout=0 尝试获取，失败则排队）
        if not self._semaphore.acquire(timeout=0):
            wait_error: list = [None]  # mutable box to capture exception from daemon thread

            def _wait_and_submit():
                try:
                    self._semaphore.acquire()
                    self._do_submit(info, coro_factory, cancel_event, bridge_queue)
                except Exception as e:
                    wait_error[0] = e
                    self._semaphore.release()

            t = threading.Thread(target=_wait_and_submit, daemon=True, name=f"{self.name}-wait")
            t.start()

            # 轮询等待 future 就绪（带超时保护：最长等 30s 信号量）
            deadline = time.time() + 30.0
            while info.future is None:
                if time.time() > deadline:
                    raise RuntimeError(
                        f"Pool '{self.name}': timed out waiting for worker slot (30s)"
                    )
                if wait_error[0] is not None:
                    raise RuntimeError(
                        f"Pool '{self.name}': submit failed: {wait_error[0]}"
                    )
                if not t.is_alive() and info.future is None:
                    raise RuntimeError(
                        f"Pool '{self.name}': wait thread died without submitting"
                    )
                time.sleep(0.02)
            return info.future

        return self._do_submit(info, coro_factory, cancel_event, bridge_queue)

    def _do_submit(
        self, info: TaskInfo, coro_factory, cancel_event, bridge_queue
    ) -> concurrent.futures.Future:
        """实际提交到线程池（调用方负责信号量管理）。

        如果提交失败（executor 已关闭等），释放信号量防止泄漏。
        """
        def _release_sem(_fut):
            self._semaphore.release()
        info.status = TaskStatus.RUNNING
        try:
            future = self._executor.submit(
                self._thread_main, info, coro_factory, cancel_event, bridge_queue
            )
        except Exception:
            self._semaphore.release()
            raise
        future.add_done_callback(_release_sem)
        info.future = future
        return future

    def _thread_main(
        self,
        info: TaskInfo,
        coro_factory: Callable[[], Coroutine],
        cancel_event: threading.Event,
        bridge_queue: Optional["queue.Queue"],
    ) -> Any:
        """每个 worker 线程的入口：设置线程名 → 创建独立 event loop → 运行协程"""
        worker_idx = info.task_id[-6:] if len(info.task_id) >= 6 else "0"
        threading.current_thread().name = f"{self.name}-{worker_idx}"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 注入 bridge queue 到 task-local（策略用此跨线程发布事件）
            if bridge_queue is not None:
                _set_bridge_queue(bridge_queue)
            # 注入 cancel event
            _set_cancel_event(cancel_event)

            coro = coro_factory()
            result = loop.run_until_complete(coro)
            info.status = TaskStatus.COMPLETED
            return result
        except asyncio.CancelledError:
            info.status = TaskStatus.CANCELLED
            return None
        except Exception:
            info.status = TaskStatus.FAILED
            raise
        finally:
            # 等待 pending callbacks（如 SQLAlchemy asyncpg 连接清理）完成后再关闭 loop
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()
            with self._lock:
                self._cleanup_task(info.task_id)

    # ------------------------------------------------------------------
    # 取消 / 查询 / 清理
    # ------------------------------------------------------------------

    def cancel(self, task_id: str) -> bool:
        """发送取消信号"""
        with self._lock:
            ce = self._cancel_events.get(task_id)
            if ce is not None:
                ce.set()
                return True
        return False

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        with self._lock:
            info = self._active.get(task_id)
            return info.status if info else None

    def get_active_count(self) -> int:
        with self._lock:
            return len([i for i in self._active.values() if i.status == TaskStatus.RUNNING])

    def get_pool_stats(self) -> dict:
        with self._lock:
            return {
                "pool": self.name,
                "max_workers": self.config.max_workers,
                "reserved": self.config.reserved_workers,
                "active_tasks": len(self._active),
                "running": len([i for i in self._active.values() if i.status == TaskStatus.RUNNING]),
                "pending": self._pending_count,
            }

    def _cleanup_task(self, task_id: str):
        """清理任务追踪数据（持有锁时调用）"""
        self._active.pop(task_id, None)
        self._cancel_events.pop(task_id, None)
        if self.config.max_pending > 0 and self._pending_count > 0:
            self._pending_count -= 1

    def shutdown(self, timeout: float = 60):
        """关闭线程池"""
        # 先取消所有活跃任务
        with self._lock:
            for ce in self._cancel_events.values():
                ce.set()
        self._executor.shutdown(wait=True, timeout=timeout)


# =============================================================================
# 跨线程事件桥接（thread-local + queue.Queue）
# =============================================================================

_bridge_queue_local = threading.local()


def _set_bridge_queue(q: "queue.Queue"):
    _bridge_queue_local.queue = q


def _set_cancel_event(ev: threading.Event):
    _bridge_queue_local.cancel_event = ev


def get_bridge_queue() -> Optional["queue.Queue"]:
    return getattr(_bridge_queue_local, "queue", None)


def get_cancel_event() -> Optional[threading.Event]:
    return getattr(_bridge_queue_local, "cancel_event", None)


# =============================================================================
# BackgroundTaskExecutor — 顶层管理器
# =============================================================================


class BackgroundTaskExecutor:
    """多池后台任务执行器。

    管理 4 个独立线程池 + 跨线程事件桥接 + 全局任务追踪。
    """

    def __init__(
        self,
        pools_config: Optional[Dict[str, dict]] = None,
        event_engine: Any = None,
    ):
        """
        Args:
            pools_config: {"sync": {...}, "strategy": {...}, ...}
            event_engine: 主线程 EventEngine 引用（用于桥接）
        """
        defaults = {
            "sync":     PoolConfig(max_workers=2, task_timeout=3600),
            "strategy": PoolConfig(max_workers=2, reserved_workers=1, task_timeout=1800),
            "backtest": PoolConfig(max_workers=3, max_pending=10, task_timeout=7200),
            "system":   PoolConfig(max_workers=1, task_timeout=300),
        }
        if pools_config:
            for name, cfg in pools_config.items():
                if name in defaults:
                    defaults[name] = PoolConfig(**{**defaults[name].__dict__, **cfg})
        self._pools: Dict[str, _WorkerPool] = {
            name: _WorkerPool(name, cfg) for name, cfg in defaults.items()
        }

        # 跨线程事件桥接
        self._event_engine = event_engine
        self._bridge_queue: queue.Queue = queue.Queue()
        self._bridge_task: Optional[asyncio.Task] = None

        # 全局取消令牌
        self._shutting_down = False

        logger.info(
            "BackgroundTaskExecutor 已创建: pools=%s",
            {n: p.config.max_workers for n, p in self._pools.items()},
        )

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def submit(
        self,
        pool: str,
        task_id: str,
        coro_factory: Callable[[], Coroutine],
        priority: TaskPriority = TaskPriority.NORMAL,
        cancellable: bool = True,
    ) -> TaskInfo:
        """提交后台任务（fire-and-forget）。"""
        wp = self._get_pool(pool)
        return wp.submit(task_id, coro_factory, priority, cancellable, self._bridge_queue)

    def submit_and_wait(
        self,
        pool: str,
        task_id: str,
        coro_factory: Callable[[], Coroutine],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> concurrent.futures.Future:
        """提交后台任务并返回 concurrent.futures.Future。

        在 async 上下文中使用 asyncio.wrap_future(future) 转换为可 await 对象：
            future = executor.submit_and_wait("sync", tid, factory)
            await asyncio.wrap_future(future)  # ← 不阻塞事件循环
        """
        wp = self._get_pool(pool)
        return wp.submit_and_wait(task_id, coro_factory, priority,
                                  bridge_queue=self._bridge_queue)

    def cancel(self, task_id: str) -> bool:
        """取消指定任务（任意池）。"""
        for wp in self._pools.values():
            if wp.cancel(task_id):
                logger.info("任务 %s 已发送取消信号", task_id)
                return True
        return False

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        for wp in self._pools.values():
            s = wp.get_status(task_id)
            if s is not None:
                return s
        return None

    def get_pool_stats(self, pool: str) -> dict:
        return self._get_pool(pool).get_pool_stats()

    def get_all_stats(self) -> dict:
        return {name: wp.get_pool_stats() for name, wp in self._pools.items()}

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self):
        """启动桥接泵 + 标记运行状态"""
        if self._event_engine is not None:
            self._bridge_task = asyncio.create_task(self._bridge_pump(), name="bg-bridge")
            logger.info("跨线程事件桥接已启动")

    async def shutdown(self, timeout: float = 60):
        """关闭所有线程池。

        关闭顺序：backtest → sync → system → strategy（实盘最后）
        """
        self._shutting_down = True
        order = ["backtest", "sync", "system", "strategy"]
        for name in order:
            wp = self._pools.get(name)
            if wp is None:
                continue
            remaining = max(timeout / len(order), 5)
            wp.shutdown(timeout=remaining)

        # 停止桥接泵（不阻塞：put 到线程安全 queue 后等待 task 退出）
        if self._bridge_task is not None:
            self._bridge_queue.put(None)  # 发送停止信号（queue.Queue 线程安全）
            try:
                await asyncio.wait_for(self._bridge_task, timeout=5)
            except (asyncio.TimeoutError):
                self._bridge_task.cancel()
            except asyncio.CancelledError:
                pass

        logger.info("BackgroundTaskExecutor 已关闭")

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _get_pool(self, pool: str) -> _WorkerPool:
        if pool not in self._pools:
            raise ValueError(
                f"未知线程池 '{pool}'，可选: {list(self._pools.keys())}"
            )
        return self._pools[pool]

    async def _bridge_pump(self):
        """主线程 asyncio task — 持续消费 bridge queue 中的事件，
        投递到 EventEngine。

        使用 asyncio.to_thread 将阻塞的 queue.Queue.get() 离线到线程池，
        避免阻塞主事件循环。
        """
        logger.debug("事件桥接泵启动")
        while not self._shutting_down:
            try:
                event = await asyncio.to_thread(self._bridge_queue.get, timeout=0.5)
                if event is None:  # 停止信号
                    break
                try:
                    await self._event_engine.put(event)
                except RuntimeError:
                    pass  # EventEngine 未运行
                except Exception as e:
                    logger.warning("事件桥接发布失败: %s", e)
            except queue.Empty:
                # 无事件时短暂休眠，让出事件循环
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error("事件桥接异常: %s", e)
        logger.debug("事件桥接泵停止")


# =============================================================================
# 模块单例
# =============================================================================

_executor_instance: Optional[BackgroundTaskExecutor] = None


def get_background_executor() -> Optional[BackgroundTaskExecutor]:
    return _executor_instance


def set_background_executor(executor: BackgroundTaskExecutor):
    global _executor_instance
    _executor_instance = executor
