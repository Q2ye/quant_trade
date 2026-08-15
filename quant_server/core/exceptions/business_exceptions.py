#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务异常定义

定义业务逻辑相关的异常，按照混合架构设计的模块划分。
"""

from typing import Any, Dict, Optional
from .base import QuantBaseException
from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class BusinessException(QuantBaseException):
    """业务异常基类"""

    def __init__(
        self,
        message: str,
        error_code: str = ErrorCode.BUSINESS_ERROR,
        business_domain: Optional[str] = None,
        business_rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化业务异常

        Args:
            message: 业务错误消息
            error_code: 错误代码
            business_domain: 业务领域
            business_rule: 违反的业务规则
            details: 额外详情
            cause: 原始异常
        """
        if business_domain or business_rule:
            details = details or {}
            if business_domain:
                details["business_domain"] = business_domain
            if business_rule:
                details["business_rule"] = business_rule

        super().__init__(
            message=message,
            error_code=error_code,
            error_type=ErrorType.BUSINESS_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details,
            cause=cause
        )


class StrategyException(BusinessException):
    """策略异常"""

    def __init__(
        self,
        message: str,
        strategy_id: Optional[str] = None,
        strategy_name: Optional[str] = None,
        strategy_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化策略异常

        Args:
            message: 策略错误消息
            strategy_id: 策略ID
            strategy_name: 策略名称
            strategy_type: 策略类型
            details: 额外详情
            cause: 原始异常
        """
        if strategy_id or strategy_name or strategy_type:
            details = details or {}
            if strategy_id:
                details["strategy_id"] = strategy_id
            if strategy_name:
                details["strategy_name"] = strategy_name
            if strategy_type:
                details["strategy_type"] = strategy_type

        super().__init__(
            message=message,
            error_code=ErrorCode.STRATEGY_ERROR,
            business_domain="strategy",
            business_rule="strategy_execution",
            details=details,
            cause=cause
        )






class OrderException(BusinessException):
    """订单异常"""

    def __init__(
        self,
        message: str,
        order_id: Optional[str] = None,
        order_type: Optional[str] = None,
        symbol: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化订单异常

        Args:
            message: 订单错误消息
            order_id: 订单ID
            order_type: 订单类型
            symbol: 股票代码
            details: 额外详情
            cause: 原始异常
        """
        if order_id or order_type or symbol:
            details = details or {}
            if order_id:
                details["order_id"] = order_id
            if order_type:
                details["order_type"] = order_type
            if symbol:
                details["symbol"] = symbol

        super().__init__(
            message=message,
            error_code=ErrorCode.ORDER_ERROR,
            business_domain="order",
            business_rule="order_processing",
            details=details,
            cause=cause
        )






class RiskControlException(BusinessException):
    """风险控制异常"""

    def __init__(
        self,
        message: str,
        rule_id: Optional[str] = None,
        rule_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化风险控制异常

        Args:
            message: 风控错误消息
            rule_id: 规则ID
            rule_type: 规则类型
            risk_level: 风险等级
            details: 额外详情
            cause: 原始异常
        """
        if rule_id or rule_type or risk_level:
            details = details or {}
            if rule_id:
                details["rule_id"] = rule_id
            if rule_type:
                details["rule_type"] = rule_type
            if risk_level:
                details["risk_level"] = risk_level

        super().__init__(
            message=message,
            error_code=ErrorCode.RISK_CONTROL_REJECTED,
            business_domain="risk_control",
            business_rule="risk_control_check",
            details=details,
            cause=cause
        )




class ValidationException(BusinessException):
    """验证异常（业务层数据验证）"""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化验证异常

        Args:
            message: 验证错误消息
            field_name: 字段名称
            field_value: 字段值
            validation_rule: 验证规则
            details: 额外详情
            cause: 原始异常
        """
        if field_name or field_value or validation_rule:
            details = details or {}
            if field_name:
                details["field_name"] = field_name
            if field_value:
                details["field_value"] = field_value
            if validation_rule:
                details["validation_rule"] = validation_rule

        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            business_domain="validation",
            business_rule="data_validation",
            details=details,
            cause=cause
        )


class ResourceNotFoundException(BusinessException):
    """资源未找到异常"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化资源未找到异常

        Args:
            message: 错误消息
            resource_type: 资源类型（如：user, account, order等）
            resource_id: 资源ID
            resource_name: 资源名称
            details: 额外详情
            cause: 原始异常
        """
        if resource_type or resource_id or resource_name:
            details = details or {}
            if resource_type:
                details["resource_type"] = resource_type
            if resource_id:
                details["resource_id"] = resource_id
            if resource_name:
                details["resource_name"] = resource_name

        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            business_domain="resource",
            business_rule="resource_existence",
            details=details,
            cause=cause
        )


class DataNotFoundException(BusinessException):
    """数据未找到异常"""

    def __init__(
        self,
        message: str,
        data_type: Optional[str] = None,
        data_id: Optional[str] = None,
        data_source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化数据未找到异常

        Args:
            message: 错误消息
            data_type: 数据类型
            data_id: 数据ID
            data_source: 数据源
            details: 额外详情
            cause: 原始异常
        """
        if data_type or data_id or data_source:
            details = details or {}
            if data_type:
                details["data_type"] = data_type
            if data_id:
                details["data_id"] = data_id
            if data_source:
                details["data_source"] = data_source

        super().__init__(
            message=message,
            error_code=ErrorCode.DATA_NOT_FOUND,
            business_domain="data",
            business_rule="data_existence",
            details=details,
            cause=cause
        )


class PermissionDeniedException(BusinessException):
    """权限不足异常"""

    def __init__(
        self,
        message: str,
        permission_required: Optional[str] = None,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化权限不足异常

        Args:
            message: 错误消息
            permission_required: 所需权限
            user_id: 用户ID
            role: 用户角色
            resource_id: 资源ID
            details: 额外详情
            cause: 原始异常
        """
        if permission_required or user_id or role or resource_id:
            details = details or {}
            if permission_required:
                details["permission_required"] = permission_required
            if user_id:
                details["user_id"] = user_id
            if role:
                details["role"] = role
            if resource_id:
                details["resource_id"] = resource_id

        super().__init__(
            message=message,
            error_code=ErrorCode.PERMISSION_DENIED,
            business_domain="security",
            business_rule="access_control",
            details=details,
            cause=cause
        )