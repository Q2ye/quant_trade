"""风险分析事件定义"""

from datetime import date
from typing import Dict, Any, Optional

from core.events.base import BaseEvent
from .types import AnalysisEventType


class RiskAnalysisStartedEvent(BaseEvent):
	"""风险分析开始事件"""

	def __init__ (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date,
			risk_type: str,
			source: str = "risk_service",
			correlation_id: Optional[str] = None
	):
		super().__init__(
			event_type=AnalysisEventType.RISK_ANALYSIS_STARTED.value,
			source=source,
			module="analysis",
			data={
				"strategy_id": strategy_id,
				"start_date": start_date.isoformat(),
				"end_date": end_date.isoformat(),
				"risk_type": risk_type
			},
			correlation_id=correlation_id
		)


class RiskAnalysisCompletedEvent(BaseEvent):
	"""风险分析完成事件"""

	def __init__ (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date,
			risk_type: str,
			result: Dict[str, Any],
			source: str = "risk_service",
			correlation_id: Optional[str] = None
	):
		super().__init__(
			event_type=AnalysisEventType.RISK_ANALYSIS_COMPLETED.value,
			source=source,
			module="analysis",
			data={
				"strategy_id": strategy_id,
				"start_date": start_date.isoformat(),
				"end_date": end_date.isoformat(),
				"risk_type": risk_type,
				"result": result
			},
			correlation_id=correlation_id
		)


class RiskAnalysisFailedEvent(BaseEvent):
	"""风险分析失败事件"""

	def __init__ (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date,
			risk_type: str,
			error: str,
			source: str = "risk_service",
			correlation_id: Optional[str] = None
	):
		super().__init__(
			event_type=AnalysisEventType.RISK_ANALYSIS_FAILED.value,
			source=source,
			module="analysis",
			data={
				"strategy_id": strategy_id,
				"start_date": start_date.isoformat(),
				"end_date": end_date.isoformat(),
				"risk_type": risk_type,
				"error": error
			},
			correlation_id=correlation_id
		)
