#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块
负责绩效评估、归因分析、对比分析、交易分析等功能

模块职责：
1. 绩效分析：计算策略和账户的绩效指标
2. 风险分析：评估策略和投资组合的风险
3. 对比分析：比较多个策略或与基准的对比
4. 归因分析：分析收益来源和贡献度
5. 交易分析：分析交易成本和执行质量

版本: 1.0.0
创建时间: 2025-01-15
作者: 量化平台团队
"""

from .handlers import (
	PerformanceAnalysisHandler,
	RiskAnalysisHandler,
	ComparisonAnalysisHandler,
	AttributionAnalysisHandler,
	TradeAnalysisHandler
)
from .schemas import *
from .models import *
from .constants import *

__all__ = [
	# Handlers
	'PerformanceAnalysisHandler',
	'RiskAnalysisHandler',
	'ComparisonAnalysisHandler',
	'AttributionAnalysisHandler',
	'TradeAnalysisHandler',

	# Schemas
	'PerformanceReportResponse',
	'RiskMetricsResponse',
	'StrategyComparisonResponse',
	'AttributionAnalysisResponse',
	'ExportReportResponse',

	# Models
	'PerformanceReport',
	'RiskMetrics',
	'StrategyComparison',
	'AttributionAnalysis',

	# Constants
	'AnalysisModuleConstants',
	'PERFORMANCE_METRICS',
	'RISK_METRICS',
	'ATTRIBUTION_METRICS'
]

__version__ = '1.0.0'
__author__ = '量化平台团队'
__description__ = '量化交易平台分析模块'