"""
异步任务模块

负责回测和优化的异步任务处理

主要组件：
1. BacktestTask：回测任务，处理单个策略的回测
2. OptimizationTask：优化任务，处理策略参数的优化
"""

from .backtest_tasks import BacktestTask
from .optimization_tasks import OptimizationTask

__all__ = [
    "BacktestTask",
    "OptimizationTask"
]