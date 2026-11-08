# -*- coding: utf-8 -*-
"""日频数据底座：期权、可转债与北向十大模型（P1）。"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from .base import Base
from .data_models_ext_common import ExtCommonMixin


class OptBasic(ExtCommonMixin, Base):
    __tablename__ = "opt_basic"

    ts_code = Column(String(24), primary_key=True)
    symbol = Column(String(40))
    exchange = Column(String(10))
    name = Column(String(100))
    per_unit = Column(String(20))
    opt_code = Column(String(40))
    opt_type = Column(String(10))
    call_put = Column(String(1))
    exercise_type = Column(String(10))
    exercise_price = Column(Numeric(14, 4))
    opt_multiplier = Column(Numeric(12, 4))
    s_month = Column(String(10))
    maturity_date = Column(Date)
    list_price = Column(Numeric(14, 4))
    list_date = Column(Date)
    delist_date = Column(Date)
    last_edate = Column(Date)
    last_ddate = Column(Date)
    quote_unit = Column(String(20))
    min_price_chg = Column(String(20))


class OptDaily(ExtCommonMixin, Base):
    __tablename__ = "opt_daily"

    ts_code = Column(String(24), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    exchange = Column(String(10))
    pre_settle = Column(Numeric(14, 4))
    pre_close = Column(Numeric(14, 4))
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    close = Column(Numeric(14, 4))
    settle = Column(Numeric(14, 4))
    vol = Column(Numeric(20, 2))
    amount = Column(Numeric(20, 2))
    oi = Column(Numeric(20, 2))


class CbBasic(ExtCommonMixin, Base):
    __tablename__ = "cb_basic"

    ts_code = Column(String(20), primary_key=True)
    bond_full_name = Column(String(120))
    bond_short_name = Column(String(60))
    cb_type = Column(String(10))
    cb_code = Column(String(20))
    stk_code = Column(String(12))
    stk_short_name = Column(String(60))
    maturity = Column(Numeric(8, 4))
    par = Column(Numeric(12, 4))
    issue_price = Column(Numeric(12, 4))
    issue_size = Column(Numeric(20, 4))
    remain_size = Column(Numeric(20, 4))
    value_date = Column(Date)
    maturity_date = Column(Date)
    rate_type = Column(String(20))
    coupon_rate = Column(Numeric(10, 6))
    add_rate = Column(Numeric(10, 6))
    pay_per_year = Column(Integer)
    list_date = Column(Date)
    delist_date = Column(Date)
    exchange = Column(String(10))
    conv_start_date = Column(Date)
    conv_end_date = Column(Date)
    conv_stop_date = Column(Date)
    first_conv_price = Column(Numeric(12, 4))
    conv_price = Column(Numeric(12, 4))
    rate_clause = Column(Text)


class CbIssue(ExtCommonMixin, Base):
    __tablename__ = "cb_issue"

    ts_code = Column(String(20), primary_key=True)
    ann_date = Column(Date)
    res_ann_date = Column(Date)
    plan_issue_size = Column(Numeric(20, 4))
    issue_size = Column(Numeric(20, 4))
    issue_price = Column(Numeric(12, 4))
    issue_type = Column(String(20))
    onl_code = Column(String(20))
    onl_name = Column(String(60))
    onl_date = Column(Date)
    onl_size = Column(Numeric(20, 4))
    onl_pch_vol = Column(Numeric(20, 4))
    onl_pch_num = Column(Integer)
    onl_pch_excess = Column(Numeric(20, 4))
    shd_ration_code = Column(String(20))
    shd_ration_name = Column(String(60))
    shd_ration_date = Column(Date)
    shd_ration_record_date = Column(Date)
    shd_ration_pay_date = Column(Date)
    shd_ration_price = Column(Numeric(12, 4))
    shd_ration_ratio = Column(Numeric(12, 6))
    shd_ration_size = Column(Numeric(20, 4))
    offl_size = Column(Numeric(20, 4))


class CbCall(ExtCommonMixin, Base):
    __tablename__ = "cb_call"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False)
    call_type = Column(String(20), nullable=False)
    is_call = Column(String(20))
    ann_date = Column(Date, nullable=False)
    call_date = Column(Date)
    call_price = Column(Numeric(12, 4))
    call_price_tax = Column(Numeric(12, 4))
    call_vol = Column(Numeric(20, 4))
    call_amount = Column(Numeric(20, 2))
    payment_date = Column(Date)
    call_reg_date = Column(Date)

    __table_args__ = (
        UniqueConstraint("ts_code", "call_type", "ann_date", name="uq_cb_call_key"),
    )


class CbDaily(ExtCommonMixin, Base):
    __tablename__ = "cb_daily"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    pre_close = Column(Numeric(12, 4))
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    change = Column(Numeric(12, 4))
    pct_chg = Column(Numeric(10, 4))
    vol = Column(Numeric(20, 2))
    amount = Column(Numeric(20, 2))


class CbShare(ExtCommonMixin, Base):
    __tablename__ = "cb_share"

    ts_code = Column(String(20), primary_key=True)
    end_date = Column(Date, primary_key=True)
    bond_short_name = Column(String(60))
    publish_date = Column(Date)
    issue_size = Column(Numeric(20, 4))
    convert_price_initial = Column(Numeric(12, 4))
    convert_price = Column(Numeric(12, 4))
    convert_val = Column(Numeric(20, 2))
    convert_vol = Column(Numeric(20, 4))
    convert_ratio = Column(Numeric(12, 6))
    acc_convert_val = Column(Numeric(20, 2))
    acc_convert_vol = Column(Numeric(20, 4))
    acc_convert_ratio = Column(Numeric(12, 6))
    remain_size = Column(Numeric(20, 4))
    total_shares = Column(Numeric(20, 4))


class CbRating(ExtCommonMixin, Base):
    __tablename__ = "cb_rating"

    ts_code = Column(String(20), primary_key=True)
    rating_date = Column(Date, primary_key=True)
    rating_com_name = Column(String(80), primary_key=True)
    ann_date = Column(Date)
    rating_way = Column(String(40))
    rating_type = Column(String(40))
    rating = Column(String(10))
    rating_outlook = Column(String(40))


class StockHsgtTop10(ExtCommonMixin, Base):
    __tablename__ = "stock_hsgt_top10"

    trade_date = Column(Date, primary_key=True)
    ts_code = Column(String(12), primary_key=True)
    name = Column(String(40))
    close = Column(Numeric(12, 4))
    change = Column(Numeric(12, 4))
    rank = Column(Integer)
    market_type = Column(String(8))
    amount = Column(Numeric(20, 2))
    net_amount = Column(Numeric(20, 2))
    buy = Column(Numeric(20, 2))
    sell = Column(Numeric(20, 2))
