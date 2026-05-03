# quant_server/utils/api_utils/response_formatter.py
"""
统一响应格式化模块

提供API响应标准化格式，包括：
- 成功响应格式化
- 错误响应格式化
- 响应头标准化
- 响应日志记录

Author: 量化交易系统团队
Version: 1.0.0
"""

import json
import logging
from typing import (
	Any, Dict, List, Optional, Union, Generic, TypeVar,
	get_type_hints, get_args, get_origin
)
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator
from fastapi import Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from core.exceptions.error_codes import ErrorCode
from core.exceptions.base import BaseAPIException

logger = logging.getLogger(__name__)

T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
	"""
	API统一响应模型

	所有API响应都使用此格式，确保一致性：
	{
		"code": "SUCCESS",          // 响应代码
		"message": "操作成功",       // 响应消息
		"data": {...},             // 响应数据（可选）
		"detail": {...},           // 响应详情（可选）
		"timestamp": "2024-01-01T00:00:00Z"  // 响应时间戳
	}
	"""

	code: str = Field(
		...,
		description="响应代码",
		example="SUCCESS"
	)

	message: str = Field(
		...,
		description="响应消息",
		example="操作成功"
	)

	data: Optional[Union[T, Dict[str, Any], List[Any]]] = Field(
		default=None,
		description="响应数据"
	)

	detail: Optional[Dict[str, Any]] = Field(
		default=None,
		description="响应详情"
	)

	timestamp: datetime = Field(
		default_factory=datetime.utcnow,
		description="响应时间戳"
	)

	@validator('code')
	def validate_code (cls, v):
		"""验证响应代码格式"""
		if not v or not isinstance(v, str):
			raise ValueError("响应代码必须是字符串")
		return v.upper()

	class Config:
		json_encoders = {
			datetime: lambda v: v.isoformat() + 'Z' if v.tzinfo is None else v.isoformat()
		}
		json_schema_extra = {
			"example": {
				"code": "SUCCESS",
				"message": "操作成功",
				"data": {"id": 1, "name": "示例数据"},
				"detail": None,
				"timestamp": "2024-01-01T00:00:00Z"
			}
		}

	@classmethod
	def success (
			cls,
			message: str = "操作成功",
			data: Optional[Any] = None,
			detail: Optional[Dict[str, Any]] = None
	) -> 'APIResponse':
		"""
		创建成功响应

		Args:
			message: 响应消息
			data: 响应数据
			detail: 响应详情

		Returns:
			APIResponse: 成功响应实例
		"""
		return cls(
			code=ErrorCode.SUCCESS,
			message=message,
			data=data,
			detail=detail,
			timestamp=datetime.utcnow()
		)

	@classmethod
	def error (
			cls,
			code: str = ErrorCode.INTERNAL_ERROR,
			message: str = "操作失败",
			detail: Optional[Dict[str, Any]] = None,
			data: Optional[Any] = None
	) -> 'APIResponse':
		"""
		创建错误响应

		Args:
			code: 错误代码
			message: 错误消息
			detail: 错误详情
			data: 响应数据

		Returns:
			APIResponse: 错误响应实例
		"""
		return cls(
			code=code,
			message=message,
			data=data,
			detail=detail,
			timestamp=datetime.utcnow()
		)

	@classmethod
	def from_exception (cls, exc: BaseAPIException) -> 'APIResponse':
		"""
		从异常创建响应

		Args:
			exc: API异常实例

		Returns:
			APIResponse: 错误响应实例
		"""
		return cls.error(
			code=exc.code,
			message=exc.message,
			detail=exc.detail,
			data=exc.data
		)

	def to_json_response (
			self,
			status_code: int = 200,
			headers: Optional[Dict[str, str]] = None
	) -> JSONResponse:
		"""
		转换为FastAPI JSONResponse

		Args:
			status_code: HTTP状态码
			headers: 响应头

		Returns:
			JSONResponse: FastAPI JSON响应
		"""
		# 记录响应日志
		self._log_response(status_code)

		# 构建响应头
		response_headers = self._build_headers(headers)

		# 转换为JSON响应
		# 使用 self.json() 以应用 json_encoders 配置，正确序列化 datetime 等类型
		return JSONResponse(
			status_code=status_code,
			content=json.loads(self.json()),
			headers=response_headers
		)

	def _log_response (self, status_code: int):
		"""记录响应日志"""
		log_level = logging.INFO if self.code == ErrorCode.SUCCESS else logging.WARNING

		logger.log(
			log_level,
			f"API响应: code={self.code}, status={status_code}, "
			f"message={self.message}, data_type={type(self.data).__name__}"
		)

	def _build_headers (self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
		"""构建响应头"""
		headers = {
			"Content-Type": "application/json",
			"X-Response-Code": self.code,
			"X-Response-Time": self.timestamp.isoformat() + 'Z',
			"Cache-Control": "no-cache, no-store, must-revalidate",
			"Pragma": "no-cache",
			"Expires": "0",
		}

		if custom_headers:
			headers.update(custom_headers)

		return headers


class ResponseFormatter:
	"""响应格式化器"""

	def __init__ (self, enable_logging: bool = True):
		"""
		初始化响应格式化器

		Args:
			enable_logging: 是否启用日志记录
		"""
		self.enable_logging = enable_logging
		logger.info("响应格式化器初始化完成")

	def success (
			self,
			message: str = "操作成功",
			data: Optional[Any] = None,
			detail: Optional[Dict[str, Any]] = None,
			status_code: int = 200,
			headers: Optional[Dict[str, str]] = None
	) -> JSONResponse:
		"""
		创建成功响应

		Args:
			message: 响应消息
			data: 响应数据
			detail: 响应详情
			status_code: HTTP状态码
			headers: 响应头

		Returns:
			JSONResponse: FastAPI JSON响应
		"""
		response = APIResponse.success(
			message=message,
			data=self._format_data(data),
			detail=detail
		)

		return response.to_json_response(
			status_code=status_code,
			headers=headers
		)

	def error (
			self,
			code: str = ErrorCode.INTERNAL_ERROR,
			message: str = "操作失败",
			detail: Optional[Dict[str, Any]] = None,
			data: Optional[Any] = None,
			status_code: int = 500,
			headers: Optional[Dict[str, str]] = None
	) -> JSONResponse:
		"""
		创建错误响应

		Args:
			code: 错误代码
			message: 错误消息
			detail: 错误详情
			data: 响应数据
			status_code: HTTP状态码
			headers: 响应头

		Returns:
			JSONResponse: FastAPI JSON响应
		"""
		response = APIResponse.error(
			code=code,
			message=message,
			detail=detail,
			data=self._format_data(data)
		)

		return response.to_json_response(
			status_code=status_code,
			headers=headers
		)

	def from_exception (
			self,
			exc: BaseAPIException,
			status_code: int = 500,
			headers: Optional[Dict[str, str]] = None
	) -> JSONResponse:
		"""
		从异常创建响应

		Args:
			exc: API异常实例
			status_code: HTTP状态码
			headers: 响应头

		Returns:
			JSONResponse: FastAPI JSON响应
		"""
		response = APIResponse.from_exception(exc)

		return response.to_json_response(
			status_code=status_code,
			headers=headers
		)

	def paginated (
			self,
			items: List[Any],
			total: int,
			page: int,
			size: int,
			message: str = "查询成功",
			detail: Optional[Dict[str, Any]] = None,
			status_code: int = 200,
			headers: Optional[Dict[str, str]] = None
	) -> JSONResponse:
		"""
		创建分页响应

		Args:
			items: 项目列表
			total: 总记录数
			page: 当前页码
			size: 每页数量
			message: 响应消息
			detail: 响应详情
			status_code: HTTP状态码
			headers: 响应头

		Returns:
			JSONResponse: FastAPI JSON响应
		"""
		from .pagination import PaginationResult

		result = PaginationResult(
			items=items,
			total=total,
			page=page,
			size=size,
			pages=(total + size - 1) // size if total > 0 else 0,
			has_prev=page > 1,
			has_next=page * size < total,
			prev_page=page - 1 if page > 1 else None,
			next_page=page + 1 if page * size < total else None
		)

		data = {
			"items": self._format_data(items),
			"pagination": {
				"page": result.page,
				"size": result.size,
				"total": result.total,
				"pages": result.pages,
				"has_prev": result.has_prev,
				"has_next": result.has_next,
				"prev_page": result.prev_page,
				"next_page": result.next_page
			}
		}

		return self.success(
			message=message,
			data=data,
			detail=detail,
			status_code=status_code,
			headers=headers
		)

	def _format_data (self, data: Any) -> Any:
		"""
		格式化响应数据

		Args:
			data: 原始数据

		Returns:
			Any: 格式化后的数据
		"""
		if data is None:
			return None

		# 处理Pydantic模型
		if isinstance(data, BaseModel):
			return data.dict()

		# 处理枚举
		if isinstance(data, Enum):
			return data.value

		# 处理字典（递归处理值）
		if isinstance(data, dict):
			return {k: self._format_data(v) for k, v in data.items()}

		# 处理列表（递归处理元素）
		if isinstance(data, list):
			return [self._format_data(item) for item in data]

		# 处理元组
		if isinstance(data, tuple):
			return tuple(self._format_data(item) for item in data)

		# 处理集合
		if isinstance(data, set):
			return {self._format_data(item) for item in data}

		# 处理日期时间
		if isinstance(data, datetime):
			return data.isoformat() + 'Z' if data.tzinfo is None else data.isoformat()

		# 其他类型直接返回
		return data

	def wrap_response (self, response: Response) -> Response:
		"""
		包装现有响应

		Args:
			response: 原始响应

		Returns:
			Response: 包装后的响应
		"""
		# 添加标准响应头
		response.headers.update({
			"X-Response-Time": datetime.utcnow().isoformat() + 'Z',
			"Cache-Control": "no-cache, no-store, must-revalidate",
		})

		return response


# 全局响应格式化器实例
_formatter = ResponseFormatter()


# 快捷函数
def success_response (
		message: str = "操作成功",
		data: Optional[Any] = None,
		detail: Optional[Dict[str, Any]] = None,
		status_code: int = 200,
		headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
	"""
	创建成功响应（快捷函数）

	Args:
		message: 响应消息
		data: 响应数据
		detail: 响应详情
		status_code: HTTP状态码
		headers: 响应头

	Returns:
		JSONResponse: FastAPI JSON响应
	"""
	return _formatter.success(
		message=message,
		data=data,
		detail=detail,
		status_code=status_code,
		headers=headers
	)


def error_response (
		code: str = ErrorCode.INTERNAL_ERROR,
		message: str = "操作失败",
		detail: Optional[Dict[str, Any]] = None,
		data: Optional[Any] = None,
		status_code: int = 500,
		headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
	"""
	创建错误响应（快捷函数）

	Args:
		code: 错误代码
		message: 错误消息
		detail: 错误详情
		data: 响应数据
		status_code: HTTP状态码
		headers: 响应头

	Returns:
		JSONResponse: FastAPI JSON响应
	"""
	return _formatter.error(
		code=code,
		message=message,
		detail=detail,
		data=data,
		status_code=status_code,
		headers=headers
	)


def paginated_response (
		items: List[Any],
		total: int,
		page: int,
		size: int,
		message: str = "查询成功",
		detail: Optional[Dict[str, Any]] = None,
		status_code: int = 200,
		headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
	"""
	创建分页响应（快捷函数）

	Args:
		items: 项目列表
		total: 总记录数
		page: 当前页码
		size: 每页数量
		message: 响应消息
		detail: 响应详情
		status_code: HTTP状态码
		headers: 响应头

	Returns:
		JSONResponse: FastAPI JSON响应
	"""
	return _formatter.paginated(
		items=items,
		total=total,
		page=page,
		size=size,
		message=message,
		detail=detail,
		status_code=status_code,
		headers=headers
	)


class ResponseMiddleware:
	"""响应中间件（用于包装所有响应）"""

	async def __call__ (self, request, call_next):
		"""
		中间件处理

		Args:
			request: FastAPI请求对象
			call_next: 下一个中间件或端点

		Returns:
			Response: 处理后的响应
		"""
		try:
			# 调用下一个中间件或端点
			response = await call_next(request)

			# 包装响应
			if isinstance(response, JSONResponse):
				# 对于JSON响应，确保使用标准格式
				try:
					content = json.loads(response.body.decode())

					# 如果响应已经是标准格式，不需要处理
					if 'code' in content and 'message' in content:
						return response

					# 否则包装为标准格式
					wrapped_response = success_response(
						message="操作成功",
						data=content,
						status_code=response.status_code,
						headers=dict(response.headers)
					)

					return wrapped_response

				except (json.JSONDecodeError, UnicodeDecodeError):
					# 如果不是JSON响应，直接返回
					return _formatter.wrap_response(response)
			else:
				# 非JSON响应，只添加标准头
				return _formatter.wrap_response(response)

		except BaseAPIException as e:
			# 处理已知的API异常
			logger.warning(f"API异常: {e.code} - {e.message}")
			return _formatter.from_exception(e, status_code=e.status_code)

		except Exception as e:
			# 处理未知异常
			logger.error(f"未知异常: {str(e)}", exc_info=True)
			return error_response(
				code=ErrorCode.INTERNAL_ERROR,
				message="服务器内部错误",
				detail={"error": str(e)} if logger.isEnabledFor(logging.DEBUG) else None,
				status_code=500
			)