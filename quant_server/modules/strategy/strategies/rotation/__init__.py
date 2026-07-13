# -*- coding: utf-8 -*-
"""
轮动策略模块

V1: MultiAssetTrendStrategy — 融合多资产动量+行业轮动，仅需OHLCV（推荐使用）
V2: IndustryRotationStrategy — 申万31行业多因子评分（需PE/PB数据）
V3: MultiAssetRotationStrategy — 多资产ETF动量轮动（移植聚宽）
"""

from .multi_asset_trend_strategy import MultiAssetTrendStrategy

__all__ = [
    "MultiAssetTrendStrategy",
]
