"""
序列化器模块
支持多种序列化方式
"""

import abc
import pickle
import json
import msgpack
import zlib
import base64
from typing import Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum


class SerializerError(Exception):
	"""序列化异常"""
	
	def __init__(self, message: str, cause: Optional[Exception] = None):
		super().__init__(message)
		self.cause = cause
		self.message = message
	
	def __str__(self) -> str:
		if self.cause:
			return f"{self.message}: {self.cause}"
		return self.message


class SerializerBase(abc.ABC):
	"""序列化器基类"""

	@abc.abstractmethod
	def serialize (self, value: Any) -> bytes:
		"""序列化值"""
		pass

	@abc.abstractmethod
	def deserialize (self, data: bytes) -> Any:
		"""反序列化值"""
		pass

	@property
	@abc.abstractmethod
	def content_type (self) -> str:
		"""内容类型"""
		pass


class JSONEncoder(json.JSONEncoder):
	"""支持更多类型的JSON编码器"""

	def default (self, obj):
		if isinstance(obj, (datetime, date)):
			return obj.isoformat()
		elif isinstance(obj, timedelta):
			return obj.total_seconds()
		elif isinstance(obj, Decimal):
			return str(obj)
		elif isinstance(obj, Enum):
			return obj.value
		elif hasattr(obj, '__dict__'):
			return obj.__dict__
		elif hasattr(obj, 'to_dict'):
			return obj.to_dict()

		return super().default(obj)


class JSONDecoder(json.JSONDecoder):
	"""JSON解码器"""

	def __init__ (self, *args, **kwargs):
		super().__init__(object_hook=self.object_hook, *args, **kwargs)

	@staticmethod
	def object_hook (obj):
		"""自定义对象钩子，用于反序列化特殊类型"""
		if isinstance(obj, dict):
			# 检查是否为特殊类型标记
			if '__type__' in obj:
				type_name = obj['__type__']
				if type_name == 'datetime':
					try:
						return datetime.fromisoformat(obj['value'])
					except (ValueError, KeyError):
						pass
				elif type_name == 'date':
					try:
						return date.fromisoformat(obj['value'])
					except (ValueError, KeyError):
						pass
				elif type_name == 'timedelta':
					try:
						return timedelta(seconds=obj['value'])
					except (KeyError, TypeError):
						pass
				elif type_name == 'decimal':
					try:
						return Decimal(obj['value'])
					except (KeyError, InvalidOperation):
						pass
			
			# 检查是否为枚举类型
			if '__enum__' in obj:
				try:
					# 这里可以添加枚举类型的反序列化逻辑
					# 需要外部提供枚举类的映射
					pass
				except (KeyError, AttributeError):
					pass
		
		return obj


class PickleSerializer(SerializerBase):
	"""Pickle序列化器"""

	def serialize (self, value: Any) -> bytes:
		"""序列化值"""
		try:
			return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
		except Exception as e:
			raise SerializerError(f"Failed to pickle value: {str(e)}")

	def deserialize (self, data: bytes) -> Any:
		"""反序列化值"""
		try:
			return pickle.loads(data)
		except Exception as e:
			raise SerializerError(f"Failed to unpickle data: {str(e)}")

	@property
	def content_type (self) -> str:
		return "application/x-pickle"


class JSONSerializer(SerializerBase):
	"""JSON序列化器"""

	def __init__ (self, ensure_ascii: bool = False, indent: Optional[int] = None):
		self.ensure_ascii = ensure_ascii
		self.indent = indent
		self.encoder = JSONEncoder(
			ensure_ascii=ensure_ascii,
			indent=indent,
			default=str
		)
		self.decoder = JSONDecoder()

	def serialize (self, value: Any) -> bytes:
		"""序列化值"""
		try:
			json_str = self.encoder.encode(value)
			return json_str.encode('utf-8')
		except Exception as e:
			raise SerializerError(f"Failed to serialize value to JSON: {str(e)}")

	def deserialize (self, data: bytes) -> Any:
		"""反序列化值"""
		try:
			json_str = data.decode('utf-8')
			return self.decoder.decode(json_str)
		except Exception as e:
			raise SerializerError(f"Failed to deserialize JSON data: {str(e)}")

	@property
	def content_type (self) -> str:
		return "application/json"


class MsgPackSerializer(SerializerBase):
	"""MessagePack序列化器"""

	def serialize (self, value: Any) -> bytes:
		"""序列化值"""
		try:
			return msgpack.packb(value, use_bin_type=True)
		except Exception as e:
			raise SerializerError(f"Failed to serialize value to MessagePack: {str(e)}")

	def deserialize (self, data: bytes) -> Any:
		"""反序列化值"""
		try:
			return msgpack.unpackb(data, raw=False)
		except Exception as e:
			raise SerializerError(f"Failed to deserialize MessagePack data: {str(e)}")

	@property
	def content_type (self) -> str:
		return "application/x-msgpack"
