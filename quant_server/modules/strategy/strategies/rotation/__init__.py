# -*- coding: utf-8 -*-
"""
轮动策略模块

  GlobalRotationV2AggressiveStrategy  — 双动量激进版，极致集中（6只高弹性，1×100%）
  HighVolMomentumStrategy              — 高波动动量轮动（高波动ETF + 主板个股增强）
"""

from .GlobalRotationV2AggressiveStrategy import GlobalRotationV2AggressiveStrategy
from .high_vol_momentum_strategy import HighVolMomentumStrategy

__all__ = [
    "GlobalRotationV2AggressiveStrategy",
    "HighVolMomentumStrategy",
]
