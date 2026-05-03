"""
business_models.py
业务相关表模型定义（策略、交易、账户、风险等）
位置：shared/database/models/business_models.py
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Float, Integer, Numeric, Boolean, Text, ForeignKey, JSON, \
    UniqueConstraint, Date, Index, BigInteger
from sqlalchemy.orm import relationship

from .base import Base


# ==================== 用户与权限管理 ====================

class SysUser(Base):
    """系统用户信息表"""
    __tablename__ = 'sys_users'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='用户ID')
    username = Column(String(50), nullable=False, unique=True, index=True, comment='用户名')
    password = Column(String(100), nullable=False, comment='密码哈希值')
    email = Column(String(100), comment='邮箱')
    phone = Column(String(20), comment='手机号')
    real_name = Column(String(50), comment='真实姓名')
    role = Column(String(20), default='user', comment='角色标识')
    is_active = Column(Boolean, default=True, comment='是否激活')
    last_login = Column(DateTime(timezone=True), comment='最后登录时间')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="user", cascade="all, delete-orphan")
    permissions = relationship("SysPermission", back_populates="user", cascade="all, delete-orphan")
    account_performance = relationship("AccountDailyPerformance", back_populates="user", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    backtest_tasks = relationship("BacktestTask", back_populates="user", cascade="all, delete-orphan")
    system_logs = relationship("SystemLog", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("SysUserRole", back_populates="user", foreign_keys="SysUserRole.user_id",
                              cascade="all, delete-orphan")
    user_preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan",
                                    uselist=False)
    api_usage_logs = relationship("ApiUsageLog", back_populates="user", cascade="all, delete-orphan")
    factor_research = relationship("FactorResearch", back_populates="user", foreign_keys="FactorResearch.user_id",
                                   cascade="all, delete-orphan")


class SysRole(Base):
    """系统角色表"""
    __tablename__ = 'sys_roles'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='角色ID')
    role_code = Column(String(50), nullable=False, unique=True, index=True, comment='角色编码')
    role_name = Column(String(100), nullable=False, comment='角色名称')
    description = Column(Text, comment='角色描述')
    is_default = Column(Boolean, default=False, comment='是否默认角色')
    permissions = Column(JSON, default=list, comment='权限列表（JSON格式）')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系（通过中间表）
    user_roles = relationship("SysUserRole", back_populates="role", cascade="all, delete-orphan")


class SysUserRole(Base):
    """用户角色关联表（多对多关系）"""
    __tablename__ = 'sys_user_roles'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='关联ID')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    role_id = Column(String(36), ForeignKey('sys_roles.id'), nullable=False, comment='角色ID')
    assigned_by = Column(String(36), ForeignKey('sys_users.id'), comment='分配人ID')
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='分配时间')

    # 唯一约束
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
        Index('idx_sys_user_roles_user_id', 'user_id'),
        Index('idx_sys_user_roles_role_id', 'role_id'),
    )

    # 关联关系
    user = relationship("SysUser", back_populates="user_roles", foreign_keys=user_id)
    role = relationship("SysRole", back_populates="user_roles")
    assigner = relationship("SysUser", foreign_keys=assigned_by)


class SysPermission(Base):
    """用户细粒度权限表"""
    __tablename__ = 'sys_permissions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='权限ID')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    module = Column(String(50), nullable=False, comment='模块名称')
    can_read = Column(Boolean, default=False, comment='读取权限')
    can_write = Column(Boolean, default=False, comment='写入权限')
    can_execute = Column(Boolean, default=False, comment='执行权限')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    user = relationship("SysUser", back_populates="permissions")

    # 索引
    __table_args__ = (
        Index('idx_sys_permissions_user_id', 'user_id'),
        Index('idx_sys_permissions_module', 'module'),
    )


# UserPreference 类已在 system_models.py 中定义，此处删除重复定义


# ApiUsageLog 类已在 system_models.py 中定义，此处删除重复定义


# LicenseKey 类已在 system_models.py 中定义，此处删除重复定义


# ==================== 策略管理 ====================

class Strategy(Base):
    """策略实例表"""
    __tablename__ = 'strategies'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='策略ID（UUID）')
    name = Column(String(100), nullable=False, comment='策略名称')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    description = Column(Text, comment='策略描述')
    class_name = Column(String(100), nullable=False, comment='策略类名')
    module_path = Column(String(200), nullable=False, comment='模块路径')
    strategy_type = Column(String(50), comment='策略类型：cta/alpha/ml/dl等')
    code = Column(Text, comment='策略代码')
    status = Column(String(20), default='stopped', comment='策略状态：stopped, running, paused')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    user = relationship("SysUser", back_populates="strategies")
    runs = relationship("StrategyRun", back_populates="strategy", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="strategy", cascade="all, delete-orphan")
    daily_performance = relationship("StrategyDailyPerformance", back_populates="strategy",
                                     cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="strategy", cascade="all, delete-orphan")
    backtest_tasks = relationship("BacktestTask", back_populates="strategy", cascade="all, delete-orphan")
    risk_events = relationship("RiskEvent", back_populates="strategy", cascade="all, delete-orphan")
    strategy_versions = relationship("StrategyVersion", back_populates="strategy", cascade="all, delete-orphan")
    strategy_parameters = relationship("StrategyParameter", back_populates="strategy", cascade="all, delete-orphan")
    portfolio_strategies = relationship("PortfolioStrategy", back_populates="strategy", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_strategies_user_id', 'user_id'),
        Index('idx_strategies_status', 'status'),
        Index('idx_strategies_name', 'name'),
    )


class StrategyRun(Base):
    """策略运行历史记录表"""
    __tablename__ = 'strategy_runs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='运行记录ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), nullable=False, comment='策略ID')
    started_at = Column(DateTime(timezone=True), nullable=False, comment='开始时间')
    stopped_at = Column(DateTime(timezone=True), comment='停止时间')
    status = Column(String(20), nullable=False, comment='运行状态：running, stopped, error')
    log_path = Column(Text, comment='日志文件路径')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    strategy = relationship("Strategy", back_populates="runs")

    # 索引
    __table_args__ = (
        Index('idx_strategy_runs_strategy_id', 'strategy_id'),
        Index('idx_strategy_runs_started_at', 'started_at'),
        Index('idx_strategy_runs_status', 'status'),
    )


class StrategyDailyPerformance(Base):
    """策略每日绩效指标表"""
    __tablename__ = 'strategy_daily_performance'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='绩效记录ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), nullable=False, comment='策略ID')
    trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
    daily_return = Column(Numeric(10, 6), nullable=False, comment='日收益率')
    total_return = Column(Numeric(10, 6), nullable=False, comment='累计收益率')
    max_drawdown = Column(Numeric(10, 6), nullable=False, comment='最大回撤')
    sharpe_ratio = Column(Numeric(10, 6), comment='夏普比率')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    strategy = relationship("Strategy", back_populates="daily_performance")

    # 索引
    __table_args__ = (
        Index('idx_strategy_daily_performance_strategy_date', 'strategy_id', 'trade_date'),
    )


class Signal(Base):
    """策略交易信号记录表"""
    __tablename__ = 'signals'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='信号ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), nullable=False, comment='策略ID')
    ts_code = Column(String(12), nullable=False, comment='股票代码')
    signal_type = Column(String(10), nullable=False, comment='信号类型：buy, sell, hold')
    signal_time = Column(DateTime(timezone=True), nullable=False, index=True, comment='信号时间')
    price = Column(Numeric(10, 4), comment='信号价格')
    strength = Column(Numeric(5, 2), comment='信号强度')
    reason = Column(Text, comment='信号理由')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    strategy = relationship("Strategy", back_populates="signals")

    # 索引
    __table_args__ = (
        Index('idx_signals_strategy_id', 'strategy_id'),
        Index('idx_signals_signal_time', 'signal_time'),
        Index('idx_signals_ts_code', 'ts_code'),
    )


class StrategyVersion(Base):
    """策略版本管理表"""
    __tablename__ = 'strategy_versions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='版本ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), nullable=False, comment='策略ID')
    version_number = Column(String(20), nullable=False, comment='版本号')
    version_name = Column(String(100), comment='版本名称')
    description = Column(Text, comment='版本描述')
    code_content = Column(Text, nullable=False, comment='代码内容')
    parameters = Column(JSON, nullable=False, default=dict, comment='版本参数（JSON格式）')
    is_current = Column(Boolean, default=False, comment='是否为当前版本')
    created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    strategy = relationship("Strategy", back_populates="strategy_versions")
    creator = relationship("SysUser")

    # 索引和约束
    __table_args__ = (
        UniqueConstraint('strategy_id', 'version_number', name='uq_strategy_version'),
        Index('idx_strategy_versions_current', 'strategy_id', 'is_current'),
        Index('idx_strategy_versions_created_by', 'created_by'),
    )


class StrategyTemplate(Base):
    """策略模板表"""
    __tablename__ = 'strategy_templates'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='模板ID')
    template_name = Column(String(100), nullable=False, comment='模板名称')
    template_type = Column(String(50), nullable=False, comment='模板类型：alpha/cta/ai/custom')
    description = Column(Text, comment='模板描述')
    code_template = Column(Text, nullable=False, comment='代码模板')
    default_parameters = Column(JSON, nullable=False, default=dict, comment='默认参数（JSON格式）')
    category = Column(String(50), comment='分类')
    is_public = Column(Boolean, default=True, comment='是否公开')
    created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    creator = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_strategy_templates_type', 'template_type'),
        Index('idx_strategy_templates_category', 'category'),
        Index('idx_strategy_templates_is_public', 'is_public'),
    )


class StrategyParameter(Base):
    """策略参数配置表"""
    __tablename__ = 'strategy_parameters'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='参数ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), nullable=False, comment='策略ID')
    param_name = Column(String(100), nullable=False, comment='参数名称')
    param_type = Column(String(50), nullable=False, comment='参数类型：int/float/string/bool/list/dict')
    param_value = Column(JSON, nullable=False, comment='参数值（JSON格式）')
    description = Column(Text, comment='参数描述')
    is_required = Column(Boolean, default=True, comment='是否必填')
    validation_rules = Column(JSON, comment='验证规则（JSON格式）')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    strategy = relationship("Strategy", back_populates="strategy_parameters")

    # 索引和约束
    __table_args__ = (
        UniqueConstraint('strategy_id', 'param_name', name='uq_strategy_parameter'),
        Index('idx_strategy_parameters_strategy_id', 'strategy_id'),
    )


class PortfolioStrategy(Base):
    """策略组合关联表"""
    __tablename__ = 'portfolio_strategies'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='组合关联ID')
    portfolio_id = Column(String(36), nullable=False, comment='组合ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), nullable=False, comment='策略ID')
    weight = Column(Numeric(5, 4), nullable=False, default=0.0, comment='权重（0-1）')
    allocation = Column(Numeric(16, 4), comment='分配资金')
    is_active = Column(Boolean, default=True, comment='是否激活')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    strategy = relationship("Strategy", back_populates="portfolio_strategies")

    # 索引和约束
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'strategy_id', name='uq_portfolio_strategy'),
        Index('idx_portfolio_strategies_portfolio_id', 'portfolio_id'),
        Index('idx_portfolio_strategies_strategy_id', 'strategy_id'),
    )


# ==================== 账户管理 ====================

class Account(Base):
    """账户信息表"""
    __tablename__ = 'accounts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='账户ID')
    account_number = Column(String(50), nullable=False, unique=True, index=True, comment='内部账户号')
    account_name = Column(String(100), nullable=False, comment='账户名称')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='所属用户ID')
    account_type = Column(String(20), nullable=False, default='cash', comment='账户类型：cash, margin, simulation')
    broker = Column(String(50), comment='券商名称')
    broker_account_id = Column(String(50), unique=True, index=True, comment='券商账户ID')

    # 账户状态
    status = Column(String(20), default='active', comment='账户状态：active, frozen, closed')
    status_reason = Column(Text, comment='状态变更原因')
    is_deleted = Column(Integer, default=0, comment='软删除标记：0-正常，1-已删除')

    # 余额和资产信息
    total_balance = Column(Numeric(16, 4), nullable=False, default=0, comment='总资产')
    available_balance = Column(Numeric(16, 4), nullable=False, default=0, comment='可用资金')
    frozen_balance = Column(Numeric(16, 4), nullable=False, default=0, comment='冻结资金')
    market_value = Column(Numeric(16, 4), nullable=False, default=0, comment='持仓市值')

    # 初始化信息
    initial_balance = Column(Numeric(16, 4), nullable=False, default=0, comment='初始资金')
    credit_line = Column(Numeric(16, 4), default=0, comment='授信额度（信用账户）')

    # 时间信息
    last_trade_date = Column(Date, comment='最后交易日')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    user = relationship("SysUser", back_populates="accounts")
    orders = relationship("Order", back_populates="account", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    transactions = relationship("AccountTransaction", back_populates="account", cascade="all, delete-orphan")
    statements = relationship("AccountStatement", back_populates="account", cascade="all, delete-orphan")
    audit_logs = relationship("AccountAuditLog", back_populates="account", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_accounts_user_id', 'user_id'),
        Index('idx_accounts_status', 'status'),
        Index('idx_accounts_account_type', 'account_type'),
    )


class AccountDailyPerformance(Base):
    """账户每日绩效快照表"""
    __tablename__ = 'account_daily_performance'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='绩效记录ID')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    trade_date = Column(DateTime, nullable=False, index=True, comment='交易日期')
    total_asset = Column(Numeric(16, 4), nullable=False, comment='总资产')
    cash = Column(Numeric(16, 4), nullable=False, comment='现金')
    market_value = Column(Numeric(16, 4), nullable=False, comment='持仓市值')
    daily_pnl = Column(Numeric(16, 4), nullable=False, comment='日盈亏')
    daily_return = Column(Numeric(10, 6), nullable=False, comment='日收益率')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    user = relationship("SysUser", back_populates="account_performance")

    # 索引
    __table_args__ = (
        Index('idx_account_daily_performance_user_date', 'user_id', 'trade_date'),
    )


class AccountTransaction(Base):
    """账户流水表"""
    __tablename__ = 'account_transactions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='流水ID')
    account_id = Column(String(36), ForeignKey('accounts.id'), nullable=False, comment='账户ID')
    transaction_type = Column(String(50), nullable=False, comment='交易类型：deposit/withdrawal/trade/fee/dividend')
    transaction_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                              comment='交易时间')
    amount = Column(Numeric(16, 4), nullable=False, comment='交易金额')
    balance_before = Column(Numeric(16, 4), nullable=False, comment='交易前余额')
    balance_after = Column(Numeric(16, 4), nullable=False, comment='交易后余额')
    description = Column(Text, comment='描述')
    reference_id = Column(String(100), comment='关联ID（如订单ID）')
    reference_type = Column(String(50), comment='关联类型')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    account = relationship("Account", back_populates="transactions")

    # 索引
    __table_args__ = (
        Index('idx_account_transactions_account_id', 'account_id'),
        Index('idx_account_transactions_date', 'transaction_date'),
        Index('idx_account_transactions_type', 'transaction_type'),
    )


class AccountStatement(Base):
    """账户对账单表"""
    __tablename__ = 'account_statements'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='对账单ID')
    account_id = Column(String(36), ForeignKey('accounts.id'), nullable=False, comment='账户ID')
    statement_date = Column(Date, nullable=False, comment='对账日期')
    statement_period = Column(String(20), nullable=False, comment='对账周期：daily/weekly/monthly')
    opening_balance = Column(Numeric(16, 4), nullable=False, comment='期初余额')
    closing_balance = Column(Numeric(16, 4), nullable=False, comment='期末余额')
    total_deposits = Column(Numeric(16, 4), default=0, comment='总存款额')
    total_withdrawals = Column(Numeric(16, 4), default=0, comment='总取款额')
    total_trades = Column(Numeric(16, 4), default=0, comment='总交易额')
    total_fees = Column(Numeric(16, 4), default=0, comment='总费用')
    statement_data = Column(JSON, comment='对账明细数据（JSON格式）')
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='生成时间')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    account = relationship("Account", back_populates="statements")

    # 索引
    __table_args__ = (
        Index('idx_account_statements_account_date', 'account_id', 'statement_date'),
    )


class CashFlow(Base):
    """资金流水表"""
    __tablename__ = 'cash_flows'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='资金流水ID')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    flow_type = Column(String(50), nullable=False, comment='流水类型：deposit/withdrawal/transfer/dividend/fee')
    flow_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                       comment='流水日期')
    amount = Column(Numeric(16, 4), nullable=False, comment='金额')
    currency = Column(String(10), default='CNY', comment='币种')
    status = Column(String(20), default='completed', comment='状态：pending/completed/failed')
    description = Column(Text, comment='描述')
    reference_id = Column(String(100), comment='关联ID')
    reference_type = Column(String(50), comment='关联类型')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    user = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_cash_flows_user_id', 'user_id'),
        Index('idx_cash_flows_date', 'flow_date'),
        Index('idx_cash_flows_flow_type', 'flow_type'),
    )


class AccountAuditLog(Base):
    """账户审计日志表"""
    __tablename__ = 'account_audit_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='审计日志ID')
    account_id = Column(String(36), ForeignKey('accounts.id'), nullable=False, comment='账户ID')
    audit_type = Column(String(50), nullable=False, comment='审计类型：daily/monthly/yearly/special')
    audit_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                        comment='审计日期')
    auditor_id = Column(String(36), ForeignKey('sys_users.id'), comment='审计人ID')
    audit_action = Column(String(100), nullable=False, comment='审计操作')
    audit_details = Column(JSON, comment='审计详情（JSON格式）')
    audit_result = Column(String(20), default='passed', comment='审计结果：passed/failed')
    remarks = Column(Text, comment='备注')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    account = relationship("Account", back_populates="audit_logs")
    auditor = relationship("SysUser", foreign_keys=auditor_id)

    # 索引
    __table_args__ = (
        Index('idx_account_audit_logs_account_id', 'account_id'),
        Index('idx_account_audit_logs_date', 'audit_date'),
    )


# ==================== 交易管理 ====================

class Order(Base):
    """委托订单表"""
    __tablename__ = 'orders'

    order_id = Column(String(36), primary_key=True, comment='订单ID（UUID）')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    account_id = Column(String(36), ForeignKey('accounts.id'), nullable=False, comment='账户ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), comment='策略ID')
    ts_code = Column(String(12), nullable=False, index=True, comment='股票代码')
    order_type = Column(String(10), nullable=False, comment='订单类型：limit, market')
    direction = Column(String(4), nullable=False, comment='买卖方向：buy, sell')
    price = Column(Numeric(10, 4), comment='委托价格（限价单必填）')
    volume = Column(Integer, nullable=False, comment='委托数量')
    filled_volume = Column(Integer, default=0, comment='已成交数量')
    filled_amount = Column(Numeric(16, 4), default=0, comment='已成交金额')
    avg_price = Column(Numeric(10, 4), comment='成交均价')
    status = Column(String(20), default='submitted',
                    comment='订单状态：submitted, partial_filled, filled, cancelled, rejected')
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='提交时间')
    filled_at = Column(DateTime(timezone=True), comment='成交时间')
    cancelled_at = Column(DateTime(timezone=True), comment='取消时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    user = relationship("SysUser", back_populates="orders")
    account = relationship("Account", back_populates="orders")
    strategy = relationship("Strategy", back_populates="orders")
    trades = relationship("Trade", back_populates="order", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_orders_user_status', 'user_id', 'status'),
        Index('idx_orders_account_status', 'account_id', 'status'),
        Index('idx_orders_ts_code', 'ts_code'),
        Index('idx_orders_submitted_at', 'submitted_at'),
    )


class Trade(Base):
    """成交记录表"""
    __tablename__ = 'trades'

    trade_id = Column(String(36), primary_key=True, comment='成交ID（UUID）')
    order_id = Column(String(36), ForeignKey('orders.order_id'), nullable=False, comment='订单ID')
    ts_code = Column(String(12), nullable=False, index=True, comment='股票代码')
    price = Column(Numeric(10, 4), nullable=False, comment='成交价格')
    volume = Column(Integer, nullable=False, comment='成交数量')
    trade_time = Column(DateTime(timezone=True), nullable=False, index=True, comment='成交时间')
    commission = Column(Numeric(10, 4), nullable=False, comment='佣金')
    tax = Column(Numeric(10, 4), nullable=False, comment='印花税')
    pnl = Column(Numeric(16, 4), default=0, comment='交易盈亏')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    order = relationship("Order", back_populates="trades")
    fees = relationship("TradeFee", back_populates="trade", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_trades_order_id', 'order_id'),
        Index('idx_trades_trade_time', 'trade_time'),
        Index('idx_trades_ts_code', 'ts_code'),
    )


class Position(Base):
    """用户持仓表"""
    __tablename__ = 'positions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='持仓ID')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    account_id = Column(String(36), ForeignKey('accounts.id'), nullable=False, comment='账户ID')
    ts_code = Column(String(12), nullable=False, index=True, comment='股票代码')
    volume = Column(Integer, nullable=False, default=0, comment='总持仓量')
    available_volume = Column(Integer, nullable=False, default=0, comment='可用持仓量')
    frozen_volume = Column(Integer, nullable=False, default=0, comment='冻结持仓量')
    cost_price = Column(Numeric(10, 4), nullable=False, comment='成本价')
    market_value = Column(Numeric(16, 4), nullable=False, default=0, comment='持仓市值')
    last_price = Column(Numeric(10, 4), comment='最新价')
    pnl = Column(Numeric(16, 4), default=0, comment='持仓盈亏')
    pnl_rate = Column(Numeric(10, 6), default=0, comment='持仓盈亏率')
    last_update = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                         comment='最后更新时间')

    # 关联关系
    user = relationship("SysUser", back_populates="positions")
    account = relationship("Account", back_populates="positions")
    adjustments = relationship("PositionAdjustment", back_populates="position", cascade="all, delete-orphan")

    # 复合唯一索引，确保同一账户、同一证券只有一个持仓记录
    __table_args__ = (
        UniqueConstraint('account_id', 'ts_code', name='uq_position_account_tscode'),
        Index('idx_positions_user_account', 'user_id', 'account_id'),
        Index('idx_positions_last_update', 'last_update'),
    )


class TradeInstruction(Base):
    """交易指令表"""
    __tablename__ = 'trade_instructions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='指令ID')
    instruction_id = Column(String(36), nullable=False, unique=True, comment='指令ID（UUID）')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), comment='策略ID')
    instruction_type = Column(String(50), nullable=False, comment='指令类型：basket_trade/portfolio_rebalance/stop_loss')
    status = Column(String(20), default='pending',
                    comment='指令状态：pending, executing, completed, failed, cancelled')
    parameters = Column(JSON, nullable=False, comment='指令参数（JSON格式）')
    execution_result = Column(JSON, comment='执行结果（JSON格式）')
    error_message = Column(Text, comment='错误信息')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')
    executed_at = Column(DateTime(timezone=True), comment='执行时间')

    # 关联关系
    user = relationship("SysUser")
    strategy = relationship("Strategy")

    # 索引
    __table_args__ = (
        Index('idx_trade_instructions_user_id', 'user_id'),
        Index('idx_trade_instructions_status', 'status'),
        Index('idx_trade_instructions_created_at', 'created_at'),
        Index('idx_trade_instructions_instruction_type', 'instruction_type'),
    )


class OrderTemplate(Base):
    """订单模板表"""
    __tablename__ = 'order_templates'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='模板ID')
    template_name = Column(String(100), nullable=False, comment='模板名称')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    template_type = Column(String(50), nullable=False, comment='模板类型：limit/market/stop/basket')
    parameters = Column(JSON, nullable=False, comment='模板参数（JSON格式）')
    is_default = Column(Boolean, default=False, comment='是否为默认模板')
    description = Column(Text, comment='模板描述')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    user = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_order_templates_user_id', 'user_id'),
        Index('idx_order_templates_type', 'template_type'),
    )


class TradeFee(Base):
    """交易费用明细表"""
    __tablename__ = 'trade_fees'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='费用ID')
    trade_id = Column(String(36), ForeignKey('trades.trade_id'), nullable=False, comment='成交ID')
    fee_type = Column(String(50), nullable=False, comment='费用类型：commission/tax/transfer/stamp')
    fee_amount = Column(Numeric(10, 4), nullable=False, comment='费用金额')
    fee_rate = Column(Numeric(8, 6), comment='费率')
    description = Column(Text, comment='描述')
    calculated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='计算时间')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    trade = relationship("Trade", back_populates="fees")

    # 索引
    __table_args__ = (
        Index('idx_trade_fees_trade_id', 'trade_id'),
        Index('idx_trade_fees_type', 'fee_type'),
    )


class PositionAdjustment(Base):
    """持仓调整记录表"""
    __tablename__ = 'position_adjustments'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='调整ID')
    position_id = Column(String(36), ForeignKey('positions.id'), nullable=False, comment='持仓ID')
    adjustment_type = Column(String(50), nullable=False, comment='调整类型：buy/sell/dividend/split/merge')
    adjustment_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                             comment='调整日期')
    volume_change = Column(Integer, nullable=False, comment='数量变化（正数为增，负数为减）')
    cost_price_change = Column(Numeric(10, 4), comment='成本价变化')
    description = Column(Text, comment='描述')
    reference_id = Column(String(100), comment='关联ID')
    reference_type = Column(String(50), comment='关联类型')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    position = relationship("Position", back_populates="adjustments")

    # 索引
    __table_args__ = (
        Index('idx_position_adjustments_position_id', 'position_id'),
        Index('idx_position_adjustments_date', 'adjustment_date'),
    )


class PositionSnapshot(Base):
    """持仓快照表"""
    __tablename__ = 'position_snapshots'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='快照ID')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    account_id = Column(String(36), ForeignKey('accounts.id'), nullable=False, comment='账户ID')
    ts_code = Column(String(12), nullable=False, comment='股票代码')
    snapshot_date = Column(Date, nullable=False, comment='快照日期')
    volume = Column(Integer, nullable=False, default=0, comment='持仓数量')
    cost_price = Column(Numeric(10, 4), nullable=False, comment='成本价')
    market_value = Column(Numeric(16, 4), nullable=False, default=0, comment='持仓市值')
    last_price = Column(Numeric(10, 4), comment='最新价格')
    pnl = Column(Numeric(16, 4), default=0, comment='持仓盈亏')
    pnl_rate = Column(Numeric(10, 6), default=0, comment='盈亏率')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 索引
    __table_args__ = (
        Index('idx_position_snapshots_account_date', 'account_id', 'snapshot_date'),
        Index('idx_position_snapshots_ts_code', 'ts_code', 'snapshot_date'),
        Index('idx_position_snapshots_user_date', 'user_id', 'snapshot_date'),
    )


# ==================== 风险管理 ====================

class RiskRule(Base):
    """风控规则配置表"""
    __tablename__ = 'risk_rules'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='规则ID')
    rule_name = Column(String(100), nullable=False, unique=True, comment='规则名称')
    rule_type = Column(String(50), nullable=False, comment='规则类型：position, account, market, blacklist')
    condition = Column(JSON, nullable=False, comment='规则条件（JSON格式）')
    action = Column(String(50), nullable=False, comment='触发动作：reject, alert, pause_strategy')
    is_active = Column(Boolean, default=True, comment='是否启用')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 索引
    __table_args__ = (
        Index('idx_risk_rules_rule_type', 'rule_type'),
        Index('idx_risk_rules_is_active', 'is_active'),
    )


class Blacklist(Base):
    """黑名单表"""
    __tablename__ = 'blacklists'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='黑名单ID')
    target_type = Column(String(50), nullable=False, comment='目标类型：stock/user/account')
    target_id = Column(String(100), nullable=False, comment='目标标识（股票代码/用户ID/账户ID）')
    target_name = Column(String(200), comment='目标名称')
    list_type = Column(String(50), nullable=False, default='global', comment='名单类型：global/user_specific/system')
    reason = Column(Text, nullable=False, comment='加入原因')
    added_by = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='添加人ID')
    expire_date = Column(DateTime(timezone=True), comment='过期时间')
    is_active = Column(Boolean, default=True, comment='是否有效')
    metainfo = Column(JSON, comment='元数据（JSON格式）')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    added_by_user = relationship("SysUser", foreign_keys=added_by)

    # 索引和约束
    __table_args__ = (
        UniqueConstraint('target_type', 'target_id', 'list_type', name='uq_blacklist_target'),
        Index('idx_blacklists_target_type_id', 'target_type', 'target_id'),
        Index('idx_blacklists_list_type', 'list_type'),
        Index('idx_blacklists_is_active', 'is_active'),
        Index('idx_blacklists_expire_date', 'expire_date'),
    )


class RiskEvent(Base):
    """风控事件触发日志表"""
    __tablename__ = 'risk_events'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='事件ID')
    rule_id = Column(String(36), ForeignKey('risk_rules.id'), nullable=False, comment='规则ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), comment='策略ID')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    event_type = Column(String(50), nullable=False, comment='事件类型')
    event_message = Column(Text, nullable=False, comment='事件描述')
    trigger_value = Column(JSON, nullable=False, comment='触发值（JSON格式）')
    action_taken = Column(String(50), comment='采取的措施')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    rule = relationship("RiskRule")
    strategy = relationship("Strategy", back_populates="risk_events")
    user = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_risk_events_rule_id', 'rule_id'),
        Index('idx_risk_events_strategy_id', 'strategy_id'),
        Index('idx_risk_events_user_id', 'user_id'),
        Index('idx_risk_events_created_at', 'created_at'),
    )


# ==================== 篮子交易 ====================

class Basket(Base):
    """交易篮子表"""
    __tablename__ = 'baskets'

    id = Column(String(36), primary_key=True, comment='篮子ID（UUID）')
    name = Column(String(100), nullable=False, comment='篮子名称')
    description = Column(Text, comment='篮子描述')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    items = relationship("BasketItem", back_populates="basket", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_baskets_name', 'name'),
        Index('idx_baskets_created_at', 'created_at'),
    )


class BasketItem(Base):
    """篮子成分表"""
    __tablename__ = 'basket_items'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='成分ID')
    basket_id = Column(String(36), ForeignKey('baskets.id'), nullable=False, comment='篮子ID')
    ts_code = Column(String(12), nullable=False, comment='股票代码')
    weight = Column(Float, default=0.0, comment='权重（0-1）')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    basket = relationship("Basket", back_populates="items")

    # 索引和约束
    __table_args__ = (
        UniqueConstraint('basket_id', 'ts_code', name='uq_basket_item'),
        Index('idx_basket_items_basket_id', 'basket_id'),
        Index('idx_basket_items_ts_code', 'ts_code'),
    )


# ==================== 数据同步 ====================

class DataSyncTask(Base):
    """数据同步任务记录表"""
    __tablename__ = 'data_sync_tasks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='任务ID')
    task_id = Column(String(64), nullable=False, unique=True, comment='任务唯一标识符（如 sync_abc12345）')
    task_type = Column(String(50), nullable=False, comment='任务类型：stock_basic, daily_quotes, financial, etc.')
    user_id = Column(String(36), ForeignKey('sys_users.id'), comment='用户ID')
    data_types = Column(JSON, comment='数据类型列表（JSON格式）')
    status = Column(String(20), nullable=False, comment='任务状态：pending, running, completed, failed')
    start_time = Column(DateTime(timezone=True), comment='开始时间')
    end_time = Column(DateTime(timezone=True), comment='结束时间')
    parameters = Column(JSON, comment='任务参数（JSON格式）')
    total_records = Column(Integer, default=0, comment='总记录数')
    processed_records = Column(Integer, default=0, comment='已处理记录数')
    records_processed = Column(Integer, default=0, comment='已处理记录数（别名）')
    records_succeeded = Column(Integer, default=0, comment='成功记录数')
    records_failed = Column(Integer, default=0, comment='失败记录数')
    error_message = Column(Text, comment='错误信息')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')
    completed_at = Column(DateTime(timezone=True), comment='完成时间')

    # 关联关系
    user = relationship("SysUser")

    # 属性（保留旧的属性以兼容旧代码，新代码应直接使用 task_id 列）
    @property
    def task_id_str(self):
        """返回任务ID字符串（使用数据库中的id字段）- 旧属性，保持兼容"""
        return str(self.id) if self.id else None

    # 索引
    __table_args__ = (
        Index('idx_data_sync_tasks_status', 'status'),
        Index('idx_data_sync_tasks_type_status', 'task_type', 'status'),
        Index('idx_data_sync_tasks_user_id', 'user_id'),
        Index('idx_data_sync_tasks_created_at', 'created_at'),
        Index('idx_data_sync_tasks_task_id', 'task_id'),
    )


class DataQualityCheck(Base):
    """数据质量检查记录表"""
    __tablename__ = 'data_quality_checks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='检查ID')
    check_type = Column(String(50), nullable=False, comment='检查类型：daily/batch/adhoc')
    data_type = Column(String(50), nullable=False, comment='数据类型：stock_daily/stock_minutes/financial')
    check_date = Column(Date, nullable=False, comment='检查日期')
    total_records = Column(Integer, nullable=False, comment='总记录数')
    valid_records = Column(Integer, nullable=False, comment='有效记录数')
    invalid_records = Column(Integer, nullable=False, comment='无效记录数')
    missing_records = Column(Integer, default=0, comment='缺失记录数')
    duplicate_records = Column(Integer, default=0, comment='重复记录数')
    check_results = Column(JSON, nullable=False, comment='检查结果（JSON格式）')
    status = Column(String(20), default='completed', comment='检查状态')
    checked_by = Column(String(50), comment='检查人/系统')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 索引
    __table_args__ = (
        Index('idx_data_quality_checks_date', 'check_date'),
        Index('idx_data_quality_checks_type', 'data_type'),
        Index('idx_data_quality_checks_status', 'status'),
    )


class DataFixRecord(Base):
    """数据修复记录表"""
    __tablename__ = 'data_fix_records'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='修复记录ID')
    quality_check_id = Column(String(36), ForeignKey('data_quality_checks.id'), comment='质量检查ID')
    data_type = Column(String(50), nullable=False, comment='数据类型')
    fix_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                      comment='修复日期')
    fix_type = Column(String(50), nullable=False, comment='修复类型：missing/duplicate/invalid')
    records_fixed = Column(Integer, nullable=False, comment='修复记录数')
    fix_details = Column(JSON, nullable=False, comment='修复详情（JSON格式）')
    fix_status = Column(String(20), default='completed', comment='修复状态')
    fixed_by = Column(String(50), comment='修复人/系统')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    quality_check = relationship("DataQualityCheck")

    # 索引
    __table_args__ = (
        Index('idx_data_fix_records_date', 'fix_date'),
        Index('idx_data_fix_records_fix_type', 'fix_type'),
    )


class DataQualityMetric(Base):
    """数据质量指标历史表"""
    __tablename__ = 'data_quality_metrics'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='指标ID')
    metric_date = Column(Date, nullable=False, comment='指标日期')
    data_type = Column(String(50), nullable=False, comment='数据类型')
    metric_name = Column(String(100), nullable=False, comment='指标名称')
    metric_value = Column(Numeric(12, 4), nullable=False, comment='指标值')
    target_value = Column(Numeric(12, 4), comment='目标值')
    status = Column(String(20), default='normal', comment='状态：normal/warning/critical')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 索引
    __table_args__ = (
        Index('idx_data_quality_metrics_date', 'metric_date'),
        Index('idx_data_quality_metrics_type', 'data_type'),
        Index('idx_data_quality_metrics_name', 'metric_name'),
    )


# ==================== 回测管理 ====================

class BacktestTask(Base):
    """回测任务表"""
    __tablename__ = 'backtest_tasks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='回测任务ID（UUID）')
    user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, comment='用户ID')
    strategy_id = Column(String(36), ForeignKey('strategies.id'), nullable=False, comment='策略ID')
    name = Column(String(100), nullable=False, comment='回测任务名称')
    description = Column(Text, comment='任务描述')
    status = Column(String(20), nullable=False, default='pending',
                    comment='任务状态：pending, running, completed, failed')
    config = Column(JSON, nullable=False, default=dict, comment='回测配置（JSON格式）')
    progress = Column(Float, default=0, comment='进度（0-1）')
    result = Column(JSON, comment='回测结果（JSON格式）')
    error_message = Column(Text, comment='错误信息')
    started_at = Column(DateTime(timezone=True), comment='开始时间')
    completed_at = Column(DateTime(timezone=True), comment='完成时间')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    user = relationship("SysUser", back_populates="backtest_tasks")
    strategy = relationship("Strategy", back_populates="backtest_tasks")
    equity_curve = relationship("BacktestEquityCurve", back_populates="task", cascade="all, delete-orphan")
    trades = relationship("BacktestTrade", back_populates="task", cascade="all, delete-orphan")
    positions = relationship("BacktestPosition", back_populates="task", cascade="all, delete-orphan")
    parameters = relationship("BacktestParameter", back_populates="task", cascade="all, delete-orphan")
    resource_usage = relationship("BacktestResourceUsage", back_populates="task", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_backtest_tasks_user_id', 'user_id'),
        Index('idx_backtest_tasks_strategy_id', 'strategy_id'),
        Index('idx_backtest_tasks_status', 'status'),
        Index('idx_backtest_tasks_created_at', 'created_at'),
    )


class BacktestEquityCurve(Base):
    """回测净值曲线表"""
    __tablename__ = 'backtest_equity_curves'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='净值记录ID')
    task_id = Column(String(36), ForeignKey('backtest_tasks.id'), nullable=False, comment='回测任务ID')
    trade_date = Column(DateTime, nullable=False, comment='交易日期')
    equity = Column(Numeric(16, 4), nullable=False, comment='总资产')
    cash = Column(Numeric(16, 4), nullable=False, comment='现金')
    market_value = Column(Numeric(16, 4), nullable=False, comment='持仓市值')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    task = relationship("BacktestTask", back_populates="equity_curve")

    # 唯一约束和索引
    __table_args__ = (
        UniqueConstraint('task_id', 'trade_date', name='uq_backtest_equity_task_date'),
        Index('idx_backtest_equity_task_date', 'task_id', 'trade_date'),
    )


class BacktestTrade(Base):
    """回测交易记录表"""
    __tablename__ = 'backtest_trades'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='交易记录ID')
    task_id = Column(String(36), ForeignKey('backtest_tasks.id'), nullable=False, comment='回测任务ID')
    trade_time = Column(DateTime(timezone=True), nullable=False, comment='交易时间')
    ts_code = Column(String(12), nullable=False, comment='股票代码')
    direction = Column(String(4), nullable=False, comment='买卖方向：buy, sell')
    price = Column(Numeric(10, 4), nullable=False, comment='成交价格')
    volume = Column(Integer, nullable=False, comment='成交数量')
    value = Column(Numeric(16, 4), nullable=False, comment='成交金额')
    commission = Column(Numeric(10, 4), nullable=False, comment='佣金')
    tax = Column(Numeric(10, 4), nullable=False, comment='印花税')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    task = relationship("BacktestTask", back_populates="trades")

    # 索引
    __table_args__ = (
        Index('idx_backtest_trades_task_time', 'task_id', 'trade_time'),
        Index('idx_backtest_trades_ts_code', 'ts_code'),
        Index('idx_backtest_trades_direction', 'direction'),
    )


class BacktestPosition(Base):
    """回测持仓快照表"""
    __tablename__ = 'backtest_positions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='持仓快照ID')
    task_id = Column(String(36), ForeignKey('backtest_tasks.id'), nullable=False, comment='回测任务ID')
    trade_date = Column(DateTime, nullable=False, comment='交易日期')
    ts_code = Column(String(12), nullable=False, comment='股票代码')
    volume = Column(Integer, nullable=False, default=0, comment='持仓量')
    cost_price = Column(Numeric(10, 4), nullable=False, comment='成本价')
    market_value = Column(Numeric(16, 4), nullable=False, comment='持仓市值')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    task = relationship("BacktestTask", back_populates="positions")

    # 唯一约束和索引
    __table_args__ = (
        UniqueConstraint('task_id', 'trade_date', 'ts_code', name='uq_backtest_position_task_date_code'),
        Index('idx_backtest_position_task_date', 'task_id', 'trade_date'),
    )


class BacktestParameter(Base):
    """回测参数配置表"""
    __tablename__ = 'backtest_parameters'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='参数ID')
    task_id = Column(String(36), ForeignKey('backtest_tasks.id'), nullable=False, comment='回测任务ID')
    param_category = Column(String(50), nullable=False, comment='参数分类：market/cost/risk/strategy')
    param_name = Column(String(100), nullable=False, comment='参数名称')
    param_value = Column(JSON, nullable=False, comment='参数值（JSON格式）')
    description = Column(Text, comment='参数描述')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    task = relationship("BacktestTask", back_populates="parameters")

    # 索引
    __table_args__ = (
        Index('idx_backtest_parameters_task_id', 'task_id'),
        Index('idx_backtest_parameters_category', 'param_category'),
    )


class BacktestScenario(Base):
    """回测场景表"""
    __tablename__ = 'backtest_scenarios'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='场景ID')
    scenario_id = Column(String(36), nullable=False, unique=True, comment='场景ID（UUID）')
    scenario_name = Column(String(100), nullable=False, comment='场景名称')
    description = Column(Text, comment='场景描述')
    market_conditions = Column(JSON, nullable=False, comment='市场条件（JSON格式）')
    economic_conditions = Column(JSON, comment='经济条件（JSON格式）')
    risk_factors = Column(JSON, comment='风险因子（JSON格式）')
    created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    creator = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_backtest_scenarios_name', 'scenario_name'),
        Index('idx_backtest_scenarios_created_by', 'created_by'),
    )


class BacktestComparison(Base):
    """回测对比结果表"""
    __tablename__ = 'backtest_comparisons'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='对比ID')
    comparison_id = Column(String(36), nullable=False, unique=True, comment='对比ID（UUID）')
    comparison_name = Column(String(100), nullable=False, comment='对比名称')
    description = Column(Text, comment='对比描述')
    base_task_id = Column(String(36), ForeignKey('backtest_tasks.id'), comment='基准回测任务ID')
    compared_tasks = Column(JSON, nullable=False, comment='对比任务列表（JSON格式）')
    comparison_metrics = Column(JSON, nullable=False, comment='对比指标（JSON格式）')
    comparison_results = Column(JSON, comment='对比结果（JSON格式）')
    created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    base_task = relationship("BacktestTask")
    creator = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_backtest_comparisons_name', 'comparison_name'),
        Index('idx_backtest_comparisons_base_task_id', 'base_task_id'),
    )


class BacktestResourceUsage(Base):
    """回测资源使用表"""
    __tablename__ = 'backtest_resource_usage'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='资源使用ID')
    task_id = Column(String(36), ForeignKey('backtest_tasks.id'), nullable=False, comment='回测任务ID')
    resource_type = Column(String(50), nullable=False, comment='资源类型：cpu/memory/disk/network')
    metric_name = Column(String(100), nullable=False, comment='指标名称')
    metric_value = Column(Numeric(12, 4), nullable=False, comment='指标值')
    unit = Column(String(20), comment='单位')
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                         comment='记录时间')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    task = relationship("BacktestTask", back_populates="resource_usage")

    # 索引
    __table_args__ = (
        Index('idx_backtest_resource_usage_task_id', 'task_id'),
        Index('idx_backtest_resource_usage_type', 'resource_type'),
        Index('idx_backtest_resource_usage_recorded_at', 'recorded_at'),
    )


# ==================== 因子研究 ====================

class FactorResearch(Base):
    """因子研究任务表"""
    __tablename__ = 'factor_research'

    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键ID')
    research_id = Column(String(64), nullable=False, unique=True, index=True, comment='研究任务ID')
    research_name = Column(String(200), nullable=False, comment='研究任务名称')

    # 因子信息
    factor_name = Column(String(100), nullable=False, index=True, comment='因子名称')
    factor_definition = Column(JSON, comment='因子定义（JSON格式）')
    factor_category = Column(String(50), index=True, comment='因子类别')

    # 研究参数
    universe = Column(JSON, comment='股票池（JSON数组格式）')
    start_date = Column(Date, comment='开始日期')
    end_date = Column(Date, comment='结束日期')
    parameters = Column(JSON, comment='研究参数（JSON格式）')
    analysis_type = Column(String(50), default='ic_analysis', comment='分析类型')

    # 研究状态和进度
    status = Column(String(20), nullable=False, default='pending',
                    comment='状态：pending, running, completed, failed, cancelled')
    progress = Column(Float, default=0.0, comment='进度（0-1）')
    calculated_count = Column(Integer, default=0, comment='已计算股票数量')
    total_stocks = Column(Integer, default=0, comment='总股票数量')

    # 研究结果
    result = Column(JSON, comment='研究结果（JSON格式）')
    summary = Column(JSON, comment='研究总结（JSON格式）')
    report = Column(JSON, comment='详细报告（JSON格式）')

    # 错误信息
    error_message = Column(Text, comment='错误信息')
    error_stack = Column(Text, comment='错误堆栈')

    # 性能指标（便于查询）
    ic_mean = Column(Numeric(10, 4), comment='IC均值')
    ic_ir = Column(Numeric(10, 4), comment='IC信息比率')
    top_minus_bottom = Column(Numeric(10, 4), comment='多空收益差')
    sharpe_ratio = Column(Numeric(10, 4), comment='夏普比率')

    # 用户和上下文
    user_id = Column(String(36), ForeignKey('sys_users.id'), index=True, comment='用户ID')
    created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
    updated_by = Column(String(36), ForeignKey('sys_users.id'), comment='更新人ID')

    # 时间戳
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')
    started_at = Column(DateTime(timezone=True), comment='开始时间')
    completed_at = Column(DateTime(timezone=True), comment='完成时间')
    estimated_completion_at = Column(DateTime(timezone=True), comment='预计完成时间')

    # 关联关系
    user = relationship("SysUser", back_populates="factor_research", foreign_keys=user_id)
    creator = relationship("SysUser", foreign_keys=created_by)
    updater = relationship("SysUser", foreign_keys=updated_by)

    # 复合索引
    __table_args__ = (
        Index('idx_factor_research_user_status', 'user_id', 'status'),
        Index('idx_factor_research_factor_status', 'factor_name', 'status'),
        Index('idx_factor_research_created_completed', 'created_at', 'completed_at'),
        Index('idx_factor_research_analysis_type', 'analysis_type'),
    )

    def __repr__(self):
        return f"<FactorResearch(id={self.id}, research_id={self.research_id}, factor={self.factor_name}, status={self.status})>"


# ==================== 分析相关 ====================

class AnalysisReport(Base):
    """分析报告表"""
    __tablename__ = 'analysis_reports'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='报告ID')
    report_type = Column(String(50), nullable=False,
                         comment='报告类型：daily, weekly, monthly, performance, risk, custom')
    report_name = Column(String(200), nullable=False, comment='报告名称')
    report_config = Column(JSON, nullable=False, default=dict, comment='报告生成配置（JSON格式）')
    report_data = Column(JSON, comment='报告数据（JSON格式）')
    format = Column(String(20), default='json', comment='报告格式：json, html, pdf, excel')
    status = Column(String(20), default='pending', comment='报告生成状态：pending, generating, completed, failed')
    generated_by = Column(String(36), ForeignKey('sys_users.id'), comment='生成人ID')
    generated_at = Column(DateTime(timezone=True), comment='生成时间')
    file_path = Column(Text, comment='报告文件存储路径')
    file_size = Column(BigInteger, comment='报告文件大小（字节）')
    is_public = Column(Boolean, default=False, comment='是否公开')
    tags = Column(JSON, default=list, comment='标签（JSON数组）')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    generator = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_analysis_reports_type', 'report_type'),
        Index('idx_analysis_reports_status', 'status'),
        Index('idx_analysis_reports_created_at', 'created_at'),
        Index('idx_analysis_reports_generated_by', 'generated_by'),
    )


class AnalysisTask(Base):
    """分析任务表"""
    __tablename__ = 'analysis_tasks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='任务ID')
    task_id = Column(String(64), nullable=False, unique=True, comment='任务ID（唯一）')
    task_name = Column(String(200), nullable=False, comment='任务名称')
    analysis_type = Column(String(50), nullable=False, comment='分析类型：performance/risk/attribution')
    parameters = Column(JSON, nullable=False, comment='分析参数（JSON格式）')
    status = Column(String(20), default='pending', comment='任务状态')
    progress = Column(Float, default=0.0, comment='进度')
    result = Column(JSON, comment='分析结果（JSON格式）')
    report_id = Column(String(36), ForeignKey('analysis_reports.id'), comment='关联的报告ID')
    error_message = Column(Text, comment='错误信息')
    created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')
    started_at = Column(DateTime(timezone=True), comment='开始时间')
    completed_at = Column(DateTime(timezone=True), comment='完成时间')

    # 关联关系
    report = relationship("AnalysisReport")
    creator = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_analysis_tasks_status', 'status'),
        Index('idx_analysis_tasks_type', 'analysis_type'),
        Index('idx_analysis_tasks_created_by', 'created_by'),
    )


class AnalysisTemplate(Base):
    """分析模板表"""
    __tablename__ = 'analysis_templates'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='模板ID')
    template_name = Column(String(100), nullable=False, comment='模板名称')
    template_type = Column(String(50), nullable=False, comment='模板类型')
    description = Column(Text, comment='模板描述')
    config_template = Column(JSON, nullable=False, comment='配置模板（JSON格式）')
    output_format = Column(String(20), default='json', comment='输出格式')
    is_public = Column(Boolean, default=True, comment='是否公开')
    created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    creator = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_analysis_templates_type', 'template_type'),
        Index('idx_analysis_templates_name', 'template_name'),
    )


class ReportGenerationLog(Base):
    """报告生成日志表"""
    __tablename__ = 'report_generation_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='日志ID')
    report_id = Column(String(36), ForeignKey('analysis_reports.id'), comment='报告ID')
    generation_type = Column(String(50), nullable=False, comment='生成类型：scheduled/manual')
    status = Column(String(20), nullable=False, comment='生成状态')
    started_at = Column(DateTime(timezone=True), nullable=False, comment='开始时间')
    completed_at = Column(DateTime(timezone=True), comment='完成时间')
    duration_ms = Column(Integer, comment='耗时（毫秒）')
    error_message = Column(Text, comment='错误信息')
    generated_by = Column(String(36), ForeignKey('sys_users.id'), comment='生成人ID')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    report = relationship("AnalysisReport")
    generator = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_report_generation_logs_report_id', 'report_id'),
        Index('idx_report_generation_logs_date', 'started_at'),
        Index('idx_report_generation_logs_status', 'status'),
    )


class AnalysisBenchmark(Base):
    """分析基准表"""
    __tablename__ = 'analysis_benchmarks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='基准ID')
    benchmark_code = Column(String(20), nullable=False, unique=True, comment='基准代码')
    benchmark_name = Column(String(100), nullable=False, comment='基准名称')
    benchmark_type = Column(String(50), nullable=False, comment='基准类型：index/custom/portfolio')
    description = Column(Text, comment='描述')
    components = Column(JSON, comment='成分股（JSON格式）')
    is_active = Column(Boolean, default=True, comment='是否激活')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 索引
    __table_args__ = (
        Index('idx_analysis_benchmarks_type', 'benchmark_type'),
        Index('idx_analysis_benchmarks_code', 'benchmark_code'),
    )


# ==================== 工作流管理 ====================

class WorkflowTask(Base):
    """工作流任务表"""
    __tablename__ = 'workflow_tasks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='任务ID')
    workflow_id = Column(String(36), nullable=False, comment='工作流ID')
    task_id = Column(String(36), nullable=False, comment='任务ID')
    task_name = Column(String(100), nullable=False, comment='任务名称')
    task_type = Column(String(50), nullable=False, comment='任务类型')
    status = Column(String(20), default='pending',
                    comment='任务状态：pending, running, completed, failed, cancelled')
    dependencies = Column(JSON, default=list, comment='依赖任务（JSON数组）')
    parameters = Column(JSON, nullable=False, comment='任务参数（JSON格式）')
    result = Column(JSON, comment='任务结果（JSON格式）')
    error_message = Column(Text, comment='错误信息')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')
    started_at = Column(DateTime(timezone=True), comment='开始时间')
    completed_at = Column(DateTime(timezone=True), comment='完成时间')

    # 唯一约束和索引
    __table_args__ = (
        UniqueConstraint('workflow_id', 'task_id', name='uq_workflow_task'),
        Index('idx_workflow_tasks_workflow_id', 'workflow_id'),
        Index('idx_workflow_tasks_status', 'status'),
        Index('idx_workflow_tasks_task_type', 'task_type'),
    )


class WorkflowLog(Base):
    """工作流执行日志表"""
    __tablename__ = 'workflow_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='日志ID')
    workflow_id = Column(String(36), nullable=False, comment='工作流ID')
    execution_id = Column(String(36), nullable=False, comment='执行ID')
    workflow_name = Column(String(100), nullable=False, comment='工作流名称')
    status = Column(String(20), nullable=False, comment='执行状态')
    started_at = Column(DateTime(timezone=True), nullable=False, comment='开始时间')
    completed_at = Column(DateTime(timezone=True), comment='完成时间')
    duration_ms = Column(Integer, comment='耗时（毫秒）')
    execution_context = Column(JSON, comment='执行上下文（JSON格式）')
    error_message = Column(Text, comment='错误信息')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 索引
    __table_args__ = (
        Index('idx_workflow_logs_workflow_id', 'workflow_id'),
        Index('idx_workflow_logs_execution_id', 'execution_id'),
        Index('idx_workflow_logs_date', 'started_at'),
        Index('idx_workflow_logs_status', 'status'),
    )


class FileAttachment(Base):
    """文件附件表"""
    __tablename__ = 'file_attachments'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='文件ID')
    file_id = Column(String(36), nullable=False, unique=True, comment='文件ID（UUID）')
    file_name = Column(String(200), nullable=False, comment='文件名')
    file_type = Column(String(50), nullable=False, comment='文件类型：report/data/strategy/log')
    file_size = Column(BigInteger, nullable=False, comment='文件大小（字节）')
    storage_path = Column(Text, nullable=False, comment='存储路径')
    mime_type = Column(String(100), comment='MIME类型')
    reference_type = Column(String(50), nullable=False, comment='关联类型')
    reference_id = Column(String(100), nullable=False, comment='关联ID')
    uploaded_by = Column(String(36), ForeignKey('sys_users.id'), comment='上传人ID')
    upload_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='上传日期')
    description = Column(Text, comment='描述')
    metainfo = Column(JSON, comment='元数据（JSON格式）')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    uploader = relationship("SysUser")

    # 索引
    __table_args__ = (
        Index('idx_file_attachments_reference', 'reference_type', 'reference_id'),
        Index('idx_file_attachments_upload_date', 'upload_date'),
        Index('idx_file_attachments_file_type', 'file_type'),
    )


# ==================== 监控管理 ====================

class MonitorAlert(Base):
    """监控报警记录表"""
    __tablename__ = 'monitor_alerts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='报警ID')
    alert_type = Column(String(50), nullable=False,
                        comment='报警类型：system_error, risk_trigger, data_quality, performance')
    alert_level = Column(String(20), nullable=False, comment='报警级别：critical, warning, info')
    source_module = Column(String(50), nullable=False, comment='报警来源模块')
    source_id = Column(String(100), comment='报警来源ID')
    title = Column(String(200), nullable=False, comment='报警标题')
    message = Column(Text, nullable=False, comment='报警详细信息')
    metainfo = Column(JSON, comment='报警元数据（JSON格式）')
    status = Column(String(20), default='active', comment='报警状态：active, acknowledged, resolved, suppressed')
    acknowledged_by = Column(String(36), ForeignKey('sys_users.id'), comment='确认人ID')
    acknowledged_at = Column(DateTime(timezone=True), comment='确认时间')
    resolved_by = Column(String(36), ForeignKey('sys_users.id'), comment='解决人ID')
    resolved_at = Column(DateTime(timezone=True), comment='解决时间')
    notification_sent = Column(Boolean, default=False, comment='是否已发送通知')
    notification_channels = Column(JSON, default=lambda: ["email", "wechat"], comment='通知渠道（JSON数组）')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 关联关系
    acknowledger = relationship("SysUser", foreign_keys=acknowledged_by)
    resolver = relationship("SysUser", foreign_keys=resolved_by)
    delivery_logs = relationship("AlertDeliveryLog", back_populates="alert", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_monitor_alerts_status', 'status'),
        Index('idx_monitor_alerts_level', 'alert_level'),
        Index('idx_monitor_alerts_type', 'alert_type'),
        Index('idx_monitor_alerts_created_at', 'created_at'),
        Index('idx_monitor_alerts_source', 'source_module', 'source_id'),
    )


class MonitorTask(Base):
    """监控任务表"""
    __tablename__ = 'monitor_tasks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='任务ID')
    task_name = Column(String(100), nullable=False, comment='任务名称')
    task_type = Column(String(50), nullable=False, comment='任务类型：system/strategy/data/trade')
    target_type = Column(String(50), nullable=False, comment='监控目标类型')
    target_id = Column(String(100), comment='监控目标ID')
    schedule_config = Column(JSON, nullable=False, comment='调度配置（JSON格式）')
    check_config = Column(JSON, nullable=False, comment='检查配置（JSON格式）')
    alert_config = Column(JSON, comment='报警配置（JSON格式）')
    is_active = Column(Boolean, default=True, comment='是否激活')
    last_run_at = Column(DateTime(timezone=True), comment='最后运行时间')
    next_run_at = Column(DateTime(timezone=True), comment='下次运行时间')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 索引
    __table_args__ = (
        Index('idx_monitor_tasks_type', 'task_type'),
        Index('idx_monitor_tasks_active', 'is_active'),
        Index('idx_monitor_tasks_last_run_at', 'last_run_at'),
    )


class MonitorThreshold(Base):
    """监控阈值配置表"""
    __tablename__ = 'monitor_thresholds'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='阈值ID')
    metric_type = Column(String(50), nullable=False, comment='指标类型')
    metric_name = Column(String(100), nullable=False, comment='指标名称')
    warning_threshold = Column(Numeric(12, 4), comment='警告阈值')
    critical_threshold = Column(Numeric(12, 4), comment='严重阈值')
    min_value = Column(Numeric(12, 4), comment='最小值')
    max_value = Column(Numeric(12, 4), comment='最大值')
    unit = Column(String(20), comment='单位')
    description = Column(Text, comment='描述')
    is_active = Column(Boolean, default=True, comment='是否激活')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 索引
    __table_args__ = (
        Index('idx_monitor_thresholds_type', 'metric_type'),
        Index('idx_monitor_thresholds_active', 'is_active'),
    )


class AlertTemplate(Base):
    """报警模板表"""
    __tablename__ = 'alert_templates'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='模板ID')
    template_name = Column(String(100), nullable=False, comment='模板名称')
    alert_type = Column(String(50), nullable=False, comment='报警类型')
    alert_level = Column(String(20), nullable=False, comment='报警级别')
    title_template = Column(Text, nullable=False, comment='标题模板')
    message_template = Column(Text, nullable=False, comment='消息模板')
    notification_channels = Column(JSON, default=lambda: ["email"], comment='通知渠道（JSON数组）')
    is_active = Column(Boolean, default=True, comment='是否激活')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

    # 索引
    __table_args__ = (
        Index('idx_alert_templates_type', 'alert_type'),
        Index('idx_alert_templates_level', 'alert_level'),
    )


class AlertDeliveryLog(Base):
    """报警发送日志表"""
    __tablename__ = 'alert_delivery_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='发送日志ID')
    alert_id = Column(String(36), ForeignKey('monitor_alerts.id'), nullable=False, comment='报警ID')
    channel = Column(String(50), nullable=False, comment='发送渠道：email/wechat/dingtalk/sms')
    recipient = Column(String(200), nullable=False, comment='接收者')
    status = Column(String(20), default='pending', comment='发送状态：pending, sent, failed, delivered')
    sent_at = Column(DateTime(timezone=True), comment='发送时间')
    delivered_at = Column(DateTime(timezone=True), comment='送达时间')
    error_message = Column(Text, comment='错误信息')
    retry_count = Column(Integer, default=0, comment='重试次数')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

    # 关联关系
    alert = relationship("MonitorAlert", back_populates="delivery_logs")

    # 索引
    __table_args__ = (
        Index('idx_alert_delivery_logs_alert_id', 'alert_id'),
        Index('idx_alert_delivery_logs_status', 'status'),
        Index('idx_alert_delivery_logs_channel', 'channel'),
    )
