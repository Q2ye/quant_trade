# -*- coding: utf-8 -*-
"""
市场模块常量 — 市场状态、板块分类、交易日历引用
"""
from enum import Enum


class MarketStatus(str, Enum):
    """市场状态枚举"""
    PRE_OPEN = "pre_open"       # 盘前（9:00-9:30）
    OPEN = "open"               # 交易中（9:30-15:00）
    LUNCH_BREAK = "lunch"       # 午休（11:30-13:00）
    CLOSED = "closed"           # 已收盘
    HOLIDAY = "holiday"         # 节假日


class SectorType(str, Enum):
    """板块分类"""
    SW_LEVEL1 = "sw_level1"     # 申万一级行业
    SW_LEVEL2 = "sw_level2"     # 申万二级行业
    CONCEPT = "concept"         # 概念板块
    REGION = "region"           # 地区板块


class MarketIndex(str, Enum):
    """市场指数代码"""
    SHANGHAI = "000001.SH"      # 上证指数
    SHENZHEN = "399001.SZ"      # 深证成指
    GEM = "399006.SZ"           # 创业板指
    CSI300 = "000300.SH"        # 沪深300
    CSI500 = "000905.SH"        # 中证500
    STAR50 = "000688.SH"        # 科创50

# 板块分类常用引用
MAJOR_INDICES = [
    MarketIndex.SHANGHAI,
    MarketIndex.SHENZHEN,
    MarketIndex.GEM,
    MarketIndex.CSI300,
]
