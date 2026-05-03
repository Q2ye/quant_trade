# -*- coding: utf-8 -*-
"""
风险监控事件

当 RiskMonitorEngine 检测到风险阈值突破时发布。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

from modules.monitor.events.types import RiskMetricsData


@dataclass
class RiskMonitorEvent:
    """风险监控事件"""

    event_type: str
    source: str = "monitor.risk_monitor"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: str = "high"

    @classmethod
    def threshold_breached(cls, metrics: RiskMetricsData) -> "RiskMonitorEvent":
        return cls(
            event_type="monitor.risk.threshold.breached",
            priority="critical" if metrics.breached_level == "critical" else "high",
            data={
                "risk_type": metrics.risk_type,
                "metric_name": metrics.metric_name,
                "current_value": metrics.current_value,
                "warning_threshold": metrics.warning_threshold,
                "critical_threshold": metrics.critical_threshold,
                "breached_level": metrics.breached_level,
            },
        )

    @classmethod
    def alert_triggered(cls, risk_type: str, message: str, level: str = "warning") -> "RiskMonitorEvent":
        return cls(
            event_type="monitor.risk.alert.triggered",
            priority="high",
            data={"risk_type": risk_type, "message": message, "level": level},
        )

    @classmethod
    def metrics_updated(cls, metrics: Dict[str, Any]) -> "RiskMonitorEvent":
        return cls(
            event_type="monitor.risk.metrics.updated",
            priority="normal",
            data={"metrics": metrics},
        )
