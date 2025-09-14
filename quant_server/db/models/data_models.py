from sqlalchemy import Column, String, DateTime, Float, Integer, BigInteger, Numeric, Text, ForeignKey, Index, Boolean, \
    UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from quant_server.db.models.base import Base


class StockBasic(Base):
    """股票基础信息表"""
    __tablename__ = 'stock_basic'

    ts_code = Column(String(20), primary_key=True)
    symbol = Column(String(10), nullable=False)
    name = Column(String(50), nullable=False)
    area = Column(String(20))
    industry = Column(String(30))
    fullname = Column(String(100))
    enname = Column(String(100))
    cnspell = Column(String(50))
    market = Column(String(20), nullable=False)
    exchange = Column(String(10))
    curr_type = Column(String(10))
    list_status = Column(String(1), default='L')
    list_date = Column(DateTime, nullable=False)
    delist_date = Column(DateTime)
    is_hs = Column(String(1))
    act_name = Column(String(50))
    act_ent_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    company = relationship("StockCompany", back_populates="stock", uselist=False)
    daily_data = relationship("StockDaily", back_populates="stock")
    moneyflow = relationship("StockMoneyflow", back_populates="stock")
    adj_factors = relationship("StockAdjFactor", back_populates="stock")


class StockCompany(Base):
    """上市公司基本信息表"""
    __tablename__ = 'stock_company'

    ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), primary_key=True)
    com_name = Column(String(100), nullable=False)
    com_id = Column(String(30), nullable=False)
    exchange = Column(String(10), nullable=False)
    chairman = Column(String(50))
    manager = Column(String(50))
    secretary = Column(String(50))
    reg_capital = Column(Numeric(15, 2), nullable=False)
    setup_date = Column(DateTime, nullable=False)
    province = Column(String(20))
    city = Column(String(20))
    introduction = Column(Text)
    website = Column(String(100))
    email = Column(String(100))
    office = Column(String(200))
    employees = Column(Integer)
    main_business = Column(Text)
    business_scope = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic", back_populates="company")
    managers = relationship("StkManager", back_populates="company")


class StkManager(Base):
    """上市公司管理层信息表"""
    __tablename__ = 'stk_managers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), ForeignKey('stock_company.ts_code'))
    ann_date = Column(DateTime, nullable=False)
    name = Column(String(50), nullable=False)
    gender = Column(String(1))
    lev = Column(String(20))
    title = Column(String(100), nullable=False)
    edu = Column(String(20))
    national = Column(String(20))
    birthday = Column(DateTime)
    begin_date = Column(DateTime)
    end_date = Column(DateTime)
    resume = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    company = relationship("StockCompany", back_populates="managers")
    rewards = relationship("StkReward", back_populates="manager")


class StkReward(Base):
    """管理层薪酬与持股明细表"""
    __tablename__ = 'stk_rewards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    manager_id = Column(Integer, ForeignKey('stk_managers.id'))
    ann_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    reward = Column(Numeric(18, 2), nullable=False)
    hold_vol = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    manager = relationship("StkManager", back_populates="rewards")


