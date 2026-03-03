"""
消息总线

提供统一的消息收发接口，支持事件发布/订阅和命令/响应模式
"""

import asyncio
from typing import Any, Dict, Optional, Callable, Awaitable
from uuid import uuid4
from .base import MessageBus, Message, MessageHeaders, MessageMetadata, MessagePriority
from .producer import get_producer, RedisProducer, RabbitMQProducer, KafkaProducer
from .consumer import get_consumer, RedisConsumer, RabbitMQConsumer, KafkaConsumer
from .serializer import JSONSerializer, serialize_message, deserialize_message
import logging

logger = logging.getLogger(__name__)


class MessageBusFactory:
	"""消息总线工厂"""

	@staticmethod
	async def create (
			backend: str = 'redis',
			producer_config: Optional[Dict] = None,
			consumer_config: Optional[Dict] = None,
			event_exchange: str = 'events',
			command_exchange: str = 'commands'
	) -> 'DefaultMessageBus':
		"""
		创建消息总线实例

		Args:
			backend: 后端类型 ('redis', 'rabbitmq', 'kafka')
			producer_config: 生产者配置
			consumer_config: 消费者配置
			event_exchange: 事件交换机名称
			command_exchange: 命令交换机名称

		Returns:
			DefaultMessageBus实例
		"""
		producer_config = producer_config or {}
		consumer_config = consumer_config or {}

		# 获取生产者和消费者
		producer = await get_producer(backend, **producer_config)
		consumer = await get_consumer(backend, **consumer_config)

		return DefaultMessageBus(
			producer=producer,
			consumer=consumer,
			backend=backend,
			event_exchange=event_exchange,
			command_exchange=command_exchange
		)


