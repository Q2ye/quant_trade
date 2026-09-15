"""
事件引擎单元测试
覆盖：事件注册、优先级排序、发布/订阅、异常隔离

⚠️ 2026-09-15 修复（本文件 6 个用例此前全部 ERROR，从未真正跑过）：
  1. **构造签名过时**：`EventEngine(max_workers=2, queue_size=100)` 已不成立 ——
     现签名为 `EventEngine(config: EngineConfigEntity, event_engine=None)`，
     且 `max_workers` / `queue_size` 移入 `config.config` 字典
     （`event_engine.py:196-197`）。原来 6 个用例都在 fixture 处抛 TypeError。
  2. **`@pytest.mark.asyncio` 无效**：`pytest-asyncio` **不在依赖中**（`pyproject.toml` 无），
     异步用例不会被 await。本项目实际约定是 `asyncio.run(...)`（另有 7 个测试文件如此）。
     故统一改为「同步用例 + `asyncio.run` 包 async 主体」。
"""
import asyncio

import pytest

from core.engines.system.event_engine import EventEngine
from core.engines.types.entities import EngineConfigEntity
from core.engines.types.enums import EngineType
from core.events.base import BaseEvent, EventPriority


class DummyEvent(BaseEvent):
    """测试用事件"""

    def __init__(self, value: str = "test", **kwargs):
        super().__init__(
            module="test",
            event_type="test.dummy",
            priority=EventPriority.NORMAL,
            source="test",
            **kwargs
        )
        self.data = {"value": value}


@pytest.fixture
def engine():
    """创建事件引擎实例（max_workers/queue_size 走 config.config）。"""
    return EventEngine(
        EngineConfigEntity(
            name="test_event_engine",
            engine_type=EngineType.EVENT,
            config={"max_workers": 2, "queue_size": 100},
        )
    )


def test_start_stop(engine):
    """测试启动和停止"""

    async def _case():
        await engine.start()
        assert engine.is_running
        await engine.stop()
        assert not engine.is_running

    asyncio.run(_case())


def test_put_and_subscribe(engine):
    """测试事件发布和订阅"""

    async def _case():
        received = []

        async def handler(event: DummyEvent):
            received.append(event.data["value"])

        engine.subscribe(DummyEvent, handler)
        await engine.start()

        await engine.put(DummyEvent(value="hello"))
        await asyncio.sleep(0.1)
        assert "hello" in received

        await engine.stop()

    asyncio.run(_case())


def test_priority_ordering():
    """优先级排序：同一批事件按 priority 出队。

    2026-09-15 修正：原实现用 2 个工作器 + 「put 一个等一个」，
    多工作器并发取事件时**顺序不可观测**（LOW 先入队就被 worker0 取走）。
    现改为**单工作器**，且**先把两个事件入队、再启动工作器** → 出队顺序确定由优先级决定。
    """

    class HighEvent(BaseEvent):
        def __init__(self, **kwargs):
            super().__init__(
                module="test", event_type="test.high",
                priority=EventPriority.HIGH, source="test", **kwargs
            )
            self.data = {"name": "high"}

    class LowEvent(BaseEvent):
        def __init__(self, **kwargs):
            super().__init__(
                module="test", event_type="test.low",
                priority=EventPriority.LOW, source="test", **kwargs
            )
            self.data = {"name": "low"}

    async def _case():
        single = EventEngine(
            EngineConfigEntity(
                name="test_event_engine_single",
                engine_type=EngineType.EVENT,
                config={"max_workers": 1, "queue_size": 100},
            )
        )
        processed = []

        async def handler(event):
            processed.append(event.data["name"])

        single.subscribe(HighEvent, handler)
        single.subscribe(LowEvent, handler)

        await single.start()

        # ⚠️ put 要求引擎处于运行态（否则抛「事件引擎未运行」），而只要工作器在跑，
        # LOW 先入队就会立刻被取走 → 顺序不可观测。故先**暂停工作器**让两个事件
        # 同时躺在优先级堆里（白盒，仅为构造确定性场景），再恢复。
        await single._stop_workers()
        await single.put(LowEvent())
        await single.put(HighEvent())

        # 1) 队列层：堆顶必须是高优先级（priority 数值越小越先出队）
        assert single.get_queue_size() == 2, "两个事件应同时驻留队列"
        head = single._event_queue[0]
        assert head.priority < 4, f"堆顶应为高优先级，实际 priority={head.priority}"

        # 2) 端到端：恢复工作器后，出队顺序由优先级决定
        await single._start_workers()
        await asyncio.sleep(0.2)

        assert processed and processed[0] == "high", f"Expected high first, got {processed}"
        await single.stop()

    asyncio.run(_case())


def test_handler_exception_isolation(engine):
    """测试处理器异常不影响其他处理器"""

    async def _case():
        good_received = []

        async def bad_handler(event):
            raise RuntimeError("handler error")

        async def good_handler(event):
            good_received.append(event.data["value"])

        engine.subscribe(DummyEvent, bad_handler)
        engine.subscribe(DummyEvent, good_handler)
        await engine.start()

        await engine.put(DummyEvent(value="should_arrive"))
        await asyncio.sleep(0.1)

        assert "should_arrive" in good_received
        await engine.stop()

    asyncio.run(_case())


def test_unsubscribe(engine):
    """测试取消订阅（2026-09-15：API 由 `unsubscribe` 更名为 `unregister(event_type, handler_id)`）"""

    async def _case():
        received = []

        async def handler(event):
            received.append(event.data["value"])

        handler_id = engine.subscribe(DummyEvent, handler)
        assert engine.unregister("DummyEvent", handler_id) is True
        await engine.start()

        await engine.put(DummyEvent(value="should_not_arrive"))
        await asyncio.sleep(0.1)

        assert len(received) == 0
        await engine.stop()

    asyncio.run(_case())


def test_multiple_subscribers(engine):
    """测试多个订阅者同时收到事件"""

    async def _case():
        results = {1: [], 2: [], 3: []}

        def make_handler(n):
            async def h(event):
                results[n].append(event.data["value"])
            return h

        for i in range(1, 4):
            engine.subscribe(DummyEvent, make_handler(i))

        await engine.start()
        await engine.put(DummyEvent(value="broadcast"))
        await asyncio.sleep(0.1)

        for i in range(1, 4):
            assert "broadcast" in results[i], f"Subscriber {i} did not receive event"
        await engine.stop()

    asyncio.run(_case())
