# -*- coding: utf-8 -*-
"""
监控模块事件数据类型

所有监控事件通过 EventEngine 异步发布/订阅。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from modules.monitor.constants import AlertLevel, AlertType, MetricType


@dataclass
class MonitorEventData:
    """监控事件数据基类"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetricsData(MonitorEventData):
    """系统指标事件数据"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_in: float = 0.0
    network_out: float = 0.0
    process_count: int = 0
    thread_count: int = 0


@dataclass
class RiskMetricsData(MonitorEventData):
    """风险指标事件数据"""
    risk_type: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    breached_level: str = ""


@dataclass
class AlertEventData(MonitorEventData):
    """告警事件数据"""
    alert_id: str = ""
    alert_type: AlertType = AlertType.SYSTEM_ERROR
    alert_level: AlertLevel = AlertLevel.WARNING
    title: str = ""
    message: str = ""
    source_module: str = "monitor"
    notification_channels: List[str] = field(default_factory=lambda: ["email"])


@dataclass
class HealthCheckData(MonitorEventData):
    """健康检查事件数据"""
    component: str = ""
    status: str = "healthy"
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class BusinessMetricsData(MonitorEventData):
    """业务指标事件数据"""
    metric_type: MetricType = MetricType.BUSINESS
    metrics: Dict[str, Any] = field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
