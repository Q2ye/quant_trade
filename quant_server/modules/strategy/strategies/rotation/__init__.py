# -*- coding: utf-8 -*-
"""
轮动策略模块
提供基于申万行业多因子评分的 ETF 行业轮动策略

V1: EtfIndustryRotationStrategy — 基于 ETF 动量排名的轮动（已移除，见 git history）
V2: IndustryRotationStrategy — 基于申万31行业多因子评分的轮动（推荐使用）
V3: MultiAssetRotationStrategy — 基于多资产 ETF 池的动量轮动（移植聚宽参考策略）
"""

from .industry_rotation_strategy import IndustryRotationStrategy
from .multi_asset_rotation_strategy import MultiAssetRotationStrategy

__all__ = [
    "IndustryRotationStrategy",
    "MultiAssetRotationStrategy",
]
