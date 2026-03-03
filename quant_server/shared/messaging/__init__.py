"""
消息中间件模块

提供统一的消息生产和消费接口，支持多种消息后端（Redis、RabbitMQ、Kafka等）
实现发布-订阅模式和消息队列模式
"""

from .base import MessageBus, MessageProducer, MessageConsumer
from .producer import RedisProducer, RabbitMQProducer, KafkaProducer, get_producer
from .consumer import RedisConsumer, RabbitMQConsumer, KafkaConsumer, get_consumer
from .message_bus import MessageBusFactory, get_message_bus
from .serializer import MessageSerializer, JSONSerializer, MsgPackSerializer
from .types import Message, MessageHeaders, MessageMetadata

__all__ = [
	# 基类
	'MessageBus',
	'MessageProducer',
	'MessageConsumer',

	# 具体实现
	'RedisProducer',
	'RabbitMQProducer',
	'KafkaProducer',
	'RedisConsumer',
	'RabbitMQConsumer',
	'KafkaConsumer',

	# 工厂方法
	'get_producer',
	'get_consumer',
	'get_message_bus',
	'MessageBusFactory',

	# 序列化
	'MessageSerializer',
	'JSONSerializer',
	'MsgPackSerializer',

	# 类型定义
	'Message',
	'MessageHeaders',
	'MessageMetadata',
]