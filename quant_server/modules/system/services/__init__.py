# -*- coding: utf-8 -*-
"""
业务服务子包
提供系统模块的无状态业务逻辑，依赖 shared/ 层的 Repository。

包含模块：
1. auth_service   — 认证服务（AuthService）
2. user_service   — 用户服务（UserService）
3. role_service   — 角色服务（RoleService）
4. log_service    — 日志服务（LogService）
5. task_service   — 任务服务（TaskService）

位置：quant_server/modules/system/services/__init__.py
"""

from .auth_service import AuthService
from .user_service import UserService
from .role_service import RoleService
from .log_service import LogService

__all__ = [
    "AuthService",
    "UserService",
    "RoleService",
    "LogService",
]

__version__ = "1.0.0"
__author__ = "Quant Team"
__description__ = "系统业务服务层"
