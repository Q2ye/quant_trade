"""对比分析事件定义"""

from datetime import date
from typing import Dict, Any, Optional, List

from quant_server.core.events.base import BaseEvent
from .types import AnalysisEventType


class ComparisonAnalysisStartedEvent(BaseEvent):
	"""对比分析开始事件"""

	def __init__ (
			self,
			items: List[str],
			start_date: date,
			end_date: date,
			comparison_type: str,
			source: str = "comparison_service",
			correlation_id: Optional[str] = None
	):
		super().__init__(
			event_type=AnalysisEventType.COMPARISON_ANALYSIS_STARTED.value,
			source=source,
			module="analysis",
			data={
				"items": items,
				"start_date": start_date.isoformat(),
				"end_date": end_date.isoformat(),
				"comparison_type": comparison_type
			},
			correlation_id=correlation_id
		)


class ComparisonAnalysisCompletedEvent(BaseEvent):
	"""对比分析完成事件"""

	def __init__ (
			self,
			items: List[str],
			start_date: date,
			end_date: date,
			comparison_type: str,
			result: Dict[str, Any],
			source: str = "comparison_service",
			correlation_id: Optional[str] = None
	):
		super().__init__(
			event_type=AnalysisEventType.COMPARISON_ANALYSIS_COMPLETED.value,
			source=source,
			module="analysis",
			data={
				"items": items,
				"start_date": start_date.isoformat(),
				"end_date": end_date.isoformat(),
				"comparison_type": comparison_type,
				"result": result
			},
			correlation_id=correlation_id
		)


class ComparisonAnalysisFailedEvent(BaseEvent):
	"""对比分析失败事件"""

	def __init__ (
			self,
			items: List[str],
			start_date: date,
			end_date: date,
			comparison_type: str,
			error: str,
			source: str = "comparison_service",
			correlation_id: Optional[str] = None
	):
		super().__init__(
			event_type=AnalysisEventType.COMPARISON_ANALYSIS_FAILED.value,
			source=source,
			module="analysis",
			data={
				"items": items,
				"start_date": start_date.isoformat(),
				"end_date": end_date.isoformat(),
				"comparison_type": comparison_type,
				"error": error
			},
			correlation_id=correlation_id
		)
