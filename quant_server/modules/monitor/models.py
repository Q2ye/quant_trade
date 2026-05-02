# -*- coding: utf-8 -*-
"""
监控模块业务 DTO（数据传输对象）

纯数据类，用于 Engine → Service → Handler 之间传递领域数据。
区别于：
- schemas.py: API 层 Pydantic 请求/响应模型
- shared/database/models/: SQLAlchemy ORM 模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


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


@dataclass
class SystemMetrics:
	"""系统指标快照"""
	cpu_percent: float = 0.0
	memory_percent: float = 0.0
	disk_percent: float = 0.0
	network_bytes_sent: int = 0
	network_bytes_recv: int = 0
	open_connections: int = 0
	active_threads: int = 0
	uptime_seconds: int = 0
	timestamp: Optional[datetime] = None


@dataclass
class MetricSnapshot:
	"""通用指标数据点"""
	metric_name: str
	metric_value: float
	labels: Dict[str, str] = field(default_factory=dict)
	timestamp: Optional[datetime] = None


@dataclass
class AlertRule:
	"""告警规则（领域对象）"""
	rule_id: str
	name: str
	alert_type: str  # system / business / risk
	condition: Dict[str, Any]  # {"metric": "cpu_percent", "operator": "gt", "threshold": 90}
	threshold: float
	alert_level: AlertLevel = AlertLevel.WARNING
	cooldown_seconds: int = 300
	enabled: bool = True


@dataclass
class Alert:
	"""告警实例"""
	alert_id: str
	rule_id: str
	alert_type: str
	message: str
	alert_level: AlertLevel = AlertLevel.WARNING
	status: AlertStatus = AlertStatus.ACTIVE
	source: str = ""  # 触发源模块
	context: Dict[str, Any] = field(default_factory=dict)
	created_at: Optional[datetime] = None
	resolved_at: Optional[datetime] = None


@dataclass
class HealthStatus:
	"""组件健康检查结果"""
	component: str
	healthy: bool = True
	message: str = ""
	latency_ms: float = 0.0
	last_check: Optional[datetime] = None
	details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceStats:
	"""性能统计"""
	total_requests: int = 0
	avg_response_time_ms: float = 0.0
	p95_response_time_ms: float = 0.0
	p99_response_time_ms: float = 0.0
	error_rate: float = 0.0
	qps: float = 0.0
	period_start: Optional[datetime] = None
	period_end: Optional[datetime] = None
