"""分析任务生命周期事件（由 AnalysisManager 使用）"""

from typing import Any, Dict

from core.events.base import BaseEvent
from core.events.types import EventPriority, EventCategory
from .types import AnalysisEventType


class AnalysisStartedEvent(BaseEvent):
	"""分析任务启动事件"""

	def __init__ (self, task_id: str, analysis_type: str, user_id: str,
	              parameters: Dict[str, Any]):
		super().__init__(
			event_type=AnalysisEventType.ANALYSIS_TASK_STARTED.value,
			source="analysis.manager",
			module="analysis",
			priority=EventPriority.NORMAL,
			category=EventCategory.BUSINESS,
			data={
				"task_id": task_id,
				"analysis_type": analysis_type,
				"user_id": user_id,
				"parameters": parameters,
			},
		)


class AnalysisProgressEvent(BaseEvent):
	"""分析任务进度事件"""

	def __init__ (self, task_id: str, progress: float, message: str):
		super().__init__(
			event_type=AnalysisEventType.ANALYSIS_TASK_PROGRESS.value,
			source="analysis.manager",
			module="analysis",
			priority=EventPriority.LOW,
			category=EventCategory.BUSINESS,
			data={
				"task_id": task_id,
				"progress": progress,
				"message": message,
			},
		)


class AnalysisCompletedEvent(BaseEvent):
	"""分析任务完成事件"""

	def __init__ (self, task_id: str, analysis_type: str, user_id: str,
	              result: Dict[str, Any]):
		super().__init__(
			event_type=AnalysisEventType.ANALYSIS_TASK_COMPLETED.value,
			source="analysis.manager",
			module="analysis",
			priority=EventPriority.NORMAL,
			category=EventCategory.BUSINESS,
			data={
				"task_id": task_id,
				"analysis_type": analysis_type,
				"user_id": user_id,
				"result": result,
			},
		)


class AnalysisFailedEvent(BaseEvent):
	"""分析任务失败事件"""

	def __init__ (self, task_id: str, analysis_type: str, user_id: str,
	              error_message: str):
		super().__init__(
			event_type=AnalysisEventType.ANALYSIS_TASK_FAILED.value,
			source="analysis.manager",
			module="analysis",
			priority=EventPriority.HIGH,
			category=EventCategory.BUSINESS,
			data={
				"task_id": task_id,
				"analysis_type": analysis_type,
				"user_id": user_id,
				"error_message": error_message,
			},
		)
