"""
消息生产者实现

支持Redis、RabbitMQ、Kafka等消息中间件
"""

import logging
from typing import Any, Dict, Optional

import aio_pika
from kafka import KafkaProducer as SyncKafkaProducer
from kafka.errors import KafkaError
from redis.asyncio import Redis

from .base import (
	MessageProducer, Message, MessageHeaders, MessageMetadata,
	MessagePriority, MessageSerializer
)
from .serializer import JSONSerializer, serialize_message

logger = logging.getLogger(__name__)


class RedisProducer(MessageProducer):
	"""Redis消息生产者"""

	def __init__ (
			self,
			redis_url: str,
			serializer: MessageSerializer = None,
			max_connections: int = 10
	):
		self.redis_url = redis_url
		self.serializer = serializer or JSONSerializer()
		self.max_connections = max_connections
		self.redis_pool = None
		self.connected = False

	async def connect (self) -> None:
		"""连接到Redis"""
		if not self.connected:
			self.redis_pool = Redis.from_url(
				self.redis_url,
				max_connections=self.max_connections
			)
			await self.redis_pool.ping()  # 测试连接
			self.connected = True
			logger.info(f"Redis producer connected to {self.redis_url}")

	async def disconnect (self) -> None:
		"""断开Redis连接"""
		if self.connected and self.redis_pool:
			await self.redis_pool.close()
			self.connected = False
			logger.info("Redis producer disconnected")

	async def publish (
			self,
			queue_name: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""发布消息到Redis列表"""
		if not self.connected:
			await self.connect()

		# 创建消息对象
		message_headers = MessageHeaders(
			message_type=kwargs.get('message_type', 'default'),
			priority=kwargs.get('priority', MessagePriority.NORMAL),
			source=kwargs.get('source'),
			destination=queue_name,
			ttl=kwargs.get('ttl')
		)

		metadata = MessageMetadata(
			queue_name=queue_name,
			persistent=kwargs.get('persistent', True)
		)

		msg = Message(
			headers=message_headers,
			body=message,
			metadata=metadata
		)

		# 序列化消息
		serialized = await serialize_message(msg, self.serializer)

		# 发布到Redis
		if kwargs.get('pattern', 'queue') == 'pubsub':
			# 发布/订阅模式
			await self.redis_pool.publish(queue_name, serialized)
		else:
			# 列表/队列模式
			await self.redis_pool.lpush(queue_name, serialized)

		logger.debug(f"Published message to Redis queue {queue_name}: {message_headers.message_id}")
		return message_headers.message_id

	async def publish_to_exchange (
			self,
			exchange: str,
			routing_key: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""Redis不支持Exchange，转发到publish"""
		return await self.publish(
			queue_name=routing_key,
			message=message,
			headers=headers,
			**kwargs
		)


class RabbitMQProducer(MessageProducer):
	"""RabbitMQ消息生产者"""

	def __init__ (
			self,
			amqp_url: str,
			serializer: MessageSerializer = None,
			connection_params: Optional[Dict] = None
	):
		self.amqp_url = amqp_url
		self.serializer = serializer or JSONSerializer()
		self.connection_params = connection_params or {}
		self.connection = None
		self.channel = None
		self.connected = False

	async def connect (self) -> None:
		"""连接到RabbitMQ"""
		if not self.connected:
			self.connection = await aio_pika.connect_robust(
				self.amqp_url,
				**self.connection_params
			)
			self.channel = await self.connection.channel()
			await self.channel.set_qos(prefetch_count=1)
			self.connected = True
			logger.info(f"RabbitMQ producer connected to {self.amqp_url}")

	async def disconnect (self) -> None:
		"""断开RabbitMQ连接"""
		if self.connected:
			if self.channel:
				await self.channel.close()
			if self.connection:
				await self.connection.close()
			self.connected = False
			logger.info("RabbitMQ producer disconnected")

	async def publish (
			self,
			queue_name: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""发布消息到RabbitMQ队列"""
		if not self.connected:
			await self.connect()

		# 创建消息对象
		message_headers = MessageHeaders(
			message_type=kwargs.get('message_type', 'default'),
			priority=kwargs.get('priority', MessagePriority.NORMAL),
			source=kwargs.get('source'),
			destination=queue_name,
			ttl=kwargs.get('ttl')
		)

		metadata = MessageMetadata(
			queue_name=queue_name,
			exchange=kwargs.get('exchange', ''),
			routing_key=queue_name,
			persistent=kwargs.get('persistent', True),
			headers=headers
		)

		msg = Message(
			headers=message_headers,
			body=message,
			metadata=metadata
		)

		# 序列化消息
		serialized = await serialize_message(msg, self.serializer)

		# 发布消息
		exchange = await self.channel.declare_exchange(
			kwargs.get('exchange', 'amq.direct'),
			aio_pika.ExchangeType.DIRECT,
			durable=True
		)

		queue = await self.channel.declare_queue(queue_name, durable=True)
		await queue.bind(exchange, queue_name)

		await exchange.publish(
			aio_pika.Message(
				body=serialized,
				delivery_mode=2 if kwargs.get('persistent', True) else 1,
				headers=headers or {},
				expiration=kwargs.get('ttl')
			),
			routing_key=queue_name
		)

		logger.debug(f"Published message to RabbitMQ queue {queue_name}: {message_headers.message_id}")
		return message_headers.message_id

	async def publish_to_exchange (
			self,
			exchange: str,
			routing_key: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""发布消息到RabbitMQ交换机"""
		if not self.connected:
			await self.connect()

		# 创建消息对象
		message_headers = MessageHeaders(
			message_type=kwargs.get('message_type', 'default'),
			priority=kwargs.get('priority', MessagePriority.NORMAL),
			source=kwargs.get('source'),
			destination=routing_key,
			ttl=kwargs.get('ttl')
		)

		metadata = MessageMetadata(
			queue_name=routing_key,
			exchange=exchange,
			routing_key=routing_key,
			persistent=kwargs.get('persistent', True),
			headers=headers
		)

		msg = Message(
			headers=message_headers,
			body=message,
			metadata=metadata
		)

		# 序列化消息
		serialized = await serialize_message(msg, self.serializer)

		# 声明交换机和队列
		exchange_type = kwargs.get('exchange_type', 'direct').upper()
		# 使用 getattr 来获取枚举值
		exchange_type_enum = getattr(aio_pika.ExchangeType, exchange_type, aio_pika.ExchangeType.DIRECT)
		exchange_obj = await self.channel.declare_exchange(
			exchange,
			exchange_type_enum,
			durable=True
		)

		# 发布到交换机
		await exchange_obj.publish(
			aio_pika.Message(
				body=serialized,
				delivery_mode=2 if kwargs.get('persistent', True) else 1,
				headers=headers or {},
				expiration=kwargs.get('ttl')
			),
			routing_key=routing_key
		)

		logger.debug(f"Published message to RabbitMQ exchange {exchange}: {message_headers.message_id}")
		return message_headers.message_id


class KafkaProducer(MessageProducer):
	"""Kafka消息生产者"""

	def __init__ (
			self,
			bootstrap_servers: str,
			serializer: MessageSerializer = None,
			producer_config: Optional[Dict] = None
	):
		self.bootstrap_servers = bootstrap_servers
		self.serializer = serializer or JSONSerializer()
		self.producer_config = producer_config or {}
		self.producer = None
		self.connected = False

	async def connect (self) -> None:
		"""连接到Kafka"""
		if not self.connected:
			config = {
				'bootstrap_servers': self.bootstrap_servers,
				'value_serializer': lambda v: v,
				**self.producer_config
			}
			self.producer = SyncKafkaProducer(**config)
			self.connected = True
			logger.info(f"Kafka producer connected to {self.bootstrap_servers}")

	async def disconnect (self) -> None:
		"""断开Kafka连接"""
		if self.connected and self.producer:
			self.producer.close()
			self.connected = False
			logger.info("Kafka producer disconnected")

	async def publish (
			self,
			queue_name: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""发布消息到Kafka主题"""
		if not self.connected:
			await self.connect()

		# 创建消息对象
		message_headers = MessageHeaders(
			message_type=kwargs.get('message_type', 'default'),
			priority=kwargs.get('priority', MessagePriority.NORMAL),
			source=kwargs.get('source'),
			destination=queue_name,
			ttl=kwargs.get('ttl')
		)

		metadata = MessageMetadata(
			queue_name=queue_name,
			persistent=kwargs.get('persistent', True),
			headers=headers
		)

		msg = Message(
			headers=message_headers,
			body=message,
			metadata=metadata
		)

		# 序列化消息
		serialized = await serialize_message(msg, self.serializer)

		# 发送到Kafka
		future = self.producer.send(
			queue_name,
			value=serialized,
			headers=[(k, str(v).encode()) for k, v in (headers or {}).items()]
		)

		try:
			# 等待发送结果
			future.get(timeout=kwargs.get('timeout', 10))
			logger.debug(f"Published message to Kafka topic {queue_name}: {message_headers.message_id}")
			return message_headers.message_id
		except KafkaError as e:
			logger.error(f"Failed to publish message to Kafka: {e}")
			raise

	async def publish_to_exchange (
			self,
			exchange: str,
			routing_key: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""Kafka不支持Exchange，转发到publish"""
		return await self.publish(
			queue_name=routing_key,
			message=message,
			headers=headers,
			**kwargs
		)


# 工厂函数
async def get_producer (
		backend: str = 'redis',
		**config
) -> MessageProducer:
	"""
	获取消息生产者实例

	Args:
		backend: 后端类型 ('redis', 'rabbitmq', 'kafka')
		**config: 后端配置参数

	Returns:
		MessageProducer实例
	"""
	backend = backend.lower()

	if backend == 'redis':
		return RedisProducer(
			redis_url=config.get('redis_url', 'redis://localhost:6379'),
			serializer=config.get('serializer'),
			max_connections=config.get('max_connections', 10)
		)
	elif backend == 'rabbitmq':
		return RabbitMQProducer(
			amqp_url=config.get('amqp_url', 'amqp://guest:guest@localhost/'),
			serializer=config.get('serializer'),
			connection_params=config.get('connection_params', {})
		)
	elif backend == 'kafka':
		return KafkaProducer(
			bootstrap_servers=config.get('bootstrap_servers', 'localhost:9092'),
			serializer=config.get('serializer'),
			producer_config=config.get('producer_config', {})
		)
	else:
		raise ValueError(f"Unsupported message backend: {backend}")