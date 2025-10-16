from sqlalchemy import Column, String, DateTime, Float, Integer, Numeric, Boolean, Text, ForeignKey, JSON, \
    UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from quant_server.db.models.base import Base

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
    runs = relationship("StrategyRun", back_populates="strategy")
    signals = relationship("Signal", back_populates="strategy")
    daily_performance = relationship("StrategyDailyPerformance", back_populates="strategy")


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
    strategy_id = Column(String(32), ForeignKey('strategies.id'))
    ts_code = Column(String(12), nullable=False)
    order_type = Column(String(10), nullable=False)
    direction = Column(String(4), nullable=False)
    price = Column(Numeric(10, 4))
    volume = Column(Integer, nullable=False)
    status = Column(String(20), default='submitted')
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    cancelled_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    user = relationship("SysUser", back_populates="orders")
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
    ts_code = Column(String(12), nullable=False)
    volume = Column(Integer, nullable=False, default=0)
    available_volume = Column(Integer, nullable=False, default=0)
    cost_price = Column(Numeric(10, 4), nullable=False)
    market_value = Column(Numeric(16, 4), nullable=False, default=0)
    last_update = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # 关联关系
    user = relationship("SysUser", back_populates="positions")


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