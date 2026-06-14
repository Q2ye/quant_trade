# -*- coding: utf-8 -*-
"""
市场行情 Pydantic Schema
API 请求/响应模型定义
"""
from typing import Optional, List
from pydantic import BaseModel, Field


# ==================== 指数 ====================

class IndexInfoSchema(BaseModel):
    """指数基本信息"""
    code: str
    name: str
    market: Optional[str] = None
    publisher: Optional[str] = None
    category: Optional[str] = None
    baseDate: Optional[str] = Field(default=None, alias="base_date")
    basePoint: Optional[float] = Field(default=None, alias="base_point")

    class Config:
        populate_by_name = True


class IndexDetailSchema(BaseModel):
    """指数详情（含最新行情）— 字段名与 ORM / index_daily 一致"""
    ts_code: str = Field(..., alias="code")
    name: str
    fullname: Optional[str] = None
    market: Optional[str] = None
    publisher: Optional[str] = None
    category: Optional[str] = None
    base_date: Optional[str] = None
    base_point: Optional[float] = None
    list_date: Optional[str] = None
    # 最新行情（index_daily 字段）
    close: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    trade_date: Optional[str] = None
    # 估值指标（index_dailybasic）
    pe: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    # 成分股数
    components_count: Optional[int] = None

    class Config:
        populate_by_name = True


class IndexListResponse(BaseModel):
    indexes: List[IndexInfoSchema]


class IndexDetailResponse(BaseModel):
    index: IndexDetailSchema


# ==================== ETF ====================

class ETFInfoSchema(BaseModel):
    """ETF基本信息"""
    ts_code: str
    name: Optional[str] = None
    shortName: Optional[str] = Field(default=None, alias="short_name")
    exchange: Optional[str] = None
    fundType: Optional[str] = Field(default=None, alias="fund_type")
    indexCode: Optional[str] = Field(default=None, alias="index_code")
    indexName: Optional[str] = Field(default=None, alias="index_name")
    manager: Optional[str] = None
    listDate: Optional[str] = Field(default=None, alias="list_date")
    managementFee: Optional[float] = Field(default=None, alias="management_fee")
    latestPrice: Optional[float] = Field(default=None, alias="latest_price")
    latestChange: Optional[float] = Field(default=None, alias="latest_change")
    latestPctChg: Optional[float] = Field(default=None, alias="latest_pct_chg")
    latestVolume: Optional[float] = Field(default=None, alias="latest_volume")
    latestAmount: Optional[float] = Field(default=None, alias="latest_amount")

    class Config:
        populate_by_name = True


class ETFListResponse(BaseModel):
    etfs: List[ETFInfoSchema]
    total: int = 0
    page: int = 1


class ETFDetailResponse(BaseModel):
    etf: ETFInfoSchema


# ==================== 板块/行业 ====================

class SectorInfoSchema(BaseModel):
    """板块/行业信息"""
    code: str
    name: str
    type: str = "industry"
    stockCount: int = Field(default=0, alias="stock_count")

    class Config:
        populate_by_name = True


class SectorListResponse(BaseModel):
    sectors: List[SectorInfoSchema]


# ==================== K线/历史行情 ====================

class KLineDataSchema(BaseModel):
    """K线数据点"""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    turnoverRate: Optional[float] = Field(default=None, alias="turnover_rate")

    class Config:
        populate_by_name = True


class StockHistoryResponse(BaseModel):
    historical: List[KLineDataSchema]


# ==================== 财务数据 ====================

class FinancialDataSchema(BaseModel):
    """财务数据"""
    symbol: str
    report_date: str
    eps: Optional[float] = None
    bps: Optional[float] = None
    roe: Optional[float] = None
    profit_margin: Optional[float] = None
    debt_to_asset: Optional[float] = None
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    total_assets: Optional[float] = None


class StockFinancialResponse(BaseModel):
    financial: List[FinancialDataSchema]
