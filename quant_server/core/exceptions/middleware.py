#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常中间件

提供FastAPI全局异常处理中间件，按照混合架构设计位于核心基础设施层。
"""

import logging
import traceback
from typing import Callable, Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .base import BaseAPIException, QuantBaseException
from .error_codes import ErrorCode
from .handlers import handle_exception, ExceptionHandlerFactory

logger = logging.getLogger(__name__)


class ExceptionMiddleware(BaseHTTPMiddleware):
	"""异常处理中间件"""

	def __init__ (
			self,
			app,
			default_status_code: int = 500,
			default_error_code: str = ErrorCode.INTERNAL_ERROR,
			include_traceback: bool = False,
			log_errors: bool = True,
			notification_enabled: bool = True
	):
		"""
		初始化异常中间件

		Args:
			app: FastAPI应用
			default_status_code: 默认HTTP状态码
			default_error_code: 默认错误码
			include_traceback: 是否包含堆栈跟踪
			log_errors: 是否记录错误日志
			notification_enabled: 是否启用通知
		"""
		super().__init__(app)
		self.default_status_code = default_status_code
		self.default_error_code = default_error_code
		self.include_traceback = include_traceback
		self.log_errors = log_errors
		self.notification_enabled = notification_enabled

	async def dispatch (self, request: Request, call_next: Callable):
		"""
		处理请求

		Args:
			request: HTTP请求
			call_next: 下一个中间件或路由处理函数

		Returns:
			HTTP响应
		"""
		try:
			response = await call_next(request)
			return response

		except HTTPException as http_exc:
			# FastAPI的HTTPException
			return self._handle_http_exception(http_exc, request)

		except BaseAPIException as api_exc:
			# 自定义API异常
			return self._handle_api_exception(api_exc, request)

		except QuantBaseException as base_exc:
			# 自定义基础异常
			return self._handle_base_exception(base_exc, request)

		except Exception as exc:
			# 其他未捕获的异常
			return self._handle_unexpected_exception(exc, request)

	def _handle_http_exception (self, exc: HTTPException, request: Request) -> JSONResponse:
		"""处理HTTP异常"""
		error_response = {
			"success": False,
			"code": self._get_error_code_from_status(exc.status_code),
			"message": exc.detail,
			"timestamp": self._get_timestamp()
		}

		if self.include_traceback:
			error_response["traceback"] = traceback.format_exc()

		# 记录日志
		if self.log_errors:
			logger.error(
				f"HTTPException: {exc.status_code} - {exc.detail}",
				extra={
					"request_path": request.url.path,
					"request_method": request.method,
					"status_code": exc.status_code,
					"error_code": error_response["code"]
				}
			)

		return JSONResponse(
			status_code=exc.status_code,
			content=error_response,
			headers=exc.headers
		)

	def _handle_api_exception (self, exc: BaseAPIException, request: Request) -> JSONResponse:
		"""处理API异常"""
		error_response = exc.to_response()

		if self.include_traceback:
			error_response["traceback"] = traceback.format_exc()

		# 记录日志
		if self.log_errors:
			logger.error(
				f"APIException: {exc.status_code} - {exc.message}",
				extra={
					"request_path": request.url.path,
					"request_method": request.method,
					"status_code": exc.status_code,
					"error_code": exc.code,
					"details": exc.detail
				}
			)

		# 发送通知
		if self.notification_enabled and exc.status_code >= 500:
			self._send_notification(exc, request)

		return JSONResponse(
			status_code=exc.status_code,
			content=error_response,
			headers=exc.headers
		)

	def _handle_base_exception (self, exc: QuantBaseException, request: Request) -> JSONResponse:
		"""处理基础异常"""
		# 转换为API异常
		api_exc = exc.to_api_exception()

		# 使用异常处理器
		context = {
			"request_path": request.url.path,
			"request_method": request.method,
			"client_ip": request.client.host if request.client else None
		}

		handler = ExceptionHandlerFactory.create_default_handler()
		handle_exception(exc, context, handler)

		return self._handle_api_exception(api_exc, request)

	def _handle_unexpected_exception (self, exc: Exception, request: Request) -> JSONResponse:
		"""处理未预期的异常"""
		error_response = {
			"success": False,
			"code": self.default_error_code,
			"message": "内部服务器错误",
			"timestamp": self._get_timestamp()
		}

		if self.include_traceback:
			error_response["traceback"] = traceback.format_exc()

		# 记录错误日志
		logger.error(
			f"Unexpected exception: {str(exc)}",
			extra={
				"request_path": request.url.path,
				"request_method": request.method,
				"exception_type": exc.__class__.__name__,
				"exception_message": str(exc),
				"traceback": traceback.format_exc()
			},
			exc_info=True
		)

		# 发送通知
		if self.notification_enabled:
			self._send_notification(exc, request)

		return JSONResponse(
			status_code=self.default_status_code,
			content=error_response
		)

	def _get_error_code_from_status (self, status_code: int) -> str:
		"""根据HTTP状态码获取错误码"""
		status_to_code = {
			400: ErrorCode.VALIDATION_ERROR,
			401: ErrorCode.AUTHENTICATION_ERROR,
			403: ErrorCode.AUTHORIZATION_ERROR,
			404: ErrorCode.NOT_FOUND,
			409: ErrorCode.CONFLICT,
			422: ErrorCode.VALIDATION_ERROR,
			429: ErrorCode.RATE_LIMIT_ERROR,
			500: ErrorCode.INTERNAL_ERROR,
			503: ErrorCode.EXTERNAL_SERVICE_ERROR
		}

		return status_to_code.get(status_code, self.default_error_code)

	@staticmethod
	def _get_timestamp () -> str:
		"""获取当前时间戳"""
		from datetime import datetime
		return datetime.now().isoformat()

	@staticmethod
	def _send_notification (exc: Exception, request: Request):
		"""发送异常通知"""
		try:
			from .handlers import NotificationExceptionHandler
			from .types import ErrorSeverity

			# 创建通知处理器
			notification_handler = NotificationExceptionHandler(min_severity=ErrorSeverity.ERROR)

			# 构建上下文
			context = {
				"request_path": request.url.path,
				"request_method": request.method,
				"client_ip": request.client.host if request.client else None,
				"user_agent": request.headers.get("user-agent", ""),
				"referer": request.headers.get("referer", "")
			}

			# 发送通知
			notification_handler.handle(exc, context)

		except Exception as e:
			logger.error(f"Failed to send notification: {str(e)}")


def setup_exception_middleware (
		app: FastAPI,
		**kwargs
) -> ExceptionMiddleware:
	"""
	设置异常中间件

	Args:
		app: FastAPI应用
		**kwargs: 传递给ExceptionMiddleware的参数

	Returns:
		配置好的异常中间件
	"""
	middleware = ExceptionMiddleware(app, **kwargs)
	app.add_middleware(ExceptionMiddleware)
	return middleware


def create_error_response (
		_status_code: int,
		code: str,
		message: str,
		detail: Optional[Dict[str, Any]] = None,
		include_traceback: bool = False
) -> Dict[str, Any]:
	"""
	创建错误响应字典

	Args:
		_status_code: HTTP状态码
		code: 错误码
		message: 错误消息
		detail: 错误详情
		include_traceback: 是否包含堆栈跟踪

	Returns:
		错误响应字典
	"""
	from datetime import datetime

	response: Dict[str, Any] = {
		"success": False,
		"code": code,
		"message": message,
		"timestamp": datetime.now().isoformat()
	}

	if detail:
		response["detail"] = detail

	if include_traceback:
		response["traceback"] = traceback.format_exc()

	return response