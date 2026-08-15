"""
系统级事件定义
与具体业务无关的系统级别事件

设计原则：
1. 通用性：不包含具体业务逻辑
2. 基础性：用于系统运行、监控、维护
3. 稳定性：事件定义稳定，不频繁变化
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List

from .base import BaseEvent
from .types import EventPriority, EventCategory


class SystemEventType(str, Enum):
	"""系统事件类型枚举"""
	SYSTEM_STARTED = "system.started"
	SYSTEM_STOPPED = "system.stopped"
	SYSTEM_HEARTBEAT = "system.heartbeat"
	SYSTEM_ALERT = "system.alert"
	SYSTEM_CONFIG_CHANGED = "system.config.changed"
	SYSTEM_MAINTENANCE_STARTED = "system.maintenance.started"
	SYSTEM_MAINTENANCE_COMPLETED = "system.maintenance.completed"
	MODULE_STARTED = "module.started"
	MODULE_STOPPED = "module.stopped"
	SERVICE_HEALTH_CHANGED = "service.health.changed"
	RESOURCE_LIMIT_WARNING = "resource.limit.warning"
	RESOURCE_LIMIT_EXCEEDED = "resource.limit.exceeded"


class SystemHealthStatus(str, Enum):
	"""系统健康状态"""
	HEALTHY = "healthy"
	DEGRADED = "degraded"
	UNHEALTHY = "unhealthy"
	UNKNOWN = "unknown"




class SystemStartedEvent(BaseEvent):
	"""
	系统启动事件
	当系统或子系统启动时触发
	"""

	def __init__ (
			self,
			system_name: str,
			version: str,
			startup_time_seconds: float,
			modules_loaded: List[str],
			config_summary: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			event_type=SystemEventType.SYSTEM_STARTED.value,
			source="system",
			module="core",
			priority=EventPriority.HIGH,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"system_name": system_name,
			"version": version,
			"startup_time_seconds": round(startup_time_seconds, 2),
			"modules_loaded": modules_loaded,
			"module_count": len(modules_loaded),
			"config_summary": config_summary or {},
			"startup_time": datetime.now().isoformat(),
			"status": "started",
			"health": SystemHealthStatus.HEALTHY.value,
		}

	@property
	def system_name (self) -> str:
		"""系统名称"""
		return self.data.get("system_name", "")

	@property
	def version (self) -> str:
		"""系统版本"""
		return self.data.get("version", "")

	@property
	def startup_time (self) -> datetime:
		"""启动时间"""
		return datetime.fromisoformat(self.data.get("startup_time", datetime.now().isoformat()))


class SystemStoppedEvent(BaseEvent):
	"""
	系统停止事件
	当系统或子系统正常停止时触发
	"""

	def __init__ (
			self,
			system_name: str,
			shutdown_reason: str,
			uptime_seconds: float,
			graceful: bool = True,
			modules_stopped: Optional[List[str]] = None,
			**kwargs
	):
		super().__init__(
			event_type=SystemEventType.SYSTEM_STOPPED.value,
			source="system",
			module="core",
			priority=EventPriority.HIGH,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"system_name": system_name,
			"shutdown_reason": shutdown_reason,
			"uptime_seconds": round(uptime_seconds, 2),
			"graceful": graceful,
			"modules_stopped": modules_stopped or [],
			"module_count": len(modules_stopped or []),
			"shutdown_time": datetime.now().isoformat(),
			"status": "stopped",
			"exit_code": 0 if graceful else 1,
		}

	@property
	def uptime_hours (self) -> float:
		"""运行时间（小时）"""
		uptime_seconds = self.data.get("uptime_seconds", 0)
		return round(uptime_seconds / 3600, 2)

	@property
	def was_graceful (self) -> bool:
		"""是否优雅停止"""
		return self.data.get("graceful", True)




class ReportGeneratedEvent(BaseEvent):
	"""
	报告生成事件
	当报告生成完成时触发
	"""

	def __init__ (
			self,
			task_id: str,
			report_type: str,
			report_path: str,
			metadata: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			event_type="report.generated",
			source="report",
			module="analysis",
			priority=EventPriority.NORMAL,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"task_id": task_id,
			"report_type": report_type,
			"report_path": report_path,
			"metadata": metadata or {},
			"generated_at": datetime.now().isoformat(),
		}


# 导出所有事件类
__all__ = [
	# 枚举
	"SystemEventType",
	"SystemHealthStatus",

	# 事件类
	"SystemStartedEvent",
	"SystemStoppedEvent",
	"ReportGeneratedEvent",
]