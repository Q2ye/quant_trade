"""
模拟器模块

负责模拟市场环境、交易成本和滑点

主要组件：
1. MarketSimulator：市场模拟器，模拟市场价格和流动性
2. CostSimulator：成本模拟器，模拟交易成本
3. SlippageSimulator：滑点模拟器，模拟交易滑点
"""

from .cost_simulator import CostSimulator
from .slippage_simulator import SlippageSimulator

__all__ = [
    "CostSimulator",
    "SlippageSimulator"
]