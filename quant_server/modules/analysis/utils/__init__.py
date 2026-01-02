# -*- coding: utf-8 -*-
"""
分析模块工具包
提供分析相关的统计工具和图表工具

包含模块：
1. statistic_utils - 统计分析工具
2. chart_utils - 图表生成工具

位置：quant_server/modules/events/utils/__init__.py
"""

from .statistic_utils import StatisticUtils
from .chart_utils import ChartStyle, ChartUtils

__all__ = [
    'StatisticUtils',
    'ChartStyle',
    'ChartUtils'
]

__version__ = '1.0.0'
__author__ = 'Quant Team'
__description__ = '量化分析工具模块'