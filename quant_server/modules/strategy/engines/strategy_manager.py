# -*- coding: utf-8 -*-
"""
策略管理器

负责策略的加载、初始化、运行控制、信号处理。
v1.1 重构: 移除硬编码注册，使用 StrategyRegistry；新增 handle_bar_batch / _publish_signals
"""
import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta
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
        session_factory=None,
    ):
        config = EngineConfigEntity(
            name="StrategyManager",
            engine_type=EngineType.STRATEGY_MANAGER.value,
        )
        super().__init__(config=config, event_engine=event_engine)
        self.event_engine = event_engine
        self.session_factory = session_factory

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

        # v1.3: 复用 load_strategy() 已创建的对象，避免重复实例化
        strategy = self._strategy_objects.get(strategy_id)
        if strategy is None:
            strategy_type = strategy_instance.strategy_type
            strategy_class = self.registry.get_first(strategy_type)
            if not strategy_class:
                raise ValueError(f"未注册的策略类型: {strategy_type}")

            strategy = strategy_class(
                name=strategy_instance.name,
                strategy_type=strategy_type,
                parameters=strategy_instance.parameters,
            )
            self._strategy_objects[strategy_id] = strategy

        strategy.context = context
        strategy.initialize()

        # v2.1: 初始化不再覆盖状态，保持原状态（通常为 DRAFT）
        if strategy_instance.status == StrategyLifecycleStatus.DRAFT:
            strategy_instance.status = StrategyLifecycleStatus.RUNNING
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
            await strategy.start()

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

        # v3.0: 仅实盘/仿真模式预热历史数据 + 恢复持仓（回测不需要）
        if getattr(strategy_instance, "run_mode", RunMode.BACKTEST) in (RunMode.LIVE):
            await self._restore_positions_from_db(strategy_id)
            await self._warmup_strategy_data(strategy_id)

        logger.info(f"策略启动成功: {strategy_id}")

    async def stop_strategy(self, strategy_id: str) -> None:
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        strategy_instance = self.strategies[strategy_id]

        strategy = self._strategy_objects.get(strategy_id)
        if strategy:
            await strategy.stop()

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


    # ---- v2.0: HTTP API 事件驱动策略生命周期 ----

    async def _on_strategy_start_requested(self, event) -> None:
        """
        响应 StrategyStartedEvent，从 DB 加载策略并真正启动执行。

        事件来源: ExecutionService.start_strategy() → event_engine.put()
        """
        data = event.data
        strategy_id = data.get("strategy_id")
        capital = data.get("initial_capital", 1000000.0)
        parameters = data.get("parameters", {})
        run_mode_str = data.get("run_mode", "live")
        execution_mode_str = data.get("execution_mode", "semi_auto")

        logger.info(
            f"收到策略启动请求: {strategy_id}, run_mode={run_mode_str}, "
            f"execution_mode={execution_mode_str}"
        )

        try:
            # 如果已在运行中，跳过
            if str(strategy_id) in self.running_states:
                logger.warning(f"策略 {strategy_id} 已在运行中，跳过")
                return

            # 从 DB 加载策略详情
            if not self.session_factory:
                logger.error(f"无法启动策略 {strategy_id}: session_factory 未设置")
                return

            from modules.strategy.constants import RunMode as RM, ExecutionMode as EM
            run_mode = getattr(RM, run_mode_str.upper(), RM.LIVE)
            execution_mode = getattr(EM, execution_mode_str.upper(), EM.SEMI_AUTO)

            async with self.session_factory() as session:
                from shared.database.repositories.strategy.management import StrategyRepository
                repo = StrategyRepository(session)
                strategy = await repo.get_by_id(strategy_id)
                if not strategy:
                    logger.error(f"策略 {strategy_id} 在 DB 中不存在")
                    return

                # 加载策略类
                await self.load_strategy(
                    strategy_id=strategy.id,
                    name=strategy.name,
                    strategy_type=StrategyType(strategy.strategy_type) if hasattr(strategy, 'strategy_type') and strategy.strategy_type else StrategyType.CTA,
                    code=strategy.code or "",
                    parameters=parameters or {},
                    config=StrategyConfig(
                        user_id=strategy.user_id,
                        initial_capital=capital,
                    ),
                )

                # 构建上下文
                from modules.strategy.strategies.base.strategy_context import StrategyContext
                context = StrategyContext(
                    strategy_id=strategy_id,
                    strategy_name=strategy.name,
                    user_id=strategy.user_id,
                    run_mode=run_mode,
                    initial_capital=capital,
                )

                # 注入 callback
                StrategyContextBuilder.inject_callbacks(
                    context=context,
                    strategy_manager=self,
                    strategy_id=strategy_id,
                    run_mode=run_mode,
                )

                # 初始化并启动
                await self.initialize_strategy(strategy_id, context)
                await self.start_strategy(strategy_id, context)

                # 设置 run_mode / execution_mode 到实例
                instance = self.strategies.get(strategy_id)
                if instance:
                    instance.run_mode = run_mode
                    instance.execution_mode = execution_mode

                logger.info(
                    f"策略启动完成(引擎): {strategy_id}, "
                    f"run_mode={run_mode.value}, execution_mode={execution_mode.value}"
                )

        except Exception as e:
            logger.error(f"引擎层启动策略失败: {strategy_id}: {e}", exc_info=True)

    async def _on_strategy_stop_requested(self, event) -> None:
        """响应 StrategyStoppedEvent，停止策略执行"""
        data = event.data
        strategy_id = data.get("strategy_id")
        logger.info(f"收到策略停止请求: {strategy_id}")

        try:
            if strategy_id in self.strategies:
                await self.stop_strategy(strategy_id)
                logger.info(f"策略停止完成(引擎): {strategy_id}")
            else:
                logger.warning(f"策略 {strategy_id} 未加载，跳过停止")
        except Exception as e:
            logger.error(f"引擎层停止策略失败: {strategy_id}: {e}")

    async def _on_strategy_pause_requested(self, event) -> None:
        """响应 StrategyPausedEvent，暂停策略执行"""
        data = event.data
        strategy_id = data.get("strategy_id")
        logger.info(f"收到策略暂停请求: {strategy_id}")

        try:
            await self.pause_strategy(strategy_id)
            logger.info(f"策略暂停完成(引擎): {strategy_id}")
        except Exception as e:
            logger.error(f"引擎层暂停策略失败: {strategy_id}: {e}")

    async def _on_strategy_resume_requested(self, event) -> None:
        """响应 StrategyResumedEvent，恢复策略执行"""
        data = event.data
        strategy_id = data.get("strategy_id")
        logger.info(f"收到策略恢复请求: {strategy_id}")

        try:
            await self.resume_strategy(strategy_id)
            logger.info(f"策略恢复完成(引擎): {strategy_id}")
        except Exception as e:
            logger.error(f"引擎层恢复策略失败: {strategy_id}: {e}")

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
            bar_error_count = 0
            total_bars = len(bars)

            for bar in bars:
                try:
                    sigs = strategy.on_bar(bar)
                    # 兼容 async on_bar（返回 coroutine）和 sync on_bar
                    if asyncio.iscoroutine(sigs):
                        sigs = await sigs
                    if sigs:
                        if isinstance(sigs, list):
                            strategy_signals.extend(sigs)
                        else:
                            strategy_signals.append(sigs)
                except Exception as e:
                    bar_error_count += 1
                    logger.error(
                        f"策略 {strategy_id} 处理 Bar 失败: "
                        f"{getattr(bar, 'ts_code', '?')} @ {trade_date}: "
                        f"{type(e).__name__}: {e}",
                        exc_info=(bar_error_count <= 3),  # 仅前 3 次打印完整堆栈
                    )

            if bar_error_count > 0:
                error_rate = bar_error_count / max(total_bars, 1)
                logger.warning(
                    f"策略 {strategy_id} @ {trade_date}: "
                    f"{bar_error_count}/{total_bars} bars 失败 ({error_rate:.1%})"
                )
                if error_rate > 0.5:
                    logger.error(
                        f"策略 {strategy_id} 超过 50%% bar 处理失败，"
                        f"自动转入 ERROR 状态"
                    )
                    # v2.1: 大面积异常 → 自动转 ERROR
                    instance = self.strategies.get(strategy_id)
                    if instance:
                        instance.status = StrategyLifecycleStatus.ERROR
                        instance.error_message = (
                            f"handle_bar_batch error_rate={error_rate:.1%} "
                            f"({bar_error_count}/{total_bars} bars) @ {trade_date}"
                        )
                    if str(strategy_id) in self.running_states:
                        del self.running_states[str(strategy_id)]
                    # 跳过该策略的信号处理
                    strategy.clear_signals() if strategy else None
                    continue

            # v1.3: 同时收集通过 add_signal() / context.submit_order() 添加的信号
            if strategy.signals:
                strategy_signals.extend(strategy.signals)
                strategy.clear_signals()

            # v1.5: 信号验证 — 过滤不合规信号
            valid_signals = []
            for sig in strategy_signals:
                try:
                    if strategy.validate_signal(sig):
                        valid_signals.append(sig)
                    else:
                        logger.warning(
                            f"信号验证失败: {getattr(sig, 'ts_code', '?')} "
                            f"{getattr(sig, 'direction', '?')}"
                        )
                except Exception:
                    valid_signals.append(sig)
            strategy_signals = valid_signals

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

        try:
            signals = strategy.on_bar(bar)
            # 兼容 async on_bar（返回 coroutine）和 sync on_bar
            if asyncio.iscoroutine(signals):
                signals = await signals

            # 归一化
            if not signals:
                signals = []
            if not isinstance(signals, list):
                signals = [signals]

            # v1.3: 同时收集通过 add_signal() / context.submit_order() 添加的信号
            if strategy.signals:
                signals.extend(strategy.signals)
                strategy.clear_signals()

            if not signals:
                return []

            state.pending_signals.extend(signals)
            await self._publish_signals(strategy_id, signals)

            return signals
        except Exception as e:
            # v2.1: 追踪连续 handle_bar 异常次数
            error_key = f"_bar_error_{strategy_id}"
            error_count = getattr(self, error_key, 0) + 1
            setattr(self, error_key, error_count)
            logger.error(
                f"策略 {strategy_id} handle_bar 失败 (#{error_count}): "
                f"{getattr(bar, 'ts_code', '?')}: "
                f"{type(e).__name__}: {e}",
                exc_info=(error_count <= 3),
            )
            # 连续 10 次 → 自动转 ERROR
            if error_count >= 10:
                logger.error(f"策略 {strategy_id} 连续 {error_count} 次 handle_bar 异常，自动转入 ERROR")
                instance = self.strategies.get(strategy_id)
                if instance:
                    instance.status = StrategyLifecycleStatus.ERROR
                    instance.error_message = f"连续 {error_count} 次 handle_bar 异常"
                if str(strategy_id) in self.running_states:
                    del self.running_states[str(strategy_id)]
            return []

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
        1. 创建 StrategySignalEvent（v2.0 含价格范围）
        2. 调用 self.event_engine.put(event)
        3. SignalEngine 订阅 → 写入 signals 超表 + WebSocket 推送
        """
        if not self.event_engine or not signals:
            return

        try:
            from modules.strategy.events.signal_events import StrategySignalEvent

            instance = self.strategies.get(strategy_id)
            # v2.2: 从策略实例读取绑定的账户ID
            account_id = getattr(instance, "account_id", "") if instance else ""

            for sig in signals:
                # v2.0: 使用 sig.to_dict() 获取完整数据（含价格范围自动计算）
                sig_dict = sig.to_dict() if hasattr(sig, "to_dict") else {}

                event = StrategySignalEvent(
                    strategy_id=strategy_id,
                    strategy_name=instance.name if instance else "",
                    ts_code=sig_dict.get("ts_code", ""),
                    signal_type=sig_dict.get("signal_type", ""),
                    signal_direction=sig_dict.get("direction", ""),
                    price=sig_dict.get("price", 0.0),
                    quantity=sig_dict.get("quantity", 0),
                    reason=sig_dict.get("reason", ""),
                    confidence=sig_dict.get("confidence", 1.0),
                    target_price=sig_dict.get("target_price"),
                    stop_loss_price=sig_dict.get("stop_loss_price"),
                    price_limit_low=sig_dict.get("price_limit_low"),
                    price_limit_high=sig_dict.get("price_limit_high"),
                    max_slippage_pct=sig_dict.get("max_slippage_pct", 0.02),
                    order_type=sig_dict.get("order_type", "limit_range"),
                    account_id=account_id,
                )
                self.event_engine.put(event)

                logger.debug(
                    f"信号发布: {strategy_id} {sig_dict.get('ts_code')} "
                    f"{sig_dict.get('direction')} {sig_dict.get('signal_type')} "
                    f"价格区间 [{sig_dict.get('price_limit_low')}~{sig_dict.get('price_limit_high')}]"
                )

        except ImportError as e:
            logger.warning(f"无法导入 StrategySignalEvent: {e}")
        except Exception as e:
            logger.error(f"信号发布失败: {e}")

    # ---- 查询方法 ----

    def get_strategy_object(self, strategy_id: str) -> Optional[BaseStrategy]:
        """
        获取已加载的策略实例对象（公开 API）。

        用于外部模块（如 BacktestService）在需要读取策略运行时状态
        （如 universe 股票池）时，通过 Manager 的安全接口访问，
        避免直接触碰 protected 成员 _strategy_objects。

        Args:
            strategy_id: 策略 ID

        Returns:
            BaseStrategy 实例，未找到时返回 None
        """
        return self._strategy_objects.get(strategy_id)

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
                from modules.strategy.events.signal_events import SignalConfirmedEvent

                self.event_engine.subscribe(
                    DataSyncCompletedEvent, self._on_data_sync_completed
                )
                self.event_engine.subscribe(
                    OrderFilledEvent, self._on_order_filled
                )
                self.event_engine.subscribe(
                    SignalConfirmedEvent, self._on_signal_confirmed
                )
                logger.info("策略管理器已订阅 DataSyncCompletedEvent / OrderFilledEvent / SignalConfirmedEvent")
            except ImportError as e:
                logger.warning(f"无法订阅数据事件: {e}")

            # v2.0: 订阅策略生命周期事件
            try:
                from modules.strategy.events.lifecycle_events import (
                    StrategyStartedEvent, StrategyStoppedEvent,
                    StrategyPausedEvent, StrategyResumedEvent,
                )
                self.event_engine.subscribe(
                    StrategyStartedEvent, self._on_strategy_start_requested
                )
                self.event_engine.subscribe(
                    StrategyStoppedEvent, self._on_strategy_stop_requested
                )
                self.event_engine.subscribe(
                    StrategyPausedEvent, self._on_strategy_pause_requested
                )
                self.event_engine.subscribe(
                    StrategyResumedEvent, self._on_strategy_resume_requested
                )
                logger.info("策略管理器已订阅策略生命周期事件")
            except ImportError as e:
                logger.warning(f"无法订阅策略生命周期事件: {e}")
        logger.info("策略管理器启动完成")

    async def _on_data_sync_completed(self, event) -> None:
        """数据同步完成 → 驱动运行中策略"""
        sync_type = event.data.get("sync_type", "")
        if sync_type not in ("daily_quotes", "daily_basic"):
            return

        trade_date_str = event.data.get("trade_date")
        if trade_date_str:
            from datetime import date as date_type
            from datetime import datetime as dt
            if isinstance(trade_date_str, str):
                trade_date = dt.fromisoformat(trade_date_str).date()
            else:
                trade_date = date_type.today()
        else:
            trade_date = date.today()

        logger.info(f"数据同步完成 (sync_type={sync_type})，驱动实盘策略 date={trade_date}")
        await self.run_daily_strategies(trade_date)

    async def run_daily_strategies(self, trade_date: date) -> list:
        """
        驱动所有 run_mode=live/simulation 的策略（公开入口）

        由 DailyStrategyRunner 或 _on_data_sync_completed 调用。
        """
        # 加载当日 BarData
        bars = await self._load_daily_bars(trade_date)
        if not bars:
            logger.warning(f"交易日 {trade_date} 无可用 BarData，跳过策略驱动")
            return []

        return await self._run_live_strategies(trade_date, bars)

    async def _load_daily_bars(self, trade_date: date) -> list:
        """
        加载指定交易日的 BarData（优先复权数据，fallback 原始数据）

        复用 DataFeedEngine 的 SQL 查询模式，使用批量 IN 子句。
        """
        from sqlalchemy import text

        try:
            # 优先查 stock_adjusted_prices (qfq)
            query = text(
                "SELECT ts_code, trade_date, open, high, low, close, vol, amount "
                "FROM stock_adjusted_prices "
                "WHERE trade_date = :trade_date "
                "  AND adj_type = 'qfq' AND freq = 'D' "
                "ORDER BY ts_code"
            )
            result = await self.db.execute(query, {"trade_date": trade_date})
            rows = result.fetchall()

            if not rows:
                # Fallback 到 stock_daily
                query2 = text(
                    "SELECT ts_code, trade_date, open, high, low, close, vol, amount "
                    "FROM stock_daily "
                    "WHERE trade_date = :trade_date "
                    "ORDER BY ts_code"
                )
                result2 = await self.db.execute(query2, {"trade_date": trade_date})
                rows = result2.fetchall()
                logger.info(f"_load_daily_bars: {trade_date} 使用 stock_daily fallback, {len(rows)} 条")

            # 转换为 BarData 对象
            bars = []
            for row in rows:
                bar = self._row_to_bar(row)
                if bar:
                    bars.append(bar)

            logger.info(f"_load_daily_bars: {trade_date} 加载 {len(bars)} 条 BarData")
            return bars

        except Exception as e:
            logger.error(f"加载 BarData 失败: {trade_date}: {e}")
            return []

    @staticmethod
    def _row_to_bar(row) -> object:
        """将数据库行转为 BarData 对象"""
        try:
            from modules.strategy.strategies.base.bar_data import BarData
            return BarData(
                ts_code=row.ts_code,
                trade_date=row.trade_date,
                open=float(row.open) if row.open else 0,
                high=float(row.high) if row.high else 0,
                low=float(row.low) if row.low else 0,
                close=float(row.close) if row.close else 0,
                volume=float(row.vol) if row.vol else 0,
                amount=float(row.amount) if row.amount else 0,
            )
        except (ImportError, AttributeError):
            # 若 BarData 不可用，返回简单命名元组
            from collections import namedtuple
            SimpleBar = namedtuple(
                "SimpleBar",
                ["ts_code", "trade_date", "open", "high", "low", "close", "volume", "amount"]
            )
            return SimpleBar(
                ts_code=row.ts_code,
                trade_date=row.trade_date,
                open=float(row.open) if row.open else 0,
                high=float(row.high) if row.high else 0,
                low=float(row.low) if row.low else 0,
                close=float(row.close) if row.close else 0,
                volume=float(row.vol) if row.vol else 0,
                amount=float(row.amount) if row.amount else 0,
            )

    async def _run_live_strategies(
        self,
        trade_date: date,
        bars: list,
    ) -> list:
        """
        驱动所有 run_mode 为 live/simulation 的策略

        含中断检测：若 last_run_date 缺失交易日，补跑但不产生信号。
        """
        from modules.strategy.constants import RunMode as RM
        all_signals = []

        for strategy_id in list(self.running_states.keys()):
            state = self.running_states.get(str(strategy_id))
            if not state or not state.is_running:
                continue

            instance = self.strategies.get(strategy_id)
            if not instance:
                continue

            # 只驱动 live/simulation 策略
            run_mode = getattr(instance, "run_mode", RM.BACKTEST)
            if run_mode != RM.LIVE:
                continue

            # 中断检测
            if state.last_run_date:
                missed = self._get_missed_trading_days(state.last_run_date, trade_date)
                if missed:
                    logger.warning(
                        f"策略 {strategy_id} 中断 {len(missed)} 个交易日: "
                        f"{missed[0]} ~ {missed[-1]}，补跑追状态（不产生信号）"
                    )
                    # 逐日回放 bar，但不产生信号
                    for missed_date in missed:
                        missed_bars = await self._load_daily_bars(missed_date)
                        if missed_bars:
                            # 临时抑制信号发布
                            await self._replay_bars_silent(strategy_id, missed_date, missed_bars)

            # v3.0: 运行前恢复持仓 + 检查昨日 pending
            await self._restore_positions_from_db(strategy_id)
            pending_map = await self._check_yesterday_pending(strategy_id, trade_date)

            # 过滤：昨天 pending 的同方向股票跳过，避免重复发信号
            filtered_bars = []
            for bar in bars:
                ts_code = getattr(bar, "ts_code", "") or getattr(bar, "symbol", "")
                if ts_code in pending_map:
                    prev = pending_map[ts_code]
                    if prev.get("direction", "") == "buy":
                        logger.info(
                            "策略 %s 股票 %s 昨日买入信号仍 pending，跳过今日信号",
                            strategy_id, ts_code,
                        )
                        continue  # 跳过该 bar
                filtered_bars.append(bar)

            # 处理当日 bar
            signals = await self.handle_bar_batch(
                trade_date=trade_date,
                bars=filtered_bars,
                run_mode=run_mode,
            )
            all_signals.extend(signals)

            # 更新最后运行日期
            state.last_run_date = trade_date

            # v3.1: 心跳 — 记录每个策略每日运行摘要
            heartbeat = {
                "trade_date": str(trade_date),
                "signals_count": len(signals),
                "positions_count": len(strategy.positions) if hasattr(strategy, "positions") else 0,
                "data_cached": len(getattr(strategy, "_data_cache", {})),
                "updated_at": datetime.now().isoformat(),
            }
            state.today_trades += len(signals)
            state.total_trades += len(signals)

            # v3.0: 盘后保存策略状态（含心跳）
            await self._save_strategy_state(strategy_id, heartbeat)
            await self._update_heartbeat(strategy_id, heartbeat)

            logger.info(
                "策略每日运行: %s @ %s | 信号: %d | 持仓: %d | 数据缓存: %d 只",
                strategy_id, trade_date, len(signals),
                heartbeat["positions_count"], heartbeat["data_cached"],
            )

        logger.info(
            f"_run_live_strategies: {trade_date} 完成, "
            f"{len(all_signals)} 个信号, "
            f"{len(self.running_states)} 个运行中策略"
        )
        return all_signals

    async def _replay_bars_silent(
        self, strategy_id: str, trade_date: date, bars: list
    ) -> None:
        """回放 bar 以追上策略状态，不产生信号"""
        state = self.running_states.get(str(strategy_id))
        strategy = self._strategy_objects.get(strategy_id)
        if not state or not strategy:
            return

        for bar in bars:
            try:
                await strategy.on_bar(bar)
            except Exception as e:
                logger.debug(f"补跑 bar 异常 (忽略): {strategy_id} {trade_date}: {e}")

        # 清除补跑过程中可能产生的信号
        strategy.clear_signals()

    def _get_missed_trading_days(
        self, last_date: date, current_date: date
    ) -> list:
        """获取两个日期之间缺失的交易日列表"""
        if last_date is None or last_date >= current_date:
            return []

        # 简单实现：返回 last_date+1 到 current_date-1 之间的所有工作日
        # 完整实现应使用 TradingCalendar
        missed = []
        d = last_date + timedelta(days=1)
        while d < current_date:
            if d.weekday() < 5:  # 周一到周五
                missed.append(d)
            d += timedelta(days=1)
        return missed

    # ==================== v3.0 仓位恢复与信号检查 ====================

    async def _restore_positions_from_db(self, strategy_id: str) -> None:
        """从 DB 持仓表加载该策略的当前持仓（按 strategy_id 隔离）"""
        strategy = self._strategy_objects.get(strategy_id)
        if not strategy:
            return

        try:
            from shared.database.session.session_manager import get_session_manager
            from shared.database.repositories.trading.position.position_repo import PositionRepository

            sm = get_session_manager()
            async with sm.get_session() as session:
                repo = PositionRepository(session)
                db_positions = await repo.get_by_strategy(str(strategy_id))

            restored = 0
            for pos in db_positions:
                qty = pos.volume
                if qty > 0:
                    strategy.update_position(
                        ts_code=pos.ts_code,
                        side="long",
                        quantity=qty,
                        avg_price=float(pos.cost_price) if pos.cost_price else 0,
                    )
                    restored += 1

            if restored:
                logger.info("策略 %s: 从 DB 恢复了 %d 只股票的持仓", strategy_id, restored)
        except Exception as e:
            logger.warning("策略 %s 仓位恢复失败（跳过）: %s", strategy_id, e)

    async def _check_yesterday_pending(
        self, strategy_id: str, trade_date: date
    ) -> Dict[str, Dict]:
        """返回 {ts_code: signal} — 该策略在 trade_date 前的 pending_manual 信号

        只查最近 10 天内 pending 的信号，防止无限回溯。
        """
        try:
            from sqlalchemy import text
            from shared.database.session.session_manager import get_session_manager

            yesterday = trade_date - timedelta(days=1)
            since = yesterday - timedelta(days=10)
            sm = get_session_manager()
            async with sm.get_session() as session:
                result = await session.execute(text("""
                    SELECT ts_code, direction, price, price_limit_low::float,
                           price_limit_high::float, signal_time::text
                    FROM signals
                    WHERE strategy_id = :sid
                      AND signal_status = 'pending_manual'
                      AND signal_time >= :since
                      AND signal_time <= :until
                """), {
                    "sid": str(strategy_id),
                    "since": since,
                    "until": yesterday + timedelta(days=1),
                })

                pending = {}
                for row in result.fetchall():
                    pending[row[0]] = {
                        "ts_code": row[0],
                        "direction": row[1],
                        "price": row[2],
                        "price_limit_low": row[3],
                        "price_limit_high": row[4],
                        "signal_time": row[5],
                    }
                return pending
        except Exception as e:
            logger.warning("策略 %s 昨日信号检查失败（跳过）: %s", strategy_id, e)
            return {}

    async def _warmup_strategy_data(
        self, strategy_id: str, ts_codes: List[str] = None, lookback: int = 200,
    ) -> None:
        """启动时加载 N 根历史 K 线，静默回放以预热策略指标

        从 DataFeedEngine 加载数据，逐日回放 on_bar + clear_signals，
        确保 MA/MACD/RSI 等指标在首次实盘 on_bar 时已就绪。
        """
        strategy = self._strategy_objects.get(strategy_id)
        if not strategy:
            return

        if ts_codes is None:
            instance = self.strategies.get(strategy_id)
            if instance and hasattr(instance, "parameters"):
                params = instance.parameters or {}
                ts_codes = list(params.get("symbols") or params.get("universe") or [])

        if not ts_codes:
            logger.info("策略 %s 无股票池，跳过预热", strategy_id)
            return

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback * 2)

        import pandas as pd
        loaded = 0
        for ts_code in ts_codes:
            try:
                bars = await self.data_feed_engine.load_stock_data(
                    ts_code, start_date.isoformat(), end_date.isoformat()
                )
                if bars is None or (hasattr(bars, 'empty') and bars.empty):
                    continue
                df = bars if isinstance(bars, pd.DataFrame) else pd.DataFrame(bars)
                if df.empty:
                    continue
                strategy._data_cache[ts_code] = df
                loaded += 1

                # 静默回放，不产生信号
                from core.engines.types.entities import BarData
                for _, row in df.iterrows():
                    bar = BarData(
                        ts_code=ts_code,
                        trade_date=row.get("trade_date") or row.name,
                        open=float(row.get("open", 0)),
                        high=float(row.get("high", 0)),
                        low=float(row.get("low", 0)),
                        close=float(row.get("close", 0)),
                        volume=float(row.get("volume", 0)),
                    )
                    try:
                        await strategy.on_bar(bar)
                    except Exception:
                        pass
                strategy.clear_signals()
            except Exception as e:
                logger.debug("预热 %s 失败: %s", ts_code, e)

        logger.info("策略 %s 预热完成: %d/%d 只股票, lookback=%d",
                    strategy_id, loaded, len(ts_codes), lookback)

    async def _save_strategy_state(self, strategy_id: str, heartbeat: dict = None) -> None:
        """盘后保存策略运行摘要到 strategy_runs.state_snapshot"""
        strategy = self._strategy_objects.get(strategy_id)
        state = self.running_states.get(str(strategy_id))
        if not strategy or not state:
            return

        import json
        from shared.database.session.session_manager import get_session_manager
        from sqlalchemy import text

        snapshot = {
            "last_trade_date": str(state.last_run_date) if state.last_run_date else None,
            "last_heartbeat": heartbeat or {},
            "positions": {
                ts_code: {"quantity": p.quantity,
                          "cost_price": getattr(p, "cost_price", 0) or getattr(p, "avg_cost", 0)}
                for ts_code, p in strategy.positions.items() if p.quantity > 0
            },
            "latest_data_dates": {
                ts_code: str(df.index[-1].date())
                for ts_code, df in strategy._data_cache.items()
                if hasattr(df, 'index') and len(df) > 0
            },
            "updated_at": datetime.now().isoformat(),
        }

        try:
            sm = get_session_manager()
            async with sm.get_session() as session:
                await session.execute(text("""
                    UPDATE strategy_runs SET state_snapshot = :snap::jsonb
                    WHERE strategy_id = :sid AND status = 'running'
                """), {"sid": str(strategy_id), "snap": json.dumps(snapshot)})
                await session.commit()
        except Exception as e:
            logger.debug("策略状态持久化失败（跳过）: %s", e)

    async def _update_heartbeat(self, strategy_id: str, heartbeat: dict) -> None:
        """v3.1: 更新策略运行心跳 — 写入 strategy_runs.state_snapshot"""
        import json
        from shared.database.session.session_manager import get_session_manager
        from sqlalchemy import text

        try:
            sm = get_session_manager()
            async with sm.get_session() as session:
                # 将心跳合并到 state_snapshot 的 last_heartbeat 键
                await session.execute(text("""
                    UPDATE strategy_runs
                    SET state_snapshot = jsonb_set(
                        coalesce(state_snapshot, '{}'::jsonb),
                        '{last_heartbeat}',
                        :hb::jsonb,
                        true
                    )
                    WHERE strategy_id = :sid AND status = 'running'
                """), {
                    "sid": str(strategy_id),
                    "hb": json.dumps(heartbeat),
                })
                await session.commit()
        except Exception as e:
            logger.warning("心跳更新失败（跳过）: %s", e)

    async def _on_signal_confirmed(self, event) -> None:
        """v2.0: 人工确认成交 → 同步策略持仓"""
        data = event.data if hasattr(event, 'data') else {}
        strategy_id = data.get("strategy_id", "")
        ts_code = data.get("ts_code", "")
        fill_price = data.get("fill_price", 0)
        fill_quantity = data.get("fill_quantity", 0)

        if not strategy_id or not ts_code:
            return

        state = self.running_states.get(str(strategy_id))
        if not state:
            logger.debug(f"策略 {strategy_id} 不在运行中，跳过持仓同步")
            return

        # 查找或创建持仓
        existing_pos = state.get_position(ts_code)
        if existing_pos:
            # 加仓：更新均价和数量
            total_cost = existing_pos.avg_cost * existing_pos.quantity + fill_price * fill_quantity
            existing_pos.quantity += fill_quantity
            existing_pos.avg_cost = total_cost / existing_pos.quantity if existing_pos.quantity > 0 else 0
            existing_pos.update_time = datetime.now()
            logger.info(f"持仓更新: {strategy_id} {ts_code} x{existing_pos.quantity} avg={existing_pos.avg_cost:.2f}")
        else:
            # 新建持仓
            from modules.strategy.models import Position
            from modules.strategy.constants import PositionSide
            import uuid
            state.positions.append(Position(
                id=str(uuid.uuid4()),
                strategy_id=strategy_id,
                ts_code=ts_code,
                side=PositionSide.LONG,
                quantity=fill_quantity,
                avg_cost=fill_price,
                current_price=fill_price,
                market_value=fill_price * fill_quantity,
                open_date=datetime.now(),
            ))
            logger.info(f"持仓新增: {strategy_id} {ts_code} x{fill_quantity} @ {fill_price}")

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

    按 RunMode（BACKTEST / LIVE / PAPER）注入不同的 callback 实现。
    """

    @staticmethod
    def inject_callbacks(
        context: StrategyContext,
        strategy_manager: "StrategyManager",
        strategy_id: str,
        run_mode: "RunMode" = None,
    ) -> None:
        """
        注入 context callback，按 RunMode 分支注入不同实现。

        Args:
            context: StrategyContext 实例
            strategy_manager: StrategyManager 引用
            strategy_id: 策略ID
            run_mode: 运行模式（BACKTEST / LIVE / PAPER）
        """
        from modules.strategy.constants import RunMode as RM

        if run_mode is None:
            run_mode = RM.BACKTEST

        is_live = run_mode == RM.LIVE

        # 数据获取 callback
        if not context.get_data_func:
            if is_live:
                async def _get_data_live(ts_code: str, start_date: str, end_date: str):
                    """实盘模式：从 DB 查询历史数据（不复用预加载缓存）"""
                    try:
                        bars = await strategy_manager.load_stock_history(
                            ts_code, start_date, end_date
                        )
                        logger.debug(
                            f"get_data(live): {ts_code} {start_date}~{end_date} "
                            f"→ {len(bars) if bars else 0} 条"
                        )
                        return bars
                    except Exception as e:
                        logger.error(f"get_data(live) 失败: {ts_code}: {e}")
                        return None
                context.get_data_func = _get_data_live
            else:
                async def _get_data(ts_code: str, start_date: str, end_date: str):
                    """回测模式：数据由 DataFeedEngine 预加载推送"""
                    logger.debug(f"get_data: {ts_code} {start_date}~{end_date}")
                    return None
                context.get_data_func = _get_data

        # 下单 callback
        if not context.submit_order_func:
            async def _submit_order(
                ts_code: str,
                direction: str,
                price: float,
                quantity: int,
                order_type: str = "limit_range",
                strategy_id: str = "",
                price_limit_low: Optional[float] = None,
                price_limit_high: Optional[float] = None,
                max_slippage_pct: float = 0.02,
                **_kwargs,
            ):
                """
                v2.0: 将订单转为 TradingSignal（含价格范围）。
                实盘模式下不发往真实经纪商，仅生成信号供人工确认。
                """
                from modules.strategy.models import TradingSignal
                from modules.strategy.constants import SignalDirection, SignalType
                import uuid

                sig = TradingSignal(
                    id=str(uuid.uuid4()),
                    strategy_id=strategy_id,
                    strategy_name="",
                    ts_code=ts_code,
                    signal_type=(
                        SignalType.ENTRY
                        if direction in ("LONG", "long") else SignalType.EXIT
                    ),
                    direction=(
                        SignalDirection.LONG
                        if direction in ("LONG", "long") else SignalDirection.SHORT
                    ),
                    price=price,
                    quantity=quantity,
                    order_type=order_type,
                    price_limit_low=price_limit_low,
                    price_limit_high=price_limit_high,
                    max_slippage_pct=max_slippage_pct,
                    amount=price * quantity if price > 0 and quantity > 0 else 0,
                    reason=f"context.submit_order: {ts_code} {direction}",
                )
                strategy_obj = strategy_manager._strategy_objects.get(strategy_id)
                if strategy_obj:
                    strategy_obj.add_signal(sig)
                logger.debug(
                    f"submit_order→signal: {ts_code} {direction} "
                    f"{quantity}股 @ {price:.2f} "
                    f"range=[{sig.price_limit_low}~{sig.price_limit_high}]"
                )
                return {"status": "submitted", "ts_code": ts_code}

            context.submit_order_func = _submit_order

        # 信号发布 callback
        if not context.on_signal_callback:
            async def _on_signal(signals: List[TradingSignal]):
                """通过 StrategyManager._publish_signals 发布信号"""
                await strategy_manager._publish_signals(strategy_id, signals)

            context.on_signal_callback = _on_signal

        logger.debug(
            f"StrategyContext callback 注入完成: {strategy_id} run_mode={run_mode}"
        )

    @staticmethod
    async def load_stock_history(
        ts_code: str, start_date: str, end_date: str
    ) -> Optional[list]:
        """实盘模式：从 DB 加载单只股票的历史 BarData"""
        from sqlalchemy import text

        try:
            # 优先查 stock_adjusted_prices
            query = text(
                "SELECT ts_code, trade_date, open, high, low, close, vol, amount "
                "FROM stock_adjusted_prices "
                "WHERE ts_code = :ts_code "
                "  AND trade_date BETWEEN :start AND :end "
                "  AND adj_type = 'qfq' AND freq = 'D' "
                "ORDER BY trade_date ASC"
            )
            # 延迟获取 db session（由 StrategyManager 持有）
            db = getattr(strategy_manager, "db", None)
            if db is None:
                return None

            result = await db.execute(query, {
                "ts_code": ts_code,
                "start": start_date,
                "end": end_date,
            })
            rows = result.fetchall()

            if not rows:
                # Fallback 到 stock_daily
                query2 = text(
                    "SELECT ts_code, trade_date, open, high, low, close, vol, amount "
                    "FROM stock_daily "
                    "WHERE ts_code = :ts_code "
                    "  AND trade_date BETWEEN :start AND :end "
                    "ORDER BY trade_date ASC"
                )
                result2 = await db.execute(query2, {
                    "ts_code": ts_code,
                    "start": start_date,
                    "end": end_date,
                })
                rows = result2.fetchall()

            from collections import namedtuple
            SimpleBar = namedtuple(
                "SimpleBar",
                ["ts_code", "trade_date", "open", "high", "low", "close", "volume", "amount"]
            )
            return [SimpleBar(
                ts_code=r.ts_code, trade_date=r.trade_date,
                open=float(r.open) if r.open else 0,
                high=float(r.high) if r.high else 0,
                low=float(r.low) if r.low else 0,
                close=float(r.close) if r.close else 0,
                volume=float(r.vol) if r.vol else 0,
                amount=float(r.amount) if r.amount else 0,
            ) for r in rows]

        except Exception as e:
            logger.error(f"load_stock_history 失败: {ts_code}: {e}")
            return None
