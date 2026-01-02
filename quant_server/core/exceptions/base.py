#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常基类定义

定义所有异常的基类，提供统一的接口和错误处理机制。
"""

from typing import Any, Dict, Optional, Union
from enum import Enum
import traceback

from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class BaseException(Exception):
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

		# 生成堆栈跟踪
		self.stack_trace = traceback.format_exc()

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
				"timestamp": self._get_timestamp()
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

	def _get_timestamp (self) -> str:
		"""获取当前时间戳"""
		from datetime import datetime
		return datetime.now().isoformat()

	def __str__ (self) -> str:
		"""字符串表示"""
		return f"{self.__class__.__name__}: {self.message} (Code: {self.error_code})"

	def __repr__ (self) -> str:
		"""对象表示"""
		return f"{self.__class__.__name__}(message={self.message!r}, code={self.error_code!r})"


class ValidationException(BaseException):
	"""验证异常"""

	def __init__ (
			self,
			message: str,
			field: Optional[str] = None,
			value: Optional[Any] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化验证异常

		Args:
			message: 验证错误消息
			field: 验证失败的字段
			value: 字段值
			details: 额外详情
			cause: 原始异常
		"""
		if field:
			details = details or {}
			details["field"] = field
			details["value"] = value

		super().__init__(
			message=message,
			error_code=ErrorCode.VALIDATION_ERROR,
			error_type=ErrorType.VALIDATION_ERROR,
			severity=ErrorSeverity.WARNING,
			details=details,
			cause=cause
		)


class ConfigurationException(BaseException):
	"""配置异常"""

	def __init__ (
			self,
			message: str,
			config_key: Optional[str] = None,
			config_value: Optional[Any] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化配置异常

		Args:
			message: 配置错误消息
			config_key: 配置键
			config_value: 配置值
			details: 额外详情
			cause: 原始异常
		"""
		if config_key:
			details = details or {}
			details["config_key"] = config_key
			details["config_value"] = config_value

		super().__init__(
			message=message,
			error_code=ErrorCode.CONFIGURATION_ERROR,
			error_type=ErrorType.CONFIGURATION_ERROR,
			severity=ErrorSeverity.ERROR,
			details=details,
			cause=cause
		)


class ServiceException(BaseException):
	"""服务异常"""

	def __init__ (
			self,
			message: str,
			service_name: Optional[str] = None,
			operation: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化服务异常

		Args:
			message: 服务错误消息
			service_name: 服务名称
			operation: 操作名称
			details: 额外详情
			cause: 原始异常
		"""
		if service_name or operation:
			details = details or {}
			if service_name:
				details["service_name"] = service_name
			if operation:
				details["operation"] = operation

		super().__init__(
			message=message,
			error_code=ErrorCode.SERVICE_ERROR,
			error_type=ErrorType.SERVICE_ERROR,
			severity=ErrorSeverity.ERROR,
			details=details,
			cause=cause
		)