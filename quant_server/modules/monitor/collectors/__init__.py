# -*- coding: utf-8 -*-
"""监控模块数据收集器"""

from modules.monitor.collectors.system_collector import SystemCollector
from modules.monitor.collectors.metric_collector import MetricCollector

__all__ = ["SystemCollector", "MetricCollector"]
