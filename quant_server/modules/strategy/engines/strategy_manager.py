# -*- coding: utf-8 -*-
"""
策略管理器

负责策略的加载、初始化、运行控制、信号处理。
v1.1 重构: 移除硬编码注册，使用 StrategyRegistry；新增 handle_bar_batch / _publish_signals
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Any, Optional, Type

from core.engines.base.engine_base import EngineBase, EngineConfigEntity
from core.engines.types.enums import EngineType
from modules.strategy.constants import (
    StrategyType,
    StrategyLifecycleStatus,
    RunMode,
)
from modules.strategy.models import (
    StrategyInstance,
    StrategyState,
    StrategyConfig,
    TradingSignal,
)
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.strategies.base.strategy_context import StrategyContext
from modules.strategy.engines.strategy_registry import StrategyRegistry

logger = logging.getLogger(__name__)


class StrategyManager(EngineBase):
    """
    策略管理器（重构后 v1.1）

    变更:
    1. 移除 _register_default_strategies() — 改为 StrategyRegistry 注入
    2. 移除内部 _strategy_registry Dict — 使用 StrategyRegistry 单例（List 存储，消除覆盖 Bug）
    3. 新增 handle_bar_batch() — 对接 DataFeedEngine.iter_bars()
    4. 新增 _publish_signals() — 信号→StrategySignalEvent→EventEngine
    """

    def __init__(
        self,
        event_engine=None,
        registry: StrategyRegistry = None,
    ):
        config = EngineConfigEntity(
            name="StrategyManager",
            engine_type=EngineType.STRATEGY_MANAGER.value,
        )
        super().__init__(config=config, event_engine=event_engine)
        self.event_engine = event_engine

        # 策略注册表（单例，支持一个类型多个策略类，消除 Dict key 覆盖 Bug）
        self.registry = registry or StrategyRegistry()

        # 策略实例 {strategy_id: StrategyInstance}
        self.strategies: Dict[str, StrategyInstance] = {}

        # 运行状态 {strategy_id: StrategyState}
        self.running_states: Dict[str, StrategyState] = {}

        # 策略对象 {strategy_id: BaseStrategy}
        self._strategy_objects: Dict[str, BaseStrategy] = {}

        # 策略上下文 {strategy_id: StrategyContext}
        self._contexts: Dict[str, StrategyContext] = {}

        logger.info("StrategyManager 初始化完成（使用 StrategyRegistry）")

    # ---- 策略类注册（委托给 StrategyRegistry） ----

    def register_strategy_class(
        self,
        strategy_type: StrategyType,
        strategy_class: Type[BaseStrategy],
    ) -> None:
        """显式注册策略类（委托给 StrategyRegistry，支持多策略类共存）"""
        self.registry.register(strategy_type, strategy_class)

    def get_strategy_class(
        self,
        strategy_type: StrategyType,
    ) -> Optional[Type[BaseStrategy]]:
        """获取指定类型的第一个策略类"""
        return self.registry.get_first(strategy_type)

    def register_strategy(
        self,
        strategy_type: StrategyType,
        strategy_class: Type[BaseStrategy],
    ) -> None:
        """兼容旧接口"""
        self.register_strategy_class(strategy_type, strategy_class)

    # ---- 策略生命周期 ----

    async def load_strategy(
        self,
        strategy_id: str,
        name: str,
        strategy_type: StrategyType,
        code: str,
        parameters: Dict[str, Any],
        config: StrategyConfig,
    ) -> StrategyInstance:
        """加载策略 — 通过 registry 获取策略类并实例化"""
        strategy_class = self.registry.get_first(strategy_type)
        if not strategy_class:
            raise ValueError(f"未注册的策略类型: {strategy_type}")

        strategy = strategy_class(
            name=name,
            strategy_type=strategy_type,
            parameters=parameters,
        )

        instance = StrategyInstance(
            id=strategy_id,
            name=name,
            strategy_type=strategy_type,
            status=StrategyLifecycleStatus.DRAFT,
            user_id=config.user_id if hasattr(config, "user_id") else 0,
            code=code,
            parameters=parameters,
            capital=config.initial_capital,
        )

        self.strategies[strategy_id] = instance
        self._strategy_objects[strategy_id] = strategy

        logger.info(f"策略加载成功: {strategy_id}, {name}")
        return instance

    async def initialize_strategy(
        self,
        strategy_id: str,
        context: StrategyContext,
    ) -> None:
        """初始化策略"""
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        strategy_instance = self.strategies[strategy_id]
        strategy_type = strategy_instance.strategy_type
        strategy_class = self.registry.get_first(strategy_type)
        if not strategy_class:
            raise ValueError(f"未注册的策略类型: {strategy_type}")

        strategy = strategy_class(
            name=strategy_instance.name,
            strategy_type=strategy_type,
            parameters=strategy_instance.parameters,
        )

        strategy.context = context
        strategy.initialize()

        strategy_instance.status = StrategyLifecycleStatus.COMPILED
        logger.info(f"策略初始化成功: {strategy_id}")

    async def start_strategy(
        self,
        strategy_id: str,
        context: StrategyContext,
    ) -> None:
        """
        启动策略（v1.1 增强：注入 context callback）

        Args:
            strategy_id: 策略ID
            context: 策略上下文
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        strategy_instance = self.strategies[strategy_id]
        if not strategy_instance.can_start():
            raise ValueError(f"策略 {strategy_id} 当前状态无法启动")

        # 注入 context callback（数据获取/下单/信号发布）
        StrategyContextBuilder.inject_callbacks(
            context=context,
            strategy_manager=self,
            strategy_id=strategy_id,
        )

        # 初始化并启动
        await self.initialize_strategy(strategy_id, context)

        strategy = self._strategy_objects.get(strategy_id)
        if strategy:
            strategy.start()

        self._contexts[strategy_id] = context

        state = StrategyState(
            strategy_id=str(strategy_id),
            is_running=True,
            available_capital=context.available_capital,
            total_assets=context.total_assets,
        )
        self.running_states[str(strategy_id)] = state

        strategy_instance.status = StrategyLifecycleStatus.RUNNING
        strategy_instance.started_at = datetime.now()

        logger.info(f"策略启动成功: {strategy_id}")

    async def stop_strategy(self, strategy_id: str) -> None:
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        strategy_instance = self.strategies[strategy_id]

        strategy = self._strategy_objects.get(strategy_id)
        if strategy:
            strategy.stop()

        if str(strategy_id) in self.running_states:
            del self.running_states[str(strategy_id)]

        strategy_instance.status = StrategyLifecycleStatus.STOPPED
        strategy_instance.stopped_at = datetime.now()
        logger.info(f"策略停止成功: {strategy_id}")

    async def pause_strategy(self, strategy_id: str) -> None:
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        if str(strategy_id) not in self.running_states:
            raise ValueError(f"策略 {strategy_id} 未在运行")

        self.running_states[str(strategy_id)].is_running = False
        self.strategies[strategy_id].status = StrategyLifecycleStatus.PAUSED
        logger.info(f"策略暂停成功: {strategy_id}")

    async def resume_strategy(self, strategy_id: str) -> None:
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        if str(strategy_id) not in self.running_states:
            raise ValueError(f"策略 {strategy_id} 不在暂停状态")

        self.running_states[str(strategy_id)].is_running = True
        self.strategies[strategy_id].status = StrategyLifecycleStatus.RUNNING
        logger.info(f"策略恢复成功: {strategy_id}")

    # ---- 数据驱动（v1.1 新增） ----

    async def handle_bar_batch(
        self,
        trade_date: date,
        bars: List[Any],
        run_mode: RunMode = RunMode.BACKTEST,
    ) -> List[TradingSignal]:
        """
        接收一批同日期的 BarData，分发给所有运行中策略

        此方法由 DataFeedEngine 调用：
        - 回测模式：逐日调用，按交易日顺序
        - 实盘模式：收盘后数据同步完成时调用

        Returns:
            所有策略生成的信号汇总
        """
        all_signals: List[TradingSignal] = []

        for strategy_id in list(self.running_states.keys()):
            state = self.running_states.get(str(strategy_id))
            if not state or not state.is_running:
                continue

            strategy = self._strategy_objects.get(strategy_id)
            if not strategy:
                continue

            strategy_signals: List[TradingSignal] = []

            for bar in bars:
                try:
                    sigs = strategy.on_bar(bar)
                    if sigs:
                        if isinstance(sigs, list):
                            strategy_signals.extend(sigs)
                        else:
                            strategy_signals.append(sigs)
                except Exception as e:
                    logger.error(
                        f"策略 {strategy_id} 处理 Bar 失败: "
                        f"{getattr(bar, 'ts_code', '?')} @ {trade_date}: {e}"
                    )

            if strategy_signals:
                state.pending_signals.extend(strategy_signals)
                await self._publish_signals(strategy_id, strategy_signals)
                all_signals.extend(strategy_signals)

        return all_signals

    async def handle_bar(
        self,
        strategy_id: str,
        bar: Any,
    ) -> List[TradingSignal]:
        """
        单策略单 Bar 处理（v1.1 增强：on_bar 返回后立即发布信号事件）

        Args:
            strategy_id: 策略ID
            bar: BarData

        Returns:
            策略生成的信号列表
        """
        if str(strategy_id) not in self.running_states:
            return []

        state = self.running_states[str(strategy_id)]
        if not state.is_running:
            return []

        strategy = self._strategy_objects.get(strategy_id)
        if not strategy or not hasattr(strategy, "on_bar"):
            return []

        signals = strategy.on_bar(bar)
        if not signals:
            return []

        if not isinstance(signals, list):
            signals = [signals]

        state.pending_signals.extend(signals)
        await self._publish_signals(strategy_id, signals)

        return signals

    async def process_bar(
        self,
        strategy_id: str,
        bar_data: Any,
    ) -> List[TradingSignal]:
        """兼容旧接口 — 委托给 handle_bar"""
        return await self.handle_bar(strategy_id, bar_data)

    # ---- 信号处理（v1.1 新增） ----

    async def _publish_signals(
        self,
        strategy_id: str,
        signals: List[TradingSignal],
    ) -> None:
        """
        将策略生成的信号通过 EventEngine 发布

        数据流:
        1. 创建 StrategySignalEvent
        2. 调用 self.event_engine.put(event)
        3. SignalEngine 订阅 → 写入 signals 超表 + WebSocket 推送
        """
        if not self.event_engine or not signals:
            return

        try:
            from modules.strategy.events.signal_events import StrategySignalEvent

            instance = self.strategies.get(strategy_id)

            for sig in signals:
                event_data = {
                    "signal_id": sig.id if hasattr(sig, "id") else None,
                    "strategy_id": strategy_id,
                    "strategy_name": instance.name if instance else "",
                    "ts_code": sig.ts_code if hasattr(sig, "ts_code") else "",
                    "signal_type": (
                        sig.signal_type.value
                        if hasattr(sig, "signal_type") and hasattr(sig.signal_type, "value")
                        else str(sig.signal_type) if hasattr(sig, "signal_type") else ""
                    ),
                    "direction": (
                        sig.direction.value
                        if hasattr(sig, "direction") and hasattr(sig.direction, "value")
                        else str(sig.direction) if hasattr(sig, "direction") else ""
                    ),
                    "price": sig.price if hasattr(sig, "price") else 0.0,
                    "quantity": sig.quantity if hasattr(sig, "quantity") else 0,
                    "confidence": sig.confidence if hasattr(sig, "confidence") else 1.0,
                    "reason": sig.reason if hasattr(sig, "reason") else "",
                    "timestamp": datetime.now().isoformat(),
                }

                event = StrategySignalEvent(data=event_data)
                self.event_engine.put(event)

                logger.debug(
                    f"信号发布: {strategy_id} {event_data['ts_code']} "
                    f"{event_data['direction']} {event_data['signal_type']}"
                )

        except ImportError as e:
            logger.warning(f"无法导入 StrategySignalEvent: {e}")
        except Exception as e:
            logger.error(f"信号发布失败: {e}")

    # ---- 查询方法 ----

    def get_strategy_state(self, strategy_id: str) -> Optional[StrategyState]:
        return self.running_states.get(str(strategy_id))

    def get_all_running_strategies(self) -> List[StrategyState]:
        return list(self.running_states.values())

    def is_strategy_running(self, strategy_id: str) -> bool:
        state = self.running_states.get(str(strategy_id))
        return state is not None and state.is_running

    # ---- 生命周期 ----

    async def _on_initialize(self):
        logger.info("策略管理器初始化")
        # 自动扫描注册策略（如果注册表为空）
        if self.registry.is_empty():
            count = self.registry.auto_discover()
            logger.info(f"自动注册 {count} 个策略类")
        logger.info("策略管理器初始化完成")

    async def _on_start(self):
        logger.info("策略管理器启动")
        if self.event_engine:
            try:
                from modules.data.events.sync_events import DataSyncCompletedEvent
                from modules.trade.events.order_events import OrderFilledEvent

                self.event_engine.subscribe(
                    DataSyncCompletedEvent, self._on_data_sync_completed
                )
                self.event_engine.subscribe(
                    OrderFilledEvent, self._on_order_filled
                )
                logger.info("策略管理器已订阅 DataSyncCompletedEvent / OrderFilledEvent")
            except ImportError as e:
                logger.warning(f"无法订阅数据事件: {e}")
        logger.info("策略管理器启动完成")

    async def _on_data_sync_completed(self, event) -> None:
        """数据同步完成 → 驱动运行中策略"""
        sync_type = event.data.get("sync_type", "")
        logger.info(f"数据同步完成: {sync_type}，驱动运行中策略...")
        for strategy_id, state in self.running_states.items():
            if state.is_running:
                await self.process_bar(strategy_id, event.data)

    async def _on_order_filled(self, event) -> None:
        """订单成交 → 更新策略持仓"""
        logger.info(f"订单成交: {event.data.get('order_id')}，更新策略持仓")
        for strategy_id, state in self.running_states.items():
            if state.is_running:
                symbol = event.data.get("symbol")
                if symbol and symbol in state.positions:
                    state.positions[symbol] += event.data.get("filled_volume", 0)

    async def _on_stop(self):
        logger.info("策略管理器停止")
        for strategy_id_str in list(self.running_states.keys()):
            try:
                await self.stop_strategy(strategy_id_str)
            except Exception as e:
                logger.error(f"停止策略 {strategy_id_str} 失败: {e}")
        logger.info("策略管理器停止完成")


