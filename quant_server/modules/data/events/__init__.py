"""
数据模块事件定义
负责数据同步、质量检查、因子研究、市场数据处理等相关事件

设计原则：
1. 继承核心事件基类：所有事件都继承自core.events.BaseEvent
2. 业务领域明确：按业务功能分类定义事件
3. 职责清晰：每个事件只关注一个业务动作或状态变化
4. 可序列化：支持JSON序列化用于网络传输

目录结构：
├── types.py                     # 数据模块事件类型枚举
├── sync_events.py               # 数据同步相关事件
├── quality_events.py            # 数据质量检查相关事件
├── research_events.py           # 因子研究相关事件
├── market_events.py             # 市场数据处理相关事件
├── factor_calculation_events.py # 因子计算相关事件
├── handlers_example.py          # 事件处理器示例
└── __init__.py                  # 模块导出
"""

from quant_server.core.events import (
    BaseEvent,
    EventPriority,
    EventCategory,
)

# 导入类型定义
from .types import (
    DataEventType,
    DataEventPriority,
    DataProcessingStatus,
    FactorCalculationStatus,
    get_event_type_descriptions,
)

# 导入具体事件类
from .sync_events import (
    DataSyncStartedEvent,
    DataSyncProgressEvent,
    DataSyncCompletedEvent,
    DataSyncFailedEvent,
)

from .quality_events import (
    DataQualityCheckStartedEvent,
    DataQualityIssueFoundEvent,
    DataQualityCheckCompletedEvent,
)

from .research_events import (
    DataResearchStartedEvent,
    DataResearchProgressEvent,
    DataResearchCompletedEvent,
)

from .market_events import (
    MarketDataMetadata,
    MarketDataRawArrivedEvent,
    MarketDataProcessingEvent,
    MarketDataProcessedEvent,
    MarketDataValidatedEvent,
)

from .factor_calculation_events import (
    FactorMetadata,
    FactorCalculationStartedEvent,
    FactorCalculationProgressEvent,
    FactorCalculationCompletedEvent,
)

# 可选：导入处理器示例
try:
    from .handlers_example import (
        DataSyncEventHandler,
        DataQualityEventHandler,
        MarketDataEventHandler,
    )
    HAS_HANDLERS = True
except ImportError:
    HAS_HANDLERS = False

# 导出所有事件类和类型
__all__ = [
    # 类型定义
    "DataEventType",
    "DataEventPriority",
    "DataProcessingStatus",
    "FactorCalculationStatus",
    "get_event_type_descriptions",

    # 数据模型
    "MarketDataMetadata",
    "FactorMetadata",

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
    "MarketDataRawArrivedEvent",
    "MarketDataProcessingEvent",
    "MarketDataProcessedEvent",
    "MarketDataValidatedEvent",

    # 因子计算事件
    "FactorCalculationStartedEvent",
    "FactorCalculationProgressEvent",
    "FactorCalculationCompletedEvent",
]

# 如果导入了处理器，也导出它们
if HAS_HANDLERS:
    __all__.extend([
        "DataSyncEventHandler",
        "DataQualityEventHandler",
        "MarketDataEventHandler",
    ])

# 事件分类映射（用于文档和工具）
EVENT_CATEGORIES = {
    "sync": [
        "DataSyncStartedEvent",
        "DataSyncProgressEvent",
        "DataSyncCompletedEvent",
        "DataSyncFailedEvent",
    ],
    "quality": [
        "DataQualityCheckStartedEvent",
        "DataQualityIssueFoundEvent",
        "DataQualityCheckCompletedEvent",
    ],
    "research": [
        "DataResearchStartedEvent",
        "DataResearchProgressEvent",
        "DataResearchCompletedEvent",
    ],
    "market": [
        "MarketDataRawArrivedEvent",
        "MarketDataProcessingEvent",
        "MarketDataProcessedEvent",
        "MarketDataValidatedEvent",
    ],
    "factor": [
        "FactorCalculationStartedEvent",
        "FactorCalculationProgressEvent",
        "FactorCalculationCompletedEvent",
    ],
}

# 版本信息
__version__ = "1.0.0"
__description__ = "数据模块事件定义 - 提供数据相关业务事件"