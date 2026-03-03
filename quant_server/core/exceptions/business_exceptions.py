#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务异常定义

定义业务逻辑相关的异常，按照混合架构设计的模块划分。
"""

from typing import Any, Dict, Optional
from .base import BaseException
from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class BusinessException(BaseException):
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


class AnalysisException(BusinessException):
    """分析异常"""

    def __init__(
        self,
        message: str,
        analysis_type: Optional[str] = None,
        analysis_id: Optional[str] = None,
        metric_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化分析异常

        Args:
            message: 分析错误消息
            analysis_type: 分析类型
            analysis_id: 分析ID
            metric_name: 指标名称
            details: 额外详情
            cause: 原始异常
        """
        if analysis_type or analysis_id or metric_name:
            details = details or {}
            if analysis_type:
                details["analysis_type"] = analysis_type
            if analysis_id:
                details["analysis_id"] = analysis_id
            if metric_name:
                details["metric_name"] = metric_name

        super().__init__(
            message=message,
            error_code=ErrorCode.ANALYSIS_ERROR,
            business_domain="analysis",
            business_rule="analysis_calculation",
            details=details,
            cause=cause
        )


class BacktestException(BusinessException):
    """回测异常"""

    def __init__(
        self,
        message: str,
        backtest_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        period: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化回测异常

        Args:
            message: 回测错误消息
            backtest_id: 回测ID
            strategy_id: 策略ID
            period: 回测周期
            details: 额外详情
            cause: 原始异常
        """
        if backtest_id or strategy_id or period:
            details = details or {}
            if backtest_id:
                details["backtest_id"] = backtest_id
            if strategy_id:
                details["strategy_id"] = strategy_id
            if period:
                details["period"] = period

        super().__init__(
            message=message,
            error_code=ErrorCode.BACKTEST_ERROR,
            business_domain="backtest",
            business_rule="backtest_simulation",
            details=details,
            cause=cause
        )


class RiskException(BusinessException):
    """风控异常"""

    def __init__(
        self,
        message: str,
        risk_rule: Optional[str] = None,
        risk_level: Optional[str] = None,
        risk_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化风控异常

        Args:
            message: 风控错误消息
            risk_rule: 风控规则
            risk_level: 风险等级
            risk_type: 风险类型
            details: 额外详情
            cause: 原始异常
        """
        if risk_rule or risk_level or risk_type:
            details = details or {}
            if risk_rule:
                details["risk_rule"] = risk_rule
            if risk_level:
                details["risk_level"] = risk_level
            if risk_type:
                details["risk_type"] = risk_type

        super().__init__(
            message=message,
            error_code=ErrorCode.RISK_ERROR,
            business_domain="risk",
            business_rule="risk_control",
            details=details,
            cause=cause
        )


class AccountException(BusinessException):
    """账户异常"""

    def __init__(
        self,
        message: str,
        account_id: Optional[str] = None,
        account_number: Optional[str] = None,
        account_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化账户异常

        Args:
            message: 账户错误消息
            account_id: 账户ID
            account_number: 账户号码
            account_type: 账户类型
            details: 额外详情
            cause: 原始异常
        """
        if account_id or account_number or account_type:
            details = details or {}
            if account_id:
                details["account_id"] = account_id
            if account_number:
                details["account_number"] = account_number
            if account_type:
                details["account_type"] = account_type

        super().__init__(
            message=message,
            error_code=ErrorCode.ACCOUNT_ERROR,
            business_domain="account",
            business_rule="account_operation",
            details=details,
            cause=cause
        )


class PortfolioException(BusinessException):
    """投资组合异常"""

    def __init__(
        self,
        message: str,
        portfolio_id: Optional[str] = None,
        portfolio_name: Optional[str] = None,
        portfolio_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化投资组合异常

        Args:
            message: 投资组合错误消息
            portfolio_id: 投资组合ID
            portfolio_name: 投资组合名称
            portfolio_type: 投资组合类型
            details: 额外详情
            cause: 原始异常
        """
        if portfolio_id or portfolio_name or portfolio_type:
            details = details or {}
            if portfolio_id:
                details["portfolio_id"] = portfolio_id
            if portfolio_name:
                details["portfolio_name"] = portfolio_name
            if portfolio_type:
                details["portfolio_type"] = portfolio_type

        super().__init__(
            message=message,
            error_code=ErrorCode.PORTFOLIO_ERROR,
            business_domain="portfolio",
            business_rule="portfolio_management",
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


class PositionNotFoundException(BusinessException):
    """持仓不存在异常"""

    def __init__(
        self,
        message: str,
        position_id: Optional[str] = None,
        symbol: Optional[str] = None,
        account_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化持仓不存在异常

        Args:
            message: 错误消息
            position_id: 持仓ID
            symbol: 股票代码
            account_id: 账户ID
            details: 额外详情
            cause: 原始异常
        """
        if position_id or symbol or account_id:
            details = details or {}
            if position_id:
                details["position_id"] = position_id
            if symbol:
                details["symbol"] = symbol
            if account_id:
                details["account_id"] = account_id

        super().__init__(
            message=message,
            error_code=ErrorCode.POSITION_NOT_FOUND,
            business_domain="position",
            business_rule="position_existence",
            details=details,
            cause=cause
        )


class InsufficientBalanceException(BusinessException):
    """余额不足异常"""

    def __init__(
        self,
        message: str,
        account_id: Optional[str] = None,
        required_amount: Optional[float] = None,
        available_amount: Optional[float] = None,
        currency: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化余额不足异常

        Args:
            message: 错误消息
            account_id: 账户ID
            required_amount: 所需金额
            available_amount: 可用金额
            currency: 货币类型
            details: 额外详情
            cause: 原始异常
        """
        if account_id or required_amount or available_amount or currency:
            details = details or {}
            if account_id:
                details["account_id"] = account_id
            if required_amount:
                details["required_amount"] = required_amount
            if available_amount:
                details["available_amount"] = available_amount
            if currency:
                details["currency"] = currency

        super().__init__(
            message=message,
            error_code=ErrorCode.INSUFFICIENT_BALANCE,
            business_domain="account",
            business_rule="balance_sufficiency",
            details=details,
            cause=cause
        )


class DataException(BusinessException):
    """数据异常（业务层）"""

    def __init__(
        self,
        message: str,
        data_type: Optional[str] = None,
        data_source: Optional[str] = None,
        data_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化数据异常

        Args:
            message: 数据错误消息
            data_type: 数据类型
            data_source: 数据源
            data_id: 数据ID
            details: 额外详情
            cause: 原始异常
        """
        if data_type or data_source or data_id:
            details = details or {}
            if data_type:
                details["data_type"] = data_type
            if data_source:
                details["data_source"] = data_source
            if data_id:
                details["data_id"] = data_id

        super().__init__(
            message=message,
            error_code=ErrorCode.DATA_ERROR,
            business_domain="data",
            business_rule="data_processing",
            details=details,
            cause=cause
        )


class MarketException(BusinessException):
    """市场异常"""

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        exchange: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化市场异常

        Args:
            message: 市场错误消息
            symbol: 股票代码
            market: 市场类型
            exchange: 交易所
            details: 额外详情
            cause: 原始异常
        """
        if symbol or market or exchange:
            details = details or {}
            if symbol:
                details["symbol"] = symbol
            if market:
                details["market"] = market
            if exchange:
                details["exchange"] = exchange

        super().__init__(
            message=message,
            error_code=ErrorCode.MARKET_CLOSED,
            business_domain="market",
            business_rule="market_operation",
            details=details,
            cause=cause
        )


class TradeException(BusinessException):
    """交易异常"""

    def __init__(
        self,
        message: str,
        trade_id: Optional[str] = None,
        trade_type: Optional[str] = None,
        symbol: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化交易异常

        Args:
            message: 交易错误消息
            trade_id: 交易ID
            trade_type: 交易类型
            symbol: 股票代码
            details: 额外详情
            cause: 原始异常
        """
        if trade_id or trade_type or symbol:
            details = details or {}
            if trade_id:
                details["trade_id"] = trade_id
            if trade_type:
                details["trade_type"] = trade_type
            if symbol:
                details["symbol"] = symbol

        super().__init__(
            message=message,
            error_code=ErrorCode.TRADE_ERROR,
            business_domain="trade",
            business_rule="trade_execution",
            details=details,
            cause=cause
        )


class ExecutionException(BusinessException):
    """执行异常"""

    def __init__(
        self,
        message: str,
        execution_id: Optional[str] = None,
        execution_type: Optional[str] = None,
        algorithm: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化执行异常

        Args:
            message: 执行错误消息
            execution_id: 执行ID
            execution_type: 执行类型
            algorithm: 执行算法
            details: 额外详情
            cause: 原始异常
        """
        if execution_id or execution_type or algorithm:
            details = details or {}
            if execution_id:
                details["execution_id"] = execution_id
            if execution_type:
                details["execution_type"] = execution_type
            if algorithm:
                details["algorithm"] = algorithm

        super().__init__(
            message=message,
            error_code=ErrorCode.EXECUTION_ERROR,
            business_domain="execution",
            business_rule="execution_processing",
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


class SettlementException(BusinessException):
    """结算异常"""

    def __init__(
        self,
        message: str,
        settlement_id: Optional[str] = None,
        settlement_date: Optional[str] = None,
        settlement_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化结算异常

        Args:
            message: 结算错误消息
            settlement_id: 结算ID
            settlement_date: 结算日期
            settlement_type: 结算类型
            details: 额外详情
            cause: 原始异常
        """
        if settlement_id or settlement_date or settlement_type:
            details = details or {}
            if settlement_id:
                details["settlement_id"] = settlement_id
            if settlement_date:
                details["settlement_date"] = settlement_date
            if settlement_type:
                details["settlement_type"] = settlement_type

        super().__init__(
            message=message,
            error_code=ErrorCode.SETTLEMENT_ERROR,
            business_domain="settlement",
            business_rule="settlement_processing",
            details=details,
            cause=cause
        )

# 在文件末尾添加以下异常类定义


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