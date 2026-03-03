"""
消息消费者实现

支持Redis、RabbitMQ、Kafka等消息中间件
"""

import asyncio
import json
from typing import Any, Dict, Optional, Callable, Awaitable
from .base import (
	MessageConsumer, Message, MessageSerializer
)
from .serializer import JSONSerializer, deserialize_message
import aioredis
import aio_pika
from aiokafka import AIOKafkaConsumer
import logging

logger = logging.getLogger(__name__)


class RedisConsumer(MessageConsumer):
	"""Redis消息消费者"""

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
		self.subscriptions = {}
		self.connected = False
		self.running = False

	async def connect (self) -> None:
		"""连接到Redis"""
		if not self.connected:
			self.redis_pool = await aioredis.create_redis_pool(
				self.redis_url,
				maxsize=self.max_connections
			)
			self.connected = True
			logger.info(f"Redis consumer connected to {self.redis_url}")

	async def disconnect (self) -> None:
		"""断开Redis连接"""
		if self.connected and self.redis_pool:
			self.running = False
			self.redis_pool.close()
			await self.redis_pool.wait_closed()
			self.connected = False
			logger.info("Redis consumer disconnected")

	async def subscribe (
			self,
			queue_name: str,
			callback: Callable[[Message], Awaitable[None]],
			**kwargs
	) -> str:
		"""订阅Redis消息"""
		if not self.connected:
			await self.connect()

		subscription_id = f"{queue_name}_{id(callback)}"

		async def consumer_task ():
			"""消费者任务"""
			pattern = kwargs.get('pattern', 'queue')

			while self.running:
				try:
					if pattern == 'pubsub':
						# 发布/订阅模式
						pubsub = self.redis_pool.pubsub()
						await pubsub.subscribe(queue_name)

						async for message in pubsub.listen():
							if message['type'] == 'message':
								msg = await deserialize_message(
									message['data'],
									self.serializer
								)
								await callback(msg)
					else:
						# 阻塞弹出消息
						if kwargs.get('blocking', True):
							result = await self.redis_pool.brpop(queue_name, timeout=1)
							if result:
								_, data = result
								msg = await deserialize_message(data, self.serializer)
								await callback(msg)
						else:
							# 非阻塞弹出
							data = await self.redis_pool.rpop(queue_name)
							if data:
								msg = await deserialize_message(data, self.serializer)
								await callback(msg)
							else:
								await asyncio.sleep(0.1)
				except asyncio.CancelledError:
					break
				except Exception as e:
					logger.error(f"Error in Redis consumer: {e}")
					await asyncio.sleep(1)

		# 启动消费者任务
		self.running = True
		task = asyncio.create_task(consumer_task())
		self.subscriptions[subscription_id] = task

		logger.info(f"Subscribed to Redis queue {queue_name}")
		return subscription_id

	async def unsubscribe (self, subscription_id: str) -> None:
		"""取消订阅"""
		if subscription_id in self.subscriptions:
			task = self.subscriptions[subscription_id]
			task.cancel()
			try:
				await task
			except asyncio.CancelledError:
				pass
			del self.subscriptions[subscription_id]
			logger.info(f"Unsubscribed from {subscription_id}")

	async def consume_one (
			self,
			queue_name: str,
			timeout: Optional[float] = None
	) -> Optional[Message]:
		"""消费单条消息"""
		if not self.connected:
			await self.connect()

		try:
			if timeout:
				# 阻塞弹出
				result = await self.redis_pool.brpop(queue_name, timeout=timeout)
				if result:
					_, data = result
					return await deserialize_message(data, self.serializer)
			else:
				# 非阻塞弹出
				data = await self.redis_pool.rpop(queue_name)
				if data:
					return await deserialize_message(data, self.serializer)
		except Exception as e:
			logger.error(f"Error consuming from Redis: {e}")

		return None


class RabbitMQConsumer(MessageConsumer):
	"""RabbitMQ消息消费者"""

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
		self.subscriptions = {}
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
			logger.info(f"RabbitMQ consumer connected to {self.amqp_url}")

	async def disconnect (self) -> None:
		"""断开RabbitMQ连接"""
		if self.connected:
			# 取消所有订阅
			for subscription_id in list(self.subscriptions.keys()):
				await self.unsubscribe(subscription_id)

			if self.channel:
				await self.channel.close()
			if self.connection:
				await self.connection.close()
			self.connected = False
			logger.info("RabbitMQ consumer disconnected")

	async def subscribe (
			self,
			queue_name: str,
			callback: Callable[[Message], Awaitable[None]],
			**kwargs
	) -> str:
		"""订阅RabbitMQ消息"""
		if not self.connected:
			await self.connect()

		# 声明队列和交换机
		exchange = await self.channel.declare_exchange(
			kwargs.get('exchange', 'amq.direct'),
			aio_pika.ExchangeType.DIRECT,
			durable=True
		)

		queue = await self.channel.declare_queue(
			queue_name,
			durable=True,
			arguments=kwargs.get('queue_arguments')
		)

		await queue.bind(exchange, queue_name)

		subscription_id = f"{queue_name}_{id(callback)}"

		async def process_message (message: aio_pika.IncomingMessage):
			"""处理接收到的消息"""
			async with message.process():
				try:
					msg = await deserialize_message(message.body, self.serializer)
					await callback(msg)
				except Exception as e:
					logger.error(f"Error processing RabbitMQ message: {e}")
					if not kwargs.get('auto_ack', True):
						await message.nack()

		# 开始消费
		consumer_tag = await queue.consume(process_message)
		self.subscriptions[subscription_id] = {
			'queue': queue,
			'consumer_tag': consumer_tag,
			'callback': callback
		}

		logger.info(f"Subscribed to RabbitMQ queue {queue_name}")
		return subscription_id

	async def unsubscribe (self, subscription_id: str) -> None:
		"""取消订阅"""
		if subscription_id in self.subscriptions:
			subscription = self.subscriptions[subscription_id]
			await subscription['queue'].cancel(subscription['consumer_tag'])
			del self.subscriptions[subscription_id]
			logger.info(f"Unsubscribed from {subscription_id}")

	async def consume_one (
			self,
			queue_name: str,
			timeout: Optional[float] = None
	) -> Optional[Message]:
		"""消费单条消息"""
		if not self.connected:
			await self.connect()

		try:
			# 声明队列
			queue = await self.channel.declare_queue(queue_name, durable=True)

			# 获取消息
			message = await queue.get(timeout=timeout, fail=False)
			if message:
				msg = await deserialize_message(message.body, self.serializer)
				await message.ack()
				return msg
		except Exception as e:
			logger.error(f"Error consuming from RabbitMQ: {e}")

		return None


