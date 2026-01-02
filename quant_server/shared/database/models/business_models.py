from sqlalchemy import Column, String, DateTime, Float, Integer, Numeric, Boolean, Text, ForeignKey, JSON, \
	UniqueConstraint, Date, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from quant_server.shared.database.models.base import Base

class SysUser(Base):
	"""系统用户信息表"""
	__tablename__ = 'sys_users'

	id = Column(Integer, primary_key=True, autoincrement=True)
	username = Column(String(50), nullable=False, unique=True)
	password_hash = Column(String(100), nullable=False)
	email = Column(String(100))
	phone = Column(String(20))
	real_name = Column(String(50))
	role = Column(String(20), default='user')
	is_active = Column(Boolean, default=True)
	last_login = Column(DateTime(timezone=True))
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	# 关联关系
	strategies = relationship("Strategy", back_populates="user")
	orders = relationship("Order", back_populates="user")
	positions = relationship("Position", back_populates="user")
	permissions = relationship("SysPermission", back_populates="user")
	account_performance = relationship("AccountDailyPerformance", back_populates="user")
	accounts = relationship("Account", back_populates="user")


class SysPermission(Base):
	"""用户细粒度权限表"""
	__tablename__ = 'sys_permissions'

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)
	module = Column(String(50), nullable=False)
	can_read = Column(Boolean, default=False)
	can_write = Column(Boolean, default=False)
	can_execute = Column(Boolean, default=False)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	# 关联关系
	user = relationship("SysUser", back_populates="permissions")


class Strategy(Base):
	"""策略实例表"""
	__tablename__ = 'strategies'

	id = Column(String(32), primary_key=True)
	name = Column(String(100), nullable=False)
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)
	description = Column(Text)
	class_name = Column(String(100), nullable=False)
	module_path = Column(String(200), nullable=False)
	status = Column(String(20), default='stopped')
	parameters = Column(JSON, nullable=False, default={})
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	# 关联关系
	user = relationship("SysUser", back_populates="strategies")
	runs = relationship("StrategyRun", back_populates="events")
	signals = relationship("Signal", back_populates="events")
	daily_performance = relationship("StrategyDailyPerformance", back_populates="events")


class StrategyRun(Base):
	"""策略运行历史记录表"""
	__tablename__ = 'strategy_runs'

	id = Column(Integer, primary_key=True, autoincrement=True)
	strategy_id = Column(String(32), ForeignKey('strategies.id'), nullable=False)
	started_at = Column(DateTime(timezone=True), nullable=False)
	stopped_at = Column(DateTime(timezone=True))
	status = Column(String(20), nullable=False)
	log_path = Column(Text)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	strategy = relationship("Strategy", back_populates="runs")


class Order(Base):
	"""委托订单表"""
	__tablename__ = 'orders'

	order_id = Column(String(32), primary_key=True)
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)
	account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)  # 添加账户ID
	strategy_id = Column(String(32), ForeignKey('strategies.id'))
	ts_code = Column(String(12), nullable=False)
	order_type = Column(String(10), nullable=False)  # limit, market
	direction = Column(String(4), nullable=False)  # buy, sell
	price = Column(Numeric(10, 4))
	volume = Column(Integer, nullable=False)
	filled_volume = Column(Integer, default=0)  # 已成交数量
	filled_amount = Column(Numeric(16, 4), default=0)  # 已成交金额
	avg_price = Column(Numeric(10, 4))  # 成交均价
	status = Column(String(20), default='submitted')  # submitted, partial_filled, filled, cancelled, rejected
	submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	filled_at = Column(DateTime(timezone=True))
	cancelled_at = Column(DateTime(timezone=True))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc))

	# 关联关系
	user = relationship("SysUser", back_populates="orders")
	account = relationship("Account", back_populates="orders")  # 添加与账户的关系
	strategy = relationship("Strategy")
	trades = relationship("Trade", back_populates="order")


class Trade(Base):
	"""成交记录表"""
	__tablename__ = 'trades'

	trade_id = Column(String(32), primary_key=True)
	order_id = Column(String(32), ForeignKey('orders.order_id'), nullable=False)
	ts_code = Column(String(12), nullable=False)
	price = Column(Numeric(10, 4), nullable=False)
	volume = Column(Integer, nullable=False)
	trade_time = Column(DateTime(timezone=True), nullable=False)
	commission = Column(Numeric(10, 4), nullable=False)
	tax = Column(Numeric(10, 4), nullable=False)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	order = relationship("Order", back_populates="trades")


