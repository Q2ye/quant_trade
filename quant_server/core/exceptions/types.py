#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常类型和严重程度定义

定义错误的类型分类和严重程度等级。
"""

from enum import Enum


class ErrorType(str, Enum):
	"""
	错误类型枚举

	定义系统中可能出现的错误类型，便于分类处理。
	"""
	# 验证错误
	VALIDATION_ERROR = "validation_error"

	# 配置错误
	CONFIGURATION_ERROR = "configuration_error"

	# 业务错误
	BUSINESS_ERROR = "business_error"
	STRATEGY_ERROR = "strategy_error"
	ANALYSIS_ERROR = "analysis_error"
	RISK_ERROR = "risk_error"
	TRADE_ERROR = "trade_error"
	ACCOUNT_ERROR = "account_error"

	# 数据错误
	DATA_ERROR = "data_error"
	DATA_NOT_FOUND = "data_not_found"
	DATA_VALIDATION_ERROR = "data_validation_error"
	DATA_SYNC_ERROR = "data_sync_error"

	# 系统错误
	SYSTEM_ERROR = "system_error"
	DATABASE_ERROR = "database_error"
	CACHE_ERROR = "cache_error"
	NETWORK_ERROR = "network_error"
	EXTERNAL_SERVICE_ERROR = "external_service_error"

	# 认证授权错误
	AUTHENTICATION_ERROR = "authentication_error"
	AUTHORIZATION_ERROR = "authorization_error"
	PERMISSION_ERROR = "permission_error"
	RATE_LIMIT_ERROR = "rate_limit_error"

	# 资源错误
	RESOURCE_ERROR = "resource_error"
	RESOURCE_EXHAUSTED = "resource_exhausted"
	RESOURCE_NOT_FOUND = "resource_not_found"

	# 执行错误
	EXECUTION_ERROR = "execution_error"
	TIMEOUT_ERROR = "timeout_error"
	CONCURRENCY_ERROR = "concurrency_error"


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