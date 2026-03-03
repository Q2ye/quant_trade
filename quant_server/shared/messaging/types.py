"""
消息中间件类型定义

为消息中间件提供详细的类型注解和类型检查
"""

from typing import Any, Dict, Optional, Union, List, Tuple, TypeAlias, TypeVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

# 类型变量
T = TypeVar('T')
MessageData = Union[str, bytes, Dict[str, Any], List[Any]]
CallbackFunction = TypeVar('CallbackFunction')


class MessageStatus(Enum):
	"""消息状态"""
	PENDING = "pending"
	PROCESSING = "processing"
	COMPLETED = "completed"
	FAILED = "failed"
	RETRY = "retry"


class DeliveryMode(Enum):
	"""消息投递模式"""
	TRANSIENT = 1  # 非持久化
	PERSISTENT = 2  # 持久化


@dataclass
class QueueConfig:
	"""队列配置"""
	name: str
	durable: bool = True
	exclusive: bool = False
	auto_delete: bool = False
	arguments: Optional[Dict[str, Any]] = None


@dataclass
class ExchangeConfig:
	"""交换机配置"""
	name: str
	type: str = "direct"  # direct, topic, fanout, headers
	durable: bool = True
	auto_delete: bool = False
	arguments: Optional[Dict[str, Any]] = None


@dataclass
class BindingConfig:
	"""绑定配置"""
	exchange: str
	queue: str
	routing_key: str = ""
	arguments: Optional[Dict[str, Any]] = None


@dataclass
class ConsumerConfig:
	"""消费者配置"""
	queue_name: str
	consumer_tag: Optional[str] = None
	no_local: bool = False
	no_ack: bool = False
	exclusive: bool = False
	arguments: Optional[Dict[str, Any]] = None


@dataclass
class ProducerConfig:
	"""生产者配置"""
	exchange_name: Optional[str] = None
	routing_key: str = ""
	mandatory: bool = False
	immediate: bool = False
	properties: Optional[Dict[str, Any]] = None


@dataclass
class RetryPolicy:
	"""重试策略"""
	max_retries: int = 3
	retry_delay: float = 1.0  # 秒
	backoff_factor: float = 2.0  # 指数退避因子
	max_delay: float = 60.0  # 最大延迟


@dataclass
class CircuitBreakerConfig:
	"""熔断器配置"""
	failure_threshold: int = 5
	recovery_timeout: float = 30.0  # 秒
	half_open_max_calls: int = 3


@dataclass
class MessageMetrics:
	"""消息指标"""
	total_messages: int = 0
	successful_messages: int = 0
	failed_messages: int = 0
	average_latency: float = 0.0  # 毫秒
	throughput: float = 0.0  # 消息/秒

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			'total_messages': self.total_messages,
			'successful_messages': self.successful_messages,
			'failed_messages': self.failed_messages,
			'success_rate': (
				self.successful_messages / self.total_messages * 100
				if self.total_messages > 0 else 0
			),
			'average_latency': self.average_latency,
			'throughput': self.throughput
		}


@dataclass
class MessageTrace:
	"""消息追踪"""
	message_id: str
	timestamp: datetime = field(default_factory=datetime.now)
	source: Optional[str] = None
	destination: Optional[str] = None
	status: MessageStatus = MessageStatus.PENDING
	error_message: Optional[str] = None
	retry_count: int = 0
	latency: Optional[float] = None  # 毫秒


# 重导出前面文件中定义的类型
from .base import Message, MessageHeaders, MessageMetadata, MessagePriority

__all__ = [
	'Message',
	'MessageHeaders',
	'MessageMetadata',
	'MessagePriority',
	'MessageStatus',
	'DeliveryMode',
	'QueueConfig',
	'ExchangeConfig',
	'BindingConfig',
	'ConsumerConfig',
	'ProducerConfig',
	'RetryPolicy',
	'CircuitBreakerConfig',
	'MessageMetrics',
	'MessageTrace',
]