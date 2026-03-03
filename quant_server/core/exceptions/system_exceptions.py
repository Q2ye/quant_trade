#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统异常定义

定义系统运行时的异常，包括数据库、缓存、网络等基础设施异常。
按照混合架构设计，位于核心基础设施层。
"""

from typing import Any, Dict, Optional
from .base import BaseException
from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class SystemException(BaseException):
    """系统异常基类"""

    def __init__(
        self,
        message: str,
        error_code: str = ErrorCode.SYSTEM_ERROR,
        system_component: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化系统异常

        Args:
            message: 系统错误消息
            error_code: 错误代码
            system_component: 系统组件
            operation: 操作名称
            details: 额外详情
            cause: 原始异常
        """
        if system_component or operation:
            details = details or {}
            if system_component:
                details["system_component"] = system_component
            if operation:
                details["operation"] = operation

        super().__init__(
            message=message,
            error_code=error_code,
            error_type=ErrorType.SYSTEM_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details,
            cause=cause
        )


class DatabaseException(SystemException):
    """数据库异常"""

    def __init__(
        self,
        message: str,
        database: Optional[str] = None,
        query: Optional[str] = None,
        table: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化数据库异常

        Args:
            message: 数据库错误消息
            database: 数据库名称
            query: SQL查询
            table: 表名
            operation: 数据库操作
            details: 额外详情
            cause: 原始异常
        """
        if database or query or table or operation:
            details = details or {}
            if database:
                details["database"] = database
            if query:
                details["query"] = query
            if table:
                details["table"] = table
            if operation:
                details["operation"] = operation

        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_ERROR,
            system_component="database",
            operation=operation or "database_operation",
            details=details,
            cause=cause
        )


class CacheException(SystemException):
    """缓存异常"""

    def __init__(
        self,
        message: str,
        cache_type: Optional[str] = None,
        cache_key: Optional[str] = None,
        operation: Optional[str] = None,
        ttl: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化缓存异常

        Args:
            message: 缓存错误消息
            cache_type: 缓存类型 (redis, memory等)
            cache_key: 缓存键
            operation: 缓存操作 (get, set, delete等)
            ttl: 缓存过期时间
            details: 额外详情
            cause: 原始异常
        """
        if cache_type or cache_key or operation or ttl:
            details = details or {}
            if cache_type:
                details["cache_type"] = cache_type
            if cache_key:
                details["cache_key"] = cache_key
            if operation:
                details["operation"] = operation
            if ttl:
                details["ttl"] = ttl

        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_ERROR,
            system_component="cache",
            operation=operation or "cache_operation",
            details=details,
            cause=cause
        )


class ExternalServiceException(SystemException):
    """外部服务异常"""

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化外部服务异常

        Args:
            message: 外部服务错误消息
            service_name: 服务名称
            endpoint: API端点
            status_code: HTTP状态码
            response_data: 响应数据
            details: 额外详情
            cause: 原始异常
        """
        if service_name or endpoint or status_code or response_data:
            details = details or {}
            if service_name:
                details["service_name"] = service_name
            if endpoint:
                details["endpoint"] = endpoint
            if status_code:
                details["status_code"] = status_code
            if response_data:
                details["response_data"] = response_data

        super().__init__(
            message=message,
            error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            system_component="external_service",
            operation="service_call",
            details=details,
            cause=cause
        )


class NetworkException(SystemException):
    """网络异常"""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        retry_count: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化网络异常

        Args:
            message: 网络错误消息
            url: 请求URL
            method: HTTP方法
            status_code: HTTP状态码
            retry_count: 重试次数
            details: 额外详情
            cause: 原始异常
        """
        if url or method or status_code or retry_count:
            details = details or {}
            if url:
                details["url"] = url
            if method:
                details["method"] = method
            if status_code:
                details["status_code"] = status_code
            if retry_count:
                details["retry_count"] = retry_count

        super().__init__(
            message=message,
            error_code=ErrorCode.NETWORK_ERROR,
            system_component="network",
            operation="network_communication",
            details=details,
            cause=cause
        )


class TimeoutException(SystemException):
    """超时异常"""

    def __init__(
        self,
        message: str,
        timeout: Optional[float] = None,
        operation: Optional[str] = None,
        timeout_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化超时异常

        Args:
            message: 超时错误消息
            timeout: 超时时间（秒）
            operation: 操作名称
            timeout_type: 超时类型
            details: 额外详情
            cause: 原始异常
        """
        if timeout or operation or timeout_type:
            details = details or {}
            if timeout:
                details["timeout"] = timeout
            if operation:
                details["operation"] = operation
            if timeout_type:
                details["timeout_type"] = timeout_type

        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            system_component="system",
            operation=operation or "timeout_operation",
            details=details,
            cause=cause
        )


class ResourceExhaustedException(SystemException):
    """资源耗尽异常"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        limit: Optional[float] = None,
        current: Optional[float] = None,
        usage_percentage: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化资源耗尽异常

        Args:
            message: 资源耗尽错误消息
            resource_type: 资源类型 (memory, cpu, connection等)
            limit: 资源限制
            current: 当前使用量
            usage_percentage: 使用百分比
            details: 额外详情
            cause: 原始异常
        """
        if resource_type or limit or current or usage_percentage:
            details = details or {}
            if resource_type:
                details["resource_type"] = resource_type
            if limit:
                details["limit"] = limit
            if current:
                details["current"] = current
            if usage_percentage:
                details["usage_percentage"] = usage_percentage

        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_EXHAUSTED,
            system_component="system",
            operation="resource_management",
            details=details,
            cause=cause
        )


class FileSystemException(SystemException):
    """文件系统异常"""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        file_size: Optional[int] = None,
        permissions: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化文件系统异常

        Args:
            message: 文件系统错误消息
            file_path: 文件路径
            operation: 文件操作
            file_size: 文件大小
            permissions: 文件权限
            details: 额外详情
            cause: 原始异常
        """
        if file_path or operation or file_size or permissions:
            details = details or {}
            if file_path:
                details["file_path"] = file_path
            if operation:
                details["operation"] = operation
            if file_size:
                details["file_size"] = file_size
            if permissions:
                details["permissions"] = permissions

        super().__init__(
            message=message,
            error_code=ErrorCode.FILE_SYSTEM_ERROR,
            system_component="file_system",
            operation=operation or "file_operation",
            details=details,
            cause=cause
        )


class MemoryException(SystemException):
    """内存异常"""

    def __init__(
        self,
        message: str,
        memory_type: Optional[str] = None,
        allocated: Optional[int] = None,
        used: Optional[int] = None,
        limit: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化内存异常

        Args:
            message: 内存错误消息
            memory_type: 内存类型
            allocated: 已分配内存
            used: 已使用内存
            limit: 内存限制
            details: 额外详情
            cause: 原始异常
        """
        if memory_type or allocated or used or limit:
            details = details or {}
            if memory_type:
                details["memory_type"] = memory_type
            if allocated:
                details["allocated"] = allocated
            if used:
                details["used"] = used
            if limit:
                details["limit"] = limit

        super().__init__(
            message=message,
            error_code=ErrorCode.MEMORY_ERROR,
            system_component="memory",
            operation="memory_management",
            details=details,
            cause=cause
        )