class DefaultMessageBus(MessageBus):
	"""默认消息总线实现"""

	def __init__ (
			self,
			producer: Any,
			consumer: Any,
			backend: str = 'redis',
			event_exchange: str = 'events',
			command_exchange: str = 'commands'
	):
		self.producer = producer
		self.consumer = consumer
		self.backend = backend
		self.event_exchange = event_exchange
		self.command_exchange = command_exchange
		self.response_callbacks = {}
		self.subscriptions = {}
		self.serializer = JSONSerializer()
		self.initialized = False

	async def initialize (self) -> None:
		"""初始化消息总线"""
		if not self.initialized:
			await self.producer.connect()
			await self.consumer.connect()
			self.initialized = True
			logger.info(f"Message bus initialized with {self.backend} backend")

	async def shutdown (self) -> None:
		"""关闭消息总线"""
		if self.initialized:
			# 取消所有订阅
			for subscription_id in list(self.subscriptions.keys()):
				await self.consumer.unsubscribe(subscription_id)

			await self.producer.disconnect()
			await self.consumer.disconnect()
			self.initialized = False
			logger.info("Message bus shutdown")

	async def publish_event (
			self,
			event_type: str,
			event_data: Any,
			routing_key: Optional[str] = None,
			**kwargs
	) -> str:
		"""
		发布事件（发布/订阅模式）

		Args:
			event_type: 事件类型
			event_data: 事件数据
			routing_key: 路由键（默认为事件类型）
			**kwargs: 其他参数

		Returns:
			消息ID
		"""
		routing_key = routing_key or event_type

		# 创建消息头
		headers = MessageHeaders(
			message_type='event',
			priority=kwargs.get('priority', MessagePriority.NORMAL),
			source=kwargs.get('source'),
			destination=routing_key,
			correlation_id=kwargs.get('correlation_id'),
			ttl=kwargs.get('ttl')
		)

		message_body = {
			'event_type': event_type,
			'event_data': event_data,
			'timestamp': headers.timestamp.isoformat()
		}

		# 发布消息
		if self.backend == 'rabbitmq':
			return await self.producer.publish_to_exchange(
				exchange=self.event_exchange,
				routing_key=routing_key,
				message=message_body,
				headers=headers.to_dict(),
				exchange_type=kwargs.get('exchange_type', 'TOPIC'),
				persistent=kwargs.get('persistent', True),
				**kwargs
			)
		else:
			# Redis和Kafka使用队列模式
			queue_name = f"{self.event_exchange}.{routing_key}"
			return await self.producer.publish(
				queue_name=queue_name,
				message=message_body,
				headers=headers.to_dict(),
				**kwargs
			)

	async def subscribe_event (
			self,
			event_type: str,
			callback: Callable[[Message], Awaitable[None]],
			**kwargs
	) -> str:
		"""
		订阅事件

		Args:
			event_type: 事件类型
			callback: 回调函数
			**kwargs: 其他参数

		Returns:
			订阅ID
		"""
		queue_name = kwargs.get('queue_name') or f"event.{event_type}.{uuid4().hex[:8]}"

		if self.backend == 'rabbitmq':
			# RabbitMQ使用主题交换机
			return await self.consumer.subscribe(
				queue_name=queue_name,
				callback=callback,
				exchange=self.event_exchange,
				routing_key=event_type,
				**kwargs
			)
		else:
			# Redis和Kafka使用队列
			return await self.consumer.subscribe(
				queue_name=f"{self.event_exchange}.{event_type}",
				callback=callback,
				**kwargs
			)

	async def send_command (
			self,
			command_name: str,
			command_data: Any,
			target_queue: str,
			**kwargs
	) -> str:
		"""
		发送命令（点对点模式）

		Args:
			command_name: 命令名称
			command_data: 命令数据
			target_queue: 目标队列
			**kwargs: 其他参数

		Returns:
			消息ID
		"""
		# 创建消息头
		headers = MessageHeaders(
			message_type='command',
			priority=kwargs.get('priority', MessagePriority.HIGH),
			source=kwargs.get('source'),
			destination=target_queue,
			correlation_id=kwargs.get('correlation_id'),
			ttl=kwargs.get('ttl', 300)  # 命令默认TTL 5分钟
		)

		message_body = {
			'command_name': command_name,
			'command_data': command_data,
			'timestamp': headers.timestamp.isoformat()
		}

		# 发送消息
		if self.backend == 'rabbitmq':
			return await self.producer.publish_to_exchange(
				exchange=self.command_exchange,
				routing_key=target_queue,
				message=message_body,
				headers=headers.to_dict(),
				exchange_type='DIRECT',
				persistent=True,
				**kwargs
			)
		else:
			return await self.producer.publish(
				queue_name=target_queue,
				message=message_body,
				headers=headers.to_dict(),
				**kwargs
			)

	async def request_response (
			self,
			request_type: str,
			request_data: Any,
			response_queue: str,
			timeout: float = 30.0,
			**kwargs
	) -> Any:
		"""
		请求-响应模式

		Args:
			request_type: 请求类型
			request_data: 请求数据
			response_queue: 响应队列
			timeout: 超时时间（秒）
			**kwargs: 其他参数

		Returns:
			响应数据
		"""
		correlation_id = str(uuid4())
		response_future = asyncio.Future()
		self.response_callbacks[correlation_id] = response_future

		# 创建响应队列消费者
		async def response_handler (message: Message):
			"""响应处理器"""
			if message.headers.correlation_id == correlation_id:
				response_future.set_result(message.body)

		# 订阅响应队列
		subscription_id = await self.subscribe_event(
			event_type=response_queue,
			callback=response_handler,
			queue_name=f"response.{correlation_id}"
		)

		try:
			# 发送请求
			await self.send_command(
				command_name=request_type,
				command_data=request_data,
				target_queue=kwargs.get('target_queue', request_type),
				correlation_id=correlation_id,
				reply_to=response_queue,
				**kwargs
			)

			# 等待响应
			try:
				response = await asyncio.wait_for(response_future, timeout=timeout)
				return response
			except asyncio.TimeoutError:
				logger.error(f"Request {correlation_id} timeout after {timeout}s")
				raise TimeoutError(f"Request timeout after {timeout}s")
		finally:
			# 清理资源
			await self.consumer.unsubscribe(subscription_id)
			if correlation_id in self.response_callbacks:
				del self.response_callbacks[correlation_id]


# 全局消息总线实例
_message_bus = None


async def get_message_bus (
		backend: str = 'redis',
		**config
) -> DefaultMessageBus:
	"""
	获取全局消息总线实例（单例模式）

	Args:
		backend: 后端类型
		**config: 配置参数

	Returns:
		DefaultMessageBus实例
	"""
	global _message_bus

	if _message_bus is None:
		_message_bus = await MessageBusFactory.create(backend, **config)
		await _message_bus.initialize()

	return _message_bus


async def shutdown_message_bus () -> None:
	"""关闭全局消息总线"""
	global _message_bus

	if _message_bus is not None:
		await _message_bus.shutdown()
		_message_bus = None