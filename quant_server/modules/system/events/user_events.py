# -*- coding: utf-8 -*-
"""系统模块用户事件"""

from core.events.base import BaseEvent
from core.events.types import EventCategory
from .types import SystemEventType


class UserCreatedEvent(BaseEvent):
    """用户创建事件"""

    def __init__(self, user_id: str, username: str, role: str, source: str = ""):
        super().__init__(
            event_type=SystemEventType.USER_CREATED,
            source=source or f"user:{user_id}",
            module="system",
            category=EventCategory.SYSTEM,
            data={"user_id": user_id, "username": username, "role": role},
        )


class UserLoginEvent(BaseEvent):
    """用户登录事件"""

    def __init__(self, user_id: str, username: str, ip_address: str = "", source: str = ""):
        super().__init__(
            event_type=SystemEventType.USER_LOGIN,
            source=source or f"user:{user_id}",
            module="system",
            category=EventCategory.SYSTEM,
            data={"user_id": user_id, "username": username, "ip_address": ip_address},
        )


class UserUpdatedEvent(BaseEvent):
    """用户更新事件"""

    def __init__(self, user_id: str, changed_fields: list, source: str = ""):
        super().__init__(
            event_type=SystemEventType.USER_UPDATED,
            source=source or f"user:{user_id}",
            module="system",
            category=EventCategory.SYSTEM,
            data={"user_id": user_id, "changed_fields": changed_fields},
        )
