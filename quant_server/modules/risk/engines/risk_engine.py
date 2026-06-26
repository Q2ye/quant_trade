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
from typing import Any, Dict, List, Optional, Tuple

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
        # 规则启用状态（key=rule_name, value=bool）
        self._rule_status: Dict[str, bool] = {}

        # 周期巡检
        self._check_task: Optional[asyncio.Task] = None
        self._last_risk_metrics: Dict[str, Any] = {}

    # ==================== EngineBase 生命周期 ====================

    @property
    def engine_type(self) -> EngineType:
        return EngineType.RISK_ENGINE

    async def _on_initialize(self) -> None:
        """加载默认规则并恢复启用状态"""
        self._load_default_rules()
        logger.info(
            "RiskEngine 初始化完成，已加载 %d 条风控规则",
            len(self._registered_rules),
        )

    async def _on_start(self) -> None:
        """启动引擎 — 启动周期巡检任务"""
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
                self._rule_status[rule.get_name()] = True  # 默认全部启用

        except ImportError as e:
            logger.warning("加载风控规则失败: %s", e)

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
                    self.event_engine.put(RiskRuleStatusChangedEvent(
                        rule_name=rule_name,
                        message=f"规则参数已更新: {params}",
                    ))
                return True
        return False

    def update_rule_status(self, rule_name: str, enabled: bool) -> bool:
        """更新规则启用状态"""
        if rule_name not in self._rule_status:
            return False
        self._rule_status[rule_name] = enabled

        # 发布规则状态变更事件
        if self.event_engine:
            from modules.risk.events.risk_events import RiskRuleStatusChangedEvent
            self.event_engine.put(RiskRuleStatusChangedEvent(
                rule_name=rule_name,
                enabled=enabled,
            ))

        logger.info("规则 %s 已%s", rule_name, "启用" if enabled else "禁用")
        return True

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
        self, signal_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        检查信号是否符合风控规则。

        v2.0: 唯一路径 — 遍历注册的 RiskRule 实例。
        不再有内联回退方法。
        """
        if not self.risk_check_enabled:
            return True, "风控检查已禁用"

        enabled_rules = self.get_enabled_rules()
        if not enabled_rules:
            logger.warning("无启用的风控规则")
            return True, "无启用的风控规则"

        violations: List[Dict[str, str]] = []
        # 初始化内存事件列表（用于快速查询 + 持久化到 DB）
        if not hasattr(self, '_risk_events'):
            self._risk_events: List[Dict[str, Any]] = []

        for rule in enabled_rules:
            try:
                passed, message = await rule.check(signal_data)
                if not passed:
                    violation = {
                        "rule_name": rule.get_name(),
                        "message": message,
                        "signal_data": signal_data,
                        "level": "warning",
                        "event_type": "risk.signal.violation.detected",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    violations.append(violation)
                    # 存入内存事件列表
                    self._risk_events.append(violation)
                    # 发布违规事件
                    if self.event_engine:
                        from modules.risk.events.risk_events import (
                            RiskViolationEvent,
                        )
                        self.event_engine.put(RiskViolationEvent(
                            rule_name=rule.get_name(),
                            message=message,
                            signal_data=signal_data,
                        ))
                    # 持久化到 DB
                    await self._persist_risk_event(violation)
            except Exception as e:
                logger.error("规则 %s 检查异常: %s", rule.get_name(), e)

        if violations:
            return False, "; ".join(
                f"[{v['rule_name']}] {v['message']}" for v in violations
            )

        return True, "所有风控规则检查通过"

    async def _persist_risk_event(self, event_data: Dict[str, Any]) -> None:
        """持久化风险事件到 DB（如果 session_factory 可用）"""
        if not self._session_factory:
            return
        try:
            from shared.database.repositories.trading.risk.risk_event_repo import (
                RiskEventRepository,
            )
            async with self._session_factory() as session:
                repo = RiskEventRepository(session)
                await repo.create({
                    "event_type": event_data.get("event_type", "risk.event"),
                    "event_message": event_data.get("message", ""),
                    "trigger_value": event_data.get("signal_data", {}),
                    "action_taken": "alert",
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
