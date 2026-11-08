# -*- coding: utf-8 -*-
"""日频数据底座：两融、改名、新股、指数月线与宏观模型（P0b）。"""

from sqlalchemy import Boolean, Column, Date, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base
from .data_models_ext_common import ExtCommonMixin


class StockMarginDetail(ExtCommonMixin, Base):
    __tablename__ = "stock_margin_detail"

    trade_date = Column(Date, primary_key=True)
    ts_code = Column(String(12), primary_key=True)
    rzye = Column(Numeric(20, 2))
    rqye = Column(Numeric(20, 2))
    rzmre = Column(Numeric(20, 2))
    rqyl = Column(Numeric(20, 2))
    rzche = Column(Numeric(20, 2))
    rqchl = Column(Numeric(20, 2))
    rqmcl = Column(Numeric(20, 2))
    rzrqye = Column(Numeric(20, 2))


class StockMarginSecs(ExtCommonMixin, Base):
    __tablename__ = "stock_margin_secs"

    trade_date = Column(Date, primary_key=True)
    ts_code = Column(String(12), primary_key=True)
    name = Column(String(40))
    exchange = Column(String(10))


class StockNamechange(ExtCommonMixin, Base):
    __tablename__ = "stock_namechange"

    ts_code = Column(String(12), primary_key=True)
    start_date = Column(Date, primary_key=True)
    name = Column(String(40), primary_key=True)
    end_date = Column(Date)
    ann_date = Column(Date, index=True)
    change_reason = Column(String(200))
    is_st = Column(Boolean)


class StockNewShare(ExtCommonMixin, Base):
    __tablename__ = "stock_new_share"

    ts_code = Column(String(12), primary_key=True)
    sub_code = Column(String(20))
    name = Column(String(40))
    ipo_date = Column(Date)
    issue_date = Column(Date)
    amount = Column(Numeric(20, 4))
    market_amount = Column(Numeric(20, 4))
    price = Column(Numeric(12, 4))
    pe = Column(Numeric(12, 4))
    limit_amount = Column(Numeric(20, 4))
    funds = Column(Numeric(20, 2))
    ballot = Column(Numeric(12, 6))


class IndexMonthly(ExtCommonMixin, Base):
    __tablename__ = "index_monthly"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    close = Column(Numeric(14, 4))
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    pre_close = Column(Numeric(14, 4))
    change = Column(Numeric(14, 4))
    pct_chg = Column(Numeric(10, 4))
    vol = Column(Numeric(20, 2))
    amount = Column(Numeric(20, 2))


class MacroRate(ExtCommonMixin, Base):
    __tablename__ = "macro_rate"

    trade_date = Column(Date, primary_key=True)
    source = Column(String(16), primary_key=True)
    currency = Column(String(8), primary_key=True)
    tenor = Column(String(8), primary_key=True)
    value = Column(Numeric(12, 6))


class MacroSf(ExtCommonMixin, Base):
    __tablename__ = "macro_sf"

    month = Column(String(8), primary_key=True)
    inc_month = Column(Numeric(20, 4))
    inc_cumval = Column(Numeric(20, 4))
    stk_endval = Column(Numeric(20, 4))


class MacroMoney(ExtCommonMixin, Base):
    __tablename__ = "macro_money"

    month = Column(String(8), primary_key=True)
    m0 = Column(Numeric(20, 4))
    m0_yoy = Column(Numeric(10, 4))
    m0_mom = Column(Numeric(10, 4))
    m1 = Column(Numeric(20, 4))
    m1_yoy = Column(Numeric(10, 4))
    m1_mom = Column(Numeric(10, 4))
    m2 = Column(Numeric(20, 4))
    m2_yoy = Column(Numeric(10, 4))
    m2_mom = Column(Numeric(10, 4))


class MacroPmi(ExtCommonMixin, Base):
    __tablename__ = "macro_pmi"

    month = Column(String(8), primary_key=True)
    pmi010000 = Column(Numeric(10, 4))
    pmi010100 = Column(Numeric(10, 4))
    pmi010200 = Column(Numeric(10, 4))
    pmi010300 = Column(Numeric(10, 4))
    pmi020100 = Column(Numeric(10, 4))
    pmi030000 = Column(Numeric(10, 4))
    raw = Column(JSONB)
