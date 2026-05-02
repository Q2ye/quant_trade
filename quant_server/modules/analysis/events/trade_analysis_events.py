"""交易分析事件定义"""

from typing import Dict, Any, Optional
from datetime import date

from quant_server.core.events.base import BaseEvent
from .types import AnalysisEventType


class TradeAnalysisStartedEvent(BaseEvent):
    """交易分析开始事件"""
    def __init__(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        analysis_type: str,
        source: str = "trade_analysis_service",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=AnalysisEventType.TRADE_ANALYSIS_STARTED.value,
            source=source,
            module="analysis",
            data={
                "strategy_id": strategy_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "analysis_type": analysis_type
            },
            correlation_id=correlation_id
        )


class TradeAnalysisCompletedEvent(BaseEvent):
    """交易分析完成事件"""
    def __init__(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        analysis_type: str,
        result: Dict[str, Any],
        source: str = "trade_analysis_service",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=AnalysisEventType.TRADE_ANALYSIS_COMPLETED.value,
            source=source,
            module="analysis",
            data={
                "strategy_id": strategy_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "analysis_type": analysis_type,
                "result": result
            },
            correlation_id=correlation_id
        )


class TradeAnalysisFailedEvent(BaseEvent):
    """交易分析失败事件"""
    def __init__(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        analysis_type: str,
        error: str,
        source: str = "trade_analysis_service",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=AnalysisEventType.TRADE_ANALYSIS_FAILED.value,
            source=source,
            module="analysis",
            data={
                "strategy_id": strategy_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "analysis_type": analysis_type,
                "error": error
            },
            correlation_id=correlation_id
        )
