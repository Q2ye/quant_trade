"""
核心事件框架
提供事件系统的基础设施，不包含具体业务事件定义

设计原则：
1. 框架与业务分离：核心框架只提供基础设施，业务事件在各模块定义
2. 松耦合：通过事件驱动实现模块间通信，避免直接依赖
3. 可扩展：支持自定义事件类型和处理器
4. 高性能：异步处理，支持优先级队列

目录结构：
├── base.py          # 事件基类定义
├── engine_events.py # 引擎生命周期事件
├── system_events.py # 系统级事件定义
├── types.py         # 事件类型和优先级枚举
└── __init__.py      # 模块导出
"""

from .base import BaseEvent, EventMetadata
from .engine_events import EngineLifecycleEvent, SystemEvent
from .system_events import (
    SystemStartedEvent,
    SystemStoppedEvent,
    SystemHeartbeatEvent,
    SystemAlertEvent
)
from .types import (
    EventType,
    EventPriority,
    EventStatus,
    EventCategory
)

# 导出公共接口
__all__ = [
    # 基础类
    "BaseEvent",
    "EventMetadata",

    # 统一事件类
    "EngineLifecycleEvent",
    "SystemEvent",

    # 系统事件
    "SystemStartedEvent",
    "SystemStoppedEvent",
    "SystemHeartbeatEvent",
    "SystemAlertEvent",

    # 类型定义
    "EventType",
    "EventPriority",
    "EventStatus",
    "EventCategory",
]

# 版本信息
__version__ = "1.0.0"
__author__ = "QuantServer Team"
__description__ = "核心事件框架 - 提供事件驱动架构的基础设施"
