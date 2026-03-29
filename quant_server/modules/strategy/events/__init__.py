# -*- coding: utf-8 -*-
"""
策略模块事件定义
包括生命周期事件、信号事件、管理事件等
"""

from .types import StrategyEventType, SignalEventType
from .lifecycle_events import (
    StrategyStartedEvent,
    StrategyStoppedEvent,
    StrategyPausedEvent,
    StrategyResumedEvent,
)
from .signal_events import (
    StrategySignalEvent,
    SignalExecutedEvent,
    SignalCancelledEvent,
)
from .management_events import (
    StrategyCreatedEvent,
    StrategyStartedEvent as ManagementStrategyStartedEvent,
    StrategyStoppedEvent as ManagementStrategyStoppedEvent,
    StrategySignalEvent as ManagementStrategySignalEvent,
)

# portfolio_events.py 暂未实现
# from .portfolio_events import (
#     PortfolioRebalanceEvent,
#     PositionUpdateEvent,
# )

__all__ = [
    # 事件类型
    "StrategyEventType",
    "SignalEventType",
    # 生命周期事件
    "StrategyStartedEvent",
    "StrategyStoppedEvent",
    "StrategyPausedEvent",
    "StrategyResumedEvent",
    # 信号事件
    "StrategySignalEvent",
    "SignalExecutedEvent",
    "SignalCancelledEvent",
    # 管理事件
    "StrategyCreatedEvent",
    "ManagementStrategyStartedEvent",
    "ManagementStrategyStoppedEvent",
    "ManagementStrategySignalEvent",
    # 组合事件 (暂未实现)
    # "PortfolioRebalanceEvent",
    # "PositionUpdateEvent",
]
