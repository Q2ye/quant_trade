# -*- coding: utf-8 -*-
"""系统模块任务事件"""

from quant_server.core.events.base import BaseEvent
from quant_server.core.events.types import EventCategory, EventPriority
from .types import SystemEventType


class TaskScheduledEvent(BaseEvent):
    """任务调度事件"""

    def __init__(self, task_id: str, task_name: str, trigger: str = "",
                 source: str = ""):
        super().__init__(
            event_type=SystemEventType.TASK_SCHEDULED,
            source=source or f"task:{task_id}",
            module="system",
            category=EventCategory.SYSTEM,
            data={
                "task_id": task_id,
                "task_name": task_name,
                "trigger": trigger,
            },
        )


class TaskExecutedEvent(BaseEvent):
    """任务执行完成事件"""

    def __init__(self, task_id: str, task_name: str, status: str,
                 duration_ms: float = 0.0, error: str = "", source: str = ""):
        super().__init__(
            event_type=SystemEventType.TASK_EXECUTED,
            source=source or f"task:{task_id}",
            module="system",
            category=EventCategory.SYSTEM,
            data={
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
                "duration_ms": duration_ms,
                "error": error,
            },
        )


class TaskFailedEvent(BaseEvent):
    """任务失败事件"""

    def __init__(self, task_id: str, task_name: str, error: str,
                 source: str = ""):
        super().__init__(
            event_type=SystemEventType.TASK_FAILED,
            source=source or f"task:{task_id}",
            module="system",
            category=EventCategory.SYSTEM,
            priority=EventPriority.HIGH,
            data={
                "task_id": task_id,
                "task_name": task_name,
                "error": error,
            },
        )
