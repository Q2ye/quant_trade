"""归因分析事件定义"""

from typing import Dict, Any, Optional
from datetime import date

from quant_server.core.events.base import BaseEvent
from .types import AnalysisEventType


class AttributionAnalysisStartedEvent(BaseEvent):
    """归因分析开始事件"""
    def __init__(
        self,
        portfolio_id: str,
        start_date: date,
        end_date: date,
        attribution_model: str,
        source: str = "attribution_service",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=AnalysisEventType.ATTRIBUTION_ANALYSIS_STARTED.value,
            source=source,
            module="analysis",
            data={
                "portfolio_id": portfolio_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "attribution_model": attribution_model
            },
            correlation_id=correlation_id
        )


class AttributionAnalysisCompletedEvent(BaseEvent):
    """归因分析完成事件"""
    def __init__(
        self,
        portfolio_id: str,
        start_date: date,
        end_date: date,
        attribution_model: str,
        result: Dict[str, Any],
        source: str = "attribution_service",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=AnalysisEventType.ATTRIBUTION_ANALYSIS_COMPLETED.value,
            source=source,
            module="analysis",
            data={
                "portfolio_id": portfolio_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "attribution_model": attribution_model,
                "result": result
            },
            correlation_id=correlation_id
        )


class AttributionAnalysisFailedEvent(BaseEvent):
    """归因分析失败事件"""
    def __init__(
        self,
        portfolio_id: str,
        start_date: date,
        end_date: date,
        attribution_model: str,
        error: str,
        source: str = "attribution_service",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=AnalysisEventType.ATTRIBUTION_ANALYSIS_FAILED.value,
            source=source,
            module="analysis",
            data={
                "portfolio_id": portfolio_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "attribution_model": attribution_model,
                "error": error
            },
            correlation_id=correlation_id
        )
