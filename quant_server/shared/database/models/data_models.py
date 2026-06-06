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
	financial_statements = relationship("FinancialStatement", back_populates="stock", cascade="all, delete-orphan")
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
	ann_date = Column(DateTime, nullable=False, comment='公告日期')
	name = Column(String(50), nullable=False, comment='姓名')
	gender = Column(String(1), comment='性别：M-男，F-女')
	lev = Column(String(20), comment='职位类别')
	title = Column(String(100), nullable=False, comment='职位')
	edu = Column(String(20), comment='学历')
	national = Column(String(20), comment='国籍')
	birthday = Column(DateTime, comment='出生日期')
	begin_date = Column(DateTime, comment='任职开始日期')
	end_date = Column(DateTime, comment='任职结束日期')
	resume = Column(Text, comment='个人简历')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	company = relationship("StockCompany", back_populates="managers")
	# rewards relationship removed — StkReward now has direct ts_code FK


class StkReward(Base):
	"""管理层薪酬与持股明细表"""
	__tablename__ = 'stk_rewards'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='薪酬ID')
	ts_code = Column(String(20), ForeignKey('stock_company.ts_code'), nullable=False, index=True,
                 comment='TS股票代码')
	ann_date = Column(DateTime, nullable=False, comment='公告日期')
	end_date = Column(DateTime, nullable=False, comment='截止日期')
	name = Column(String(50), nullable=False, comment='高层姓名')
	title = Column(String(100), nullable=False, comment='担任职务')
	reward = Column(Numeric(18, 2), nullable=False, comment='报酬')
	hold_vol = Column(BigInteger, nullable=False, comment='持股数')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# manager relationship removed — StkReward now uses direct ts_code FK


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
	change = Column(Numeric(9, 3), nullable=False, comment='涨跌额')
	pct_chg = Column(Numeric(7, 4), nullable=False, comment='涨跌幅（百分比）')
	vol = Column(BigInteger, nullable=False, comment='成交量（手）')
	amount = Column(Numeric(14, 4), nullable=False, comment='成交额（千元）')
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
	amount = Column(Numeric(16, 4), nullable=False, comment='成交额')
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
	amount = Column(Numeric(16, 4), nullable=False, comment='成交额')
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
	amount = Column(Numeric(16, 4), nullable=False, comment='成交额')
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
	amount = Column(Numeric(16, 4), nullable=False, comment='成交额')
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
	pre_close = Column(Numeric(9, 4), nullable=False, comment='前收盘价')
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
	buy_sm_vol = Column(Integer, nullable=False, comment='小单买入量（手）')
	buy_sm_amount = Column(Numeric(12, 4), nullable=False, comment='小单买入金额（万元）')
	sell_sm_vol = Column(Integer, nullable=False, comment='小单卖出量（手）')
	sell_sm_amount = Column(Numeric(12, 4), nullable=False, comment='小单卖出金额（万元）')
	buy_md_vol = Column(Integer, nullable=False, comment='中单买入量（手）')
	buy_md_amount = Column(Numeric(12, 4), nullable=False, comment='中单买入金额（万元）')
	sell_md_vol = Column(Integer, nullable=False, comment='中单卖出量（手）')
	sell_md_amount = Column(Numeric(12, 4), nullable=False, comment='中单卖出金额（万元）')
	buy_lg_vol = Column(Integer, nullable=False, comment='大单买入量（手）')
	buy_lg_amount = Column(Numeric(12, 4), nullable=False, comment='大单买入金额（万元）')
	sell_lg_vol = Column(Integer, nullable=False, comment='大单卖出量（手）')
	sell_lg_amount = Column(Numeric(12, 4), nullable=False, comment='大单卖出金额（万元）')
	buy_elg_vol = Column(Integer, nullable=False, comment='特大单买入量（手）')
	buy_elg_amount = Column(Numeric(12, 4), nullable=False, comment='特大单买入金额（万元）')
	sell_elg_vol = Column(Integer, nullable=False, comment='特大单卖出量（手）')
	sell_elg_amount = Column(Numeric(12, 4), nullable=False, comment='特大单卖出金额（万元）')
	net_mf_vol = Column(Integer, nullable=False, comment='净流入量（手）')
	net_mf_amount = Column(Numeric(12, 4), nullable=False, comment='净流入金额（万元）')
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

