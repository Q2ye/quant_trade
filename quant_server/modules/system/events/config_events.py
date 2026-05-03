# -*- coding: utf-8 -*-
"""系统模块配置事件"""

from core.events.base import BaseEvent
from core.events.types import EventCategory
from .types import SystemEventType


class ConfigUpdatedEvent(BaseEvent):
    """配置更新事件"""

    def __init__(self, config_key: str, old_value: str = "", new_value: str = "",
                 updated_by: str = "", source: str = ""):
        super().__init__(
            event_type=SystemEventType.CONFIG_UPDATED,
            source=source or f"config:{config_key}",
            module="system",
            category=EventCategory.SYSTEM,
            data={
                "config_key": config_key,
                "old_value": old_value,
                "new_value": new_value,
                "updated_by": updated_by,
            },
        )


class ConfigDeletedEvent(BaseEvent):
    """配置删除事件"""

    def __init__(self, config_key: str, deleted_by: str = "", source: str = ""):
        super().__init__(
            event_type=SystemEventType.CONFIG_DELETED,
            source=source or f"config:{config_key}",
            module="system",
            category=EventCategory.SYSTEM,
            data={
                "config_key": config_key,
                "deleted_by": deleted_by,
            },
        )
