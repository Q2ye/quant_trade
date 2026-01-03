# quant_server/shared/database/models/system_models.py

from sqlalchemy import Column, String, DateTime, Integer, Numeric, Boolean, Text, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from quant_server.shared.database.models.base import Base


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = 'system_configs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(String(50), default='string')
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey('sys_users.id'))
    updated_by = Column(Integer, ForeignKey('sys_users.id'))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    creator = relationship("SysUser", foreign_keys=[created_by])
    updater = relationship("SysUser", foreign_keys=[updated_by])


class ScheduledTask(Base):
    """定时任务调度表"""
    __tablename__ = 'scheduled_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False)
    task_type = Column(String(50), nullable=False)
    task_config = Column(JSON, nullable=False)
    cron_expression = Column(String(100))
    status = Column(String(20), default='active')
    last_run_time = Column(DateTime(timezone=True))
    next_run_time = Column(DateTime(timezone=True))
    run_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))


class SystemLog(Base):
    """系统操作日志表"""
    __tablename__ = 'system_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_level = Column(String(20), nullable=False)
    module = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey('sys_users.id'))
    action = Column(String(100), nullable=False)
    details = Column(Text)  # JSON格式
    ip_address = Column(String(50))
    user_agent = Column(Text)
    execution_time = Column(Integer)  # 毫秒
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # 关联关系
    user = relationship("SysUser")


class FinancialStatement(Base):
    """上市公司财务报表数据"""
    __tablename__ = 'financial_statements'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), ForeignKey('stock_basic.ts_code'), nullable=False)
    ann_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    report_type = Column(String(20), nullable=False)
    comp_type = Column(String(20))
    basic_eps = Column(Numeric(12, 4))
    diluted_eps = Column(Numeric(12, 4))
    total_revenue = Column(Numeric(18, 4))
    revenue = Column(Numeric(18, 4))
    int_income = Column(Numeric(18, 4))
    prem_earned = Column(Numeric(18, 4))
    comm_income = Column(Numeric(18, 4))
    n_commis_income = Column(Numeric(18, 4))
    n_oth_income = Column(Numeric(18, 4))
    n_oth_b_income = Column(Numeric(18, 4))
    prem_income = Column(Numeric(18, 4))
    out_prem = Column(Numeric(18, 4))
    une_prem_reser = Column(Numeric(18, 4))
    reins_income = Column(Numeric(18, 4))
    n_sec_tb_income = Column(Numeric(18, 4))
    n_sec_uw_income = Column(Numeric(18, 4))
    n_asset_mg_income = Column(Numeric(18, 4))
    oth_b_income = Column(Numeric(18, 4))
    fv_value_chg_gain = Column(Numeric(18, 4))
    invest_income = Column(Numeric(18, 4))
    ass_invest_income = Column(Numeric(18, 4))
    forex_gain = Column(Numeric(18, 4))
    total_cogs = Column(Numeric(18, 4))
    oper_cost = Column(Numeric(18, 4))
    int_exp = Column(Numeric(18, 4))
    comm_exp = Column(Numeric(18, 4))
    biz_tax_surchg = Column(Numeric(18, 4))
    sell_exp = Column(Numeric(18, 4))
    admin_exp = Column(Numeric(18, 4))
    fin_exp = Column(Numeric(18, 4))
    assets_impair_loss = Column(Numeric(18, 4))
    prem_refund = Column(Numeric(18, 4))
    compen_payout = Column(Numeric(18, 4))
    reser_insur_liab = Column(Numeric(18, 4))
    div_payt = Column(Numeric(18, 4))
    reins_exp = Column(Numeric(18, 4))
    oper_exp = Column(Numeric(18, 4))
    compens_payout = Column(Numeric(18, 4))
    insur_reser = Column(Numeric(18, 4))
    reinsur_payout = Column(Numeric(18, 4))
    misc_exp = Column(Numeric(18, 4))
    operate_profit = Column(Numeric(18, 4))
    non_oper_income = Column(Numeric(18, 4))
    non_oper_exp = Column(Numeric(18, 4))
    nca_disploss = Column(Numeric(18, 4))
    total_profit = Column(Numeric(18, 4))
    income_tax = Column(Numeric(18, 4))
    n_income = Column(Numeric(18, 4))
    n_income_attr_p = Column(Numeric(18, 4))
    minority_gain = Column(Numeric(18, 4))
    oth_compr_income = Column(Numeric(18, 4))
    t_compr_income = Column(Numeric(18, 4))
    compr_inc_attr_p = Column(Numeric(18, 4))
    compr_inc_attr_m_s = Column(Numeric(18, 4))
    ebit = Column(Numeric(18, 4))
    ebitda = Column(Numeric(18, 4))
    insurance_exp = Column(Numeric(18, 4))
    undist_profit = Column(Numeric(18, 4))
    distable_profit = Column(Numeric(18, 4))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    stock = relationship("StockBasic")


class IndexBasic(Base):
    """指数基本信息表"""
    __tablename__ = 'index_basic'

    ts_code = Column(String(20), primary_key=True)
    name = Column(String(100), nullable=False)
    fullname = Column(String(200))
    market = Column(String(20))
    publisher = Column(String(100))
    index_type = Column(String(50))
    category = Column(String(50))
    base_date = Column(DateTime)
    base_point = Column(Numeric(12, 2))
    list_date = Column(DateTime)
    weight_rule = Column(String(100))
    desc = Column(String(500))
    exp_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))


class IndexDaily(Base):
    """指数日线行情数据"""
    __tablename__ = 'index_daily'

    ts_code = Column(String(20), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    close = Column(Numeric(12, 4), nullable=False)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    pre_close = Column(Numeric(12, 4))
    change = Column(Numeric(12, 4))
    pct_chg = Column(Numeric(10, 6))
    vol = Column(Integer)
    amount = Column(Numeric(18, 4))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        {'schema': 'public'},
    )


class FactorData(Base):
    """因子数据表"""
    __tablename__ = 'factor_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), nullable=False)
    factor_name = Column(String(100), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    factor_value = Column(Numeric(18, 6), nullable=False)
    data_source = Column(String(50))
    calc_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))