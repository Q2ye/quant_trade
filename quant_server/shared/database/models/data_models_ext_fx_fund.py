# -*- coding: utf-8 -*-
"""日频数据底座：外汇与基金模型（P0b 外汇/基金 + P2 基金扩展）。"""

from sqlalchemy import BigInteger, Column, Date, Numeric, String, Text

from .base import Base
from .data_models_ext_common import ExtCommonMixin


class FxBasic(ExtCommonMixin, Base):
    __tablename__ = "fx_basic"

    ts_code = Column(String(20), primary_key=True)
    name = Column(String(80))
    classify = Column(String(40))
    exchange = Column(String(20))
    min_unit = Column(Numeric(18, 6))
    max_unit = Column(Numeric(18, 6))
    pip = Column(Numeric(10, 6))
    pip_cost = Column(Numeric(18, 6))
    target_spread = Column(Numeric(18, 6), comment="源字段 traget_spread")
    min_stop_distance = Column(Numeric(18, 6))
    trading_hours = Column(String(100))
    break_time = Column(String(100))


class FxDaily(ExtCommonMixin, Base):
    __tablename__ = "fx_daily"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True, comment="北京业务日")
    source_date = Column(Date, comment="源 GMT 日期")
    bid_open = Column(Numeric(18, 6))
    bid_close = Column(Numeric(18, 6))
    bid_high = Column(Numeric(18, 6))
    bid_low = Column(Numeric(18, 6))
    ask_open = Column(Numeric(18, 6))
    ask_close = Column(Numeric(18, 6))
    ask_high = Column(Numeric(18, 6))
    ask_low = Column(Numeric(18, 6))
    tick_qty = Column(BigInteger)


class FundNav(ExtCommonMixin, Base):
    __tablename__ = "fund_nav"

    ts_code = Column(String(20), primary_key=True)
    nav_date = Column(Date, primary_key=True)
    ann_date = Column(Date, index=True)
    unit_nav = Column(Numeric(18, 6))
    accum_nav = Column(Numeric(18, 6))
    accum_div = Column(Numeric(18, 6))
    net_asset = Column(Numeric(20, 2))
    adj_nav = Column(Numeric(18, 6))
    update_flag = Column(String(8))


class FundBasic(ExtCommonMixin, Base):
    __tablename__ = "fund_basic"

    ts_code = Column(String(20), primary_key=True)
    name = Column(String(80))
    management = Column(String(80))
    custodian = Column(String(80))
    fund_type = Column(String(40))
    found_date = Column(Date)
    due_date = Column(Date)
    list_date = Column(Date)
    issue_date = Column(Date)
    delist_date = Column(Date)
    issue_amount = Column(Numeric(20, 4))
    m_fee = Column(Numeric(10, 4))
    c_fee = Column(Numeric(10, 4))
    duration_year = Column(Numeric(10, 4))
    p_value = Column(Numeric(12, 4))
    min_amount = Column(Numeric(20, 4))
    exp_return = Column(Numeric(12, 4))
    benchmark = Column(Text)
    status = Column(String(8))
    invest_type = Column(String(40))
    type = Column(String(20))
    trustee = Column(String(80))
    purc_startdate = Column(Date)
    redm_startdate = Column(Date)
    market = Column(String(8))


class FundCompany(ExtCommonMixin, Base):
    __tablename__ = "fund_company"

    name = Column(String(80), primary_key=True)
    shortname = Column(String(80))
    province = Column(String(40))
    city = Column(String(40))
    address = Column(String(200))
    phone = Column(String(80))
    office = Column(String(200))
    website = Column(String(120))
    chairman = Column(String(40))
    manager = Column(String(40))
    reg_capital = Column(Numeric(20, 4))
    setup_date = Column(Date)
    end_date = Column(Date)
    employees = Column(Numeric(10, 0))
    main_business = Column(Text)
    org_code = Column(String(40))
    credit_code = Column(String(40))


class FundManager(ExtCommonMixin, Base):
    __tablename__ = "fund_manager"

    ts_code = Column(String(20), primary_key=True)
    ann_date = Column(Date, primary_key=True)
    name = Column(String(40), primary_key=True)
    begin_date = Column(Date, primary_key=True)
    gender = Column(String(8))
    birth_year = Column(String(8))
    edu = Column(String(40))
    nationality = Column(String(40))
    end_date = Column(Date)
    resume = Column(Text)


class FundDiv(ExtCommonMixin, Base):
    __tablename__ = "fund_div"

    ts_code = Column(String(20), primary_key=True)
    ann_date = Column(Date, primary_key=True)
    div_proc = Column(String(40), primary_key=True)
    imp_anndate = Column(Date)
    base_date = Column(Date)
    record_date = Column(Date)
    ex_date = Column(Date)
    pay_date = Column(Date)
    earpay_date = Column(Date)
    net_ex_date = Column(Date)
    div_cash = Column(Numeric(18, 6))
    base_unit = Column(Numeric(18, 6))
    ear_distr = Column(Numeric(18, 6))
    ear_amount = Column(Numeric(20, 2))
    account_date = Column(Date)
    base_year = Column(String(8))


class FundShare(ExtCommonMixin, Base):
    __tablename__ = "fund_share"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    fd_share = Column(Numeric(20, 4))
    fund_type = Column(String(40))
    market = Column(String(8))


class FundDailyEx(ExtCommonMixin, Base):
    __tablename__ = "fund_daily_ex"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    pre_close = Column(Numeric(12, 4))
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    change = Column(Numeric(12, 4))
    pct_chg = Column(Numeric(10, 4))
    vol = Column(Numeric(20, 4))
    amount = Column(Numeric(20, 2))
