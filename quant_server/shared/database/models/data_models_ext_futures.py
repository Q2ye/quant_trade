# -*- coding: utf-8 -*-
"""日频数据底座：大宗交易、全球指数与期货模型（P1）。"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from .base import Base
from .data_models_ext_common import ExtCommonMixin


class StockBlockTrade(ExtCommonMixin, Base):
    __tablename__ = "stock_block_trade"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    ts_code = Column(String(12), nullable=False)
    price = Column(Numeric(12, 4))
    vol = Column(Numeric(20, 4))
    amount = Column(Numeric(20, 2))
    buyer = Column(String(200), nullable=False, default="")
    seller = Column(String(200), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "price", "vol", "buyer", "seller",
            name="uq_block_trade_key",
        ),
    )


class IndexGlobalDaily(ExtCommonMixin, Base):
    __tablename__ = "index_global_daily"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    close = Column(Numeric(14, 4))
    pre_close = Column(Numeric(14, 4))
    change = Column(Numeric(14, 4))
    pct_chg = Column(Numeric(10, 4))
    swing = Column(Numeric(10, 4))
    vol = Column(Numeric(20, 2))


class FutBasic(ExtCommonMixin, Base):
    __tablename__ = "fut_basic"

    ts_code = Column(String(20), primary_key=True)
    symbol = Column(String(20))
    exchange = Column(String(10))
    name = Column(String(80))
    fut_code = Column(String(20))
    multiplier = Column(Numeric(12, 4))
    trade_unit = Column(String(20))
    per_unit = Column(Numeric(12, 4))
    quote_unit = Column(String(20))
    quote_unit_desc = Column(String(40))
    d_mode_desc = Column(String(80))
    list_date = Column(Date)
    delist_date = Column(Date)
    d_month = Column(String(10))
    last_ddate = Column(Date)


class FutDaily(ExtCommonMixin, Base):
    __tablename__ = "fut_daily"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    pre_close = Column(Numeric(14, 4))
    pre_settle = Column(Numeric(14, 4))
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    close = Column(Numeric(14, 4))
    settle = Column(Numeric(14, 4))
    change1 = Column(Numeric(14, 4))
    change2 = Column(Numeric(14, 4))
    vol = Column(Numeric(20, 2))
    amount = Column(Numeric(20, 2))
    oi = Column(Numeric(20, 2))
    oi_chg = Column(Numeric(20, 2))


class FutHolding(ExtCommonMixin, Base):
    __tablename__ = "fut_holding"

    trade_date = Column(Date, primary_key=True)
    symbol = Column(String(20), primary_key=True)
    broker = Column(String(80), primary_key=True)
    exchange = Column(String(10), primary_key=True, default="")
    vol = Column(Integer)
    vol_chg = Column(Integer)
    long_hld = Column(Integer)
    long_chg = Column(Integer)
    short_hld = Column(Integer)
    short_chg = Column(Integer)


class FutWsr(ExtCommonMixin, Base):
    __tablename__ = "fut_wsr"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    symbol = Column(String(20), nullable=False)
    fut_name = Column(String(80), nullable=False, default="")
    warehouse = Column(String(120), nullable=False, default="")
    pre_vol = Column(Integer)
    vol = Column(Integer)
    vol_chg = Column(Integer)
    unit = Column(String(20), nullable=False, default="")
    exchange = Column(String(10), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "symbol", "warehouse", "fut_name", "unit", "exchange",
            name="uq_fut_wsr_key",
        ),
    )


class FutSettle(ExtCommonMixin, Base):
    __tablename__ = "fut_settle"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    settle = Column(Numeric(14, 4))
    trading_fee_rate = Column(Numeric(12, 6))
    trading_fee = Column(Numeric(14, 4))
    delivery_fee = Column(Numeric(14, 4))
    b_hedging_margin_rate = Column(Numeric(10, 6))
    s_hedging_margin_rate = Column(Numeric(10, 6))
    long_margin_rate = Column(Numeric(10, 6))
    short_margin_rate = Column(Numeric(10, 6))


class FutMapping(ExtCommonMixin, Base):
    __tablename__ = "fut_mapping"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    mapping_ts_code = Column(String(20))


class FutIndexDaily(ExtCommonMixin, Base):
    __tablename__ = "fut_index_daily"

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
