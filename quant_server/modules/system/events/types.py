# -*- coding: utf-8 -*-
"""系统模块事件类型定义"""

from enum import Enum


class SystemEventType(str, Enum):
    """系统模块事件类型枚举"""

    # 用户事件
    USER_CREATED = "system.user.created"
    USER_UPDATED = "system.user.updated"
    USER_DELETED = "system.user.deleted"
    USER_LOGIN = "system.user.login"
    USER_LOGOUT = "system.user.logout"
    USER_ACTIVATED = "system.user.activated"
    USER_DEACTIVATED = "system.user.deactivated"
    USER_ROLE_CHANGED = "system.user.role_changed"
    USER_PASSWORD_CHANGED = "system.user.password_changed"

    # 认证事件
    AUTH_LOGIN_SUCCESS = "system.auth.login_success"
    AUTH_LOGIN_FAILED = "system.auth.login_failed"
    AUTH_LOGOUT = "system.auth.logout"
    AUTH_TOKEN_REFRESHED = "system.auth.token_refreshed"
    AUTH_REGISTERED = "system.auth.registered"

    # 角色事件
    ROLE_CREATED = "system.role.created"
    ROLE_UPDATED = "system.role.updated"
    ROLE_DELETED = "system.role.deleted"

    # 配置事件
    CONFIG_UPDATED = "system.config.updated"
    CONFIG_DELETED = "system.config.deleted"

    # 任务事件
    TASK_SCHEDULED = "system.task.scheduled"
    TASK_EXECUTED = "system.task.executed"
    TASK_FAILED = "system.task.failed"
