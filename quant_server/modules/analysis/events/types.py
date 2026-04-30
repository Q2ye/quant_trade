"""分析模块事件类型定义"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import date, datetime


class AnalysisEventType(str, Enum):
    """分析模块事件类型"""
    # 绩效分析事件
    PERFORMANCE_ANALYSIS_STARTED = "analysis.performance.started"
    PERFORMANCE_ANALYSIS_COMPLETED = "analysis.performance.completed"
    PERFORMANCE_ANALYSIS_FAILED = "analysis.performance.failed"
    
    # 风险分析事件
    RISK_ANALYSIS_STARTED = "analysis.risk.started"
    RISK_ANALYSIS_COMPLETED = "analysis.risk.completed"
    RISK_ANALYSIS_FAILED = "analysis.risk.failed"
    
    # 归因分析事件
    ATTRIBUTION_ANALYSIS_STARTED = "analysis.attribution.started"
    ATTRIBUTION_ANALYSIS_COMPLETED = "analysis.attribution.completed"
    ATTRIBUTION_ANALYSIS_FAILED = "analysis.attribution.failed"
    
    # 对比分析事件
    COMPARISON_ANALYSIS_STARTED = "analysis.comparison.started"
    COMPARISON_ANALYSIS_COMPLETED = "analysis.comparison.completed"
    COMPARISON_ANALYSIS_FAILED = "analysis.comparison.failed"
    
    # 交易分析事件
    TRADE_ANALYSIS_STARTED = "analysis.trade.started"
    TRADE_ANALYSIS_COMPLETED = "analysis.trade.completed"
    TRADE_ANALYSIS_FAILED = "analysis.trade.failed"


class AnalysisEventData:
    """分析事件数据基类"""
    pass


class PerformanceAnalysisEventData(AnalysisEventData):
    """绩效分析事件数据"""
    def __init__(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        analysis_type: str,
        result: Optional[Dict[str, Any]] = None
    ):
        self.strategy_id = strategy_id
        self.start_date = start_date
        self.end_date = end_date
        self.analysis_type = analysis_type
        self.result = result


class RiskAnalysisEventData(AnalysisEventData):
    """风险分析事件数据"""
    def __init__(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        risk_type: str,
        result: Optional[Dict[str, Any]] = None
    ):
        self.strategy_id = strategy_id
        self.start_date = start_date
        self.end_date = end_date
        self.risk_type = risk_type
        self.result = result


class AttributionAnalysisEventData(AnalysisEventData):
    """归因分析事件数据"""
    def __init__(
        self,
        portfolio_id: str,
        start_date: date,
        end_date: date,
        attribution_model: str,
        result: Optional[Dict[str, Any]] = None
    ):
        self.portfolio_id = portfolio_id
        self.start_date = start_date
        self.end_date = end_date
        self.attribution_model = attribution_model
        self.result = result


class ComparisonAnalysisEventData(AnalysisEventData):
    """对比分析事件数据"""
    def __init__(
        self,
        items: List[str],
        start_date: date,
        end_date: date,
        comparison_type: str,
        result: Optional[Dict[str, Any]] = None
    ):
        self.items = items
        self.start_date = start_date
        self.end_date = end_date
        self.comparison_type = comparison_type
        self.result = result


class TradeAnalysisEventData(AnalysisEventData):
    """交易分析事件数据"""
    def __init__(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        analysis_type: str,
        result: Optional[Dict[str, Any]] = None
    ):
        self.strategy_id = strategy_id
        self.start_date = start_date
        self.end_date = end_date
        self.analysis_type = analysis_type
        self.result = result
