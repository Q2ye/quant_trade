"""
消息中间件抽象基类

定义消息生产者和消费者的统一接口，支持多种消息后端的实现
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Awaitable, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid


class MessagePriority(Enum):
	"""消息优先级"""
	LOW = 0
	NORMAL = 1
	HIGH = 2
	CRITICAL = 3


@dataclass
class MessageHeaders:
	"""消息头部信息"""
	message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
	correlation_id: Optional[str] = None
	message_type: str = "default"
	priority: MessagePriority = MessagePriority.NORMAL
	timestamp: datetime = field(default_factory=datetime.now)
	source: Optional[str] = None
	destination: Optional[str] = None
	retry_count: int = 0
	ttl: Optional[int] = None  # 生存时间（秒）

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		data = asdict(self)
		data['timestamp'] = self.timestamp.isoformat()
		data['priority'] = self.priority.value
		return data


@dataclass
class MessageMetadata:
	"""消息元数据"""
	queue_name: str
	exchange: Optional[str] = None
	routing_key: Optional[str] = None
	persistent: bool = True
	headers: Optional[Dict[str, Any]] = None


@dataclass
class Message:
	"""消息体"""
	headers: MessageHeaders
	body: Any
	metadata: MessageMetadata

	def serialize (self) -> Dict[str, Any]:
		"""序列化消息"""
		return {
			'headers': self.headers.to_dict(),
			'body': self.body,
			'metadata': asdict(self.metadata) if self.metadata else None
		}


class MessageSerializer(ABC):
	"""消息序列化器抽象基类"""

	@abstractmethod
	async def serialize (self, message: Message) -> bytes:
		"""序列化消息"""
		pass

	@abstractmethod
	async def deserialize (self, data: bytes) -> Message:
		"""反序列化消息"""
		pass


class MessageProducer(ABC):
	"""消息生产者抽象基类"""

	@abstractmethod
	async def connect (self) -> None:
		"""连接到消息中间件"""
		pass

	@abstractmethod
	async def disconnect (self) -> None:
		"""断开连接"""
		pass

	@abstractmethod
	async def publish (
			self,
			queue_name: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""发布消息到指定队列"""
		pass

	@abstractmethod
	async def publish_to_exchange (
			self,
			exchange: str,
			routing_key: str,
			message: Any,
			headers: Optional[Dict[str, Any]] = None,
			**kwargs
	) -> str:
		"""发布消息到交换机"""
		pass


class MessageConsumer(ABC):
	"""消息消费者抽象基类"""

	@abstractmethod
	async def connect (self) -> None:
		"""连接到消息中间件"""
		pass

	@abstractmethod
	async def disconnect (self) -> None:
		"""断开连接"""
		pass

	@abstractmethod
	async def subscribe (
			self,
			queue_name: str,
			callback: Callable[[Message], Awaitable[None]],
			**kwargs
	) -> str:
		"""订阅队列消息"""
		pass

	@abstractmethod
	async def unsubscribe (self, subscription_id: str) -> None:
		"""取消订阅"""
		pass

	@abstractmethod
	async def consume_one (
			self,
			queue_name: str,
			timeout: Optional[float] = None
	) -> Optional[Message]:
		"""消费单条消息"""
		pass


class MessageBus(ABC):
	"""消息总线抽象基类"""

	@abstractmethod
	async def initialize (self) -> None:
		"""初始化消息总线"""
		pass

	@abstractmethod
	async def shutdown (self) -> None:
		"""关闭消息总线"""
		pass

	@abstractmethod
	async def publish_event (
			self,
			event_type: str,
			event_data: Any,
			routing_key: Optional[str] = None,
			**kwargs
	) -> str:
		"""发布事件"""
		pass

	@abstractmethod
	async def subscribe_event (
			self,
			event_type: str,
			callback: Callable[[Message], Awaitable[None]],
			**kwargs
	) -> str:
		"""订阅事件"""
		pass

	@abstractmethod
	async def send_command (
			self,
			command_name: str,
			command_data: Any,
			target_queue: str,
			**kwargs
	) -> str:
		"""发送命令（点对点）"""
		pass

	@abstractmethod
	async def request_response (
			self,
			request_type: str,
			request_data: Any,
			response_queue: str,
			timeout: float = 30.0,
			**kwargs
	) -> Any:
		"""请求-响应模式"""
		pass