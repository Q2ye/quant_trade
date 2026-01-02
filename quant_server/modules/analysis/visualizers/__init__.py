# -*- coding: utf-8 -*-
"""
可视化器模块
提供图表生成和报告生成功能

包含模块：
1. chart_generator - 图表生成器
2. report_generator - 报告生成器

位置：quant_server/modules/events/visualizers/__init__.py
"""

from .chart_generator import ChartGenerator
from .report_generator import ReportGenerator

__all__ = [
    'ChartGenerator',
    'ReportGenerator'
]

__version__ = '1.0.0'
__author__ = 'Quant Team'
__description__ = '量化可视化模块'