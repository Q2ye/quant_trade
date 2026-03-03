#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证授权异常定义

定义认证授权相关的异常，包括登录、权限、令牌等异常。
按照混合架构设计，位于核心基础设施层。
"""

from typing import Any, Dict, Optional
from .base import BaseException
from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class AuthenticationException(BaseException):
    """认证异常"""

    def __init__(
        self,
        message: str,
        username: Optional[str] = None,
        authentication_method: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化认证异常

        Args:
            message: 认证错误消息
            username: 用户名
            authentication_method: 认证方法
            ip_address: IP地址
            details: 额外详情
            cause: 原始异常
        """
        if username or authentication_method or ip_address:
            details = details or {}
            if username:
                details["username"] = username
            if authentication_method:
                details["authentication_method"] = authentication_method
            if ip_address:
                details["ip_address"] = ip_address

        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            error_type=ErrorType.AUTHENTICATION_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details,
            cause=cause
        )


class AuthorizationException(BaseException):
    """授权异常"""

    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        required_permissions: Optional[list] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化授权异常

        Args:
            message: 授权错误消息
            user_id: 用户ID
            resource: 资源
            action: 操作
            required_permissions: 所需权限
            details: 额外详情
            cause: 原始异常
        """
        if user_id or resource or action or required_permissions:
            details = details or {}
            if user_id:
                details["user_id"] = user_id
            if resource:
                details["resource"] = resource
            if action:
                details["action"] = action
            if required_permissions:
                details["required_permissions"] = required_permissions

        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHORIZATION_ERROR,
            error_type=ErrorType.AUTHORIZATION_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details,
            cause=cause
        )


class TokenException(BaseException):
    """令牌异常"""

    def __init__(
        self,
        message: str,
        token_type: Optional[str] = None,
        token_expiry: Optional[str] = None,
        token_issuer: Optional[str] = None,
        token_subject: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化令牌异常

        Args:
            message: 令牌错误消息
            token_type: 令牌类型
            token_expiry: 令牌过期时间
            token_issuer: 令牌签发者
            token_subject: 令牌主体
            details: 额外详情
            cause: 原始异常
        """
        if token_type or token_expiry or token_issuer or token_subject:
            details = details or {}
            if token_type:
                details["token_type"] = token_type
            if token_expiry:
                details["token_expiry"] = token_expiry
            if token_issuer:
                details["token_issuer"] = token_issuer
            if token_subject:
                details["token_subject"] = token_subject

        super().__init__(
            message=message,
            error_code=ErrorCode.TOKEN_ERROR,
            error_type=ErrorType.AUTHENTICATION_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details,
            cause=cause
        )


class PermissionException(BaseException):
    """权限异常"""

    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        permission: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化权限异常

        Args:
            message: 权限错误消息
            user_id: 用户ID
            role: 角色
            permission: 权限
            resource: 资源
            details: 额外详情
            cause: 原始异常
        """
        if user_id or role or permission or resource:
            details = details or {}
            if user_id:
                details["user_id"] = user_id
            if role:
                details["role"] = role
            if permission:
                details["permission"] = permission
            if resource:
                details["resource"] = resource

        super().__init__(
            message=message,
            error_code=ErrorCode.PERMISSION_ERROR,
            error_type=ErrorType.AUTHORIZATION_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details,
            cause=cause
        )


class RateLimitException(BaseException):
    """速率限制异常"""

    def __init__(
        self,
        message: str,
        limit: Optional[int] = None,
        window: Optional[str] = None,
        remaining: Optional[int] = None,
        reset_time: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化速率限制异常

        Args:
            message: 速率限制错误消息
            limit: 限制数量
            window: 时间窗口
            remaining: 剩余数量
            reset_time: 重置时间
            details: 额外详情
            cause: 原始异常
        """
        if limit or window or remaining or reset_time:
            details = details or {}
            if limit:
                details["limit"] = limit
            if window:
                details["window"] = window
            if remaining:
                details["remaining"] = remaining
            if reset_time:
                details["reset_time"] = reset_time

        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_ERROR,
            error_type=ErrorType.RATE_LIMIT_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details,
            cause=cause
        )


class SessionException(BaseException):
    """会话异常"""

    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_expiry: Optional[str] = None,
        session_status: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化会话异常

        Args:
            message: 会话错误消息
            session_id: 会话ID
            user_id: 用户ID
            session_expiry: 会话过期时间
            session_status: 会话状态
            details: 额外详情
            cause: 原始异常
        """
        if session_id or user_id or session_expiry or session_status:
            details = details or {}
            if session_id:
                details["session_id"] = session_id
            if user_id:
                details["user_id"] = user_id
            if session_expiry:
                details["session_expiry"] = session_expiry
            if session_status:
                details["session_status"] = session_status

        super().__init__(
            message=message,
            error_code=ErrorCode.SESSION_EXPIRED,
            error_type=ErrorType.AUTHENTICATION_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details,
            cause=cause
        )