# -*- coding: utf-8 -*-
"""
统一风险控制引擎

职责：
1. 信号级风控：check_signal() — 遍历注册的 RiskRule 实例检查每笔信号
2. 周期级巡检：_check_loop() — 定时计算风险指标并与阈值比较

与旧版（trade/engines/risk_engine.py）的区别：
- 删除了 5 个内联回退方法（_check_position_limit 等），统一走 RiskRule
- 合并了 monitor/engines/risk_monitor.py 的周期巡检功能
- 事件全部使用 modules/risk/events/ 的统一事件
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.engines import EngineConfigEntity
from core.engines.base.engine_base import EngineBase
from core.engines.system import EventEngine
from core.engines.types.enums import EngineType
from modules.risk.constants import ModuleConfig

logger = logging.getLogger(__name__)


class RiskEngine(EngineBase):
    """统一风险控制引擎

    同时支持：
    - 信号级检查（实时，由 SignalEngine 调用）
    - 周期级巡检（定时，内部 check loop）
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_engine: Optional[EventEngine] = None,
        position_engine=None,  # 可选：用于获取持仓/资产数据
        threshold_repo=None,   # 可选：MonitorThresholdRepository
        session_factory=None,
        risk_manager=None,     # 兼容旧版 trade 模块调用，v2.0 不再使用
    ):
        cfg = config or {}
        config_obj = EngineConfigEntity(
            name=cfg.get("name", "risk_engine"),
            engine_type="risk_engine",
            dependencies=cfg.get("dependencies", []),
            max_retries=cfg.get("max_retries", 3),
            retry_delay=cfg.get("retry_delay", 1.0),
            config=cfg,
        )
        # 确保 config 属性始终存在（即使 super().__init__ 失败也不会导致 __del__ 崩溃）
        self.config = config_obj

        super().__init__(config=config_obj, event_engine=event_engine)
        self._position_engine = position_engine
        self._threshold_repo = threshold_repo
        self._session_factory = session_factory

        # 配置
        self.risk_check_enabled = cfg.get(
            "risk_check_enabled", ModuleConfig.RISK_CHECK_ENABLED
        )
        self._check_interval = cfg.get(
            "risk_check_interval", ModuleConfig.RISK_CHECK_INTERVAL
        )

        # 规则实例列表（在 _on_initialize 中加载）
        self._registered_rules: List = []
        self._registered_rules_map: Dict[str, Any] = {}
        # 规则启用状态（key=rule_name, value=bool）
        self._rule_status: Dict[str, bool] = {}

        # 周期巡检
        self._check_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._last_risk_metrics: Dict[str, Any] = {}

    # ==================== EngineBase 生命周期 ====================

    @property
    def engine_type(self) -> EngineType:
        return EngineType.RISK_ENGINE

    async def _on_initialize(self) -> None:
        """加载默认规则并恢复启用状态"""
        self._load_default_rules()
        await self._load_rule_status_from_db()
        logger.info(
            "RiskEngine 初始化完成，已加载 %d 条风控规则",
            len(self._registered_rules),
        )

    async def _on_start(self) -> None:
        """启动引擎 — 订阅风控事件 + 启动周期巡检任务"""
        # 订阅 trade 模块的风控检查请求事件
        if self.event_engine:
            self.event_engine.subscribe(
                "risk.check.requested", self._on_risk_check_requested
            )
            logger.info("RiskEngine 已订阅 risk.check.requested 事件")

        logger.info(
            "RiskEngine 启动，信号检查=%s，巡检间隔=%ds",
            self.risk_check_enabled,
            self._check_interval,
        )
        if self.risk_check_enabled:
            self._check_task = asyncio.create_task(
                self._check_loop(),
                name="risk_check_loop",
            )

        # v3.0: 启动事件清理任务（每天凌晨清理 90 天前的旧事件）
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(),
            name="risk_cleanup_loop",
        )

    async def _on_risk_check_requested(self, event) -> None:
        """处理风控检查请求（通过 EventEngine 接收，异步处理）"""
        signal_data = event.data.get("signal_data", {})
        is_valid, message = await self.check_signal(signal_data)
        if not is_valid:
            from modules.risk.events.risk_events import RiskViolationEvent
            violation = RiskViolationEvent(
                rule_name="signal_check",
                message=message,
                signal_data=signal_data,
            )
            await self.event_engine.put(violation)

    async def _on_stop(self) -> None:
        """停止引擎"""
        logger.info("RiskEngine 停止中...")
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None
        if hasattr(self, '_cleanup_task') and self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("RiskEngine 已停止")

    async def _on_force_stop(self) -> None:
        """强制停止"""
        logger.warning("RiskEngine 强制停止")
        if self._check_task:
            self._check_task.cancel()
            self._check_task = None

    def _validate_config(self) -> None:
        """验证配置"""
        pass

    async def _check_dependencies(self) -> None:
        """检查依赖"""
        pass

    async def _start_background_tasks(self) -> None:
        pass

    async def _stop_background_tasks(self) -> None:
        pass

    async def _monitoring_loop(self) -> None:
        pass

    # ==================== 规则管理 ====================

    def _load_default_rules(self) -> None:
        """
        从 modules/risk/rules/ 加载全部 19 条 RiskRule 实例。

        每条规则默认启用，可通过 update_rule_status() 动态启禁。
        """
        if self._registered_rules:
            return

        try:
            from modules.risk.rules.position_rules import (
                PositionLimitRule,
                SinglePositionLimitRule,
                PositionConcentrationRule,
                SectorConcentrationRule,
                StockStopLossRule,
            )
            from modules.risk.rules.account_rules import (
                AccountBalanceRule,
                LossLimitRule,
                DrawdownLimitRule,
                CapitalChangeRule,
                TradeCountRule,
            )
            from modules.risk.rules.blacklist_rules import (
                BlacklistRule,
                MarketBlacklistRule,
                SectorBlacklistRule,
            )
            from modules.risk.rules.market_rules import (
                LiquidityRule,
                PriceRule,
                VolatilityRule,
                MarketStatusRule,
                LimitUpDownRule,
                SuspensionRule,
            )

            rules = [
                PositionLimitRule(),
                SinglePositionLimitRule(),
                PositionConcentrationRule(),
                SectorConcentrationRule(),
                StockStopLossRule(),
                AccountBalanceRule(),
                LossLimitRule(),
                DrawdownLimitRule(),
                CapitalChangeRule(),
                TradeCountRule(),
                BlacklistRule(),
                MarketBlacklistRule(),
                SectorBlacklistRule(),
                LiquidityRule(),
                PriceRule(),
                VolatilityRule(),
                MarketStatusRule(),
                LimitUpDownRule(),
                SuspensionRule(),
            ]

            for rule in rules:
                self._registered_rules.append(rule)
                self._registered_rules_map[rule.get_name()] = rule
                self._rule_status[rule.get_name()] = True  # 默认全部启用

        except ImportError as e:
            logger.warning("加载风控规则失败: %s", e)

    async def _load_rule_status_from_db(self) -> None:
        """启动时从 DB 恢复规则启用/禁用状态，覆盖默认值（默认全部启用）"""
        try:
            from shared.database.session.session_manager import get_session_manager
            from shared.database.repositories.trading.risk.risk_rule_repo import RiskRuleRepository
            sm = get_session_manager()
            async with sm.get_session() as session:
                repo = RiskRuleRepository(session)
                db_rules = await repo.get_all()
                restored = 0
                for r in db_rules:
                    if r.rule_name in self._rule_status:
                        if self._rule_status[r.rule_name] != r.is_active:
                            self._rule_status[r.rule_name] = r.is_active
                            restored += 1
                if restored:
                    logger.info("从 DB 恢复了 %d 条规则的启停状态", restored)
        except Exception as e:
            logger.debug("从 DB 加载规则状态失败（使用默认值）: %s", e)

    def get_enabled_rules(self) -> List:
        """获取所有已启用的规则实例"""
        return [
            rule for rule in self._registered_rules
            if self._rule_status.get(rule.get_name(), False)
        ]

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """获取全部规则信息（含启用状态、参数、输入字段）"""
        _INPUTS_MAP = {
            "position_limit": ["total_asset", "position_value"],
            "single_position_limit": ["total_asset", "trade_amount"],
            "position_concentration": ["positions", "total_asset"],
            "sector_concentration": ["sector", "positions", "total_asset"],
            "stock_stop_loss": ["ts_code", "cost_price", "current_price"],
            "account_balance": ["trade_amount", "available_cash"],
            "loss_limit": ["total_asset", "initial_capital"],
            "drawdown_limit": ["total_asset", "peak_asset"],
            "capital_change": ["total_asset", "previous_asset"],
            "trade_count": ["daily_trade_count"],
            "blacklist": ["ts_code"],
            "market_blacklist": ["market"],
            "sector_blacklist": ["sector"],
            "liquidity": ["liquidity"],
            "price": ["close", "high", "low"],
            "volatility": ["volatility"],
            "market_status": ["market_status"],
            "limit_up_down": ["ts_code", "close", "pre_close", "direction", "is_st"],
            "suspension": ["ts_code", "volume", "suspended"],
        }
        _DEFAULT_ACTION = {
            "position_limit": "alert",
            "single_position_limit": "stop_strategy",
            "position_concentration": "alert",
            "sector_concentration": "alert",
            "stock_stop_loss": "stop_strategy",
            "account_balance": "cancel_orders",
            "loss_limit": "stop_strategy",
            "drawdown_limit": "stop_strategy",
            "capital_change": "alert",
            "trade_count": "alert",
            "blacklist": "cancel_orders",
            "market_blacklist": "cancel_orders",
            "sector_blacklist": "cancel_orders",
            "liquidity": "alert",
            "price": "alert",
            "volatility": "alert",
            "market_status": "stop_strategy",
            "limit_up_down": "cancel_orders",
            "suspension": "cancel_orders",
        }
        return [
            {
                "name": rule.get_name(),
                "description": rule.get_description(),
                "enabled": self._rule_status.get(rule.get_name(), False),
                "rule_type": self._classify_rule(rule.get_name()),
                "params": rule.get_params(),
                "inputs": _INPUTS_MAP.get(rule.get_name(), []),
                "action": _DEFAULT_ACTION.get(rule.get_name(), "alert"),
            }
            for rule in self._registered_rules
        ]

    def update_rule_params(
        self, rule_name: str, params: Dict[str, Any]
    ) -> bool:
        """更新规则的可配置参数"""
        for rule in self._registered_rules:
            if rule.get_name() == rule_name:
                for key, value in params.items():
                    if hasattr(rule, key) and not callable(getattr(rule, key)):
                        try:
                            # 保持类型一致
                            current = getattr(rule, key)
                            if isinstance(current, bool):
                                value = bool(value)
                            elif isinstance(current, int) and not isinstance(current, bool):
                                value = int(value)
                            elif isinstance(current, float):
                                value = float(value)
                            setattr(rule, key, value)
                        except (ValueError, TypeError):
                            logger.warning("参数 %s=%s 类型转换失败", key, value)
                # 发布规则变更事件
                if self.event_engine:
                    from modules.risk.events.risk_events import (
                        RiskRuleStatusChangedEvent,
                    )
                    # 修复 2026-08（A15）：put 为 async，未 await 则事件永不发布；
                    # 同步方法内用 create_task 派发（无运行 loop 时跳过并告警）
                    try:
                        asyncio.create_task(self.event_engine.put(RiskRuleStatusChangedEvent(
                            rule_name=rule_name,
                            message=f"规则参数已更新: {params}",
                        )))
                    except RuntimeError:
                        logger.warning("无运行事件循环，规则变更事件未发布")
                return True
        return False

    def update_rule_status(self, rule_name: str, enabled: bool) -> bool:
        """更新规则启用状态（内存 + DB 双写）"""
        if rule_name not in self._rule_status:
            return False
        self._rule_status[rule_name] = enabled

        # 发布规则状态变更事件
        if self.event_engine:
            from modules.risk.events.risk_events import RiskRuleStatusChangedEvent
            # 修复 2026-08（A15）：async put 未 await 则事件永不发布，create_task 派发
            try:
                asyncio.create_task(self.event_engine.put(RiskRuleStatusChangedEvent(
                    rule_name=rule_name,
                    enabled=enabled,
                )))
            except RuntimeError:
                logger.warning("无运行事件循环，规则状态事件未发布")

        # v3.0: 持久化到 risk_rules 表
        self._schedule_rule_db_sync(rule_name, enabled)

        logger.info("规则 %s 已%s", rule_name, "启用" if enabled else "禁用")
        return True

    def _schedule_rule_db_sync(self, rule_name: str, enabled: bool) -> None:
        """异步同步规则状态到 DB（fire-and-forget，失败不影响主流程）"""
        async def _sync():
            try:
                from shared.database.session.session_manager import get_session_manager
                from shared.database.repositories.trading.risk.risk_rule_repo import RiskRuleRepository
                from shared.database.models.business_models import RiskRule
                from sqlalchemy import select
                sm = get_session_manager()
                async with sm.get_session() as session:
                    repo = RiskRuleRepository(session)
                    # 按 rule_name 查找已有记录
                    existing = await repo.get_by_name(rule_name)
                    if existing:
                        if enabled:
                            await repo.enable_rule(str(existing.id))
                        else:
                            await repo.disable_rule(str(existing.id))
                    else:
                        # 首次：创建 DB 记录
                        rule = self._registered_rules_map.get(rule_name)
                        rule_type = self._classify_rule(rule_name) if rule else "unknown"
                        await repo.create({
                            "rule_name": rule_name,
                            "rule_type": rule_type,
                            "condition": {},
                            "action": "alert",
                            "is_active": enabled,
                        })
                    await session.commit()
            except Exception as e:
                logger.debug("规则状态 DB 同步失败（不影响运行时）: %s", e)

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_sync())
        except RuntimeError:
            pass

    # ---- 黑名单运行时管理 ----

    def add_blacklist_stock(self, ts_code: str) -> None:
        """运行时向黑名单规则注入股票代码（同步 DB 黑名单）"""
        for rule in self._registered_rules:
            name = rule.get_name()
            if name == "blacklist" and hasattr(rule, 'blacklist'):
                if ts_code not in rule.blacklist:
                    rule.blacklist.append(ts_code)
                    logger.info("黑名单已添加: %s", ts_code)

    def remove_blacklist_stock(self, ts_code: str) -> None:
        """运行时从黑名单规则移除股票代码"""
        for rule in self._registered_rules:
            name = rule.get_name()
            if name == "blacklist" and hasattr(rule, 'blacklist'):
                if ts_code in rule.blacklist:
                    rule.blacklist.remove(ts_code)
                    logger.info("黑名单已移除: %s", ts_code)

    def load_blacklist_from_db(self, stocks: List[str]) -> None:
        """启动时从 DB 批量加载黑名单股票"""
        for rule in self._registered_rules:
            if rule.get_name() == "blacklist" and hasattr(rule, 'blacklist'):
                rule.blacklist = list(set(rule.blacklist + stocks))
                logger.info("从 DB 加载 %d 只黑名单股票", len(stocks))

    @staticmethod
    def _classify_rule(rule_name: str) -> str:
        """推断规则分类"""
        position_rules = {
            "position_limit", "single_position_limit", "position_concentration",
            "sector_concentration", "stock_stop_loss",
        }
        account_rules = {
            "account_balance", "loss_limit", "drawdown_limit", "capital_change",
            "trade_count",
        }
        blacklist_rules = {
            "blacklist", "market_blacklist", "sector_blacklist",
        }
        market_rules = {
            "liquidity", "price", "volatility", "market_status",
            "limit_up_down", "suspension",
        }

        if rule_name in position_rules:
            return "position"
        if rule_name in account_rules:
            return "account"
        if rule_name in blacklist_rules:
            return "blacklist"
        if rule_name in market_rules:
            return "market"
        return "unknown"

    # ==================== 信号级风控检查 ====================

    async def check_signal(
        self, signal_data: Dict[str, Any],
        exclude_rules: Optional[Iterable[str]] = None,
    ) -> Tuple[bool, str]:
        """
        检查信号是否符合风控规则。

        v3.0: 分层 severity — info/warning 不阻断，error/critical 阻断。
        v2.0: 唯一路径 — 遍历注册的 RiskRule 实例。
        v6.11: 新增 exclude_rules — 按规则名排除（如回测中跳过账户级日终监控规则）。
        """
        if not self.risk_check_enabled:
            return True, "风控检查已禁用"

        enabled_rules = self.get_enabled_rules()
        if not enabled_rules:
            logger.warning("无启用的风控规则")
            return True, "无启用的风控规则"

        if exclude_rules:
            exclude_set = set(exclude_rules)
            enabled_rules = [r for r in enabled_rules if r.get_name() not in exclude_set]

        violations: List[Dict[str, str]] = []
        if not hasattr(self, '_risk_events'):
            self._risk_events: List[Dict[str, Any]] = []

        # 追踪最高 severity
        max_severity = "info"
        severity_rank = {"info": 0, "warning": 1, "error": 2, "critical": 3}
        action_hints: List[str] = []

        for rule in enabled_rules:
            try:
                # v3.0: 优先使用 check_with_severity()
                if hasattr(rule, 'check_with_severity'):
                    result = await rule.check_with_severity(signal_data)
                    passed = result.passed
                    severity = result.severity
                    message = result.message
                    action = result.action
                else:
                    passed, message = await rule.check(signal_data)
                    severity = "error" if not passed else "info"
                    action = "block" if not passed else "allow"

                severity_idx = severity_rank.get(severity, 2)
                if severity_idx > severity_rank.get(max_severity, 0):
                    max_severity = severity
                if action in ("reduce_size", "block", "kill"):
                    action_hints.append(action)

                if not passed or severity in ("warning", "error", "critical"):
                    level = severity if severity in ("warning", "error", "critical") else "warning"
                    violation = {
                        "rule_name": rule.get_name(),
                        "message": message,
                        "signal_data": signal_data,
                        "level": level,
                        "severity": severity,
                        "action": action,
                        "event_type": "risk.signal.violation.detected",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    violations.append(violation)
                    self._risk_events.append(violation)
                    if self.event_engine:
                        from modules.risk.events.risk_events import RiskViolationEvent
                        self.event_engine.put(RiskViolationEvent(
                            rule_name=rule.get_name(),
                            message=message,
                            signal_data=signal_data,
                        ))
                    await self._persist_risk_event(violation)
            except Exception as e:
                logger.error("规则 %s 检查异常: %s", rule.get_name(), e)

        # v3.0: 按最高 severity 决定 pass/fail
        blocking_violations = [v for v in violations
                               if v.get("severity") in ("error", "critical")]
        warning_violations = [v for v in violations
                              if v.get("severity") == "warning"]

        if blocking_violations:
            msg = "; ".join(f"[{v['rule_name']}] {v['message']}" for v in blocking_violations)
            if warning_violations:
                msg += " | 警告: " + "; ".join(v['message'] for v in warning_violations[:2])
            return False, msg

        if warning_violations:
            msg = "警告: " + "; ".join(v['message'] for v in warning_violations[:3])
            return True, msg  # warning 不阻断，通过但携带提示

        return True, "所有风控规则检查通过"

    def get_last_check_action_hint(self) -> Optional[str]:
        """获取最近一次 check_signal 的最高 action 建议（供 SignalEngine 使用）"""
        if not hasattr(self, '_risk_events') or not self._risk_events:
            return None
        recent = self._risk_events[-3:] if len(self._risk_events) >= 3 else self._risk_events
        actions = [e.get("action", "block") for e in recent]
        if "kill" in actions:
            return "kill"
        if "block" in actions:
            return "block"
        if "reduce_size" in actions:
            return "reduce_size"
        return None

    async def _persist_risk_event(self, event_data: Dict[str, Any]) -> None:
        """持久化风险事件到 DB（如果 session_factory 可用）。

        risk_events.rule_id / user_id 均为 NOT NULL 外键（→ risk_rules / sys_users）。
        内置规则（如 limit_up_down/suspension）无对应 DB 规则行、回测场景无用户上下文，
        此时缺失必填外键 → 直接跳过落库（事件仍保留在 _risk_events 内存并经 EventEngine
        广播，回测报告另有 _risk_violations 收集），避免向超表插入违反 NOT NULL/FK 的记录
        导致事务回滚刷屏、并静默丢失。
        """
        if not self._session_factory:
            return
        # 必填外键守卫：缺 rule_id/user_id（内置规则/回测）→ 不落库
        rule_id = event_data.get("rule_id")
        user_id = event_data.get("user_id")
        if not rule_id or not user_id:
            return
        try:
            from shared.database.repositories.trading.risk.risk_event_repo import (
                RiskEventRepository,
            )
            async with self._session_factory() as session:
                repo = RiskEventRepository(session)
                await repo.create({
                    "rule_id": rule_id,
                    "user_id": user_id,
                    "strategy_id": event_data.get("strategy_id"),
                    "event_type": event_data.get("event_type", "risk.event"),
                    "event_message": event_data.get("message", ""),
                    "trigger_value": event_data.get("signal_data", {}),
                    "action_taken": event_data.get("action", "alert"),
                    "created_at": event_data.get("created_at"),
                })
        except Exception as e:
            logger.debug("持久化风险事件失败（非致命）: %s", e)

    # ==================== 周期级风险巡检 ====================

    async def _check_loop(self) -> None:
        """定时巡检循环"""
        while self.record.status.value == "running":
            try:
                await self._run_risk_check()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("风险巡检异常: %s", e)
                await asyncio.sleep(min(self._check_interval, 10))

    async def _cleanup_loop(self) -> None:
        """定时清理过期风险事件（每天执行一次，保留 90 天）"""
        while self.record.status.value == "running":
            try:
                # 首次启动后等 5 分钟再执行，避免影响启动
                await asyncio.sleep(300)
                while self.record.status.value == "running":
                    try:
                        repo = getattr(self, '_db_session', None)
                        if repo is None:
                            try:
                                from shared.database.repositories.trading.risk.risk_event_repo import RiskEventRepository
                                from shared.database.session.session_manager import get_session_manager
                                sm = get_session_manager()
                                async with sm.get_session() as session:
                                    repo = RiskEventRepository(session)
                                    deleted = await repo.cleanup_old_events(days=90)
                                    if deleted > 0:
                                        logger.info("风险事件清理完成: 删除 %d 条 90 天前的旧记录", deleted)
                            except Exception:
                                pass  # DB 不可用时静默跳过
                        break  # 执行一次后退出内层循环
                    except Exception as e:
                        logger.warning("风险事件清理失败: %s", e)
                    await asyncio.sleep(86400)  # 每天清理一次
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(3600)  # 异常时 1 小时后重试

    async def _run_risk_check(self) -> Dict[str, Any]:
        """执行一次风险巡检"""
        metrics = await self._collect_risk_metrics()
        if not metrics:
            return {"status": "no_data"}

        self._last_risk_metrics = metrics

        # 与阈值比较
        from modules.risk.services.risk_service import RiskService
        evaluation = await RiskService.evaluate_risk(metrics, self._threshold_repo)

        # 发布指标更新事件
        if self.event_engine:
            from modules.risk.events.risk_events import RiskMetricsUpdatedEvent
            self.event_engine.put(RiskMetricsUpdatedEvent(metrics=metrics))

        # 发布阈值突破事件
        for breach in evaluation.get("breaches", []):
            if self.event_engine:
                from modules.risk.events.risk_events import (
                    RiskThresholdBreachedEvent,
                    RiskAlertTriggeredEvent,
                )
                self.event_engine.put(RiskThresholdBreachedEvent(
                    metric_name=breach.get("metric", ""),
                    current_value=breach.get("value", 0),
                    warning_threshold=breach.get("warning_threshold", 0),
                    critical_threshold=breach.get("critical_threshold", 0),
                    breached_level=breach.get("level", "warning"),
                ))

                if breach.get("level") == "critical":
                    self.event_engine.put(RiskAlertTriggeredEvent(
                        risk_type=breach.get("metric", ""),
                        message=(
                            f"风险阈值严重突破: {breach.get('metric')} = "
                            f"{breach.get('value')} "
                            f"(严重阈值: {breach.get('critical_threshold')})"
                        ),
                        level="critical",
                    ))

        return evaluation

    async def _collect_risk_metrics(self) -> Dict[str, float]:
        """
        收集当前风险指标。

        优先从 position_engine 获取，fallback 到上次数据。
        """
        metrics: Dict[str, float] = {}

        if self._position_engine:
            try:
                total_asset = self._position_engine.get_total_asset()
                position_value = self._position_engine.get_position_value()
                initial_capital = self.config.config.get("initial_capital", total_asset)

                # 仓位比例
                if total_asset > 0:
                    metrics["position_ratio"] = round(
                        (position_value / total_asset) * 100, 2
                    )

                # 回撤
                # peak_asset 可从 position_engine 或配置获取
                peak_asset = self.config.config.get("peak_asset", total_asset)
                if peak_asset > 0:
                    metrics["drawdown"] = round(
                        ((peak_asset - total_asset) / peak_asset) * 100, 2
                    )

                # 亏损比例
                if initial_capital > 0 and total_asset < initial_capital:
                    metrics["max_loss"] = round(
                        ((initial_capital - total_asset) / initial_capital) * 100, 2
                    )

                # 可用现金（用于计算杠杆）
                available_cash = self._position_engine.get_available_cash()
                if available_cash > 0 and total_asset > 0:
                    metrics["leverage_ratio"] = round(
                        (position_value / available_cash) * 100, 2
                    )
            except Exception as e:
                logger.warning("从 position_engine 采集指标失败: %s", e)

        # fallback 到上次数据
        if not metrics:
            metrics = dict(self._last_risk_metrics)

        return metrics

    async def update_risk_metrics(self, metrics: Dict[str, float]) -> None:
        """外部更新风险指标（由 handlers 或其他引擎调用）"""
        self._last_risk_metrics.update(metrics)

    async def get_risk_metrics(self) -> Dict[str, Any]:
        """获取最近的风险指标"""
        return dict(self._last_risk_metrics)

    # ==================== 持仓风险检查 ====================

    async def check_position_risk(self) -> List[Dict[str, Any]]:
        """检查所有持仓的个体风险"""
        risks: List[Dict[str, Any]] = []

        if not self._position_engine:
            return risks

        try:
            positions = await self._position_engine.get_position()
        except Exception as e:
            logger.warning("获取持仓失败: %s", e)
            return risks

        threshold = self.config.config.get("position_risk_threshold", 0.10)

        for pos in positions:
            cost = pos.get("cost_price", 0)
            current = pos.get("current_price", 0)
            if cost > 0:
                pnl_pct = (current - cost) / cost
                if abs(pnl_pct) > threshold:
                    risks.append({
                        "ts_code": pos.get("symbol", pos.get("ts_code")),
                        "risk_type": "position_pnl",
                        "message": f"持仓盈亏比例过大: {pnl_pct:.2%}",
                        "level": "warning" if pnl_pct > 0 else "danger",
                    })

        return risks
