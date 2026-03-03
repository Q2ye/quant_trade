# quant_server/utils/api_utils/request_validator.py
"""
请求验证器模块

提供统一的请求参数验证功能，包括：
- 请求参数验证
- 请求体验证
- 查询参数验证
- 路径参数验证
- 自定义验证规则

Author: 量化交易系统团队
Version: 1.0.0
"""

import re
import logging
from typing import (
	Any, Dict, List, Optional, Union, Callable, Type, TypeVar,
	get_type_hints, get_origin, get_args, Tuple
)
from datetime import datetime, date
from decimal import Decimal
from functools import wraps

from pydantic import BaseModel, ValidationError, create_model
from pydantic.fields import FieldInfo
from fastapi import Request, HTTPException, Query, Path, Body, Depends
from fastapi.params import Param

from quant_server.core.exceptions.validation_exceptions import ValidationError as CustomValidationError
from quant_server.core.exceptions.error_codes import ErrorCode
from quant_server.utils.api_utils.response_formatter import APIResponse

logger = logging.getLogger(__name__)

T = TypeVar('T')
ModelType = TypeVar('ModelType', bound=BaseModel)


class RequestValidator:
	"""请求验证器"""

	def __init__ (self):
		"""初始化请求验证器"""
		self._validators: Dict[str, Callable] = {}
		self._register_builtin_validators()
		logger.info("请求验证器初始化完成")

	def _register_builtin_validators (self):
		"""注册内置验证器"""
		self.register_validator("email", self._validate_email)
		self.register_validator("phone", self._validate_phone)
		self.register_validator("password", self._validate_password)
		self.register_validator("url", self._validate_url)
		self.register_validator("ip_address", self._validate_ip_address)
		self.register_validator("date_string", self._validate_date_string)
		self.register_validator("datetime_string", self._validate_datetime_string)
		self.register_validator("numeric_string", self._validate_numeric_string)
		self.register_validator("alphanumeric", self._validate_alphanumeric)
		self.register_validator("stock_code", self._validate_stock_code)
		self.register_validator("trade_symbol", self._validate_trade_symbol)

	def register_validator (self, name: str, validator: Callable):
		"""
		注册自定义验证器

		Args:
			name: 验证器名称
			validator: 验证器函数
		"""
		self._validators[name] = validator
		logger.debug(f"注册验证器: {name}")

	def validate_request (
			self,
			model: Type[ModelType],
			data: Dict[str, Any],
			context: Optional[Dict[str, Any]] = None
	) -> ModelType:
		"""
		验证请求数据

		Args:
			model: Pydantic模型类
			data: 请求数据
			context: 验证上下文

		Returns:
			ModelType: 验证后的模型实例

		Raises:
			ValidationError: 验证失败
		"""
		try:
			# 执行前置验证
			data = self._pre_validate(data, context)

			# 使用Pydantic验证
			instance = model(**data)

			# 执行后置验证
			self._post_validate(instance, context)

			logger.debug(f"请求验证成功: {model.__name__}")
			return instance

		except ValidationError as e:
			logger.warning(f"请求验证失败: {e.errors()}")
			raise CustomValidationError(
				code=ErrorCode.VALIDATION_ERROR,
				message="请求参数验证失败",
				detail=self._format_validation_errors(e.errors())
			)

	def validate_query_params (
			self,
			model: Type[ModelType],
			request: Request,
			context: Optional[Dict[str, Any]] = None
	) -> ModelType:
		"""
		验证查询参数

		Args:
			model: 查询参数模型
			request: FastAPI请求对象
			context: 验证上下文

		Returns:
			ModelType: 验证后的模型实例
		"""
		query_params = dict(request.query_params)
		return self.validate_request(model, query_params, context)

	def validate_path_params (
			self,
			model: Type[ModelType],
			request: Request,
			context: Optional[Dict[str, Any]] = None
	) -> ModelType:
		"""
		验证路径参数

		Args:
			model: 路径参数模型
			request: FastAPI请求对象
			context: 验证上下文

		Returns:
			ModelType: 验证后的模型实例
		"""
		path_params = dict(request.path_params)
		return self.validate_request(model, path_params, context)

	def validate_body (
			self,
			model: Type[ModelType],
			request: Request,
			context: Optional[Dict[str, Any]] = None
	) -> ModelType:
		"""
		验证请求体

		Args:
			model: 请求体模型
			request: FastAPI请求对象
			context: 验证上下文

		Returns:
			ModelType: 验证后的模型实例
		"""
		body_data = request.state.body_data if hasattr(request.state, 'body_data') else {}
		return self.validate_request(model, body_data, context)

	def _pre_validate (self, data: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
		"""
		前置验证

		Args:
			data: 原始数据
			context: 验证上下文

		Returns:
			Dict[str, Any]: 处理后的数据
		"""
		# 这里可以添加一些通用的预处理逻辑
		# 例如：去除空白字符、转换数据类型等

		processed_data = {}
		for key, value in data.items():
			if isinstance(value, str):
				# 去除字符串两端的空白字符
				value = value.strip()

			processed_data[key] = value

		return processed_data

	def _post_validate (self, instance: ModelType, context: Optional[Dict[str, Any]]):
		"""
		后置验证

		Args:
			instance: 验证后的模型实例
			context: 验证上下文
		"""
		# 这里可以添加一些跨字段的验证逻辑
		# 例如：验证开始时间小于结束时间

		# 检查模型是否定义了自定义验证方法
		if hasattr(instance, 'validate_cross_field'):
			instance.validate_cross_field()

	def _format_validation_errors (self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		格式化验证错误

		Args:
			errors: Pydantic验证错误列表

		Returns:
			List[Dict[str, Any]]: 格式化后的错误列表
		"""
		formatted_errors = []

		for error in errors:
			field = ".".join(str(loc) for loc in error.get('loc', ()))
			if not field:
				field = "root"

			formatted_errors.append({
				"field": field,
				"type": error.get('type', 'validation_error'),
				"message": error.get('msg', '验证失败'),
				"input": error.get('input')
			})

		return formatted_errors

	# 内置验证器实现
	def _validate_email (self, value: str) -> str:
		"""验证邮箱地址"""
		pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
		if not re.match(pattern, value):
			raise ValueError("无效的邮箱地址")
		return value

	def _validate_phone (self, value: str) -> str:
		"""验证手机号码"""
		pattern = r'^1[3-9]\d{9}$'
		if not re.match(pattern, value):
			raise ValueError("无效的手机号码")
		return value

	def _validate_password (self, value: str) -> str:
		"""验证密码强度"""
		if len(value) < 8:
			raise ValueError("密码长度至少8位")

		# 检查是否包含数字
		if not re.search(r'\d', value):
			raise ValueError("密码必须包含数字")

		# 检查是否包含字母
		if not re.search(r'[a-zA-Z]', value):
			raise ValueError("密码必须包含字母")

		return value

	def _validate_url (self, value: str) -> str:
		"""验证URL"""
		pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
		if not re.match(pattern, value):
			raise ValueError("无效的URL")
		return value

	def _validate_ip_address (self, value: str) -> str:
		"""验证IP地址"""
		pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
		if not re.match(pattern, value):
			raise ValueError("无效的IP地址")

		# 验证每个数字在0-255之间
		parts = value.split('.')
		for part in parts:
			if not 0 <= int(part) <= 255:
				raise ValueError("无效的IP地址范围")

		return value

	def _validate_date_string (self, value: str) -> str:
		"""验证日期字符串（YYYY-MM-DD）"""
		try:
			datetime.strptime(value, '%Y-%m-%d').date()
			return value
		except ValueError:
			raise ValueError("无效的日期格式，应为YYYY-MM-DD")

	def _validate_datetime_string (self, value: str) -> str:
		"""验证日期时间字符串（YYYY-MM-DD HH:MM:SS）"""
		try:
			datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
			return value
		except ValueError:
			try:
				# 也支持ISO格式
				datetime.fromisoformat(value.replace('Z', '+00:00'))
				return value
			except ValueError:
				raise ValueError("无效的日期时间格式")

	def _validate_numeric_string (self, value: str) -> str:
		"""验证数字字符串"""
		if not value.replace('.', '', 1).isdigit():
			raise ValueError("必须是数字字符串")
		return value

	def _validate_alphanumeric (self, value: str) -> str:
		"""验证字母数字字符串"""
		if not value.isalnum():
			raise ValueError("必须是字母数字字符串")
		return value

	def _validate_stock_code (self, value: str) -> str:
		"""验证股票代码"""
		# 简单的股票代码验证，可根据实际情况扩展
		pattern = r'^[0-9]{6}$'
		if not re.match(pattern, value):
			raise ValueError("无效的股票代码")
		return value

	def _validate_trade_symbol (self, value: str) -> str:
		"""验证交易品种"""
		# 简单的交易品种验证，可根据实际情况扩展
		pattern = r'^[A-Z]{1,10}$'
		if not re.match(pattern, value):
			raise ValueError("无效的交易品种")
		return value

	def create_dynamic_model (
			self,
			name: str,
			fields: Dict[str, Tuple[Type, FieldInfo]],
			base_model: Optional[Type[BaseModel]] = None
	) -> Type[BaseModel]:
		"""
		创建动态模型

		Args:
			name: 模型名称
			fields: 字段定义字典
			base_model: 基础模型类

		Returns:
			Type[BaseModel]: 动态创建的模型类
		"""
		try:
			model = create_model(name, __base__=base_model, **fields)
			logger.debug(f"创建动态模型: {name}")
			return model
		except Exception as e:
			logger.error(f"创建动态模型失败: {str(e)}")
			raise


# 全局验证器实例
_validator = RequestValidator()


def validate_request (model: Type[ModelType]):
	"""
	请求验证装饰器

	Args:
		model: 验证模型

	Returns:
		装饰器函数
	"""

	def decorator (func: Callable) -> Callable:
		@wraps(func)
		async def wrapper (*args, **kwargs):
			# 从参数中提取请求对象和数据
			request = None
			data = {}

			for arg in args:
				if isinstance(arg, Request):
					request = arg
					break

			for key, value in kwargs.items():
				if key == 'request' and isinstance(value, Request):
					request = value
				elif key == 'data':
					data = value

			if not request:
				raise ValueError("未找到请求对象")

			try:
				# 根据请求方法获取数据
				if request.method in ["POST", "PUT", "PATCH"]:
					# 尝试从请求体获取数据
					if hasattr(request.state, 'body_data'):
						body_data = request.state.body_data
					else:
						try:
							body_data = await request.json()
						except Exception:
							body_data = {}

					data.update(body_data)

				# 合并查询参数
				data.update(dict(request.query_params))

				# 合并路径参数
				data.update(dict(request.path_params))

				# 验证数据
				validated_data = _validator.validate_request(model, data)

				# 将验证后的数据添加到kwargs中
				kwargs['validated_data'] = validated_data

				# 调用原始函数
				return await func(*args, **kwargs)

			except CustomValidationError as e:
				# 返回验证错误响应
				response = APIResponse.error(
					code=e.code,
					message=e.message,
					detail=e.detail
				)

				from fastapi.responses import JSONResponse
				return JSONResponse(
					status_code=422,
					content=response.dict()
				)

			except Exception as e:
				logger.error(f"请求验证异常: {str(e)}", exc_info=True)
				raise

		return wrapper

	return decorator


def validate_query (model: Type[ModelType]):
	"""
	查询参数验证装饰器

	Args:
		model: 查询参数模型

	Returns:
		装饰器函数
	"""

	def decorator (func: Callable) -> Callable:
		@wraps(func)
		async def wrapper (*args, **kwargs):
			request = None

			for arg in args:
				if isinstance(arg, Request):
					request = arg
					break

			for key, value in kwargs.items():
				if key == 'request' and isinstance(value, Request):
					request = value

			if not request:
				raise ValueError("未找到请求对象")

			try:
				# 验证查询参数
				validated_query = _validator.validate_query_params(model, request)

				# 将验证后的查询参数添加到kwargs中
				kwargs['validated_query'] = validated_query

				# 调用原始函数
				return await func(*args, **kwargs)

			except CustomValidationError as e:
				response = APIResponse.error(
					code=e.code,
					message=e.message,
					detail=e.detail
				)

				from fastapi.responses import JSONResponse
				return JSONResponse(
					status_code=422,
					content=response.dict()
				)

		return wrapper

	return decorator


def validate_path (model: Type[ModelType]):
	"""
	路径参数验证装饰器

	Args:
		model: 路径参数模型

	Returns:
		装饰器函数
	"""

	def decorator (func: Callable) -> Callable:
		@wraps(func)
		async def wrapper (*args, **kwargs):
			request = None

			for arg in args:
				if isinstance(arg, Request):
					request = arg
					break

			for key, value in kwargs.items():
				if key == 'request' and isinstance(value, Request):
					request = value

			if not request:
				raise ValueError("未找到请求对象")

			try:
				# 验证路径参数
				validated_path = _validator.validate_path_params(model, request)

				# 将验证后的路径参数添加到kwargs中
				kwargs['validated_path'] = validated_path

				# 调用原始函数
				return await func(*args, **kwargs)

			except CustomValidationError as e:
				response = APIResponse.error(
					code=e.code,
					message=e.message,
					detail=e.detail
				)

				from fastapi.responses import JSONResponse
				return JSONResponse(
					status_code=422,
					content=response.dict()
				)

		return wrapper

	return decorator


class ValidatedQuery:
	"""已验证的查询参数依赖"""

	def __init__ (self, model: Type[ModelType]):
		self.model = model

	async def __call__ (self, request: Request) -> ModelType:
		"""依赖调用"""
		return _validator.validate_query_params(self.model, request)


class ValidatedPath:
	"""已验证的路径参数依赖"""

	def __init__ (self, model: Type[ModelType]):
		self.model = model

	async def __call__ (self, request: Request) -> ModelType:
		"""依赖调用"""
		return _validator.validate_path_params(self.model, request)


class ValidatedBody:
	"""已验证的请求体依赖"""

	def __init__ (self, model: Type[ModelType]):
		self.model = model

	async def __call__ (self, request: Request) -> ModelType:
		"""依赖调用"""
		return _validator.validate_body(self.model, request)


# 常用验证规则
class ValidationRules:
	"""验证规则工具类"""

	@staticmethod
	def not_empty (value: Any, field_name: str = "字段") -> Any:
		"""
		验证非空

		Args:
			value: 值
			field_name: 字段名

		Returns:
			Any: 原值

		Raises:
			ValueError: 值为空
		"""
		if value is None or (isinstance(value, str) and not value.strip()):
			raise ValueError(f"{field_name}不能为空")
		return value

	@staticmethod
	def min_length (value: str, min_len: int, field_name: str = "字段") -> str:
		"""
		验证最小长度

		Args:
			value: 字符串值
			min_len: 最小长度
			field_name: 字段名

		Returns:
			str: 原值

		Raises:
			ValueError: 长度不足
		"""
		if len(value) < min_len:
			raise ValueError(f"{field_name}长度不能小于{min_len}")
		return value

	@staticmethod
	def max_length (value: str, max_len: int, field_name: str = "字段") -> str:
		"""
		验证最大长度

		Args:
			value: 字符串值
			max_len: 最大长度
			field_name: 字段名

		Returns:
			str: 原值

		Raises:
			ValueError: 长度超出
		"""
		if len(value) > max_len:
			raise ValueError(f"{field_name}长度不能超过{max_len}")
		return value

	@staticmethod
	def in_range (value: Union[int, float], min_val: float, max_val: float, field_name: str = "字段") -> Union[
		int, float]:
		"""
		验证数值范围

		Args:
			value: 数值
			min_val: 最小值
			max_val: 最大值
			field_name: 字段名

		Returns:
			Union[int, float]: 原值

		Raises:
			ValueError: 超出范围
		"""
		if value < min_val or value > max_val:
			raise ValueError(f"{field_name}必须在{min_val}到{max_val}之间")
		return value

	@staticmethod
	def regex_match (value: str, pattern: str, field_name: str = "字段", error_message: Optional[str] = None) -> str:
		"""
		正则表达式匹配

		Args:
			value: 字符串值
			pattern: 正则表达式
			field_name: 字段名
			error_message: 错误消息

		Returns:
			str: 原值

		Raises:
			ValueError: 不匹配
		"""
		if not re.match(pattern, value):
			if error_message:
				raise ValueError(error_message)
			else:
				raise ValueError(f"{field_name}格式不正确")
		return value

	@staticmethod
	def start_before_end (start_value: Any, end_value: Any, start_field: str = "开始时间",
	                      end_field: str = "结束时间") -> None:
		"""
		验证开始时间早于结束时间

		Args:
			start_value: 开始值
			end_value: 结束值
			start_field: 开始字段名
			end_field: 结束字段名

		Raises:
			ValueError: 开始时间晚于结束时间
		"""
		if start_value >= end_value:
			raise ValueError(f"{start_field}必须早于{end_field}")

	@staticmethod
	def positive (value: Union[int, float], field_name: str = "字段") -> Union[int, float]:
		"""
		验证正数

		Args:
			value: 数值
			field_name: 字段名

		Returns:
			Union[int, float]: 原值

		Raises:
			ValueError: 不是正数
		"""
		if value <= 0:
			raise ValueError(f"{field_name}必须是正数")
		return value

	@staticmethod
	def non_negative (value: Union[int, float], field_name: str = "字段") -> Union[int, float]:
		"""
		验证非负数

		Args:
			value: 数值
			field_name: 字段名

		Returns:
			Union[int, float]: 原值

		Raises:
			ValueError: 是负数
		"""
		if value < 0:
			raise ValueError(f"{field_name}不能是负数")
		return value