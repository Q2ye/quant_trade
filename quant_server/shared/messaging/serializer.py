"""
消息序列化器

提供多种序列化格式支持：JSON、MsgPack、Pickle等
"""

import json
import pickle
from typing import Any
from .base import Message, MessageSerializer, MessageHeaders, MessageMetadata
import msgpack


class JSONSerializer(MessageSerializer):
	"""JSON序列化器"""

	def __init__ (self, encoding: str = 'utf-8'):
		self.encoding = encoding
		self.default_encoder = json.JSONEncoder(
			default=self._default_encoder,
			ensure_ascii=False
		)

	def _default_encoder (self, obj: Any) -> Any:
		"""自定义编码器"""
		if hasattr(obj, 'to_dict'):
			return obj.to_dict()
		elif hasattr(obj, '__dict__'):
			return obj.__dict__
		raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

	async def serialize (self, message: Message) -> bytes:
		"""序列化为JSON"""
		serialized = self.default_encoder.encode(message.serialize())
		return serialized.encode(self.encoding)

	async def deserialize (self, data: bytes) -> Message:
		"""从JSON反序列化"""
		json_str = data.decode(self.encoding)
		message_dict = json.loads(json_str)

		# 重建消息头
		headers_dict = message_dict['headers']
		headers = MessageHeaders(
			message_id=headers_dict['message_id'],
			correlation_id=headers_dict.get('correlation_id'),
			message_type=headers_dict['message_type'],
			priority=headers_dict['priority'],
			timestamp=datetime.fromisoformat(headers_dict['timestamp']),
			source=headers_dict.get('source'),
			destination=headers_dict.get('destination'),
			retry_count=headers_dict.get('retry_count', 0),
			ttl=headers_dict.get('ttl')
		)

		# 重建元数据
		metadata_dict = message_dict.get('metadata', {})
		metadata = MessageMetadata(
			queue_name=metadata_dict.get('queue_name', ''),
			exchange=metadata_dict.get('exchange'),
			routing_key=metadata_dict.get('routing_key'),
			persistent=metadata_dict.get('persistent', True),
			headers=metadata_dict.get('headers')
		)

		return Message(
			headers=headers,
			body=message_dict['body'],
			metadata=metadata
		)


class MsgPackSerializer(MessageSerializer):
	"""MessagePack序列化器"""

	async def serialize (self, message: Message) -> bytes:
		"""序列化为MessagePack"""
		return msgpack.packb(message.serialize(), use_bin_type=True)

	async def deserialize (self, data: bytes) -> Message:
		"""从MessagePack反序列化"""
		message_dict = msgpack.unpackb(data, raw=False)

		# 重建消息头
		headers_dict = message_dict['headers']
		headers = MessageHeaders(
			message_id=headers_dict['message_id'],
			correlation_id=headers_dict.get('correlation_id'),
			message_type=headers_dict['message_type'],
			priority=MessagePriority(headers_dict['priority']),
			timestamp=datetime.fromisoformat(headers_dict['timestamp']),
			source=headers_dict.get('source'),
			destination=headers_dict.get('destination'),
			retry_count=headers_dict.get('retry_count', 0),
			ttl=headers_dict.get('ttl')
		)

		# 重建元数据
		metadata_dict = message_dict.get('metadata', {})
		metadata = MessageMetadata(
			queue_name=metadata_dict.get('queue_name', ''),
			exchange=metadata_dict.get('exchange'),
			routing_key=metadata_dict.get('routing_key'),
			persistent=metadata_dict.get('persistent', True),
			headers=metadata_dict.get('headers')
		)

		return Message(
			headers=headers,
			body=message_dict['body'],
			metadata=metadata
		)


class PickleSerializer(MessageSerializer):
	"""Pickle序列化器（仅限内部使用，不安全）"""

	async def serialize (self, message: Message) -> bytes:
		"""序列化为Pickle"""
		return pickle.dumps(message)

	async def deserialize (self, data: bytes) -> Message:
		"""从Pickle反序列化"""
		return pickle.loads(data)


# 默认序列化器
DEFAULT_SERIALIZER = JSONSerializer()


async def serialize_message (message: Message, serializer: MessageSerializer = None) -> bytes:
	"""序列化消息（快捷函数）"""
	if serializer is None:
		serializer = DEFAULT_SERIALIZER
	return await serializer.serialize(message)


async def deserialize_message (data: bytes, serializer: MessageSerializer = None) -> Message:
	"""反序列化消息（快捷函数）"""
	if serializer is None:
		serializer = DEFAULT_SERIALIZER
	return await serializer.deserialize(data)