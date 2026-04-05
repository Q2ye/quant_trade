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


class AlertLevel(str, Enum):
	"""警报级别"""
	INFO = "info"
	WARNING = "warning"
	ERROR = "error"
	CRITICAL = "critical"


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


def _generate_sequence () -> int:
	"""生成序列号（简单实现）"""
	return int(datetime.now().timestamp())


def _calculate_health (component_statuses: Dict[str, Dict[str, Any]]) -> str:
	"""计算整体健康状态"""
	if not component_statuses:
		return SystemHealthStatus.UNKNOWN.value

	unhealthy_count = 0
	degraded_count = 0

	for status in component_statuses.values():
		health = status.get("health", SystemHealthStatus.UNKNOWN.value)
		if health == SystemHealthStatus.UNHEALTHY.value:
			unhealthy_count += 1
		elif health == SystemHealthStatus.DEGRADED.value:
			degraded_count += 1

	if unhealthy_count > 0:
		return SystemHealthStatus.UNHEALTHY.value
	elif degraded_count > 0:
		return SystemHealthStatus.DEGRADED.value
	else:
		return SystemHealthStatus.HEALTHY.value


class SystemHeartbeatEvent(BaseEvent):
	"""
	系统心跳事件
	定期触发，用于系统健康监控
	"""

	def __init__ (
			self,
			system_name: str,
			component_statuses: Dict[str, Dict[str, Any]],
			resource_usage: Dict[str, float],
			metrics: Optional[Dict[str, Any]] = None,
			interval_seconds: int = 60,
			**kwargs
	):
		super().__init__(
			event_type=SystemEventType.SYSTEM_HEARTBEAT.value,
			source="monitor",
			module="core",
			priority=EventPriority.LOW,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"system_name": system_name,
			"component_statuses": component_statuses,
			"component_count": len(component_statuses),
			"resource_usage": resource_usage,
			"metrics": metrics or {},
			"interval_seconds": interval_seconds,
			"timestamp": datetime.now().isoformat(),
			"sequence_number": _generate_sequence(),
			"health_status": _calculate_health(component_statuses),
		}

	@property
	def health_status (self) -> str:
		"""健康状态"""
		return self.data.get("health_status", SystemHealthStatus.UNKNOWN.value)

	@property
	def timestamp (self) -> datetime:
		"""心跳时间"""
		return datetime.fromisoformat(self.data.get("timestamp", datetime.now().isoformat()))


class SystemAlertEvent(BaseEvent):
	"""
	系统警报事件
	当系统出现异常或需要关注的情况时触发
	"""

	def __init__ (
			self,
			alert_id: str,
			alert_level: AlertLevel,
			alert_message: str,
			component: str,
			alert_details: Dict[str, Any],
			recommendation: Optional[str] = None,
			auto_resolve: bool = False,
			**kwargs
	):
		# 根据警报级别设置优先级
		priority_map = {
			AlertLevel.INFO: EventPriority.LOW,
			AlertLevel.WARNING: EventPriority.NORMAL,
			AlertLevel.ERROR: EventPriority.HIGH,
			AlertLevel.CRITICAL: EventPriority.CRITICAL,
		}
		priority = priority_map.get(alert_level, EventPriority.NORMAL)

		super().__init__(
			event_type=SystemEventType.SYSTEM_ALERT.value,
			source="alert",
			module="monitor",
			priority=priority,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"alert_id": alert_id,
			"alert_level": alert_level.value,
			"alert_message": alert_message,
			"component": component,
			"alert_details": alert_details,
			"recommendation": recommendation or "请检查相关组件",
			"auto_resolve": auto_resolve,
			"timestamp": datetime.now().isoformat(),
			"acknowledged": False,
			"resolved": False,
			"acknowledged_by": None,
			"acknowledged_at": None,
			"resolved_at": None,
		}

	def acknowledge (self, user: str) -> None:
		"""确认警报"""
		self.data["acknowledged"] = True
		self.data["acknowledged_by"] = user
		self.data["acknowledged_at"] = datetime.now().isoformat()

	def resolve (self) -> None:
		"""解决警报"""
		self.data["resolved"] = True
		self.data["resolved_at"] = datetime.now().isoformat()

	@property
	def is_acknowledged (self) -> bool:
		"""是否已确认"""
		return self.data.get("acknowledged", False)

	@property
	def is_resolved (self) -> bool:
		"""是否已解决"""
		return self.data.get("resolved", False)

	@property
	def alert_level (self) -> AlertLevel:
		"""警报级别"""
		return AlertLevel(self.data.get("alert_level", AlertLevel.INFO.value))


def _determine_change_type (old_value: Any, new_value: Any) -> str:
	"""确定变更类型"""
	if old_value is None and new_value is not None:
		return "add"
	elif old_value is not None and new_value is None:
		return "delete"
	else:
		return "update"


class SystemConfigChangedEvent(BaseEvent):
	"""
	系统配置变更事件
	当系统配置发生变化时触发
	"""

	def __init__ (
			self,
			config_key: str,
			old_value: Any,
			new_value: Any,
			changed_by: str,
			change_reason: Optional[str] = None,
			requires_restart: bool = False,
			**kwargs
	):
		super().__init__(
			event_type=SystemEventType.SYSTEM_CONFIG_CHANGED.value,
			source="config",
			module="core",
			priority=EventPriority.NORMAL,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"config_key": config_key,
			"old_value": old_value,
			"new_value": new_value,
			"changed_by": changed_by,
			"change_reason": change_reason or "配置更新",
			"requires_restart": requires_restart,
			"change_time": datetime.now().isoformat(),
			"change_type": _determine_change_type(old_value, new_value),
			"is_rollback": False,
		}

	def mark_as_rollback (self) -> None:
		"""标记为回滚"""
		self.data["is_rollback"] = True


