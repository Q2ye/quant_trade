"""
引擎生命周期事件

统一引擎层所有生命周期事件，继承 BaseEvent，获得完整生命周期、追踪、序列化能力。

使用方式：
    event = EngineLifecycleEvent(
        engine_name="trade_engine",
        lifecycle_stage="started",
        engine_status="running",
    )
    await event_engine.put(event)

事件类型格式：engine.{stage}  (如 engine.started, engine.error, engine.health_check)
"""

from typing import Any, Dict, Optional

from .base import BaseEvent
from .types import EventPriority, EventCategory


class EngineLifecycleEvent(BaseEvent):
	"""引擎生命周期事件 — 统一引擎层所有事件类型

	覆盖 EngineBase._publish_event() 发出的所有事件：
	- engine_initialized / engine_initialize_failed
	- engine_started / engine_start_failed
	- engine_stopped / engine_stop_failed
	- engine_restart_started / engine_restart_completed / engine_restart_failed
	- engine_paused / engine_resumed
	- engine_health_check / engine_health_check_immediate
	- engine_status_response / engine_config_updated
	- engine_error / engine_auto_recovered
	- engine_graceful_shutdown_started / engine_graceful_shutdown_completed / engine_graceful_shutdown_failed
	- engine_metric / engine_alert (from EngineMonitor)
	- system_started / system_stopped (from MainEngine)
	- monitor.alert.created (from monitor handler)
	"""

	# str → EventPriority 映射（兼容旧代码的字符串 priority）
	_PRIORITY_MAP = {
		"critical": EventPriority.CRITICAL,
		"high": EventPriority.HIGH,
		"normal": EventPriority.NORMAL,
		"low": EventPriority.LOW,
	}

	def __init__ (
			self,
			engine_name: str,
			lifecycle_stage: str,
			engine_status: str = "unknown",
			details: Optional[Dict[str, Any]] = None,
			priority: Any = EventPriority.NORMAL,
			source: str = "",
			**kwargs,
	):
		"""初始化引擎生命周期事件

		Args:
			engine_name: 引擎名称
			lifecycle_stage: 生命周期阶段（如 "started", "error", "health_check"）
			engine_status: 引擎当前状态
			details: 事件详细数据
			priority: 优先级（支持 str "normal"/"high"/"critical"/"low" 或 EventPriority int）
			source: 事件源（覆盖默认的 engine:{name} 格式）
			**kwargs: 传递给 BaseEvent 的额外参数
		"""
		# 字符串优先级转换
		if isinstance(priority, str):
			priority = self._PRIORITY_MAP.get(priority.lower(), EventPriority.NORMAL)

		et = f"engine.{lifecycle_stage}"
		src = source or f"engine:{engine_name}"

		super().__init__(
			event_type=et,
			source=src,
			module="core",
			priority=priority,
			category=EventCategory.SYSTEM,
			**kwargs,
		)

		self.data = {
			"engine_name": engine_name,
			"lifecycle_stage": lifecycle_stage,
			"engine_status": engine_status,
			"details": details or {},
		}

	def to_dict (self) -> Dict[str, Any]:
		result = super().to_dict()
		return result


class SystemEvent(BaseEvent):
	"""通用系统事件

	供非引擎组件（如 API 依赖层）发布系统级事件。
	可作为一次性灵活事件的快速创建方式，无需定义专门的 Event 子类。
	"""

	_PRIORITY_MAP = {
		"critical": EventPriority.CRITICAL,
		"high": EventPriority.HIGH,
		"normal": EventPriority.NORMAL,
		"low": EventPriority.LOW,
	}

	def __init__ (
			self,
			event_type: str,
			data: Optional[Dict[str, Any]] = None,
			priority: Any = EventPriority.NORMAL,
			source: str = "system",
			**kwargs,
	):
		if isinstance(priority, str):
			priority = self._PRIORITY_MAP.get(priority.lower(), EventPriority.NORMAL)

		super().__init__(
			event_type=event_type,
			source=source,
			module="core",
			priority=priority,
			category=EventCategory.SYSTEM,
			**kwargs,
		)

		self.data = data or {}
