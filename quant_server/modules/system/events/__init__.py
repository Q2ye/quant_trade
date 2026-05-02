# -*- coding: utf-8 -*-
"""
系统模块事件子包
定义系统模块所有事件类型和事件类。

包含模块：
1. types         — 事件类型枚举（SystemEventType）
2. auth_events   — 认证事件（登录成功/失败、注册）
3. config_events — 配置事件（更新、删除）
4. user_events   — 用户事件（创建、登录、更新）
5. task_events   — 任务事件（调度、执行、失败）

位置：quant_server/modules/system/events/__init__.py
"""

from .types import SystemEventType
from .auth_events import (
    AuthLoginSuccessEvent,
    AuthLoginFailedEvent,
    AuthRegisteredEvent,
)
from .config_events import (
    ConfigUpdatedEvent,
    ConfigDeletedEvent,
)
from .user_events import (
    UserCreatedEvent,
    UserLoginEvent,
    UserUpdatedEvent,
)
from .task_events import (
    TaskScheduledEvent,
    TaskExecutedEvent,
    TaskFailedEvent,
)

__all__ = [
    "SystemEventType",
    "AuthLoginSuccessEvent",
    "AuthLoginFailedEvent",
    "AuthRegisteredEvent",
    "ConfigUpdatedEvent",
    "ConfigDeletedEvent",
    "UserCreatedEvent",
    "UserLoginEvent",
    "UserUpdatedEvent",
    "TaskScheduledEvent",
    "TaskExecutedEvent",
    "TaskFailedEvent",
]

__version__ = "1.0.0"
__author__ = "Quant Team"
__description__ = "系统模块事件定义"
