# -*- coding: utf-8 -*-
"""
监控模块常量定义
"""

from enum import Enum


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """告警状态"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertType(str, Enum):
    """告警类型"""
    SYSTEM_ERROR = "system_error"
    RISK_TRIGGER = "risk_trigger"
    DATA_QUALITY = "data_quality"
    PERFORMANCE = "performance"
    BUSINESS = "business"


class NotificationChannel(str, Enum):
    """通知渠道"""
    EMAIL = "email"
    WECHAT = "wechat"
    DINGTALK = "dingtalk"
    SMS = "sms"


class MetricType(str, Enum):
    """监控指标类型"""
    SYSTEM = "system"
    RISK = "risk"
    BUSINESS = "business"
    PERFORMANCE = "performance"


class SystemMetricName(str, Enum):
    """系统指标名称"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    NETWORK_IN = "network_in"
    NETWORK_OUT = "network_out"
    PROCESS_COUNT = "process_count"
    THREAD_COUNT = "thread_count"


class RiskMetricName(str, Enum):
    """风险指标名称"""
    POSITION_RATIO = "position_ratio"
    LEVERAGE_RATIO = "leverage_ratio"
    DRAWDOWN = "drawdown"
    VAR = "var"
    SHARPE_RATIO = "sharpe_ratio"
    VOLATILITY = "volatility"
    MAX_LOSS = "max_loss"


class ModuleConfig:
    """监控模块默认配置"""
    MODULE_NAME = "monitor"
    VERSION = "1.0.0"
    SYSTEM_COLLECT_INTERVAL = 10
    RISK_CHECK_INTERVAL = 30
    BUSINESS_METRICS_INTERVAL = 60
    ALERT_RETRY_MAX = 3
    ALERT_RETRY_DELAY = 5.0
    ALERT_CLEANUP_DAYS = 90
    HEALTH_CHECK_TIMEOUT = 30.0
    ENGINE_MAX_WORKERS = 4
    ENGINE_QUEUE_SIZE = 5000


class EventType(str, Enum):
    """监控模块事件类型"""
    SYSTEM_METRICS_COLLECTED = "monitor.system.metrics.collected"
    SYSTEM_HEALTH_CHANGED = "monitor.system.health.changed"
    SYSTEM_COMPONENT_DOWN = "monitor.system.component.down"
    RISK_THRESHOLD_BREACHED = "monitor.risk.threshold.breached"
    RISK_ALERT_TRIGGERED = "monitor.risk.alert.triggered"
    RISK_METRICS_UPDATED = "monitor.risk.metrics.updated"
    BUSINESS_METRICS_UPDATED = "monitor.business.metrics.updated"
    BUSINESS_ANOMALY_DETECTED = "monitor.business.anomaly.detected"
    ALERT_CREATED = "monitor.alert.created"
    ALERT_NOTIFICATION_SENT = "monitor.alert.notification.sent"
    ALERT_NOTIFICATION_FAILED = "monitor.alert.notification.failed"
    ALERT_ACKNOWLEDGED = "monitor.alert.acknowledged"
    ALERT_RESOLVED = "monitor.alert.resolved"
    HEALTH_CHECK_PASSED = "monitor.health.check.passed"
    HEALTH_CHECK_FAILED = "monitor.health.check.failed"


DEFAULT_THRESHOLDS = {
    "system.cpu_usage": {"warning": 70.0, "critical": 90.0, "unit": "%"},
    "system.memory_usage": {"warning": 80.0, "critical": 95.0, "unit": "%"},
    "system.disk_usage": {"warning": 80.0, "critical": 90.0, "unit": "%"},
    "risk.drawdown": {"warning": 10.0, "critical": 20.0, "unit": "%"},
    "risk.position_ratio": {"warning": 80.0, "critical": 95.0, "unit": "%"},
    "risk.var": {"warning": 2.0, "critical": 5.0, "unit": "%"},
    "performance.avg_latency_ms": {"warning": 100.0, "critical": 500.0, "unit": "ms"},
}

ALERT_TEMPLATES = {
    AlertType.SYSTEM_ERROR: {
        "title": "[{level}] 系统异常 - {component}",
        "message": "组件: {component}\n指标: {metric}\n当前值: {value}\n阈值: {threshold}\n时间: {timestamp}"
    },
    AlertType.RISK_TRIGGER: {
        "title": "[{level}] 风险预警 - {risk_type}",
        "message": "风险类型: {risk_type}\n当前值: {value}\n阈值: {threshold}\n级别: {level}\n时间: {timestamp}"
    },
    AlertType.PERFORMANCE: {
        "title": "[{level}] 性能告警 - {metric}",
        "message": "指标: {metric}\n当前值: {value}\n阈值: {threshold}\n时间: {timestamp}"
    },
}
