#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心异常处理中间件

业务无关的异常处理逻辑，提供：
1. 异常到HTTP响应的映射
2. 结构化错误响应
3. 异常日志记录
"""

import logging
import traceback
from typing import Dict, Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..exceptions import (
	QuantBaseException,
	BusinessException,
	AuthenticationException,
	AuthorizationException,
	ValidationException,
	DataNotFoundException,
	PermissionException,
)
from ..exceptions.base import ServiceException
from ..exceptions.error_codes import ErrorCode
from ..exceptions.types import ErrorSeverity


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
	"""异常处理中间件"""

	def __init__ (self, app, debug: bool = False):
		super().__init__(app)
		self.debug = debug
		self.logger = logging.getLogger(__name__)

	async def dispatch (self, request: Request, call_next):
		try:
			response = await call_next(request)
			return response
		except Exception as exc:
			return await self.handle_exception(request, exc)

	async def handle_exception (self, request: Request, exc: Exception) -> JSONResponse:
		"""处理异常并返回标准化的错误响应"""

		# 处理HTTP异常
		if isinstance(exc, HTTPException):
			return self._handle_http_exception(request, exc)

		# 处理自定义业务异常
		elif isinstance(exc, QuantBaseException):
			return await self._handle_base_exception(request, exc)

		# 处理其他异常
		else:
			return await self._handle_generic_exception(request, exc)

	def _handle_http_exception (self, request: Request, exc: HTTPException) -> JSONResponse:
		"""处理FastAPI HTTP异常"""
		status_code = exc.status_code

		error_response = {
			"success": False,
			"error": {
				"code": self._get_http_error_code(status_code),
				"message": exc.detail,
				"type": "http_error",
				"status_code": status_code,
				"timestamp": self._get_timestamp()
			}
		}

		self.logger.warning(
			f"HTTP Exception: {status_code} - {exc.detail}",
			extra={
				"path": request.url.path,
				"method": request.method,
				"status_code": status_code
			}
		)

		return JSONResponse(
			status_code=status_code,
			content=error_response
		)

	async def _handle_base_exception (self, request: Request, exc: QuantBaseException) -> JSONResponse:
		"""处理自定义业务异常"""
		# 记录异常日志
		self._log_exception(exc, request)

		# 根据异常类型确定HTTP状态码
		status_code = self._get_status_code_for_exception(exc)

		# 构建错误响应
		error_response = exc.to_dict()

		# 生产环境下隐藏敏感信息
		if not self.debug:
			error_response["error"] = self._sanitize_error_response(error_response["error"])

		return JSONResponse(
			status_code=status_code,
			content=error_response
		)

	async def _handle_generic_exception (self, request: Request, exc: Exception) -> JSONResponse:
		"""处理未知异常"""
		# 记录详细错误日志
		self.logger.error(
			f"Unhandled exception: {str(exc)}",
			exc_info=True,
			extra={
				"path": request.url.path,
				"method": request.method,
				"exception_type": exc.__class__.__name__
			}
		)

		if self.debug:
			# 调试模式下返回详细错误
			error_response = {
				"success": False,
				"error": {
					"code": ErrorCode.INTERNAL_ERROR,
					"message": f"Unhandled exception: {str(exc)}",
					"type": "unhandled_exception",
					"severity": ErrorSeverity.CRITICAL.value,
					"stack_trace": traceback.format_exc(),
					"timestamp": self._get_timestamp()
				}
			}
		else:
			# 生产环境下返回通用错误
			error_response = {
				"success": False,
				"error": {
					"code": ErrorCode.INTERNAL_ERROR,
					"message": "Internal server error",
					"type": "internal_error",
					"severity": ErrorSeverity.CRITICAL.value,
					"timestamp": self._get_timestamp()
				}
			}

		return JSONResponse(
			status_code=500,
			content=error_response
		)

	def _log_exception (self, exc: QuantBaseException, request: Request):
		"""记录异常日志"""
		log_level = self._get_log_level_for_severity(exc.severity)

		log_data = {
			"path": request.url.path,
			"method": request.method,
			"error_code": exc.error_code,
			"error_type": exc.error_type.value,
			"severity": exc.severity.value,
			"details": exc.details
		}

		if hasattr(request.state, 'user_id'):
			log_data["user_id"] = request.state.user_id

		self.logger.log(
			log_level,
			f"{exc.__class__.__name__}: {exc.message}",
			extra=log_data
		)

	@staticmethod
	def _get_status_code_for_exception (exc: QuantBaseException) -> int:
		"""根据异常类型获取HTTP状态码"""
		status_mapping = {
			AuthenticationException: 401,
			AuthorizationException: 403,
			PermissionException: 403,
			ValidationException: 400,
			DataNotFoundException: 404,
			BusinessException: 422,
			ServiceException: 503,
			QuantBaseException: 500
		}

		for exc_type, status_code in status_mapping.items():
			if isinstance(exc, exc_type):
				return status_code

		return 500

	@staticmethod
	def _get_log_level_for_severity (severity: ErrorSeverity) -> int:
		"""根据严重程度获取日志级别"""
		mapping = {
			ErrorSeverity.DEBUG: logging.DEBUG,
			ErrorSeverity.INFO: logging.INFO,
			ErrorSeverity.WARNING: logging.WARNING,
			ErrorSeverity.ERROR: logging.ERROR,
			ErrorSeverity.CRITICAL: logging.CRITICAL
		}
		return mapping.get(severity, logging.ERROR)

	@staticmethod
	def _get_http_error_code (status_code: int) -> str:
		"""根据HTTP状态码获取错误代码"""
		mapping = {
			400: "BAD_REQUEST",
			401: "UNAUTHORIZED",
			403: "FORBIDDEN",
			404: "NOT_FOUND",
			405: "METHOD_NOT_ALLOWED",
			409: "CONFLICT",
			422: "UNPROCESSABLE_ENTITY",
			429: "TOO_MANY_REQUESTS",
			500: "INTERNAL_ERROR",
			503: "SERVICE_UNAVAILABLE"
		}
		return mapping.get(status_code, "UNKNOWN_ERROR")

	def _sanitize_error_response (self, error_data: Dict[str, Any]) -> Dict[str, Any]:
		"""净化错误响应（生产环境）"""
		sanitized = error_data.copy()

		# 移除敏感信息
		if "stack_trace" in sanitized:
			del sanitized["stack_trace"]

		if "details" in sanitized:
			# 保留非敏感详情
			safe_details = {}
			for key, value in sanitized["details"].items():
				if not self._is_sensitive_field(key):
					safe_details[key] = value
			sanitized["details"] = safe_details

		return sanitized

	@staticmethod
	def _is_sensitive_field (field_name: str) -> bool:
		"""检查字段是否敏感"""
		sensitive_fields = {
			"password", "token", "secret", "key", "credential",
			"private_key", "api_key", "access_token", "refresh_token"
		}
		return any(sensitive in field_name.lower() for sensitive in sensitive_fields)

	@staticmethod
	def _get_timestamp () -> str:
		"""获取当前时间戳"""
		from datetime import datetime
		return datetime.now().isoformat()


__all__ = [
	'ExceptionHandlingMiddleware',
	'QuantBaseException',
	'BusinessException',
	'AuthenticationException',
	'AuthorizationException',
	'ValidationException',
	'DataNotFoundException',
	'PermissionException',
	'ServiceException'
]