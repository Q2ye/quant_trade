"""
绩效分析器模块

负责回测结果的绩效分析、风险评估和交易分析

主要组件：
1. PerformanceAnalyzer：绩效分析器，计算收益率、夏普比率等指标
2. RiskAnalyzer：风险分析器，计算最大回撤、波动率等指标
3. TradeAnalyzer：交易分析器，分析交易频率、胜率等指标
"""

from .performance_analyzer import PerformanceAnalyzer
from .risk_analyzer import RiskAnalyzer
from .trade_analyzer import TradeAnalyzer

__all__ = [
    "PerformanceAnalyzer",
    "RiskAnalyzer",
    "TradeAnalyzer"
]