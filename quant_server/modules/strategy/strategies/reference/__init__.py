# -*- coding: utf-8 -*-
"""
聚宽参考策略移植模块
提供从聚宽平台迁移的自定义策略

StockLowHighStrategy — 沪深主板强势股低吸轮动（移植自聚宽高抛低吸策略）
"""

from .stock_low_high_strategy import StockLowHighStrategy

__all__ = [
    "StockLowHighStrategy",
]
