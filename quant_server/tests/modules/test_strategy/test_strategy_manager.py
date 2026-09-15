"""
策略管理器单元测试
覆盖：策略加载、生命周期管理、事件订阅
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.strategy.engines.strategy_manager import StrategyManager
from modules.strategy.constants import StrategyType, StrategyLifecycleStatus


class TestStrategyManager:
    """StrategyManager 单元测试"""

    @pytest.fixture
    def event_engine(self):
        """Mock 事件引擎"""
        engine = MagicMock()
        engine.subscribe = MagicMock()
        return engine

    @pytest.fixture
    def manager(self, event_engine):
        """创建策略管理器"""
        return StrategyManager(event_engine=event_engine)

    @pytest.mark.asyncio
    async def test_initialization(self, manager, event_engine):
        """测试初始化：策略注册表在 `_on_initialize` 后已填充默认策略。

        ⚠️ 2026-09-15：注册逻辑已从 `__init__` 迁到 `_on_initialize` ——
        `StrategyManager.__init__` 不再调用 `_register_default_strategies()`（见类 docstring
        「移除 _register_default_strategies() — 改为 StrategyRegistry 注入」），改为在
        `_on_initialize()` 中对空注册表执行 `registry.auto_discover()`
        （`strategy_manager.py:1166`）。故本测试须先驱动初始化，否则注册表恒为空。
        """
        assert manager.event_engine is event_engine

        # 注册表初始为空 → 由初始化触发自动发现
        assert manager.registry.is_empty()
        await manager._on_initialize()

        # 2026-09-15：注册表已抽为 StrategyRegistry 单例（List 存储，消除覆盖 Bug），
        # 管理器上的属性由 `_strategy_registry`（Dict）改为 `registry`。
        #
        # ⚠️ 原断言为 CTA / TECHNICAL —— 对应 MACrossStrategy 等技术指标策略，
        # **代码中已不存在**（CLAUDE.md《实际策略清单》）。按实测的注册结果校正：
        #   rotation → CrossMarketMomentum / HighVolMomentum
        #   ml       → LightGBMBottom
        #   custom   → DeepDropRebound / StockLowHigh / PanicBottom / Microcap
        registered = {t.value for t in manager.registry.get_registered_types()}
        assert registered == {"rotation", "ml", "custom"}, f"实际注册类型: {registered}"
        assert StrategyType.ROTATION in manager.registry
        assert len(manager.registry) == 7, "应注册 7 个策略类"

    @pytest.mark.asyncio
    async def test_register_strategy(self, manager):
        """测试注册自定义策略类"""
        from modules.strategy.strategies.reference.stock_low_high_strategy import StockLowHighStrategy

        manager.register_strategy(StrategyType.CTA, StockLowHighStrategy)
        # 2026-09-15：注册表改为 List 存储（同类型可有多个类），故改用包含判断
        assert StockLowHighStrategy in manager.registry.get(StrategyType.CTA)

    @pytest.mark.asyncio
    async def test_load_strategy(self, manager):
        """测试加载策略实例"""
        from modules.strategy.models import StrategyConfig

        config = StrategyConfig(initial_capital=100000)
        instance = await manager.load_strategy(
            strategy_id="test-001",
            name="测试策略",
            strategy_type=StrategyType.CTA,
            code="MACrossStrategy",
            parameters={"fast_period": 5, "slow_period": 20},
            config=config,
        )

        assert instance.id == "test-001"
        assert instance.status == StrategyLifecycleStatus.DRAFT
        assert "test-001" in manager.strategies

    @pytest.mark.asyncio
    async def test_start_stop_strategy(self, manager):
        """测试策略的启动和停止"""
        from modules.strategy.models import StrategyConfig
        from modules.strategy.strategies.base.strategy_context import StrategyContext

        config = StrategyConfig(initial_capital=100000)
        await manager.load_strategy(
            strategy_id="test-002",
            name="运行测试",
            strategy_type=StrategyType.CTA,
            code="MACrossStrategy",
            parameters={"fast_period": 5, "slow_period": 20},
            config=config,
        )

        context = StrategyContext(
            # 2026-09-15：`strategy_id`/`strategy_name`/`user_id` 已成必填字段
            strategy_id="test-002", strategy_name="运行测试", user_id="test-user",
            available_capital=100000, total_assets=100000,
        )
        await manager.start_strategy("test-002", context)

        assert manager.is_strategy_running("test-002")
        assert manager.strategies["test-002"].status == StrategyLifecycleStatus.RUNNING

        await manager.stop_strategy("test-002")
        assert not manager.is_strategy_running("test-002")
        assert manager.strategies["test-002"].status == StrategyLifecycleStatus.STOPPED

    @pytest.mark.asyncio
    async def test_event_subscriptions_on_start(self, manager, event_engine):
        """测试 _on_start 注册事件订阅"""
        await manager._on_start()

        assert event_engine.subscribe.call_count >= 2
        # 验证订阅了 DataSyncCompletedEvent 和 OrderFilledEvent
        subscribed_types = [call.args[0] for call in event_engine.subscribe.call_args_list]
        type_names = [getattr(t, '__name__', str(t)) for t in subscribed_types]
        print(f"Subscribed to: {type_names}")

    @pytest.mark.asyncio
    async def test_pause_resume_strategy(self, manager):
        """测试策略暂停和恢复"""
        from modules.strategy.models import StrategyConfig
        from modules.strategy.strategies.base.strategy_context import StrategyContext

        config = StrategyConfig(initial_capital=100000)
        await manager.load_strategy(
            strategy_id="test-003",
            name="暂停测试",
            strategy_type=StrategyType.CTA,
            code="MACrossStrategy",
            parameters={},
            config=config,
        )

        context = StrategyContext(
            strategy_id="test-003", strategy_name="暂停测试", user_id="test-user",
            available_capital=100000, total_assets=100000,
        )
        await manager.start_strategy("test-003", context)
        await manager.pause_strategy("test-003")

        assert not manager.is_strategy_running("test-003")
        assert manager.strategies["test-003"].status == StrategyLifecycleStatus.PAUSED

        await manager.resume_strategy("test-003")
        assert manager.is_strategy_running("test-003")

        await manager.stop_strategy("test-003")
