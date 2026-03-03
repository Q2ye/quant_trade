#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常类型和严重程度定义

定义错误的类型分类和严重程度等级。
按照混合架构设计，位于核心基础设施层。
"""

from enum import Enum


class ErrorType(str, Enum):
	"""
	错误类型枚举

	定义系统中可能出现的错误类型，便于分类处理。
	"""
	# 验证错误
	VALIDATION_ERROR = "validation_error"
	SCHEMA_ERROR = "schema_error"
	FIELD_ERROR = "field_error"
	PARAMETER_ERROR = "parameter_error"
	DATA_VALIDATION_ERROR = "data_validation_error"
	BUSINESS_RULE_ERROR = "business_rule_error"

	# 配置错误
	CONFIGURATION_ERROR = "configuration_error"
	SETTINGS_ERROR = "settings_error"
	ENVIRONMENT_ERROR = "environment_error"

	# 业务错误
	BUSINESS_ERROR = "business_error"
	STRATEGY_ERROR = "strategy_error"
	ANALYSIS_ERROR = "analysis_error"
	BACKTEST_ERROR = "backtest_error"
	RISK_ERROR = "risk_error"
	ACCOUNT_ERROR = "account_error"
	PORTFOLIO_ERROR = "portfolio_error"
	ORDER_ERROR = "order_error"
	TRADE_ERROR = "trade_error"
	EXECUTION_ERROR = "execution_error"
	SETTLEMENT_ERROR = "settlement_error"
	RECONCILIATION_ERROR = "reconciliation_error"

	# 数据错误
	DATA_ERROR = "data_error"
	DATA_NOT_FOUND = "data_not_found"
	DATA_SYNC_ERROR = "data_sync_error"
	DATA_QUALITY_ERROR = "data_quality_error"
	DATA_FORMAT_ERROR = "data_format_error"
	DATA_SOURCE_ERROR = "data_source_error"
	DATA_TRANSFORMATION_ERROR = "data_transformation_error"

	# 系统错误
	SYSTEM_ERROR = "system_error"
	DATABASE_ERROR = "database_error"
	CACHE_ERROR = "cache_error"
	FILE_SYSTEM_ERROR = "file_system_error"
	MEMORY_ERROR = "memory_error"
	PROCESS_ERROR = "process_error"
	THREAD_ERROR = "thread_error"
	CONCURRENCY_ERROR = "concurrency_error"
	DEADLOCK_ERROR = "deadlock_error"
	CIRCUIT_BREAKER_ERROR = "circuit_breaker_error"

	# 网络错误
	NETWORK_ERROR = "network_error"
	CONNECTION_ERROR = "connection_error"
	TIMEOUT_ERROR = "timeout_error"
	SSL_ERROR = "ssl_error"
	DNS_ERROR = "dns_error"

	# 外部服务错误
	EXTERNAL_SERVICE_ERROR = "external_service_error"
	API_ERROR = "api_error"
	SERVICE_UNAVAILABLE = "service_unavailable"
	RATE_LIMIT_ERROR = "rate_limit_error"

	# 认证授权错误
	AUTHENTICATION_ERROR = "authentication_error"
	AUTHORIZATION_ERROR = "authorization_error"
	PERMISSION_ERROR = "permission_error"
	TOKEN_ERROR = "token_error"
	SESSION_ERROR = "session_error"
	CREDENTIALS_ERROR = "credentials_error"

	# 资源错误
	RESOURCE_ERROR = "resource_error"
	RESOURCE_EXHAUSTED = "resource_exhausted"
	RESOURCE_NOT_FOUND = "resource_not_found"
	RESOURCE_LIMIT_ERROR = "resource_limit_error"



class ErrorLevel(Enum):
    """错误级别（兼容性）"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorSeverity(str, Enum):
	"""
	错误严重程度枚举

	定义错误的严重程度，便于决定处理策略和报警级别。
	"""
	DEBUG = "debug"  # 调试信息，不影响功能
	INFO = "info"  # 一般信息，可能需要关注
	WARNING = "warning"  # 警告，功能可能受影响
	ERROR = "error"  # 错误，功能受影响
	CRITICAL = "critical"  # 严重错误，系统可能崩溃

	@classmethod
	def from_level (cls, level: int) -> 'ErrorSeverity':
		"""
		根据数字级别获取严重程度

		Args:
			level: 数字级别 (0-4)

		Returns:
			对应的严重程度
		"""
		levels = {
			0: cls.DEBUG,
			1: cls.INFO,
			2: cls.WARNING,
			3: cls.ERROR,
			4: cls.CRITICAL
		}
		return levels.get(level, cls.ERROR)

	def to_level (self) -> int:
		"""
		转换为数字级别

		Returns:
			数字级别 (0-4)
		"""
		mapping = {
			self.DEBUG: 0,
			self.INFO: 1,
			self.WARNING: 2,
			self.ERROR: 3,
			self.CRITICAL: 4
		}
		return mapping.get(self, 2)

	def is_critical (self) -> bool:
		"""
		检查是否为严重错误

		Returns:
			是否为严重错误
		"""
		return self in [self.ERROR, self.CRITICAL]

	def should_alert (self) -> bool:
		"""
		检查是否需要报警

		Returns:
			是否需要报警
		"""
		return self in [self.ERROR, self.CRITICAL]

	def should_retry (self) -> bool:
		"""
		检查是否应该重试

		Returns:
			是否应该重试
		"""
		return self not in [self.CRITICAL]


