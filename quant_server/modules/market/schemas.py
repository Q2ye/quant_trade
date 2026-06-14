# -*- coding: utf-8 -*-
"""Market 模块 Pydantic 响应模型"""
from typing import Optional, List, Any, Dict
from datetime import date, datetime
from pydantic import BaseModel, Field


# =====================================================================
# Dashboard 聚合响应
# =====================================================================

class IndexOverviewItem(BaseModel):
    """指数概览"""
    code: str = ""
    name: str = ""
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None


class IndustryHeatmapItem(BaseModel):
    """行业热力图数据"""
    code: str = ""
    name: str = ""
    pct_chg: Optional[float] = None
    pct_chg_5d: Optional[float] = None
    pct_chg_20d: Optional[float] = None


class MarketBreadth(BaseModel):
    """市场宽度统计"""
    up: int = 0
    down: int = 0
    flat: int = 0
    total: int = 0
    limit_up: int = 0
    limit_down: int = 0


class TopVolumeItem(BaseModel):
    """成交额 TOP 项"""
    ts_code: str = ""
    name: str = ""
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    amount: Optional[float] = None
    industry: Optional[str] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    turnover_rate: Optional[float] = None


class TopMoneyflowItem(BaseModel):
    """资金流向 TOP 项"""
    ts_code: str = ""
    name: str = ""
    net_mf_amount: Optional[float] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    buy_elg_amount: Optional[float] = None
    sell_elg_amount: Optional[float] = None
    buy_lg_amount: Optional[float] = None
    sell_lg_amount: Optional[float] = None


class HsgtFlowItem(BaseModel):
    """沪深港通资金流"""
    trade_date: Any = None
    net_inflow: Optional[float] = None
    sh_inflow: Optional[float] = None
    sz_inflow: Optional[float] = None


class SwHeatmapItem(BaseModel):
    """多窗口行业热力图单行"""
    code: str
    name: str
    pct_1d: Optional[float] = None
    pct_5d: Optional[float] = None
    pct_10d: Optional[float] = None
    pct_20d: Optional[float] = None
    pct_30d: Optional[float] = None
    pct_60d: Optional[float] = None
    amount: Optional[float] = None


class MacroLatestItem(BaseModel):
    """宏观指标最新值"""
    date: Optional[str] = None
    cpi_yoy: Optional[float] = None
    ppi_yoy: Optional[float] = None
    gdp_yoy: Optional[float] = None
    model_config = {"extra": "allow"}


class MacroLatestGroup(BaseModel):
    """宏观最新值汇总"""
    cpi: Optional[dict] = None
    ppi: Optional[dict] = None
    gdp: Optional[dict] = None


class DashboardOverviewResponse(BaseModel):
    """Dashboard 聚合响应"""
    data_date: Optional[str] = None
    indices: List[IndexOverviewItem] = Field(default_factory=list)
    industry_heatmap: List[IndustryHeatmapItem] = Field(default_factory=list)
    market_breadth: MarketBreadth = Field(default_factory=MarketBreadth)
    top_volume: List[TopVolumeItem] = Field(default_factory=list)
    top_moneyflow: List[TopMoneyflowItem] = Field(default_factory=list)
    hsgt_flow: Optional[HsgtFlowItem] = None
    sw_heatmap: List[SwHeatmapItem] = Field(default_factory=list)
    macro_latest: Optional[MacroLatestGroup] = None


# =====================================================================
# StockDetail 全量响应
# =====================================================================

class StockBasicInfo(BaseModel):
    """股票基本信息"""
    ts_code: str = ""
    name: str = ""
    industry: Optional[str] = None
    list_date: Optional[str] = None
    is_st: bool = False
    fullname: Optional[str] = None
    area: Optional[str] = None
    market: Optional[str] = None


class StockLatestQuote(BaseModel):
    """最新行情"""
    trade_date: Optional[str] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None


class StockLatestBasic(BaseModel):
    """最新每日指标"""
    pe: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    circ_mv: Optional[float] = None
    turnover_rate: Optional[float] = None
    volume_ratio: Optional[float] = None


class StockLimitPrice(BaseModel):
    """涨跌停价格"""
    up_limit: Optional[float] = None
    down_limit: Optional[float] = None
    pre_close: Optional[float] = None


class KLineItem(BaseModel):
    """K 线数据"""
    trade_date: str = ""
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    pct_chg: Optional[float] = None


class StockQuotesGroup(BaseModel):
    """多周期 K 线"""
    daily: List[KLineItem] = Field(default_factory=list)
    weekly: List[KLineItem] = Field(default_factory=list)
    monthly: List[KLineItem] = Field(default_factory=list)


class StockMoneyflowItem(BaseModel):
    """个股资金流向"""
    trade_date: Optional[str] = None
    net_mf_amount: Optional[float] = None
    buy_lg_amount: Optional[float] = None
    sell_lg_amount: Optional[float] = None
    buy_elg_amount: Optional[float] = None
    sell_elg_amount: Optional[float] = None
    buy_md_amount: Optional[float] = None
    sell_md_amount: Optional[float] = None
    buy_sm_amount: Optional[float] = None
    sell_sm_amount: Optional[float] = None


class StockFullResponse(BaseModel):
    """StockDetail 全量响应"""
    basic: Optional[StockBasicInfo] = None
    latest_quote: Optional[StockLatestQuote] = None
    latest_basic: Optional[StockLatestBasic] = None
    limit_price: Optional[StockLimitPrice] = None
    quotes: StockQuotesGroup = Field(default_factory=StockQuotesGroup)
    moneyflow: List[StockMoneyflowItem] = Field(default_factory=list)
    financial: Dict[str, Any] = Field(default_factory=dict)
    shareholders: Dict[str, Any] = Field(default_factory=dict)
    factors: Dict[str, Any] = Field(default_factory=dict)
    risk: Dict[str, Any] = Field(default_factory=dict)
