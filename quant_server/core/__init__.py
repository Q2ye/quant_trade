# -*- coding: utf-8 -*-
"""
核心基础设施层

稳定层顶层包，提供引擎基类、事件框架、异常体系三大核心能力。
所有模块只能单向依赖 core/，core/ 不可反向依赖 modules/。

包结构：
  engines/     — 引擎框架（EngineBase、EventEngine、MainEngine、类型定义）
  events/      — 事件框架（BaseEvent、系统事件、事件类型枚举）
  exceptions/  — 分层异常体系（业务异常、安全异常、事件异常、验证异常）
"""

from .engines.base import EngineBase
from .engines.system import EventEngine, MainEngine
from .events.base import BaseEvent, EventPriority
from .events.types import EventType, EventCategory
from .events.system_events import SystemStartedEvent, SystemStoppedEvent
from .exceptions.base import QuantBaseException
from .exceptions import (
    BusinessException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    DataNotFoundException,
    ErrorCode,
)

__all__ = [
    # 引擎
    "EngineBase",
    "EventEngine",
    "MainEngine",
    # 事件
    "BaseEvent",
    "EventPriority",
    "EventType",
    "EventCategory",
    "SystemStartedEvent",
    "SystemStoppedEvent",
    # 异常
    "QuantBaseException",
    "BusinessException",
    "ValidationException",
    "AuthenticationException",
    "AuthorizationException",
    "DataNotFoundException",
    "ErrorCode",
]
