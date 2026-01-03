"""
数据模块异步任务包

提供数据模块的异步任务实现，包括：
1. 数据同步任务
2. 质量检查任务
3. 研究任务
4. 数据处理任务

设计原则：
1. 任务独立：每个任务独立运行，不依赖其他任务状态
2. 错误恢复：任务失败后可以重试或恢复
3. 进度跟踪：支持任务进度监控
4. 资源管理：合理管理计算资源

任务类型：
- Celery任务：长时间运行的后台任务
- APScheduler任务：定时任务
- 异步函数：即时执行的异步任务
"""

from .sync_tasks import (
	sync_stock_data_task,
	sync_financial_data_task,
	sync_index_data_task,
	sync_macro_data_task,
	schedule_daily_sync
)

from .quality_tasks import (
	check_data_quality_task,
	run_daily_quality_check,
	clean_invalid_data_task,
	validate_data_consistency_task
)

from .research_tasks import (
	calculate_factor_task,
	analyze_factor_performance_task,
	optimize_factor_parameters_task,
	schedule_weekly_research
)

__all__ = [
	# 同步任务
	"sync_stock_data_task",
	"sync_financial_data_task",
	"sync_index_data_task",
	"sync_macro_data_task",
	"schedule_daily_sync",

	# 质量检查任务
	"check_data_quality_task",
	"run_daily_quality_check",
	"clean_invalid_data_task",
	"validate_data_consistency_task",

	# 研究任务
	"calculate_factor_task",
	"analyze_factor_performance_task",
	"optimize_factor_parameters_task",
	"schedule_weekly_research"
]

# 版本信息
__version__ = "1.0.0"
__description__ = "数据模块异步任务包"
__author__ = "QuantServer Team"