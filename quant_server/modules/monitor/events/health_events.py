# -*- coding: utf-8 -*-
"""
健康检查事件

当模块健康检查完成或检测到异常时发布。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class HealthMonitorEvent:
    """健康检查事件"""

    event_type: str
    source: str = "monitor.health_manager"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: str = "normal"

    @classmethod
    def check_passed(cls, component: str, details: Dict[str, Any] = None,
                     duration_ms: float = 0.0) -> "HealthMonitorEvent":
        return cls(
            event_type="monitor.health.check.passed",
            data={
                "component": component,
                "status": "healthy",
                "details": details or {},
                "duration_ms": duration_ms,
            },
        )

    @classmethod
    def check_failed(cls, component: str, error: str,
                     details: Dict[str, Any] = None) -> "HealthMonitorEvent":
        return cls(
            event_type="monitor.health.check.failed",
            priority="high",
            data={
                "component": component,
                "status": "unhealthy",
                "error": error,
                "details": details or {},
            },
        )

    @classmethod
    def all_checks_summary(cls, results: List[Dict[str, Any]],
                           overall_status: str) -> "HealthMonitorEvent":
        return cls(
            event_type="monitor.health.check.passed" if overall_status == "healthy"
            else "monitor.health.check.failed",
            priority="normal" if overall_status == "healthy" else "high",
            data={
                "overall_status": overall_status,
                "checks": results,
            },
        )