class Position(Base):
	"""用户持仓表"""
	__tablename__ = 'positions'

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)
	account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)  # 添加账户ID
	ts_code = Column(String(12), nullable=False)
	volume = Column(Integer, nullable=False, default=0)  # 总持仓
	available_volume = Column(Integer, nullable=False, default=0)  # 可用持仓
	frozen_volume = Column(Integer, nullable=False, default=0)  # 冻结持仓
	cost_price = Column(Numeric(10, 4), nullable=False)
	market_value = Column(Numeric(16, 4), nullable=False, default=0)
	last_price = Column(Numeric(10, 4))  # 最新价
	pnl = Column(Numeric(16, 4), default=0)  # 持仓盈亏
	pnl_rate = Column(Numeric(10, 6), default=0)  # 持仓盈亏率
	last_update = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

	# 关联关系
	user = relationship("SysUser", back_populates="positions")
	account = relationship("Account", back_populates="positions")  # 添加与账户的关系

	# 复合唯一索引，确保同一账户、同一证券只有一个持仓记录
	__table_args__ = (
		UniqueConstraint('account_id', 'ts_code', name='uq_position_account_tscode'),
	)


class RiskRule(Base):
	"""风控规则配置表"""
	__tablename__ = 'risk_rules'

	id = Column(Integer, primary_key=True, autoincrement=True)
	rule_name = Column(String(100), nullable=False)
	rule_type = Column(String(50), nullable=False)
	condition = Column(JSON, nullable=False)
	action = Column(String(50), nullable=False)
	is_active = Column(Boolean, default=True)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RiskEvent(Base):
	"""风控事件触发日志表"""
	__tablename__ = 'risk_events'

	id = Column(Integer, primary_key=True, autoincrement=True)
	rule_id = Column(Integer, ForeignKey('risk_rules.id'), nullable=False)
	strategy_id = Column(String(32), ForeignKey('strategies.id'))
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)
	event_type = Column(String(50), nullable=False)
	event_message = Column(Text, nullable=False)
	trigger_value = Column(JSON, nullable=False)
	action_taken = Column(String(50))
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	rule = relationship("RiskRule")
	strategy = relationship("Strategy")
	user = relationship("SysUser")


# 在 business_models.py 中添加以下内容

class Account(Base):
	"""账户信息表"""
	__tablename__ = 'accounts'

	# 主键和基本标识
	id = Column(Integer, primary_key=True, autoincrement=True)
	account_number = Column(String(50), nullable=False, unique=True, index=True)  # 内部账户号
	account_name = Column(String(100), nullable=False)  # 账户名称
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)  # 所属用户
	account_type = Column(String(20), nullable=False, default='cash')  # 账户类型: cash, margin, simulation等
	broker = Column(String(50))  # 券商名称
	broker_account_id = Column(String(50), unique=True, index=True)  # 券商账户ID

	# 账户状态
	status = Column(String(20), default='active')  # active, frozen, closed, etc.
	status_reason = Column(Text)  # 状态变更原因
	is_deleted = Column(Integer, default=0)  # 软删除标记

	# 余额和资产信息
	total_balance = Column(Numeric(16, 4), nullable=False, default=0)  # 总资产
	available_balance = Column(Numeric(16, 4), nullable=False, default=0)  # 可用资金
	frozen_balance = Column(Numeric(16, 4), nullable=False, default=0)  # 冻结资金
	market_value = Column(Numeric(16, 4), nullable=False, default=0)  # 持仓市值

	# 初始化信息
	initial_balance = Column(Numeric(16, 4), nullable=False, default=0)  # 初始资金
	credit_line = Column(Numeric(16, 4), default=0)  # 授信额度（信用账户）

	# 时间信息
	last_trade_date = Column(Date)  # 最后交易日
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
						onupdate=lambda: datetime.now(timezone.utc))

	# 关联关系
	user = relationship("SysUser", back_populates="accounts")
	orders = relationship("Order", back_populates="events")
	positions = relationship("Position", back_populates="events")


class AccountDailyPerformance(Base):
	"""账户每日绩效快照表"""
	__tablename__ = 'account_daily_performance'

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)
	trade_date = Column(DateTime, nullable=False)
	total_asset = Column(Numeric(16, 4), nullable=False)
	cash = Column(Numeric(16, 4), nullable=False)
	market_value = Column(Numeric(16, 4), nullable=False)
	daily_pnl = Column(Numeric(16, 4), nullable=False)
	daily_return = Column(Numeric(10, 6), nullable=False)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	user = relationship("SysUser", back_populates="account_performance")


class StrategyDailyPerformance(Base):
	"""策略每日绩效指标表"""
	__tablename__ = 'strategy_daily_performance'

	id = Column(Integer, primary_key=True, autoincrement=True)
	strategy_id = Column(String(32), ForeignKey('strategies.id'), nullable=False)
	trade_date = Column(DateTime, nullable=False)
	daily_return = Column(Numeric(10, 6), nullable=False)
	total_return = Column(Numeric(10, 6), nullable=False)
	max_drawdown = Column(Numeric(10, 6), nullable=False)
	sharpe_ratio = Column(Numeric(10, 6))
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	strategy = relationship("Strategy", back_populates="daily_performance")


