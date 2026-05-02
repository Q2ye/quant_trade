#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块 — 服务层

导出所有分析服务（绩效、归因、对比、交易、集成），供 handlers 和 managers 统一导入。
"""

from .performance_service import PerformanceService
from .attribution_service import AttributionService
from .comparison_service import ComparisonService
from .trade_analysis_service import TradeAnalysisService
from .integration_service import AnalysisIntegrationService

__all__ = [
    'PerformanceService',
    'AttributionService',
    'ComparisonService',
    'TradeAnalysisService',
    'AnalysisIntegrationService'
]