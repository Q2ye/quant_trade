# -*- coding: utf-8 -*-
"""日频数据底座：港股、美股与港股通模型（P2）。"""

from sqlalchemy import Column, Date, Numeric, String

from .base import Base
from .data_models_ext_common import ExtCommonMixin


class HkBasic(ExtCommonMixin, Base):
    __tablename__ = "hk_basic"

    ts_code = Column(String(20), primary_key=True)
    name = Column(String(80))
    fullname = Column(String(200))
    enname = Column(String(200))
    cn_spell = Column(String(80))
    market = Column(String(20))
    list_status = Column(String(8))
    list_date = Column(Date)
    delist_date = Column(Date)
    trade_unit = Column(Numeric(12, 4))
    isin = Column(String(40))
    curr_type = Column(String(8))


class HkDaily(ExtCommonMixin, Base):
    __tablename__ = "hk_daily"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    close = Column(Numeric(14, 4))
    pre_close = Column(Numeric(14, 4))
    change = Column(Numeric(14, 4))
    pct_chg = Column(Numeric(10, 4))
    vol = Column(Numeric(20, 2))
    amount = Column(Numeric(20, 2))


class UsBasic(ExtCommonMixin, Base):
    __tablename__ = "us_basic"

    ts_code = Column(String(20), primary_key=True)
    name = Column(String(200))
    enname = Column(String(200))
    classify = Column(String(40))
    list_date = Column(Date)
    delist_date = Column(Date)


class UsDaily(ExtCommonMixin, Base):
    __tablename__ = "us_daily"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    close = Column(Numeric(14, 4))
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    pre_close = Column(Numeric(14, 4))
    pct_change = Column(Numeric(10, 4))
    vol = Column(Numeric(20, 2))
    amount = Column(Numeric(20, 2))
    vwap = Column(Numeric(14, 4))


class GgtDaily(ExtCommonMixin, Base):
    __tablename__ = "ggt_daily"

    trade_date = Column(Date, primary_key=True)
    buy_amount = Column(Numeric(20, 2))
    buy_volume = Column(Numeric(20, 4))
    sell_amount = Column(Numeric(20, 2))
    sell_volume = Column(Numeric(20, 4))
