"""
回测模块事件定义
负责历史回测、参数优化、绩效验证等相关事件通知

按照业务功能分类：
1. 进度事件 (progress_events.py): 回测执行进度相关事件
2. 结果事件 (result_events.py): 回测结果和报告相关事件
3. 优化事件 (optimization_events.py): 参数优化相关事件

业务场景：
1. 历史数据回测执行过程通知
2. 回测结果分析和报告生成
3. 策略参数优化过程通知
4. 回测任务管理和状态更新

设计原则：
1. 每个事件类对应一个具体的回测业务动作
2. 事件数据包含完整的回测上下文和进度信息
3. 支持大规模回测任务的分布式通知
"""

from .progress_events import (
	BacktestStartedEvent,
	BacktestProgressEvent,
	BacktestCompletedEvent,
	BacktestFailedEvent
)

from .result_events import (
	BacktestReportGeneratedEvent,
	BacktestPerformanceCalculatedEvent,
	BacktestRiskAnalysisCompletedEvent
)

from .optimization_events import (
	BacktestOptimizationStartedEvent,
	BacktestOptimizationProgressEvent,
	BacktestOptimizationCompletedEvent
)

# 导出所有回测事件类
__all__ = [
	# 进度事件
	"BacktestStartedEvent",
	"BacktestProgressEvent",
	"BacktestCompletedEvent",
	"BacktestFailedEvent",

	# 结果事件
	"BacktestReportGeneratedEvent",
	"BacktestPerformanceCalculatedEvent",
	"BacktestRiskAnalysisCompletedEvent",

	# 优化事件
	"BacktestOptimizationStartedEvent",
	"BacktestOptimizationProgressEvent",
	"BacktestOptimizationCompletedEvent",
]