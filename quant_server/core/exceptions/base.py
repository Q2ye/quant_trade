#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常基类定义

定义所有异常的基类，提供统一的接口和错误处理机制。
按照混合架构设计，位于核心基础设施层。
"""

import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union

from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class BaseAPIException(Exception):
	"""
	API异常基类

	所有API相关的异常都继承自此基类，用于HTTP响应。
	"""

	def __init__ (
			self,
			status_code: int = 500,
			code: str = ErrorCode.INTERNAL_ERROR,
			message: str = "内部服务器错误",
			detail: Optional[Dict[str, Any]] = None,
			headers: Optional[Dict[str, str]] = None
	):
		"""
		初始化API异常

		Args:
			status_code: HTTP状态码
			code: 业务错误码
			message: 错误消息
			detail: 错误详情
			headers: HTTP头部
		"""
		self.status_code = status_code
		self.code = code
		self.message = message
		self.detail: Dict[str, Any] = detail or {}
		self.headers = headers or {}

		super().__init__(self.message)

	def to_response (self) -> Dict[str, Any]:
		"""
		转换为响应字典

		Returns:
			响应字典
		"""
		response: Dict[str, Any] = {
			"success": False,
			"code": self.code,
			"message": self.message,
			"timestamp": datetime.now().isoformat()
		}

		if self.detail:
			response["detail"] = self.detail

		return response


class QuantBaseException(Exception):
	"""
	异常基类

	所有自定义异常都继承自此基类，提供统一的错误处理接口。
	"""

	def __init__ (
			self,
			message: str,
			error_code: Union[str, ErrorCode] = ErrorCode.INTERNAL_ERROR,
			error_type: ErrorType = ErrorType.SYSTEM_ERROR,
			severity: ErrorSeverity = ErrorSeverity.ERROR,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化异常

		Args:
			message: 错误消息（人类可读）
			error_code: 错误代码
			error_type: 错误类型
			severity: 错误严重程度
			details: 额外的错误详情
			cause: 导致此异常的原始异常
		"""
		self.message = message
		self.error_code = error_code.value if isinstance(error_code, ErrorCode) else error_code
		self.error_type = error_type
		self.severity = severity
		self.details = details or {}
		self.cause = cause
		self.timestamp = datetime.now()

		# 生成堆栈跟踪
		try:
			self.stack_trace = traceback.format_exc()
		except Exception:
			self.stack_trace = ""

		# 构建完整错误消息
		if isinstance(error_code, ErrorCode):
			error_msg = f"[{error_code.name}] {message}"
		else:
			error_msg = f"[{error_code}] {message}"

		super().__init__(error_msg)

	def to_dict (self) -> Dict[str, Any]:
		"""
		将异常转换为字典格式

		Returns:
			包含异常信息的字典
		"""
		return {
			"success": False,
			"error": {
				"code": self.error_code,
				"message": self.message,
				"type": self.error_type.value,
				"severity": self.severity.value,
				"details": self.details,
				"timestamp": self.timestamp.isoformat(),
				"stack_trace": self.stack_trace if self.severity == ErrorSeverity.DEBUG else None
			}
		}

	def to_json (self) -> str:
		"""
		将异常转换为JSON格式

		Returns:
			JSON格式的异常信息
		"""
		import json
		return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

	def to_api_exception (self) -> BaseAPIException:
		"""
		转换为API异常

		Returns:
			BaseAPIException: API异常实例
		"""
		# 根据错误码映射HTTP状态码
		status_map = {
			"4000": 400,  # BAD_REQUEST
			"1001": 400,  # VALIDATION_ERROR
			"5000": 401,  # AUTHENTICATION_ERROR
			"5100": 403,  # AUTHORIZATION_ERROR
			"1009": 429,  # RATE_LIMIT_ERROR
			"1006": 404,  # NOT_FOUND
			"1007": 409,  # CONFLICT
		}

		status_code = status_map.get(self.error_code, 500)

		return BaseAPIException(
			status_code=status_code,
			code=self.error_code,
			message=self.message,
			detail=self.details
		)

	def __str__ (self) -> str:
		"""字符串表示"""
		return f"{self.__class__.__name__}: {self.message} (Code: {self.error_code})"

	def __repr__ (self) -> str:
		"""对象表示"""
		return f"{self.__class__.__name__}(message={self.message!r}, code={self.error_code!r})"


class ValidationException(QuantBaseException):
	"""验证异常"""

	def __init__ (
			self,
			message: str,
			field: Optional[str] = None,
			value: Optional[Any] = None,
			validation_errors: Optional[list] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化验证异常

		Args:
			message: 验证错误消息
			field: 验证失败的字段
			value: 字段值
			validation_errors: 验证错误列表
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if field:
			details["field"] = field
		if value:
			details["value"] = value
		if validation_errors:
			details["validation_errors"] = validation_errors

		super().__init__(
			message=message,
			error_code=ErrorCode.VALIDATION_ERROR,
			error_type=ErrorType.VALIDATION_ERROR,
			severity=ErrorSeverity.WARNING,
			details=details,
			cause=cause
		)


class ConfigurationException(QuantBaseException):
	"""配置异常"""

	def __init__ (
			self,
			message: str,
			config_key: Optional[str] = None,
			config_value: Optional[Any] = None,
			config_section: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化配置异常

		Args:
			message: 配置错误消息
			config_key: 配置键
			config_value: 配置值
			config_section: 配置部分
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if config_key:
			details["config_key"] = config_key
		if config_value:
			details["config_value"] = config_value
		if config_section:
			details["config_section"] = config_section

		super().__init__(
			message=message,
			error_code=ErrorCode.CONFIGURATION_ERROR,
			error_type=ErrorType.CONFIGURATION_ERROR,
			severity=ErrorSeverity.ERROR,
			details=details,
			cause=cause
		)


class ServiceException(QuantBaseException):
	"""服务异常"""

	def __init__ (
			self,
			message: str,
			service_name: Optional[str] = None,
			operation: Optional[str] = None,
			service_type: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化服务异常

		Args:
			message: 服务错误消息
			service_name: 服务名称
			operation: 操作名称
			service_type: 服务类型
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if service_name:
			details["service_name"] = service_name
		if operation:
			details["operation"] = operation
		if service_type:
			details["service_type"] = service_type

		super().__init__(
			message=message,
			error_code=ErrorCode.SERVICE_ERROR,
			error_type=ErrorType.EXTERNAL_SERVICE_ERROR,
			severity=ErrorSeverity.ERROR,
			details=details,
			cause=cause
		)