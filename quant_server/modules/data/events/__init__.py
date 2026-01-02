"""
数据模块事件定义
负责数据同步、质量检查、因子研究、市场数据处理等相关事件

按照业务功能分类：
1. 同步事件 (sync_events.py): 数据同步相关事件
2. 质量事件 (quality_events.py): 数据质量检查相关事件
3. 研究事件 (research_events.py): 因子研究相关事件
4. 市场事件 (market_events.py): 市场数据更新相关事件

设计原则：
1. 每个事件类对应一个具体的业务动作
2. 事件数据包含完整的上下文信息
3. 支持序列化和反序列化
"""

from .sync_events import (
    DataSyncStartedEvent,
    DataSyncProgressEvent,
    DataSyncCompletedEvent,
    DataSyncFailedEvent
)

from .quality_events import (
    DataQualityCheckStartedEvent,
    DataQualityIssueFoundEvent,
    DataQualityCheckCompletedEvent
)

from .research_events import (
    DataResearchStartedEvent,
    DataResearchProgressEvent,
    DataResearchCompletedEvent
)

from .market_events import (
    MarketDataUpdatedEvent
)

# 导出所有事件类
__all__ = [
    # 同步事件
    "DataSyncStartedEvent",
    "DataSyncProgressEvent",
    "DataSyncCompletedEvent",
    "DataSyncFailedEvent",

    # 质量事件
    "DataQualityCheckStartedEvent",
    "DataQualityIssueFoundEvent",
    "DataQualityCheckCompletedEvent",

    # 研究事件
    "DataResearchStartedEvent",
    "DataResearchProgressEvent",
    "DataResearchCompletedEvent",

    # 市场事件
    "MarketDataUpdatedEvent",
]