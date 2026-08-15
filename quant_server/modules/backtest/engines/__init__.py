"""
回测引擎模块

负责回测执行、交易模拟、参数优化和报告生成

主要组件：
1. BacktestEngine：回测引擎，负责执行回测流程
2. SimulationEngine：模拟引擎，负责模拟交易执行
3. OptimizationEngine：优化引擎，负责策略参数优化
4. ReportEngine：报告引擎，负责生成回测报告
"""

from .backtest_engine import BacktestEngine
from .optimization_engine import OptimizationEngine
from .report_engine import ReportEngine
from .backtest_broker import BacktestBroker, BacktestBrokerConfig

__all__ = [
    "BacktestEngine",
    "OptimizationEngine",
    "ReportEngine",
    "BacktestBroker",
    "BacktestBrokerConfig",
]