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
from .technical import (
    MACrossStrategy,
    MACDStrategy,
)
from .rotation import (
    GlobalRotationV2Strategy,
)
from .reference import (
	StockLowHighStrategy,
)
from .etf import (
    LightGBMBottomStrategy,
)

__all__ = [
    # 基类
    "BaseStrategy",
    "TechnicalStrategy",
    "MarketData",
    "BarData",
    "StrategyContext",
    # 技术指标策略
    "MACrossStrategy",
    "MACDStrategy",
    # 轮动策略
    "GlobalRotationV2Strategy",
    # 参考策略移植
    "StockLowHighStrategy",
    # ETF 策略
    "LightGBMBottomStrategy",
]