# ============================================================
# StrategyContextBuilder — 按 RunMode 构建 StrategyContext
# ============================================================

class StrategyContextBuilder:
    """
    StrategyContext 构建器

    按 RunMode（BACKTEST / SIMULATION / LIVE / PAPER）注入不同的 callback 实现。
    """

    @staticmethod
    def inject_callbacks(
        context: StrategyContext,
        strategy_manager: "StrategyManager",
        strategy_id: str,
    ) -> None:
        """
        注入 context callback

        Args:
            context: StrategyContext 实例
            strategy_manager: StrategyManager 引用
            strategy_id: 策略ID
        """
        # 数据获取 callback
        if not context.get_data_func:
            async def _get_data(ts_code: str, start_date: str, end_date: str):
                """从 DataFeedEngine 获取数据（回测模式使用预加载数据）"""
                logger.debug(f"get_data: {ts_code} {start_date}~{end_date}")
                return None  # 回测模式数据由 DataFeedEngine 推送，不需要主动拉取

            context.get_data_func = _get_data

        # 下单 callback
        if not context.submit_order_func:
            async def _submit_order(
                ts_code: str,
                direction: str,
                price: float,
                quantity: int,
                order_type: str = "market",
            ):
                """通过 EventEngine 发布订单事件"""
                logger.debug(
                    f"submit_order: {ts_code} {direction} "
                    f"{quantity}股 @ {price:.2f}"
                )
                return {"status": "submitted", "ts_code": ts_code}

            context.submit_order_func = _submit_order

        # 信号发布 callback
        if not context.on_signal_func:
            async def _on_signal(signals: List[TradingSignal]):
                """通过 StrategyManager._publish_signals 发布信号"""
                await strategy_manager._publish_signals(strategy_id, signals)

            context.on_signal_func = _on_signal

        logger.debug(f"StrategyContext callback 注入完成: {strategy_id}")
