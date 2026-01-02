"""
绩效分析事件定义
包含绩效计算、风险分析、收益分析等相关事件
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.core.events.types import AnalysisEventType


class PerformanceMetricType(Enum):
    """绩效指标类型枚举"""
    RETURN = "return"                     # 收益率指标
    RISK = "risk"                         # 风险指标
    RISK_ADJUSTED = "risk_adjusted"       # 风险调整后收益指标
    DRAWDOWN = "drawdown"                 # 回撤指标
    WIN_RATE = "win_rate"                 # 胜率指标


@dataclass
class PerformanceAnalysisStartedEvent(BaseEvent):
    """
    绩效分析开始事件
    触发时机：绩效分析任务开始时
    """
    def __init__(self,
                 task_id: str,
                 analysis_type: str,
                 strategy_id: Optional[str] = None,
                 portfolio_id: Optional[str] = None,
                 start_date: Optional[datetime] = None,
                 end_date: Optional[datetime] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.module = "events"
        self.event_type = AnalysisEventType.PERFORMANCE_CALCULATED.value
        self.priority = EventPriority.NORMAL

        # 任务信息
        self.data.update({
            "task_id": task_id,
            "analysis_type": analysis_type,
            "strategy_id": strategy_id,
            "portfolio_id": portfolio_id,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "timestamp": datetime.now().isoformat(),
        })


@dataclass
class PerformanceMetricCalculatedEvent(BaseEvent):
    """
    绩效指标计算完成事件
    触发时机：单个绩效指标计算完成时
    """
    def __init__(self,
                 task_id: str,
                 metric_type: PerformanceMetricType,
                 metric_name: str,
                 metric_value: float,
                 metric_data: Dict[str, Any],
                 **kwargs):
        super().__init__(**kwargs)
        self.module = "events"
        self.event_type = f"events.performance.metric_calculated"
        self.priority = EventPriority.LOW

        self.data.update({
            "task_id": task_id,
            "metric_type": metric_type.value,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "metric_data": metric_data,
        })


@dataclass
class PerformanceCalculatedEvent(BaseEvent):
    """
    绩效计算完成事件
    触发时机：完整绩效分析完成时
    """
    def __init__(self,
                 task_id: str,
                 analysis_id: str,
                 strategy_id: Optional[str],
                 portfolio_id: Optional[str],
                 start_date: datetime,
                 end_date: datetime,
                 performance_metrics: Dict[str, Any],
                 benchmark_comparison: Optional[Dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.module = "events"
        self.event_type = AnalysisEventType.PERFORMANCE_CALCULATED.value
        self.priority = EventPriority.NORMAL

        self.data.update({
            "task_id": task_id,
            "analysis_id": analysis_id,
            "strategy_id": strategy_id,
            "portfolio_id": portfolio_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "performance_metrics": performance_metrics,
            "benchmark_comparison": benchmark_comparison or {},
            "calculation_time": datetime.now().isoformat(),
        })


@dataclass
class PerformanceAnalysisCompletedEvent(BaseEvent):
    """
    绩效分析完成事件
    触发时机：所有绩效分析任务完成时
    """
    def __init__(self,
                 task_id: str,
                 analysis_id: str,
                 total_metrics: int,
                 calculated_metrics: int,
                 analysis_duration: float,
                 report_url: Optional[str] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.module = "events"
        self.event_type = "events.performance.completed"
        self.priority = EventPriority.NORMAL

        self.data.update({
            "task_id": task_id,
            "analysis_id": analysis_id,
            "total_metrics": total_metrics,
            "calculated_metrics": calculated_metrics,
            "success_rate": calculated_metrics / total_metrics if total_metrics > 0 else 0,
            "analysis_duration": analysis_duration,
            "report_url": report_url,
            "completion_time": datetime.now().isoformat(),
        })


@dataclass
class PerformanceAnalysisFailedEvent(BaseEvent):
    """
    绩效分析失败事件
    触发时机：绩效分析任务失败时
    """
    def __init__(self,
                 task_id: str,
                 error_type: str,
                 error_message: str,
                 failed_metric: Optional[str] = None,
                 stack_trace: Optional[str] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.module = "events"
        self.event_type = "events.performance.failed"
        self.priority = EventPriority.HIGH

        self.data.update({
            "task_id": task_id,
            "error_type": error_type,
            "error_message": error_message,
            "failed_metric": failed_metric,
            "stack_trace": stack_trace,
            "failure_time": datetime.now().isoformat(),
        })