class FinancialStatement(Base):
	"""上市公司财务报表数据"""
	__tablename__ = 'financial_statements'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='财务报表ID')
	ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), nullable=False, index=True, comment='TS代码')
	ann_date = Column(DateTime, nullable=False, index=True, comment='公告日期')
	f_ann_date = Column(DateTime, comment='实际公告日期（Tushare新接口，部分公司会延迟公告）')
	end_date = Column(DateTime, nullable=False, comment='报告期')
	report_type = Column(String(20), nullable=False, comment='报告类型：Q1-一季报，S1-半年报，Q3-三季报，A-年报')
	comp_type = Column(String(20), comment='公司类型：一般企业、银行、保险、证券')
	basic_eps = Column(Numeric(12, 4), comment='基本每股收益')
	diluted_eps = Column(Numeric(12, 4), comment='稀释每股收益')
	total_revenue = Column(Numeric(18, 4), comment='营业总收入')
	revenue = Column(Numeric(18, 4), comment='营业收入')
	int_income = Column(Numeric(18, 4), comment='利息收入')
	prem_earned = Column(Numeric(18, 4), comment='已赚保费')
	comm_income = Column(Numeric(18, 4), comment='手续费及佣金收入')
	n_commis_income = Column(Numeric(18, 4), comment='手续费及佣金净收入')
	n_oth_income = Column(Numeric(18, 4), comment='其他业务净收入')
	n_oth_b_income = Column(Numeric(18, 4), comment='其他业务利润')
	prem_income = Column(Numeric(18, 4), comment='保费业务收入')
	out_prem = Column(Numeric(18, 4), comment='分出保费')
	une_prem_reser = Column(Numeric(18, 4), comment='未到期责任准备金')
	reins_income = Column(Numeric(18, 4), comment='分保费收入')
	n_sec_tb_income = Column(Numeric(18, 4), comment='代理买卖证券业务净收入')
	n_sec_uw_income = Column(Numeric(18, 4), comment='证券承销业务净收入')
	n_asset_mg_income = Column(Numeric(18, 4), comment='受托客户资产管理业务净收入')
	oth_b_income = Column(Numeric(18, 4), comment='其他业务收入')
	fv_value_chg_gain = Column(Numeric(18, 4), comment='公允价值变动收益')
	invest_income = Column(Numeric(18, 4), comment='投资收益')
	ass_invest_income = Column(Numeric(18, 4), comment='其中:对联营企业和合营企业的投资收益')
	forex_gain = Column(Numeric(18, 4), comment='汇兑收益')
	total_cogs = Column(Numeric(18, 4), comment='营业总成本')
	oper_cost = Column(Numeric(18, 4), comment='营业成本')
	int_exp = Column(Numeric(18, 4), comment='利息支出')
	comm_exp = Column(Numeric(18, 4), comment='手续费及佣金支出')
	biz_tax_surchg = Column(Numeric(18, 4), comment='营业税金及附加')
	sell_exp = Column(Numeric(18, 4), comment='销售费用')
	admin_exp = Column(Numeric(18, 4), comment='管理费用')
	fin_exp = Column(Numeric(18, 4), comment='财务费用')
	assets_impair_loss = Column(Numeric(18, 4), comment='资产减值损失')
	prem_refund = Column(Numeric(18, 4), comment='退保金')
	compen_payout = Column(Numeric(18, 4), comment='赔付支出')
	reser_insur_liab = Column(Numeric(18, 4), comment='提取保险合同准备金净额')
	div_payt = Column(Numeric(18, 4), comment='分红')
	reins_exp = Column(Numeric(18, 4), comment='分保费用')
	oper_exp = Column(Numeric(18, 4), comment='营业支出')
	compens_payout = Column(Numeric(18, 4), comment='赔付支出净额')
	insur_reser = Column(Numeric(18, 4), comment='提取保险责任准备金')
	reinsur_payout = Column(Numeric(18, 4), comment='分保赔付支出')
	misc_exp = Column(Numeric(18, 4), comment='其他')
	operate_profit = Column(Numeric(18, 4), comment='营业利润')
	non_oper_income = Column(Numeric(18, 4), comment='营业外收入')
	non_oper_exp = Column(Numeric(18, 4), comment='营业外支出')
	nca_disploss = Column(Numeric(18, 4), comment='非流动资产处置损失')
	total_profit = Column(Numeric(18, 4), comment='利润总额')
	income_tax = Column(Numeric(18, 4), comment='所得税费用')
	n_income = Column(Numeric(18, 4), comment='净利润')
	n_income_attr_p = Column(Numeric(18, 4), comment='归属于母公司所有者的净利润')
	minority_gain = Column(Numeric(18, 4), comment='少数股东损益')
	oth_compr_income = Column(Numeric(18, 4), comment='其他综合收益')
	t_compr_income = Column(Numeric(18, 4), comment='综合收益总额')
	compr_inc_attr_p = Column(Numeric(18, 4), comment='归属于母公司所有者的综合收益总额')
	compr_inc_attr_m_s = Column(Numeric(18, 4), comment='归属于少数股东的综合收益总额')
	ebit = Column(Numeric(18, 4), comment='息税前利润')
	ebitda = Column(Numeric(18, 4), comment='息税折旧摊销前利润')
	insurance_exp = Column(Numeric(18, 4), comment='保险业务支出')
	undist_profit = Column(Numeric(18, 4), comment='年初未分配利润')
	distable_profit = Column(Numeric(18, 4), comment='可分配利润')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	stock = relationship("StockBasic", back_populates="financial_statements")

	# 索引
	__table_args__ = (
		UniqueConstraint('ts_code', 'ann_date', 'report_type', name='uq_financial_statement_code_date_type'),
		Index('idx_financial_statement_end_date', 'end_date'),
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
	amount = Column(Numeric(16, 4), nullable=False, comment='成交额')
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
	ts_code = Column(String(20), ForeignKey('stock_basic.ts_code', ondelete='CASCADE'), nullable=False, comment='股票代码，关联 stock_basic.ts_code')
	weight = Column(Numeric(12, 8), comment='成分股权重（小数形式，如 0.0352 表示 3.52%）')
	trade_date = Column(Date, nullable=False, comment='权重生效日期')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

	# 关联关系 — 使用 backref 避免修改 IndexBasic / StockBasic
	index = relationship("IndexBasic", backref="index_weights")
	stock = relationship("StockBasic", backref="index_weights")

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
	"""业绩预告数据表"""
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
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	__table_args__ = (
		Index('idx_stock_forecasts_ts_code', 'ts_code'),
		Index('idx_stock_forecasts_ann_date', 'ann_date'),
		UniqueConstraint('ts_code', 'ann_date', name='uq_forecasts_ts_ann'),
	)


class StockExpress(Base):
	"""业绩快报数据表"""
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
	yoy_eps = Column(Numeric(16, 4), comment='EPS同比(%)')
	yoy_net_profit = Column(Numeric(16, 4), comment='净利润同比(%)')
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
    """PPI工业生产者出厂价格指数月度数据"""
    __tablename__ = 'macro_ppi'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    month = Column(String(6), nullable=False, unique=True, comment='月份YYYYMM')
    nt_val = Column(Numeric(10, 4), comment='全国当月值')
    nt_yoy = Column(Numeric(10, 4), comment='全国同比(%)')
    nt_mom = Column(Numeric(10, 4), comment='全国环比(%)')
    nt_accu = Column(Numeric(10, 4), comment='全国累计值')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MacroGdp(Base):
    """GDP国内生产总值季度数据"""
    __tablename__ = 'macro_gdp'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    quarter = Column(String(6), nullable=False, unique=True, comment='季度YYYYQ1~Q4')
    gdp = Column(Numeric(18, 4), comment='GDP总额(亿元)')
    gdp_yoy = Column(Numeric(10, 4), comment='GDP同比(%)')
    pi = Column(Numeric(18, 4), comment='第一产业增加值(亿元)')
    si = Column(Numeric(18, 4), comment='第二产业增加值(亿元)')
    ti = Column(Numeric(18, 4), comment='第三产业增加值(亿元)')
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