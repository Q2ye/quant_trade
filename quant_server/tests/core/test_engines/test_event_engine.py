"""
事件引擎单元测试
覆盖：事件注册、优先级排序、发布/订阅、异常隔离
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.events.base import BaseEvent, EventPriority
from core.engines.system.event_engine import EventEngine


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


class TestEventEngine:
    """EventEngine 核心功能测试"""

    @pytest.fixture
    def engine(self):
        """创建事件引擎实例"""
        engine = EventEngine(max_workers=2, queue_size=100)
        return engine

    @pytest.mark.asyncio
    async def test_start_stop(self, engine):
        """测试启动和停止"""
        await engine.start()
        assert engine.is_running
        await engine.stop()
        assert not engine.is_running

    @pytest.mark.asyncio
    async def test_put_and_subscribe(self, engine):
        """测试事件发布和订阅"""
        received = []

        async def handler(event: DummyEvent):
            received.append(event.data["value"])

        engine.subscribe(DummyEvent, handler)
        await engine.start()

        event = DummyEvent(value="hello")
        await engine.put(event)

        # 等待事件处理
        await asyncio.sleep(0.1)
        assert "hello" in received

        await engine.stop()

    @pytest.mark.asyncio
    async def test_priority_ordering(self, engine):
        """测试优先级排序：高优先级先处理"""
        processed = []

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

        async def handler(event):
            processed.append(event.data["name"])

        engine.subscribe(HighEvent, handler)
        engine.subscribe(LowEvent, handler)
        await engine.start()

        await engine.put(LowEvent())
        await engine.put(HighEvent())
        await asyncio.sleep(0.15)

        assert processed[0] == "high", f"Expected high first, got {processed}"
        await engine.stop()

    @pytest.mark.asyncio
    async def test_handler_exception_isolation(self, engine):
        """测试处理器异常不影响其他处理器"""
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

    @pytest.mark.asyncio
    async def test_unsubscribe(self, engine):
        """测试取消订阅"""
        received = []

        async def handler(event):
            received.append(event.data["value"])

        engine.subscribe(DummyEvent, handler)
        engine.unsubscribe(DummyEvent, handler)
        await engine.start()

        await engine.put(DummyEvent(value="should_not_arrive"))
        await asyncio.sleep(0.1)

        assert len(received) == 0
        await engine.stop()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, engine):
        """测试多个订阅者同时收到事件"""
        results = {1: [], 2: [], 3: []}

        for i in range(1, 4):
            async def make_handler(n):
                async def h(event):
                    results[n].append(event.data["value"])
                return h
            engine.subscribe(DummyEvent, await make_handler(i))

        await engine.start()
        await engine.put(DummyEvent(value="broadcast"))
        await asyncio.sleep(0.1)

        for i in range(1, 4):
            assert "broadcast" in results[i], f"Subscriber {i} did not receive event"
        await engine.stop()
