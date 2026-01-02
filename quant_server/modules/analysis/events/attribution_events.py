"""
归因分析事件定义
包含Brinson归因、因子归因、风格归因等相关事件
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.core.events.types import AnalysisEventType


class AttributionMethod(Enum):
	"""归因分析方法枚举"""
	BRINSON_MODEL = "brinson_model"  # Brinson归因模型
	BRINSON_FACHER = "brinson_facher"  # Brinson-Facher归因模型
	FACTOR_ATTRIBUTION = "factor_attribution"  # 因子归因
	RISK_ATTRIBUTION = "risk_attribution"  # 风险归因


@dataclass
class AttributionAnalysisStartedEvent(BaseEvent):
	"""
	归因分析开始事件
	触发时机：归因分析任务开始时
	"""

	def __init__ (self,
	              task_id: str,
	              attribution_method: AttributionMethod,
	              portfolio_id: str,
	              benchmark_id: str,
	              start_date: datetime,
	              end_date: datetime,
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = f"events.attribution.started"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"attribution_method": attribution_method.value,
			"portfolio_id": portfolio_id,
			"benchmark_id": benchmark_id,
			"start_date": start_date.isoformat(),
			"end_date": end_date.isoformat(),
			"analysis_parameters": kwargs.get("analysis_parameters", {}),
		})


@dataclass
class BrinsonAttributionCompletedEvent(BaseEvent):
	"""
	Brinson归因完成事件
	触发时机：Brinson归因分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              portfolio_id: str,
	              benchmark_id: str,
	              allocation_effect: float,  # 资产配置效应
	              selection_effect: float,  # 证券选择效应
	              interaction_effect: float,  # 交互效应
	              total_active_return: float,  # 总主动收益
	              attribution_details: Dict[str, Any],
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = f"events.attribution.brinson_completed"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"portfolio_id": portfolio_id,
			"benchmark_id": benchmark_id,
			"allocation_effect": allocation_effect,
			"selection_effect": selection_effect,
			"interaction_effect": interaction_effect,
			"total_active_return": total_active_return,
			"attribution_details": attribution_details,
			"analysis_time": datetime.now().isoformat(),
		})


@dataclass
class FactorAttributionCompletedEvent(BaseEvent):
	"""
	因子归因完成事件
	触发时机：因子归因分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              portfolio_id: str,
	              factor_model: str,
	              factor_exposures: Dict[str, float],  # 因子暴露度
	              factor_returns: Dict[str, float],  # 因子收益
	              factor_contributions: Dict[str, float],  # 因子贡献
	              specific_return: float,  # 特质收益
	              r_squared: float,  # R²
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = f"events.attribution.factor_completed"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"portfolio_id": portfolio_id,
			"factor_model": factor_model,
			"factor_exposures": factor_exposures,
			"factor_returns": factor_returns,
			"factor_contributions": factor_contributions,
			"specific_return": specific_return,
			"r_squared": r_squared,
			"analysis_time": datetime.now().isoformat(),
		})


@dataclass
class AttributionCompletedEvent(BaseEvent):
	"""
	归因分析完成事件
	触发时机：归因分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              analysis_id: str,
	              attribution_method: AttributionMethod,
	              portfolio_id: str,
	              benchmark_id: str,
	              start_date: datetime,
	              end_date: datetime,
	              attribution_results: Dict[str, Any],
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = AnalysisEventType.ATTRIBUTION_COMPLETED.value
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"analysis_id": analysis_id,
			"attribution_method": attribution_method.value,
			"portfolio_id": portfolio_id,
			"benchmark_id": benchmark_id,
			"start_date": start_date.isoformat(),
			"end_date": end_date.isoformat(),
			"attribution_results": attribution_results,
			"completion_time": datetime.now().isoformat(),
		})


@dataclass
class AttributionAnalysisCompletedEvent(BaseEvent):
	"""
	归因分析任务完成事件
	触发时机：所有归因分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              total_analyses: int,
	              completed_analyses: int,
	              analysis_duration: float,
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = "events.attribution.task_completed"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"total_analyses": total_analyses,
			"completed_analyses": completed_analyses,
			"success_rate": completed_analyses / total_analyses if total_analyses > 0 else 0,
			"analysis_duration": analysis_duration,
			"completion_time": datetime.now().isoformat(),
		})


@dataclass
class AttributionAnalysisFailedEvent(BaseEvent):
	"""
	归因分析失败事件
	触发时机：归因分析失败时
	"""

	def __init__ (self,
	              task_id: str,
	              error_type: str,
	              error_message: str,
	              attribution_method: Optional[str] = None,
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = "events.attribution.failed"
		self.priority = EventPriority.HIGH

		self.data.update({
			"task_id": task_id,
			"error_type": error_type,
			"error_message": error_message,
			"attribution_method": attribution_method,
			"failure_time": datetime.now().isoformat(),
		})