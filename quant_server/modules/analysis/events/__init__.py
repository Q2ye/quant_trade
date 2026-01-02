"""
分析模块事件定义
包含绩效分析、归因分析、对比分析、报告生成等事件
"""

from .performance_events import (
    PerformanceCalculatedEvent,
    PerformanceAnalysisStartedEvent,
    PerformanceAnalysisCompletedEvent,
    PerformanceAnalysisFailedEvent,
    PerformanceMetricCalculatedEvent
)

from .attribution_events import (
    AttributionCompletedEvent,
    AttributionAnalysisStartedEvent,
    AttributionAnalysisCompletedEvent,
    AttributionAnalysisFailedEvent,
    BrinsonAttributionCompletedEvent,
    FactorAttributionCompletedEvent
)

from .comparison_events import (
    ComparisonCompletedEvent,
    BenchmarkComparisonCompletedEvent,
    StrategyComparisonCompletedEvent,
    PortfolioComparisonCompletedEvent,
    ComparisonAnalysisStartedEvent,
    ComparisonAnalysisCompletedEvent
)

from .report_events import (
    AnalysisReportGeneratedEvent,
    PerformanceReportGeneratedEvent,
    AttributionReportGeneratedEvent,
    ComparisonReportGeneratedEvent,
    ComprehensiveReportGeneratedEvent,
    ReportGenerationStartedEvent,
    ReportGenerationCompletedEvent
)

from .trade_analysis_events import (
    TradeAnalysisCompletedEvent,
    TradeCostAnalysisCompletedEvent,
    TradeExecutionAnalysisCompletedEvent,
    TradePatternAnalysisCompletedEvent
)

from quant_server.core.events.base import BaseEvent
from quant_server.core.events.types import AnalysisEventType

__all__ = [
    # Base
    "BaseEvent",
    "AnalysisEventType",

    # Performance Events
    "PerformanceCalculatedEvent",
    "PerformanceAnalysisStartedEvent",
    "PerformanceAnalysisCompletedEvent",
    "PerformanceAnalysisFailedEvent",
    "PerformanceMetricCalculatedEvent",

    # Attribution Events
    "AttributionCompletedEvent",
    "AttributionAnalysisStartedEvent",
    "AttributionAnalysisCompletedEvent",
    "AttributionAnalysisFailedEvent",
    "BrinsonAttributionCompletedEvent",
    "FactorAttributionCompletedEvent",

    # Comparison Events
    "ComparisonCompletedEvent",
    "BenchmarkComparisonCompletedEvent",
    "StrategyComparisonCompletedEvent",
    "PortfolioComparisonCompletedEvent",
    "ComparisonAnalysisStartedEvent",
    "ComparisonAnalysisCompletedEvent",

    # Report Events
    "AnalysisReportGeneratedEvent",
    "PerformanceReportGeneratedEvent",
    "AttributionReportGeneratedEvent",
    "ComparisonReportGeneratedEvent",
    "ComprehensiveReportGeneratedEvent",
    "ReportGenerationStartedEvent",
    "ReportGenerationCompletedEvent",

    # Trade Analysis Events
    "TradeAnalysisCompletedEvent",
    "TradeCostAnalysisCompletedEvent",
    "TradeExecutionAnalysisCompletedEvent",
    "TradePatternAnalysisCompletedEvent",
]