# -*- coding: utf-8 -*-
"""
认证授权子包
提供身份验证、权限鉴权、JWT 令牌管理功能。

包含模块：
1. authentication — 身份验证（AuthenticationManager）
2. authorization  — 权限鉴权（AuthorizationManager）
3. jwt_handler    — JWT 令牌提取/验证/黑名单

位置：quant_server/modules/system/auth/__init__.py
"""

from .authentication import AuthenticationManager
from .authorization import AuthorizationManager
from .jwt_handler import (
    get_token_from_header,
    verify_access_token,
    blacklist_token,
    is_token_blacklisted,
    clear_expired_blacklist,
)

__all__ = [
    "AuthenticationManager",
    "AuthorizationManager",
    "get_token_from_header",
    "verify_access_token",
    "blacklist_token",
    "is_token_blacklisted",
    "clear_expired_blacklist",
]

__version__ = "1.0.0"
__author__ = "Quant Team"
__description__ = "认证授权子包"
