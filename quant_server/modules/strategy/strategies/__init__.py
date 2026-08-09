# -*- coding: utf-8 -*-
"""
策略实现模块
提供各种具体策略类的导入
"""

from .base import (
    BaseStrategy,
    TechnicalStrategy,
    MarketData,
    BarData,
    StrategyContext,
)
from .etf import (
    LightGBMBottomStrategy,
)
from .reference import (
    StockLowHighStrategy,
)
from .rotation import (
    GlobalRotationV2AggressiveStrategy,
    HighVolMomentumStrategy,
)

__all__ = [
    # 基类
    "BaseStrategy",
    "TechnicalStrategy",
    "MarketData",
    "BarData",
    "StrategyContext",
    # ETF 策略
    "LightGBMBottomStrategy",
    # 参考策略移植
    "StockLowHighStrategy",
    # 轮动策略
    "GlobalRotationV2AggressiveStrategy",
    "HighVolMomentumStrategy",
]