class ModuleStartedEvent(BaseEvent):
	"""
	模块启动事件
	当某个模块启动时触发
	"""

	def __init__ (
			self,
			module_name: str,
			module_version: str,
			startup_time_seconds: float,
			dependencies: List[str],
			config_loaded: bool = True,
			**kwargs
	):
		super().__init__(
			event_type=SystemEventType.MODULE_STARTED.value,
			source=module_name,
			module=module_name,
			priority=EventPriority.NORMAL,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"module_name": module_name,
			"module_version": module_version,
			"startup_time_seconds": round(startup_time_seconds, 2),
			"dependencies": dependencies,
			"dependency_count": len(dependencies),
			"config_loaded": config_loaded,
			"startup_time": datetime.now().isoformat(),
			"status": "started",
			"health": SystemHealthStatus.HEALTHY.value,
		}


class ModuleStoppedEvent(BaseEvent):
	"""
	模块停止事件
	当某个模块停止时触发
	"""

	def __init__ (
			self,
			module_name: str,
			shutdown_reason: str,
			uptime_seconds: float,
			graceful: bool = True,
			**kwargs
	):
		super().__init__(
			event_type=SystemEventType.MODULE_STOPPED.value,
			source=module_name,
			module=module_name,
			priority=EventPriority.NORMAL,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"module_name": module_name,
			"shutdown_reason": shutdown_reason,
			"uptime_seconds": round(uptime_seconds, 2),
			"graceful": graceful,
			"shutdown_time": datetime.now().isoformat(),
			"status": "stopped",
		}


def _is_improvement (old_health: SystemHealthStatus, new_health: SystemHealthStatus) -> bool:
	"""判断是否健康状态改善"""
	health_order = {
		SystemHealthStatus.UNHEALTHY: 0,
		SystemHealthStatus.DEGRADED: 1,
		SystemHealthStatus.HEALTHY: 2,
		SystemHealthStatus.UNKNOWN: 3,
	}
	return health_order.get(new_health, 3) > health_order.get(old_health, 3)


class ServiceHealthChangedEvent(BaseEvent):
	"""
	服务健康状态变更事件
	当某个服务的健康状态发生变化时触发
	"""

	def __init__ (
			self,
			service_name: str,
			old_health: SystemHealthStatus,
			new_health: SystemHealthStatus,
			health_details: Dict[str, Any],
			**kwargs
	):
		# 根据健康状态变化设置优先级
		priority = EventPriority.NORMAL
		if new_health == SystemHealthStatus.UNHEALTHY:
			priority = EventPriority.HIGH
		elif new_health == SystemHealthStatus.DEGRADED:
			priority = EventPriority.NORMAL

		super().__init__(
			event_type=SystemEventType.SERVICE_HEALTH_CHANGED.value,
			source="health",
			module="monitor",
			priority=priority,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"service_name": service_name,
			"old_health": old_health.value,
			"new_health": new_health.value,
			"health_details": health_details,
			"change_time": datetime.now().isoformat(),
			"is_improvement": _is_improvement(old_health, new_health),
		}


def _generate_recommendation (resource_type: str, current_usage: float) -> str:
	"""生成资源使用建议"""
	recommendations = {
		"cpu": "考虑优化算法或增加计算资源",
		"memory": "考虑增加内存或优化内存使用",
		"disk": "清理临时文件或增加磁盘空间",
		"network": "检查网络带宽或优化数据传输",
	}
	return recommendations.get(resource_type, "请检查资源使用情况")


class ResourceLimitWarningEvent(BaseEvent):
	"""
	资源限制警告事件
	当系统资源使用接近限制时触发
	"""

	def __init__ (
			self,
			resource_type: str,  # cpu, memory, disk, network
			current_usage: float,  # 百分比
			limit_threshold: float,
			warning_threshold: float,
			usage_details: Dict[str, Any],
			**kwargs
	):
		super().__init__(
			event_type=SystemEventType.RESOURCE_LIMIT_WARNING.value,
			source="resource",
			module="monitor",
			priority=EventPriority.NORMAL,
			category=EventCategory.SYSTEM,
			**kwargs
		)

		self.data = {
			"resource_type": resource_type,
			"current_usage": round(current_usage, 2),
			"limit_threshold": limit_threshold,
			"warning_threshold": warning_threshold,
			"usage_details": usage_details,
			"timestamp": datetime.now().isoformat(),
			"is_critical": current_usage >= limit_threshold,
			"recommendation": _generate_recommendation(resource_type, current_usage),
		}


# 导出所有事件类
__all__ = [
	# 枚举
	"SystemEventType",
	"SystemHealthStatus",
	"AlertLevel",

	# 事件类
	"SystemStartedEvent",
	"SystemStoppedEvent",
	"SystemHeartbeatEvent",
	"SystemAlertEvent",
	"SystemConfigChangedEvent",
	"ModuleStartedEvent",
	"ModuleStoppedEvent",
	"ServiceHealthChangedEvent",
	"ResourceLimitWarningEvent",
]
