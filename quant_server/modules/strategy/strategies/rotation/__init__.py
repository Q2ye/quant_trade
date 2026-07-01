# -*- coding: utf-8 -*-
"""
轮动策略模块
提供 ETF 行业轮动等基于排名调仓的轮动策略
"""

from .etf_rotation_strategy import EtfIndustryRotationStrategy

__all__ = [
    "EtfIndustryRotationStrategy",
]