class KafkaConsumer(MessageConsumer):
	"""Kafka消息消费者"""

	def __init__ (
			self,
			bootstrap_servers: str,
			group_id: str,
			serializer: MessageSerializer = None,
			consumer_config: Optional[Dict] = None
	):
		self.bootstrap_servers = bootstrap_servers
		self.group_id = group_id
		self.serializer = serializer or JSONSerializer()
		self.consumer_config = consumer_config or {}
		self.consumer = None
		self.subscriptions = {}
		self.connected = False
		self.running = False

	async def connect (self) -> None:
		"""连接到Kafka"""
		if not self.connected:
			config = {
				'bootstrap_servers': self.bootstrap_servers,
				'group_id': self.group_id,
				'enable_auto_commit': True,
				'value_deserializer': lambda v: v,
				**self.consumer_config
			}
			self.consumer = AIOKafkaConsumer(**config)
			self.connected = True
			logger.info(f"Kafka consumer connected to {self.bootstrap_servers}")

	async def disconnect (self) -> None:
		"""断开Kafka连接"""
		if self.connected and self.consumer:
			self.running = False
			await self.consumer.stop()
			self.connected = False
			logger.info("Kafka consumer disconnected")

	async def subscribe (
			self,
			queue_name: str,
			callback: Callable[[Message], Awaitable[None]],
			**kwargs
	) -> str:
		"""订阅Kafka消息"""
		if not self.connected:
			await self.connect()

		subscription_id = f"{queue_name}_{id(callback)}"

		async def consumer_task ():
			"""消费者任务"""
			await self.consumer.start()
			self.consumer.subscribe([queue_name])

			self.running = True
			try:
				async for msg in self.consumer:
					if not self.running:
						break

					try:
						message = await deserialize_message(msg.value, self.serializer)
						await callback(message)
					except Exception as e:
						logger.error(f"Error processing Kafka message: {e}")
			except asyncio.CancelledError:
				pass
			finally:
				await self.consumer.stop()

		# 启动消费者任务
		task = asyncio.create_task(consumer_task())
		self.subscriptions[subscription_id] = task

		logger.info(f"Subscribed to Kafka topic {queue_name}")
		return subscription_id

	async def unsubscribe (self, subscription_id: str) -> None:
		"""取消订阅"""
		if subscription_id in self.subscriptions:
			self.running = False
			task = self.subscriptions[subscription_id]
			task.cancel()
			try:
				await task
			except asyncio.CancelledError:
				pass
			del self.subscriptions[subscription_id]
			logger.info(f"Unsubscribed from {subscription_id}")

	async def consume_one (
			self,
			queue_name: str,
			timeout: Optional[float] = None
	) -> Optional[Message]:
		"""消费单条消息"""
		if not self.connected:
			await self.connect()

		try:
			# 创建一次性消费者
			consumer = AIOKafkaConsumer(
				queue_name,
				bootstrap_servers=self.bootstrap_servers,
				value_deserializer=lambda v: v,
				enable_auto_commit=False,
				auto_offset_reset='earliest'
			)

			await consumer.start()

			# 获取消息
			msg = await consumer.getone(timeout=timeout)
			if msg:
				message = await deserialize_message(msg.value, self.serializer)
				await consumer.commit()
				return message
		except Exception as e:
			logger.error(f"Error consuming from Kafka: {e}")
		finally:
			if 'consumer' in locals():
				await consumer.stop()

		return None


# 工厂函数
async def get_consumer (
		backend: str = 'redis',
		**config
) -> MessageConsumer:
	"""
	获取消息消费者实例

	Args:
		backend: 后端类型 ('redis', 'rabbitmq', 'kafka')
		**config: 后端配置参数

	Returns:
		MessageConsumer实例
	"""
	backend = backend.lower()

	if backend == 'redis':
		return RedisConsumer(
			redis_url=config.get('redis_url', 'redis://localhost:6379'),
			serializer=config.get('serializer'),
			max_connections=config.get('max_connections', 10)
		)
	elif backend == 'rabbitmq':
		return RabbitMQConsumer(
			amqp_url=config.get('amqp_url', 'amqp://guest:guest@localhost/'),
			serializer=config.get('serializer'),
			connection_params=config.get('connection_params', {})
		)
	elif backend == 'kafka':
		return KafkaConsumer(
			bootstrap_servers=config.get('bootstrap_servers', 'localhost:9092'),
			group_id=config.get('group_id', 'default_group'),
			serializer=config.get('serializer'),
			consumer_config=config.get('consumer_config', {})
		)
	else:
		raise ValueError(f"Unsupported message backend: {backend}")