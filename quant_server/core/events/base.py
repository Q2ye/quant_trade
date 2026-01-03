"""
事件基类定义
提供所有事件的基础结构和通用功能

设计原则：
1. 不可变性：事件一旦创建就不应修改（除了状态字段）
2. 可序列化：支持JSON序列化用于网络传输和持久化
3. 上下文完整：包含事件发生的完整上下文信息
4. 轻量级：避免在事件中存储大量数据
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional, List, TypeVar, Generic
from uuid import uuid4
import json

from .types import EventType, EventPriority, EventStatus, EventCategory


@dataclass
class EventMetadata:
	"""
	事件元数据
	包含事件的通用描述信息
	"""
	event_id: str = field(default_factory=lambda: str(uuid4()))
	event_type: str = ""
	priority: int = EventPriority.NORMAL
	category: str = EventCategory.SYSTEM
	source: str = "unknown"
	module: str = ""
	timestamp: datetime = field(default_factory=datetime.now)
	correlation_id: Optional[str] = None  # 用于跟踪相关事件链
	trace_id: Optional[str] = None  # 分布式追踪ID
	span_id: Optional[str] = None  # 调用链ID

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典，用于序列化"""
		return {
			"event_id": self.event_id,
			"event_type": self.event_type,
			"priority": self.priority,
			"category": self.category,
			"source": self.source,
			"module": self.module,
			"timestamp": self.timestamp.isoformat(),
			"correlation_id": self.correlation_id,
			"trace_id": self.trace_id,
			"span_id": self.span_id,
		}

	@classmethod
	def from_dict (cls, data: Dict[str, Any]) -> "EventMetadata":
		"""从字典创建元数据"""
		return cls(
			event_id=data.get("event_id", str(uuid4())),
			event_type=data.get("event_type", ""),
			priority=data.get("priority", EventPriority.NORMAL),
			category=data.get("category", EventCategory.SYSTEM),
			source=data.get("source", "unknown"),
			module=data.get("module", ""),
			timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
			correlation_id=data.get("correlation_id"),
			trace_id=data.get("trace_id"),
			span_id=data.get("span_id"),
		)


class BaseEvent(ABC):
	"""
	事件基类
	所有具体事件的基类，提供统一接口

	子类实现要求：
	1. 必须实现__init__方法并调用super().__init__
	2. 必须在data属性中存储事件数据
	3. 建议使用@DataClass定义事件数据

	属性说明：
	- metadata: 事件元数据，包含事件的通用描述信息
	- data: 事件具体数据，由子类定义
	- status: 事件状态，用于跟踪事件处理流程
	"""

	def __init__ (
			self,
			event_type: str,
			source: str,
			module: str = "",
			priority: int = EventPriority.NORMAL,
			category: str = EventCategory.BUSINESS,
			data: Optional[Dict[str, Any]] = None,
			correlation_id: Optional[str] = None,
			trace_id: Optional[str] = None,
			span_id: Optional[str] = None,
	):
		"""
		初始化事件

		Args:
			event_type: 事件类型，建议使用模块名.动作.状态格式，如"data.sync.started"
			source: 事件源，标识产生事件的组件
			module: 所属模块，用于分类和过滤
			priority: 事件优先级，影响处理顺序
			category: 事件类别，用于分类处理
			data: 事件数据，包含具体业务信息
			correlation_id: 关联ID，用于跟踪相关事件
			trace_id: 分布式追踪ID
			span_id: 调用链ID
		"""
		self.metadata = EventMetadata(
			event_type=event_type,
			priority=priority,
			category=category,
			source=source,
			module=module,
			correlation_id=correlation_id,
			trace_id=trace_id,
			span_id=span_id,
		)

		# 事件数据，由子类填充
		self.data = data or {}

		# 事件状态
		self.status = EventStatus.CREATED
		self.processed_time: Optional[datetime] = None
		self.error: Optional[str] = None

		# 事件创建时间
		self.created_time = datetime.now()

	@property
	def event_id (self) -> str:
		"""事件ID"""
		return self.metadata.event_id

	@property
	def event_type (self) -> str:
		"""事件类型"""
		return self.metadata.event_type

	@property
	def timestamp (self) -> datetime:
		"""事件时间戳"""
		return self.metadata.timestamp

	def mark_processing (self) -> None:
		"""标记事件开始处理"""
		self.status = EventStatus.PROCESSING

	def mark_processed (self, success: bool = True, error: Optional[str] = None) -> None:
		"""标记事件处理完成"""
		self.status = EventStatus.PROCESSED if success else EventStatus.FAILED
		self.processed_time = datetime.now()
		if error:
			self.error = error

	def to_dict (self) -> Dict[str, Any]:
		"""将事件转换为字典，用于序列化"""
		return {
			"metadata": self.metadata.to_dict(),
			"data": self.data,
			"status": self.status,
			"created_time": self.created_time.isoformat(),
			"processed_time": self.processed_time.isoformat() if self.processed_time else None,
			"error": self.error,
		}

	def to_json (self) -> str:
		"""将事件转换为JSON字符串"""
		return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

	@classmethod
	def from_dict (cls, data: Dict[str, Any]) -> "BaseEvent":
		"""从字典创建事件（基类方法，子类可覆盖）"""
		metadata = EventMetadata.from_dict(data.get("metadata", {}))

		# 创建事件实例
		event = cls(
			event_type=metadata.event_type,
			source=metadata.source,
			module=metadata.module,
			priority=metadata.priority,
			category=metadata.category,
			data=data.get("data", {}),
			correlation_id=metadata.correlation_id,
			trace_id=metadata.trace_id,
			span_id=metadata.span_id,
		)

		# 恢复状态信息
		event.status = data.get("status", EventStatus.CREATED)
		if processed_time := data.get("processed_time"):
			event.processed_time = datetime.fromisoformat(processed_time)
		event.error = data.get("error")

		return event

	@classmethod
	def from_json (cls, json_str: str) -> "BaseEvent":
		"""从JSON字符串创建事件"""
		data = json.loads(json_str)
		return cls.from_dict(data)

	def __str__ (self) -> str:
		"""字符串表示"""
		return f"{self.__class__.__name__}(id={self.event_id}, type={self.event_type}, source={self.metadata.source})"

	def __repr__ (self) -> str:
		"""详细表示"""
		return f"{self.__class__.__name__}(metadata={self.metadata}, data={self.data}, status={self.status})"


class TypedEvent(BaseEvent, Generic[EventType]):
	"""
	类型化事件基类
	提供类型提示支持的事件基类

	示例：
		class MyEvent(TypedEvent[MyEventType]):
			def __init__(self, event_type: MyEventType, **kwargs):
				super().__init__(event_type=event_type.value, **kwargs)
	"""
	pass


# 类型变量，用于类型提示
T = TypeVar("T", bound=BaseEvent)
E = TypeVar("E", bound=BaseEvent)