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
from decimal import Decimal
from enum import Enum


class SerializerError(Exception):
	"""序列化异常"""
	pass


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

	def object_hook (self, obj):
		# 这里可以添加自定义的反序列化逻辑
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


class CompressedSerializer(SerializerBase):
	"""压缩序列化器（包装器）"""

	def __init__ (self, inner_serializer: SerializerBase, compression_level: int = 6):
		self.inner_serializer = inner_serializer
		self.compression_level = compression_level

	def serialize (self, value: Any) -> bytes:
		"""序列化值并压缩"""
		try:
			data = self.inner_serializer.serialize(value)
			compressed = zlib.compress(data, level=self.compression_level)
			return compressed
		except Exception as e:
			raise SerializerError(f"Failed to compress serialized data: {str(e)}")

	def deserialize (self, data: bytes) -> Any:
		"""解压并反序列化值"""
		try:
			decompressed = zlib.decompress(data)
			return self.inner_serializer.deserialize(decompressed)
		except Exception as e:
			raise SerializerError(f"Failed to decompress serialized data: {str(e)}")

	@property
	def content_type (self) -> str:
		return f"{self.inner_serializer.content_type}+compressed"


class Base64Serializer(SerializerBase):
	"""Base64编码序列化器（包装器）"""

	def __init__ (self, inner_serializer: SerializerBase):
		self.inner_serializer = inner_serializer

	def serialize (self, value: Any) -> bytes:
		"""序列化值并Base64编码"""
		try:
			data = self.inner_serializer.serialize(value)
			encoded = base64.b64encode(data)
			return encoded
		except Exception as e:
			raise SerializerError(f"Failed to Base64 encode serialized data: {str(e)}")

	def deserialize (self, data: bytes) -> Any:
		"""Base64解码并反序列化值"""
		try:
			decoded = base64.b64decode(data)
			return self.inner_serializer.deserialize(decoded)
		except Exception as e:
			raise SerializerError(f"Failed to Base64 decode serialized data: {str(e)}")

	@property
	def content_type (self) -> str:
		return f"{self.inner_serializer.content_type}+base64"


def get_serializer (name: str, **kwargs) -> SerializerBase:
	"""获取序列化器"""
	serializers = {
		"pickle": PickleSerializer,
		"json": JSONSerializer,
		"msgpack": MsgPackSerializer,
	}

	if name not in serializers:
		raise SerializerError(f"Serializer '{name}' is not supported")

	return serializers[name](**kwargs)