class ErrorCategory(str, Enum):
	"""
	错误分类枚举

	根据错误影响范围进行分类。
	"""
	CLIENT_ERROR = "client_error"  # 客户端错误 (400系列)
	SERVER_ERROR = "server_error"  # 服务器错误 (500系列)
	EXTERNAL_ERROR = "external_error"  # 外部服务错误
	BUSINESS_ERROR = "business_error"  # 业务逻辑错误
	INFRASTRUCTURE_ERROR = "infrastructure_error"  # 基础设施错误
	SECURITY_ERROR = "security_error"  # 安全错误
	DATA_ERROR = "data_error"  # 数据错误
	VALIDATION_ERROR = "validation_error"  # 验证错误
	CONFIGURATION_ERROR = "configuration_error"  # 配置错误

	@classmethod
	def from_error_type (cls, error_type: ErrorType) -> 'ErrorCategory':
		"""
		根据错误类型获取分类

		Args:
			error_type: 错误类型

		Returns:
			错误分类
		"""
		category_mapping = {
			# 验证错误
			ErrorType.VALIDATION_ERROR: cls.VALIDATION_ERROR,
			ErrorType.SCHEMA_ERROR: cls.VALIDATION_ERROR,
			ErrorType.FIELD_ERROR: cls.VALIDATION_ERROR,
			ErrorType.PARAMETER_ERROR: cls.VALIDATION_ERROR,
			ErrorType.DATA_VALIDATION_ERROR: cls.VALIDATION_ERROR,
			ErrorType.BUSINESS_RULE_ERROR: cls.VALIDATION_ERROR,

			# 配置错误
			ErrorType.CONFIGURATION_ERROR: cls.CONFIGURATION_ERROR,
			ErrorType.SETTINGS_ERROR: cls.CONFIGURATION_ERROR,
			ErrorType.ENVIRONMENT_ERROR: cls.CONFIGURATION_ERROR,

			# 业务错误
			ErrorType.BUSINESS_ERROR: cls.BUSINESS_ERROR,
			ErrorType.STRATEGY_ERROR: cls.BUSINESS_ERROR,
			ErrorType.ANALYSIS_ERROR: cls.BUSINESS_ERROR,
			ErrorType.BACKTEST_ERROR: cls.BUSINESS_ERROR,
			ErrorType.RISK_ERROR: cls.BUSINESS_ERROR,
			ErrorType.ACCOUNT_ERROR: cls.BUSINESS_ERROR,
			ErrorType.PORTFOLIO_ERROR: cls.BUSINESS_ERROR,
			ErrorType.ORDER_ERROR: cls.BUSINESS_ERROR,
			ErrorType.TRADE_ERROR: cls.BUSINESS_ERROR,
			ErrorType.EXECUTION_ERROR: cls.BUSINESS_ERROR,
			ErrorType.SETTLEMENT_ERROR: cls.BUSINESS_ERROR,
			ErrorType.RECONCILIATION_ERROR: cls.BUSINESS_ERROR,

			# 数据错误
			ErrorType.DATA_ERROR: cls.DATA_ERROR,
			ErrorType.DATA_NOT_FOUND: cls.DATA_ERROR,
			ErrorType.DATA_SYNC_ERROR: cls.DATA_ERROR,
			ErrorType.DATA_QUALITY_ERROR: cls.DATA_ERROR,
			ErrorType.DATA_FORMAT_ERROR: cls.DATA_ERROR,
			ErrorType.DATA_SOURCE_ERROR: cls.DATA_ERROR,
			ErrorType.DATA_TRANSFORMATION_ERROR: cls.DATA_ERROR,

			# 系统错误
			ErrorType.SYSTEM_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.DATABASE_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.CACHE_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.FILE_SYSTEM_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.MEMORY_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.PROCESS_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.THREAD_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.CONCURRENCY_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.DEADLOCK_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.CIRCUIT_BREAKER_ERROR: cls.INFRASTRUCTURE_ERROR,

			# 网络错误
			ErrorType.NETWORK_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.CONNECTION_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.TIMEOUT_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.SSL_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.DNS_ERROR: cls.INFRASTRUCTURE_ERROR,

			# 外部服务错误
			ErrorType.EXTERNAL_SERVICE_ERROR: cls.EXTERNAL_ERROR,
			ErrorType.API_ERROR: cls.EXTERNAL_ERROR,
			ErrorType.SERVICE_UNAVAILABLE: cls.EXTERNAL_ERROR,
			ErrorType.RATE_LIMIT_ERROR: cls.EXTERNAL_ERROR,

			# 认证授权错误
			ErrorType.AUTHENTICATION_ERROR: cls.SECURITY_ERROR,
			ErrorType.AUTHORIZATION_ERROR: cls.SECURITY_ERROR,
			ErrorType.PERMISSION_ERROR: cls.SECURITY_ERROR,
			ErrorType.TOKEN_ERROR: cls.SECURITY_ERROR,
			ErrorType.SESSION_ERROR: cls.SECURITY_ERROR,
			ErrorType.CREDENTIALS_ERROR: cls.SECURITY_ERROR,

			# 资源错误
			ErrorType.RESOURCE_ERROR: cls.INFRASTRUCTURE_ERROR,
			ErrorType.RESOURCE_EXHAUSTED: cls.INFRASTRUCTURE_ERROR,
			ErrorType.RESOURCE_NOT_FOUND: cls.INFRASTRUCTURE_ERROR,
			ErrorType.RESOURCE_LIMIT_ERROR: cls.INFRASTRUCTURE_ERROR,
		}

		return category_mapping.get(error_type, cls.SERVER_ERROR)