class Signal(Base):
	"""策略交易信号记录表"""
	__tablename__ = 'signals'

	id = Column(Integer, primary_key=True, autoincrement=True)
	strategy_id = Column(String(32), ForeignKey('strategies.id'), nullable=False)
	ts_code = Column(String(12), nullable=False)
	signal_type = Column(String(10), nullable=False)
	signal_time = Column(DateTime(timezone=True), nullable=False)
	price = Column(Numeric(10, 4))
	strength = Column(Numeric(5, 2))
	reason = Column(Text)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	strategy = relationship("Strategy", back_populates="signals")


class Basket(Base):
	"""交易篮子表"""
	__tablename__ = 'baskets'

	id = Column(String, primary_key=True)
	name = Column(String(100), nullable=False)
	description = Column(Text)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	# 关联关系
	items = relationship("BasketItem", back_populates="basket")


class BasketItem(Base):
	"""篮子成分表"""
	__tablename__ = 'basket_items'

	id = Column(Integer, primary_key=True, autoincrement=True)
	basket_id = Column(String, ForeignKey('baskets.id'), nullable=False)
	ts_code = Column(String(12), nullable=False)
	weight = Column(Float, default=0.0)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	basket = relationship("Basket", back_populates="items")


class DataSyncTask(Base):
	"""数据同步任务记录表"""
	__tablename__ = 'data_sync_tasks'

	id = Column(Integer, primary_key=True, autoincrement=True)
	task_type = Column(String(50), nullable=False) # 任务类型
	status = Column(String(20), nullable=False) # 任务状态: pending, running, completed, failed
	start_time = Column(DateTime(timezone=True)) # 开始时间
	end_time = Column(DateTime(timezone=True)) # 结束时间
	parameters = Column(JSON)  # 任务参数
	total_records = Column(Integer, default=0) # 同步记录数
	error_message = Column(Text) # 错误信息
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BacktestTask(Base):
	"""回测任务表"""
	__tablename__ = 'backtest_tasks'

	id = Column(String(32), primary_key=True)
	user_id = Column(Integer, ForeignKey('sys_users.id'), nullable=False)
	strategy_id = Column(String(32), ForeignKey('strategies.id'), nullable=False)
	name = Column(String(100), nullable=False)
	description = Column(Text)
	status = Column(String(20), nullable=False, default='pending')
	config = Column(JSON, nullable=False, default={})
	progress = Column(Float, default=0)
	result = Column(JSON)
	error_message = Column(Text)
	started_at = Column(DateTime(timezone=True))
	completed_at = Column(DateTime(timezone=True))
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

	# 关联关系
	user = relationship("SysUser")
	strategy = relationship("Strategy")
	equity_curve = relationship("BacktestEquityCurve", back_populates="task", cascade="all, delete-orphan")
	trades = relationship("BacktestTrade", back_populates="task", cascade="all, delete-orphan")
	positions = relationship("BacktestPosition", back_populates="task", cascade="all, delete-orphan")


class BacktestEquityCurve(Base):
	"""回测净值曲线表"""
	__tablename__ = 'backtest_equity_curves'

	id = Column(Integer, primary_key=True, autoincrement=True)
	task_id = Column(String(32), ForeignKey('backtest_tasks.id'), nullable=False)
	trade_date = Column(DateTime, nullable=False)
	equity = Column(Numeric(16, 4), nullable=False)
	cash = Column(Numeric(16, 4), nullable=False)
	market_value = Column(Numeric(16, 4), nullable=False)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	task = relationship("BacktestTask", back_populates="equity_curve")

	__table_args__ = (
		UniqueConstraint('task_id', 'trade_date', name='uq_backtest_equity_task_date'),
	)


class BacktestTrade(Base):
	"""回测交易记录表"""
	__tablename__ = 'backtest_trades'

	id = Column(Integer, primary_key=True, autoincrement=True)
	task_id = Column(String(32), ForeignKey('backtest_tasks.id'), nullable=False)
	trade_time = Column(DateTime(timezone=True), nullable=False)
	ts_code = Column(String(12), nullable=False)
	direction = Column(String(4), nullable=False)
	price = Column(Numeric(10, 4), nullable=False)
	volume = Column(Integer, nullable=False)
	value = Column(Numeric(16, 4), nullable=False)
	commission = Column(Numeric(10, 4), nullable=False)
	tax = Column(Numeric(10, 4), nullable=False)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	task = relationship("BacktestTask", back_populates="trades")


class BacktestPosition(Base):
	"""回测持仓快照表"""
	__tablename__ = 'backtest_positions'

	id = Column(Integer, primary_key=True, autoincrement=True)
	task_id = Column(String(32), ForeignKey('backtest_tasks.id'), nullable=False)
	trade_date = Column(DateTime, nullable=False)
	ts_code = Column(String(12), nullable=False)
	volume = Column(Integer, nullable=False, default=0)
	cost_price = Column(Numeric(10, 4), nullable=False)
	market_value = Column(Numeric(16, 4), nullable=False)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

	# 关联关系
	task = relationship("BacktestTask", back_populates="positions")

	__table_args__ = (
		UniqueConstraint('task_id', 'trade_date', 'ts_code', name='uq_backtest_position_task_date_code'),
	)