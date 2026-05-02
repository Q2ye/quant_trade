# -*- coding: utf-8 -*-
"""分析模块报告事件"""

from quant_server.core.events.base import BaseEvent
from quant_server.core.events.types import EventCategory, EventPriority
from .types import AnalysisEventType


class ReportGenerationStartedEvent(BaseEvent):
    """报告生成开始事件"""

    def __init__(self, report_id: str, report_type: str, strategy_id: str = "",
                 source: str = ""):
        super().__init__(
            event_type=AnalysisEventType.REPORT_GENERATION_STARTED.value,
            source=source or f"report:{report_id}",
            module="analysis",
            category=EventCategory.BUSINESS,
            data={
                "report_id": report_id,
                "report_type": report_type,
                "strategy_id": strategy_id,
            },
        )


class ReportGenerationCompletedEvent(BaseEvent):
    """报告生成完成事件"""

    def __init__(self, report_id: str, report_type: str, file_path: str = "",
                 file_size: int = 0, source: str = ""):
        super().__init__(
            event_type=AnalysisEventType.REPORT_GENERATION_COMPLETED.value,
            source=source or f"report:{report_id}",
            module="analysis",
            category=EventCategory.BUSINESS,
            data={
                "report_id": report_id,
                "report_type": report_type,
                "file_path": file_path,
                "file_size": file_size,
            },
        )


class ReportGenerationFailedEvent(BaseEvent):
    """报告生成失败事件"""

    def __init__(self, report_id: str, report_type: str, error: str,
                 source: str = ""):
        super().__init__(
            event_type=AnalysisEventType.REPORT_GENERATION_FAILED.value,
            source=source or f"report:{report_id}",
            module="analysis",
            category=EventCategory.BUSINESS,
            priority=EventPriority.HIGH,
            data={
                "report_id": report_id,
                "report_type": report_type,
                "error": error,
            },
        )
