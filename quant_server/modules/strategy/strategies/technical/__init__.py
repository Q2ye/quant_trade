# -*- coding: utf-8 -*-
"""
技术指标策略模块
提供基于技术指标的交易策略
"""

from .ma_cross_strategy import MACrossStrategy
from .macd_strategy import MACDStrategy

__all__ = [
    "MACrossStrategy",
    "MACDStrategy",
]
