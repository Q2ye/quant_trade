# -*- coding: utf-8 -*-
"""
风险模块统一事件

全部继承 BaseEvent，命名遵循 risk.{domain}.{action}.{status} 格式。

合并来源：
- trade/events/risk_events.py（RiskAlert/RiskViolation/RiskCheck 事件）
- monitor/events/risk_events.py（RiskMonitorEvent @dataclass 事件）
"""

from typing import Any, Dict, Optional

from core.events.base import BaseEvent
from core.events.types import EventPriority, EventCategory


class RiskCheckRequestedEvent(BaseEvent):
    """风控检查请求事件 — trade 模块信号产生时发布，risk 引擎订阅处理。

    risk.check.requested
    """

    def __init__(self, signal_data: Dict[str, Any], **kwargs):
        super().__init__(
            event_type="risk.check.requested",
            source="trade_signal_engine",
            module="risk",
            priority=EventPriority.HIGH,
            category=EventCategory.MONITOR,
            **kwargs,
        )
        self.data.update({"signal_data": signal_data})


class RiskViolationEvent(BaseEvent):
    """
    风险违规事件 — 信号风控检查未通过时发布。

    risk.signal.violation.detected
    """

    def __init__(
        self,
        rule_name: str,
        message: str,
        signal_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(
            event_type="risk.signal.violation.detected",
            source="risk_engine",
            module="risk",
            priority=EventPriority.HIGH,
            category=EventCategory.MONITOR,
            **kwargs,
        )
        self.data.update({
            "rule_name": rule_name,
            "message": message,
            "signal_data": signal_data or {},
        })


class RiskThresholdBreachedEvent(BaseEvent):
    """
    风险阈值突破事件 — 定时巡检检测到指标超阈值时发布。

    risk.threshold.breached
    """

    def __init__(
        self,
        metric_name: str,
        current_value: float,
        warning_threshold: float,
        critical_threshold: float,
        breached_level: str,  # "warning" | "critical"
        **kwargs,
    ):
        priority = (
            EventPriority.CRITICAL if breached_level == "critical"
            else EventPriority.HIGH
        )
        super().__init__(
            event_type="risk.threshold.breached",
            source="risk_engine",
            module="risk",
            priority=priority,
            category=EventCategory.MONITOR,
            **kwargs,
        )
        self.data.update({
            "metric_name": metric_name,
            "current_value": current_value,
            "warning_threshold": warning_threshold,
            "critical_threshold": critical_threshold,
            "breached_level": breached_level,
        })


class RiskAlertTriggeredEvent(BaseEvent):
    """
    风险告警触发事件 — 严重阈值突破或手动告警时发布。

    risk.alert.triggered
    """

    def __init__(
        self,
        risk_type: str,
        message: str,
        level: str = "warning",
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(
            event_type="risk.alert.triggered",
            source="risk_engine",
            module="risk",
            priority=EventPriority.HIGH,
            category=EventCategory.MONITOR,
            **kwargs,
        )
        self.data.update({
            "risk_type": risk_type,
            "message": message,
            "level": level,
            "metadata": metadata or {},
        })


class RiskMetricsUpdatedEvent(BaseEvent):
    """
    风险指标更新事件 — 每次巡检计算完风险指标后发布。

    risk.metrics.updated
    """

    def __init__(self, metrics: Dict[str, Any], **kwargs):
        super().__init__(
            event_type="risk.metrics.updated",
            source="risk_engine",
            module="risk",
            priority=EventPriority.NORMAL,
            category=EventCategory.MONITOR,
            **kwargs,
        )
        self.data.update({"metrics": metrics})


class RiskRuleStatusChangedEvent(BaseEvent):
    """
    规则启禁状态变更事件 — 管理员启用/禁用某条规则时发布。

    risk.rule.status.changed
    """

    def __init__(
        self,
        rule_name: str,
        enabled: Optional[bool] = None,  # 修复 2026-08（A17）：参数更新场景无 enabled，此前必填致 TypeError
        operator_id: str = "",
        **kwargs,
    ):
        super().__init__(
            event_type="risk.rule.status.changed",
            source="risk_manager",
            module="risk",
            priority=EventPriority.NORMAL,
            category=EventCategory.AUDIT,
            **kwargs,
        )
        self.data.update({
            "rule_name": rule_name,
            "enabled": enabled,
            "operator_id": operator_id,
        })
