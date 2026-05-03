# -*- coding: utf-8 -*-
"""
系统监控事件

当 SystemMonitorEngine 采集到系统指标或检测到健康状态变化时发布。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

from modules.monitor.events.types import SystemMetricsData


@dataclass
class SystemMonitorEvent:
	"""系统监控事件 — 封装为 EventEngine 兼容的事件对象"""

	event_type: str
	source: str = "monitor.system_monitor"
	data: Dict[str, Any] = field(default_factory=dict)
	timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	priority: str = "normal"

	@classmethod
	def metrics_collected (cls, metrics: SystemMetricsData) -> "SystemMonitorEvent":
		return cls(
			event_type="monitor.system.metrics.collected",
			data={
				"cpu_usage": metrics.cpu_usage,
				"memory_usage": metrics.memory_usage,
				"disk_usage": metrics.disk_usage,
				"network_in": metrics.network_in,
				"network_out": metrics.network_out,
				"process_count": metrics.process_count,
				"thread_count": metrics.thread_count,
			},
		)

	@classmethod
	def health_changed (cls, component: str, old_status: str, new_status: str,
	                    message: str = "") -> "SystemMonitorEvent":
		return cls(
			event_type="monitor.system.health.changed",
			priority="high",
			data={
				"component": component,
				"old_status": old_status,
				"new_status": new_status,
				"message": message,
			},
		)

	@classmethod
	def component_down (cls, component: str, error: str) -> "SystemMonitorEvent":
		return cls(
			event_type="monitor.system.component.down",
			priority="critical",
			data={"component": component, "error": error},
		)
