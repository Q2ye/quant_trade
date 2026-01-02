# -*- coding: utf-8 -*-
"""
分析模块异步任务包
提供每日分析和报告生成等异步任务

包含模块：
1. daily_analysis_tasks - 每日分析任务
2. report_tasks - 报告生成任务

位置：quant_server/modules/events/tasks/__init__.py
"""

from .daily_analysis_tasks import DailyAnalysisTasks
from .report_tasks import ReportTasks

__all__ = [
    'DailyAnalysisTasks',
    'ReportTasks'
]

__version__ = '1.0.0'
__author__ = 'Quant Team'
__description__ = '量化分析异步任务模块'