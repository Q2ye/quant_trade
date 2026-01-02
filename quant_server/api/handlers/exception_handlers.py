#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API层异常处理器

负责将业务异常转换为HTTP响应，处理Web-specific异常逻辑。
"""

from typing import Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from quant_server.core.exceptions import (
	BaseException,
	AuthenticationException,
	AuthorizationException,
	ValidationException,
	DataNotFoundException
)
from quant_server.core.exceptions.error_codes import ErrorCode


async def handle_validation_error (request: Request, exc: RequestValidationError) -> JSONResponse:
	"""处理请求验证错误"""
	errors = []
	for error in exc.errors():
		errors.append({
			"field": " -> ".join(str(loc) for loc in error.get("loc", [])),
			"message": error.get("msg"),
			"type": error.get("type")
		})

	return JSONResponse(
		status_code=422,
		content={
			"success": False,
			"error": {
				"code": ErrorCode.VALIDATION_ERROR,
				"message": "请求参数验证失败",
				"type": "validation_error",
				"details": {"errors": errors},
				"timestamp": _get_timestamp()
			}
		}
	)


async def handle_http_exception (request: Request, exc: HTTPException) -> JSONResponse:
	"""处理HTTP异常"""
	return JSONResponse(
		status_code=exc.status_code,
		content={
			"success": False,
			"error": {
				"code": _get_error_code_for_status(exc.status_code),
				"message": exc.detail,
				"type": "http_error",
				"status_code": exc.status_code,
				"timestamp": _get_timestamp()
			}
		}
	)


async def handle_base_exception (request: Request, exc: BaseException) -> JSONResponse:
	"""处理基础异常"""
	# 将业务异常转换为HTTP响应
	return JSONResponse(
		status_code=_get_http_status_for_exception(exc),
		content=exc.to_dict()
	)


def setup_exception_handlers (app):
	"""设置FastAPI异常处理器"""

	# 处理验证错误
	app.add_exception_handler(RequestValidationError, handle_validation_error)

	# 处理HTTP异常
	app.add_exception_handler(HTTPException, handle_http_exception)

	# 处理自定义异常
	app.add_exception_handler(BaseException, handle_base_exception)

	# 处理认证异常
	app.add_exception_handler(AuthenticationException, lambda request, exc: JSONResponse(
		status_code=401,
		content=exc.to_dict()
	))

	# 处理授权异常
	app.add_exception_handler(AuthorizationException, lambda request, exc: JSONResponse(
		status_code=403,
		content=exc.to_dict()
	))

	# 处理数据不存在异常
	app.add_exception_handler(DataNotFoundException, lambda request, exc: JSONResponse(
		status_code=404,
		content=exc.to_dict()
	))


def _get_error_code_for_status (status_code: int) -> str:
	"""根据HTTP状态码获取错误代码"""
	mapping = {
		400: "BAD_REQUEST",
		401: "UNAUTHORIZED",
		403: "FORBIDDEN",
		404: "NOT_FOUND",
		405: "METHOD_NOT_ALLOWED",
		409: "CONFLICT",
		422: "VALIDATION_ERROR",
		429: "RATE_LIMIT_EXCEEDED",
		500: "INTERNAL_ERROR",
		502: "BAD_GATEWAY",
		503: "SERVICE_UNAVAILABLE",
		504: "GATEWAY_TIMEOUT"
	}
	return mapping.get(status_code, "UNKNOWN_ERROR")


def _get_http_status_for_exception (exc: BaseException) -> int:
	"""根据异常类型获取HTTP状态码"""
	if isinstance(exc, AuthenticationException):
		return 401
	elif isinstance(exc, AuthorizationException):
		return 403
	elif isinstance(exc, ValidationException):
		return 400
	elif isinstance(exc, DataNotFoundException):
		return 404
	else:
		return 500


def _get_timestamp () -> str:
	"""获取当前时间戳"""
	from datetime import datetime
	return datetime.now().isoformat()