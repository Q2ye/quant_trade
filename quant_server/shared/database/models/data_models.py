"""
data_models.py
数据相关表模型定义（股票、行情、财务、因子等）
位置：shared/database/models/data_models.py
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Date, DateTime, Float, Integer, BigInteger, Numeric, Text, ForeignKey, Index, Boolean, \
	UniqueConstraint, PrimaryKeyConstraint, JSON
from sqlalchemy.orm import relationship

from .base import Base


# ==================== 股票基本信息 ====================

class StockBasic(Base):
	"""股票基础信息表"""
	__tablename__ = 'stock_basic'

	ts_code = Column(String(20), primary_key=True, comment='TS代码')
	symbol = Column(String(10), nullable=False, index=True, comment='股票代码')
	name = Column(String(50), nullable=False, comment='股票名称')
	area = Column(String(20), comment='地域')
	industry = Column(String(30), comment='所属行业')
	fullname = Column(String(100), comment='股票全称')
	enname = Column(String(100), comment='英文全称')
	cnspell = Column(String(50), comment='拼音缩写')
	market = Column(String(20), nullable=False, comment='市场类型')
	exchange = Column(String(10), comment='交易所代码')
	curr_type = Column(String(10), comment='交易货币')
	list_status = Column(String(1), default='L', comment='上市状态：L-上市，D-退市，P-暂停上市')
	list_date = Column(DateTime, nullable=False, comment='上市日期')
	delist_date = Column(DateTime, comment='退市日期')
	is_hs = Column(String(1), comment='是否沪深港通：H-沪股通，S-深股通，N-否')
	act_name = Column(String(50), comment='实控人名称')
	act_ent_type = Column(String(50), comment='实控人企业性质')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	company = relationship("StockCompany", back_populates="stock", uselist=False, cascade="all, delete-orphan")
	daily_data = relationship("StockDaily", back_populates="stock", cascade="all, delete-orphan")
	moneyflow = relationship("StockMoneyflow", back_populates="stock", cascade="all, delete-orphan")
	adj_factors = relationship("StockAdjFactor", back_populates="stock", cascade="all, delete-orphan")
	financial_income = relationship("FinancialIncome", back_populates="stock", cascade="all, delete-orphan")
	financial_balance = relationship("FinancialBalance", back_populates="stock", cascade="all, delete-orphan")
	financial_cashflow = relationship("FinancialCashflow", back_populates="stock", cascade="all, delete-orphan")
	minutes_data = relationship("StockMinutes", back_populates="stock", cascade="all, delete-orphan")
	announcements = relationship("CompanyAnnouncement", back_populates="stock", cascade="all, delete-orphan")
	weekly_data = relationship("StockWeekly", back_populates="stock", cascade="all, delete-orphan")
	monthly_data = relationship("StockMonthly", back_populates="stock", cascade="all, delete-orphan")
	adjusted_prices = relationship("StockAdjustedPrices", back_populates="stock", cascade="all, delete-orphan")


class StockCompany(Base):
	"""上市公司基本信息表"""
	__tablename__ = 'stock_company'

	ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), primary_key=True, comment='TS代码')
	com_name = Column(String(100), nullable=False, comment='公司名称')
	com_id = Column(String(30), nullable=False, comment='公司ID')
	exchange = Column(String(10), nullable=False, comment='交易所')
	chairman = Column(String(50), comment='法人代表')
	manager = Column(String(50), comment='总经理')
	secretary = Column(String(50), comment='董事会秘书')
	reg_capital = Column(Numeric(15, 2), nullable=False, comment='注册资本')
	setup_date = Column(DateTime, nullable=False, comment='成立日期')
	province = Column(String(20), comment='所在省份')
	city = Column(String(20), comment='所在城市')
	introduction = Column(Text, comment='公司介绍')
	website = Column(String(100), comment='公司主页')
	email = Column(String(100), comment='电子邮件')
	office = Column(String(200), comment='办公室')
	employees = Column(Integer, comment='员工人数')
	main_business = Column(Text, comment='主营业务')
	business_scope = Column(Text, comment='经营范围')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="company")
	managers = relationship("StkManager", back_populates="company", cascade="all, delete-orphan")


class StkManager(Base):
	"""上市公司管理层信息表"""
	__tablename__ = 'stk_managers'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='管理层ID')
	ts_code = Column(String(20), ForeignKey('stock_company.ts_code'), index=True, comment='TS代码')
	ann_date = Column(DateTime, comment='公告日期（可能为空）')
	name = Column(String(50), nullable=False, comment='姓名')
	gender = Column(String(1), comment='性别：M-男，F-女')
	lev = Column(String(20), comment='职位类别')
	title = Column(String(100), comment='职位（可能为空）')
	edu = Column(String(20), comment='学历')
	national = Column(String(20), comment='国籍')
	birthday = Column(String(10), comment='出生日期（格式不统一 YYYY/YYYYMM/YYYYMMDD）')
	begin_date = Column(String(10), comment='任职开始日期（格式不统一 YYYY/YYYYMM/YYYYMMDD）')
	end_date = Column(String(10), comment='任职结束日期（格式不统一）')
	resume = Column(Text, comment='个人简历')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'name', 'title', name='uq_stk_managers_unique'),
	)

	# 关联关系
	company = relationship("StockCompany", back_populates="managers")


class StkReward(Base):
	"""管理层薪酬与持股明细表"""
	__tablename__ = 'stk_rewards'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='薪酬ID')
	ts_code = Column(String(20), ForeignKey('stock_company.ts_code'), nullable=False, index=True,
                 comment='TS股票代码')
	ann_date = Column(DateTime, comment='公告日期（可能为空）')
	end_date = Column(DateTime, comment='截止日期（可能为空）')
	name = Column(String(50), nullable=False, comment='高层姓名')
	title = Column(String(100), comment='担任职务（可能为空）')
	reward = Column(Numeric(18, 2), comment='报酬（Tushare不保证返回）')
	hold_vol = Column(BigInteger, comment='持股数（Tushare不保证返回）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'end_date', 'name', 'title', name='uq_stk_rewards_unique'),
	)


# ==================== 行情数据 ====================

class StockDaily(Base):
	"""A股日线行情表"""
	__tablename__ = 'stock_daily'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='日线数据ID')
	ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	open = Column(Numeric(9, 3), nullable=False, comment='开盘价')
	high = Column(Numeric(9, 3), nullable=False, comment='最高价')
	low = Column(Numeric(9, 3), nullable=False, comment='最低价')
	close = Column(Numeric(9, 3), nullable=False, comment='收盘价')
	pre_close = Column(Numeric(9, 3), nullable=False, comment='昨收价')
	change = Column(Numeric(10, 3), nullable=False, comment='涨跌额')
	pct_chg = Column(Numeric(10, 4), nullable=False, comment='涨跌幅（百分比）')
	vol = Column(BigInteger, nullable=False, comment='成交量（手）')
	amount = Column(Numeric(16, 4), nullable=False, comment='成交额（千元）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="daily_data")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_daily_code_date'),
		Index('idx_stock_daily_trade_date', 'trade_date'),
	)


class StockMinutes(Base):
	"""A股分钟级行情数据"""
	__tablename__ = 'stock_minutes'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='分钟数据ID')
	ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	freq = Column(String(5), nullable=False, comment='频率：1min/5min/15min/30min/60min')
	trade_time = Column(DateTime, nullable=False, index=True, comment='交易时间')
	open = Column(Numeric(9, 4), nullable=False, comment='开盘价')
	high = Column(Numeric(9, 4), nullable=False, comment='最高价')
	low = Column(Numeric(9, 4), nullable=False, comment='最低价')
	close = Column(Numeric(9, 4), nullable=False, comment='收盘价')
	vol = Column(BigInteger, nullable=False, comment='成交量')
	amount = Column(Numeric(18, 2), nullable=False, comment='成交额')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="minutes_data")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'freq', 'trade_time', name='uq_stock_minutes_code_freq_time'),
		Index('idx_stock_minutes_ts_code_time', 'ts_code', 'trade_time'),
	)


class StockWeekly(Base):
	"""A股周线行情数据表"""
	__tablename__ = 'stock_weekly'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='周线数据ID')
	ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	open = Column(Numeric(9, 4), nullable=False, comment='开盘价')
	high = Column(Numeric(9, 4), nullable=False, comment='最高价')
	low = Column(Numeric(9, 4), nullable=False, comment='最低价')
	close = Column(Numeric(9, 4), nullable=False, comment='收盘价')
	pre_close = Column(Numeric(9, 4), nullable=False, comment='上周收盘价')
	change = Column(Numeric(9, 4), nullable=False, comment='涨跌额')
	pct_chg = Column(Numeric(8, 4), nullable=False, comment='涨跌幅')
	vol = Column(BigInteger, nullable=False, comment='成交量')
	amount = Column(Numeric(18, 2), nullable=False, comment='成交额')
	week_start = Column(DateTime, comment='周开始日期')
	week_end = Column(DateTime, comment='周结束日期')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="weekly_data")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_weekly_code_date'),
	)


class StockMonthly(Base):
	"""A股月线行情数据表"""
	__tablename__ = 'stock_monthly'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='月线数据ID')
	ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	open = Column(Numeric(9, 4), nullable=False, comment='开盘价')
	high = Column(Numeric(9, 4), nullable=False, comment='最高价')
	low = Column(Numeric(9, 4), nullable=False, comment='最低价')
	close = Column(Numeric(9, 4), nullable=False, comment='收盘价')
	pre_close = Column(Numeric(9, 4), nullable=False, comment='上月收盘价')
	change = Column(Numeric(9, 4), nullable=False, comment='涨跌额')
	pct_chg = Column(Numeric(8, 4), nullable=False, comment='涨跌幅')
	vol = Column(BigInteger, nullable=False, comment='成交量')
	amount = Column(Numeric(18, 2), nullable=False, comment='成交额')
	month_start = Column(DateTime, comment='月开始日期')
	month_end = Column(DateTime, comment='月结束日期')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="monthly_data")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_monthly_code_date'),
	)


class StockAdjustedPrices(Base):
	"""A股复权行情数据表"""
	__tablename__ = 'stock_adjusted_prices'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='复权数据ID')
	ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	asset_type = Column(String(1), default='E', comment='资产类型：E-股票，F-基金，I-指数')
	adj_type = Column(String(3), comment='复权类型：qfq-前复权，hfq-后复权')
	freq = Column(String(4), default='D', comment='频率：D-日，W-周，M-月')
	open = Column(Numeric(9, 4), nullable=False, comment='开盘价')
	high = Column(Numeric(9, 4), nullable=False, comment='最高价')
	low = Column(Numeric(9, 4), nullable=False, comment='最低价')
	close = Column(Numeric(9, 4), nullable=False, comment='收盘价')
	pre_close = Column(Numeric(9, 4), nullable=False, comment='前收盘价')
	change = Column(Numeric(9, 4), nullable=False, comment='涨跌额')
	pct_chg = Column(Numeric(8, 4), nullable=False, comment='涨跌幅')
	vol = Column(BigInteger, nullable=False, comment='成交量')
	amount = Column(Numeric(18, 2), nullable=False, comment='成交额')
	ma_values = Column(Text, comment='移动平均线值（JSON格式）')
	adj_factor = Column(Numeric(18, 10), nullable=False, comment='复权因子')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="adjusted_prices")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', 'adj_type', name='uq_stock_adj_prices_code_date_type'),
	)


class StockAdjFactor(Base):
	"""股票复权因子数据表"""
	__tablename__ = 'stock_adj_factor'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='复权因子ID')
	ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	adj_factor = Column(Numeric(18, 10), nullable=False, comment='复权因子')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="adj_factors")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_adj_factor_code_date'),
	)


# ==================== 基本面数据 ====================

class StockDailyBasic(Base):
	"""股票每日基本面指标数据表"""
	__tablename__ = 'stock_daily_basic'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='基本面数据ID')
	ts_code = Column(String(12), index=True, comment='TS代码')
	trade_date = Column(DateTime, index=True, comment='交易日期')
	close = Column(Numeric(9, 4), comment='收盘价')
	turnover_rate = Column(Numeric(8, 4), comment='换手率（%）')
	turnover_rate_f = Column(Numeric(8, 4), comment='流通股换手率（%）')
	volume_ratio = Column(Numeric(8, 4), comment='量比')
	pe = Column(Numeric(12, 4), comment='市盈率（总市值/净利润）')
	pe_ttm = Column(Numeric(12, 4), comment='市盈率（TTM）')
	pb = Column(Numeric(12, 4), comment='市净率（总市值/净资产）')
	ps = Column(Numeric(12, 4), comment='市销率')
	ps_ttm = Column(Numeric(12, 4), comment='市销率（TTM）')
	dv_ratio = Column(Numeric(8, 4), comment='股息率（%）')
	dv_ttm = Column(Numeric(8, 4), comment='股息率（TTM）')
	total_share = Column(Numeric(16, 4), comment='总股本（万股）')
	float_share = Column(Numeric(16, 4), comment='流通股本（万股）')
	free_share = Column(Numeric(16, 4), comment='自由流通股本（万股）')
	total_mv = Column(Numeric(18, 4), comment='总市值（万元）')
	circ_mv = Column(Numeric(18, 4), comment='流通市值（万元）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_daily_basic_code_date'),
	)


class StockDailyLimit(Base):
	"""股票每日涨跌停价格表"""
	__tablename__ = 'stock_daily_limit'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='涨跌停数据ID')
	ts_code = Column(String(12), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	pre_close = Column(Numeric(9, 4), comment='前收盘价（Tushare不保证返回）')
	up_limit = Column(Numeric(9, 4), nullable=False, comment='涨停价')
	down_limit = Column(Numeric(9, 4), nullable=False, comment='跌停价')
	up_percent = Column(Numeric(5, 2), comment='涨停幅度（%）')
	down_percent = Column(Numeric(5, 2), comment='跌停幅度（%）')
	price_range = Column(Numeric(9, 4), comment='价格区间')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_daily_limit_code_date'),
	)


class StockMoneyflow(Base):
	"""个股资金流向数据表"""
	__tablename__ = 'stock_moneyflow'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='资金流向ID')
	ts_code = Column(String(12), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	buy_sm_vol = Column(Integer, comment='小单买入量（手）')
	buy_sm_amount = Column(Numeric(12, 4), comment='小单买入金额（万元）')
	sell_sm_vol = Column(Integer, comment='小单卖出量（手）')
	sell_sm_amount = Column(Numeric(12, 4), comment='小单卖出金额（万元）')
	buy_md_vol = Column(Integer, comment='中单买入量（手）')
	buy_md_amount = Column(Numeric(12, 4), comment='中单买入金额（万元）')
	sell_md_vol = Column(Integer, comment='中单卖出量（手）')
	sell_md_amount = Column(Numeric(12, 4), comment='中单卖出金额（万元）')
	buy_lg_vol = Column(Integer, comment='大单买入量（手）')
	buy_lg_amount = Column(Numeric(12, 4), comment='大单买入金额（万元）')
	sell_lg_vol = Column(Integer, comment='大单卖出量（手）')
	sell_lg_amount = Column(Numeric(12, 4), comment='大单卖出金额（万元）')
	buy_elg_vol = Column(Integer, comment='特大单买入量（手）')
	buy_elg_amount = Column(Numeric(12, 4), comment='特大单买入金额（万元）')
	sell_elg_vol = Column(Integer, comment='特大单卖出量（手）')
	sell_elg_amount = Column(Numeric(12, 4), comment='特大单卖出金额（万元）')
	net_mf_vol = Column(Integer, comment='净流入量（手）')
	net_mf_amount = Column(Numeric(12, 4), comment='净流入金额（万元）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="moneyflow")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_moneyflow_code_date'),
	)


# ==================== 财务数据 ====================

class FinancialIncome(Base):
    """上市公司利润表数据（对应 Tushare income 接口）"""
    __tablename__ = 'financial_income'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
    ann_date = Column(DateTime, nullable=False, index=True, comment='公告日期')
    f_ann_date = Column(DateTime, comment='实际公告日期')
    end_date = Column(DateTime, nullable=False, comment='报告期')
    report_type = Column(String(10), comment='报告类型')
    comp_type = Column(String(20), comment='公司类型')
    end_type = Column(String(10), comment='报告期类型')
    basic_eps = Column(Numeric(12, 4), comment='基本每股收益')
    diluted_eps = Column(Numeric(12, 4), comment='稀释每股收益')
    total_revenue = Column(Numeric(18, 4), comment='营业总收入')
    revenue = Column(Numeric(18, 4), comment='营业收入')
    int_income = Column(Numeric(18, 4), comment='利息收入')
    prem_earned = Column(Numeric(18, 4), comment='已赚保费')
    comm_income = Column(Numeric(18, 4), comment='手续费及佣金收入')
    n_commis_income = Column(Numeric(18, 4), comment='手续费及佣金净收入')
    n_oth_income = Column(Numeric(18, 4), comment='其他经营净收益')
    n_oth_b_income = Column(Numeric(18, 4), comment='其他业务净收益')
    prem_income = Column(Numeric(18, 4), comment='保险业务收入')
    out_prem = Column(Numeric(18, 4), comment='分出保费')
    une_prem_reser = Column(Numeric(18, 4), comment='提取未到期责任准备金')
    reins_income = Column(Numeric(18, 4), comment='分保费收入')
    n_sec_tb_income = Column(Numeric(18, 4), comment='代理买卖证券业务净收入')
    n_sec_uw_income = Column(Numeric(18, 4), comment='证券承销业务净收入')
    n_asset_mg_income = Column(Numeric(18, 4), comment='受托客户资产管理业务净收入')
    oth_b_income = Column(Numeric(18, 4), comment='其他业务收入')
    fv_value_chg_gain = Column(Numeric(18, 4), comment='公允价值变动净收益')
    invest_income = Column(Numeric(18, 4), comment='投资净收益')
    ass_invest_income = Column(Numeric(18, 4), comment='对联营企业和合营企业的投资收益')
    forex_gain = Column(Numeric(18, 4), comment='汇兑净收益')
    total_cogs = Column(Numeric(18, 4), comment='营业总成本')
    oper_cost = Column(Numeric(18, 4), comment='营业成本')
    int_exp = Column(Numeric(18, 4), comment='利息支出')
    comm_exp = Column(Numeric(18, 4), comment='手续费及佣金支出')
    biz_tax_surchg = Column(Numeric(18, 4), comment='营业税金及附加')
    sell_exp = Column(Numeric(18, 4), comment='销售费用')
    admin_exp = Column(Numeric(18, 4), comment='管理费用')
    fin_exp = Column(Numeric(18, 4), comment='财务费用')
    fin_exp_int_exp = Column(Numeric(18, 4), comment='财务费用:利息费用')
    fin_exp_int_inc = Column(Numeric(18, 4), comment='财务费用:利息收入')
    assets_impair_loss = Column(Numeric(18, 4), comment='资产减值损失')
    credit_impa_loss = Column(Numeric(18, 4), comment='信用减值损失')
    rd_exp = Column(Numeric(18, 4), comment='研发费用')
    prem_refund = Column(Numeric(18, 4), comment='退保金')
    compens_payout = Column(Numeric(18, 4), comment='赔付总支出')
    reser_insur_liab = Column(Numeric(18, 4), comment='提取保险责任准备金')
    div_payt = Column(Numeric(18, 4), comment='保户红利支出')
    reins_exp = Column(Numeric(18, 4), comment='分保费用')
    oper_exp = Column(Numeric(18, 4), comment='营业支出')
    compens_payout_refu = Column(Numeric(18, 4), comment='摊回赔付支出')
    insur_reser_refu = Column(Numeric(18, 4), comment='摊回保险责任准备金')
    reins_cost_refund = Column(Numeric(18, 4), comment='摊回分保费用')
    other_bus_cost = Column(Numeric(18, 4), comment='其他业务成本')
    operate_profit = Column(Numeric(18, 4), comment='营业利润')
    non_oper_income = Column(Numeric(18, 4), comment='营业外收入')
    non_oper_exp = Column(Numeric(18, 4), comment='营业外支出')
    nca_disploss = Column(Numeric(18, 4), comment='非流动资产处置净损失')
    total_profit = Column(Numeric(18, 4), comment='利润总额')
    income_tax = Column(Numeric(18, 4), comment='所得税费用')
    n_income = Column(Numeric(18, 4), comment='净利润(含少数股东损益)')
    n_income_attr_p = Column(Numeric(18, 4), comment='净利润(不含少数股东损益)')
    minority_gain = Column(Numeric(18, 4), comment='少数股东损益')
    oth_compr_income = Column(Numeric(18, 4), comment='其他综合收益')
    t_compr_income = Column(Numeric(18, 4), comment='综合收益总额')
    compr_inc_attr_p = Column(Numeric(18, 4), comment='归属于母公司的综合收益总额')
    compr_inc_attr_m_s = Column(Numeric(18, 4), comment='归属于少数股东的综合收益总额')
    ebit = Column(Numeric(18, 4), comment='息税前利润')
    ebitda = Column(Numeric(18, 4), comment='息税折旧摊销前利润')
    insurance_exp = Column(Numeric(18, 4), comment='保险业务支出')
    undist_profit = Column(Numeric(18, 4), comment='年初未分配利润')
    distable_profit = Column(Numeric(18, 4), comment='可分配利润')
    transfer_surplus_rese = Column(Numeric(18, 4), comment='盈余公积转入')
    withdr_oth_ersu = Column(Numeric(18, 4), comment='提取任意盈余公积金')
    workers_welfare = Column(Numeric(18, 4), comment='职工奖金福利')
    prfshare_payable_dvd = Column(Numeric(18, 4), comment='应付优先股股利')
    comshare_payable_dvd = Column(Numeric(18, 4), comment='应付普通股股利')
    oth_income = Column(Numeric(18, 4), comment='其他收益')
    asset_disp_income = Column(Numeric(18, 4), comment='资产处置收益')
    continued_net_profit = Column(Numeric(18, 4), comment='持续经营净利润')
    end_net_profit = Column(Numeric(18, 4), comment='终止经营净利润')
    update_flag = Column(String(10), comment='更新标识')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    stock = relationship('StockBasic', back_populates='financial_income')

    __table_args__ = (
        UniqueConstraint('ts_code', 'ann_date', name='uq_financial_income_code_date'),
        Index('idx_financial_income_end_date', 'end_date'),
    )


class FinancialBalance(Base):
    """上市公司资产负债表数据（对应 Tushare balancesheet 接口）"""
    __tablename__ = 'financial_balance'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
    ann_date = Column(DateTime, nullable=False, index=True, comment='公告日期')
    f_ann_date = Column(DateTime, comment='实际公告日期')
    end_date = Column(DateTime, nullable=False, comment='报告期')
    report_type = Column(String(10), comment='报告类型')
    comp_type = Column(String(20), comment='公司类型')
    end_type = Column(String(10), comment='报告期类型')
    total_share = Column(Numeric(18, 4), comment='期末总股本')
    cap_rese = Column(Numeric(18, 4), comment='资本公积金')
    surplus_rese = Column(Numeric(18, 4), comment='盈余公积金')
    undistr_porfit = Column(Numeric(18, 4), comment='未分配利润')
    money_cap = Column(Numeric(18, 4), comment='货币资金')
    trad_asset = Column(Numeric(18, 4), comment='交易性金融资产')
    notes_receiv = Column(Numeric(18, 4), comment='应收票据')
    accounts_receiv = Column(Numeric(18, 4), comment='应收账款')
    oth_receiv = Column(Numeric(18, 4), comment='其他应收款')
    prepayment = Column(Numeric(18, 4), comment='预付款项')
    inventories = Column(Numeric(18, 4), comment='存货')
    total_cur_assets = Column(Numeric(18, 4), comment='流动资产合计')
    fa_avail_for_sale = Column(Numeric(18, 4), comment='可供出售金融资产')
    htm_invest = Column(Numeric(18, 4), comment='持有至到期投资')
    lt_eqt_invest = Column(Numeric(18, 4), comment='长期股权投资')
    invest_real_estate = Column(Numeric(18, 4), comment='投资性房地产')
    fix_assets = Column(Numeric(18, 4), comment='固定资产')
    cip = Column(Numeric(18, 4), comment='在建工程')
    intan_assets = Column(Numeric(18, 4), comment='无形资产')
    r_and_d = Column(Numeric(18, 4), comment='研发支出')
    goodwill = Column(Numeric(18, 4), comment='商誉')
    lt_amor_exp = Column(Numeric(18, 4), comment='长期待摊费用')
    defer_tax_assets = Column(Numeric(18, 4), comment='递延所得税资产')
    use_right_assets = Column(Numeric(18, 4), comment='使用权资产')
    contract_assets = Column(Numeric(18, 4), comment='合同资产')
    total_nca = Column(Numeric(18, 4), comment='非流动资产合计')
    total_assets = Column(Numeric(18, 4), comment='资产总计')
    lt_borr = Column(Numeric(18, 4), comment='长期借款')
    st_borr = Column(Numeric(18, 4), comment='短期借款')
    notes_payable = Column(Numeric(18, 4), comment='应付票据')
    acct_payable = Column(Numeric(18, 4), comment='应付账款')
    adv_receipts = Column(Numeric(18, 4), comment='预收款项')
    payroll_payable = Column(Numeric(18, 4), comment='应付职工薪酬')
    taxes_payable = Column(Numeric(18, 4), comment='应交税费')
    int_payable = Column(Numeric(18, 4), comment='应付利息')
    div_payable = Column(Numeric(18, 4), comment='应付股利')
    oth_payable = Column(Numeric(18, 4), comment='其他应付款')
    total_cur_liab = Column(Numeric(18, 4), comment='流动负债合计')
    bond_payable = Column(Numeric(18, 4), comment='应付债券')
    lt_payable = Column(Numeric(18, 4), comment='长期应付款')
    defer_tax_liab = Column(Numeric(18, 4), comment='递延所得税负债')
    lease_liab = Column(Numeric(18, 4), comment='租赁负债')
    contract_liab = Column(Numeric(18, 4), comment='合同负债')
    total_ncl = Column(Numeric(18, 4), comment='非流动负债合计')
    total_liab = Column(Numeric(18, 4), comment='负债合计')
    treasury_share = Column(Numeric(18, 4), comment='库存股')
    minority_int = Column(Numeric(18, 4), comment='少数股东权益')
    total_hldr_eqy_exc_min_int = Column(Numeric(18, 4), comment='股东权益合计(不含少数股东)')
    total_hldr_eqy_inc_min_int = Column(Numeric(18, 4), comment='股东权益合计(含少数股东)')
    total_liab_hldr_eqy = Column(Numeric(18, 4), comment='负债及股东权益总计')
    update_flag = Column(String(10), comment='更新标识')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    stock = relationship('StockBasic', back_populates='financial_balance')

    __table_args__ = (
        UniqueConstraint('ts_code', 'ann_date', name='uq_financial_balance_code_date'),
        Index('idx_financial_balance_end_date', 'end_date'),
    )


class FinancialCashflow(Base):
    """上市公司现金流量表数据（对应 Tushare cashflow 接口）"""
    __tablename__ = 'financial_cashflow'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
    ann_date = Column(DateTime, nullable=False, index=True, comment='公告日期')
    f_ann_date = Column(DateTime, comment='实际公告日期')
    end_date = Column(DateTime, nullable=False, comment='报告期')
    report_type = Column(String(10), comment='报告类型')
    comp_type = Column(String(20), comment='公司类型')
    end_type = Column(String(10), comment='报告期类型')
    net_profit = Column(Numeric(18, 4), comment='净利润')
    c_fr_sale_sg = Column(Numeric(18, 4), comment='销售商品、提供劳务收到的现金')
    recp_tax_rends = Column(Numeric(18, 4), comment='收到的税费返还')
    c_fr_oth_operate_a = Column(Numeric(18, 4), comment='收到其他与经营活动有关的现金')
    c_inf_fr_operate_a = Column(Numeric(18, 4), comment='经营活动现金流入小计')
    c_paid_goods_s = Column(Numeric(18, 4), comment='购买商品、接受劳务支付的现金')
    c_paid_to_for_empl = Column(Numeric(18, 4), comment='支付给职工以及为职工支付的现金')
    c_paid_for_taxes = Column(Numeric(18, 4), comment='支付的各项税费')
    oth_cash_pay_oper_act = Column(Numeric(18, 4), comment='支付其他与经营活动有关的现金')
    st_cash_out_act = Column(Numeric(18, 4), comment='经营活动现金流出小计')
    n_cashflow_act = Column(Numeric(18, 4), comment='经营活动产生的现金流量净额')
    c_disp_withdrwl_invest = Column(Numeric(18, 4), comment='收回投资收到的现金')
    c_recp_return_invest = Column(Numeric(18, 4), comment='取得投资收益收到的现金')
    n_recp_disp_fiolta = Column(Numeric(18, 4), comment='处置固定资产无形资产和其他长期资产收回的现金净额')
    stot_inflows_inv_act = Column(Numeric(18, 4), comment='投资活动现金流入小计')
    c_pay_acq_const_fiolta = Column(Numeric(18, 4), comment='购建固定资产无形资产和其他长期资产支付的现金')
    c_paid_invest = Column(Numeric(18, 4), comment='投资支付的现金')
    stot_out_inv_act = Column(Numeric(18, 4), comment='投资活动现金流出小计')
    n_cashflow_inv_act = Column(Numeric(18, 4), comment='投资活动产生的现金流量净额')
    c_recp_borrow = Column(Numeric(18, 4), comment='取得借款收到的现金')
    proc_issue_bonds = Column(Numeric(18, 4), comment='发行债券收到的现金')
    c_recp_cap_contrib = Column(Numeric(18, 4), comment='吸收投资收到的现金')
    stot_cash_in_fnc_act = Column(Numeric(18, 4), comment='筹资活动现金流入小计')
    c_prepay_amt_borr = Column(Numeric(18, 4), comment='偿还债务支付的现金')
    c_pay_dist_dpcp_int_exp = Column(Numeric(18, 4), comment='分配股利、利润或偿付利息支付的现金')
    oth_cashpay_ral_fnc_act = Column(Numeric(18, 4), comment='支付其他与筹资活动有关的现金')
    stot_cashout_fnc_act = Column(Numeric(18, 4), comment='筹资活动现金流出小计')
    n_cash_flows_fnc_act = Column(Numeric(18, 4), comment='筹资活动产生的现金流量净额')
    free_cashflow = Column(Numeric(18, 4), comment='企业自由现金流量')
    eff_fx_flu_cash = Column(Numeric(18, 4), comment='汇率变动对现金的影响')
    n_incr_cash_cash_equ = Column(Numeric(18, 4), comment='现金及现金等价物净增加额')
    c_cash_equ_beg_period = Column(Numeric(18, 4), comment='期初现金及现金等价物余额')
    c_cash_equ_end_period = Column(Numeric(18, 4), comment='期末现金及现金等价物余额')
    prov_depr_assets = Column(Numeric(18, 4), comment='资产减值准备')
    depr_fa_coga_dpba = Column(Numeric(18, 4), comment='固定资产折旧、油气资产折耗、生产性生物资产折旧')
    amort_intang_assets = Column(Numeric(18, 4), comment='无形资产摊销')
    loss_disp_fiolta = Column(Numeric(18, 4), comment='处置固定资产、无形资产和其他长期资产的损失')
    invest_loss = Column(Numeric(18, 4), comment='投资损失')
    decr_inventories = Column(Numeric(18, 4), comment='存货的减少')
    im_net_cashflow_oper_act = Column(Numeric(18, 4), comment='经营活动净现金流(间接法)')
    update_flag = Column(String(10), comment='更新标识')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    stock = relationship('StockBasic', back_populates='financial_cashflow')

    __table_args__ = (
        UniqueConstraint('ts_code', 'ann_date', name='uq_financial_cashflow_code_date'),
        Index('idx_financial_cashflow_end_date', 'end_date'),
    )



# ==================== 市场参考数据 ====================

class TradeCalendar(Base):
	"""交易所交易日历表"""
	__tablename__ = 'trade_calendar'

	exchange = Column(String(10), primary_key=True, comment='交易所代码')
	cal_date = Column(DateTime, primary_key=True, comment='日历日期')
	is_open = Column(Boolean, nullable=False, default=False, comment='是否交易日')
	pretrade_date = Column(DateTime, comment='前一交易日')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

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

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='ST记录ID')
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	name = Column(String(50), nullable=False, comment='股票名称')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	st_type = Column(String(10), nullable=False, comment='ST类型：ST, *ST, SST等')
	st_type_name = Column(String(50), nullable=False, comment='ST类型名称')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 唯一约束
	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uniq_st_stock'),
		Index('idx_stock_st_list_ts_code', 'ts_code'),
		Index('idx_stock_st_list_trade_date', 'trade_date'),
		Index('idx_stock_st_list_type', 'st_type'),
	)


# ==================== ETF数据 ====================

class EtfIndex(Base):
	"""ETF基准指数列表信息（字段对齐 Tushare etf_index 接口）"""
	__tablename__ = 'etf_index'

	ts_code = Column(String(20), primary_key=True, comment='指数代码')
	indx_name = Column(String(200), comment='指数全称')
	indx_csname = Column(String(100), comment='指数简称')
	pub_party_name = Column(String(200), comment='发布机构')
	pub_date = Column(DateTime(timezone=True), comment='发布日期')
	base_date = Column(DateTime(timezone=True), comment='指数基日')
	bp = Column(Float, comment='指数基点')
	adj_circle = Column(String(50), comment='调整周期')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))



class EtfBasic(Base):
	"""ETF基础信息表（字段对齐 Tushare fund_basic 接口）"""
	__tablename__ = 'etf_basic'

	ts_code = Column(String(20), primary_key=True, comment='基金代码')
	name = Column(String(100), comment='基金简称')
	management = Column(String(200), comment='管理人')
	custodian = Column(String(200), comment='托管人')
	fund_type = Column(String(50), comment='基金类型')
	found_date = Column(DateTime(timezone=True), comment='成立日期')
	due_date = Column(DateTime(timezone=True), comment='到期日期')
	list_date = Column(DateTime(timezone=True), comment='上市日期')
	issue_date = Column(DateTime(timezone=True), comment='发行日期')
	delist_date = Column(DateTime(timezone=True), comment='退市日期')
	issue_amount = Column(Float, comment='发行份额(万)')
	m_fee = Column(Float, comment='管理费率')
	c_fee = Column(Float, comment='托管费率')
	duration_year = Column(Float, comment='存续期')
	p_value = Column(Float, comment='面值')
	min_amount = Column(Float, comment='起购金额')
	exp_return = Column(Float, comment='预期收益')
	benchmark = Column(String(200), comment='业绩基准')
	status = Column(String(1), comment='状态: L=上市 D=退市')
	invest_type = Column(String(100), comment='投资类型')
	market = Column(String(2), comment='市场: E=上交所 S=深交所')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))
	adj_factors = relationship("FundAdjFactor", back_populates="etf", cascade="all, delete-orphan")


class EtfDaily(Base):
	"""ETF日线行情数据"""
	__tablename__ = 'etf_daily'

	ts_code = Column(String(20), ForeignKey('etf_basic.ts_code'), primary_key=True, comment='TS代码')
	trade_date = Column(DateTime, primary_key=True, comment='交易日期')
	open = Column(Numeric(10, 4), nullable=False, comment='开盘价')
	high = Column(Numeric(10, 4), nullable=False, comment='最高价')
	low = Column(Numeric(10, 4), nullable=False, comment='最低价')
	close = Column(Numeric(10, 4), nullable=False, comment='收盘价')
	pre_close = Column(Numeric(10, 4), nullable=False, comment='前收盘价')
	change = Column(Numeric(10, 4), nullable=False, comment='涨跌额')
	pct_chg = Column(Numeric(8, 4), nullable=False, comment='涨跌幅')
	vol = Column(BigInteger, nullable=False, comment='成交量（手）')
	amount = Column(Numeric(16, 4), nullable=False, comment='成交额（千元）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	etf = relationship("EtfBasic", foreign_keys=[ts_code])


class EtfMinute(Base):
	"""ETF历史分钟行情数据"""
	__tablename__ = 'etf_minute'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='分钟数据ID')
	ts_code = Column(String(20), ForeignKey('etf_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	freq = Column(String(10), nullable=False, comment='频率：1min/5min/15min/30min/60min')
	trade_time = Column(DateTime, nullable=False, index=True, comment='交易时间')
	open = Column(Numeric(10, 4), nullable=False, comment='开盘价')
	close = Column(Numeric(10, 4), nullable=False, comment='收盘价')
	high = Column(Numeric(10, 4), nullable=False, comment='最高价')
	low = Column(Numeric(10, 4), nullable=False, comment='最低价')
	vol = Column(BigInteger, nullable=False, comment='成交量')
	amount = Column(Numeric(18, 2), nullable=False, comment='成交额')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

	# 关联关系
	etf = relationship("EtfBasic", foreign_keys=[ts_code])

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'freq', 'trade_time', name='uq_etf_minute_code_freq_time'),
	)


class FundAdjFactor(Base):
	"""基金复权因子数据"""
	__tablename__ = 'fund_adj_factor'

	ts_code = Column(String(20), ForeignKey('etf_basic.ts_code'), primary_key=True, comment='TS代码')
	trade_date = Column(DateTime, primary_key=True, comment='交易日期')
	adj_factor = Column(Numeric(16, 8), nullable=False, comment='复权因子')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	etf = relationship("EtfBasic", back_populates="adj_factors")


# ==================== 指数数据 ====================

class IndexBasic(Base):
	"""指数基本信息表"""
	__tablename__ = 'index_basic'

	ts_code = Column(String(20), primary_key=True, comment='指数代码')
	name = Column(String(100), nullable=False, comment='指数名称')
	fullname = Column(String(200), comment='指数全称')
	market = Column(String(20), comment='市场')
	publisher = Column(String(100), comment='发布方')
	index_type = Column(String(50), comment='指数类型')
	category = Column(String(50), comment='指数类别')
	base_date = Column(DateTime, comment='基期')
	base_point = Column(Numeric(12, 2), comment='基点')
	list_date = Column(DateTime, comment='发布日期')
	weight_rule = Column(String(100), comment='加权方式')
	desc = Column(String(500), comment='描述')
	exp_date = Column(DateTime, comment='到期日')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')


class IndexDaily(Base):
	"""指数日线行情数据（TimescaleDB 超表，复合主键）"""
	__tablename__ = 'index_daily'

	ts_code = Column(String(20), primary_key=True, comment='指数代码')
	trade_date = Column(DateTime, primary_key=True, comment='交易日期')
	close = Column(Numeric(12, 4), nullable=False, comment='收盘价')
	open = Column(Numeric(12, 4), comment='开盘价')
	high = Column(Numeric(12, 4), comment='最高价')
	low = Column(Numeric(12, 4), comment='最低价')
	pre_close = Column(Numeric(12, 4), comment='前收盘价')
	change = Column(Numeric(12, 4), comment='涨跌额')
	pct_chg = Column(Numeric(10, 6), comment='涨跌幅')
	vol = Column(BigInteger, comment='成交量（手）')
	amount = Column(Numeric(18, 4), comment='成交额（万元）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

	__table_args__ = (
		Index('idx_index_daily_trade_date', 'trade_date'),
	)


# ==================== 指数成分股权重 ====================

class IndexWeight(Base):
	"""指数成分股权重表

	存储各指数（沪深300、中证500等）的成分股及对应权重。
	权重数据来源：Tushare index_weight 接口 / Baostock query_hs300_stocks / query_zz500_stocks。
	同步策略：每月初同步一次（指数成分股通常每月调整一次）。
	"""
	__tablename__ = 'index_weight'

	id = Column(String(36), default=lambda: str(uuid.uuid4()), comment='UUID')
	index_code = Column(String(20), ForeignKey('index_basic.ts_code', ondelete='CASCADE'), nullable=False, comment='指数代码，关联 index_basic.ts_code')
	ts_code = Column(String(20), nullable=False, comment='成分股代码')
	weight = Column(Numeric(12, 8), comment='成分股权重（小数形式，如 0.0352 表示 3.52%）')
	trade_date = Column(Date, nullable=False, comment='权重生效日期')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

	# 关联关系 — 使用 backref 避免修改 IndexBasic / StockBasic
	index = relationship("IndexBasic", backref="index_weights")

	# 索引
	__table_args__ = (
		PrimaryKeyConstraint('index_code', 'ts_code', 'trade_date', name='pk_index_weight'),
		Index('idx_index_weight_code_date', 'index_code', 'trade_date'),
		Index('idx_index_weight_ts_code', 'ts_code'),
	)


# ==================== 因子数据 ====================

class FactorData(Base):
	"""因子数据表"""
	__tablename__ = 'factor_data'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='因子数据ID')
	factor_definition_id = Column(String(36), ForeignKey('factor_definitions.id'), nullable=True, index=True,
	                              comment='因子定义ID')
	ts_code = Column(String(12), nullable=False, index=True, comment='股票代码')
	factor_name = Column("factor_code", String(50), nullable=False, index=True, comment='因子名称')
	trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
	factor_value = Column(Numeric(18, 6), nullable=False, comment='因子值')
	data_source = Column(String(50), comment='数据来源')
	calc_time = Column(DateTime(timezone=True), comment='计算时间')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	definition = relationship("FactorDefinition", back_populates="factor_values")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'factor_code', 'trade_date', name='uq_factor_data_code_name_date'),
		Index('idx_factor_data_factor_code_date', 'factor_code', 'trade_date'),
	)


# 在 data_models.py 末尾添加以下模型定义
# ==================== 因子定义 ====================

class FactorDefinition(Base):
	"""量化因子定义表"""
	__tablename__ = 'factor_definitions'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='因子定义ID')
	factor_code = Column(String(50), unique=True, nullable=False, index=True, comment='因子代码')
	factor_name = Column(String(100), nullable=False, comment='因子名称')
	factor_type = Column(String(30), nullable=False,
	                     comment='因子类型：technical-技术指标, fundamental-基本面, macro-宏观, alternative-另类数据, custom-自定义')
	category = Column(String(50), comment='因子类别')
	description = Column(Text, comment='因子描述')
	formula = Column(Text, comment='因子计算公式')
	parameters = Column(JSON, comment='因子参数（JSON格式）')
	data_requirements = Column(JSON, comment='数据需求（JSON格式）')
	output_type = Column(String(20), default='float', comment='输出类型：float, int, bool, string')
	calculation_frequency = Column(String(20), default='daily', comment='计算频率：minute, daily, weekly, monthly')
	is_public = Column(Boolean, default=True, comment='是否公开')
	is_active = Column(Boolean, default=True, comment='是否激活')
	created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建者')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	creator = relationship("SysUser", foreign_keys=created_by)
	factor_values = relationship("FactorData", back_populates="definition", cascade="all, delete-orphan")

	# 索引
	__table_args__ = (
		Index('idx_factor_definitions_factor_type', 'factor_type'),
		Index('idx_factor_definitions_category', 'category'),
		Index('idx_factor_definitions_is_active', 'is_active'),
		Index('idx_factor_definitions_created_by', 'created_by'),
	)


# ==================== 公司公告信息 ====================

class CompanyAnnouncement(Base):
	"""公司公告信息表"""
	__tablename__ = 'company_announcements'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='公告ID')
	ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='股票代码')
	announcement_date = Column(DateTime, nullable=False, index=True, comment='公告日期')
	title = Column(String(500), nullable=False, comment='公告标题')
	announcement_type = Column(String(50), nullable=False, index=True, comment='公告类型')
	content = Column(Text, comment='公告内容')
	pdf_url = Column(String(500), comment='PDF文件URL')
	source = Column(String(100), comment='数据来源')
	importance_level = Column(Integer, default=1, comment='重要程度：1-一般，2-重要，3-重大')
	is_processed = Column(Boolean, default=False, comment='是否已处理')
	processed_at = Column(DateTime(timezone=True), comment='处理时间')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="announcements")

	# 索引
	__table_args__ = (
		Index('idx_company_anns_ts_date', 'ts_code', 'announcement_date'),
		Index('idx_company_anns_date_type', 'announcement_date', 'announcement_type'),
		Index('idx_company_anns_importance', 'importance_level'),
		UniqueConstraint('ts_code', 'announcement_date', 'title', name='uq_announcement_unique'),
	)


# ==================== 财务衍生数据 ====================

class StockForecast(Base):
	"""业绩预告数据表（字段对齐 Tushare forecast 接口）"""
	__tablename__ = 'stock_forecasts'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime(timezone=True), nullable=False, comment='公告日期')
	end_date = Column(DateTime(timezone=True), nullable=False, comment='报告期')
	type = Column(String(10), comment='预告类型')
	p_change_min = Column(Numeric(12, 4), comment='净利润变动下限(%)')
	p_change_max = Column(Numeric(12, 4), comment='净利润变动上限(%)')
	net_profit_min = Column(Numeric(18, 4), comment='净利润下限')
	net_profit_max = Column(Numeric(18, 4), comment='净利润上限')
	last_parent_net = Column(Numeric(18, 4), comment='上年同期净利润')
	first_ann_date = Column(DateTime(timezone=True), comment='首次公告日期')
	summary = Column(Text, comment='业绩变动摘要')
	change_reason = Column(Text, comment='业绩变动原因')
	update_flag = Column(String(10), comment='Tushare更新标记')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_forecasts_ts_code', 'ts_code'),
		Index('idx_stock_forecasts_ann_date', 'ann_date'),
		UniqueConstraint('ts_code', 'ann_date', name='uq_forecasts_ts_ann'),
	)


class StockExpress(Base):
	"""业绩快报数据表（字段对齐 Tushare express 接口）"""
	__tablename__ = 'stock_expresses'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime(timezone=True), nullable=False, comment='公告日期')
	end_date = Column(DateTime(timezone=True), nullable=False, comment='报告期')
	revenue = Column(Numeric(18, 4), comment='营业收入')
	operate_profit = Column(Numeric(18, 4), comment='营业利润')
	total_profit = Column(Numeric(18, 4), comment='利润总额')
	n_income = Column(Numeric(18, 4), comment='净利润')
	total_assets = Column(Numeric(18, 4), comment='总资产')
	total_hldr_eqy_exc_min_int = Column(Numeric(18, 4), comment='股东权益')
	diluted_eps = Column(Numeric(12, 4), comment='稀释每股收益')
	diluted_roe = Column(Numeric(12, 4), comment='净资产收益率(%)')
	yoy_net_profit = Column(Numeric(16, 4), comment='净利润同比(%)')
	bps = Column(Numeric(12, 4), comment='每股净资产')
	yoy_sales = Column(Numeric(16, 4), comment='营收同比(%)')
	yoy_op = Column(Numeric(16, 4), comment='营业利润同比(%)')
	yoy_tp = Column(Numeric(16, 4), comment='利润总额同比(%)')
	yoy_dedu_np = Column(Numeric(16, 4), comment='归母净利润同比(%)')
	yoy_eps = Column(Numeric(16, 4), comment='EPS同比(%)')
	yoy_roe = Column(Numeric(16, 4), comment='净资产收益率同比(%)')
	growth_assets = Column(Numeric(16, 4), comment='总资产增长率(%)')
	yoy_equity = Column(Numeric(16, 4), comment='股东权益增长率(%)')
	growth_bps = Column(Numeric(16, 4), comment='每股净资产增长率(%)')
	or_last_year = Column(Numeric(18, 4), comment='去年同期营业收入')
	op_last_year = Column(Numeric(18, 4), comment='去年同期营业利润')
	tp_last_year = Column(Numeric(18, 4), comment='去年同期利润总额')
	np_last_year = Column(Numeric(18, 4), comment='去年同期净利润')
	eps_last_year = Column(Numeric(12, 4), comment='去年同期每股收益')
	open_net_assets = Column(Numeric(18, 4), comment='期初净资产')
	open_bps = Column(Numeric(12, 4), comment='期初每股净资产')
	perf_summary = Column(Text, comment='业绩简要说明')
	is_audit = Column(Integer, comment='是否审计：1是0否')
	remark = Column(Text, comment='备注')
	update_flag = Column(String(10), comment='Tushare更新标记')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_expresses_ts_code', 'ts_code'),
		Index('idx_stock_expresses_ann_date', 'ann_date'),
		UniqueConstraint('ts_code', 'ann_date', name='uq_expresses_ts_ann'),
	)


class StockDividend(Base):
	"""分红送股数据表"""
	__tablename__ = 'stock_dividends'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime(timezone=True), comment='公告日期')
	end_date = Column(DateTime(timezone=True), comment='报告期')
	div_proc = Column(Text, comment='分红预案')
	stk_div = Column(Numeric(18, 4), comment='每股送转')
	stk_bo_rate = Column(Numeric(12, 4), comment='每股转增')
	stk_co_rate = Column(Numeric(12, 4), comment='每股送股')
	cash_div = Column(Numeric(18, 4), comment='每股分红')
	cash_div_tax = Column(Numeric(18, 4), comment='每股分红（含税）')
	record_date = Column(DateTime(timezone=True), comment='股权登记日')
	ex_date = Column(DateTime(timezone=True), comment='除权除息日')
	pay_date = Column(DateTime(timezone=True), comment='派息日')
	div_listdate = Column(DateTime(timezone=True), comment='分红实施公告日')
	imp_ann_date = Column(DateTime(timezone=True), comment='实施公告日')
	base_share = Column(Numeric(18, 4), comment='基准股本')
	base_vol = Column(Numeric(18, 4), comment='基准成交量')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_dividends_ts_code', 'ts_code'),
		Index('idx_stock_dividends_ann_date', 'ann_date'),
		UniqueConstraint('ts_code', 'ann_date', 'div_proc', name='uq_dividends_unique'),
	)


class StockFinaIndicator(Base):
	"""财务指标数据表"""
	__tablename__ = 'stock_fina_indicators'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime(timezone=True), comment='公告日期')
	end_date = Column(DateTime(timezone=True), nullable=False, comment='报告期')
	eps = Column(Numeric(18, 4), comment='每股收益')
	roe = Column(Numeric(16, 4), comment='净资产收益率(%)')
	roa = Column(Numeric(16, 4), comment='总资产收益率(%)')
	roic = Column(Numeric(16, 4), comment='投入资本回报率(%)')
	grossprofit_margin = Column(Numeric(16, 4), comment='毛利率(%)')
	netprofit_margin = Column(Numeric(16, 4), comment='净利率(%)')
	debt_to_assets = Column(Numeric(16, 4), comment='资产负债率(%)')
	current_ratio = Column(Numeric(16, 4), comment='流动比率')
	quick_ratio = Column(Numeric(16, 4), comment='速动比率')
	assets_turn = Column(Numeric(16, 4), comment='总资产周转率')
	op_cycle = Column(Numeric(18, 4), comment='营业周期')
	turnover_days = Column(Numeric(18, 4), comment='存货周转天数')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_fina_indicators_ts_code', 'ts_code'),
		Index('idx_stock_fina_indicators_ann_date', 'ann_date'),
		UniqueConstraint('ts_code', 'end_date', name='uq_fina_indicator_unique'),
	)


class StockAuditOpinion(Base):
	"""审计意见数据表"""
	__tablename__ = 'stock_audit_opinions'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime(timezone=True), comment='公告日期')
	end_date = Column(DateTime(timezone=True), nullable=False, comment='报告期')
	audit_result = Column(String(200), comment='审计结果')
	audit_fees = Column(Numeric(18, 4), comment='审计费用')
	audit_agency = Column(String(200), comment='会计师事务所')
	audit_sign = Column(String(100), comment='签字会计师')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_audit_opinions_ts_code', 'ts_code'),
		Index('idx_stock_audit_opinions_ann_date', 'ann_date'),
		UniqueConstraint('ts_code', 'end_date', name='uq_audit_opinion_unique'),
	)


class StockBusinessIncome(Base):
	"""主营业务构成数据表"""
	__tablename__ = 'stock_business_incomes'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	end_date = Column(DateTime(timezone=True), nullable=False, comment='报告期')
	bz_item = Column(String(200), comment='主营业务项目')
	bz_code = Column(String(10), comment='来源类型(P产品/D地区/I行业)')
	bz_sales = Column(Numeric(18, 4), comment='主营收入')
	bz_profit = Column(Numeric(18, 4), comment='主营利润')
	bz_cost = Column(Numeric(18, 4), comment='主营成本')
	curr_type = Column(String(10), comment='货币代码')
	type = Column(String(5), comment='类型(P/D/I)')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_business_incomes_ts_code', 'ts_code'),
		UniqueConstraint('ts_code', 'end_date', 'bz_item', 'bz_code', name='uq_biz_income_unique'),
	)


class EtfShare(Base):
	"""ETF份额数据表"""
	__tablename__ = 'etf_shares'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='ETF代码')
	trade_date = Column(DateTime(timezone=True), nullable=False, comment='交易日期')
	fund_size = Column(Numeric(18, 4), comment='基金规模(份)')
	fund_vol = Column(Numeric(18, 4), comment='基金份额变动')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_etf_shares_ts_code', 'ts_code'),
		Index('idx_etf_shares_trade_date', 'trade_date'),
		UniqueConstraint('ts_code', 'trade_date', name='uq_etf_share_unique'),
	)


class MacroCpi(Base):
    """CPI居民消费价格指数月度数据"""
    __tablename__ = 'macro_cpi'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    month = Column(String(6), nullable=False, unique=True, comment='月份YYYYMM')
    nt_val = Column(Numeric(10, 4), comment='全国当月值')
    nt_yoy = Column(Numeric(10, 4), comment='全国同比(%)')
    nt_mom = Column(Numeric(10, 4), comment='全国环比(%)')
    nt_accu = Column(Numeric(10, 4), comment='全国累计值')
    town_val = Column(Numeric(10, 4), comment='城市当月值')
    town_yoy = Column(Numeric(10, 4), comment='城市同比(%)')
    town_mom = Column(Numeric(10, 4), comment='城市环比(%)')
    town_accu = Column(Numeric(10, 4), comment='城市累计值')
    cnt_val = Column(Numeric(10, 4), comment='农村当月值')
    cnt_yoy = Column(Numeric(10, 4), comment='农村同比(%)')
    cnt_mom = Column(Numeric(10, 4), comment='农村环比(%)')
    cnt_accu = Column(Numeric(10, 4), comment='农村累计值')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MacroPpi(Base):
    """PPI工业生产者出厂价格指数月度数据（对齐 Tushare cn_ppi 接口）"""
    __tablename__ = 'macro_ppi'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    month = Column(String(6), nullable=False, unique=True, comment='月份YYYYMM')
    # 全部工业品
    ppi_yoy = Column(Numeric(10, 4), comment='全部工业品:当月同比')
    ppi_mom = Column(Numeric(10, 4), comment='全部工业品:环比')
    ppi_accu = Column(Numeric(10, 4), comment='全部工业品:累计同比')
    # 生产资料
    ppi_mp_yoy = Column(Numeric(10, 4), comment='生产资料:当月同比')
    ppi_mp_mom = Column(Numeric(10, 4), comment='生产资料:环比')
    ppi_mp_accu = Column(Numeric(10, 4), comment='生产资料:累计同比')
    ppi_mp_qm_yoy = Column(Numeric(10, 4), comment='生产资料-采掘业:当月同比')
    ppi_mp_qm_mom = Column(Numeric(10, 4), comment='生产资料-采掘业:环比')
    ppi_mp_qm_accu = Column(Numeric(10, 4), comment='生产资料-采掘业:累计同比')
    ppi_mp_rm_yoy = Column(Numeric(10, 4), comment='生产资料-原料业:当月同比')
    ppi_mp_rm_mom = Column(Numeric(10, 4), comment='生产资料-原料业:环比')
    ppi_mp_rm_accu = Column(Numeric(10, 4), comment='生产资料-原料业:累计同比')
    ppi_mp_p_yoy = Column(Numeric(10, 4), comment='生产资料-加工业:当月同比')
    ppi_mp_p_mom = Column(Numeric(10, 4), comment='生产资料-加工业:环比')
    ppi_mp_p_accu = Column(Numeric(10, 4), comment='生产资料-加工业:累计同比')
    # 生活资料
    ppi_cg_yoy = Column(Numeric(10, 4), comment='生活资料:当月同比')
    ppi_cg_mom = Column(Numeric(10, 4), comment='生活资料:环比')
    ppi_cg_accu = Column(Numeric(10, 4), comment='生活资料:累计同比')
    ppi_cg_f_yoy = Column(Numeric(10, 4), comment='生活资料-食品:当月同比')
    ppi_cg_f_mom = Column(Numeric(10, 4), comment='生活资料-食品:环比')
    ppi_cg_f_accu = Column(Numeric(10, 4), comment='生活资料-食品:累计同比')
    ppi_cg_c_yoy = Column(Numeric(10, 4), comment='生活资料-衣着:当月同比')
    ppi_cg_c_mom = Column(Numeric(10, 4), comment='生活资料-衣着:环比')
    ppi_cg_c_accu = Column(Numeric(10, 4), comment='生活资料-衣着:累计同比')
    ppi_cg_adu_yoy = Column(Numeric(10, 4), comment='生活资料-日用品:当月同比')
    ppi_cg_adu_mom = Column(Numeric(10, 4), comment='生活资料-日用品:环比')
    ppi_cg_adu_accu = Column(Numeric(10, 4), comment='生活资料-日用品:累计同比')
    ppi_cg_dcg_yoy = Column(Numeric(10, 4), comment='生活资料-耐用消费品:当月同比')
    ppi_cg_dcg_mom = Column(Numeric(10, 4), comment='生活资料-耐用消费品:环比')
    ppi_cg_dcg_accu = Column(Numeric(10, 4), comment='生活资料-耐用消费品:累计同比')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MacroGdp(Base):
    """GDP国内生产总值季度数据（对齐 Tushare cn_gdp 接口）"""
    __tablename__ = 'macro_gdp'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    quarter = Column(String(6), nullable=False, unique=True, comment='季度YYYYQ1~Q4')
    gdp = Column(Numeric(18, 4), comment='GDP总额(亿元)')
    gdp_yoy = Column(Numeric(10, 4), comment='GDP同比(%)')
    pi = Column(Numeric(18, 4), comment='第一产业增加值')
    pi_yoy = Column(Numeric(10, 4), comment='第一产业同比(%)')
    si = Column(Numeric(18, 4), comment='第二产业增加值')
    si_yoy = Column(Numeric(10, 4), comment='第二产业同比(%)')
    ti = Column(Numeric(18, 4), comment='第三产业增加值')
    ti_yoy = Column(Numeric(10, 4), comment='第三产业同比(%)')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StockSuspendInfo(Base):
	"""股票停复牌信息表"""
	__tablename__ = 'stock_suspend_info'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	trade_date = Column(DateTime(timezone=True), nullable=False, comment='停复牌日期')
	suspend_timing = Column(String(100), comment='日内停牌时间段')
	suspend_type = Column(String(2), nullable=False, comment='停复牌类型：S-停牌，R-复牌')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_suspend_info_ts_code', 'ts_code'),
		Index('idx_stock_suspend_info_trade_date', 'trade_date'),
		UniqueConstraint('ts_code', 'trade_date', 'suspend_type', name='uq_suspend_info_unique'),
	)


# ==================== 事件驱动与解禁数据 ====================

class StockHsgt(Base):
	"""沪深港通股票列表"""
	__tablename__ = 'stock_hsgt'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='股票代码')
	trade_date = Column(DateTime, nullable=False, comment='交易日期')
	type = Column(String(5), nullable=False, comment='类型: HK_SZ/SZ_HK/HK_SH/SH_HK')
	name = Column(String(100), comment='股票名称')
	type_name = Column(String(50), comment='类型名称')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', 'type', name='uq_stock_hsgt_unique'),
	)


class StockStRisk(Base):
	"""ST风险警示板股票"""
	__tablename__ = 'stock_st_risk'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='股票代码')
	name = Column(String(100), comment='股票名称')
	pub_date = Column(DateTime, comment='发布日期')
	imp_date = Column(DateTime, nullable=False, comment='实施日期')
	st_type = Column(String(10), comment='ST类型')
	st_reason = Column(String(500), comment='ST变更原因')
	st_explain = Column(Text, comment='ST变更详细原因')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'imp_date', name='uq_stock_st_risk_unique'),
	)


class FinancialDisclosureDate(Base):
	"""财报披露日期表"""
	__tablename__ = 'financial_disclosure_dates'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime, comment='最新披露公告日')
	end_date = Column(DateTime, nullable=False, comment='报告期')
	pre_date = Column(DateTime, comment='预计披露日期')
	actual_date = Column(DateTime, comment='实际披露日期')
	modify_date = Column(String(500), comment='披露日期修正记录')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'end_date', name='uq_disclosure_date_unique'),
	)


class StockShareFloat(Base):
	"""限售股解禁表"""
	__tablename__ = 'stock_share_float'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime, comment='公告日期')
	float_date = Column(DateTime, nullable=False, comment='解禁日期')
	float_share = Column(Numeric(18, 2), comment='流通股份(股)')
	float_ratio = Column(Numeric(8, 4), comment='流通股份占总股本比率')
	holder_name = Column(String(200), comment='股东名称')
	share_type = Column(String(50), comment='股份类型')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'float_date', 'holder_name', name='uq_share_float_unique'),
	)


class StockStkHoldernumber(Base):
	"""股东人数表"""
	__tablename__ = 'stock_stk_holdernumber'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	ann_date = Column(DateTime, comment='公告日期')
	end_date = Column(DateTime, nullable=False, comment='截止日期')
	holder_num = Column(Integer, comment='股东户数')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'end_date', name='uq_holdernumber_unique'),
	)


class StockTop10Holders(Base):
	"""前十大股东表"""
	__tablename__ = 'stock_top10_holders'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	ann_date = Column(DateTime, comment='公告日期')
	end_date = Column(DateTime, nullable=False, comment='报告期')
	holder_name = Column(String(200), nullable=False, comment='股东名称')
	hold_amount = Column(Numeric(18, 2), comment='持有数量（股）')
	hold_ratio = Column(Numeric(18, 4), comment='占总股本比例(%)')
	hold_float_ratio = Column(Numeric(18, 4), comment='占流通股本比例(%)')
	hold_change = Column(Numeric(18, 4), comment='持股变动')
	holder_type = Column(String(50), comment='股东类型')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'end_date', 'holder_name', name='uq_top10_holders_unique'),
	)


class StockTop10FloatHolders(Base):
	"""前十大流通股东表"""
	__tablename__ = 'stock_top10_float_holders'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	ann_date = Column(DateTime, comment='公告日期')
	end_date = Column(DateTime, nullable=False, comment='报告期')
	holder_name = Column(String(200), nullable=False, comment='股东名称')
	hold_amount = Column(Numeric(18, 2), comment='持有数量（股）')
	hold_ratio = Column(Numeric(18, 4), comment='占总股本比例(%)')
	hold_float_ratio = Column(Numeric(18, 4), comment='占流通股本比例(%)')
	hold_change = Column(Numeric(18, 4), comment='持股变动')
	holder_type = Column(String(50), comment='股东类型')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'end_date', 'holder_name', name='uq_top10_float_holders_unique'),
	)


class StockPledgeStat(Base):
	"""股权质押统计表"""
	__tablename__ = 'stock_pledge_stat'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	end_date = Column(DateTime, nullable=False, comment='截止日期')
	pledge_count = Column(Integer, comment='质押次数')
	unrest_pledge = Column(Numeric(18, 2), comment='无限售股质押数量（万股）')
	rest_pledge = Column(Numeric(18, 2), comment='限售股质押数量（万股）')
	total_share = Column(Numeric(18, 2), comment='质押总股本（万股）')
	pledge_ratio = Column(Numeric(8, 4), comment='质押比例(%)')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'end_date', name='uq_pledge_stat_unique'),
	)


class StockStkHoldertrade(Base):
	"""股东增减持表"""
	__tablename__ = 'stock_stk_holdertrade'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	ann_date = Column(DateTime, comment='公告日期')
	holder_name = Column(String(200), nullable=False, comment='股东名称')
	holder_type = Column(String(10), comment='股东类型')
	in_de = Column(String(2), comment='增减持方向（IN增持/DE减持）')
	change_vol = Column(Numeric(18, 2), comment='变动数量（股）')
	change_ratio = Column(Numeric(8, 4), comment='变动比例(%)')
	after_share = Column(Numeric(18, 2), comment='变动后持股')
	after_ratio = Column(Numeric(8, 4), comment='变动后持股比例(%)')
	avg_price = Column(Numeric(12, 4), comment='增/减持均价')
	total_share = Column(Numeric(18, 2), comment='总股本')
	begin_date = Column(DateTime, comment='变动开始日期')
	close_date = Column(DateTime, comment='变动结束日期')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'holder_name', 'in_de', name='uq_holdertrade_unique'),
	)


# ==================== Phase 3 新增数据类型 ====================

class IndexSwClassify(Base):
	"""申万行业分类表"""
	__tablename__ = 'index_sw_classify'

	index_code = Column(String(20), primary_key=True, comment='指数代码')
	industry_name = Column(String(100), comment='行业名称')
	parent_code = Column(String(20), comment='父级代码')
	level = Column(String(3), comment='行业层级 L1/L2/L3')
	industry_code = Column(String(20), comment='行业代码')
	is_pub = Column(String(1), comment='是否发布指数 0/1')
	src = Column(String(10), comment='指数来源 SW2014/SW2021')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))


class IndexSwMember(Base):
	"""申万行业成分表"""
	__tablename__ = 'index_sw_member'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	l1_code = Column(String(20), comment='一级行业代码')
	l1_name = Column(String(100), comment='一级行业名称')
	l2_code = Column(String(20), comment='二级行业代码')
	l2_name = Column(String(100), comment='二级行业名称')
	l3_code = Column(String(20), comment='三级行业代码')
	l3_name = Column(String(100), comment='三级行业名称')
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	name = Column(String(100), comment='股票名称')
	in_date = Column(Date, comment='纳入日期')
	out_date = Column(Date, comment='剔除日期')
	is_new = Column(String(1), comment='是否最新 Y/N')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('l3_code', 'ts_code', 'in_date', name='uq_sw_member_unique'),
	)


class IndexSwDaily(Base):
	"""申万行业日线行情表"""
	__tablename__ = 'index_sw_daily'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='行业指数代码')
	trade_date = Column(DateTime, nullable=False, comment='交易日期')
	name = Column(String(100), comment='指数名称')
	open = Column(Numeric(12, 4), comment='开盘点位')
	low = Column(Numeric(12, 4), comment='最低点位')
	high = Column(Numeric(12, 4), comment='最高点位')
	close = Column(Numeric(12, 4), comment='收盘点位')
	change = Column(Numeric(12, 4), comment='涨跌点位')
	pct_change = Column(Numeric(8, 4), comment='涨跌幅')
	vol = Column(Numeric(18, 2), comment='成交量（万股）')
	amount = Column(Numeric(18, 2), comment='成交额（万元）')
	pe = Column(Numeric(12, 4), comment='市盈率')
	pb = Column(Numeric(12, 4), comment='市净率')
	float_mv = Column(Numeric(18, 2), comment='流通市值（万元）')
	total_mv = Column(Numeric(18, 2), comment='总市值（万元）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_sw_daily_unique'),
	)


class IndexDailyBasic(Base):
	"""大盘指数每日指标表"""
	__tablename__ = 'index_dailybasic'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='指数代码')
	trade_date = Column(Date, nullable=False, comment='交易日期')
	total_mv = Column(Numeric(18, 2), comment='总市值')
	float_mv = Column(Numeric(18, 2), comment='流通市值')
	total_share = Column(Numeric(18, 2), comment='总股本')
	float_share = Column(Numeric(18, 2), comment='流通股本')
	free_share = Column(Numeric(18, 2), comment='自由流通股本')
	turnover_rate = Column(Numeric(8, 4), comment='换手率(%)')
	turnover_rate_f = Column(Numeric(8, 4), comment='自由流通换手率(%)')
	pe = Column(Numeric(12, 4), comment='市盈率')
	pe_ttm = Column(Numeric(12, 4), comment='市盈率(TTM)')
	pb = Column(Numeric(12, 4), comment='市净率')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_index_dailybasic_unique'),
	)


class StockForecastPro(Base):
	"""券商盈利预测表"""
	__tablename__ = 'stock_forecast_pro'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	name = Column(String(100), comment='股票名称')
	report_date = Column(Date, comment='报告日期')
	report_title = Column(String(500), comment='报告标题')
	report_type = Column(String(50), comment='报告类型')
	classify = Column(String(50), comment='分类')
	org_name = Column(String(200), comment='机构名称')
	author_name = Column(String(100), comment='作者姓名')
	quarter = Column(String(10), comment='预测季度')
	op_rt = Column(Numeric(18, 4), comment='预测营业收入')
	op_pr = Column(Numeric(18, 4), comment='预测营业利润')
	tp = Column(Numeric(18, 4), comment='预测利润总额')
	np = Column(Numeric(18, 4), comment='预测净利润')
	eps = Column(Numeric(12, 4), comment='预测每股收益')
	pe = Column(Numeric(12, 4), comment='预测市盈率')
	rd = Column(Numeric(8, 4), comment='预测研发费用')
	roe = Column(Numeric(8, 4), comment='预测净资产收益率')
	ev_ebitda = Column(Numeric(12, 4), comment='预测EV/EBITDA')
	rating = Column(String(50), comment='评级')
	max_price = Column(Numeric(12, 4), comment='目标最高价')
	min_price = Column(Numeric(12, 4), comment='目标最低价')
	imp_dg = Column(String(50), comment='隐含涨幅')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'report_date', 'org_name', 'quarter', name='uq_forecast_pro_unique'),
	)


class StockMoneyflowHsgt(Base):
	"""沪深港通资金流向表"""
	__tablename__ = 'stock_moneyflow_hsgt'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	trade_date = Column(Date, nullable=False, comment='交易日期')
	ggt_ss = Column(Numeric(18, 2), comment='港股通（上海）')
	ggt_sz = Column(Numeric(18, 2), comment='港股通（深圳）')
	hgt = Column(Numeric(18, 2), comment='沪股通')
	sgt = Column(Numeric(18, 2), comment='深股通')
	north_money = Column(Numeric(18, 2), comment='北向资金')
	south_money = Column(Numeric(18, 2), comment='南向资金')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('trade_date', name='uq_moneyflow_hsgt_date'),
	)


# ==================== Phase 4 新增 ====================


class IndexWeekly(Base):
	"""指数周线行情表"""
	__tablename__ = 'index_weekly'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS指数代码')
	trade_date = Column(DateTime, nullable=False, comment='交易日')
	close = Column(Numeric(12, 4), comment='收盘点位')
	open = Column(Numeric(12, 4), comment='开盘点位')
	high = Column(Numeric(12, 4), comment='最高点位')
	low = Column(Numeric(12, 4), comment='最低点位')
	pre_close = Column(Numeric(12, 4), comment='昨日收盘点')
	change = Column(Numeric(12, 4), comment='涨跌点位')
	pct_chg = Column(Numeric(8, 4), comment='涨跌幅')
	vol = Column(Numeric(18, 2), comment='成交量（手）')
	amount = Column(Numeric(18, 2), comment='成交额（千元）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_index_weekly_unique'),
	)


class StockFactorDaily(Base):
	"""股票技术因子基础版表（~33列，不复权指标）"""
	__tablename__ = 'stock_factor_daily'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	trade_date = Column(DateTime, nullable=False, comment='交易日期')
	close = Column(Numeric(12, 4), comment='收盘价')
	open = Column(Numeric(12, 4), comment='开盘价')
	high = Column(Numeric(12, 4), comment='最高价')
	low = Column(Numeric(12, 4), comment='最低价')
	pre_close = Column(Numeric(12, 4), comment='前收盘价')
	change = Column(Numeric(12, 4), comment='涨跌额')
	pct_change = Column(Numeric(8, 4), comment='涨跌幅')
	vol = Column(Numeric(18, 2), comment='成交量（手）')
	amount = Column(Numeric(18, 2), comment='成交额（千元）')
	adj_factor = Column(Numeric(18, 6), comment='复权因子')
	open_hfq = Column(Numeric(18, 6), comment='开盘价（后复权）')
	open_qfq = Column(Numeric(18, 6), comment='开盘价（前复权）')
	close_hfq = Column(Numeric(18, 6), comment='收盘价（后复权）')
	close_qfq = Column(Numeric(18, 6), comment='收盘价（前复权）')
	high_hfq = Column(Numeric(18, 6), comment='最高价（后复权）')
	high_qfq = Column(Numeric(18, 6), comment='最高价（前复权）')
	low_hfq = Column(Numeric(18, 6), comment='最低价（后复权）')
	low_qfq = Column(Numeric(18, 6), comment='最低价（前复权）')
	pre_close_hfq = Column(Numeric(18, 6), comment='前收盘价（后复权）')
	pre_close_qfq = Column(Numeric(18, 6), comment='前收盘价（前复权）')
	macd_dif = Column(Numeric(18, 6), comment='MACD DIF值')
	macd_dea = Column(Numeric(18, 6), comment='MACD DEA值')
	macd = Column(Numeric(18, 6), comment='MACD柱值')
	kdj_k = Column(Numeric(18, 6), comment='KDJ K值')
	kdj_d = Column(Numeric(18, 6), comment='KDJ D值')
	kdj_j = Column(Numeric(18, 6), comment='KDJ J值')
	rsi_6 = Column(Numeric(18, 6), comment='RSI 6日')
	rsi_12 = Column(Numeric(18, 6), comment='RSI 12日')
	rsi_24 = Column(Numeric(18, 6), comment='RSI 24日')
	boll_upper = Column(Numeric(18, 6), comment='BOLL上轨')
	boll_mid = Column(Numeric(18, 6), comment='BOLL中轨')
	boll_lower = Column(Numeric(18, 6), comment='BOLL下轨')
	cci = Column(Numeric(18, 6), comment='CCI商品通道指数（不复权）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_factor_daily_unique'),
	)


class StockFactorProDaily(Base):
	"""股票技术因子专业版表（200+列，含三复权版本的所有技术指标）"""
	__tablename__ = 'stock_factor_pro_daily'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='TS股票代码')
	trade_date = Column(DateTime, nullable=False, comment='交易日期')
	# 基础行情
	open = Column(Numeric(18, 6), comment='开盘价')
	high = Column(Numeric(18, 6), comment='最高价')
	low = Column(Numeric(18, 6), comment='最低价')
	close = Column(Numeric(18, 6), comment='收盘价')
	pre_close = Column(Numeric(18, 6), comment='前收盘价')
	change = Column(Numeric(18, 6), comment='涨跌额')
	pct_chg = Column(Numeric(8, 4), comment='涨跌幅')
	vol = Column(Numeric(18, 2), comment='成交量（手）')
	amount = Column(Numeric(18, 2), comment='成交额（千元）')
	# 复权价格（后复权/前复权）
	open_hfq = Column(Numeric(12, 4), comment='开盘价（后复权）')
	open_qfq = Column(Numeric(12, 4), comment='开盘价（前复权）')
	high_hfq = Column(Numeric(12, 4), comment='最高价（后复权）')
	high_qfq = Column(Numeric(12, 4), comment='最高价（前复权）')
	low_hfq = Column(Numeric(12, 4), comment='最低价（后复权）')
	low_qfq = Column(Numeric(12, 4), comment='最低价（前复权）')
	close_hfq = Column(Numeric(12, 4), comment='收盘价（后复权）')
	close_qfq = Column(Numeric(12, 4), comment='收盘价（前复权）')
	pre_close_hfq = Column(Numeric(12, 4), comment='前收盘价（后复权）')
	pre_close_qfq = Column(Numeric(12, 4), comment='前收盘价（前复权）')
	# 估值与股本
	turnover_rate = Column(Numeric(8, 4), comment='换手率(%)')
	turnover_rate_f = Column(Numeric(8, 4), comment='自由流通换手率(%)')
	volume_ratio = Column(Numeric(8, 4), comment='量比')
	pe = Column(Numeric(18, 6), comment='市盈率')
	pe_ttm = Column(Numeric(18, 6), comment='市盈率(TTM)')
	pb = Column(Numeric(18, 6), comment='市净率')
	ps = Column(Numeric(18, 6), comment='市销率')
	ps_ttm = Column(Numeric(18, 6), comment='市销率(TTM)')
	dv_ratio = Column(Numeric(8, 4), comment='股息率(%)')
	dv_ttm = Column(Numeric(8, 4), comment='股息率(TTM)')
	total_share = Column(Numeric(18, 2), comment='总股本（万股）')
	float_share = Column(Numeric(18, 2), comment='流通股本（万股）')
	free_share = Column(Numeric(18, 2), comment='自由流通股本（万股）')
	total_mv = Column(Numeric(18, 2), comment='总市值（万元）')
	circ_mv = Column(Numeric(18, 2), comment='流通市值（万元）')
	adj_factor = Column(Numeric(18, 6), comment='复权因子')
	# ASI 振动升降指标
	asi_bfq = Column(Numeric(18, 6)); asi_hfq = Column(Numeric(18, 6)); asi_qfq = Column(Numeric(18, 6))
	asit_bfq = Column(Numeric(18, 6)); asit_hfq = Column(Numeric(18, 6)); asit_qfq = Column(Numeric(18, 6))
	# ATR 真实波幅
	atr_bfq = Column(Numeric(18, 6)); atr_hfq = Column(Numeric(18, 6)); atr_qfq = Column(Numeric(18, 6))
	# BBI 多空指数
	bbi_bfq = Column(Numeric(18, 6)); bbi_hfq = Column(Numeric(18, 6)); bbi_qfq = Column(Numeric(18, 6))
	# BIAS 乖离率
	bias1_bfq = Column(Numeric(18, 6)); bias1_hfq = Column(Numeric(18, 6)); bias1_qfq = Column(Numeric(18, 6))
	bias2_bfq = Column(Numeric(18, 6)); bias2_hfq = Column(Numeric(18, 6)); bias2_qfq = Column(Numeric(18, 6))
	bias3_bfq = Column(Numeric(18, 6)); bias3_hfq = Column(Numeric(18, 6)); bias3_qfq = Column(Numeric(18, 6))
	# BOLL 布林带
	boll_upper_bfq = Column(Numeric(18, 6)); boll_upper_hfq = Column(Numeric(18, 6)); boll_upper_qfq = Column(Numeric(18, 6))
	boll_mid_bfq = Column(Numeric(18, 6)); boll_mid_hfq = Column(Numeric(18, 6)); boll_mid_qfq = Column(Numeric(18, 6))
	boll_lower_bfq = Column(Numeric(18, 6)); boll_lower_hfq = Column(Numeric(18, 6)); boll_lower_qfq = Column(Numeric(18, 6))
	# BRAR 情绪指标
	brar_ar_bfq = Column(Numeric(18, 6)); brar_ar_hfq = Column(Numeric(18, 6)); brar_ar_qfq = Column(Numeric(18, 6))
	brar_br_bfq = Column(Numeric(18, 6)); brar_br_hfq = Column(Numeric(18, 6)); brar_br_qfq = Column(Numeric(18, 6))
	# CCI 商品通道指数
	cci_bfq = Column(Numeric(18, 6)); cci_hfq = Column(Numeric(18, 6)); cci_qfq = Column(Numeric(18, 6))
	# CR 能量指标
	cr_bfq = Column(Numeric(18, 6)); cr_hfq = Column(Numeric(18, 6)); cr_qfq = Column(Numeric(18, 6))
	# DFMA 动向平均
	dfma_dif_bfq = Column(Numeric(18, 6)); dfma_dif_hfq = Column(Numeric(18, 6)); dfma_dif_qfq = Column(Numeric(18, 6))
	dfma_difma_bfq = Column(Numeric(18, 6)); dfma_difma_hfq = Column(Numeric(18, 6)); dfma_difma_qfq = Column(Numeric(18, 6))
	# DMI 趋向指标
	dmi_adx_bfq = Column(Numeric(18, 6)); dmi_adx_hfq = Column(Numeric(18, 6)); dmi_adx_qfq = Column(Numeric(18, 6))
	dmi_adxr_bfq = Column(Numeric(18, 6)); dmi_adxr_hfq = Column(Numeric(18, 6)); dmi_adxr_qfq = Column(Numeric(18, 6))
	dmi_mdi_bfq = Column(Numeric(18, 6)); dmi_mdi_hfq = Column(Numeric(18, 6)); dmi_mdi_qfq = Column(Numeric(18, 6))
	dmi_pdi_bfq = Column(Numeric(18, 6)); dmi_pdi_hfq = Column(Numeric(18, 6)); dmi_pdi_qfq = Column(Numeric(18, 6))
	# 涨跌天数
	downdays = Column(Numeric(8, 2), comment='下跌天数')
	updays = Column(Numeric(8, 2), comment='上涨天数')
	# DPO 区间震荡线
	dpo_bfq = Column(Numeric(18, 6)); dpo_hfq = Column(Numeric(18, 6)); dpo_qfq = Column(Numeric(18, 6))
	madpo_bfq = Column(Numeric(18, 6)); madpo_hfq = Column(Numeric(18, 6)); madpo_qfq = Column(Numeric(18, 6))
	# EMA 指数移动平均
	ema_5_bfq = Column(Numeric(18, 6)); ema_5_hfq = Column(Numeric(18, 6)); ema_5_qfq = Column(Numeric(18, 6))
	ema_10_bfq = Column(Numeric(18, 6)); ema_10_hfq = Column(Numeric(18, 6)); ema_10_qfq = Column(Numeric(18, 6))
	ema_20_bfq = Column(Numeric(18, 6)); ema_20_hfq = Column(Numeric(18, 6)); ema_20_qfq = Column(Numeric(18, 6))
	ema_30_bfq = Column(Numeric(18, 6)); ema_30_hfq = Column(Numeric(18, 6)); ema_30_qfq = Column(Numeric(18, 6))
	ema_60_bfq = Column(Numeric(18, 6)); ema_60_hfq = Column(Numeric(18, 6)); ema_60_qfq = Column(Numeric(18, 6))
	ema_90_bfq = Column(Numeric(18, 6)); ema_90_hfq = Column(Numeric(18, 6)); ema_90_qfq = Column(Numeric(18, 6))
	ema_250_bfq = Column(Numeric(18, 6)); ema_250_hfq = Column(Numeric(18, 6)); ema_250_qfq = Column(Numeric(18, 6))
	# EMV 简易波动指标
	emv_bfq = Column(Numeric(18, 6)); emv_hfq = Column(Numeric(18, 6)); emv_qfq = Column(Numeric(18, 6))
	maemv_bfq = Column(Numeric(18, 6)); maemv_hfq = Column(Numeric(18, 6)); maemv_qfq = Column(Numeric(18, 6))
	# EXPMA 指数平均线
	expma_12_bfq = Column(Numeric(18, 6)); expma_12_hfq = Column(Numeric(18, 6)); expma_12_qfq = Column(Numeric(18, 6))
	expma_50_bfq = Column(Numeric(18, 6)); expma_50_hfq = Column(Numeric(18, 6)); expma_50_qfq = Column(Numeric(18, 6))
	# KDJ 随机指标
	kdj_k_bfq = Column(Numeric(18, 6)); kdj_k_hfq = Column(Numeric(18, 6)); kdj_k_qfq = Column(Numeric(18, 6))
	kdj_d_bfq = Column(Numeric(18, 6)); kdj_d_hfq = Column(Numeric(18, 6)); kdj_d_qfq = Column(Numeric(18, 6))
	kdj_j_bfq = Column(Numeric(18, 6)); kdj_j_hfq = Column(Numeric(18, 6)); kdj_j_qfq = Column(Numeric(18, 6))
	# KTN 肯特纳通道
	ktn_down_bfq = Column(Numeric(18, 6)); ktn_down_hfq = Column(Numeric(18, 6)); ktn_down_qfq = Column(Numeric(18, 6))
	ktn_mid_bfq = Column(Numeric(18, 6)); ktn_mid_hfq = Column(Numeric(18, 6)); ktn_mid_qfq = Column(Numeric(18, 6))
	ktn_upper_bfq = Column(Numeric(18, 6)); ktn_upper_hfq = Column(Numeric(18, 6)); ktn_upper_qfq = Column(Numeric(18, 6))
	# 极端天数
	lowdays = Column(Numeric(8, 2), comment='低位天数')
	topdays = Column(Numeric(8, 2), comment='高位天数')
	# MA 移动平均
	ma_5_bfq = Column(Numeric(18, 6)); ma_5_hfq = Column(Numeric(18, 6)); ma_5_qfq = Column(Numeric(18, 6))
	ma_10_bfq = Column(Numeric(18, 6)); ma_10_hfq = Column(Numeric(18, 6)); ma_10_qfq = Column(Numeric(18, 6))
	ma_20_bfq = Column(Numeric(18, 6)); ma_20_hfq = Column(Numeric(18, 6)); ma_20_qfq = Column(Numeric(18, 6))
	ma_30_bfq = Column(Numeric(18, 6)); ma_30_hfq = Column(Numeric(18, 6)); ma_30_qfq = Column(Numeric(18, 6))
	ma_60_bfq = Column(Numeric(18, 6)); ma_60_hfq = Column(Numeric(18, 6)); ma_60_qfq = Column(Numeric(18, 6))
	ma_90_bfq = Column(Numeric(18, 6)); ma_90_hfq = Column(Numeric(18, 6)); ma_90_qfq = Column(Numeric(18, 6))
	ma_250_bfq = Column(Numeric(18, 6)); ma_250_hfq = Column(Numeric(18, 6)); ma_250_qfq = Column(Numeric(18, 6))
	# MACD
	macd_dif_bfq = Column(Numeric(18, 6)); macd_dif_hfq = Column(Numeric(18, 6)); macd_dif_qfq = Column(Numeric(18, 6))
	macd_dea_bfq = Column(Numeric(18, 6)); macd_dea_hfq = Column(Numeric(18, 6)); macd_dea_qfq = Column(Numeric(18, 6))
	macd_bfq = Column(Numeric(18, 6)); macd_hfq = Column(Numeric(18, 6)); macd_qfq = Column(Numeric(18, 6))
	# MASS 梅斯线
	mass_bfq = Column(Numeric(18, 6)); mass_hfq = Column(Numeric(18, 6)); mass_qfq = Column(Numeric(18, 6))
	ma_mass_bfq = Column(Numeric(18, 6)); ma_mass_hfq = Column(Numeric(18, 6)); ma_mass_qfq = Column(Numeric(18, 6))
	# MFI 资金流量指标
	mfi_bfq = Column(Numeric(18, 6)); mfi_hfq = Column(Numeric(18, 6)); mfi_qfq = Column(Numeric(18, 6))
	# MTM 动量线
	mtm_bfq = Column(Numeric(18, 6)); mtm_hfq = Column(Numeric(18, 6)); mtm_qfq = Column(Numeric(18, 6))
	mtmma_bfq = Column(Numeric(18, 6)); mtmma_hfq = Column(Numeric(18, 6)); mtmma_qfq = Column(Numeric(18, 6))
	# OBV 能量潮
	obv_bfq = Column(Numeric(18, 6)); obv_hfq = Column(Numeric(18, 6)); obv_qfq = Column(Numeric(18, 6))
	# PSY 心理线
	psy_bfq = Column(Numeric(18, 6)); psy_hfq = Column(Numeric(18, 6)); psy_qfq = Column(Numeric(18, 6))
	psyma_bfq = Column(Numeric(18, 6)); psyma_hfq = Column(Numeric(18, 6)); psyma_qfq = Column(Numeric(18, 6))
	# ROC 变动率
	roc_bfq = Column(Numeric(18, 6)); roc_hfq = Column(Numeric(18, 6)); roc_qfq = Column(Numeric(18, 6))
	maroc_bfq = Column(Numeric(18, 6)); maroc_hfq = Column(Numeric(18, 6)); maroc_qfq = Column(Numeric(18, 6))
	# RSI 相对强弱指标
	rsi_6_bfq = Column(Numeric(18, 6)); rsi_6_hfq = Column(Numeric(18, 6)); rsi_6_qfq = Column(Numeric(18, 6))
	rsi_12_bfq = Column(Numeric(18, 6)); rsi_12_hfq = Column(Numeric(18, 6)); rsi_12_qfq = Column(Numeric(18, 6))
	rsi_24_bfq = Column(Numeric(18, 6)); rsi_24_hfq = Column(Numeric(18, 6)); rsi_24_qfq = Column(Numeric(18, 6))
	# TAQ 三均线
	taq_down_bfq = Column(Numeric(18, 6)); taq_down_hfq = Column(Numeric(18, 6)); taq_down_qfq = Column(Numeric(18, 6))
	taq_mid_bfq = Column(Numeric(18, 6)); taq_mid_hfq = Column(Numeric(18, 6)); taq_mid_qfq = Column(Numeric(18, 6))
	taq_up_bfq = Column(Numeric(18, 6)); taq_up_hfq = Column(Numeric(18, 6)); taq_up_qfq = Column(Numeric(18, 6))
	# TRIX 三重指数平滑平均线
	trix_bfq = Column(Numeric(18, 6)); trix_hfq = Column(Numeric(18, 6)); trix_qfq = Column(Numeric(18, 6))
	trma_bfq = Column(Numeric(18, 6)); trma_hfq = Column(Numeric(18, 6)); trma_qfq = Column(Numeric(18, 6))
	# VR 容量比率
	vr_bfq = Column(Numeric(18, 6)); vr_hfq = Column(Numeric(18, 6)); vr_qfq = Column(Numeric(18, 6))
	# WR 威廉指标
	wr6_bfq = Column(Numeric(18, 6)); wr6_hfq = Column(Numeric(18, 6)); wr6_qfq = Column(Numeric(18, 6))
	wr10_bfq = Column(Numeric(18, 6)); wr10_hfq = Column(Numeric(18, 6)); wr10_qfq = Column(Numeric(18, 6))
	# XSII 薛斯通道
	xsii_td1_bfq = Column(Numeric(18, 6)); xsii_td1_hfq = Column(Numeric(18, 6)); xsii_td1_qfq = Column(Numeric(18, 6))
	xsii_td2_bfq = Column(Numeric(18, 6)); xsii_td2_hfq = Column(Numeric(18, 6)); xsii_td2_qfq = Column(Numeric(18, 6))
	xsii_td3_bfq = Column(Numeric(18, 6)); xsii_td3_hfq = Column(Numeric(18, 6)); xsii_td3_qfq = Column(Numeric(18, 6))
	xsii_td4_bfq = Column(Numeric(18, 6)); xsii_td4_hfq = Column(Numeric(18, 6)); xsii_td4_qfq = Column(Numeric(18, 6))
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_stock_factor_pro_daily_unique'),
	)


class IndexFactorProDaily(Base):
	"""指数技术因子专业版（Tushare idx_factor_pro 接口）

	包含 200+ 列技术指标，仅含后复权(_bfq)版本。
	与 StockFactorProDaily 接口类似，但数据源为指数而非个股。
	需 Tushare 5000 积分以上权限。
	"""
	__tablename__ = 'index_factor_pro_daily'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	ts_code = Column(String(20), nullable=False, index=True, comment='指数代码')
	trade_date = Column(DateTime, nullable=False, comment='交易日期')
	# 基础行情
	open = Column(Numeric(18, 6), comment='开盘价')
	high = Column(Numeric(18, 6), comment='最高价')
	low = Column(Numeric(18, 6), comment='最低价')
	close = Column(Numeric(18, 6), comment='收盘价')
	pre_close = Column(Numeric(18, 6), comment='前收盘价')
	change = Column(Numeric(18, 6), comment='涨跌额')
	pct_change = Column(Numeric(8, 4), comment='涨跌幅')
	vol = Column(Numeric(18, 2), comment='成交量（手）')
	amount = Column(Numeric(18, 2), comment='成交额（千元）')
	# ASI 振动升降指标
	asi_bfq = Column(Numeric(18, 6))
	asit_bfq = Column(Numeric(18, 6))
	# ATR 真实波幅
	atr_bfq = Column(Numeric(18, 6))
	# BBI 多空指数
	bbi_bfq = Column(Numeric(18, 6))
	# BIAS 乖离率
	bias1_bfq = Column(Numeric(18, 6))
	bias2_bfq = Column(Numeric(18, 6))
	bias3_bfq = Column(Numeric(18, 6))
	# BOLL 布林带
	boll_lower_bfq = Column(Numeric(18, 6))
	boll_mid_bfq = Column(Numeric(18, 6))
	boll_upper_bfq = Column(Numeric(18, 6))
	# BRAR 情绪指标
	brar_ar_bfq = Column(Numeric(18, 6))
	brar_br_bfq = Column(Numeric(18, 6))
	# CCI 商品通道指数
	cci_bfq = Column(Numeric(18, 6))
	# CR 能量指标
	cr_bfq = Column(Numeric(18, 6))
	# DFMA 动向平均
	dfma_dif_bfq = Column(Numeric(18, 6))
	dfma_difma_bfq = Column(Numeric(18, 6))
	# DMI 趋向指标
	dmi_adx_bfq = Column(Numeric(18, 6))
	dmi_adxr_bfq = Column(Numeric(18, 6))
	dmi_mdi_bfq = Column(Numeric(18, 6))
	dmi_pdi_bfq = Column(Numeric(18, 6))
	# 涨跌天数
	downdays = Column(Numeric(8, 2), comment='下跌天数')
	updays = Column(Numeric(8, 2), comment='上涨天数')
	# DPO 区间震荡线
	dpo_bfq = Column(Numeric(18, 6))
	madpo_bfq = Column(Numeric(18, 6))
	# EMA 指数移动平均
	ema_bfq_5 = Column(Numeric(18, 6))
	ema_bfq_10 = Column(Numeric(18, 6))
	ema_bfq_20 = Column(Numeric(18, 6))
	ema_bfq_30 = Column(Numeric(18, 6))
	ema_bfq_60 = Column(Numeric(18, 6))
	ema_bfq_90 = Column(Numeric(18, 6))
	ema_bfq_250 = Column(Numeric(18, 6))
	# EMV 简易波动指标
	emv_bfq = Column(Numeric(18, 6))
	maemv_bfq = Column(Numeric(18, 6))
	# EXPMA 指数平均线
	expma_12_bfq = Column(Numeric(18, 6))
	expma_50_bfq = Column(Numeric(18, 6))
	# KDJ 随机指标
	kdj_k_bfq = Column(Numeric(18, 6))
	kdj_d_bfq = Column(Numeric(18, 6))
	kdj_bfq = Column(Numeric(18, 6))
	# KTN 肯特纳通道
	ktn_down_bfq = Column(Numeric(18, 6))
	ktn_mid_bfq = Column(Numeric(18, 6))
	ktn_upper_bfq = Column(Numeric(18, 6))
	# 极端天数
	lowdays = Column(Numeric(8, 2), comment='低位天数')
	topdays = Column(Numeric(8, 2), comment='高位天数')
	# MA 移动平均
	ma_bfq_5 = Column(Numeric(18, 6))
	ma_bfq_10 = Column(Numeric(18, 6))
	ma_bfq_20 = Column(Numeric(18, 6))
	ma_bfq_30 = Column(Numeric(18, 6))
	ma_bfq_60 = Column(Numeric(18, 6))
	ma_bfq_90 = Column(Numeric(18, 6))
	ma_bfq_250 = Column(Numeric(18, 6))
	# MACD
	macd_dif_bfq = Column(Numeric(18, 6))
	macd_dea_bfq = Column(Numeric(18, 6))
	macd_bfq = Column(Numeric(18, 6))
	# MASS 梅斯线
	mass_bfq = Column(Numeric(18, 6))
	ma_mass_bfq = Column(Numeric(18, 6))
	# MFI 资金流量指标
	mfi_bfq = Column(Numeric(18, 6))
	# MTM 动量线
	mtm_bfq = Column(Numeric(18, 6))
	mtmma_bfq = Column(Numeric(18, 6))
	# OBV 能量潮
	obv_bfq = Column(Numeric(18, 6))
	# PSY 心理线
	psy_bfq = Column(Numeric(18, 6))
	psyma_bfq = Column(Numeric(18, 6))
	# ROC 变动率
	roc_bfq = Column(Numeric(18, 6))
	maroc_bfq = Column(Numeric(18, 6))
	# RSI 相对强弱指标
	rsi_bfq_6 = Column(Numeric(18, 6))
	rsi_bfq_12 = Column(Numeric(18, 6))
	rsi_bfq_24 = Column(Numeric(18, 6))
	# TAQ 三均线
	taq_down_bfq = Column(Numeric(18, 6))
	taq_mid_bfq = Column(Numeric(18, 6))
	taq_up_bfq = Column(Numeric(18, 6))
	# TRIX 三重指数平滑平均线
	trix_bfq = Column(Numeric(18, 6))
	trma_bfq = Column(Numeric(18, 6))
	# VR 容量比率
	vr_bfq = Column(Numeric(18, 6))
	# WR 威廉指标
	wr_bfq = Column(Numeric(18, 6))
	wr1_bfq = Column(Numeric(18, 6))
	# XSII 薛斯通道
	xsii_td1_bfq = Column(Numeric(18, 6))
	xsii_td2_bfq = Column(Numeric(18, 6))
	xsii_td3_bfq = Column(Numeric(18, 6))
	xsii_td4_bfq = Column(Numeric(18, 6))
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		UniqueConstraint('ts_code', 'trade_date', name='uq_idx_factor_pro_daily_unique'),
	)
