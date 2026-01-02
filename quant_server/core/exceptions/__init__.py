#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心异常模块

提供量化交易系统的统一异常处理框架，包括：
1. 异常基类：定义统一的异常接口
2. 业务异常：业务逻辑相关的异常
3. 系统异常：系统运行时的异常
4. 认证异常：认证授权相关的异常
5. 数据异常：数据相关的异常
6. 交易异常：交易相关的异常

所有异常都继承自BaseException，提供统一的错误处理接口。
"""

from .base import (
	BaseException,
	ValidationException,
	ConfigurationException,
	ServiceException
)
from .business_exceptions import (
	BusinessException,
	StrategyException,
	AnalysisException,
	BacktestException,
	RiskException,
	AccountException,
	PortfolioException,
	OrderException,
	PositionNotFoundException,
	InsufficientBalanceException
)
from .system_exceptions import (
	SystemException,
	DatabaseException,
	CacheException,
	ExternalServiceException,
	NetworkException,
	TimeoutException,
	ResourceExhaustedException
)
from .auth_exceptions import (
	AuthenticationException,
	AuthorizationException,
	TokenException,
	PermissionException,
	RateLimitException
)
from .data_exceptions import (
	DataException,
	DataNotFoundException,
	DataValidationException,
	DataSyncException,
	DataQualityException
)
from .trade_exceptions import (
	TradeException,
	OrderRejectedException,
	OrderTimeoutException,
	ExecutionException,
	MarketClosedException,
	InvalidPriceException,
	InsufficientVolumeException
)
from .types import ErrorType, ErrorSeverity
from .error_codes import ErrorCode, get_error_message
from .handlers import (
	ExceptionHandler,
	LoggingExceptionHandler,
	NotificationExceptionHandler,
	RetryExceptionHandler
)

__all__ = [
	# 基础异常
	'BaseException',
	'ValidationException',
	'ConfigurationException',
	'ServiceException',

	# 业务异常
	'BusinessException',
	'StrategyException',
	'AnalysisException',
	'BacktestException',
	'RiskException',
	'AccountException',
	'PortfolioException',
	'OrderException',
	'PositionNotFoundException',
	'InsufficientBalanceException',

	# 系统异常
	'SystemException',
	'DatabaseException',
	'CacheException',
	'ExternalServiceException',
	'NetworkException',
	'TimeoutException',
	'ResourceExhaustedException',

	# 认证异常
	'AuthenticationException',
	'AuthorizationException',
	'TokenException',
	'PermissionException',
	'RateLimitException',

	# 数据异常
	'DataException',
	'DataNotFoundException',
	'DataValidationException',
	'DataSyncException',
	'DataQualityException',

	# 交易异常
	'TradeException',
	'OrderRejectedException',
	'OrderTimeoutException',
	'ExecutionException',
	'MarketClosedException',
	'InvalidPriceException',
	'InsufficientVolumeException',

	# 异常类型和错误码
	'ErrorType',
	'ErrorSeverity',
	'ErrorCode',
	'get_error_message',

	# 异常处理器
	'ExceptionHandler',
	'LoggingExceptionHandler',
	'NotificationExceptionHandler',
	'RetryExceptionHandler'
]

__version__ = '1.0.0'
__author__ = '量化平台团队'
__description__ = '量化交易系统核心异常处理模块'