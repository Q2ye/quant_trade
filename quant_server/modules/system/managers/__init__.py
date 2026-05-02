# -*- coding: utf-8 -*-
"""
资源管理器子包
提供用户、权限、配置等资源的生命周期管理。

包含模块：
1. user_manager       — 用户管理器（UserManager）
2. permission_manager — 权限管理器（PermissionManager）
3. config_manager     — 配置管理器（ConfigManager）

位置：quant_server/modules/system/managers/__init__.py
"""

from .user_manager import UserManager
from .permission_manager import PermissionManager
from .config_manager import ConfigManager

__all__ = [
    "UserManager",
    "PermissionManager",
    "ConfigManager",
]

__version__ = "1.0.0"
__author__ = "Quant Team"
__description__ = "系统资源管理器"
