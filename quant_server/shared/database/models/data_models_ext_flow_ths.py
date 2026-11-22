# -*- coding: utf-8 -*-
"""日频数据底座：龙虎榜、筹码、THS、资金流与市场统计模型（P0c）。"""

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


class StockTopList(ExtCommonMixin, Base):
    __tablename__ = "stock_top_list"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    ts_code = Column(String(12), nullable=False)
    name = Column(String(40))
    close = Column(Numeric(12, 4))
    pct_change = Column(Numeric(10, 4))
    turnover_rate = Column(Numeric(10, 4))
    amount = Column(Numeric(20, 2))
    l_sell = Column(Numeric(20, 2))
    l_buy = Column(Numeric(20, 2))
    l_amount = Column(Numeric(20, 2))
    net_amount = Column(Numeric(20, 2))
    net_rate = Column(Numeric(12, 6))
    amount_rate = Column(Numeric(12, 6))
    float_values = Column(Numeric(20, 2))
    reason = Column(String(200), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", "reason", name="uq_top_list_key"),
    )


class StockTopInst(ExtCommonMixin, Base):
    __tablename__ = "stock_top_inst"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    ts_code = Column(String(12), nullable=False)
    exalter = Column(String(200), nullable=False)
    buy = Column(Numeric(20, 2))
    buy_rate = Column(Numeric(12, 6))
    sell = Column(Numeric(20, 2))
    sell_rate = Column(Numeric(12, 6))
    net_buy = Column(Numeric(20, 2))
    side = Column(String(1), nullable=False, default="")
    reason = Column(String(200), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "exalter", "side", "reason",
            name="uq_top_inst_key",
        ),
    )


class StockCyqPerf(ExtCommonMixin, Base):
    __tablename__ = "stock_cyq_perf"

    ts_code = Column(String(12), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    his_low = Column(Numeric(12, 4))
    his_high = Column(Numeric(12, 4))
    cost_5pct = Column(Numeric(12, 4))
    cost_15pct = Column(Numeric(12, 4))
    cost_50pct = Column(Numeric(12, 4))
    cost_85pct = Column(Numeric(12, 4))
    cost_95pct = Column(Numeric(12, 4))
    weight_avg = Column(Numeric(12, 4))
    winner_rate = Column(Numeric(12, 6))


class IndexThs(ExtCommonMixin, Base):
    __tablename__ = "index_ths"

    ts_code = Column(String(20), primary_key=True)
    name = Column(String(80))
    count = Column(Integer)
    exchange = Column(String(8))
    list_date = Column(Date)
    type = Column(String(8))


class IndexThsDaily(ExtCommonMixin, Base):
    __tablename__ = "index_ths_daily"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    # 2026-11-09 放宽：ths_daily 源值 open/high/low/close 可达 1.02e10，
    # pct_change 可达 2.5e7，原 (14,4)/(10,4) 会整批 NumericValueOutOfRange。
    open = Column(Numeric(20, 4))
    high = Column(Numeric(20, 4))
    low = Column(Numeric(20, 4))
    close = Column(Numeric(20, 4))
    pre_close = Column(Numeric(20, 4))
    avg_price = Column(Numeric(20, 4))
    change = Column(Numeric(20, 4))
    pct_change = Column(Numeric(20, 4))
    vol = Column(Numeric(20, 2))
    turnover_rate = Column(Numeric(20, 4))


class IndexThsMember(ExtCommonMixin, Base):
    __tablename__ = "index_ths_member"

    snapshot_date = Column(Date, primary_key=True)
    index_code = Column(String(20), primary_key=True)
    con_code = Column(String(12), primary_key=True)
    con_name = Column(String(40))


class StockMoneyflowExt(ExtCommonMixin, Base):
    __tablename__ = "stock_moneyflow_ext"

    trade_date = Column(Date, primary_key=True)
    ts_code = Column(String(12), primary_key=True)
    source = Column(String(8), primary_key=True)
    name = Column(String(40))
    pct_change = Column(Numeric(10, 4))
    close = Column(Numeric(12, 4))
    latest = Column(Numeric(12, 4))
    net_amount = Column(Numeric(20, 2))
    net_amount_rate = Column(Numeric(12, 6))
    net_d5_amount = Column(Numeric(20, 2))
    buy_elg_amount = Column(Numeric(20, 2))
    buy_elg_amount_rate = Column(Numeric(12, 6))
    buy_lg_amount = Column(Numeric(20, 2))
    buy_lg_amount_rate = Column(Numeric(12, 6))
    buy_md_amount = Column(Numeric(20, 2))
    buy_md_amount_rate = Column(Numeric(12, 6))
    buy_sm_amount = Column(Numeric(20, 2))
    buy_sm_amount_rate = Column(Numeric(12, 6))


class StockMoneyflowInd(ExtCommonMixin, Base):
    __tablename__ = "stock_moneyflow_ind"

    trade_date = Column(Date, primary_key=True)
    ts_code = Column(String(20), primary_key=True)
    source = Column(String(12), primary_key=True)
    content_type = Column(String(20))
    name = Column(String(80))
    industry = Column(String(80))
    lead_stock = Column(String(40))
    close = Column(Numeric(14, 4))
    close_price = Column(Numeric(14, 4))
    pct_change = Column(Numeric(10, 4))
    industry_index = Column(Numeric(14, 4))
    company_num = Column(Integer)
    pct_change_stock = Column(Numeric(10, 4))
    net_buy_amount = Column(Numeric(20, 2))
    net_sell_amount = Column(Numeric(20, 2))
    net_amount = Column(Numeric(20, 2))
    net_amount_rate = Column(Numeric(12, 6))
    buy_elg_amount = Column(Numeric(20, 2))
    buy_elg_amount_rate = Column(Numeric(12, 6))
    buy_lg_amount = Column(Numeric(20, 2))
    buy_lg_amount_rate = Column(Numeric(12, 6))
    buy_md_amount = Column(Numeric(20, 2))
    buy_md_amount_rate = Column(Numeric(12, 6))
    buy_sm_amount = Column(Numeric(20, 2))
    buy_sm_amount_rate = Column(Numeric(12, 6))
    buy_sm_amount_stock = Column(String(200))
    rank = Column(Integer)


class MarketDailyInfo(ExtCommonMixin, Base):
    __tablename__ = "market_daily_info"

    trade_date = Column(Date, primary_key=True)
    ts_code = Column(String(40), primary_key=True)
    source = Column(String(8), primary_key=True)
    ts_name = Column(String(40))
    com_count = Column(Integer)
    total_share = Column(Numeric(20, 4))
    float_share = Column(Numeric(20, 4))
    total_mv = Column(Numeric(20, 2))
    float_mv = Column(Numeric(20, 2))
    amount = Column(Numeric(20, 2))
    vol = Column(Numeric(20, 2))
    trans_count = Column(BigInteger)
    pe = Column(Numeric(12, 4))
    tr = Column(Numeric(12, 6))
    exchange = Column(String(8))
