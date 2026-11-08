# -*- coding: utf-8 -*-
"""日频数据底座：质押、回购、调研、榜单、游资与财经日历模型（P2）。"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base
from .data_models_ext_common import ExtCommonMixin


class StockPledgeDetail(ExtCommonMixin, Base):
    __tablename__ = "stock_pledge_detail"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), nullable=False)
    ann_date = Column(Date, nullable=False)
    holder_name = Column(String(200), nullable=False, default="")
    pledge_amount = Column(Numeric(20, 4))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    is_release = Column(String(8))
    release_date = Column(Date)
    pledgor = Column(String(200))
    holding_amount = Column(Numeric(20, 4))
    pledged_amount = Column(Numeric(20, 4))
    p_total_ratio = Column(Numeric(12, 6))
    h_total_ratio = Column(Numeric(12, 6))
    is_buyback = Column(String(8))

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "ann_date", "holder_name", "start_date",
            name="uq_pledge_detail_key",
        ),
    )


class StockRepurchase(ExtCommonMixin, Base):
    __tablename__ = "stock_repurchase"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), nullable=False)
    ann_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    proc = Column(String(40), nullable=False, default="")
    exp_date = Column(Date)
    vol = Column(Numeric(20, 4))
    amount = Column(Numeric(20, 2))
    high_limit = Column(Numeric(12, 4))
    low_limit = Column(Numeric(12, 4))

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "ann_date", "end_date", "proc", name="uq_repurchase_key"
        ),
    )


class StockSurv(ExtCommonMixin, Base):
    __tablename__ = "stock_surv"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), nullable=False)
    name = Column(String(40))
    surv_date = Column(Date, nullable=False)
    fund_visitors = Column(Numeric(20, 4))
    rece_place = Column(String(120))
    rece_mode = Column(String(80))
    rece_org = Column(String(200), nullable=False, default="")
    org_type = Column(String(80))
    comp_rece = Column(String(200))

    __table_args__ = (
        UniqueConstraint("ts_code", "surv_date", "rece_org", name="uq_surv_key"),
    )


class StockKplList(ExtCommonMixin, Base):
    __tablename__ = "stock_kpl_list"

    trade_date = Column(Date, primary_key=True)
    ts_code = Column(String(12), primary_key=True)
    tag = Column(String(40), primary_key=True)
    name = Column(String(40))
    lu_time = Column(String(20))
    ld_time = Column(String(20))
    open_time = Column(String(20))
    last_time = Column(String(20))
    lu_desc = Column(String(200))
    theme = Column(String(200))
    net_change = Column(Numeric(20, 2))
    bid_amount = Column(Numeric(20, 2))
    status = Column(String(20))
    bid_change = Column(Numeric(20, 2))
    bid_turnover = Column(Numeric(20, 2))
    lu_bid_vol = Column(Numeric(20, 4))
    pct_chg = Column(Numeric(10, 4))
    bid_pct_chg = Column(Numeric(10, 4))
    rt_pct_chg = Column(Numeric(10, 4))
    limit_order = Column(Numeric(20, 4))
    amount = Column(Numeric(20, 2))
    turnover_rate = Column(Numeric(10, 4))
    free_float = Column(Numeric(20, 4))
    lu_limit_order = Column(Numeric(20, 4))


class StockHmList(ExtCommonMixin, Base):
    __tablename__ = "stock_hm_list"

    name = Column(String(200), primary_key=True)
    description = Column(Text, comment="源字段 desc")
    orgs = Column(JSONB)


class MacroEcoCal(ExtCommonMixin, Base):
    __tablename__ = "macro_eco_cal"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_date = Column(Date, nullable=False)
    event_time = Column(String(20))
    currency = Column(String(8), nullable=False, default="")
    country = Column(String(40))
    event = Column(String(200), nullable=False)
    value = Column(String(40))
    pre_value = Column(String(40))
    fore_value = Column(String(40))

    __table_args__ = (
        UniqueConstraint("event_date", "currency", "event", name="uq_eco_cal_key"),
    )
