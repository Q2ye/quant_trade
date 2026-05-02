# -*- coding: utf-8 -*-
"""系统模块认证事件"""

from quant_server.core.events.base import BaseEvent
from quant_server.core.events.types import EventCategory, EventPriority
from .types import SystemEventType


class AuthLoginSuccessEvent(BaseEvent):
    """登录成功事件"""

    def __init__(self, user_id: str, username: str, ip_address: str = "", source: str = ""):
        super().__init__(
            event_type=SystemEventType.AUTH_LOGIN_SUCCESS,
            source=source or f"user:{user_id}",
            module="system",
            category=EventCategory.SYSTEM,
            data={"user_id": user_id, "username": username, "ip_address": ip_address},
        )


class AuthLoginFailedEvent(BaseEvent):
    """登录失败事件（安全敏感，高优先级）"""

    def __init__(self, username: str, reason: str, ip_address: str = "", source: str = ""):
        super().__init__(
            event_type=SystemEventType.AUTH_LOGIN_FAILED,
            source=source or "system:auth",
            module="system",
            category=EventCategory.SYSTEM,
            priority=EventPriority.HIGH,
            data={"username": username, "reason": reason, "ip_address": ip_address},
        )


class AuthRegisteredEvent(BaseEvent):
    """用户注册事件"""

    def __init__(self, user_id: str, username: str, source: str = ""):
        super().__init__(
            event_type=SystemEventType.AUTH_REGISTERED,
            source=source or f"user:{user_id}",
            module="system",
            category=EventCategory.SYSTEM,
            data={"user_id": user_id, "username": username},
        )