class StockDaily(Base):
    """A股日线行情表"""
    __tablename__ = 'stock_daily'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    open = Column(Numeric(9, 3), nullable=False)
    high = Column(Numeric(9, 3), nullable=False)
    low = Column(Numeric(9, 3), nullable=False)
    close = Column(Numeric(9, 3), nullable=False)
    pre_close = Column(Numeric(9, 3), nullable=False)
    change = Column(Numeric(9, 3), nullable=False)
    pct_chg = Column(Numeric(7, 4), nullable=False)
    vol = Column(BigInteger, nullable=False)
    amount = Column(Numeric(14, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic", back_populates="daily_data")
    daily_basic = relationship("StockDailyBasic", back_populates="daily", uselist=False)
    daily_limit = relationship("StockDailyLimit", back_populates="daily", uselist=False)
    moneyflow = relationship("StockMoneyflow", back_populates="daily", uselist=False)


class StockMinutes(Base):
    """A股分钟级行情数据"""
    __tablename__ = 'stock_minutes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False)
    freq = Column(String(5), nullable=False)  # 1min/5min/15min/30min/60min
    trade_time = Column(DateTime, nullable=False)
    open = Column(Numeric(9, 4), nullable=False)
    high = Column(Numeric(9, 4), nullable=False)
    low = Column(Numeric(9, 4), nullable=False)
    close = Column(Numeric(9, 4), nullable=False)
    vol = Column(BigInteger, nullable=False)
    amount = Column(Numeric(16, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic")


class StockWeekly(Base):
    """A股周线行情数据表"""
    __tablename__ = 'stock_weekly'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    open = Column(Numeric(9, 4), nullable=False)
    high = Column(Numeric(9, 4), nullable=False)
    low = Column(Numeric(9, 4), nullable=False)
    close = Column(Numeric(9, 4), nullable=False)
    pre_close = Column(Numeric(9, 4), nullable=False)
    change = Column(Numeric(9, 4), nullable=False)
    pct_chg = Column(Numeric(8, 4), nullable=False)
    vol = Column(BigInteger, nullable=False)
    amount = Column(Numeric(16, 4), nullable=False)
    week_start = Column(DateTime)
    week_end = Column(DateTime)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic")


class StockMonthly(Base):
    """A股月线行情数据表"""
    __tablename__ = 'stock_monthly'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    open = Column(Numeric(9, 4), nullable=False)
    high = Column(Numeric(9, 4), nullable=False)
    low = Column(Numeric(9, 4), nullable=False)
    close = Column(Numeric(9, 4), nullable=False)
    pre_close = Column(Numeric(9, 4), nullable=False)
    change = Column(Numeric(9, 4), nullable=False)
    pct_chg = Column(Numeric(8, 4), nullable=False)
    vol = Column(BigInteger, nullable=False)
    amount = Column(Numeric(16, 4), nullable=False)
    month_start = Column(DateTime)
    month_end = Column(DateTime)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic")


class StockAdjustedPrices(Base):
    """A股复权行情数据表"""
    __tablename__ = 'stock_adjusted_prices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    asset_type = Column(String(1), default='E')
    adj_type = Column(String(3))  # qfq/hfq
    freq = Column(String(4), default='D')
    open = Column(Numeric(9, 4), nullable=False)
    high = Column(Numeric(9, 4), nullable=False)
    low = Column(Numeric(9, 4), nullable=False)
    close = Column(Numeric(9, 4), nullable=False)
    pre_close = Column(Numeric(9, 4), nullable=False)
    change = Column(Numeric(9, 4), nullable=False)
    pct_chg = Column(Numeric(8, 4), nullable=False)
    vol = Column(BigInteger, nullable=False)
    amount = Column(Numeric(16, 4), nullable=False)
    ma_values = Column(Text)  # JSON格式
    adj_factor = Column(Numeric(18, 10), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic")


class StockAdjFactor(Base):
    """股票复权因子数据表"""
    __tablename__ = 'stock_adj_factor'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    adj_factor = Column(Numeric(18, 10), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic", back_populates="adj_factors")


class StockDailyBasic(Base):
    """股票每日基本面指标数据表"""
    __tablename__ = 'stock_daily_basic'

    id = Column(Integer, primary_key=True, autoincrement=True)
    daily_id = Column(Integer, ForeignKey('stock_daily.id'))
    ts_code = Column(String(12), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    close = Column(Numeric(9, 4), nullable=False)
    turnover_rate = Column(Numeric(8, 4), nullable=False)
    turnover_rate_f = Column(Numeric(8, 4), nullable=False)
    volume_ratio = Column(Numeric(8, 4), nullable=False)
    pe = Column(Numeric(12, 4))
    pe_ttm = Column(Numeric(12, 4))
    pb = Column(Numeric(12, 4), nullable=False)
    ps = Column(Numeric(12, 4))
    ps_ttm = Column(Numeric(12, 4))
    dv_ratio = Column(Numeric(8, 4))
    dv_ttm = Column(Numeric(8, 4))
    total_share = Column(Numeric(16, 4), nullable=False)
    float_share = Column(Numeric(16, 4), nullable=False)
    free_share = Column(Numeric(16, 4), nullable=False)
    total_mv = Column(Numeric(18, 4), nullable=False)
    circ_mv = Column(Numeric(18, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    daily = relationship("StockDaily", back_populates="daily_basic")


class StockDailyLimit(Base):
    """股票每日涨跌停价格表"""
    __tablename__ = 'stock_daily_limit'

    id = Column(Integer, primary_key=True, autoincrement=True)
    daily_id = Column(Integer, ForeignKey('stock_daily.id'))
    ts_code = Column(String(12), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    pre_close = Column(Numeric(9, 4), nullable=False)
    up_limit = Column(Numeric(9, 4), nullable=False)
    down_limit = Column(Numeric(9, 4), nullable=False)
    up_percent = Column(Numeric(5, 2))
    down_percent = Column(Numeric(5, 2))
    price_range = Column(Numeric(9, 4))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    daily = relationship("StockDaily", back_populates="daily_limit")


class StockMoneyflow(Base):
    """个股资金流向数据表"""
    __tablename__ = 'stock_moneyflow'

    id = Column(Integer, primary_key=True, autoincrement=True)
    daily_id = Column(Integer, ForeignKey('stock_daily.id'))
    ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    buy_sm_vol = Column(Integer, nullable=False)
    buy_sm_amount = Column(Numeric(12, 4), nullable=False)
    sell_sm_vol = Column(Integer, nullable=False)
    sell_sm_amount = Column(Numeric(12, 4), nullable=False)
    buy_md_vol = Column(Integer, nullable=False)
    buy_md_amount = Column(Numeric(12, 4), nullable=False)
    sell_md_vol = Column(Integer, nullable=False)
    sell_md_amount = Column(Numeric(12, 4), nullable=False)
    buy_lg_vol = Column(Integer, nullable=False)
    buy_lg_amount = Column(Numeric(12, 4), nullable=False)
    sell_lg_vol = Column(Integer, nullable=False)
    sell_lg_amount = Column(Numeric(12, 4), nullable=False)
    buy_elg_vol = Column(Integer, nullable=False)
    buy_elg_amount = Column(Numeric(12, 4), nullable=False)
    sell_elg_vol = Column(Integer, nullable=False)
    sell_elg_amount = Column(Numeric(12, 4), nullable=False)
    net_mf_vol = Column(Integer, nullable=False)
    net_mf_amount = Column(Numeric(12, 4), nullable=False)
    total_vol = Column(Integer)
    buy_ratio = Column(Numeric(8, 4))
    large_net_ratio = Column(Numeric(8, 4))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    daily = relationship("StockDaily", back_populates="moneyflow")
    stock = relationship("StockBasic", back_populates="moneyflow")


class TradeCalendar(Base):
    """交易所交易日历表"""
    __tablename__ = 'trade_calendar'

    exchange = Column(String(10), primary_key=True)
    cal_date = Column(DateTime, primary_key=True)
    is_open = Column(Boolean, nullable=False, default=False)
    pretrade_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 索引
    __table_args__ = (
        Index('idx_trade_calendar_cal_date', 'cal_date'),
        Index('idx_trade_calendar_exchange', 'exchange'),
        Index('idx_trade_calendar_is_open', 'is_open'),
        Index('idx_trade_calendar_pretrade', 'pretrade_date'),
    )


class StockSTList(Base):
    """ST股票列表历史记录表"""
    __tablename__ = 'stock_st_list'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False)
    name = Column(String(50), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    st_type = Column(String(10), nullable=False)
    st_type_name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 唯一约束
    __table_args__ = (
        UniqueConstraint('ts_code', 'trade_date', name='uniq_st_stock'),
    )

    # 索引
    Index('idx_stock_st_list_ts_code', 'ts_code')
    Index('idx_stock_st_list_trade_date', 'trade_date')
    Index('idx_stock_st_list_type', 'st_type')



class EtfIndex(Base):
    """ETF基准指数列表信息"""
    __tablename__ = 'etf_index'

    ts_code = Column(String(20), primary_key=True)
    indx_name = Column(String(200), nullable=False)
    indx_csname = Column(String(100), nullable=False)
    pub_party_name = Column(String(200), nullable=False)
    pub_date = Column(String(8), nullable=False)  # 格式: YYYYMMDD
    base_date = Column(String(8), nullable=False)  # 格式: YYYYMMDD
    bp = Column(Float, nullable=False)  # 指数基点
    adj_circle = Column(String(50), nullable=False)  # 调整周期
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系 - 一个指数可以被多个ETF跟踪
    etfs = relationship("EtfBasic", back_populates="index_info")

class EtfBasic(Base):
    """ETF基础信息表"""
    __tablename__ = 'etf_basic'

    ts_code = Column(String(20), primary_key=True)
    csname = Column(String(100), nullable=False)
    extname = Column(String(200), nullable=False)
    cname = Column(String(200), nullable=False)
    index_code = Column(String(20), ForeignKey('etf_index.ts_code'))
    index_name = Column(String(200))
    setup_date = Column(DateTime, nullable=False)
    list_date = Column(DateTime)
    list_status = Column(String(1), nullable=False)
    exchange = Column(String(2), nullable=False)
    mgr_name = Column(String(100), nullable=False)
    custod_name = Column(String(100), nullable=False)
    mgt_fee = Column(Float)
    etf_type = Column(String(10), nullable=False)

    # 关联关系
    daily_data = relationship("EtfDaily", back_populates="etf")
    minute_data = relationship("EtfMinute", back_populates="etf")
    adj_factors = relationship("FundAdjFactor", back_populates="etf")
    index_info = relationship("EtfIndex", back_populates="etfs")


class EtfDaily(Base):
    """ETF日线行情数据"""
    __tablename__ = 'etf_daily'

    ts_code = Column(String(20), ForeignKey('etf_basic.ts_code'), primary_key=True)
    trade_date = Column(DateTime, primary_key=True)
    open = Column(Numeric(10, 4), nullable=False)
    high = Column(Numeric(10, 4), nullable=False)
    low = Column(Numeric(10, 4), nullable=False)
    close = Column(Numeric(10, 4), nullable=False)
    pre_close = Column(Numeric(10, 4), nullable=False)
    change = Column(Numeric(10, 4), nullable=False)
    pct_chg = Column(Numeric(8, 4), nullable=False)
    vol = Column(BigInteger, nullable=False)
    amount = Column(Numeric(16, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))  # 添加创建时间
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))  # 添加更新时间

    # 关联关系
    etf = relationship("EtfBasic", back_populates="daily_data")


class EtfMinute(Base):
    """ETF历史分钟行情数据"""
    __tablename__ = 'etf_minute'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), ForeignKey('etf_basic.ts_code'), nullable=False)
    freq = Column(String(10), nullable=False)  # 1min/5min/15min/30min/60min
    trade_time = Column(DateTime, nullable=False)
    open = Column(Numeric(10, 4), nullable=False)
    close = Column(Numeric(10, 4), nullable=False)
    high = Column(Numeric(10, 4), nullable=False)
    low = Column(Numeric(10, 4), nullable=False)
    vol = Column(BigInteger, nullable=False)
    amount = Column(Numeric(16, 4), nullable=False)

    # 关联关系
    etf = relationship("EtfBasic", back_populates="minute_data")


class FundAdjFactor(Base):
    """基金复权因子数据"""
    __tablename__ = 'fund_adj_factor'

    ts_code = Column(String(20), ForeignKey('etf_basic.ts_code'), primary_key=True)
    trade_date = Column(DateTime, primary_key=True)
    adj_factor = Column(Numeric(16, 8), nullable=False)

    # 关联关系
    etf = relationship("EtfBasic", back_populates="adj_factors")
