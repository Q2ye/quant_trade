"""
对比分析事件定义
包含基准对比、策略对比、组合对比等相关事件
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.core.events.types import AnalysisEventType


class ComparisonType(Enum):
	"""对比分析类型枚举"""
	BENCHMARK_COMPARISON = "benchmark_comparison"  # 基准对比
	STRATEGY_COMPARISON = "strategy_comparison"  # 策略对比
	PORTFOLIO_COMPARISON = "portfolio_comparison"  # 组合对比
	PERIOD_COMPARISON = "period_comparison"  # 期间对比
	ATTRIBUTION_COMPARISON = "attribution_comparison"  # 归因对比


@dataclass
class ComparisonAnalysisStartedEvent(BaseEvent):
	"""
	对比分析开始事件
	触发时机：对比分析任务开始时
	"""

	def __init__ (self,
	              task_id: str,
	              comparison_type: ComparisonType,
	              comparison_items: List[str],  # 对比项列表
	              comparison_metrics: List[str],  # 对比指标列表
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = f"events.comparison.started"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"comparison_type": comparison_type.value,
			"comparison_items": comparison_items,
			"comparison_metrics": comparison_metrics,
			"start_time": datetime.now().isoformat(),
			"comparison_parameters": kwargs.get("comparison_parameters", {}),
		})


@dataclass
class BenchmarkComparisonCompletedEvent(BaseEvent):
	"""
	基准对比完成事件
	触发时机：与基准的对比分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              strategy_id: str,
	              benchmark_id: str,
	              start_date: datetime,
	              end_date: datetime,
	              excess_return: float,  # 超额收益
	              tracking_error: float,  # 跟踪误差
	              information_ratio: float,  # 信息比率
	              beta: float,  # Beta系数
	              alpha: float,  # Alpha
	              comparison_details: Dict[str, Any],
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = f"events.comparison.benchmark_completed"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"strategy_id": strategy_id,
			"benchmark_id": benchmark_id,
			"start_date": start_date.isoformat(),
			"end_date": end_date.isoformat(),
			"excess_return": excess_return,
			"tracking_error": tracking_error,
			"information_ratio": information_ratio,
			"beta": beta,
			"alpha": alpha,
			"comparison_details": comparison_details,
			"analysis_time": datetime.now().isoformat(),
		})


@dataclass
class StrategyComparisonCompletedEvent(BaseEvent):
	"""
	策略对比完成事件
	触发时机：多个策略之间的对比分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              strategy_ids: List[str],
	              comparison_matrix: Dict[str, Dict[str, float]],  # 策略对比矩阵
	              ranking_results: List[Dict[str, Any]],  # 策略排名结果
	              cluster_analysis: Optional[Dict[str, Any]] = None,
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = f"events.comparison.strategy_completed"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"strategy_ids": strategy_ids,
			"comparison_matrix": comparison_matrix,
			"ranking_results": ranking_results,
			"cluster_analysis": cluster_analysis or {},
			"analysis_time": datetime.now().isoformat(),
		})


@dataclass
class PortfolioComparisonCompletedEvent(BaseEvent):
	"""
	组合对比完成事件
	触发时机：多个投资组合的对比分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              portfolio_ids: List[str],
	              comparison_period: str,  # 对比期间
	              performance_comparison: Dict[str, Any],
	              risk_comparison: Dict[str, Any],
	              correlation_matrix: Dict[str, Dict[str, float]],
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = f"events.comparison.portfolio_completed"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"portfolio_ids": portfolio_ids,
			"comparison_period": comparison_period,
			"performance_comparison": performance_comparison,
			"risk_comparison": risk_comparison,
			"correlation_matrix": correlation_matrix,
			"analysis_time": datetime.now().isoformat(),
		})


@dataclass
class ComparisonCompletedEvent(BaseEvent):
	"""
	对比分析完成事件
	触发时机：对比分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              analysis_id: str,
	              comparison_type: ComparisonType,
	              comparison_summary: Dict[str, Any],
	              detailed_results: Dict[str, Any],
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = AnalysisEventType.COMPARISON_COMPLETED.value
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"analysis_id": analysis_id,
			"comparison_type": comparison_type.value,
			"comparison_summary": comparison_summary,
			"detailed_results": detailed_results,
			"completion_time": datetime.now().isoformat(),
		})


@dataclass
class ComparisonAnalysisCompletedEvent(BaseEvent):
	"""
	对比分析任务完成事件
	触发时机：所有对比分析完成时
	"""

	def __init__ (self,
	              task_id: str,
	              total_comparisons: int,
	              completed_comparisons: int,
	              analysis_duration: float,
	              **kwargs):
		super().__init__(**kwargs)
		self.module = "events"
		self.event_type = "events.comparison.task_completed"
		self.priority = EventPriority.NORMAL

		self.data.update({
			"task_id": task_id,
			"total_comparisons": total_comparisons,
			"completed_comparisons": completed_comparisons,
			"success_rate": completed_comparisons / total_comparisons if total_comparisons > 0 else 0,
			"analysis_duration": analysis_duration,
			"completion_time": datetime.now().isoformat(),
		})