# -*- coding: utf-8 -*-
"""
策略管理器

负责策略的加载、初始化、运行控制、信号处理。
v1.1 重构: 移除硬编码注册，使用 StrategyRegistry；新增 handle_bar_batch / _publish_signals
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Type

from core.engines import BarData
from core.engines.base.engine_base import EngineBase, EngineConfigEntity
from core.engines.types.enums import EngineType
from modules.data.events import DataSyncCompletedEvent
from modules.strategy.constants import (
    StrategyType,
    StrategyLifecycleStatus,
    RunMode,
)
from modules.strategy.events import StrategyStartedEvent, StrategyStoppedEvent, StrategyPausedEvent, \
	StrategyResumedEvent
from modules.strategy.events.signal_events import SignalConfirmedEvent
from modules.strategy.models import (
    StrategyInstance,
    StrategyState,
    StrategyConfig,
    TradingSignal,
)
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.strategies.base.strategy_context import StrategyContext
from modules.strategy.engines.strategy_registry import StrategyRegistry
from modules.trade import OrderFilledEvent
from shared.database.repositories import strategy

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

    # ---- 动态代码加载（exec 沙箱，v2.4 新增） ----

    def _load_strategy_class_from_code(
        self, code: str
    ) -> Optional[Type[BaseStrategy]]:
        """
        从用户自定义代码字符串动态加载策略类（exec 沙箱）。

        与 BacktestService._load_strategy_class() 路径 B 逻辑一致，
        确保实盘模式也能执行用户通过 Web 编辑器保存的策略代码。

        Args:
            code: 策略源代码字符串（来自 strategies.code 字段）

        Returns:
            BaseStrategy 子类，未找到返回 None
        """
        try:
            from modules.strategy.strategies.base.base_strategy import BaseStrategy as BS
            from datetime import datetime as _dt
            from modules.strategy.constants import (
                StrategyType as ST, SignalDirection, SignalType as SigType, TimeFrame, RunMode,
            )
            from modules.strategy.models import TradingSignal, Position
            from core.engines.types.entities import BarData
            import numpy as np
            import pandas as pd
            import typing as _typing
            import logging as _logging

            temp_module: Dict[str, Any] = {
                "logging": _logging,
                "logger": _logging.getLogger(__name__),
                "BaseStrategy": BS,
                "StrategyType": ST,
                "SignalDirection": SignalDirection,
                "SignalType": SigType,
                "TimeFrame": TimeFrame,
                "RunMode": RunMode,
                "TradingSignal": TradingSignal,
                "Position": Position,
                "BarData": BarData,
                "pd": pd,
                "np": np,
                "datetime": _dt,
                "typing": _typing,
            }
            # v2.4: 注入常用 typing 名称，避免策略代码中裸用 Optional 报 NameError
            for _tname in ("Optional", "List", "Dict", "Tuple", "Set", "Union", "Any", "Callable", "Type"):
                if hasattr(_typing, _tname):
                    temp_module[_tname] = getattr(_typing, _tname)

            # v2.5: 注入策略专用依赖（兜底：防止旧策略代码仅含类体、缺少 import 导致 NameError）
            try:
                from modules.strategy.services.industry_scoring_service import (
                    IndustryScore, IndustryScoringService, ScoringConfig,
                )
                temp_module["IndustryScore"] = IndustryScore
                temp_module["IndustryScoringService"] = IndustryScoringService
                temp_module["ScoringConfig"] = ScoringConfig
            except ImportError:
                pass
            try:
                from modules.strategy.services.etf_industry_mapper import (
                    EtfIndustryMapper, EtfSelection,
                )
                temp_module["EtfIndustryMapper"] = EtfIndustryMapper
                temp_module["EtfSelection"] = EtfSelection
            except ImportError:
                pass
            try:
                from modules.strategy.enums.sector_groups import get_sector
                temp_module["get_sector"] = get_sector
            except ImportError:
                pass

            # v2.4: exec() 沙箱加固 — 全量 builtins，仅移除危险函数
            import builtins as _b
            safe_builtins = dict(vars(_b))
            # 移除可执行任意代码的危险函数
            for _danger in ("eval", "exec", "compile", "open", "input", "breakpoint"):
                safe_builtins.pop(_danger, None)
            # v2.6: 使用正确的模块路径作为 __name__，确保策略中
            # logging.getLogger(__name__) 的日志能沿标准层级传播到 root handler（含文件日志）
            safe_builtins["__name__"] = "modules.strategy.strategies.custom"
            temp_module["__builtins__"] = safe_builtins
            try:
                # v2.5: 若策略代码不含 from __future__ import annotations，
                # 则自动注入，避免类型注解（如 List[IndustryScore]）引发 NameError
                _code_to_exec = code or ""
                if "from __future__" not in _code_to_exec[:200]:
                    _code_to_exec = "from __future__ import annotations\n" + _code_to_exec
                exec(_code_to_exec, temp_module)
                # v2.6: 补全 logging 基础设施，logger 名与 __name__ 保持一致
                if "logging" not in temp_module:
                    temp_module["logging"] = _logging
                if "logger" not in temp_module:
                    temp_module["logger"] = _logging.getLogger(
                        temp_module.get("__name__", "strategy")
                    )
            except ModuleNotFoundError as e:
                missing = e.name or str(e)
                raise ValueError(f"缺少依赖模块: {missing}") from e
            except SyntaxError as e:
                raise ValueError(f"策略代码语法错误: {e}") from e

            # 提取第一个 BaseStrategy 子类
            for _name, obj in temp_module.items():
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BS)
                    and obj is not BS
                ):
                    logger.info(f"策略类加载成功 (exec 沙箱): {_name}")
                    return obj

            logger.warning("exec 沙箱中未找到 BaseStrategy 子类")
            return None

        except Exception as e:
            logger.error(f"exec 沙箱加载策略类失败: {e}")
            return None

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
        """加载策略 — v3.0: exec(code) 优先，registry 仅作回退。

        所有策略（内置模板创建的实例 + 自定义策略）统一走 exec 沙箱加载。
        这样用户编辑内置策略代码后，新实例能正确使用编辑后的代码。
        """
        strategy_class = None

        # v3.0: exec(code) 优先 — 确保用户编辑的代码生效
        if code:
            strategy_class = self._load_strategy_class_from_code(code)

        # 回退：无 code 的旧数据走 registry
        if not strategy_class:
            strategy_class = self.registry.get_first(strategy_type)
        if not strategy_class and strategy_type == StrategyType.CTA:
            strategy_class = self.registry.get_first(StrategyType.TECHNICAL)

        if not strategy_class:
            raise ValueError(f"未注册的策略类型: {strategy_type}")

        strategy = strategy_class(
            name=name,
            strategy_type=strategy_type,
            parameters=parameters,
        )
        # v2.5: 注入 DB 会话工厂，供策略 on_start 时加载历史预热数据
        if self.session_factory:
            strategy._db_session_factory = self.session_factory

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
            if not strategy_class and strategy_type == StrategyType.CTA:
                strategy_class = self.registry.get_first(StrategyType.TECHNICAL)
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

        # 同步状态到 DB（修复：之前只更新内存，前端看不到状态变更）
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    from shared.database.repositories.strategy.management import StrategyRepository
                    await StrategyRepository(session).update(
                        strategy_id,
                        {"status": StrategyLifecycleStatus.RUNNING.value, "updated_at": datetime.now()},
                    )
            except Exception as e:
                logger.warning(f"策略状态同步到DB失败: {e}")

        # v3.0: 仅实盘/仿真模式预热历史数据 + 恢复持仓（回测不需要）
        # 注意：strategy_instance.run_mode 在调用方 start_strategy() 返回后才设置，
        # 因此必须从 context.run_mode 读取，否则预热永远被跳过。
        _run_mode = getattr(context, "run_mode", None) or getattr(strategy_instance, "run_mode", RunMode.BACKTEST)
        if _run_mode in (RunMode.LIVE,):
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

                # v3.3: 检查代码默认参数与 DB 参数是否冲突
                instance = self.strategies.get(strategy_id)
                if instance and hasattr(instance, 'DEFAULT_PARAMS'):
                    try:
                        from shared.database.repositories.strategy.management.strategy_parameter_repo import (
                            StrategyParameterRepository
                        )
                        param_repo = StrategyParameterRepository(session)
                        db_params = await param_repo.get_by_strategy_id(strategy_id)
                        db_dict = {p.param_name: p.param_value for p in db_params}
                        for key, default_val in instance.DEFAULT_PARAMS.items():
                            if key in db_dict and db_dict[key] != default_val:
                                logger.info(
                                    f"策略 {strategy_id}: 参数 '{key}' DB值={db_dict[key]} "
                                    f"≠ 代码默认值={default_val}。使用DB值。如需更新为默认值，请删除此参数后重新保存。"
                                )
                    except Exception:
                        pass

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
            if 'BottomStrategy' in type(strategy).__name__:
                logger.debug(
                    '[HBB/OBJ] strategy_id=%s type=%s id=%s hasP4=%s p4buf=%d restored=%s',
                    str(strategy_id)[:8], type(strategy).__name__, id(strategy),
                    hasattr(strategy, '_p4_buffer'),
                    len(getattr(strategy, '_p4_buffer', {})),
                    getattr(strategy, '_confirm_restored', '?'),
                )

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
                        if 'BottomStrategy' in type(strategy).__name__:
                            logger.debug('[on_bar返回] %s -> %d 个信号 %s',
                                getattr(bar, 'ts_code', '?'),
                                len(sigs) if isinstance(sigs, list) else 1,
                                [getattr(s, 'ts_code', '?') for s in (sigs if isinstance(sigs, list) else [sigs])])
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

            # v6.2: 批次结束 hook — 当日全部 bar 推送完毕后调用（可选实现）。
            # 供需要"全市场当日数据就绪后统一决策"的策略（如低吸轮动全市场选股）
            # 使用：on_bar 仅缓存数据，调仓在此 hook 中执行，确保各股票缓存
            # 均已包含当日数据（信号仍走 T+1 撮合，无前视）。
            batch_end = getattr(strategy, "on_bar_batch_end", None)
            if callable(batch_end):
                try:
                    end_sigs = batch_end(trade_date)
                    if asyncio.iscoroutine(end_sigs):
                        end_sigs = await end_sigs
                    if end_sigs:
                        if isinstance(end_sigs, list):
                            strategy_signals.extend(end_sigs)
                        else:
                            strategy_signals.append(end_sigs)
                except Exception as e:
                    logger.error(
                        f"策略 {strategy_id} on_bar_batch_end 失败 @ {trade_date}: "
                        f"{type(e).__name__}: {e}",
                        exc_info=True,
                    )

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
                logger.info(
                    "[信号收集] 策略 %s @ %s: %d 个信号 ts=%s",
                    str(strategy_id)[:8], trade_date, len(strategy_signals),
                    [getattr(s, "ts_code", "?") for s in strategy_signals[:5]],
                )
                state.pending_signals.extend(strategy_signals)
                await self._publish_signals(strategy_id, strategy_signals)
                all_signals.extend(strategy_signals)
                # 发布后清除 pending 缓存，防止内存泄漏
                state.pending_signals = [s for s in state.pending_signals
                                          if s not in strategy_signals]

        logger.info(
            "[handle_bar_batch] %s 完成: %d 个信号, %d 个策略",
            trade_date, len(all_signals), len(self.running_states),
        )
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
        将策略生成的信号通过 EventEngine 发布。

        数据流:
        1. 创建 StrategySignalEvent（v2.0 含价格范围）
        2. 检测是否在后台线程中运行：
           - 主线程 → 直接 self.event_engine.put(event)
           - 后台线程 → bridge_queue.put(event) → 主线程 _bridge_pump() → event_engine.put(event)
        3. SignalEngine 订阅 → 写入 signals 超表 + WebSocket 推送
        """
        if not signals:
            return

        # 检测跨线程路径（仅实盘/仿真模式走 bridge；回测信号不发布到实盘管线）
        instance = self.strategies.get(strategy_id)
        run_mode = getattr(instance, "run_mode", "backtest") if instance else "backtest"
        if str(run_mode).lower() in ("live", "paper"):
            try:
                from shared.utils.background_executor import get_bridge_queue
                bq = get_bridge_queue()
            except ImportError:
                bq = None
            if bq is not None:
                self._publish_via_bridge(bq, strategy_id, signals)
                return

        # 主线程 → 直接发布
        if not self.event_engine:
            return

        try:
            from modules.strategy.events.signal_events import StrategySignalEvent

            instance = self.strategies.get(strategy_id)
            account_id = getattr(instance, "account_id", "") if instance else ""
            version_id = getattr(instance, "current_version_id", "") if instance else ""

            for sig in signals:
                sig_dict = sig.to_dict() if hasattr(sig, "to_dict") else {}

                event = StrategySignalEvent(
                    strategy_id=strategy_id,
                    strategy_name=instance.name if instance else "",
                    strategy_version_id=version_id,
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
                    run_mode=getattr(instance, "run_mode", "live") if instance else "live",
                    execution_mode=getattr(instance, "execution_mode", "semi_auto") if instance else "semi_auto",
                )
                await self.event_engine.put(event)

                logger.debug(
                    f"信号发布: {strategy_id} {sig_dict.get('ts_code')} "
                    f"{sig_dict.get('direction')} {sig_dict.get('signal_type')} "
                    f"价格区间 [{sig_dict.get('price_limit_low')}~{sig_dict.get('price_limit_high')}]"
                )

        except ImportError as e:
            logger.warning(f"无法导入 StrategySignalEvent: {e}")
        except Exception as e:
            logger.error(f"信号发布失败: {e}")

    def _publish_via_bridge(self, bq, strategy_id: str, signals: list) -> None:
        """后台线程路径 — 通过 bridge queue 将信号事件跨线程发布到主线程 EventEngine。

        不依赖 self.event_engine（asyncio.Lock 绑定了主线程 event loop）。
        """
        try:
            from modules.strategy.events.signal_events import StrategySignalEvent

            instance = self.strategies.get(strategy_id)
            account_id = getattr(instance, "account_id", "") if instance else ""
            version_id = getattr(instance, "current_version_id", "") if instance else ""

            for sig in signals:
                sig_dict = sig.to_dict() if hasattr(sig, "to_dict") else {}

                event = StrategySignalEvent(
                    strategy_id=strategy_id,
                    strategy_name=instance.name if instance else "",
                    strategy_version_id=version_id,
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
                    run_mode=getattr(instance, "run_mode", "live") if instance else "live",
                    execution_mode=getattr(instance, "execution_mode", "semi_auto") if instance else "semi_auto",
                )
                bq.put(event)

                logger.debug(
                    "信号入桥: %s %s %s %s",
                    strategy_id, sig_dict.get("ts_code"),
                    sig_dict.get("direction"), sig_dict.get("signal_type"),
                )
        except ImportError as e:
            logger.warning("无法导入 StrategySignalEvent (bridge): %s", e)
        except Exception as e:
            logger.error("信号桥接发布失败: %s", e)

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

        # v3.0: 同步内置策略到 strategy_templates 表（幂等）
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    from modules.strategy.services.template_service import TemplateService
                    svc = TemplateService(session)
                    result = await svc.seed_builtin_templates()
                    logger.info(f"内置模板同步完成: {result}")
            except Exception as e:
                logger.warning(f"内置模板同步失败（非致命）: {e}")

        logger.info("策略管理器初始化完成")

    async def _on_start(self):
        logger.info("策略管理器启动")
        if self.event_engine:
            try:

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

        # v2.3: 重启恢复 — 将 DB 中 status='running' 的策略重新加载到内存
        await self._recover_running_strategies()

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

    async def _load_daily_bars(
        self, trade_date: date, symbols: Optional[List[str]] = None,
    ) -> list:
        """
        加载指定交易日的 BarData（优先复权数据，fallback 原始数据）。

        v2.4: 使用 Repository 批量查询替代裸 SQL；支持 ETF 数据自动分派。
        """
        if self.session_factory is None:
            logger.error("_load_daily_bars: session_factory 未注入，无法加载数据")
            return []

        try:
            async with self.session_factory() as session:
                rows = []
                has_symbols = bool(symbols)

                if has_symbols:
                    # ---- 按指定股票池：拆分股票 / ETF，走 Repo 批量查询 ----
                    from shared.database.repositories.market.quote.stock_adjusted_price_repo import (
                        StockAdjustedPriceRepository,
                    )
                    from shared.database.repositories.market.quote.stock_daily_repo import (
                        StockDailyRepository,
                    )
                    from shared.database.repositories.market.basic.etf_repo import (
                        ETFRepository,
                    )

                    stock_syms = [s for s in symbols if not self._is_etf(s)]
                    etf_syms = [s for s in symbols if self._is_etf(s)]

                    # 股票：复权价格
                    if stock_syms:
                        adj_repo = StockAdjustedPriceRepository(session)
                        stock_rows = await adj_repo.get_batch_by_date_range(
                            symbols=stock_syms,
                            start_date=trade_date,
                            end_date=trade_date,
                            adj_type="qfq",
                            freq="D",
                        )
                        if stock_rows:
                            rows.extend(stock_rows)
                        else:
                            daily_repo = StockDailyRepository(session)
                            rows.extend(
                                await daily_repo.get_batch_by_date_range(
                                    symbols=stock_syms,
                                    start_date=trade_date,
                                    end_date=trade_date,
                                )
                            )

                    # ETF：复权日线
                    if etf_syms:
                        etf_repo = ETFRepository(session)
                        etf_dicts = await etf_repo.get_etf_adjusted_daily_batch(
                            symbols=etf_syms,
                            start_date=trade_date,
                            end_date=trade_date,
                        )
                        if etf_dicts:
                            rows.extend(etf_dicts)
                else:
                    # ---- 全市场：用 ORM select 保持类型安全（不写裸 SQL） ----
                    from shared.database.models.data_models import (
                        StockAdjustedPrices, StockDaily, EtfDaily, FundAdjFactor,
                    )
                    from sqlalchemy import select as sa_select

                    # 股票复权
                    q = sa_select(StockAdjustedPrices).where(
                        StockAdjustedPrices.trade_date == trade_date,
                        StockAdjustedPrices.adj_type == "qfq",
                        StockAdjustedPrices.freq == "D",
                    )
                    result = await session.execute(q)
                    rows = list(result.scalars().all())

                    if not rows:
                        q2 = sa_select(StockDaily).where(
                            StockDaily.trade_date == trade_date,
                        )
                        result2 = await session.execute(q2)
                        rows = list(result2.scalars().all())

                    # ETF 日线 + 复权因子 JOIN（全市场）
                    q3 = sa_select(
                        EtfDaily.ts_code, EtfDaily.trade_date,
                        (EtfDaily.open * FundAdjFactor.adj_factor).label("open"),
                        (EtfDaily.high * FundAdjFactor.adj_factor).label("high"),
                        (EtfDaily.low * FundAdjFactor.adj_factor).label("low"),
                        (EtfDaily.close * FundAdjFactor.adj_factor).label("close"),
                        EtfDaily.vol, EtfDaily.amount,
                    ).outerjoin(
                        FundAdjFactor,
                        (EtfDaily.ts_code == FundAdjFactor.ts_code)
                        & (EtfDaily.trade_date == FundAdjFactor.trade_date),
                    ).where(EtfDaily.trade_date == trade_date)
                    result3 = await session.execute(q3)
                    etf_rows = result3.fetchall()
                    if etf_rows:
                        rows.extend(etf_rows)

                # 转换为 BarData 对象
                bars = []
                for row in rows:
                    bar = self._row_to_bar(row)
                    if bar:
                        bars.append(bar)

                logger.info(
                    f"_load_daily_bars: {trade_date} 加载 {len(bars)} 条 BarData"
                    + (f" (symbols={len(symbols)} 只)" if has_symbols else " (全市场)")
                )
                return bars

        except Exception as e:
            logger.error(f"加载 BarData 失败: {trade_date}: {e}")
            return []

    async def _load_daily_bars_range(
        self, start_date: date, end_date: date, symbols: Optional[List[str]] = None,
    ) -> Dict[date, list]:
        """
        加载日期范围内每日的 BarData，按 trade_date 分组返回。

        v2.4: 使用 Repository 批量查询替代裸 SQL；支持 ETF 数据。
        """
        if self.session_factory is None:
            return {}

        try:
            async with self.session_factory() as session:
                rows = []
                has_symbols = bool(symbols)

                if has_symbols:
                    from shared.database.repositories.market.quote.stock_adjusted_price_repo import (
                        StockAdjustedPriceRepository,
                    )
                    from shared.database.repositories.market.quote.stock_daily_repo import (
                        StockDailyRepository,
                    )
                    from shared.database.repositories.market.basic.etf_repo import (
                        ETFRepository,
                    )

                    stock_syms = [s for s in symbols if not self._is_etf(s)]
                    etf_syms = [s for s in symbols if self._is_etf(s)]

                    if stock_syms:
                        adj_repo = StockAdjustedPriceRepository(session)
                        stock_rows = await adj_repo.get_batch_by_date_range(
                            symbols=stock_syms,
                            start_date=start_date,
                            end_date=end_date,
                            adj_type="qfq",
                            freq="D",
                        )
                        if stock_rows:
                            rows.extend(stock_rows)
                        else:
                            daily_repo = StockDailyRepository(session)
                            rows.extend(
                                await daily_repo.get_batch_by_date_range(
                                    symbols=stock_syms,
                                    start_date=start_date,
                                    end_date=end_date,
                                )
                            )

                    if etf_syms:
                        etf_repo = ETFRepository(session)
                        etf_dicts = await etf_repo.get_etf_adjusted_daily_batch(
                            symbols=etf_syms,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        if etf_dicts:
                            rows.extend(etf_dicts)
                else:
                    from shared.database.models.data_models import (
                        StockAdjustedPrices, StockDaily, EtfDaily, FundAdjFactor,
                    )
                    from sqlalchemy import select as sa_select

                    q = sa_select(StockAdjustedPrices).where(
                        StockAdjustedPrices.trade_date.between(start_date, end_date),
                        StockAdjustedPrices.adj_type == "qfq",
                        StockAdjustedPrices.freq == "D",
                    )
                    result = await session.execute(q)
                    rows = list(result.scalars().all())

                    if not rows:
                        q2 = sa_select(StockDaily).where(
                            StockDaily.trade_date.between(start_date, end_date),
                        )
                        result2 = await session.execute(q2)
                        rows = list(result2.scalars().all())

                    q3 = sa_select(
                        EtfDaily.ts_code, EtfDaily.trade_date,
                        (EtfDaily.open * FundAdjFactor.adj_factor).label("open"),
                        (EtfDaily.high * FundAdjFactor.adj_factor).label("high"),
                        (EtfDaily.low * FundAdjFactor.adj_factor).label("low"),
                        (EtfDaily.close * FundAdjFactor.adj_factor).label("close"),
                        EtfDaily.vol, EtfDaily.amount,
                    ).outerjoin(
                        FundAdjFactor,
                        (EtfDaily.ts_code == FundAdjFactor.ts_code)
                        & (EtfDaily.trade_date == FundAdjFactor.trade_date),
                    ).where(EtfDaily.trade_date.between(start_date, end_date))
                    result3 = await session.execute(q3)
                    etf_rows = result3.fetchall()
                    if etf_rows:
                        rows.extend(etf_rows)

                bars_by_date: Dict[date, list] = {}
                for row in rows:
                    bar = self._row_to_bar(row)
                    if bar:
                        td = row["trade_date"] if isinstance(row, dict) else row.trade_date
                        if hasattr(td, "date"):
                            td = td.date()
                        if td not in bars_by_date:
                            bars_by_date[td] = []
                        bars_by_date[td].append(bar)

                return bars_by_date

        except Exception as e:
            logger.error(f"加载 BarData 范围失败: {start_date}~{end_date}: {e}")
            return {}

    @staticmethod
    def _is_etf(ts_code: str) -> bool:
        """判断是否为 ETF 代码（与 DataFeedEngine._is_etf 保持一致）。"""
        if not ts_code:
            return False
        return (
            ts_code.endswith(".OF")
            or (len(ts_code) >= 6 and ts_code[:2] in ("51", "56", "58", "15"))
        )

    @staticmethod
    def _row_to_bar(row) -> object:
        """将数据库行（ORM 对象或 dict）转为 BarData 对象"""
        try:

            if isinstance(row, dict):
                return BarData(
                    ts_code=row["ts_code"],
                    period="daily",
                    trade_date=row.get("trade_date"),
                    open=float(row["open"]) if row["open"] else 0,
                    high=float(row["high"]) if row["high"] else 0,
                    low=float(row["low"]) if row["low"] else 0,
                    close=float(row["close"]) if row["close"] else 0,
                    volume=float(row["volume"]) if row.get("volume") else 0,
                    amount=float(row["amount"]) if row.get("amount") else 0,
                )

            return BarData(
                ts_code=row.ts_code,
                period="daily",
                trade_date=row.trade_date,
                open=float(row.open) if row.open else 0,
                high=float(row.high) if row.high else 0,
                low=float(row.low) if row.low else 0,
                close=float(row.close) if row.close else 0,
                volume=float(row.vol) if row.vol else 0,
                amount=float(row.amount) if row.amount else 0,
            )
        except (ImportError, AttributeError):
            from collections import namedtuple
            SimpleBar = namedtuple(
                "SimpleBar",
                ["ts_code", "trade_date", "open", "high", "low", "close",
                 "volume", "amount", "trade_time"]
            )
            if isinstance(row, dict):
                return SimpleBar(
                    ts_code=row["ts_code"],
                    trade_date=row.get("trade_date"),
                    open=float(row["open"]) if row["open"] else 0,
                    high=float(row["high"]) if row["high"] else 0,
                    low=float(row["low"]) if row["low"] else 0,
                    close=float(row["close"]) if row["close"] else 0,
                    volume=float(row["volume"]) if row.get("volume") else 0,
                    amount=float(row["amount"]) if row.get("amount") else 0,
                    trade_time=None,
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
                trade_time=None,
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
            # v3.4: 注入实盘状态——必须在实际策略对象上调用（非 wrapper）
            strategy_obj = self._strategy_objects.get(strategy_id)
            if strategy_obj and hasattr(strategy_obj, 'load_live_state') and self.session_factory:
                async with self.session_factory() as _db:
                    await strategy_obj.load_live_state(_db, strategy_id=str(strategy_id))
            pending_map = await self._check_yesterday_pending(strategy_id, trade_date)

            # 过滤：昨天 pending 的同方向股票跳过，避免重复发信号
            filtered_bars = []
            for bar in bars:
                ts_code = getattr(bar, "ts_code", "") or getattr(bar, "symbol", "")
                if ts_code in pending_map:
                    prev = pending_map[ts_code]
                    if prev.get("direction", "") in ("long", "buy"):
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
            strategy_obj = self._strategy_objects.get(strategy_id)
            heartbeat = {
                "trade_date": str(trade_date),
                "signals_count": len(signals),
                "positions_count": (
                    len(strategy_obj.positions) +
                    len(getattr(strategy_obj, "_active_positions", {}))
                ) if strategy_obj else 0,
                "data_cached": len(getattr(strategy_obj, "_data_cache", {})) if strategy_obj else 0,
                "updated_at": datetime.now().isoformat(),
            }
            state.today_trades += len(signals)
            state.total_trades += len(signals)

            # v3.0: 盘后保存策略状态（含心跳）
            await self._save_strategy_state(strategy_id, heartbeat)
            await self._update_heartbeat(strategy_id, heartbeat)

            # v3.4: 策略诊断（所有策略自动启用，子类覆写 get_daily_diagnostic 提供详情）
            diag = None
            if strategy_obj and hasattr(strategy_obj, "get_daily_diagnostic"):
                diag = strategy_obj.get_daily_diagnostic()

            logger.info(
                "策略每日运行: %s @ %s | 信号: %d | 持仓: %d | 数据缓存: %d 只",
                strategy_id, trade_date, len(signals),
                heartbeat["positions_count"], heartbeat["data_cached"],
            )
            if diag:
                logger.info("[策略诊断] %s: %s", str(strategy_id)[:8], diag)

        logger.info(
            f"_run_live_strategies: {trade_date} 完成, "
            f"{len(all_signals)} 个信号, "
            f"{len(self.running_states)} 个运行中策略"
        )
        return all_signals

    # ---- v2.3: 手动触发（开发调试工具） ----

    async def trigger_strategy(
        self,
        strategy_id: str,
        trade_date: date,
        end_date: Optional[date] = None,
        symbols: Optional[List[str]] = None,
        skip_pending_check: bool = False,
    ) -> Dict[str, Any]:
        """
        手动触发单个策略在指定交易日执行（开发调试工具）。

        v2.3: 支持 end_date 日期范围，逐日循环触发。

        与 _run_live_strategies 的区别：
        - 只驱动指定策略，不遍历所有运行中策略
        - 不检查 run_mode（允许任意模式）
        - 不执行中断检测和补跑
        - 可选跳过 pending 检查（便于重复测试同一日期）
        - 不更新 last_run_date / heartbeat（不干扰正常日终调度）
        - 使用 session_factory 获取 DB 会话

        Args:
            strategy_id: 策略 ID
            trade_date: 交易日
            symbols: 股票池（可选，默认使用策略参数的 symbols/universe）
            skip_pending_check: 跳过昨日 pending 过滤（默认 False）

        Returns:
            {
                strategy_id, strategy_name, trade_date,
                bars_loaded, symbols_used, signals_generated,
                signals: [{ts_code, direction, signal_type, price,
                           quantity, confidence, reason, status}]
            }
        """
        # 0. 前置校验
        instance = self.strategies.get(strategy_id)
        if not instance:
            return {"success": False, "error": f"策略 {strategy_id} 未加载"}

        strategy = self._strategy_objects.get(strategy_id)
        if not strategy:
            return {"success": False, "error": f"策略 {strategy_id} 对象未找到"}

        # 策略股票池解析
        full_market = False
        if symbols is None:
            params = getattr(instance, "parameters", {}) or {}
            raw_symbols = list(params.get("symbols") or [])
            raw_universe = params.get("universe") or []
            # 避免字符串（如 "all_market"）被 list() 拆成单个字符
            if isinstance(raw_universe, str):
                raw_universe = [raw_universe]
            else:
                raw_universe = list(raw_universe)
            symbols = raw_symbols or raw_universe or list(getattr(strategy, "_universe", []))
        if not symbols:
            # 未指定股票池 → 全市场模式，由策略 on_bar 自行筛选
            full_market = True
            symbols = None  # 传 None 给 _load_daily_bars 加载全市场

        strategy_name = instance.name

        # 构建日期列表
        if end_date is None:
            end_date = trade_date
        date_list: List[date] = []
        d = trade_date
        while d <= end_date:
            date_list.append(d)
            d += timedelta(days=1)

        symbol_desc = f"{len(symbols)} 只" if symbols else "全市场"
        logger.info(
            f"手动触发策略: {strategy_id} ({strategy_name}) {trade_date}"
            + (f" ~ {end_date}" if end_date != trade_date else "")
            + f", symbols={symbol_desc}, skip_pending={skip_pending_check}"
        )

        # 1. 预热历史数据（静默回放，不产生信号）
        # v3.5: 若策略已有足够缓存数据（实盘运行中），跳过预热直接使用
        data_cache = getattr(strategy, "_data_cache", None)
        cache_ready = data_cache and len(data_cache) >= 100  # 已缓存 ≥100 只股票

        if not cache_ready:
            strategy.clear_signals()
            if hasattr(strategy, "_price_data"):
                strategy._price_data = strategy._price_data.iloc[0:0]
            for attr in ("_data_cache", "_last_signal"):
                if hasattr(strategy, attr):
                    setattr(strategy, attr, None if attr == "_last_signal" else {})

        if not cache_ready and symbols:
            lookback_start = trade_date - timedelta(days=365)
            warmup_bars = await self._load_daily_bars_range(
                lookback_start, trade_date - timedelta(days=1), symbols=symbols,
            )
            if warmup_bars:
                warmup_count = sum(len(b) for b in warmup_bars.values())
                logger.info(
                    f"手动触发: {strategy_id} 预热 {warmup_count} 条历史 bar, "
                    f"{len(warmup_bars)} 个交易日"
                )
                for dt in sorted(warmup_bars.keys()):
                    for bar in warmup_bars[dt]:
                        try:
                            strategy.on_bar(bar)
                        except Exception:
                            pass
                strategy.clear_signals()
            del warmup_bars
        elif cache_ready:
            strategy.clear_signals()  # 只清信号，不清缓存
            logger.info(
                f"手动触发: {strategy_id} 跳过预热（已有 {len(data_cache)} 只股票缓存）"
            )

        total_bars = 0
        total_signals = 0
        all_valid_signals: List[TradingSignal] = []
        daily_results: List[Dict] = []

        for cur_date in date_list:
            # 2. 加载当日 BarData
            bars = await self._load_daily_bars(cur_date, symbols=symbols)
            if not bars:
                daily_results.append({"trade_date": str(cur_date), "bars": 0, "signals": 0})
                continue

            # 3. pending 过滤
            pending_map: Dict[str, Dict] = {}
            if not skip_pending_check:
                try:
                    pending_map = await self._check_yesterday_pending(strategy_id, cur_date)
                except Exception:
                    pass

            filtered_bars = []
            for bar in bars:
                ts_code = getattr(bar, "ts_code", "") or getattr(bar, "symbol", "")
                if ts_code not in pending_map:
                    filtered_bars.append(bar)

            # 4. 逐 bar 驱动策略
            day_signals: List[TradingSignal] = []
            bar_error_count = 0
            for bar in filtered_bars:
                try:
                    sigs = strategy.on_bar(bar)
                    if asyncio.iscoroutine(sigs):
                        sigs = await sigs
                    if sigs:
                        if isinstance(sigs, list):
                            day_signals.extend(sigs)
                        else:
                            day_signals.append(sigs)
                except Exception as e:
                    bar_error_count += 1

            # 5. 调用 on_bar_batch_end（部分策略在此生成信号，如 StockLowHighStrategy）
            batch_end = getattr(strategy, "on_bar_batch_end", None)
            if batch_end:
                try:
                    batch_sigs = batch_end(cur_date)
                    if batch_sigs:
                        if isinstance(batch_sigs, list):
                            day_signals.extend(batch_sigs)
                        else:
                            day_signals.append(batch_sigs)
                except Exception as e:
                    logger.warning(f"trigger_strategy on_bar_batch_end 失败: {e}")

            # 6. 收集 add_signal() 信号
            if strategy.signals:
                day_signals.extend(strategy.signals)
                strategy.clear_signals()

            # 6. 信号验证
            valid = [s for s in day_signals if strategy.validate_signal(s) if not isinstance(strategy.validate_signal(s), Exception)]

            valid_day = []
            for sig in day_signals:
                try:
                    if strategy.validate_signal(sig):
                        valid_day.append(sig)
                except Exception:
                    valid_day.append(sig)

            total_bars += len(filtered_bars)
            total_signals += len(valid_day)
            all_valid_signals.extend(valid_day)

            daily_results.append({
                "trade_date": str(cur_date),
                "bars": len(filtered_bars),
                "signals": len(valid_day),
            })

        # 7. 发布所有信号
        if all_valid_signals:
            await self._publish_signals(strategy_id, all_valid_signals)

        # 8. 构造信号摘要
        signal_summaries = []
        for sig in all_valid_signals:
            sig_dict = sig.to_dict() if hasattr(sig, "to_dict") else {}
            signal_summaries.append({
                "ts_code": sig_dict.get("ts_code", ""),
                "direction": sig_dict.get("direction", ""),
                "signal_type": sig_dict.get("signal_type", ""),
                "price": sig_dict.get("price", 0.0),
                "quantity": sig_dict.get("quantity", 0),
                "confidence": sig_dict.get("confidence", 1.0),
                "reason": sig_dict.get("reason", ""),
                "status": "pending_manual",
            })

        logger.info(
            f"手动触发完成: {strategy_id} {trade_date}"
            + (f"~{end_date}" if end_date != trade_date else "")
            + f" | {len(date_list)} 天, bars={total_bars}, signals={total_signals}"
        )

        return {
            "success": True,
            "data": {
                "strategy_id": strategy_id,
                "strategy_name": strategy_name,
                "trade_date": str(trade_date),
                "end_date": str(end_date) if end_date != trade_date else None,
                "days_processed": len(date_list),
                "daily": daily_results,
                "bars_loaded": total_bars,
                "symbols_used": symbols if symbols else ["全市场"],
                "signals_generated": total_signals,
                "signals": signal_summaries,
            },
        }

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
        # v3.4: 静默回放后重置策略状态，避免污染今日正式处理
        if hasattr(strategy, "_reset_diag"):
            strategy._diag = strategy._reset_diag()
        for attr in ("_position_entry", "_p4_buffer", "_track_high", "_cooling"):
            if hasattr(strategy, attr):
                getattr(strategy, attr).clear()
        # P4 确认缓冲区在回放中被消费掉了，重置标志让今天正式 bar 触发重建
        if hasattr(strategy, "_confirm_restored"):
            strategy._confirm_restored = False

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

            # v3.5: 先清理内存中的旧持仓数据，确保 DB 是唯一真相源。
            # 否则手动卖出后 DB 已清空但内存字典仍保留脏数据，
            # 导致策略误判当前持仓数量（current_holdings = _holdings | _active_positions）。
            strategy.positions.clear()
            if hasattr(strategy, "_holdings"):
                strategy._holdings.clear()
            if hasattr(strategy, "_track_high"):
                strategy._track_high.clear()

            sm = get_session_manager()
            async with sm.get_session() as session:
                repo = PositionRepository(session)
                db_positions = await repo.get_by_strategy(str(strategy_id))

            restored = 0
            for pos in db_positions:
                qty = pos.volume
                if qty > 0:
                    avg_price = float(pos.cost_price) if pos.cost_price else 0
                    side = getattr(pos, "side", "long") or "long"
                    strategy.update_position(
                        ts_code=pos.ts_code,
                        side=side,
                        quantity=qty,
                        avg_price=avg_price,
                    )
                    restored += 1

                    # v3.2: 同步恢复策略内部的 _holdings 字典（低吸轮动等策略依赖此字典决策）
                    # weight=1.0 代表满仓权重，shares=qty 为 DB 中的实际股数。
                    # _track_high 初始设为 avg_price（成本价），重启恢复流程中
                    # _recover_running_strategies 会用 state_snapshot 中的精确历史高点覆盖。
                    if hasattr(strategy, "_holdings"):
                        strategy._holdings[pos.ts_code] = {
                            "entry_price": avg_price,
                            "weight": 1.0,
                            "shares": qty,
                            "locked": False,
                        }
                    if hasattr(strategy, "_track_high"):
                        strategy._track_high[pos.ts_code] = avg_price

            if restored:
                logger.info("策略 %s: 从 DB 恢复了 %d 只股票的持仓", strategy_id, restored)
        except Exception as e:
            logger.warning("策略 %s 仓位恢复失败（跳过）: %s", strategy_id, e)

    # ==================== v2.3 重启恢复 ====================

    async def _recover_running_strategies(self) -> None:
        """
        重启后从 DB 恢复所有 status='running' 的策略到内存。

        在 _on_start 末尾调用，确保事件订阅就绪后再加载策略。
        恢复包括：strategy 实例、strategy_run 记录、state_snapshot 状态。
        """
        if self.session_factory is None:
            logger.warning("session_factory 未注入，跳过策略恢复")
            return

        try:
            from sqlalchemy import text

            async with self.session_factory() as session:
                # 查询所有 status='running' 的策略
                result = await session.execute(
                    text(
                        "SELECT id, name, user_id, strategy_type, code, status, "
                        "run_mode, execution_mode, account_id, allocated_capital "
                        "FROM strategies WHERE status = 'running'"
                    )
                )
                running_rows = result.fetchall()

                if not running_rows:
                    logger.info("重启恢复: 没有需要恢复的运行中策略")
                    return

                logger.info(f"重启恢复: 发现 {len(running_rows)} 个运行中策略，开始恢复...")

                recovered = 0
                failed = 0

                for row in running_rows:
                    sid = row[0]
                    try:
                        # 检查是否已在内存中（避免重复加载）
                        if sid in self.strategies:
                            logger.info(f"重启恢复: 策略 {sid} 已在内存中，跳过")
                            recovered += 1
                            continue


                        # row: 0=id, 1=name, 2=user_id, 3=strategy_type,
                        #      4=code, 5=status, 6=run_mode, 7=execution_mode,
                        #      8=account_id, 9=allocated_capital
                        strategy_type = StrategyType(row[3]) if row[3] else StrategyType.CTA
                        run_mode_str = row[6] or "live"
                        execution_mode_str = row[7] or "semi_auto"
                        account_id = row[8] or ""
                        capital = float(row[9]) if row[9] else 1000000.0

                        # 加载策略类 + 实例化
                        _code_to_load = row[4] or ""
                        logger.info(
                            '[BOOT/CODE] 策略 %s code=%d字节 hasTRACE=%s',
                            sid, len(_code_to_load),
                            '[TRACE]' in _code_to_load,
                        )
                        await self.load_strategy(
                            strategy_id=sid,
                            name=row[1] or sid,
                            strategy_type=strategy_type,
                            code=_code_to_load,
                            parameters={},
                            config=StrategyConfig(
                                user_id=str(row[2]) if row[2] else "0",
                                initial_capital=capital,
                            ),
                        )
                        # 构建上下文
                        context = StrategyContext(
                            strategy_id=sid,
                            strategy_name=row[1] or sid,
                            user_id=row[2] or "0",
                            run_mode=RunMode(run_mode_str) if run_mode_str else RunMode.LIVE,
                            initial_capital=capital,
                        )

                        # 注入 callback
                        StrategyContextBuilder.inject_callbacks(
                            context=context,
                            strategy_manager=self,
                            strategy_id=sid,
                            run_mode=RunMode(run_mode_str) if run_mode_str else RunMode.LIVE,
                        )

                        # 初始化 + 启动（恢复时状态已是 RUNNING，先改回 DRAFT 以通过 can_start 检查）
                        instance_before = self.strategies.get(sid)
                        if instance_before:
                            instance_before.status = StrategyLifecycleStatus.DRAFT
                        await self.initialize_strategy(sid, context)
                        await self.start_strategy(sid, context)

                        # 设置 run_mode / execution_mode / account_id
                        from modules.strategy.constants import ExecutionMode

                        instance = self.strategies.get(sid)
                        if instance:
                            instance.run_mode = RunMode(run_mode_str) if run_mode_str else RunMode.LIVE
                            instance.execution_mode = (
                                ExecutionMode(execution_mode_str)
                                if execution_mode_str else ExecutionMode.SEMI_AUTO
                            )
                            instance.account_id = account_id

                        # 从 state_snapshot 恢复 last_run_date 等运行时状态
                        run_result = await session.execute(
                            text(
                                "SELECT state_snapshot FROM strategy_runs "
                                "WHERE strategy_id = :sid AND status = 'running' "
                                "ORDER BY started_at DESC LIMIT 1"
                            ),
                            {"sid": sid},
                        )
                        run_row = run_result.fetchone()
                        if run_row and run_row[0]:
                            import json
                            snap = run_row[0] if isinstance(run_row[0], dict) else json.loads(run_row[0])
                            last_date_str = snap.get("last_trade_date")
                            if last_date_str and str(sid) in self.running_states:
                                from datetime import date as date_type
                                try:
                                    self.running_states[str(sid)].last_run_date = (
                                        date_type.fromisoformat(last_date_str)
                                    )
                                except (ValueError, TypeError):
                                    pass

                            # v3.2: 恢复策略累积状态（防 phantom drawdown + 回撤连续性）
                            strategy_obj = self._strategy_objects.get(sid)
                            if strategy_obj:
                                if hasattr(strategy_obj, "_exited_entry_value"):
                                    strategy_obj._exited_entry_value = float(
                                        snap.get("_exited_entry_value", 0)
                                    )
                                if hasattr(strategy_obj, "_exited_cash_value"):
                                    strategy_obj._exited_cash_value = float(
                                        snap.get("_exited_cash_value", 0)
                                    )
                                if hasattr(strategy_obj, "_peak_return"):
                                    strategy_obj._peak_return = float(
                                        snap.get("_peak_return", -999.0)
                                    )
                                # 恢复 _track_high（覆盖 _restore_positions_from_db 设置的 avg_price 兜底值）
                                if hasattr(strategy_obj, "_track_high") and snap.get("_track_high"):
                                    for ts_code, high_val in snap["_track_high"].items():
                                        strategy_obj._track_high[ts_code] = float(high_val)
                                    logger.info(
                                        "重启恢复: 策略 %s 恢复了 %d 只股票的 _track_high 历史高点",
                                        sid, len(snap["_track_high"]),
                                    )
                                logger.info(
                                    "重启恢复: 策略 %s 累积状态已恢复 "
                                    "(exited_entry=%.2f, exited_cash=%.2f, peak=%.4f)",
                                    sid,
                                    getattr(strategy_obj, "_exited_entry_value", 0),
                                    getattr(strategy_obj, "_exited_cash_value", 0),
                                    getattr(strategy_obj, "_peak_return", -999.0),
                                )

                        recovered += 1
                        logger.info(
                            f"重启恢复: 策略 {sid} ({row[1]}) 已恢复, "
                            f"run_mode={run_mode_str}, execution_mode={execution_mode_str}, "
                            f"capital={capital}"
                        )

                    except Exception as e:
                        failed += 1
                        logger.error(
                            f"重启恢复: 策略 {sid} 恢复失败: {type(e).__name__}: {e}",
                            exc_info=True,
                        )

                logger.info(
                    f"重启恢复完成: 成功 {recovered}, 失败 {failed}, "
                    f"总计 {len(running_rows)} 个策略"
                )

        except Exception as e:
            logger.error(f"重启恢复异常: {type(e).__name__}: {e}", exc_info=True)

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
                    "until": yesterday,  # 严格昨天及之前，不含今天
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
        """启动时加载 N 根历史 K 线，静默回放以预热策略指标。

        v2.4: 使用 Repository 批量加载（替代已删除的 data_feed_engine.load_stock_data）。
        """
        strategy = self._strategy_objects.get(strategy_id)
        if not strategy:
            return

        if ts_codes is None:
            instance = self.strategies.get(strategy_id)
            params = {}
            if instance and hasattr(instance, "parameters"):
                params = instance.parameters or {}
            # v3.2: instance.parameters 在恢复时可能为空，回退到策略对象的合并参数
            if not params:
                params = getattr(strategy, "parameters", {}) or {}
            raw = params.get("symbols") or params.get("universe") or params.get("etf_pool") or []
            # 避免 list("all_market") → ['a','l','l','_',...] 的拆字 Bug
            if isinstance(raw, str):
                ts_codes = [raw]
            else:
                ts_codes = list(raw)

        # 如果 instance.parameters 中没有，回退到策略对象的 universe property
        if not ts_codes:
            strategy_obj = self._strategy_objects.get(strategy_id)
            if strategy_obj and strategy_obj.universe:
                ts_codes = list(strategy_obj.universe)

        if not ts_codes:
            logger.info("策略 %s 无股票池，跳过预热", strategy_id)
            return

        # v3.2: 全市场策略快速预热 — 直接填充 _data_cache 而不触发 on_bar/rebalance
        if ts_codes == ["all_market"] or "all_market" in ts_codes:
            await self._warmup_all_market(strategy_id, strategy)
            return

        if self.session_factory is None:
            logger.warning("策略 %s session_factory 未注入，跳过预热", strategy_id)
            return

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback * 2)

        try:
            bars_by_date = await self._load_daily_bars_range(
                start_date, end_date, symbols=ts_codes,
            )
        except Exception as e:
            logger.warning("策略 %s 预热数据加载失败: %s", strategy_id, e)
            return

        if not bars_by_date:
            logger.info("策略 %s 预热数据为空，跳过", strategy_id)
            return

        loaded = 0
        for dt in sorted(bars_by_date.keys()):
            for bar in bars_by_date[dt]:
                try:
                    result = strategy.on_bar(bar)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass
        strategy.clear_signals()

        n_bars = sum(len(b) for b in bars_by_date.values())
        n_days = len(bars_by_date)

        # 显式释放预热临时数据
        bars_by_date.clear()
        del bars_by_date

        logger.info(
            "策略 %s 预热完成: %d 个交易日 / %d 条 bar, lookback=%d",
            strategy_id, n_days, n_bars, lookback,
        )

        # 强制 GC + 尝试归还内存给 OS（降低进程 RSS）
        import gc as _gc
        _gc.collect()
        try:
            import ctypes
            ctypes.CDLL("ucrtbase").malloc_trim(0)
        except Exception:
            pass

    async def _warmup_all_market(self, strategy_id: str, strategy) -> None:
        """
        v3.2: 全市场策略快速预热。

        全市场扫描类策略（如 StockLowHighStrategy）的股票池为动态全 A 股，
        无法通过逐条 on_bar() 回放来预热（每根 bar 触发 _run_rebalance 会导致
        O(N²) 全市场扫描，5000 股 × 60 天 ~ 30 万次完整扫描不可接受）。

        此方法直接查询 DB → 按 ts_code 分组构造 DataFrame → 写入 _data_cache，
        绕过 on_bar/rebalance，实现 O(N) 时间的数据预填充。

        预热后 _data_cache 直接可用，策略首个交易日即可正常选股。
        """
        if self.session_factory is None:
            logger.warning("策略 %s session_factory 未注入，跳过全市场预热", strategy_id)
            return

        from datetime import date as date_type, timedelta
        from sqlalchemy import text
        import pandas as pd

        # 从策略对象参数获取回看天数（默认 60）
        # 注意：使用 strategy.parameters（策略实例的合并参数）而非 instance.parameters（包装器参数，
        # 重启恢复时包装器参数可能为空字典）
        params = getattr(strategy, "parameters", {}) or {}
        lookback = int(params.get("lookback_days", 60))

        end_date = date_type.today()
        start_date = end_date - timedelta(days=lookback * 2)  # 留余量覆盖非交易日

        try:
            async with self.session_factory() as session:
                from shared.database.repositories.market.quote.stock_adjusted_price_repo import (
                    StockAdjustedPriceRepository,
                )
                from shared.database.repositories.market.quote.stock_daily_repo import (
                    StockDailyRepository,
                )

                # 1. 获取全 A 股主板代码（00/60 开头）
                all_codes_result = await session.execute(
                    text(
                        "SELECT DISTINCT ts_code FROM stock_basic "
                        "WHERE (ts_code LIKE '000%' OR ts_code LIKE '002%' "
                        "   OR ts_code LIKE '600%' OR ts_code LIKE '601%' "
                        "   OR ts_code LIKE '603%' OR ts_code LIKE '605%')"
                    )
                )
                all_codes = [r[0] for r in all_codes_result.fetchall()]
                if not all_codes:
                    logger.warning("策略 %s 全市场预热: 未找到主板股票代码", strategy_id)
                    return

                logger.info(
                    "策略 %s 全市场预热: 加载 %d 只股票, lookback=%d 天...",
                    strategy_id, len(all_codes), lookback,
                )

                # 2. 批量加载日线数据
                adj_repo = StockAdjustedPriceRepository(session)
                rows = await adj_repo.get_batch_by_date_range(
                    symbols=all_codes,
                    start_date=start_date,
                    end_date=end_date,
                    adj_type="qfq",
                    freq="D",
                )
                if not rows:
                    daily_repo = StockDailyRepository(session)
                    rows = await daily_repo.get_batch_by_date_range(
                        symbols=all_codes,
                        start_date=start_date,
                        end_date=end_date,
                    )

                if not rows:
                    logger.warning("策略 %s 全市场预热: 日线数据为空", strategy_id)
                    return

                # 3. 按 ts_code 分组，直接构造 DataFrame 写入 _data_cache
                rows_by_code: dict = {}
                for r in rows:
                    code = r.ts_code if hasattr(r, "ts_code") else r["ts_code"]
                    td = r.trade_date if hasattr(r, "trade_date") else r["trade_date"]
                    if code not in rows_by_code:
                        rows_by_code[code] = []
                    rows_by_code[code].append({
                        "trade_date": td,
                        "close": float(r.close if hasattr(r, "close") else r["close"] or 0),
                        "open": float(r.open if hasattr(r, "open") else r["open"] or 0),
                        "high": float(r.high if hasattr(r, "high") else r["high"] or 0),
                        "low": float(r.low if hasattr(r, "low") else r["low"] or 0),
                        "volume": float(r.vol if hasattr(r, "vol") else (r["vol"] or r.get("volume", 0) or 0)),
                        "amount": float(r.amount if hasattr(r, "amount") else (r.get("amount", 0) or 0)),
                    })

                populated = 0
                for code, recs in rows_by_code.items():
                    if len(recs) < 2:
                        continue
                    df = pd.DataFrame(recs)
                    df = df.sort_values("trade_date").reset_index(drop=True)
                    df = df[["close", "volume", "amount", "open", "high", "low"]]
                    # 限制缓存行数（与 _append_data 的 tail(120) 一致）
                    if len(df) > 120:
                        df = df.tail(120).reset_index(drop=True)
                    strategy._data_cache[code] = df
                    populated += 1

                logger.info(
                    "策略 %s 全市场预热完成: %d/%d 只股票已填充数据缓存 "
                    "(lookback=%d 天, 总行数=%d)",
                    strategy_id, populated, len(all_codes), lookback, len(rows),
                )

                # 释放临时构建数据并归还内存给 OS
                rows_by_code.clear()
                del rows_by_code, rows, all_codes
                import gc as _gc
                _gc.collect()
                try:
                    import ctypes
                    ctypes.CDLL("ucrtbase").malloc_trim(0)
                except Exception:
                    pass

        except Exception as e:
            logger.warning(
                "策略 %s 全市场预热失败（跳过，策略将自然积累数据）: %s",
                strategy_id, e,
            )

    @staticmethod
    def _safe_last_date(df):
        """安全获取 DataFrame 最后一条数据的日期字符串，兼容 RangeIndex 和 DatetimeIndex。"""
        try:
            last_val = df.index[-1]
            if hasattr(last_val, 'date'):
                return str(last_val.date())
            # RangeIndex → 回退到 trade_date 列或行数
            if 'trade_date' in df.columns:
                return str(df['trade_date'].iloc[-1])
            return f'rows={len(df)}'
        except Exception:
            return 'unknown'

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
                ts_code: self._safe_last_date(df)
                for ts_code, df in strategy._data_cache.items()
                if hasattr(df, 'index') and len(df) > 0
            },
            "updated_at": datetime.now().isoformat(),
        }

        # v3.2: 持久化策略自定义持仓字典（低吸轮动等策略使用 _holdings 而非 positions）
        if hasattr(strategy, "_holdings") and strategy._holdings:
            snapshot["_holdings"] = {
                ts_code: {
                    "entry_price": h.get("entry_price", 0),
                    "weight": h.get("weight", 1.0),
                    "shares": h.get("shares", 0),
                    "locked": h.get("locked", False),
                }
                for ts_code, h in strategy._holdings.items()
            }
        if hasattr(strategy, "_track_high") and strategy._track_high:
            snapshot["_track_high"] = dict(strategy._track_high)
        # v3.2: 持久化累积状态（防 phantom drawdown + 回撤计算连续性）
        if hasattr(strategy, "_exited_entry_value"):
            snapshot["_exited_entry_value"] = strategy._exited_entry_value
        if hasattr(strategy, "_exited_cash_value"):
            snapshot["_exited_cash_value"] = strategy._exited_cash_value
        if hasattr(strategy, "_peak_return"):
            snapshot["_peak_return"] = strategy._peak_return

        try:
            sm = get_session_manager()
            async with sm.get_session() as session:
                await session.execute(text("""
                    UPDATE strategy_runs SET state_snapshot = CAST(:snap AS jsonb)
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
                        coalesce(state_snapshot, CAST('{}' AS jsonb)),
                        '{last_heartbeat}',
                        CAST(:hb AS jsonb),
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
        """v2.0: 人工确认成交 → 同步策略持仓（支持买入和卖出）"""
        data = event.data if hasattr(event, 'data') else {}
        strategy_id = data.get("strategy_id", "")
        ts_code = data.get("ts_code", "")
        direction = data.get("direction", "")
        fill_price = float(data.get("fill_price", 0))
        fill_quantity = int(data.get("fill_quantity", 0))

        if not strategy_id or not ts_code:
            return

        state = self.running_states.get(str(strategy_id))
        if not state:
            logger.debug(f"策略 {strategy_id} 不在运行中，跳过持仓同步")
            return

        # 判断是否为卖出/平仓方向
        is_sell = direction in ("sell", "close_long")
        if is_sell:
            fill_quantity = -fill_quantity  # 卖出方向 → 减少持仓

        # 查找或创建持仓
        existing_pos = state.get_position(ts_code)
        if existing_pos:
            if fill_quantity > 0:
                # 买入/加仓：更新均价和数量
                total_cost = existing_pos.avg_cost * existing_pos.quantity + fill_price * fill_quantity
                existing_pos.quantity += fill_quantity
                existing_pos.avg_cost = total_cost / existing_pos.quantity if existing_pos.quantity > 0 else 0
            else:
                # 卖出/减仓：只减数量，均价不变
                existing_pos.quantity += fill_quantity  # fill_quantity 已为负值
            existing_pos.update_time = datetime.now()
            if existing_pos.quantity <= 0:
                state.positions = [p for p in state.positions if p.ts_code != ts_code]
                logger.info(f"持仓清空: {strategy_id} {ts_code}")
            else:
                logger.info(f"持仓更新: {strategy_id} {ts_code} x{existing_pos.quantity} avg={existing_pos.avg_cost:.2f}")
        else:
            if fill_quantity <= 0:
                logger.warning(f"尝试卖出不存在的持仓: {strategy_id} {ts_code}，跳过")
                return
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

        # 同步策略对象内部持仓追踪（防止策略反复为同一标的生成买入信号）
        strategy_obj = self._strategy_objects.get(str(strategy_id))
        if strategy_obj and hasattr(strategy_obj, '_position_entry'):
            if is_sell:
                strategy_obj._position_entry.pop(ts_code, None)
                if hasattr(strategy_obj, '_track_high'):
                    strategy_obj._track_high.pop(ts_code, None)
                logger.info(f"策略持仓已清除: {strategy_id} {ts_code}")
            else:
                strategy_obj._position_entry[ts_code] = (datetime.now().date(), fill_price)
                if hasattr(strategy_obj, '_track_high'):
                    strategy_obj._track_high[ts_code] = fill_price
                logger.info(f"策略持仓已同步: {strategy_id} {ts_code}")

    async def _on_order_filled(self, event) -> None:
        """v3.3: 订单成交 → 更新策略持仓（支持买入和卖出方向）"""
        logger.info(f"订单成交: {event.data.get('order_id')}，更新策略持仓")
        direction = str(event.data.get("direction", "")).lower()
        is_sell = direction in ("sell", "close_long")
        for strategy_id, state in self.running_states.items():
            if state.is_running:
                symbol = event.data.get("symbol") or event.data.get("ts_code", "")
                if not symbol:
                    continue
                filled_vol = int(event.data.get("filled_volume", 0) or 0)
                if is_sell:
                    filled_vol = -filled_vol  # 卖出方向 → 减少持仓
                # state.positions 是 List[Position]，遍历找到对应的持仓
                found = False
                for pos in state.positions:
                    if pos.ts_code == symbol:
                        pos.quantity += filled_vol
                        found = True
                        break
                if found and pos.quantity <= 0:
                    state.positions = [p for p in state.positions if p.ts_code != symbol]
                if not found and filled_vol > 0:
                    # 新持仓（仅买入方向）
                    from modules.strategy.models import Position, PositionSide
                    state.positions.append(Position(
                        strategy_id=strategy_id,
                        ts_code=symbol,
                        side=PositionSide.LONG,
                        quantity=filled_vol,
                        avg_cost=float(event.data.get("price", 0)),
                    ))

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

    async def load_stock_history(
        self, ts_code: str, start_date: str, end_date: str
    ) -> Optional[list]:
        """v2.4: 从 DB 加载单只股票历史 BarData — 使用 Repository 替代裸 SQL + namedtuple"""
        from datetime import datetime as _dt
        from shared.database.repositories.market.quote.stock_adjusted_price_repo import StockAdjustedPriceRepository
        from shared.database.repositories.market.quote.stock_daily_repo import StockDailyRepository
        from core.engines.types.entities import BarData

        if not self.session_factory:
            logger.warning("session_factory 未注入，无法加载历史数据")
            return None

        try:
            start_dt = _dt.strptime(start_date, "%Y-%m-%d").date()
            end_dt = _dt.strptime(end_date, "%Y-%m-%d").date()

            async with self.session_factory() as session:
                # 优先查复权价格
                adj_repo = StockAdjustedPriceRepository(session)
                rows = await adj_repo.get_by_code_and_date_range(
                    ts_code, start_dt, end_dt, adj_type="qfq", freq="D", limit=5000
                )

                if not rows:
                    # Fallback 到原始日行情
                    daily_repo = StockDailyRepository(session)
                    rows = await daily_repo.get_quotes_by_date_range(
                        str(start_dt), str(end_dt), limit=5000
                    )
                    rows = [r for r in rows if getattr(r, 'ts_code', '') == ts_code]

                return [
                    BarData(
                        ts_code=getattr(r, 'ts_code', ts_code),
                        trade_date=str(getattr(r, 'trade_date', ''))[:10],
                        open=float(getattr(r, 'open', 0) or 0),
                        high=float(getattr(r, 'high', 0) or 0),
                        low=float(getattr(r, 'low', 0) or 0),
                        close=float(getattr(r, 'close', 0) or 0),
                        volume=float(getattr(r, 'vol', getattr(r, 'volume', 0)) or 0),
                        amount=float(getattr(r, 'amount', 0) or 0),
                    )
                    for r in rows
                ]

        except Exception as e:
            logger.error(f"load_stock_history 失败: {ts_code}: {e}")
            return None
