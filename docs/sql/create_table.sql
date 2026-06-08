-- ============================================================
-- 量化交易系统数据库完整建表脚本
-- 数据库：PostgreSQL 14+ + TimescaleDB 2.10+
-- 说明：本脚本包含所有表结构、索引、约束和TimescaleDB配置
-- 执行顺序：先执行关系表，再执行时序表转换
-- ============================================================

-- 1. 数据库和扩展设置
-- ------------------------------------------------------------

-- 注意：请先创建数据库并连接
-- CREATE DATABASE quant_trading;
-- \c quant_trading;

-- 启用TimescaleDB扩展（必须）
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 查看扩展状态
COMMENT ON EXTENSION timescaledb IS '时序数据库扩展，用于处理高频时间序列数据';

-- ============================================================
-- 第一部分：PostgreSQL关系表（非时序数据）
-- ============================================================

-- ------------------------------------------------------------
-- 1.1 用户管理模块
-- ------------------------------------------------------------

-- 用户信息表
CREATE TABLE sys_users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    real_name VARCHAR(50),
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'guest')),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_users IS '系统用户信息表';
COMMENT ON COLUMN sys_users.id IS '用户ID（UUID）';
COMMENT ON COLUMN sys_users.username IS '用户名（唯一）';
COMMENT ON COLUMN sys_users.password IS '密码（BASE64加密）';
COMMENT ON COLUMN sys_users.email IS '用户邮箱';
COMMENT ON COLUMN sys_users.phone IS '手机号码';
COMMENT ON COLUMN sys_users.real_name IS '用户真实姓名';
COMMENT ON COLUMN sys_users.role IS '用户角色：admin-管理员, user-普通用户, guest-访客';
COMMENT ON COLUMN sys_users.is_active IS '账户是否激活';
COMMENT ON COLUMN sys_users.last_login IS '最后登录时间';
COMMENT ON COLUMN sys_users.created_at IS '账户创建时间';
COMMENT ON COLUMN sys_users.updated_at IS '账户信息最后更新时间';

-- 角色信息表
CREATE TABLE sys_roles (
    id VARCHAR(36) PRIMARY KEY,
    role_code VARCHAR(50) NOT NULL UNIQUE,
    role_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    permissions JSONB DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_roles IS '系统角色表';
COMMENT ON COLUMN sys_roles.id IS '角色ID（UUID）';
COMMENT ON COLUMN sys_roles.role_code IS '角色编码（唯一）';
COMMENT ON COLUMN sys_roles.role_name IS '角色名称';
COMMENT ON COLUMN sys_roles.description IS '角色描述';
COMMENT ON COLUMN sys_roles.is_default IS '是否默认角色';
COMMENT ON COLUMN sys_roles.permissions IS '权限列表（JSON格式）';
COMMENT ON COLUMN sys_roles.created_at IS '创建时间';
COMMENT ON COLUMN sys_roles.updated_at IS '更新时间';

-- 用户角色关联表
CREATE TABLE sys_user_roles (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id) ON DELETE CASCADE,
    role_id VARCHAR(36) NOT NULL REFERENCES sys_roles(id) ON DELETE CASCADE,
    assigned_by VARCHAR(36) REFERENCES sys_users(id),
    assigned_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, role_id)
);

COMMENT ON TABLE sys_user_roles IS '用户角色关联表（多对多关系）';
COMMENT ON COLUMN sys_user_roles.id IS '关联ID（UUID）';
COMMENT ON COLUMN sys_user_roles.user_id IS '用户ID';
COMMENT ON COLUMN sys_user_roles.role_id IS '角色ID';
COMMENT ON COLUMN sys_user_roles.assigned_by IS '分配人ID';
COMMENT ON COLUMN sys_user_roles.assigned_at IS '分配时间';

-- 用户权限表
CREATE TABLE sys_permissions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id) ON DELETE CASCADE,
    module VARCHAR(50) NOT NULL,
    can_read BOOLEAN DEFAULT FALSE,
    can_write BOOLEAN DEFAULT FALSE,
    can_execute BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, module)
);

COMMENT ON TABLE sys_permissions IS '用户细粒度权限表';
COMMENT ON COLUMN sys_permissions.user_id IS '外键，关联用户ID';
COMMENT ON COLUMN sys_permissions.module IS '权限所属模块（如strategy, basket, trading, market）';
COMMENT ON COLUMN sys_permissions.can_read IS '是否可读';
COMMENT ON COLUMN sys_permissions.can_write IS '是否可写';
COMMENT ON COLUMN sys_permissions.can_execute IS '是否可执行（如交易、回测）';

-- 用户偏好设置表
CREATE TABLE user_preferences (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id) ON DELETE CASCADE UNIQUE,
    language VARCHAR(10) DEFAULT 'zh-CN',
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    theme VARCHAR(20) DEFAULT 'light',
    notification_settings JSONB DEFAULT '{"email": true, "wechat": false, "sms": false}',
    trading_settings JSONB DEFAULT '{"default_account": null, "confirm_before_trade": true}',
    display_settings JSONB DEFAULT '{"default_chart_type": "candle", "show_grid": true}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_preferences IS '用户偏好设置表';
COMMENT ON COLUMN user_preferences.user_id IS '用户ID（唯一）';
COMMENT ON COLUMN user_preferences.language IS '语言设置';
COMMENT ON COLUMN user_preferences.timezone IS '时区设置';
COMMENT ON COLUMN user_preferences.theme IS '主题：light/dark';
COMMENT ON COLUMN user_preferences.notification_settings IS '通知设置（JSON）';
COMMENT ON COLUMN user_preferences.trading_settings IS '交易设置（JSON）';
COMMENT ON COLUMN user_preferences.display_settings IS '显示设置（JSON）';

-- API使用日志表
CREATE TABLE api_usage_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES sys_users(id) ON DELETE SET NULL,
    api_endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    request_params JSONB,
    response_status INT NOT NULL,
    response_time_ms INT NOT NULL,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE api_usage_logs IS 'API使用日志表';
COMMENT ON COLUMN api_usage_logs.user_id IS '用户ID';
COMMENT ON COLUMN api_usage_logs.api_endpoint IS 'API端点';
COMMENT ON COLUMN api_usage_logs.method IS 'HTTP方法';
COMMENT ON COLUMN api_usage_logs.request_params IS '请求参数（JSON）';
COMMENT ON COLUMN api_usage_logs.response_status IS '响应状态码';
COMMENT ON COLUMN api_usage_logs.response_time_ms IS '响应时间（毫秒）';
COMMENT ON COLUMN api_usage_logs.ip_address IS 'IP地址';
COMMENT ON COLUMN api_usage_logs.user_agent IS '用户代理';

-- 系统健康指标表
CREATE TABLE system_health_metrics (
    id VARCHAR(36) PRIMARY KEY,
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC(12,4) NOT NULL,
    unit VARCHAR(20),
    status VARCHAR(20) DEFAULT 'normal' CHECK (status IN ('normal', 'warning', 'critical')),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE system_health_metrics IS '系统健康指标表';
COMMENT ON COLUMN system_health_metrics.metric_type IS '指标类型：cpu, memory, disk, network, database';
COMMENT ON COLUMN system_health_metrics.metric_name IS '指标名称';
COMMENT ON COLUMN system_health_metrics.metric_value IS '指标值';
COMMENT ON COLUMN system_health_metrics.unit IS '单位';
COMMENT ON COLUMN system_health_metrics.status IS '状态：normal/warning/critical';
COMMENT ON COLUMN system_health_metrics.collected_at IS '指标采集时间';

-- 许可证密钥表
CREATE TABLE license_keys (
    id VARCHAR(36) PRIMARY KEY,
    license_key VARCHAR(100) NOT NULL UNIQUE,
    license_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(36) REFERENCES sys_users(id) ON DELETE SET NULL,
    max_users INT DEFAULT 1,
    max_strategies INT DEFAULT 10,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    activation_date TIMESTAMPTZ,
    last_check_date TIMESTAMPTZ,
    metainfo JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE license_keys IS '许可证密钥表';
COMMENT ON COLUMN license_keys.license_key IS '许可证密钥（唯一）';
COMMENT ON COLUMN license_keys.license_type IS '许可证类型：trial/basic/pro/enterprise';
COMMENT ON COLUMN license_keys.user_id IS '绑定的用户ID';
COMMENT ON COLUMN license_keys.max_users IS '最大用户数';
COMMENT ON COLUMN license_keys.max_strategies IS '最大策略数';
COMMENT ON COLUMN license_keys.valid_from IS '有效期开始';
COMMENT ON COLUMN license_keys.valid_to IS '有效期结束';
COMMENT ON COLUMN license_keys.is_active IS '是否激活';
COMMENT ON COLUMN license_keys.activation_date IS '激活时间';
COMMENT ON COLUMN license_keys.last_check_date IS '最后检查时间';

-- ------------------------------------------------------------
-- 1.2 股票基础数据模块
-- ------------------------------------------------------------

-- 股票基础信息表
CREATE TABLE stock_basic (
    ts_code VARCHAR(20) PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    name VARCHAR(50) NOT NULL,
    area VARCHAR(20),
    industry VARCHAR(30),
    fullname VARCHAR(100),
    enname VARCHAR(100),
    cnspell VARCHAR(50),
    market VARCHAR(20) NOT NULL,
    exchange VARCHAR(10),
    curr_type VARCHAR(10),
    list_status CHAR(1) DEFAULT 'L',
    list_date DATE NOT NULL,
    delist_date DATE,
    is_hs CHAR(1),
    act_name VARCHAR(50),
    act_ent_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_basic IS '股票基础信息表';
COMMENT ON COLUMN stock_basic.ts_code IS 'TS唯一代码 (主键)';
COMMENT ON COLUMN stock_basic.symbol IS '股票代码 (交易所代码)';
COMMENT ON COLUMN stock_basic.name IS '股票名称';
COMMENT ON COLUMN stock_basic.area IS '地域';
COMMENT ON COLUMN stock_basic.industry IS '所属行业';
COMMENT ON COLUMN stock_basic.fullname IS '公司全称';
COMMENT ON COLUMN stock_basic.enname IS '英文全称';
COMMENT ON COLUMN stock_basic.cnspell IS '拼音缩写';
COMMENT ON COLUMN stock_basic.market IS '市场类型 (主板/创业板/科创板/CDR/北交所)';
COMMENT ON COLUMN stock_basic.exchange IS '交易所 (SSE:上交所/SZSE:深交所/BSE:北交所)';
COMMENT ON COLUMN stock_basic.curr_type IS '交易货币 (CNY/HKD/USD)';
COMMENT ON COLUMN stock_basic.list_status IS '上市状态 (L:上市/D:退市/P:暂停上市)';
COMMENT ON COLUMN stock_basic.list_date IS '上市日期';
COMMENT ON COLUMN stock_basic.delist_date IS '退市日期';
COMMENT ON COLUMN stock_basic.is_hs IS '沪深港通标的 (N:否/H:沪股通/S:深股通)';
COMMENT ON COLUMN stock_basic.act_name IS '实控人名称';
COMMENT ON COLUMN stock_basic.act_ent_type IS '实控人企业性质';

-- 创建索引优化查询性能
CREATE INDEX idx_stock_basic_symbol ON stock_basic(symbol);
CREATE INDEX idx_stock_basic_name ON stock_basic(name);
CREATE INDEX idx_stock_basic_industry ON stock_basic(industry);
CREATE INDEX idx_stock_basic_exchange ON stock_basic(exchange);
CREATE INDEX idx_stock_basic_list_status ON stock_basic(list_status);
CREATE INDEX idx_stock_basic_is_hs ON stock_basic(is_hs);

-- ST股票列表表
CREATE TABLE stock_st_list (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    UNIQUE (ts_code, trade_date),
    st_type VARCHAR(10) NOT NULL,
    st_type_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);

COMMENT ON TABLE stock_st_list IS 'ST股票列表历史记录表';
COMMENT ON COLUMN stock_st_list.ts_code IS '股票TS代码';
COMMENT ON COLUMN stock_st_list.name IS '股票名称';
COMMENT ON COLUMN stock_st_list.trade_date IS '交易日期';
COMMENT ON COLUMN stock_st_list.st_type IS 'ST类型（如：ST/*ST/U等）';
COMMENT ON COLUMN stock_st_list.st_type_name IS '类型名称（如：ST特别处理/*ST退市风险警示等）';

CREATE INDEX idx_stock_st_list_ts_code ON stock_st_list(ts_code);
CREATE INDEX idx_stock_st_list_trade_date ON stock_st_list(trade_date);
CREATE INDEX idx_stock_st_list_type ON stock_st_list(st_type);

-- 上市公司基本信息表
CREATE TABLE stock_company (
    ts_code VARCHAR(20) PRIMARY KEY,
    com_name VARCHAR(100) NOT NULL,
    com_id VARCHAR(30) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    chairman VARCHAR(50),
    manager VARCHAR(50),
    secretary VARCHAR(50),
    reg_capital NUMERIC(15, 2) NOT NULL,
    setup_date DATE NOT NULL,
    province VARCHAR(20),
    city VARCHAR(20),
    introduction TEXT,
    website VARCHAR(100),
    email VARCHAR(100),
    office VARCHAR(200),
    employees INT,
    main_business TEXT,
    business_scope TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_company IS '上市公司基本信息表';
COMMENT ON COLUMN stock_company.ts_code IS '股票代码 (主键)';
COMMENT ON COLUMN stock_company.com_name IS '公司全称';
COMMENT ON COLUMN stock_company.com_id IS '统一社会信用代码';
COMMENT ON COLUMN stock_company.exchange IS '交易所代码 (SSE:上交所/SZSE:深交所/BSE:北交所)';
COMMENT ON COLUMN stock_company.chairman IS '法人代表';
COMMENT ON COLUMN stock_company.manager IS '总经理';
COMMENT ON COLUMN stock_company.secretary IS '董事会秘书';
COMMENT ON COLUMN stock_company.reg_capital IS '注册资本(万元)';
COMMENT ON COLUMN stock_company.setup_date IS '注册日期';
COMMENT ON COLUMN stock_company.province IS '所在省份';
COMMENT ON COLUMN stock_company.city IS '所在城市';
COMMENT ON COLUMN stock_company.introduction IS '公司介绍';
COMMENT ON COLUMN stock_company.website IS '公司主页';
COMMENT ON COLUMN stock_company.email IS '电子邮件';
COMMENT ON COLUMN stock_company.office IS '办公室地址';
COMMENT ON COLUMN stock_company.employees IS '员工人数';
COMMENT ON COLUMN stock_company.main_business IS '主要业务及产品';
COMMENT ON COLUMN stock_company.business_scope IS '经营范围';

CREATE INDEX idx_stock_company_com_name ON stock_company(com_name);
CREATE INDEX idx_stock_company_exchange ON stock_company(exchange);
CREATE INDEX idx_stock_company_province ON stock_company(province);
CREATE INDEX idx_stock_company_city ON stock_company(city);
CREATE INDEX idx_stock_company_setup_date ON stock_company(setup_date);

-- 上市公司管理层表
CREATE TABLE stk_managers (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    name VARCHAR(50) NOT NULL,
    gender CHAR(1),
    lev VARCHAR(20),
    title VARCHAR(100),
    edu VARCHAR(20),
    national VARCHAR(20),
    birthday VARCHAR(10),
    begin_date VARCHAR(10),
    end_date VARCHAR(10),
    resume TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, name, title)
);

COMMENT ON TABLE stk_managers IS '上市公司管理层信息表';
COMMENT ON COLUMN stk_managers.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stk_managers.ann_date IS '公告日期';
COMMENT ON COLUMN stk_managers.name IS '姓名';
COMMENT ON COLUMN stk_managers.gender IS '性别 (M:男/F:女)';
COMMENT ON COLUMN stk_managers.lev IS '岗位类别 (董事会/监事会/高管)';
COMMENT ON COLUMN stk_managers.title IS '具体岗位 (董事长/总经理等)';
COMMENT ON COLUMN stk_managers.edu IS '学历 (博士/硕士/本科等)';
COMMENT ON COLUMN stk_managers.national IS '国籍';
COMMENT ON COLUMN stk_managers.birthday IS '出生年月';
COMMENT ON COLUMN stk_managers.begin_date IS '上任日期';
COMMENT ON COLUMN stk_managers.end_date IS '离任日期';
COMMENT ON COLUMN stk_managers.resume IS '个人简历';

CREATE INDEX idx_stk_managers_ts_code ON stk_managers(ts_code);
CREATE INDEX idx_stk_managers_ann_date ON stk_managers(ann_date);
CREATE INDEX idx_stk_managers_name ON stk_managers(name);
CREATE INDEX idx_stk_managers_title ON stk_managers(title);
CREATE INDEX idx_stk_managers_begin_date ON stk_managers(begin_date);
CREATE INDEX idx_stk_managers_end_date ON stk_managers(end_date);

-- 上市公司管理层薪酬和持股信息
CREATE TABLE stk_rewards (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    end_date DATE,
    name VARCHAR(50) NOT NULL,
    title VARCHAR(100),
    reward NUMERIC(18, 2),
    hold_vol BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, end_date, name, title)
);
CREATE INDEX IF NOT EXISTS idx_stk_rewards_ts_code ON stk_rewards(ts_code);

COMMENT ON TABLE stk_rewards IS '上市公司管理层薪酬与持股明细表';
COMMENT ON COLUMN stk_rewards.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stk_rewards.ann_date IS '公告发布日期';
COMMENT ON COLUMN stk_rewards.end_date IS '报告期截止日期';
COMMENT ON COLUMN stk_rewards.name IS '管理层成员姓名';
COMMENT ON COLUMN stk_rewards.title IS '担任职务';
COMMENT ON COLUMN stk_rewards.reward IS '年度税前报酬（元）';
COMMENT ON COLUMN stk_rewards.hold_vol IS '期末直接持股数（股）';

-- ------------------------------------------------------------
-- 宏观经济数据表
-- ------------------------------------------------------------

-- CPI 居民消费价格指数
CREATE TABLE macro_cpi (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    month VARCHAR(6) NOT NULL,
    nt_val NUMERIC(10, 4),
    nt_yoy NUMERIC(10, 4),
    nt_mom NUMERIC(10, 4),
    nt_accu NUMERIC(10, 4),
    town_val NUMERIC(10, 4),
    town_yoy NUMERIC(10, 4),
    town_mom NUMERIC(10, 4),
    town_accu NUMERIC(10, 4),
    cnt_val NUMERIC(10, 4),
    cnt_yoy NUMERIC(10, 4),
    cnt_mom NUMERIC(10, 4),
    cnt_accu NUMERIC(10, 4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(month)
);
COMMENT ON TABLE macro_cpi IS 'CPI居民消费价格指数月度数据';
COMMENT ON COLUMN macro_cpi.month IS '月份（YYYYMM）';
COMMENT ON COLUMN macro_cpi.nt_val IS '全国当月值';
COMMENT ON COLUMN macro_cpi.nt_yoy IS '全国同比(%)';
COMMENT ON COLUMN macro_cpi.nt_mom IS '全国环比(%)';

-- PPI 工业生产者出厂价格指数
CREATE TABLE macro_ppi (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    month VARCHAR(6) NOT NULL UNIQUE,
    ppi_yoy NUMERIC(10,4), ppi_mom NUMERIC(10,4), ppi_accu NUMERIC(10,4),
    ppi_mp_yoy NUMERIC(10,4), ppi_mp_mom NUMERIC(10,4), ppi_mp_accu NUMERIC(10,4),
    ppi_mp_qm_yoy NUMERIC(10,4), ppi_mp_qm_mom NUMERIC(10,4), ppi_mp_qm_accu NUMERIC(10,4),
    ppi_mp_rm_yoy NUMERIC(10,4), ppi_mp_rm_mom NUMERIC(10,4), ppi_mp_rm_accu NUMERIC(10,4),
    ppi_mp_p_yoy NUMERIC(10,4), ppi_mp_p_mom NUMERIC(10,4), ppi_mp_p_accu NUMERIC(10,4),
    ppi_cg_yoy NUMERIC(10,4), ppi_cg_mom NUMERIC(10,4), ppi_cg_accu NUMERIC(10,4),
    ppi_cg_f_yoy NUMERIC(10,4), ppi_cg_f_mom NUMERIC(10,4), ppi_cg_f_accu NUMERIC(10,4),
    ppi_cg_c_yoy NUMERIC(10,4), ppi_cg_c_mom NUMERIC(10,4), ppi_cg_c_accu NUMERIC(10,4),
    ppi_cg_adu_yoy NUMERIC(10,4), ppi_cg_adu_mom NUMERIC(10,4), ppi_cg_adu_accu NUMERIC(10,4),
    ppi_cg_dcg_yoy NUMERIC(10,4), ppi_cg_dcg_mom NUMERIC(10,4), ppi_cg_dcg_accu NUMERIC(10,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE macro_ppi IS 'PPI工业生产者出厂价格指数（对齐 Tushare cn_ppi）';
COMMENT ON COLUMN macro_ppi.month IS '月份YYYYMM';

-- GDP 国内生产总值
CREATE TABLE macro_gdp (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    quarter VARCHAR(6) NOT NULL,
    gdp NUMERIC(18, 4),
    gdp_yoy NUMERIC(10, 4),
    pi NUMERIC(18, 4),
    si NUMERIC(18, 4),
    ti NUMERIC(18, 4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quarter)
);
COMMENT ON TABLE macro_gdp IS 'GDP国内生产总值季度数据';
COMMENT ON COLUMN macro_gdp.quarter IS '季度（YYYYQ1~YYYYQ4）';
COMMENT ON COLUMN macro_gdp.gdp IS 'GDP总额（亿元）';

-- ------------------------------------------------------------
-- 1.3 账户相关表
-- ------------------------------------------------------------

-- 账户信息表
CREATE TABLE accounts (
    id VARCHAR(36) PRIMARY KEY,
    account_number VARCHAR(50) NOT NULL UNIQUE,
    account_name VARCHAR(100) NOT NULL,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    account_type VARCHAR(20) NOT NULL DEFAULT 'cash',
    broker VARCHAR(50),
    broker_account_id VARCHAR(50) UNIQUE,
    status VARCHAR(20) DEFAULT 'active',
    status_reason TEXT,
    is_deleted INT DEFAULT 0,
    total_balance NUMERIC(16, 4) NOT NULL DEFAULT 0,
    available_balance NUMERIC(16, 4) NOT NULL DEFAULT 0,
    frozen_balance NUMERIC(16, 4) NOT NULL DEFAULT 0,
    market_value NUMERIC(16, 4) NOT NULL DEFAULT 0,
    initial_balance NUMERIC(16, 4) NOT NULL DEFAULT 0,
    credit_line NUMERIC(16, 4) DEFAULT 0,
    last_trade_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE accounts IS '账户信息主表';
COMMENT ON COLUMN accounts.id IS '账户ID（主键）';
COMMENT ON COLUMN accounts.account_number IS '内部账户号（唯一）';
COMMENT ON COLUMN accounts.account_name IS '账户名称';
COMMENT ON COLUMN accounts.user_id IS '所属用户ID';
COMMENT ON COLUMN accounts.account_type IS '账户类型：cash-现金账户, margin-融资融券账户, simulation-模拟账户';
COMMENT ON COLUMN accounts.broker IS '券商名称';
COMMENT ON COLUMN accounts.broker_account_id IS '券商账户ID（外部系统关联）';
COMMENT ON COLUMN accounts.status IS '账户状态：active-激活, frozen-冻结, closed-关闭';
COMMENT ON COLUMN accounts.status_reason IS '状态变更原因';
COMMENT ON COLUMN accounts.is_deleted IS '软删除标记（0-正常，1-删除）';
COMMENT ON COLUMN accounts.total_balance IS '总资产（现金+持仓市值）';
COMMENT ON COLUMN accounts.available_balance IS '可用资金';
COMMENT ON COLUMN accounts.frozen_balance IS '冻结资金（挂单冻结等）';
COMMENT ON COLUMN accounts.market_value IS '持仓总市值';
COMMENT ON COLUMN accounts.initial_balance IS '初始资金';
COMMENT ON COLUMN accounts.credit_line IS '授信额度（信用账户专用）';
COMMENT ON COLUMN accounts.last_trade_date IS '最后交易日';

CREATE INDEX idx_accounts_user_id ON accounts(user_id);
CREATE INDEX idx_accounts_account_number ON accounts(account_number);
CREATE INDEX idx_accounts_broker_account_id ON accounts(broker_account_id);
CREATE INDEX idx_accounts_status ON accounts(status);

-- 账户流水表
CREATE TABLE account_transactions (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50) NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    amount NUMERIC(16, 4) NOT NULL,
    balance_before NUMERIC(16, 4) NOT NULL,
    balance_after NUMERIC(16, 4) NOT NULL,
    description TEXT,
    reference_id VARCHAR(100),
    reference_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE account_transactions IS '账户流水表';
COMMENT ON COLUMN account_transactions.account_id IS '账户ID';
COMMENT ON COLUMN account_transactions.transaction_type IS '交易类型：deposit/withdrawal/trade/fee/dividend';
COMMENT ON COLUMN account_transactions.transaction_date IS '交易时间';
COMMENT ON COLUMN account_transactions.amount IS '交易金额';
COMMENT ON COLUMN account_transactions.balance_before IS '交易前余额';
COMMENT ON COLUMN account_transactions.balance_after IS '交易后余额';
COMMENT ON COLUMN account_transactions.description IS '描述';
COMMENT ON COLUMN account_transactions.reference_id IS '关联ID（如订单ID）';
COMMENT ON COLUMN account_transactions.reference_type IS '关联类型';

CREATE INDEX idx_account_transactions_account_id ON account_transactions(account_id);
CREATE INDEX idx_account_transactions_date ON account_transactions(transaction_date DESC);
CREATE INDEX idx_account_transactions_type ON account_transactions(transaction_type);

-- 账户对账单表
CREATE TABLE account_statements (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    statement_date DATE NOT NULL,
    statement_period VARCHAR(20) NOT NULL,
    opening_balance NUMERIC(16, 4) NOT NULL,
    closing_balance NUMERIC(16, 4) NOT NULL,
    total_deposits NUMERIC(16, 4) DEFAULT 0,
    total_withdrawals NUMERIC(16, 4) DEFAULT 0,
    total_trades NUMERIC(16, 4) DEFAULT 0,
    total_fees NUMERIC(16, 4) DEFAULT 0,
    statement_data JSONB,
    generated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE account_statements IS '账户对账单表';
COMMENT ON COLUMN account_statements.account_id IS '账户ID';
COMMENT ON COLUMN account_statements.statement_date IS '对账日期';
COMMENT ON COLUMN account_statements.statement_period IS '对账周期：daily/weekly/monthly';
COMMENT ON COLUMN account_statements.opening_balance IS '期初余额';
COMMENT ON COLUMN account_statements.closing_balance IS '期末余额';
COMMENT ON COLUMN account_statements.total_deposits IS '总存款额';
COMMENT ON COLUMN account_statements.total_withdrawals IS '总取款额';
COMMENT ON COLUMN account_statements.total_trades IS '总交易额';
COMMENT ON COLUMN account_statements.total_fees IS '总费用';
COMMENT ON COLUMN account_statements.statement_data IS '对账明细数据（JSON格式）';

CREATE INDEX idx_account_statements_account_date ON account_statements(account_id, statement_date DESC);

-- 资金流水表
CREATE TABLE cash_flows (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    flow_type VARCHAR(50) NOT NULL,
    flow_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    amount NUMERIC(16, 4) NOT NULL,
    currency VARCHAR(10) DEFAULT 'CNY',
    status VARCHAR(20) DEFAULT 'completed',
    description TEXT,
    reference_id VARCHAR(100),
    reference_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE cash_flows IS '资金流水表';
COMMENT ON COLUMN cash_flows.user_id IS '用户ID';
COMMENT ON COLUMN cash_flows.flow_type IS '流水类型：deposit/withdrawal/transfer/dividend/fee';
COMMENT ON COLUMN cash_flows.flow_date IS '流水日期';
COMMENT ON COLUMN cash_flows.amount IS '金额';
COMMENT ON COLUMN cash_flows.currency IS '币种';
COMMENT ON COLUMN cash_flows.status IS '状态：pending/completed/failed';
COMMENT ON COLUMN cash_flows.description IS '描述';
COMMENT ON COLUMN cash_flows.reference_id IS '关联ID';
COMMENT ON COLUMN cash_flows.reference_type IS '关联类型';

CREATE INDEX idx_cash_flows_user_id ON cash_flows(user_id);
CREATE INDEX idx_cash_flows_date ON cash_flows(flow_date DESC);

-- 账户审计日志表
CREATE TABLE account_audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    audit_type VARCHAR(50) NOT NULL,
    audit_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    auditor_id VARCHAR(36) REFERENCES sys_users(id),
    audit_action VARCHAR(100) NOT NULL,
    audit_details JSONB,
    audit_result VARCHAR(20) DEFAULT 'passed',
    remarks TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE account_audit_logs IS '账户审计日志表';
COMMENT ON COLUMN account_audit_logs.account_id IS '账户ID';
COMMENT ON COLUMN account_audit_logs.audit_type IS '审计类型：daily/monthly/yearly/special';
COMMENT ON COLUMN account_audit_logs.audit_date IS '审计日期';
COMMENT ON COLUMN account_audit_logs.auditor_id IS '审计人ID';
COMMENT ON COLUMN account_audit_logs.audit_action IS '审计操作';
COMMENT ON COLUMN account_audit_logs.audit_details IS '审计详情（JSON格式）';
COMMENT ON COLUMN account_audit_logs.audit_result IS '审计结果：passed/failed';
COMMENT ON COLUMN account_audit_logs.remarks IS '备注';

CREATE INDEX idx_account_audit_logs_account_id ON account_audit_logs(account_id);
CREATE INDEX idx_account_audit_logs_date ON account_audit_logs(audit_date DESC);

-- ------------------------------------------------------------
-- 1.4 策略管理模块
-- ------------------------------------------------------------

-- 策略实例表
CREATE TABLE strategies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    description TEXT,
    class_name VARCHAR(100) NOT NULL,
    module_path VARCHAR(200) NOT NULL,
    strategy_type VARCHAR(50),
    code TEXT,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'compiled', 'deployed', 'running', 'paused', 'stopped', 'error', 'archived')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE strategies IS '策略实例表';
COMMENT ON COLUMN strategies.id IS '策略唯一标识（建议使用UUID）';
COMMENT ON COLUMN strategies.name IS '策略名称';
COMMENT ON COLUMN strategies.user_id IS '策略创建者用户ID';
COMMENT ON COLUMN strategies.description IS '策略详细描述';
COMMENT ON COLUMN strategies.class_name IS '策略类名（Python类名）';
COMMENT ON COLUMN strategies.module_path IS '策略文件路径（相对路径）';
COMMENT ON COLUMN strategies.strategy_type IS '策略类型：cta/alpha/ml/dl等';
COMMENT ON COLUMN strategies.code IS '策略代码';
COMMENT ON COLUMN strategies.status IS '策略状态：draft-草稿, compiled-已编译, deployed-已部署, running-运行中, paused-已暂停, stopped-已停止, error-异常, archived-已归档';

-- 策略运行记录表
CREATE TABLE strategy_runs (
    id VARCHAR(36) PRIMARY KEY,
    strategy_id VARCHAR(36) NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    stopped_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL,
    log_path TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE strategy_runs IS '策略运行历史记录表';
COMMENT ON COLUMN strategy_runs.strategy_id IS '外键，关联策略ID';
COMMENT ON COLUMN strategy_runs.started_at IS '策略启动时间';
COMMENT ON COLUMN strategy_runs.stopped_at IS '策略停止时间';
COMMENT ON COLUMN strategy_runs.status IS '运行结果状态：completed, stopped, error';
COMMENT ON COLUMN strategy_runs.log_path IS '本次运行日志文件存储路径';

-- 策略版本管理表
CREATE TABLE strategy_versions (
    id VARCHAR(36) PRIMARY KEY,
    strategy_id VARCHAR(36) NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    version_number VARCHAR(20) NOT NULL,
    version_name VARCHAR(100),
    description TEXT,
    code_content TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::JSONB,
    is_current BOOLEAN DEFAULT FALSE,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (strategy_id, version_number)
);

COMMENT ON TABLE strategy_versions IS '策略版本管理表';
COMMENT ON COLUMN strategy_versions.strategy_id IS '策略ID';
COMMENT ON COLUMN strategy_versions.version_number IS '版本号（如1.0.0）';
COMMENT ON COLUMN strategy_versions.version_name IS '版本名称';
COMMENT ON COLUMN strategy_versions.description IS '版本描述';
COMMENT ON COLUMN strategy_versions.code_content IS '策略代码内容';
COMMENT ON COLUMN strategy_versions.parameters IS '版本参数（JSON格式）';
COMMENT ON COLUMN strategy_versions.is_current IS '是否为当前版本';
COMMENT ON COLUMN strategy_versions.created_by IS '创建人ID';

CREATE INDEX idx_strategy_versions_strategy_id ON strategy_versions(strategy_id);
CREATE INDEX idx_strategy_versions_current ON strategy_versions(is_current) WHERE is_current = TRUE;

-- 策略模板表
CREATE TABLE strategy_templates (
    id VARCHAR(36) PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    template_type VARCHAR(50) NOT NULL,
    description TEXT,
    code_template TEXT NOT NULL,
    default_parameters JSONB NOT NULL DEFAULT '{}'::JSONB,
    category VARCHAR(50),
    is_public BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE strategy_templates IS '策略模板表';
COMMENT ON COLUMN strategy_templates.template_name IS '模板名称';
COMMENT ON COLUMN strategy_templates.template_type IS '模板类型：alpha/cta/ai/custom';
COMMENT ON COLUMN strategy_templates.description IS '模板描述';
COMMENT ON COLUMN strategy_templates.code_template IS '代码模板';
COMMENT ON COLUMN strategy_templates.default_parameters IS '默认参数（JSON格式）';
COMMENT ON COLUMN strategy_templates.category IS '分类';
COMMENT ON COLUMN strategy_templates.is_public IS '是否公开';
COMMENT ON COLUMN strategy_templates.created_by IS '创建人ID';

CREATE INDEX idx_strategy_templates_type ON strategy_templates(template_type);
CREATE INDEX idx_strategy_templates_category ON strategy_templates(category);

-- 策略参数配置表
CREATE TABLE strategy_parameters (
    id VARCHAR(36) PRIMARY KEY,
    strategy_id VARCHAR(36) NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    param_name VARCHAR(100) NOT NULL,
    param_type VARCHAR(50) NOT NULL,
    param_value JSONB NOT NULL,
    description TEXT,
    is_required BOOLEAN DEFAULT TRUE,
    validation_rules JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (strategy_id, param_name)
);

COMMENT ON TABLE strategy_parameters IS '策略参数配置表';
COMMENT ON COLUMN strategy_parameters.strategy_id IS '策略ID';
COMMENT ON COLUMN strategy_parameters.param_name IS '参数名称';
COMMENT ON COLUMN strategy_parameters.param_type IS '参数类型：int/float/string/bool/list/dict';
COMMENT ON COLUMN strategy_parameters.param_value IS '参数值（JSON格式）';
COMMENT ON COLUMN strategy_parameters.description IS '参数描述';
COMMENT ON COLUMN strategy_parameters.is_required IS '是否必填';
COMMENT ON COLUMN strategy_parameters.validation_rules IS '验证规则（JSON格式）';

CREATE INDEX IF NOT EXISTS idx_strategy_parameters_strategy_id ON strategy_parameters(strategy_id);

-- 策略组合关联表
CREATE TABLE portfolio_strategies (
    id VARCHAR(36) PRIMARY KEY,
    portfolio_id VARCHAR(36) NOT NULL,
    strategy_id VARCHAR(36) NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    weight NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    allocation NUMERIC(16,4),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (portfolio_id, strategy_id)
);

COMMENT ON TABLE portfolio_strategies IS '策略组合关联表';
COMMENT ON COLUMN portfolio_strategies.portfolio_id IS '组合ID';
COMMENT ON COLUMN portfolio_strategies.strategy_id IS '策略ID';
COMMENT ON COLUMN portfolio_strategies.weight IS '权重（0-1）';
COMMENT ON COLUMN portfolio_strategies.allocation IS '分配资金';
COMMENT ON COLUMN portfolio_strategies.is_active IS '是否激活';

CREATE INDEX idx_portfolio_strategies_portfolio_id ON portfolio_strategies(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_strategies_strategy_id ON portfolio_strategies(strategy_id);

-- ------------------------------------------------------------
-- 1.5 交易管理模块
-- ------------------------------------------------------------

-- 订单表
CREATE TABLE orders (
    order_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    account_id VARCHAR(36) NOT NULL REFERENCES accounts(id),
    strategy_id VARCHAR(36) REFERENCES strategies(id),
    ts_code VARCHAR(12) NOT NULL,
    order_type VARCHAR(10) NOT NULL CHECK (order_type IN ('limit', 'market', 'stop')),
    direction VARCHAR(4) NOT NULL CHECK (direction IN ('buy', 'sell')),
    price NUMERIC(10, 4),
    volume INT NOT NULL,
    filled_volume INT DEFAULT 0,
    filled_amount NUMERIC(16, 4) DEFAULT 0,
    avg_price NUMERIC(10, 4),
    status VARCHAR(20) DEFAULT 'submitted' CHECK (status IN ('submitted', 'partial_filled', 'filled', 'cancelled', 'rejected')),
    submitted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE orders IS '委托订单表';
COMMENT ON COLUMN orders.order_id IS '订单唯一ID（平台内部生成）';
COMMENT ON COLUMN orders.user_id IS '下单用户ID';
COMMENT ON COLUMN orders.account_id IS '账户ID';
COMMENT ON COLUMN orders.strategy_id IS '关联策略ID（若为策略下单）';
COMMENT ON COLUMN orders.ts_code IS '股票代码';
COMMENT ON COLUMN orders.order_type IS '订单类型：limit-限价单, market-市价单, stop-止损单';
COMMENT ON COLUMN orders.direction IS '交易方向：buy-买入, sell-卖出';
COMMENT ON COLUMN orders.price IS '委托价格（对于市价单，此字段为NULL）';
COMMENT ON COLUMN orders.volume IS '委托数量（单位：股）';
COMMENT ON COLUMN orders.filled_volume IS '已成交数量';
COMMENT ON COLUMN orders.filled_amount IS '已成交金额';
COMMENT ON COLUMN orders.avg_price IS '成交均价';
COMMENT ON COLUMN orders.status IS '订单状态：submitted-已报, partial_filled-部成, filled-已成, cancelled-已撤, rejected-废单';
COMMENT ON COLUMN orders.submitted_at IS '订单提交时间';
COMMENT ON COLUMN orders.filled_at IS '成交时间';
COMMENT ON COLUMN orders.cancelled_at IS '订单撤销时间（如果被撤销）';

-- 成交记录表
CREATE TABLE trades (
    trade_id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL REFERENCES orders(order_id),
    ts_code VARCHAR(12) NOT NULL,
    price NUMERIC(10, 4) NOT NULL,
    volume INT NOT NULL,
    trade_time TIMESTAMPTZ NOT NULL,
    commission NUMERIC(10, 4) NOT NULL,
    tax NUMERIC(10, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE trades IS '成交记录表';
COMMENT ON COLUMN trades.trade_id IS '成交记录唯一ID（通常来自券商接口）';
COMMENT ON COLUMN trades.order_id IS '外键，关联订单ID';
COMMENT ON COLUMN trades.ts_code IS '股票代码';
COMMENT ON COLUMN trades.price IS '成交价格';
COMMENT ON COLUMN trades.volume IS '成交数量（单位：股）';
COMMENT ON COLUMN trades.trade_time IS '成交发生时间';
COMMENT ON COLUMN trades.commission IS '交易佣金';
COMMENT ON COLUMN trades.tax IS '印花税';

-- 持仓表
CREATE TABLE positions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    account_id VARCHAR(36) NOT NULL REFERENCES accounts(id),
    ts_code VARCHAR(12) NOT NULL,
    volume INT NOT NULL DEFAULT 0,
    available_volume INT NOT NULL DEFAULT 0,
    frozen_volume INT NOT NULL DEFAULT 0,
    cost_price NUMERIC(10, 4) NOT NULL,
    market_value NUMERIC(16, 4) NOT NULL DEFAULT 0,
    last_price NUMERIC(10, 4),
    pnl NUMERIC(16, 4) DEFAULT 0,
    pnl_rate NUMERIC(10, 6) DEFAULT 0,
    last_update TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (account_id, ts_code)
);

COMMENT ON TABLE positions IS '用户持仓表';
COMMENT ON COLUMN positions.user_id IS '用户ID';
COMMENT ON COLUMN positions.account_id IS '账户ID';
COMMENT ON COLUMN positions.ts_code IS '股票代码';
COMMENT ON COLUMN positions.volume IS '持仓总数量';
COMMENT ON COLUMN positions.available_volume IS '可用数量（考虑T+1交易制度）';
COMMENT ON COLUMN positions.frozen_volume IS '冻结数量';
COMMENT ON COLUMN positions.cost_price IS '平均持仓成本价';
COMMENT ON COLUMN positions.market_value IS '当前市值（动态更新）';
COMMENT ON COLUMN positions.last_price IS '最新价格';
COMMENT ON COLUMN positions.pnl IS '持仓盈亏';
COMMENT ON COLUMN positions.pnl_rate IS '持仓盈亏率';
COMMENT ON COLUMN positions.last_update IS '最后更新时间';


-- 交易指令表
CREATE TABLE trade_instructions (
    id VARCHAR(36) PRIMARY KEY,
    instruction_id VARCHAR(36) NOT NULL UNIQUE,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    strategy_id VARCHAR(36) REFERENCES strategies(id),
    instruction_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'executing', 'completed', 'failed', 'cancelled')),
    parameters JSONB NOT NULL,
    execution_result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMPTZ
);

COMMENT ON TABLE trade_instructions IS '交易指令表';
COMMENT ON COLUMN trade_instructions.instruction_id IS '指令ID（UUID）';
COMMENT ON COLUMN trade_instructions.user_id IS '用户ID';
COMMENT ON COLUMN trade_instructions.strategy_id IS '策略ID';
COMMENT ON COLUMN trade_instructions.instruction_type IS '指令类型：basket_trade/portfolio_rebalance/stop_loss';
COMMENT ON COLUMN trade_instructions.status IS '指令状态';
COMMENT ON COLUMN trade_instructions.parameters IS '指令参数（JSON格式）';
COMMENT ON COLUMN trade_instructions.execution_result IS '执行结果（JSON格式）';
COMMENT ON COLUMN trade_instructions.error_message IS '错误信息';

CREATE INDEX idx_trade_instructions_user_id ON trade_instructions(user_id);
CREATE INDEX idx_trade_instructions_status ON trade_instructions(status);
CREATE INDEX idx_trade_instructions_created_at ON trade_instructions(created_at DESC);

-- 订单模板表
CREATE TABLE order_templates (
    id VARCHAR(36) PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    template_type VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE order_templates IS '订单模板表';
COMMENT ON COLUMN order_templates.template_name IS '模板名称';
COMMENT ON COLUMN order_templates.user_id IS '用户ID';
COMMENT ON COLUMN order_templates.template_type IS '模板类型：limit/market/stop/basket';
COMMENT ON COLUMN order_templates.parameters IS '模板参数（JSON格式）';
COMMENT ON COLUMN order_templates.is_default IS '是否为默认模板';
COMMENT ON COLUMN order_templates.description IS '模板描述';

CREATE INDEX idx_order_templates_user_id ON order_templates(user_id);
CREATE INDEX idx_order_templates_type ON order_templates(template_type);

-- 交易费用明细表
CREATE TABLE trade_fees (
    id VARCHAR(36) PRIMARY KEY,
    trade_id VARCHAR(36) NOT NULL REFERENCES trades(trade_id) ON DELETE CASCADE,
    fee_type VARCHAR(50) NOT NULL,
    fee_amount NUMERIC(10, 4) NOT NULL,
    fee_rate NUMERIC(8,6),
    description TEXT,
    calculated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE trade_fees IS '交易费用明细表';
COMMENT ON COLUMN trade_fees.trade_id IS '成交ID';
COMMENT ON COLUMN trade_fees.fee_type IS '费用类型：commission/tax/transfer/stamp';
COMMENT ON COLUMN trade_fees.fee_amount IS '费用金额';
COMMENT ON COLUMN trade_fees.fee_rate IS '费率';
COMMENT ON COLUMN trade_fees.description IS '描述';

CREATE INDEX idx_trade_fees_trade_id ON trade_fees(trade_id);
CREATE INDEX idx_trade_fees_type ON trade_fees(fee_type);

-- 持仓调整记录表
CREATE TABLE position_adjustments (
    id VARCHAR(36) PRIMARY KEY,
    position_id VARCHAR(36) NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    adjustment_type VARCHAR(50) NOT NULL,
    adjustment_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    volume_change INT NOT NULL,
    cost_price_change NUMERIC(10, 4),
    description TEXT,
    reference_id VARCHAR(100),
    reference_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE position_adjustments IS '持仓调整记录表';
COMMENT ON COLUMN position_adjustments.position_id IS '持仓ID';
COMMENT ON COLUMN position_adjustments.adjustment_type IS '调整类型：buy/sell/dividend/split/merge';
COMMENT ON COLUMN position_adjustments.adjustment_date IS '调整日期';
COMMENT ON COLUMN position_adjustments.volume_change IS '数量变化（正数为增，负数为减）';
COMMENT ON COLUMN position_adjustments.cost_price_change IS '成本价变化';
COMMENT ON COLUMN position_adjustments.description IS '描述';
COMMENT ON COLUMN position_adjustments.reference_id IS '关联ID';
COMMENT ON COLUMN position_adjustments.reference_type IS '关联类型';

CREATE INDEX idx_position_adjustments_position_id ON position_adjustments(position_id);
CREATE INDEX idx_position_adjustments_date ON position_adjustments(adjustment_date DESC);

-- 持仓快照表
CREATE TABLE position_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    account_id VARCHAR(36) NOT NULL REFERENCES accounts(id),
    ts_code VARCHAR(12) NOT NULL,
    snapshot_date DATE NOT NULL,
    volume INT NOT NULL DEFAULT 0,
    cost_price NUMERIC(10, 4) NOT NULL,
    market_value NUMERIC(16, 4) NOT NULL DEFAULT 0,
    last_price NUMERIC(10, 4),
    pnl NUMERIC(16, 4) DEFAULT 0,
    pnl_rate NUMERIC(10, 6) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (account_id, ts_code, snapshot_date)
);

COMMENT ON TABLE position_snapshots IS '持仓快照表';
COMMENT ON COLUMN position_snapshots.user_id IS '用户ID';
COMMENT ON COLUMN position_snapshots.account_id IS '账户ID';
COMMENT ON COLUMN position_snapshots.ts_code IS '股票代码';
COMMENT ON COLUMN position_snapshots.snapshot_date IS '快照日期';
COMMENT ON COLUMN position_snapshots.volume IS '持仓数量';
COMMENT ON COLUMN position_snapshots.cost_price IS '成本价';
COMMENT ON COLUMN position_snapshots.market_value IS '持仓市值';
COMMENT ON COLUMN position_snapshots.last_price IS '最新价格';
COMMENT ON COLUMN position_snapshots.pnl IS '持仓盈亏';
COMMENT ON COLUMN position_snapshots.pnl_rate IS '盈亏率';

CREATE INDEX idx_position_snapshots_account_date ON position_snapshots(account_id, snapshot_date DESC);
CREATE INDEX idx_position_snapshots_ts_code ON position_snapshots(ts_code, snapshot_date);
CREATE INDEX idx_position_snapshots_user_date ON position_snapshots(user_id, snapshot_date DESC);

-- ------------------------------------------------------------
-- 1.6 篮子管理模块
-- ------------------------------------------------------------

-- 交易篮子表
CREATE TABLE baskets (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE baskets IS '交易篮子表';
COMMENT ON COLUMN baskets.id IS '篮子唯一标识符';
COMMENT ON COLUMN baskets.name IS '篮子名称';
COMMENT ON COLUMN baskets.description IS '篮子描述信息';
COMMENT ON COLUMN baskets.created_at IS '记录创建时间';
COMMENT ON COLUMN baskets.updated_at IS '记录最后更新时间';

-- 篮子成分表
CREATE TABLE basket_items (
    id VARCHAR(36) PRIMARY KEY,
    basket_id VARCHAR(50) NOT NULL REFERENCES baskets(id) ON DELETE CASCADE,
    ts_code VARCHAR(12) NOT NULL REFERENCES stock_basic(ts_code) ON DELETE CASCADE,
    weight FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE basket_items IS '篮子成分表';
COMMENT ON COLUMN basket_items.id IS '成分项唯一标识符';
COMMENT ON COLUMN basket_items.basket_id IS '关联篮子ID';
COMMENT ON COLUMN basket_items.ts_code IS '股票代码';
COMMENT ON COLUMN basket_items.weight IS '成分在篮子中的权重';
COMMENT ON COLUMN basket_items.created_at IS '记录创建时间';

CREATE INDEX idx_basket_items_basket_id ON basket_items(basket_id);
CREATE INDEX idx_basket_items_ts_code ON basket_items(ts_code);

-- ------------------------------------------------------------
-- 1.7 ETF基础数据
-- ------------------------------------------------------------

-- ETF基准指数列表信息（字段对齐 Tushare etf_index 接口）
CREATE TABLE IF NOT EXISTS etf_index (
    ts_code VARCHAR(20) PRIMARY KEY,
    indx_name VARCHAR(200),
    indx_csname VARCHAR(100),
    pub_party_name VARCHAR(200),
    pub_date TIMESTAMPTZ,
    base_date TIMESTAMPTZ,
    bp DOUBLE PRECISION,
    adj_circle VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE etf_index IS 'ETF基准指数列表信息（对齐 Tushare etf_index 接口）';
COMMENT ON COLUMN etf_index.ts_code IS '指数代码';
COMMENT ON COLUMN etf_index.indx_name IS '指数全称';
COMMENT ON COLUMN etf_index.indx_csname IS '指数简称';
COMMENT ON COLUMN etf_index.pub_party_name IS '发布机构';
COMMENT ON COLUMN etf_index.pub_date IS '发布日期';
COMMENT ON COLUMN etf_index.base_date IS '指数基日';
COMMENT ON COLUMN etf_index.bp IS '指数基点';
COMMENT ON COLUMN etf_index.adj_circle IS '调整周期';

-- ETF基础信息表
CREATE TABLE IF NOT EXISTS etf_basic (
    ts_code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    management VARCHAR(200),
    custodian VARCHAR(200),
    fund_type VARCHAR(50),
    found_date TIMESTAMPTZ,
    due_date TIMESTAMPTZ,
    list_date TIMESTAMPTZ,
    issue_date TIMESTAMPTZ,
    delist_date TIMESTAMPTZ,
    issue_amount DOUBLE PRECISION,
    m_fee DOUBLE PRECISION,
    c_fee DOUBLE PRECISION,
    duration_year DOUBLE PRECISION,
    p_value DOUBLE PRECISION,
    min_amount DOUBLE PRECISION,
    exp_return DOUBLE PRECISION,
    benchmark VARCHAR(200),
    status VARCHAR(1),
    invest_type VARCHAR(100),
    market VARCHAR(2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE etf_basic IS '国内ETF基础信息（字段对齐 Tushare fund_basic）';
COMMENT ON COLUMN etf_basic.ts_code IS '基金代码';
COMMENT ON COLUMN etf_basic.name IS '基金简称';
COMMENT ON COLUMN etf_basic.management IS '管理人';
COMMENT ON COLUMN etf_basic.custodian IS '托管人';
COMMENT ON COLUMN etf_basic.fund_type IS '投资类型';
COMMENT ON COLUMN etf_basic.found_date IS '成立日期';
COMMENT ON COLUMN etf_basic.list_date IS '上市日期';
COMMENT ON COLUMN etf_basic.status IS '存续状态: L上市/D退市';
COMMENT ON COLUMN etf_basic.market IS '市场: E-上交所 S-深交所';
COMMENT ON COLUMN etf_basic.benchmark IS '业绩基准';

-- ------------------------------------------------------------
-- 1.8 回测模块
-- ------------------------------------------------------------

-- 回测任务表
CREATE TABLE backtest_tasks (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    strategy_id VARCHAR(36) NOT NULL REFERENCES strategies(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    config JSONB NOT NULL DEFAULT '{}'::JSONB,
    progress FLOAT DEFAULT 0,
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE backtest_tasks IS '回测任务表';
COMMENT ON COLUMN backtest_tasks.id IS '任务唯一标识';
COMMENT ON COLUMN backtest_tasks.user_id IS '发起回测的用户ID';
COMMENT ON COLUMN backtest_tasks.strategy_id IS '被回测的策略ID';
COMMENT ON COLUMN backtest_tasks.name IS '回测任务名称';
COMMENT ON COLUMN backtest_tasks.description IS '回测任务描述';
COMMENT ON COLUMN backtest_tasks.status IS '任务状态：pending-等待中, running-运行中, completed-完成, failed-失败, cancelled-已取消';
COMMENT ON COLUMN backtest_tasks.config IS '回测配置（JSON格式）';
COMMENT ON COLUMN backtest_tasks.progress IS '回测进度（百分比）';
COMMENT ON COLUMN backtest_tasks.result IS '回测结果（JSON格式，包含汇总指标）';
COMMENT ON COLUMN backtest_tasks.error_message IS '错误信息（如果任务失败）';
COMMENT ON COLUMN backtest_tasks.started_at IS '任务开始时间';
COMMENT ON COLUMN backtest_tasks.completed_at IS '任务完成时间';

-- 回测交易记录表
CREATE TABLE backtest_trades (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
    trade_time TIMESTAMPTZ NOT NULL,
    ts_code VARCHAR(12) NOT NULL,
    direction VARCHAR(4) NOT NULL CHECK (direction IN ('buy', 'sell')),
    price NUMERIC(10, 4) NOT NULL,
    volume INT NOT NULL,
    value NUMERIC(16, 4) NOT NULL,
    commission NUMERIC(10, 4) NOT NULL,
    tax NUMERIC(10, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE backtest_trades IS '回测交易记录表';
COMMENT ON COLUMN backtest_trades.task_id IS '关联的回测任务ID';
COMMENT ON COLUMN backtest_trades.trade_time IS '交易时间';
COMMENT ON COLUMN backtest_trades.ts_code IS '股票代码';
COMMENT ON COLUMN backtest_trades.direction IS '交易方向：buy-买入, sell-卖出';
COMMENT ON COLUMN backtest_trades.price IS '成交价格';
COMMENT ON COLUMN backtest_trades.volume IS '成交数量（股）';
COMMENT ON COLUMN backtest_trades.value IS '成交金额';
COMMENT ON COLUMN backtest_trades.commission IS '交易佣金';
COMMENT ON COLUMN backtest_trades.tax IS '交易税费';

-- 回测持仓快照表
CREATE TABLE backtest_positions (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(12) NOT NULL,
    volume INT NOT NULL DEFAULT 0,
    cost_price NUMERIC(10, 4) NOT NULL,
    market_value NUMERIC(16, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (task_id, trade_date, ts_code)
);

COMMENT ON TABLE backtest_positions IS '回测持仓快照表';
COMMENT ON COLUMN backtest_positions.task_id IS '关联的回测任务ID';
COMMENT ON COLUMN backtest_positions.trade_date IS '交易日';
COMMENT ON COLUMN backtest_positions.ts_code IS '股票代码';
COMMENT ON COLUMN backtest_positions.volume IS '持仓数量';
COMMENT ON COLUMN backtest_positions.cost_price IS '平均成本价';
COMMENT ON COLUMN backtest_positions.market_value IS '持仓市值';

-- 回测参数配置表
CREATE TABLE backtest_parameters (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
    param_category VARCHAR(50) NOT NULL,
    param_name VARCHAR(100) NOT NULL,
    param_value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE backtest_parameters IS '回测参数配置表';
COMMENT ON COLUMN backtest_parameters.task_id IS '回测任务ID';
COMMENT ON COLUMN backtest_parameters.param_category IS '参数分类：market/cost/risk/strategy';
COMMENT ON COLUMN backtest_parameters.param_name IS '参数名称';
COMMENT ON COLUMN backtest_parameters.param_value IS '参数值（JSON格式）';
COMMENT ON COLUMN backtest_parameters.description IS '参数描述';

CREATE INDEX IF NOT EXISTS idx_backtest_parameters_task_id ON backtest_parameters(task_id);

-- 回测场景表
CREATE TABLE backtest_scenarios (
    id VARCHAR(36) PRIMARY KEY,
    scenario_id VARCHAR(36) NOT NULL UNIQUE,
    scenario_name VARCHAR(100) NOT NULL,
    description TEXT,
    market_conditions JSONB NOT NULL,
    economic_conditions JSONB,
    risk_factors JSONB,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE backtest_scenarios IS '回测场景表';
COMMENT ON COLUMN backtest_scenarios.scenario_id IS '场景ID（UUID）';
COMMENT ON COLUMN backtest_scenarios.scenario_name IS '场景名称';
COMMENT ON COLUMN backtest_scenarios.description IS '场景描述';
COMMENT ON COLUMN backtest_scenarios.market_conditions IS '市场条件（JSON格式）';
COMMENT ON COLUMN backtest_scenarios.economic_conditions IS '经济条件（JSON格式）';
COMMENT ON COLUMN backtest_scenarios.risk_factors IS '风险因子（JSON格式）';
COMMENT ON COLUMN backtest_scenarios.created_by IS '创建人ID';

CREATE INDEX idx_backtest_scenarios_name ON backtest_scenarios(scenario_name);

-- 回测对比结果表
CREATE TABLE backtest_comparisons (
    id VARCHAR(36) PRIMARY KEY,
    comparison_id VARCHAR(36) NOT NULL UNIQUE,
    comparison_name VARCHAR(100) NOT NULL,
    description TEXT,
    base_task_id VARCHAR(36) REFERENCES backtest_tasks(id),
    compared_tasks JSONB NOT NULL,
    comparison_metrics JSONB NOT NULL,
    comparison_results JSONB,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE backtest_comparisons IS '回测对比结果表';
COMMENT ON COLUMN backtest_comparisons.comparison_id IS '对比ID（UUID）';
COMMENT ON COLUMN backtest_comparisons.comparison_name IS '对比名称';
COMMENT ON COLUMN backtest_comparisons.description IS '对比描述';
COMMENT ON COLUMN backtest_comparisons.base_task_id IS '基准回测任务ID';
COMMENT ON COLUMN backtest_comparisons.compared_tasks IS '对比任务列表（JSON格式）';
COMMENT ON COLUMN backtest_comparisons.comparison_metrics IS '对比指标（JSON格式）';
COMMENT ON COLUMN backtest_comparisons.comparison_results IS '对比结果（JSON格式）';
COMMENT ON COLUMN backtest_comparisons.created_by IS '创建人ID';

CREATE INDEX idx_backtest_comparisons_name ON backtest_comparisons(comparison_name);

-- 回测资源使用表
CREATE TABLE backtest_resource_usage (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC(12,4) NOT NULL,
    unit VARCHAR(20),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE backtest_resource_usage IS '回测资源使用表';
COMMENT ON COLUMN backtest_resource_usage.task_id IS '回测任务ID';
COMMENT ON COLUMN backtest_resource_usage.resource_type IS '资源类型：cpu/memory/disk/network';
COMMENT ON COLUMN backtest_resource_usage.metric_name IS '指标名称';
COMMENT ON COLUMN backtest_resource_usage.metric_value IS '指标值';
COMMENT ON COLUMN backtest_resource_usage.unit IS '单位';
COMMENT ON COLUMN backtest_resource_usage.recorded_at IS '记录时间';

CREATE INDEX idx_backtest_resource_usage_task_id ON backtest_resource_usage(task_id);
CREATE INDEX idx_backtest_resource_usage_type ON backtest_resource_usage(resource_type);

-- ------------------------------------------------------------
-- 1.9 风控管理模块
-- ------------------------------------------------------------

-- 风控规则表
CREATE TABLE risk_rules (
    id VARCHAR(36) PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    condition JSONB NOT NULL,
    action VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE risk_rules IS '风控规则配置表';
COMMENT ON COLUMN risk_rules.rule_name IS '风控规则名称';
COMMENT ON COLUMN risk_rules.rule_type IS '规则类型：position_limit-持仓限制, daily_loss_limit-单日亏损限制, blacklist-黑名单, etc.';
COMMENT ON COLUMN risk_rules.condition IS '规则触发条件（JSON格式，如{"max_position_ratio": 0.2, "max_daily_loss": 0.05}）';
COMMENT ON COLUMN risk_rules.action IS '触发动作：alert-报警, stop_strategy-停止策略, cancel_orders-撤单, etc.';
COMMENT ON COLUMN risk_rules.is_active IS '规则是否启用';

-- ------------------------------------------------------------
-- 1.10 系统管理表
-- ------------------------------------------------------------

-- 数据同步任务记录表
CREATE TABLE data_sync_tasks (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL UNIQUE,
    task_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(36) REFERENCES sys_users(id),
    data_types JSON,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    parameters JSON,
    total_records INT DEFAULT 0,
    processed_records INT DEFAULT 0,
    records_processed INT DEFAULT 0,
    records_succeeded INT DEFAULT 0,
    records_failed INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

COMMENT ON TABLE data_sync_tasks IS '数据同步任务记录表';
COMMENT ON COLUMN data_sync_tasks.task_id IS '任务唯一标识符（如 sync_abc12345）';
COMMENT ON COLUMN data_sync_tasks.task_type IS '任务类型：daily-日线, minute-分钟线, financial-财务数据, etc.';
COMMENT ON COLUMN data_sync_tasks.user_id IS '用户ID';
COMMENT ON COLUMN data_sync_tasks.data_types IS '数据类型列表（JSON格式）';
COMMENT ON COLUMN data_sync_tasks.status IS '任务状态：pending-等待中, running-执行中, completed-成功, failed-失败, cancelled-已取消';
COMMENT ON COLUMN data_sync_tasks.start_time IS '任务开始时间';
COMMENT ON COLUMN data_sync_tasks.end_time IS '任务结束时间';
COMMENT ON COLUMN data_sync_tasks.parameters IS '任务参数（JSON格式）';
COMMENT ON COLUMN data_sync_tasks.total_records IS '总记录数';
COMMENT ON COLUMN data_sync_tasks.processed_records IS '已处理记录数';
COMMENT ON COLUMN data_sync_tasks.records_processed IS '已处理记录数（别名）';
COMMENT ON COLUMN data_sync_tasks.records_succeeded IS '成功记录数';
COMMENT ON COLUMN data_sync_tasks.records_failed IS '失败记录数';
COMMENT ON COLUMN data_sync_tasks.error_message IS '错误信息（如果任务失败）';
COMMENT ON COLUMN data_sync_tasks.completed_at IS '完成时间';

-- 系统配置表
CREATE TABLE system_configs (
    id VARCHAR(36) PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type VARCHAR(50) DEFAULT 'string',
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    updated_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE system_configs IS '系统配置表';
COMMENT ON COLUMN system_configs.config_key IS '配置键（唯一）';
COMMENT ON COLUMN system_configs.config_value IS '配置值';
COMMENT ON COLUMN system_configs.config_type IS '配置类型：string, int, float, bool, json';
COMMENT ON COLUMN system_configs.description IS '配置描述';
COMMENT ON COLUMN system_configs.is_public IS '是否公开配置';
COMMENT ON COLUMN system_configs.created_by IS '创建人';
COMMENT ON COLUMN system_configs.updated_by IS '更新人';

-- 定时任务调度表
CREATE TABLE scheduled_tasks (
    id VARCHAR(36) PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    task_config JSONB NOT NULL,
    cron_expression VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active',
    last_run_time TIMESTAMPTZ,
    next_run_time TIMESTAMPTZ,
    run_count INT DEFAULT 0,
    error_count INT DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE scheduled_tasks IS '定时任务调度表';
COMMENT ON COLUMN scheduled_tasks.task_name IS '任务名称';
COMMENT ON COLUMN scheduled_tasks.task_type IS '任务类型：data_sync, strategy_run, report_gen, etc.';
COMMENT ON COLUMN scheduled_tasks.task_config IS '任务配置（JSON格式）';
COMMENT ON COLUMN scheduled_tasks.cron_expression IS 'Cron表达式';
COMMENT ON COLUMN scheduled_tasks.status IS '任务状态：active, paused, disabled';
COMMENT ON COLUMN scheduled_tasks.last_run_time IS '最后执行时间';
COMMENT ON COLUMN scheduled_tasks.next_run_time IS '下次执行时间';
COMMENT ON COLUMN scheduled_tasks.run_count IS '执行次数';
COMMENT ON COLUMN scheduled_tasks.error_count IS '错误次数';
COMMENT ON COLUMN scheduled_tasks.last_error IS '最后错误信息';

-- 系统操作日志表
CREATE TABLE system_logs (
    id VARCHAR(36) PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL,
    module VARCHAR(50) NOT NULL,
    user_id VARCHAR(36) REFERENCES sys_users(id),
    action VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(50),
    user_agent TEXT,
    execution_time INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE system_logs IS '系统操作日志表';
COMMENT ON COLUMN system_logs.log_level IS '日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL';
COMMENT ON COLUMN system_logs.module IS '模块名称';
COMMENT ON COLUMN system_logs.user_id IS '操作用户ID';
COMMENT ON COLUMN system_logs.action IS '操作行为';
COMMENT ON COLUMN system_logs.details IS '操作详情（JSON格式）';
COMMENT ON COLUMN system_logs.ip_address IS 'IP地址';
COMMENT ON COLUMN system_logs.user_agent IS '用户代理';
COMMENT ON COLUMN system_logs.execution_time IS '执行时间（毫秒）';

CREATE INDEX idx_system_logs_created_at ON system_logs(created_at);
CREATE INDEX idx_system_logs_user_id ON system_logs(user_id);
CREATE INDEX idx_system_logs_module ON system_logs(module);
CREATE INDEX idx_system_logs_log_level ON system_logs(log_level);

-- 操作日志表
CREATE TABLE sys_operation_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    module VARCHAR(50) NOT NULL,
    operation VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details JSONB,
    ip_address VARCHAR(50),
    user_agent TEXT,
    status VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'failed', 'pending')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_operation_logs IS '系统操作日志表';
COMMENT ON COLUMN sys_operation_logs.user_id IS '操作用户ID';
COMMENT ON COLUMN sys_operation_logs.module IS '操作所属模块';
COMMENT ON COLUMN sys_operation_logs.operation IS '操作类型（create, update, delete, query, execute等）';
COMMENT ON COLUMN sys_operation_logs.action IS '具体操作描述';
COMMENT ON COLUMN sys_operation_logs.details IS '操作详情（JSON格式）';
COMMENT ON COLUMN sys_operation_logs.ip_address IS '操作者IP地址';
COMMENT ON COLUMN sys_operation_logs.user_agent IS '用户代理信息';
COMMENT ON COLUMN sys_operation_logs.status IS '操作状态';

CREATE INDEX idx_sys_operation_logs_user_id ON sys_operation_logs(user_id);
CREATE INDEX idx_sys_operation_logs_module ON sys_operation_logs(module);
CREATE INDEX idx_sys_operation_logs_created_at ON sys_operation_logs(created_at DESC);

-- 审计日志表
CREATE TABLE sys_audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    audit_type VARCHAR(50) NOT NULL CHECK (audit_type IN ('login', 'logout', 'access', 'data_change', 'config_change', 'security_event')),
    user_id VARCHAR(36) REFERENCES sys_users(id),
    username VARCHAR(50),
    ip_address VARCHAR(50),
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    before_state JSONB,
    after_state JSONB,
    changes JSONB,
    is_success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    session_id VARCHAR(100),
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_audit_logs IS '系统审计日志表';
COMMENT ON COLUMN sys_audit_logs.audit_type IS '审计类型';
COMMENT ON COLUMN sys_audit_logs.resource_type IS '资源类型（user, strategy, order, config等）';
COMMENT ON COLUMN sys_audit_logs.resource_id IS '资源ID';
COMMENT ON COLUMN sys_audit_logs.before_state IS '变更前状态（JSON格式）';
COMMENT ON COLUMN sys_audit_logs.after_state IS '变更后状态（JSON格式）';
COMMENT ON COLUMN sys_audit_logs.changes IS '变更内容（JSON格式，只记录变化的字段）';

CREATE INDEX idx_sys_audit_logs_user_id ON sys_audit_logs(user_id);
CREATE INDEX idx_sys_audit_logs_audit_type ON sys_audit_logs(audit_type);
CREATE INDEX idx_sys_audit_logs_resource ON sys_audit_logs(resource_type, resource_id);
CREATE INDEX idx_sys_audit_logs_created_at ON sys_audit_logs(created_at DESC);

-- 消息通知表
CREATE TABLE sys_notifications (
    id VARCHAR(36) PRIMARY KEY,
    notification_type VARCHAR(50) NOT NULL CHECK (notification_type IN ('system', 'alert', 'trade', 'strategy', 'data', 'report')),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    metainfo JSONB,
    sender_type VARCHAR(50) DEFAULT 'system',
    sender_id VARCHAR(100),
    recipient_type VARCHAR(20) DEFAULT 'user' CHECK (recipient_type IN ('user', 'role', 'all')),
    recipient_id VARCHAR(36),
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_notifications IS '系统消息通知表';
COMMENT ON COLUMN sys_notifications.notification_type IS '通知类型';
COMMENT ON COLUMN sys_notifications.priority IS '优先级';
COMMENT ON COLUMN sys_notifications.sender_type IS '发送者类型（system, user, strategy, monitor等）';
COMMENT ON COLUMN sys_notifications.sender_id IS '发送者ID';
COMMENT ON COLUMN sys_notifications.recipient_type IS '接收者类型';
COMMENT ON COLUMN sys_notifications.recipient_id IS '接收者ID（用户ID或角色ID）';
COMMENT ON COLUMN sys_notifications.expires_at IS '过期时间';

CREATE INDEX idx_sys_notifications_recipient ON sys_notifications(recipient_type, recipient_id);
CREATE INDEX idx_sys_notifications_read_status ON sys_notifications(is_read);
CREATE INDEX idx_sys_notifications_created_at ON sys_notifications(created_at DESC);
CREATE INDEX idx_sys_notifications_type ON sys_notifications(notification_type);

-- 任务调度表
CREATE TABLE sys_scheduled_tasks (
    id VARCHAR(50) PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('cron', 'interval', 'date', 'manual')),
    task_module VARCHAR(50) NOT NULL,
    schedule_config JSONB NOT NULL,
    task_config JSONB DEFAULT '{}'::JSONB,
    last_run_at TIMESTAMPTZ,
    last_run_result VARCHAR(20),
    last_run_duration INT,
    next_run_at TIMESTAMPTZ,
    total_runs INT DEFAULT 0,
    success_runs INT DEFAULT 0,
    failed_runs INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    max_retries INT DEFAULT 3,
    retry_delay INT DEFAULT 60,
    timeout_seconds INT DEFAULT 300,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_scheduled_tasks IS '系统定时任务调度表';
COMMENT ON COLUMN sys_scheduled_tasks.id IS '任务唯一标识';
COMMENT ON COLUMN sys_scheduled_tasks.task_name IS '任务名称';
COMMENT ON COLUMN sys_scheduled_tasks.task_type IS '任务调度类型（cron表达式、时间间隔、指定时间、手动）';
COMMENT ON COLUMN sys_scheduled_tasks.task_module IS '任务所属模块';
COMMENT ON COLUMN sys_scheduled_tasks.schedule_config IS '调度配置（JSON格式，如cron表达式）';
COMMENT ON COLUMN sys_scheduled_tasks.task_config IS '任务配置（JSON格式）';
COMMENT ON COLUMN sys_scheduled_tasks.last_run_result IS '上次运行结果（success, failed, skipped）';

CREATE INDEX idx_sys_scheduled_tasks_active ON sys_scheduled_tasks(is_active);
CREATE INDEX idx_sys_scheduled_tasks_next_run ON sys_scheduled_tasks(next_run_at);
CREATE INDEX idx_sys_scheduled_tasks_module ON sys_scheduled_tasks(task_module);

-- 报警记录表
CREATE TABLE monitor_alerts (
    id VARCHAR(36) PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL CHECK (alert_level IN ('critical', 'warning', 'info')),
    source_module VARCHAR(50) NOT NULL,
    source_id VARCHAR(100),
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    metainfo JSONB,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved', 'suppressed')),
    acknowledged_by VARCHAR(36) REFERENCES sys_users(id),
    acknowledged_at TIMESTAMPTZ,
    resolved_by VARCHAR(36) REFERENCES sys_users(id),
    resolved_at TIMESTAMPTZ,
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB DEFAULT '["email", "wechat"]'::JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE monitor_alerts IS '监控报警记录表';
COMMENT ON COLUMN monitor_alerts.alert_type IS '报警类型（system_error, risk_trigger, data_quality, performance等）';
COMMENT ON COLUMN monitor_alerts.alert_level IS '报警级别';
COMMENT ON COLUMN monitor_alerts.source_module IS '报警来源模块';
COMMENT ON COLUMN monitor_alerts.source_id IS '报警来源ID（如策略ID、任务ID等）';
COMMENT ON COLUMN monitor_alerts.title IS '报警标题';
COMMENT ON COLUMN monitor_alerts.message IS '报警详细信息';
COMMENT ON COLUMN monitor_alerts.metainfo IS '报警元数据（JSON格式）';
COMMENT ON COLUMN monitor_alerts.status IS '报警状态';
COMMENT ON COLUMN monitor_alerts.notification_channels IS '通知渠道（email, wechat, dingtalk, sms等）';

CREATE INDEX idx_monitor_alerts_status ON monitor_alerts(status);
CREATE INDEX idx_monitor_alerts_level ON monitor_alerts(alert_level);
CREATE INDEX idx_monitor_alerts_type ON monitor_alerts(alert_type);
CREATE INDEX idx_monitor_alerts_created_at ON monitor_alerts(created_at DESC);
CREATE INDEX idx_monitor_alerts_source ON monitor_alerts(source_module, source_id);

-- 监控任务表
CREATE TABLE monitor_tasks (
    id VARCHAR(36) PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(100),
    schedule_config JSONB NOT NULL,
    check_config JSONB NOT NULL,
    alert_config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE monitor_tasks IS '监控任务表';
COMMENT ON COLUMN monitor_tasks.task_name IS '任务名称';
COMMENT ON COLUMN monitor_tasks.task_type IS '任务类型：system/strategy/data/trade';
COMMENT ON COLUMN monitor_tasks.target_type IS '监控目标类型';
COMMENT ON COLUMN monitor_tasks.target_id IS '监控目标ID';
COMMENT ON COLUMN monitor_tasks.schedule_config IS '调度配置（JSON格式）';
COMMENT ON COLUMN monitor_tasks.check_config IS '检查配置（JSON格式）';
COMMENT ON COLUMN monitor_tasks.alert_config IS '报警配置（JSON格式）';
COMMENT ON COLUMN monitor_tasks.is_active IS '是否激活';

CREATE INDEX idx_monitor_tasks_type ON monitor_tasks(task_type);
CREATE INDEX idx_monitor_tasks_active ON monitor_tasks(is_active);

-- 监控阈值配置表
CREATE TABLE monitor_thresholds (
    id VARCHAR(36) PRIMARY KEY,
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    warning_threshold NUMERIC(12,4),
    critical_threshold NUMERIC(12,4),
    min_value NUMERIC(12,4),
    max_value NUMERIC(12,4),
    unit VARCHAR(20),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE monitor_thresholds IS '监控阈值配置表';
COMMENT ON COLUMN monitor_thresholds.metric_type IS '指标类型';
COMMENT ON COLUMN monitor_thresholds.metric_name IS '指标名称';
COMMENT ON COLUMN monitor_thresholds.warning_threshold IS '警告阈值';
COMMENT ON COLUMN monitor_thresholds.critical_threshold IS '严重阈值';
COMMENT ON COLUMN monitor_thresholds.min_value IS '最小值';
COMMENT ON COLUMN monitor_thresholds.max_value IS '最大值';
COMMENT ON COLUMN monitor_thresholds.unit IS '单位';
COMMENT ON COLUMN monitor_thresholds.description IS '描述';

CREATE INDEX idx_monitor_thresholds_type ON monitor_thresholds(metric_type);

-- 报警模板表
CREATE TABLE alert_templates (
    id VARCHAR(36) PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL,
    title_template TEXT NOT NULL,
    message_template TEXT NOT NULL,
    notification_channels JSONB DEFAULT '["email"]'::JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE alert_templates IS '报警模板表';
COMMENT ON COLUMN alert_templates.template_name IS '模板名称';
COMMENT ON COLUMN alert_templates.alert_type IS '报警类型';
COMMENT ON COLUMN alert_templates.alert_level IS '报警级别';
COMMENT ON COLUMN alert_templates.title_template IS '标题模板';
COMMENT ON COLUMN alert_templates.message_template IS '消息模板';
COMMENT ON COLUMN alert_templates.notification_channels IS '通知渠道';

CREATE INDEX idx_alert_templates_type ON alert_templates(alert_type);

-- 报警发送日志表
CREATE TABLE alert_delivery_logs (
    id VARCHAR(36) PRIMARY KEY,
    alert_id VARCHAR(36) NOT NULL REFERENCES monitor_alerts(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL,
    recipient VARCHAR(200) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'delivered')),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE alert_delivery_logs IS '报警发送日志表';
COMMENT ON COLUMN alert_delivery_logs.alert_id IS '报警ID';
COMMENT ON COLUMN alert_delivery_logs.channel IS '发送渠道：email/wechat/dingtalk/sms';
COMMENT ON COLUMN alert_delivery_logs.recipient IS '接收者';
COMMENT ON COLUMN alert_delivery_logs.status IS '发送状态';
COMMENT ON COLUMN alert_delivery_logs.sent_at IS '发送时间';
COMMENT ON COLUMN alert_delivery_logs.delivered_at IS '送达时间';
COMMENT ON COLUMN alert_delivery_logs.error_message IS '错误信息';

CREATE INDEX idx_alert_delivery_logs_alert_id ON alert_delivery_logs(alert_id);
CREATE INDEX idx_alert_delivery_logs_status ON alert_delivery_logs(status);

-- ------------------------------------------------------------
-- 1.11 因子相关表
-- ------------------------------------------------------------

-- 因子定义表
CREATE TABLE factor_definitions (
    id VARCHAR(36) PRIMARY KEY,
    factor_code VARCHAR(50) UNIQUE NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    factor_type VARCHAR(30) NOT NULL CHECK (factor_type IN ('technical', 'fundamental', 'macro', 'alternative', 'custom')),
    category VARCHAR(50),
    description TEXT,
    formula TEXT,
    parameters JSONB DEFAULT '{}'::JSONB,
    data_requirements JSONB,
    output_type VARCHAR(20) DEFAULT 'float',
    calculation_frequency VARCHAR(20) DEFAULT 'daily' CHECK (calculation_frequency IN ('minute', 'daily', 'weekly', 'monthly')),
    is_public BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE factor_definitions IS '量化因子定义表';
COMMENT ON COLUMN factor_definitions.factor_code IS '因子代码（唯一标识）';
COMMENT ON COLUMN factor_definitions.factor_name IS '因子名称';
COMMENT ON COLUMN factor_definitions.factor_type IS '因子类型（技术指标、基本面、宏观、另类数据、自定义）';
COMMENT ON COLUMN factor_definitions.formula IS '因子计算公式（可以是Python表达式或函数名）';
COMMENT ON COLUMN factor_definitions.parameters IS '因子参数（JSON格式）';
COMMENT ON COLUMN factor_definitions.data_requirements IS '数据需求（JSON格式，描述计算所需的数据）';
COMMENT ON COLUMN factor_definitions.output_type IS '输出类型（float, int, bool, string）';

CREATE INDEX idx_factor_definitions_type ON factor_definitions(factor_type);
CREATE INDEX idx_factor_definitions_category ON factor_definitions(category);
CREATE INDEX idx_factor_definitions_active ON factor_definitions(is_active);

-- 数据质量检查记录表
CREATE TABLE data_quality_checks (
    id VARCHAR(36) PRIMARY KEY,
    check_type VARCHAR(50) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    check_date DATE NOT NULL,
    total_records INT NOT NULL,
    valid_records INT NOT NULL,
    invalid_records INT NOT NULL,
    missing_records INT DEFAULT 0,
    duplicate_records INT DEFAULT 0,
    check_results JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'completed',
    checked_by VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE data_quality_checks IS '数据质量检查记录表';
COMMENT ON COLUMN data_quality_checks.check_type IS '检查类型：daily/batch/adhoc';
COMMENT ON COLUMN data_quality_checks.data_type IS '数据类型：stock_daily/stock_minutes/financial';
COMMENT ON COLUMN data_quality_checks.check_date IS '检查日期';
COMMENT ON COLUMN data_quality_checks.total_records IS '总记录数';
COMMENT ON COLUMN data_quality_checks.valid_records IS '有效记录数';
COMMENT ON COLUMN data_quality_checks.invalid_records IS '无效记录数';
COMMENT ON COLUMN data_quality_checks.missing_records IS '缺失记录数';
COMMENT ON COLUMN data_quality_checks.duplicate_records IS '重复记录数';
COMMENT ON COLUMN data_quality_checks.check_results IS '检查结果（JSON格式）';
COMMENT ON COLUMN data_quality_checks.status IS '检查状态';
COMMENT ON COLUMN data_quality_checks.checked_by IS '检查人/系统';

CREATE INDEX IF NOT EXISTS idx_data_quality_checks_date ON data_quality_checks(check_date DESC);
CREATE INDEX idx_data_quality_checks_type ON data_quality_checks(data_type);

-- 数据修复记录表
CREATE TABLE data_fix_records (
    id VARCHAR(36) PRIMARY KEY,
    quality_check_id VARCHAR(36) REFERENCES data_quality_checks(id),
    data_type VARCHAR(50) NOT NULL,
    fix_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fix_type VARCHAR(50) NOT NULL,
    records_fixed INT NOT NULL,
    fix_details JSONB NOT NULL,
    fix_status VARCHAR(20) DEFAULT 'completed',
    fixed_by VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE data_fix_records IS '数据修复记录表';
COMMENT ON COLUMN data_fix_records.quality_check_id IS '关联的质量检查ID';
COMMENT ON COLUMN data_fix_records.data_type IS '数据类型';
COMMENT ON COLUMN data_fix_records.fix_date IS '修复日期';
COMMENT ON COLUMN data_fix_records.fix_type IS '修复类型：missing/duplicate/invalid';
COMMENT ON COLUMN data_fix_records.records_fixed IS '修复记录数';
COMMENT ON COLUMN data_fix_records.fix_details IS '修复详情（JSON格式）';
COMMENT ON COLUMN data_fix_records.fix_status IS '修复状态';
COMMENT ON COLUMN data_fix_records.fixed_by IS '修复人/系统';

CREATE INDEX idx_data_fix_records_date ON data_fix_records(fix_date DESC);

-- 数据质量指标历史表
CREATE TABLE data_quality_issues (
    id VARCHAR(36) PRIMARY KEY,
    metric_date DATE NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC(12,4) NOT NULL,
    target_value NUMERIC(12,4),
    status VARCHAR(20) DEFAULT 'normal',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE data_quality_metrics IS '数据质量指标历史表';
COMMENT ON COLUMN data_quality_metrics.metric_date IS '指标日期';
COMMENT ON COLUMN data_quality_metrics.data_type IS '数据类型';
COMMENT ON COLUMN data_quality_metrics.metric_name IS '指标名称';
COMMENT ON COLUMN data_quality_metrics.metric_value IS '指标值';
COMMENT ON COLUMN data_quality_metrics.target_value IS '目标值';
COMMENT ON COLUMN data_quality_metrics.status IS '状态：normal/warning/critical';

CREATE INDEX idx_data_quality_metrics_date ON data_quality_metrics(metric_date DESC);
CREATE INDEX idx_data_quality_metrics_type ON data_quality_metrics(data_type);

-- ------------------------------------------------------------
-- 1.12 分析相关表
-- ------------------------------------------------------------

-- 分析报告表
CREATE TABLE analysis_reports (
    id VARCHAR(36) PRIMARY KEY,
    report_type VARCHAR(50) NOT NULL CHECK (report_type IN ('daily', 'weekly', 'monthly', 'performance', 'risk', 'custom')),
    report_name VARCHAR(200) NOT NULL,
    report_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    report_data JSONB,
    format VARCHAR(20) DEFAULT 'json' CHECK (format IN ('json', 'html', 'pdf', 'excel')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'completed', 'failed')),
    generated_by VARCHAR(36) REFERENCES sys_users(id),
    generated_at TIMESTAMPTZ,
    file_path TEXT,
    file_size BIGINT,
    is_public BOOLEAN DEFAULT FALSE,
    tags JSONB DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE analysis_reports IS '分析报告表';
COMMENT ON COLUMN analysis_reports.report_type IS '报告类型';
COMMENT ON COLUMN analysis_reports.report_name IS '报告名称';
COMMENT ON COLUMN analysis_reports.report_config IS '报告生成配置（JSON格式）';
COMMENT ON COLUMN analysis_reports.report_data IS '报告数据（JSON格式）';
COMMENT ON COLUMN analysis_reports.format IS '报告格式';
COMMENT ON COLUMN analysis_reports.status IS '报告生成状态';
COMMENT ON COLUMN analysis_reports.file_path IS '报告文件存储路径';
COMMENT ON COLUMN analysis_reports.file_size IS '报告文件大小（字节）';

CREATE INDEX idx_analysis_reports_type ON analysis_reports(report_type);
CREATE INDEX idx_analysis_reports_status ON analysis_reports(status);
CREATE INDEX idx_analysis_reports_created_at ON analysis_reports(created_at DESC);

-- 分析任务表
CREATE TABLE analysis_tasks (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL UNIQUE,
    task_name VARCHAR(200) NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    progress FLOAT DEFAULT 0.0,
    result JSONB,
    report_id VARCHAR(36) REFERENCES analysis_reports(id),
    error_message TEXT,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

COMMENT ON TABLE analysis_tasks IS '分析任务表';
COMMENT ON COLUMN analysis_tasks.task_id IS '任务ID（唯一）';
COMMENT ON COLUMN analysis_tasks.task_name IS '任务名称';
COMMENT ON COLUMN analysis_tasks.analysis_type IS '分析类型：performance/risk/attribution';
COMMENT ON COLUMN analysis_tasks.parameters IS '分析参数（JSON格式）';
COMMENT ON COLUMN analysis_tasks.status IS '任务状态';
COMMENT ON COLUMN analysis_tasks.progress IS '进度';
COMMENT ON COLUMN analysis_tasks.result IS '分析结果（JSON格式）';
COMMENT ON COLUMN analysis_tasks.report_id IS '关联的报告ID';
COMMENT ON COLUMN analysis_tasks.error_message IS '错误信息';

CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status ON analysis_tasks(status);
CREATE INDEX idx_analysis_tasks_type ON analysis_tasks(analysis_type);

-- 分析模板表
CREATE TABLE analysis_templates (
    id VARCHAR(36) PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    template_type VARCHAR(50) NOT NULL,
    description TEXT,
    config_template JSONB NOT NULL,
    output_format VARCHAR(20) DEFAULT 'json',
    is_public BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE analysis_templates IS '分析模板表';
COMMENT ON COLUMN analysis_templates.template_name IS '模板名称';
COMMENT ON COLUMN analysis_templates.template_type IS '模板类型';
COMMENT ON COLUMN analysis_templates.description IS '模板描述';
COMMENT ON COLUMN analysis_templates.config_template IS '配置模板（JSON格式）';
COMMENT ON COLUMN analysis_templates.output_format IS '输出格式';
COMMENT ON COLUMN analysis_templates.is_public IS '是否公开';
COMMENT ON COLUMN analysis_templates.created_by IS '创建人';

CREATE INDEX idx_analysis_templates_type ON analysis_templates(template_type);

-- 报告生成日志表
CREATE TABLE report_generation_logs (
    id VARCHAR(36) PRIMARY KEY,
    report_id VARCHAR(36) REFERENCES analysis_reports(id),
    generation_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INT,
    error_message TEXT,
    generated_by VARCHAR(36) REFERENCES sys_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE report_generation_logs IS '报告生成日志表';
COMMENT ON COLUMN report_generation_logs.report_id IS '报告ID';
COMMENT ON COLUMN report_generation_logs.generation_type IS '生成类型：scheduled/manual';
COMMENT ON COLUMN report_generation_logs.status IS '生成状态';
COMMENT ON COLUMN report_generation_logs.started_at IS '开始时间';
COMMENT ON COLUMN report_generation_logs.completed_at IS '完成时间';
COMMENT ON COLUMN report_generation_logs.duration_ms IS '耗时（毫秒）';
COMMENT ON COLUMN report_generation_logs.error_message IS '错误信息';
COMMENT ON COLUMN report_generation_logs.generated_by IS '生成人';

CREATE INDEX idx_report_generation_logs_report_id ON report_generation_logs(report_id);
CREATE INDEX idx_report_generation_logs_date ON report_generation_logs(started_at DESC);

-- 分析基准表
CREATE TABLE analysis_benchmarks (
    id VARCHAR(36) PRIMARY KEY,
    benchmark_code VARCHAR(20) NOT NULL UNIQUE,
    benchmark_name VARCHAR(100) NOT NULL,
    benchmark_type VARCHAR(50) NOT NULL,
    description TEXT,
    components JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE analysis_benchmarks IS '分析基准表';
COMMENT ON COLUMN analysis_benchmarks.benchmark_code IS '基准代码';
COMMENT ON COLUMN analysis_benchmarks.benchmark_name IS '基准名称';
COMMENT ON COLUMN analysis_benchmarks.benchmark_type IS '基准类型：index/custom/portfolio';
COMMENT ON COLUMN analysis_benchmarks.description IS '描述';
COMMENT ON COLUMN analysis_benchmarks.components IS '成分股（JSON格式）';
COMMENT ON COLUMN analysis_benchmarks.is_active IS '是否激活';

CREATE INDEX idx_analysis_benchmarks_type ON analysis_benchmarks(benchmark_type);

-- ------------------------------------------------------------
-- 1.13 财务数据表
-- ------------------------------------------------------------

-- 财务报表主表
CREATE TABLE financial_statements (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE NOT NULL,
    f_ann_date DATE,
    end_date DATE NOT NULL,
    report_type VARCHAR(20) NOT NULL,
    comp_type VARCHAR(20),
    basic_eps NUMERIC(12, 4),
    diluted_eps NUMERIC(12, 4),
    total_revenue NUMERIC(18, 4),
    revenue NUMERIC(18, 4),
    int_income NUMERIC(18, 4),
    prem_earned NUMERIC(18, 4),
    comm_income NUMERIC(18, 4),
    n_commis_income NUMERIC(18, 4),
    n_oth_income NUMERIC(18, 4),
    n_oth_b_income NUMERIC(18, 4),
    prem_income NUMERIC(18, 4),
    out_prem NUMERIC(18, 4),
    une_prem_reser NUMERIC(18, 4),
    reins_income NUMERIC(18, 4),
    n_sec_tb_income NUMERIC(18, 4),
    n_sec_uw_income NUMERIC(18, 4),
    n_asset_mg_income NUMERIC(18, 4),
    oth_b_income NUMERIC(18, 4),
    fv_value_chg_gain NUMERIC(18, 4),
    invest_income NUMERIC(18, 4),
    ass_invest_income NUMERIC(18, 4),
    forex_gain NUMERIC(18, 4),
    total_cogs NUMERIC(18, 4),
    oper_cost NUMERIC(18, 4),
    int_exp NUMERIC(18, 4),
    comm_exp NUMERIC(18, 4),
    biz_tax_surchg NUMERIC(18, 4),
    sell_exp NUMERIC(18, 4),
    admin_exp NUMERIC(18, 4),
    fin_exp NUMERIC(18, 4),
    assets_impair_loss NUMERIC(18, 4),
    prem_refund NUMERIC(18, 4),
    compen_payout NUMERIC(18, 4),
    reser_insur_liab NUMERIC(18, 4),
    div_payt NUMERIC(18, 4),
    reins_exp NUMERIC(18, 4),
    oper_exp NUMERIC(18, 4),
    compens_payout NUMERIC(18, 4),
    insur_reser NUMERIC(18, 4),
    reinsur_payout NUMERIC(18, 4),
    misc_exp NUMERIC(18, 4),
    operate_profit NUMERIC(18, 4),
    non_oper_income NUMERIC(18, 4),
    non_oper_exp NUMERIC(18, 4),
    nca_disploss NUMERIC(18, 4),
    total_profit NUMERIC(18, 4),
    income_tax NUMERIC(18, 4),
    n_income NUMERIC(18, 4),
    n_income_attr_p NUMERIC(18, 4),
    minority_gain NUMERIC(18, 4),
    oth_compr_income NUMERIC(18, 4),
    t_compr_income NUMERIC(18, 4),
    compr_inc_attr_p NUMERIC(18, 4),
    compr_inc_attr_m_s NUMERIC(18, 4),
    ebit NUMERIC(18, 4),
    ebitda NUMERIC(18, 4),
    insurance_exp NUMERIC(18, 4),
    undist_profit NUMERIC(18, 4),
    distable_profit NUMERIC(18, 4),
    -- 资产负债表核心字段
    total_assets NUMERIC(18, 4),
    total_cur_assets NUMERIC(18, 4),
    total_nca NUMERIC(18, 4),
    total_liab NUMERIC(18, 4),
    total_cur_liab NUMERIC(18, 4),
    total_ncl NUMERIC(18, 4),
    total_hldr_eqy_exc_min_int NUMERIC(18, 4),
    total_hldr_eqy_inc_min_int NUMERIC(18, 4),
    minority_int NUMERIC(18, 4),
    money_cap NUMERIC(18, 4),
    accounts_receiv NUMERIC(18, 4),
    inventories NUMERIC(18, 4),
    -- 现金流量表核心字段
    n_cashflow_act NUMERIC(18, 4),
    n_cashflow_inv_act NUMERIC(18, 4),
    n_cashflow_fin_act NUMERIC(18, 4),
    n_cash NUMERIC(18, 4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE financial_statements IS '上市公司财务报表数据（利润表+资产负债表+现金流量表，通过report_type区分）';
COMMENT ON COLUMN financial_statements.ts_code IS '股票代码';
COMMENT ON COLUMN financial_statements.ann_date IS '公告日期';
COMMENT ON COLUMN financial_statements.end_date IS '报告期截止日期';
COMMENT ON COLUMN financial_statements.report_type IS '报表类型: income-利润表, balance-资产负债表, cashflow-现金流量表';
COMMENT ON COLUMN financial_statements.comp_type IS '公司类型：1-合并报表，2-母公司';
-- 利润表核心字段
COMMENT ON COLUMN financial_statements.basic_eps IS '基本每股收益';
COMMENT ON COLUMN financial_statements.total_revenue IS '营业总收入';
COMMENT ON COLUMN financial_statements.operate_profit IS '营业利润';
COMMENT ON COLUMN financial_statements.total_profit IS '利润总额';
COMMENT ON COLUMN financial_statements.n_income IS '净利润';
COMMENT ON COLUMN financial_statements.ebit IS '息税前利润';
COMMENT ON COLUMN financial_statements.ebitda IS '息税折旧摊销前利润';
-- 资产负债表核心字段
COMMENT ON COLUMN financial_statements.total_assets IS '资产总计';
COMMENT ON COLUMN financial_statements.total_liab IS '负债合计';
COMMENT ON COLUMN financial_statements.total_hldr_eqy_exc_min_int IS '股东权益（不含少数股东）';
COMMENT ON COLUMN financial_statements.total_cur_assets IS '流动资产合计';
COMMENT ON COLUMN financial_statements.total_cur_liab IS '流动负债合计';
COMMENT ON COLUMN financial_statements.money_cap IS '货币资金';
COMMENT ON COLUMN financial_statements.inventories IS '存货';
-- 现金流量表核心字段
COMMENT ON COLUMN financial_statements.n_cashflow_act IS '经营活动净现金流';
COMMENT ON COLUMN financial_statements.n_cashflow_inv_act IS '投资活动净现金流';
COMMENT ON COLUMN financial_statements.n_cashflow_fin_act IS '筹资活动净现金流';
COMMENT ON COLUMN financial_statements.n_cash IS '现金净增加额';
-- 时间戳
COMMENT ON COLUMN financial_statements.created_at IS '创建时间';
COMMENT ON COLUMN financial_statements.updated_at IS '更新时间';

CREATE INDEX idx_financial_statements_ts_code ON financial_statements(ts_code);
CREATE INDEX idx_financial_statements_end_date ON financial_statements(end_date);
CREATE INDEX idx_financial_statements_ann_date ON financial_statements(ann_date);
CREATE INDEX idx_financial_statements_report_type ON financial_statements(report_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_financial_statement_code_date_type ON financial_statements(ts_code, ann_date, report_type);


-- ------------------------------------------------------------
-- 1.14 指数相关表
-- ------------------------------------------------------------

-- 指数基本信息表
CREATE TABLE index_basic (
    ts_code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    fullname VARCHAR(200),
    market VARCHAR(20),
    publisher VARCHAR(100),
    index_type VARCHAR(50),
    category VARCHAR(50),
    base_date DATE,
    base_point NUMERIC(12, 2),
    list_date DATE,
    weight_rule VARCHAR(100),
    "desc" VARCHAR(500),
    exp_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE index_basic IS '指数基本信息表';
COMMENT ON COLUMN index_basic.ts_code IS '指数代码';
COMMENT ON COLUMN index_basic.name IS '指数简称';
COMMENT ON COLUMN index_basic.fullname IS '指数全称';
COMMENT ON COLUMN index_basic.market IS '市场（SSE/SZSE）';
COMMENT ON COLUMN index_basic.publisher IS '发布方';
COMMENT ON COLUMN index_basic.index_type IS '指数类型';
COMMENT ON COLUMN index_basic.category IS '指数类别';
COMMENT ON COLUMN index_basic.base_date IS '基期';
COMMENT ON COLUMN index_basic.base_point IS '基点';
COMMENT ON COLUMN index_basic.list_date IS '发布日期';
COMMENT ON COLUMN index_basic.weight_rule IS '加权方式';
COMMENT ON COLUMN index_basic.desc IS '指数描述';
COMMENT ON COLUMN index_basic.exp_date IS '终止日期';

-- ------------------------------------------------------------
-- 1.15 工作流管理表
-- ------------------------------------------------------------

-- 工作流任务表
CREATE TABLE workflow_tasks (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL,
    task_id VARCHAR(36) NOT NULL,
    task_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    dependencies JSONB DEFAULT '[]'::JSONB,
    parameters JSONB NOT NULL,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (workflow_id, task_id)
);

COMMENT ON TABLE workflow_tasks IS '工作流任务表';
COMMENT ON COLUMN workflow_tasks.workflow_id IS '工作流ID';
COMMENT ON COLUMN workflow_tasks.task_id IS '任务ID';
COMMENT ON COLUMN workflow_tasks.task_name IS '任务名称';
COMMENT ON COLUMN workflow_tasks.task_type IS '任务类型';
COMMENT ON COLUMN workflow_tasks.status IS '任务状态';
COMMENT ON COLUMN workflow_tasks.dependencies IS '依赖任务（JSON数组）';
COMMENT ON COLUMN workflow_tasks.parameters IS '任务参数（JSON格式）';
COMMENT ON COLUMN workflow_tasks.result IS '任务结果（JSON格式）';
COMMENT ON COLUMN workflow_tasks.error_message IS '错误信息';

CREATE INDEX IF NOT EXISTS idx_workflow_tasks_workflow_id ON workflow_tasks(workflow_id);
CREATE INDEX idx_workflow_tasks_status ON workflow_tasks(status);

-- 工作流执行日志表
CREATE TABLE workflow_logs (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL,
    execution_id VARCHAR(36) NOT NULL,
    workflow_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INT,
    execution_context JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE workflow_logs IS '工作流执行日志表';
COMMENT ON COLUMN workflow_logs.workflow_id IS '工作流ID';
COMMENT ON COLUMN workflow_logs.execution_id IS '执行ID';
COMMENT ON COLUMN workflow_logs.workflow_name IS '工作流名称';
COMMENT ON COLUMN workflow_logs.status IS '执行状态';
COMMENT ON COLUMN workflow_logs.started_at IS '开始时间';
COMMENT ON COLUMN workflow_logs.completed_at IS '完成时间';
COMMENT ON COLUMN workflow_logs.duration_ms IS '耗时（毫秒）';
COMMENT ON COLUMN workflow_logs.execution_context IS '执行上下文（JSON格式）';
COMMENT ON COLUMN workflow_logs.error_message IS '错误信息';

CREATE INDEX IF NOT EXISTS idx_workflow_logs_workflow_id ON workflow_logs(workflow_id);
CREATE INDEX idx_workflow_logs_execution_id ON workflow_logs(execution_id);
CREATE INDEX idx_workflow_logs_date ON workflow_logs(started_at DESC);

-- 文件附件表
CREATE TABLE file_attachments (
    id VARCHAR(36) PRIMARY KEY,
    file_id VARCHAR(36) NOT NULL UNIQUE,
    file_name VARCHAR(200) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type VARCHAR(100),
    reference_type VARCHAR(50) NOT NULL,
    reference_id VARCHAR(100) NOT NULL,
    uploaded_by VARCHAR(36) REFERENCES sys_users(id),
    upload_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    metainfo JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE file_attachments IS '文件附件表';
COMMENT ON COLUMN file_attachments.file_id IS '文件ID（UUID）';
COMMENT ON COLUMN file_attachments.file_name IS '文件名';
COMMENT ON COLUMN file_attachments.file_type IS '文件类型：report/data/strategy/log';
COMMENT ON COLUMN file_attachments.file_size IS '文件大小（字节）';
COMMENT ON COLUMN file_attachments.storage_path IS '存储路径';
COMMENT ON COLUMN file_attachments.mime_type IS 'MIME类型';
COMMENT ON COLUMN file_attachments.reference_type IS '关联类型';
COMMENT ON COLUMN file_attachments.reference_id IS '关联ID';
COMMENT ON COLUMN file_attachments.uploaded_by IS '上传人';
COMMENT ON COLUMN file_attachments.upload_date IS '上传日期';
COMMENT ON COLUMN file_attachments.description IS '描述';
COMMENT ON COLUMN file_attachments.metainfo IS '元数据（JSON格式）';

CREATE INDEX IF NOT EXISTS idx_file_attachments_reference ON file_attachments(reference_type, reference_id);
CREATE INDEX idx_file_attachments_upload_date ON file_attachments(upload_date DESC);

-- ------------------------------------------------------------
-- 1.16 因子研究任务表（补充完整）
-- ------------------------------------------------------------

CREATE TABLE factor_research (
    -- 基础信息
    id VARCHAR(36) PRIMARY KEY,
    research_id VARCHAR(64) NOT NULL UNIQUE,
    research_name VARCHAR(200) NOT NULL,

    -- 因子信息
    factor_name VARCHAR(100) NOT NULL,
    factor_definition JSONB,
    factor_category VARCHAR(50),

    -- 研究参数
    universe JSONB,
    start_date DATE,
    end_date DATE,
    parameters JSONB,
    analysis_type VARCHAR(50) DEFAULT 'ic_analysis',

    -- 研究状态和进度
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress FLOAT DEFAULT 0.0,
    calculated_count INTEGER DEFAULT 0,
    total_stocks INTEGER DEFAULT 0,

    -- 研究结果
    result JSONB,
    summary JSONB,
    report JSONB,

    -- 错误信息
    error_message TEXT,
    error_stack TEXT,

    -- 性能指标（从结果中提取的常用指标，便于查询）
    ic_mean DECIMAL(10, 4),
    ic_ir DECIMAL(10, 4),
    top_minus_bottom DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),

    -- 用户和上下文
    user_id INTEGER,
    created_by INTEGER,
    updated_by INTEGER,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_completion_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE factor_research IS '因子研究任务表';
COMMENT ON COLUMN factor_research.id IS '主键ID';
COMMENT ON COLUMN factor_research.research_id IS '研究任务ID';
COMMENT ON COLUMN factor_research.research_name IS '研究任务名称';
COMMENT ON COLUMN factor_research.factor_name IS '因子名称';
COMMENT ON COLUMN factor_research.factor_definition IS '因子定义（JSON格式）';
COMMENT ON COLUMN factor_research.factor_category IS '因子类别：value, quality, momentum, volatility, size, etc.';
COMMENT ON COLUMN factor_research.universe IS '股票池（JSON数组格式）';
COMMENT ON COLUMN factor_research.start_date IS '开始日期';
COMMENT ON COLUMN factor_research.end_date IS '结束日期';
COMMENT ON COLUMN factor_research.parameters IS '研究参数（JSON格式）';
COMMENT ON COLUMN factor_research.analysis_type IS '分析类型：ic_analysis, quantile_analysis, correlation_analysis';
COMMENT ON COLUMN factor_research.status IS '状态：pending, running, completed, failed, cancelled';
COMMENT ON COLUMN factor_research.progress IS '进度（0-1）';
COMMENT ON COLUMN factor_research.calculated_count IS '已计算股票数量';
COMMENT ON COLUMN factor_research.total_stocks IS '总股票数量';
COMMENT ON COLUMN factor_research.result IS '研究结果（JSON格式）';
COMMENT ON COLUMN factor_research.summary IS '研究总结（JSON格式）';
COMMENT ON COLUMN factor_research.report IS '详细报告（JSON格式）';
COMMENT ON COLUMN factor_research.error_message IS '错误信息';
COMMENT ON COLUMN factor_research.error_stack IS '错误堆栈';
COMMENT ON COLUMN factor_research.ic_mean IS 'IC均值';
COMMENT ON COLUMN factor_research.ic_ir IS 'IC信息比率';
COMMENT ON COLUMN factor_research.top_minus_bottom IS '多空收益差';
COMMENT ON COLUMN factor_research.sharpe_ratio IS '夏普比率';
COMMENT ON COLUMN factor_research.user_id IS '用户ID';
COMMENT ON COLUMN factor_research.created_by IS '创建人ID';
COMMENT ON COLUMN factor_research.updated_by IS '更新人ID';
COMMENT ON COLUMN factor_research.created_at IS '创建时间';
COMMENT ON COLUMN factor_research.updated_at IS '更新时间';
COMMENT ON COLUMN factor_research.started_at IS '开始时间';
COMMENT ON COLUMN factor_research.completed_at IS '完成时间';
COMMENT ON COLUMN factor_research.estimated_completion_at IS '预计完成时间';

-- 创建黑名单表
CREATE TABLE blacklists (
    -- 主键
    id VARCHAR(36) PRIMARY KEY,

    -- 目标信息
    target_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(100) NOT NULL,
    target_name VARCHAR(200),

    -- 名单信息
    list_type VARCHAR(50) NOT NULL DEFAULT 'global',
    reason TEXT NOT NULL,

    -- 管理信息
    added_by VARCHAR(36) NOT NULL,
    expire_date TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    metainfo JSONB,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 外键约束
    CONSTRAINT fk_blacklists_added_by
        FOREIGN KEY (added_by)
        REFERENCES sys_users(id)
        ON DELETE RESTRICT,

    -- 唯一约束
    CONSTRAINT uq_blacklist_target
        UNIQUE (target_type, target_id, list_type)
);

-- 添加表注释
COMMENT ON TABLE blacklists IS '黑名单表';

-- 添加列注释
COMMENT ON COLUMN blacklists.id IS '黑名单ID';
COMMENT ON COLUMN blacklists.target_type IS '目标类型：stock/user/account';
COMMENT ON COLUMN blacklists.target_id IS '目标标识（股票代码/用户ID/账户ID）';
COMMENT ON COLUMN blacklists.target_name IS '目标名称';
COMMENT ON COLUMN blacklists.list_type IS '名单类型：global/user_specific/system';
COMMENT ON COLUMN blacklists.reason IS '加入原因';
COMMENT ON COLUMN blacklists.added_by IS '添加人ID';
COMMENT ON COLUMN blacklists.expire_date IS '过期时间';
COMMENT ON COLUMN blacklists.is_active IS '是否有效';
COMMENT ON COLUMN blacklists.metainfo IS '元数据（JSON格式）';
COMMENT ON COLUMN blacklists.created_at IS '创建时间';
COMMENT ON COLUMN blacklists.updated_at IS '更新时间';

-- 创建索引
CREATE INDEX idx_blacklists_target_type_id ON blacklists(target_type, target_id);
CREATE INDEX idx_blacklists_list_type ON blacklists(list_type);
CREATE INDEX idx_blacklists_is_active ON blacklists(is_active);
CREATE INDEX idx_blacklists_expire_date ON blacklists(expire_date);
CREATE INDEX idx_blacklists_created_at ON blacklists(created_at);
CREATE INDEX idx_blacklists_updated_at ON blacklists(updated_at);
CREATE INDEX idx_blacklists_added_by ON blacklists(added_by);

-- 创建部分索引（针对特定查询优化）
CREATE INDEX idx_blacklists_active_expired ON blacklists(is_active, expire_date)
    WHERE is_active = TRUE AND expire_date IS NOT NULL;

CREATE INDEX idx_blacklists_stock_active ON blacklists(target_type, target_id, is_active)
    WHERE target_type = 'stock' AND is_active = TRUE;

CREATE INDEX idx_blacklists_user_active ON blacklists(target_type, target_id, is_active)
    WHERE target_type = 'user' AND is_active = TRUE;

-- ============================================================
-- 第二部分：TimescaleDB时序表
-- 注意：这些表将转换为超表，支持时序数据处理
-- ============================================================

-- ------------------------------------------------------------
-- 2.1 行情数据时序表
-- ------------------------------------------------------------

-- A股日线行情表（TimescaleDB超表）
CREATE TABLE stock_daily (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    UNIQUE (ts_code, trade_date),
    open NUMERIC(9,3) NOT NULL,
    high NUMERIC(9,3) NOT NULL,
    low NUMERIC(9,3) NOT NULL,
    close NUMERIC(9,3),
    pre_close NUMERIC(9,3) NOT NULL,
    change NUMERIC(9,3) NOT NULL,
    pct_chg NUMERIC(10,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(14,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_daily IS 'A股日线行情表（TimescaleDB超表）';
COMMENT ON COLUMN stock_daily.ts_code IS '股票TS代码（包含交易所后缀）';
COMMENT ON COLUMN stock_daily.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_daily.open IS '当日开盘价（精确到厘）';
COMMENT ON COLUMN stock_daily.high IS '当日最高价（精确到厘）';
COMMENT ON COLUMN stock_daily.low IS '当日最低价（精确到厘）';
COMMENT ON COLUMN stock_daily.close IS '当日收盘价（未复权）';
COMMENT ON COLUMN stock_daily.pre_close IS '除权后的昨日收盘价（用于计算涨跌幅）';
COMMENT ON COLUMN stock_daily.change IS '涨跌额（收盘价-除权昨收价）';
COMMENT ON COLUMN stock_daily.pct_chg IS '涨跌幅百分比（计算公式：(close-pre_close)/pre_close）';
COMMENT ON COLUMN stock_daily.vol IS '成交量（单位：手，1手=100股）';
COMMENT ON COLUMN stock_daily.amount IS '成交额（单位：千元人民币）';
COMMENT ON COLUMN stock_daily.created_at IS '数据首次入库时间';
COMMENT ON COLUMN stock_daily.updated_at IS '数据最后更新时间';

-- 股票分钟行情表（TimescaleDB超表）
CREATE TABLE stock_minutes (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    freq VARCHAR(5) NOT NULL CHECK (freq IN ('1min','5min','15min','30min','60min')),
    trade_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(9,4) NOT NULL,
    high NUMERIC(9,4) NOT NULL,
    low NUMERIC(9,4) NOT NULL,
    close NUMERIC(9,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(16,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_minutes IS 'A股分钟级行情数据（TimescaleDB超表）';
COMMENT ON COLUMN stock_minutes.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_minutes.freq IS 'K线频度（1min/5min/15min/30min/60min）';
COMMENT ON COLUMN stock_minutes.trade_time IS '精确交易时间（含日期和时分秒）';
COMMENT ON COLUMN stock_minutes.open IS '分钟周期开盘价';
COMMENT ON COLUMN stock_minutes.high IS '分钟周期最高价';
COMMENT ON COLUMN stock_minutes.low IS '分钟周期最低价';
COMMENT ON COLUMN stock_minutes.close IS '分钟周期收盘价';
COMMENT ON COLUMN stock_minutes.vol IS '成交量（单位：手，1手=100股）';
COMMENT ON COLUMN stock_minutes.amount IS '成交金额（单位：元人民币）';
COMMENT ON COLUMN stock_minutes.created_at IS '数据入库时间（自动记录）';

-- 周线行情表（TimescaleDB超表）
CREATE TABLE stock_weekly (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(9,4) NOT NULL,
    high NUMERIC(9,4) NOT NULL,
    low NUMERIC(9,4) NOT NULL,
    close NUMERIC(9,4) NOT NULL,
    pre_close NUMERIC(9,4) NOT NULL,
    change NUMERIC(9,4) NOT NULL,
    pct_chg NUMERIC(8,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(16,4) NOT NULL,
    week_start DATE,
    week_end DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_weekly_code_date ON stock_weekly(ts_code, trade_date);


COMMENT ON TABLE stock_weekly IS 'A股周线行情数据表（TimescaleDB超表）';
COMMENT ON COLUMN stock_weekly.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_weekly.trade_date IS '周线交易日（每周最后一个交易日）';
COMMENT ON COLUMN stock_weekly.open IS '周一开盘价';
COMMENT ON COLUMN stock_weekly.high IS '周内最高价';
COMMENT ON COLUMN stock_weekly.low IS '周内最低价';
COMMENT ON COLUMN stock_weekly.close IS '周五收盘价（未复权）';
COMMENT ON COLUMN stock_weekly.pre_close IS '上周收盘价（用于计算涨跌幅）';
COMMENT ON COLUMN stock_weekly.change IS '周涨跌额（计算公式：close - pre_close）';
COMMENT ON COLUMN stock_weekly.pct_chg IS '周涨跌幅百分比（计算公式：(close-pre_close)/pre_close）';
COMMENT ON COLUMN stock_weekly.vol IS '周成交量（单位：手，1手=100股）';
COMMENT ON COLUMN stock_weekly.amount IS '周成交额（单位：元人民币）';
COMMENT ON COLUMN stock_weekly.week_start IS '周开始日期（自动计算）';
COMMENT ON COLUMN stock_weekly.week_end IS '周结束日期（自动计算）';

-- 月线行情表（TimescaleDB超表）
CREATE TABLE stock_monthly (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(9,4) NOT NULL,
    high NUMERIC(9,4) NOT NULL,
    low NUMERIC(9,4) NOT NULL,
    close NUMERIC(9,4) NOT NULL,
    pre_close NUMERIC(9,4) NOT NULL,
    change NUMERIC(9,4) NOT NULL,
    pct_chg NUMERIC(8,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(16,4) NOT NULL,
    month_start DATE,
    month_end DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_monthly_code_date ON stock_monthly(ts_code, trade_date);


COMMENT ON TABLE stock_monthly IS 'A股月线行情数据表（TimescaleDB超表）';
COMMENT ON COLUMN stock_monthly.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_monthly.trade_date IS '月线交易日（每月最后一个交易日）';
COMMENT ON COLUMN stock_monthly.open IS '月初开盘价';
COMMENT ON COLUMN stock_monthly.high IS '月内最高价';
COMMENT ON COLUMN stock_monthly.low IS '月内最低价';
COMMENT ON COLUMN stock_monthly.close IS '月末收盘价（未复权）';
COMMENT ON COLUMN stock_monthly.pre_close IS '上月收盘价（用于计算涨跌幅）';
COMMENT ON COLUMN stock_monthly.change IS '月涨跌额（计算公式：close - pre_close）';
COMMENT ON COLUMN stock_monthly.pct_chg IS '月涨跌幅百分比（计算公式：(close-pre_close)/pre_close）';
COMMENT ON COLUMN stock_monthly.vol IS '月成交量（单位：手，1手=100股）';
COMMENT ON COLUMN stock_monthly.amount IS '月成交额（单位：元人民币）';
COMMENT ON COLUMN stock_monthly.month_start IS '月开始日期（自动计算）';
COMMENT ON COLUMN stock_monthly.month_end IS '月结束日期（自动计算）';

-- 复权因子表（TimescaleDB超表）
CREATE TABLE stock_adj_factor (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    adj_factor NUMERIC(18,10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_adj_factor_code_date ON stock_adj_factor(ts_code, trade_date);


COMMENT ON TABLE stock_adj_factor IS '股票复权因子数据表（TimescaleDB超表）';
COMMENT ON COLUMN stock_adj_factor.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_adj_factor.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_adj_factor.adj_factor IS '复权因子（高精度数值，用于计算复权价格）';

-- A股复权行情表（TimescaleDB超表）
CREATE TABLE stock_adjusted_prices (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    asset_type CHAR(1) NOT NULL DEFAULT 'E' CHECK (asset_type IN ('E','I','C','FT','FD','O')),
    adj_type VARCHAR(3) CHECK (adj_type IN (NULL, 'qfq', 'hfq')),
    freq VARCHAR(4) NOT NULL DEFAULT 'D' CHECK (freq IN ('D','1MIN','5MIN','15MIN','30MIN','60MIN')),
    open NUMERIC(9,4) NOT NULL,
    high NUMERIC(9,4) NOT NULL,
    low NUMERIC(9,4) NOT NULL,
    close NUMERIC(9,4) NOT NULL,
    pre_close NUMERIC(9,4) NOT NULL,
    change NUMERIC(9,4) NOT NULL,
    pct_chg NUMERIC(8,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(16,4) NOT NULL,
    ma_values JSONB,
    adj_factor NUMERIC(18,10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_adjusted_prices IS 'A股复权行情数据表（TimescaleDB超表）';
COMMENT ON COLUMN stock_adjusted_prices.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_adjusted_prices.trade_date IS '交易日期';
COMMENT ON COLUMN stock_adjusted_prices.asset_type IS '资产类型：E-股票，I-指数，C-可转债，FT-期货，FD-基金，O-其他';
COMMENT ON COLUMN stock_adjusted_prices.adj_type IS '复权类型：qfq-前复权，hfq-后复权';
COMMENT ON COLUMN stock_adjusted_prices.freq IS '数据频率';
COMMENT ON COLUMN stock_adjusted_prices.ma_values IS '移动平均线值（JSON格式）';
COMMENT ON COLUMN stock_adjusted_prices.adj_factor IS '复权因子';

-- 每日指标表（TimescaleDB超表）
CREATE TABLE stock_daily_basic (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    UNIQUE (ts_code, trade_date),
    close NUMERIC(9,4) NOT NULL,
    turnover_rate NUMERIC(8,4),
    turnover_rate_f NUMERIC(8,4),
    volume_ratio NUMERIC(8,4),
    pe NUMERIC(12,4),
    pe_ttm NUMERIC(12,4),
    pb NUMERIC(12,4),
    ps NUMERIC(12,4),
    ps_ttm NUMERIC(12,4),
    dv_ratio NUMERIC(8,4),
    dv_ttm NUMERIC(8,4),
    total_share NUMERIC(16,4),
    float_share NUMERIC(16,4),
    free_share NUMERIC(16,4),
    total_mv NUMERIC(18,4),
    circ_mv NUMERIC(18,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_daily_basic_code_date ON stock_daily_basic(ts_code, trade_date);


COMMENT ON TABLE stock_daily_basic IS '股票每日基本面指标数据表（TimescaleDB超表）';
COMMENT ON COLUMN stock_daily_basic.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_daily_basic.trade_date IS '交易日期';
COMMENT ON COLUMN stock_daily_basic.close IS '收盘价';
COMMENT ON COLUMN stock_daily_basic.turnover_rate IS '换手率（%）';
COMMENT ON COLUMN stock_daily_basic.turnover_rate_f IS '换手率（自由流通股）';
COMMENT ON COLUMN stock_daily_basic.volume_ratio IS '量比';
COMMENT ON COLUMN stock_daily_basic.pe IS '市盈率（总市值/净利润）';
COMMENT ON COLUMN stock_daily_basic.pe_ttm IS '市盈率（TTM）';
COMMENT ON COLUMN stock_daily_basic.pb IS '市净率（总市值/净资产）';
COMMENT ON COLUMN stock_daily_basic.ps IS '市销率';
COMMENT ON COLUMN stock_daily_basic.ps_ttm IS '市销率（TTM）';
COMMENT ON COLUMN stock_daily_basic.dv_ratio IS '股息率（%）';
COMMENT ON COLUMN stock_daily_basic.dv_ttm IS '股息率（TTM）';
COMMENT ON COLUMN stock_daily_basic.total_share IS '总股本（万股）';
COMMENT ON COLUMN stock_daily_basic.float_share IS '流通股本（万股）';
COMMENT ON COLUMN stock_daily_basic.free_share IS '自由流通股本（万股）';
COMMENT ON COLUMN stock_daily_basic.total_mv IS '总市值（万元）';
COMMENT ON COLUMN stock_daily_basic.circ_mv IS '流通市值（万元）';

-- 每日涨跌停价格表（TimescaleDB超表）
CREATE TABLE stock_daily_limit (
    id VARCHAR(36),
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    pre_close NUMERIC(9,4),
    up_limit NUMERIC(9,4) NOT NULL,
    down_limit NUMERIC(9,4) NOT NULL,
    up_percent NUMERIC(5,2),
    down_percent NUMERIC(5,2),
    price_range NUMERIC(9,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_daily_limit_code_date ON stock_daily_limit(ts_code, trade_date);

COMMENT ON TABLE stock_daily_limit IS '股票每日涨跌停价格表（TimescaleDB超表）';
COMMENT ON COLUMN stock_daily_limit.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_daily_limit.trade_date IS '交易日期';
COMMENT ON COLUMN stock_daily_limit.pre_close IS '前收盘价';
COMMENT ON COLUMN stock_daily_limit.up_limit IS '涨停价';
COMMENT ON COLUMN stock_daily_limit.down_limit IS '跌停价';
COMMENT ON COLUMN stock_daily_limit.up_percent IS '涨停幅度（%）';
COMMENT ON COLUMN stock_daily_limit.down_percent IS '跌停幅度（%）';
COMMENT ON COLUMN stock_daily_limit.price_range IS '价格区间（涨停价-跌停价）';

-- 个股资金流向表（TimescaleDB超表）
CREATE TABLE stock_moneyflow (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    buy_sm_vol INT NOT NULL,
    buy_sm_amount NUMERIC(12,4) NOT NULL,
    sell_sm_vol INT NOT NULL,
    sell_sm_amount NUMERIC(12,4) NOT NULL,
    buy_md_vol INT NOT NULL,
    buy_md_amount NUMERIC(12,4) NOT NULL,
    sell_md_vol INT NOT NULL,
    sell_md_amount NUMERIC(12,4) NOT NULL,
    buy_lg_vol INT NOT NULL,
    buy_lg_amount NUMERIC(12,4) NOT NULL,
    sell_lg_vol INT NOT NULL,
    sell_lg_amount NUMERIC(12,4) NOT NULL,
    buy_elg_vol INT NOT NULL,
    buy_elg_amount NUMERIC(12,4) NOT NULL,
    sell_elg_vol INT NOT NULL,
    sell_elg_amount NUMERIC(12,4) NOT NULL,
    net_mf_vol INT NOT NULL,
    net_mf_amount NUMERIC(12,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);

COMMENT ON TABLE stock_moneyflow IS '个股资金流向数据表（TimescaleDB超表）';
COMMENT ON COLUMN stock_moneyflow.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_moneyflow.trade_date IS '交易日期';
COMMENT ON COLUMN stock_moneyflow.buy_sm_vol IS '小单买入量（手）';
COMMENT ON COLUMN stock_moneyflow.buy_sm_amount IS '小单买入金额（万元）';
COMMENT ON COLUMN stock_moneyflow.sell_sm_vol IS '小单卖出量（手）';
COMMENT ON COLUMN stock_moneyflow.sell_sm_amount IS '小单卖出金额（万元）';
COMMENT ON COLUMN stock_moneyflow.buy_md_vol IS '中单买入量（手）';
COMMENT ON COLUMN stock_moneyflow.buy_md_amount IS '中单买入金额（万元）';
COMMENT ON COLUMN stock_moneyflow.sell_md_vol IS '中单卖出量（手）';
COMMENT ON COLUMN stock_moneyflow.sell_md_amount IS '中单卖出金额（万元）';
COMMENT ON COLUMN stock_moneyflow.buy_lg_vol IS '大单买入量（手）';
COMMENT ON COLUMN stock_moneyflow.buy_lg_amount IS '大单买入金额（万元）';
COMMENT ON COLUMN stock_moneyflow.sell_lg_vol IS '大单卖出量（手）';
COMMENT ON COLUMN stock_moneyflow.sell_lg_amount IS '大单卖出金额（万元）';
COMMENT ON COLUMN stock_moneyflow.buy_elg_vol IS '特大单买入量（手）';
COMMENT ON COLUMN stock_moneyflow.buy_elg_amount IS '特大单买入金额（万元）';
COMMENT ON COLUMN stock_moneyflow.sell_elg_vol IS '特大单卖出量（手）';
COMMENT ON COLUMN stock_moneyflow.sell_elg_amount IS '特大单卖出金额（万元）';
COMMENT ON COLUMN stock_moneyflow.net_mf_vol IS '净流入量（手）';
COMMENT ON COLUMN stock_moneyflow.net_mf_amount IS '净流入金额（万元）';

-- ------------------------------------------------------------
-- 2.2 ETF行情时序表
-- ------------------------------------------------------------

    -- ETF日线行情表（TimescaleDB超表）
    CREATE TABLE etf_daily (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(10,4) NOT NULL,
    high NUMERIC(10,4) NOT NULL,
    low NUMERIC(10,4) NOT NULL,
    close NUMERIC(10,4) NOT NULL,
    pre_close NUMERIC(10,4) NOT NULL,
    change NUMERIC(10,4) NOT NULL,
    pct_chg NUMERIC(8,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(16,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

COMMENT ON TABLE etf_daily IS 'ETF日线行情数据（TimescaleDB超表）';
COMMENT ON COLUMN etf_daily.ts_code IS 'ETF代码';
COMMENT ON COLUMN etf_daily.trade_date IS '交易日期';
COMMENT ON COLUMN etf_daily.open IS '开盘价';
COMMENT ON COLUMN etf_daily.high IS '最高价';
COMMENT ON COLUMN etf_daily.low IS '最低价';
COMMENT ON COLUMN etf_daily.close IS '收盘价';
COMMENT ON COLUMN etf_daily.pre_close IS '前收盘价';
COMMENT ON COLUMN etf_daily.change IS '涨跌额';
COMMENT ON COLUMN etf_daily.pct_chg IS '涨跌幅（%）';
COMMENT ON COLUMN etf_daily.vol IS '成交量（手）';
COMMENT ON COLUMN etf_daily.amount IS '成交额（万元）';

-- ETF历史分钟行情数据（TimescaleDB超表）
CREATE TABLE etf_minute (
    id VARCHAR(36),
    ts_code VARCHAR(20) NOT NULL REFERENCES etf_basic(ts_code),
    freq VARCHAR(10) NOT NULL,
    trade_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(10,4) NOT NULL,
    close NUMERIC(10,4) NOT NULL,
    high NUMERIC(10,4) NOT NULL,
    low NUMERIC(10,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(16,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, freq, trade_time)
);

COMMENT ON TABLE etf_minute IS 'ETF历史分钟行情数据（TimescaleDB超表）';
COMMENT ON COLUMN etf_minute.ts_code IS 'ETF代码';
COMMENT ON COLUMN etf_minute.freq IS '频率：1min/5min/15min/30min/60min';
COMMENT ON COLUMN etf_minute.trade_time IS '交易时间';
COMMENT ON COLUMN etf_minute.open IS '开盘价';
COMMENT ON COLUMN etf_minute.close IS '收盘价';
COMMENT ON COLUMN etf_minute.high IS '最高价';
COMMENT ON COLUMN etf_minute.low IS '最低价';
COMMENT ON COLUMN etf_minute.vol IS '成交量（手）';
COMMENT ON COLUMN etf_minute.amount IS '成交额（万元）';

-- ETF复权因子（TimescaleDB超表）
CREATE TABLE fund_adj_factor (
    ts_code VARCHAR(20) NOT NULL REFERENCES etf_basic(ts_code),
    trade_date DATE NOT NULL,
    adj_factor NUMERIC(16,8) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

COMMENT ON TABLE fund_adj_factor IS '基金复权因子数据（TimescaleDB超表）';
COMMENT ON COLUMN fund_adj_factor.ts_code IS 'ETF代码';
COMMENT ON COLUMN fund_adj_factor.trade_date IS '交易日期';
COMMENT ON COLUMN fund_adj_factor.adj_factor IS '复权因子';

-- ------------------------------------------------------------
-- 2.3 指数行情时序表
-- ------------------------------------------------------------

-- 指数日线行情数据（TimescaleDB超表）
CREATE TABLE index_daily (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    close NUMERIC(12,4) NOT NULL,
    open NUMERIC(12,4),
    high NUMERIC(12,4),
    low NUMERIC(12,4),
    pre_close NUMERIC(12,4),
    change NUMERIC(12,4),
    pct_chg NUMERIC(10,6),
    vol BIGINT,
    amount NUMERIC(18,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

COMMENT ON TABLE index_daily IS '指数日线行情数据（TimescaleDB超表）';
COMMENT ON COLUMN index_daily.ts_code IS '指数代码';
COMMENT ON COLUMN index_daily.trade_date IS '交易日期';
COMMENT ON COLUMN index_daily.close IS '收盘价';
COMMENT ON COLUMN index_daily.open IS '开盘价';
COMMENT ON COLUMN index_daily.high IS '最高价';
COMMENT ON COLUMN index_daily.low IS '最低价';
COMMENT ON COLUMN index_daily.pre_close IS '前收盘价';
COMMENT ON COLUMN index_daily.change IS '涨跌额';
COMMENT ON COLUMN index_daily.pct_chg IS '涨跌幅（%）';
COMMENT ON COLUMN index_daily.vol IS '成交量（手）';
COMMENT ON COLUMN index_daily.amount IS '成交额（万元）';

-- 指数成分股权重表
-- 存储各指数在特定日期的成分股及其权重，支持历史时点查询
-- 数据来源：Tushare index_weight 接口 / Baostock hs300/zz500 成分股接口
CREATE TABLE index_weight (
    id VARCHAR(36),
    index_code VARCHAR(20) NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    weight NUMERIC(12, 8),
    trade_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    -- 同一指数同一股票在同一天只有一条记录
    PRIMARY KEY (index_code, ts_code, trade_date)
);

COMMENT ON TABLE index_weight IS '指数成分股权重表';
COMMENT ON COLUMN index_weight.index_code IS '指数代码，关联 index_basic.ts_code';
COMMENT ON COLUMN index_weight.ts_code IS '股票代码，关联 stock_basic.ts_code';
COMMENT ON COLUMN index_weight.weight IS '成分股权重（小数形式，如 0.0352 表示 3.52%）';
COMMENT ON COLUMN index_weight.trade_date IS '权重生效日期';

CREATE INDEX idx_index_weight_code ON index_weight(index_code, trade_date);
CREATE INDEX idx_index_weight_stock ON index_weight(ts_code);

-- ------------------------------------------------------------
-- 2.4 绩效和信号时序表
-- ------------------------------------------------------------

-- 账户每日绩效表（TimescaleDB超表）
CREATE TABLE account_daily_performance (
    id VARCHAR(36),
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    trade_date DATE NOT NULL,
    total_asset NUMERIC(16,4) NOT NULL,
    cash NUMERIC(16,4) NOT NULL,
    market_value NUMERIC(16,4) NOT NULL,
    daily_pnl NUMERIC(16,4) NOT NULL,
    daily_return NUMERIC(10,6) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE account_daily_performance IS '账户每日绩效快照表（TimescaleDB超表）';
COMMENT ON COLUMN account_daily_performance.user_id IS '用户ID';
COMMENT ON COLUMN account_daily_performance.trade_date IS '交易日期';
COMMENT ON COLUMN account_daily_performance.total_asset IS '总资产';
COMMENT ON COLUMN account_daily_performance.cash IS '现金';
COMMENT ON COLUMN account_daily_performance.market_value IS '持仓市值';
COMMENT ON COLUMN account_daily_performance.daily_pnl IS '当日盈亏';
COMMENT ON COLUMN account_daily_performance.daily_return IS '当日收益率（%）';

-- 策略每日绩效表（TimescaleDB超表）
CREATE TABLE strategy_daily_performance (
    id VARCHAR(36),
    strategy_id VARCHAR(36) NOT NULL REFERENCES strategies(id),
    trade_date DATE NOT NULL,
    daily_return NUMERIC(10,6) NOT NULL,
    total_return NUMERIC(10,6) NOT NULL,
    max_drawdown NUMERIC(10,6) NOT NULL,
    sharpe_ratio NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE strategy_daily_performance IS '策略每日绩效指标表（TimescaleDB超表）';
COMMENT ON COLUMN strategy_daily_performance.strategy_id IS '策略ID';
COMMENT ON COLUMN strategy_daily_performance.trade_date IS '交易日期';
COMMENT ON COLUMN strategy_daily_performance.daily_return IS '当日收益率（%）';
COMMENT ON COLUMN strategy_daily_performance.total_return IS '累计收益率（%）';
COMMENT ON COLUMN strategy_daily_performance.max_drawdown IS '最大回撤（%）';
COMMENT ON COLUMN strategy_daily_performance.sharpe_ratio IS '夏普比率';

-- 信号记录表（TimescaleDB超表）
CREATE TABLE signals (
    id VARCHAR(36),
    strategy_id VARCHAR(36) NOT NULL REFERENCES strategies(id),
    ts_code VARCHAR(12) NOT NULL,
    signal_type VARCHAR(10) NOT NULL CHECK (signal_type IN ('buy', 'sell', 'hold')),
    signal_time TIMESTAMPTZ NOT NULL,
    price NUMERIC(10,4),
    strength NUMERIC(5,2),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE signals IS '策略交易信号记录表（TimescaleDB超表）';
COMMENT ON COLUMN signals.strategy_id IS '策略ID';
COMMENT ON COLUMN signals.ts_code IS '股票代码';
COMMENT ON COLUMN signals.signal_type IS '信号类型：buy-买入, sell-卖出, hold-持有';
COMMENT ON COLUMN signals.signal_time IS '信号时间';
COMMENT ON COLUMN signals.price IS '信号价格';
COMMENT ON COLUMN signals.strength IS '信号强度（0-100）';
COMMENT ON COLUMN signals.reason IS '信号产生原因';

-- 回测净值曲线表（TimescaleDB超表）
CREATE TABLE backtest_equity_curves (
    id VARCHAR(36),
    task_id VARCHAR(36) NOT NULL REFERENCES backtest_tasks(id),
    trade_date DATE NOT NULL,
    equity NUMERIC(16,4) NOT NULL,
    cash NUMERIC(16,4) NOT NULL,
    market_value NUMERIC(16,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE backtest_equity_curves IS '回测净值曲线表（TimescaleDB超表）';
COMMENT ON COLUMN backtest_equity_curves.task_id IS '回测任务ID';
COMMENT ON COLUMN backtest_equity_curves.trade_date IS '交易日期';
COMMENT ON COLUMN backtest_equity_curves.equity IS '总权益';
COMMENT ON COLUMN backtest_equity_curves.cash IS '现金';
COMMENT ON COLUMN backtest_equity_curves.market_value IS '持仓市值';

-- 风控事件日志表（TimescaleDB超表）
CREATE TABLE risk_events (
    id VARCHAR(36),
    rule_id VARCHAR(36) NOT NULL REFERENCES risk_rules(id),
    strategy_id VARCHAR(36) REFERENCES strategies(id),
    user_id VARCHAR(36) NOT NULL REFERENCES sys_users(id),
    event_type VARCHAR(50) NOT NULL,
    event_message TEXT NOT NULL,
    trigger_value JSONB NOT NULL,
    action_taken VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE risk_events IS '风控事件触发日志表（TimescaleDB超表）';
COMMENT ON COLUMN risk_events.rule_id IS '风控规则ID';
COMMENT ON COLUMN risk_events.strategy_id IS '策略ID';
COMMENT ON COLUMN risk_events.user_id IS '用户ID';
COMMENT ON COLUMN risk_events.event_type IS '事件类型';
COMMENT ON COLUMN risk_events.event_message IS '事件描述';
COMMENT ON COLUMN risk_events.trigger_value IS '触发值（JSON格式）';
COMMENT ON COLUMN risk_events.action_taken IS '采取的行动';

-- ------------------------------------------------------------
-- 2.5 因子数据时序表
-- ------------------------------------------------------------

-- 因子数据表（TimescaleDB超表）
CREATE TABLE factor_data (
    id VARCHAR(36),
    factor_code VARCHAR(50) NOT NULL,
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    factor_value NUMERIC(18,6),
    z_score NUMERIC(10,6),
    percentile NUMERIC(8,4),
    rank INT,
    universe_rank INT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE factor_data IS '因子数据表（TimescaleDB超表）';
COMMENT ON COLUMN factor_data.factor_code IS '因子代码';
COMMENT ON COLUMN factor_data.ts_code IS '股票代码';
COMMENT ON COLUMN factor_data.trade_date IS '交易日';
COMMENT ON COLUMN factor_data.factor_value IS '因子原始值';
COMMENT ON COLUMN factor_data.z_score IS '标准化Z分数';
COMMENT ON COLUMN factor_data.percentile IS '百分位排名';
COMMENT ON COLUMN factor_data.rank IS '排名';
COMMENT ON COLUMN factor_data.universe_rank IS '在全市场中的排名';

-- ------------------------------------------------------------
-- 2.6 系统时序表
-- ------------------------------------------------------------

-- 交易日历史表（TimescaleDB超表）
CREATE TABLE trade_calendar (
    exchange VARCHAR(10) NOT NULL,
    cal_date DATE NOT NULL,
    is_open BOOLEAN NOT NULL DEFAULT FALSE,
    pretrade_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (exchange, cal_date)
);

COMMENT ON TABLE trade_calendar IS '交易所交易日历表（TimescaleDB超表）';
COMMENT ON COLUMN trade_calendar.exchange IS '交易所代码：SSE-上交所, SZSE-深交所, BSE-北交所';
COMMENT ON COLUMN trade_calendar.cal_date IS '日历日期';
COMMENT ON COLUMN trade_calendar.is_open IS '是否交易日';
COMMENT ON COLUMN trade_calendar.pretrade_date IS '前一交易日';

-- ============================================================
-- 第三部分：TimescaleDB超表转换
-- ============================================================

-- 转换为超表，按trade_date分区，7天一个分区
SELECT create_hypertable(
    'stock_daily',
    'trade_date',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- 添加空间分区键（按ts_code）
SELECT add_dimension(
    'stock_daily',
    'ts_code',
    number_partitions => 50,
    if_not_exists => TRUE
);

-- 分钟数据分区更细（1天）
SELECT create_hypertable(
    'stock_minutes',
    'trade_time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- 按股票代码和频率分区
SELECT add_dimension(
    'stock_minutes',
    'ts_code',
    number_partitions => 100,
    if_not_exists => TRUE
);

SELECT add_dimension(
    'stock_minutes',
    'freq',
    number_partitions => 5,
    if_not_exists => TRUE
);

-- 周线数据转换为超表
SELECT create_hypertable(
    'stock_weekly',
    'trade_date',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- 月线数据转换为超表
SELECT create_hypertable(
    'stock_monthly',
    'trade_date',
    chunk_time_interval => INTERVAL '90 days',
    if_not_exists => TRUE
);

-- 复权因子转换为超表
SELECT create_hypertable(
    'stock_adj_factor',
    'trade_date',
    chunk_time_interval => INTERVAL '180 days',
    if_not_exists => TRUE
);

-- 复权行情转换为超表
SELECT create_hypertable(
    'stock_adjusted_prices',
    'trade_date',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- 每日指标转换为超表
SELECT create_hypertable(
    'stock_daily_basic',
    'trade_date',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- 涨跌停价格转换为超表
SELECT create_hypertable(
    'stock_daily_limit',
    'trade_date',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- 资金流向转换为超表
SELECT create_hypertable(
    'stock_moneyflow',
    'trade_date',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- ETF日线转换为超表
SELECT create_hypertable(
    'etf_daily',
    'trade_date',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- ETF分钟线转换为超表
SELECT create_hypertable(
    'etf_minute',
    'trade_time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ETF复权因子转换为超表
SELECT create_hypertable(
    'fund_adj_factor',
    'trade_date',
    chunk_time_interval => INTERVAL '180 days',
    if_not_exists => TRUE
);

-- 指数日线转换为超表
SELECT create_hypertable(
    'index_daily',
    'trade_date',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- 账户绩效转换为超表
SELECT create_hypertable(
    'account_daily_performance',
    'trade_date',
    chunk_time_interval => INTERVAL '180 days',
    if_not_exists => TRUE
);

-- 策略绩效转换为超表
SELECT create_hypertable(
    'strategy_daily_performance',
    'trade_date',
    chunk_time_interval => INTERVAL '180 days',
    if_not_exists => TRUE
);

-- 信号记录转换为超表
SELECT create_hypertable(
    'signals',
    'signal_time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- 回测净值曲线转换为超表
SELECT create_hypertable(
    'backtest_equity_curves',
    'trade_date',
    chunk_time_interval => INTERVAL '180 days',
    if_not_exists => TRUE
);

-- 风控事件转换为超表
SELECT create_hypertable(
    'risk_events',
    'created_at',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- 因子数据转换为超表
SELECT create_hypertable(
    'factor_data',
    'trade_date',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- 交易日历转换为超表
SELECT create_hypertable(
    'trade_calendar',
    'cal_date',
    chunk_time_interval => INTERVAL '365 days',
    if_not_exists => TRUE
);

-- ============================================================
-- 第四部分：索引优化
-- ============================================================

-- TimescaleDB超表索引
CREATE INDEX IF NOT EXISTS idx_stock_daily_ts_code ON stock_daily (ts_code);
CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily (trade_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_daily_code_date ON stock_daily(ts_code, trade_date);

CREATE INDEX IF NOT EXISTS idx_stock_minutes_ts_code ON stock_minutes (ts_code);
CREATE INDEX IF NOT EXISTS idx_stock_minutes_time ON stock_minutes (trade_time DESC);
CREATE INDEX IF NOT EXISTS idx_stock_minutes_freq ON stock_minutes (freq);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_minutes_code_freq_time ON stock_minutes(ts_code, freq, trade_time);

CREATE INDEX IF NOT EXISTS idx_stock_moneyflow_ts_code ON stock_moneyflow (ts_code);
CREATE INDEX IF NOT EXISTS idx_stock_moneyflow_date ON stock_moneyflow (trade_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_moneyflow_code_date ON stock_moneyflow(ts_code, trade_date);

CREATE INDEX IF NOT EXISTS idx_etf_daily_ts_code ON etf_daily (ts_code);
CREATE INDEX IF NOT EXISTS idx_etf_daily_date ON etf_daily (trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_etf_minute_ts_code ON etf_minute (ts_code);
CREATE INDEX IF NOT EXISTS idx_etf_minute_time ON etf_minute (trade_time DESC);
CREATE INDEX IF NOT EXISTS idx_etf_minute_freq ON etf_minute (freq);
CREATE INDEX IF NOT EXISTS idx_index_daily_ts_code ON index_daily (ts_code);
CREATE INDEX IF NOT EXISTS idx_index_daily_date ON index_daily (trade_date DESC);

-- 补充索引
CREATE INDEX IF NOT EXISTS idx_account_daily_perf_user_date ON account_daily_performance(user_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_daily_perf_strategy_date ON strategy_daily_performance(strategy_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_signals_strategy_time ON signals(strategy_id, signal_time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_ts_code ON signals(ts_code);
CREATE INDEX IF NOT EXISTS idx_backtest_equity_task_date ON backtest_equity_curves(task_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_created_at ON risk_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_user_id ON risk_events(user_id);
CREATE INDEX IF NOT EXISTS idx_factor_data_factor_code ON factor_data(factor_code);
CREATE INDEX IF NOT EXISTS idx_factor_data_ts_code ON factor_data(ts_code);
CREATE INDEX IF NOT EXISTS idx_factor_data_date ON factor_data(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trade_calendar_date ON trade_calendar(cal_date DESC);
CREATE INDEX IF NOT EXISTS idx_trade_calendar_exchange ON trade_calendar(exchange);

-- 外键索引（优化关联查询）
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_strategy_id ON orders(strategy_id);
CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders(account_id);
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id);
CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_account_id ON positions(account_id);
CREATE INDEX IF NOT EXISTS idx_strategy_runs_strategy_id ON strategy_runs(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_task_id ON backtest_trades(task_id);
CREATE INDEX IF NOT EXISTS idx_backtest_positions_task_id ON backtest_positions(task_id);
CREATE INDEX IF NOT EXISTS idx_backtest_parameters_task_id ON backtest_parameters(task_id);
CREATE INDEX IF NOT EXISTS idx_strategy_parameters_strategy_id ON strategy_parameters(strategy_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_strategies_strategy_id ON portfolio_strategies(strategy_id);
CREATE INDEX IF NOT EXISTS idx_factor_research_user_id ON factor_research(user_id);
CREATE INDEX IF NOT EXISTS idx_factor_research_status ON factor_research(status);
CREATE INDEX IF NOT EXISTS idx_data_quality_checks_date ON data_quality_checks(check_date DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status ON analysis_tasks(status);
CREATE INDEX IF NOT EXISTS idx_workflow_tasks_workflow_id ON workflow_tasks(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_logs_workflow_id ON workflow_logs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_file_attachments_reference ON file_attachments(reference_type, reference_id);

-- ============================================================
-- 第五部分：TimescaleDB压缩和保留策略
-- 注意：根据实际数据量调整参数
-- ============================================================

-- 启用压缩（适用于历史数据）
-- 1. 为stock_daily启用压缩（30天以上的数据）
ALTER TABLE stock_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ts_code',
    timescaledb.compress_orderby = 'trade_date DESC, id'
);

-- 创建压缩策略（30天后自动压缩）
SELECT add_compression_policy('stock_daily', INTERVAL '30 days');

-- 2. 为stock_minutes启用压缩（7天以上的分钟数据）
ALTER TABLE stock_minutes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ts_code, freq',
    timescaledb.compress_orderby = 'trade_time DESC, id'
);

SELECT add_compression_policy('stock_minutes', INTERVAL '7 days');

-- 3. 为其他超表启用压缩策略（根据需求）
-- SELECT add_compression_policy('etf_daily', INTERVAL '30 days');
-- SELECT add_compression_policy('index_daily', INTERVAL '30 days');

-- 4. 数据保留策略（自动删除旧数据）
-- 保留3年的分钟数据（可根据存储调整）
-- SELECT add_retention_policy('stock_minutes', INTERVAL '3 years');

-- 保留10年的日线数据
-- SELECT add_retention_policy('stock_daily', INTERVAL '10 years');

-- 保留2年的资金流向数据
-- SELECT add_retention_policy('stock_moneyflow', INTERVAL '2 years');

-- ============================================================
-- 第六部分：触发器函数（用于自动更新时间）
-- ============================================================

-- 自动更新时间的触发器函数
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要更新时间的表添加触发器
CREATE TRIGGER update_sys_users_modtime BEFORE UPDATE ON sys_users FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_stock_basic_modtime BEFORE UPDATE ON stock_basic FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_stock_company_modtime BEFORE UPDATE ON stock_company FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_strategies_modtime BEFORE UPDATE ON strategies FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_orders_modtime BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_accounts_modtime BEFORE UPDATE ON accounts FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_baskets_modtime BEFORE UPDATE ON baskets FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_system_configs_modtime BEFORE UPDATE ON system_configs FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_scheduled_tasks_modtime BEFORE UPDATE ON scheduled_tasks FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_sys_roles_modtime BEFORE UPDATE ON sys_roles FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_user_preferences_modtime BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_license_keys_modtime BEFORE UPDATE ON license_keys FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_strategy_parameters_modtime BEFORE UPDATE ON strategy_parameters FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_portfolio_strategies_modtime BEFORE UPDATE ON portfolio_strategies FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_trade_instructions_modtime BEFORE UPDATE ON trade_instructions FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_order_templates_modtime BEFORE UPDATE ON order_templates FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_backtest_tasks_modtime BEFORE UPDATE ON backtest_tasks FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_backtest_scenarios_modtime BEFORE UPDATE ON backtest_scenarios FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_factor_definitions_modtime BEFORE UPDATE ON factor_definitions FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_analysis_reports_modtime BEFORE UPDATE ON analysis_reports FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_analysis_templates_modtime BEFORE UPDATE ON analysis_templates FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_monitor_tasks_modtime BEFORE UPDATE ON monitor_tasks FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_alert_templates_modtime BEFORE UPDATE ON alert_templates FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_workflow_tasks_modtime BEFORE UPDATE ON workflow_tasks FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_factor_research_modtime BEFORE UPDATE ON factor_research FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- 因子研究表触发器
CREATE OR REPLACE FUNCTION update_factor_research_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_factor_research_updated_at
    BEFORE UPDATE ON factor_research
    FOR EACH ROW
    EXECUTE FUNCTION update_factor_research_updated_at();

-- 状态变更触发器（记录状态变更时间）
CREATE OR REPLACE FUNCTION update_factor_research_status_timestamps()
RETURNS TRIGGER AS $$
BEGIN
    -- 如果状态变为running，设置started_at
    IF NEW.status = 'running' AND (OLD.status != 'running' OR OLD.status IS NULL) THEN
        NEW.started_at = CURRENT_TIMESTAMP;
    END IF;

    -- 如果状态变为completed, failed, cancelled，设置completed_at
    IF NEW.status IN ('completed', 'failed', 'cancelled') AND
       OLD.status NOT IN ('completed', 'failed', 'cancelled') THEN
        NEW.completed_at = CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_factor_research_status_timestamps
    BEFORE UPDATE ON factor_research
    FOR EACH ROW
    EXECUTE FUNCTION update_factor_research_status_timestamps();

-- ============================================================
-- 第七部分：视图和物化视图（用于性能优化）
-- ============================================================

-- 创建接近涨停的股票视图
CREATE VIEW v_near_up_limit AS
SELECT d.ts_code, d.trade_date, d.close,
       l.up_limit, l.up_percent,
       (l.up_limit - d.close) AS space,
       (l.up_limit - d.close) / d.close * 100 AS space_pct
FROM stock_daily d
JOIN stock_daily_limit l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
WHERE d.close >= l.up_limit * 0.99  -- 接近涨停（99%以上）
  AND d.close < l.up_limit;         -- 未涨停

-- 创建连续涨停股票池物化视图（每日刷新）
CREATE MATERIALIZED VIEW mv_consecutive_limit_up AS
WITH limit_up AS (
    SELECT
        d.ts_code AS ts_code,
        d.trade_date AS trade_date,
        LAG(d.trade_date) OVER (PARTITION BY d.ts_code ORDER BY d.trade_date) AS prev_date
    FROM stock_daily d
    JOIN stock_daily_limit l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
    WHERE d.close = l.up_limit  -- 实际涨停
)
SELECT
    ts_code,
    MIN(trade_date) AS start_date,
    MAX(trade_date) AS end_date,
    COUNT(*) AS consecutive_days
FROM (
    SELECT
        ts_code,
        trade_date,
        prev_date,
        trade_date - ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date)::INT AS grp
    FROM limit_up
    WHERE trade_date = prev_date + INTERVAL '1 day' OR prev_date IS NULL
) t
GROUP BY ts_code, grp
HAVING COUNT(*) >= 3  -- 连续3天涨停
WITH DATA;

-- 创建股票基本信息视图
CREATE VIEW v_stock_info AS
SELECT
    b.ts_code,
    b.symbol,
    b.name,
    b.industry,
    b.market,
    b.exchange,
    b.list_date,
    c.com_name,
    c.chairman,
    c.province,
    c.city
FROM stock_basic b
LEFT JOIN stock_company c ON b.ts_code = c.ts_code;

-- 创建策略绩效概览视图
CREATE VIEW v_strategy_performance_overview AS
SELECT
    s.id as strategy_id,
    s.name as strategy_name,
    s.status as strategy_status,
    COUNT(DISTINCT sr.id) as total_runs,
    MAX(sr.started_at) as last_run_time,
    AVG(sdp.daily_return) as avg_daily_return,
    MAX(sdp.total_return) as total_return,
    MIN(sdp.max_drawdown) as max_drawdown
FROM strategies s
LEFT JOIN strategy_runs sr ON s.id = sr.strategy_id
LEFT JOIN strategy_daily_performance sdp ON s.id = sdp.strategy_id
GROUP BY s.id, s.name, s.status;

-- 创建账户资产概览视图
CREATE VIEW v_account_asset_overview AS
SELECT
    a.id as account_id,
    a.account_number,
    a.account_name,
    a.total_balance,
    a.available_balance,
    a.market_value,
    COUNT(DISTINCT p.ts_code) as positions_count,
    SUM(p.pnl) as total_pnl
FROM accounts a
LEFT JOIN positions p ON a.id = p.account_id
WHERE a.is_deleted = 0
GROUP BY a.id, a.account_number, a.account_name, a.total_balance, a.available_balance, a.market_value;

-- ============================================================
-- 第八部分：最终检查和更新
-- ============================================================

-- 更新数据库统计信息（提高查询计划器性能）
ANALYZE;

-- 验证表创建完整性
DO $$
DECLARE
    expected_tables INT := 70; -- 预期的表数量
    actual_tables INT;
BEGIN
    SELECT COUNT(*) INTO actual_tables
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE';

    RAISE NOTICE '===================================================';
    RAISE NOTICE '数据库表完整性检查';
    RAISE NOTICE '预期表数量: %', expected_tables;
    RAISE NOTICE '实际表数量: %', actual_tables;

    IF actual_tables >= expected_tables THEN
        RAISE NOTICE '✓ 表创建完整性检查通过';
    ELSE
        RAISE WARNING '⚠ 表数量不足，请检查缺失的表';
    END IF;

    -- 检查关键表是否存在
    PERFORM 1 FROM information_schema.tables WHERE table_name = 'accounts';
    IF FOUND THEN
        RAISE NOTICE '✓ accounts 表存在';
    ELSE
        RAISE WARNING '⚠ accounts 表缺失';
    END IF;

    PERFORM 1 FROM information_schema.tables WHERE table_name = 'system_configs';
    IF FOUND THEN
        RAISE NOTICE '✓ system_configs 表存在';
    ELSE
        RAISE WARNING '⚠ system_configs 表缺失';
    END IF;

    PERFORM 1 FROM information_schema.tables WHERE table_name = 'factor_definitions';
    IF FOUND THEN
        RAISE NOTICE '✓ factor_definitions 表存在';
    ELSE
        RAISE WARNING '⚠ factor_definitions 表缺失';
    END IF;

    PERFORM 1 FROM information_schema.tables WHERE table_name = 'analysis_reports';
    IF FOUND THEN
        RAISE NOTICE '✓ analysis_reports 表存在';
    ELSE
        RAISE WARNING '⚠ analysis_reports 表缺失';
    END IF;

    RAISE NOTICE '===================================================';
    RAISE NOTICE '量化交易系统数据库创建完成！';
    RAISE NOTICE '数据库名称: quant_trading';
    RAISE NOTICE 'PostgreSQL版本: 14+';
    RAISE NOTICE 'TimescaleDB版本: 2.10+';
    RAISE NOTICE '创建表数量: %张表（包含关系表和时序表）', actual_tables;
    RAISE NOTICE '超表数量: 20+ 张（已启用TimescaleDB分区）';
    RAISE NOTICE '===================================================';
    RAISE NOTICE '重要提醒:';
    RAISE NOTICE '1. 请根据实际硬件配置调整分区间隔和压缩策略';
    RAISE NOTICE '2. 定期运行ANALYZE命令更新统计信息';
    RAISE NOTICE '3. 监控TimescaleDB分区大小和压缩率';
    RAISE NOTICE '4. 根据需要调整数据保留策略';
    RAISE NOTICE '===================================================';
END
$$;

-- ============================================================
-- 脚本执行完成
-- ============================================================

-- ============================================================
-- 新增数据类型建表（业绩预告/快报/分红/财务指标/审计/主营/ETF份额）
-- ============================================================

-- 业绩预告数据表
CREATE TABLE stock_forecasts (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    type VARCHAR(10),
    p_change_min NUMERIC(12,4),
    p_change_max NUMERIC(12,4),
    net_profit_min NUMERIC(18,4),
    net_profit_max NUMERIC(18,4),
    last_parent_net NUMERIC(18,4),
    first_ann_date TIMESTAMPTZ,
    summary TEXT,
    change_reason TEXT,
    update_flag VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date)
);
COMMENT ON TABLE stock_forecasts IS '业绩预告数据';
COMMENT ON COLUMN stock_forecasts.ts_code IS 'TS代码';
COMMENT ON COLUMN stock_forecasts.ann_date IS '公告日期';
COMMENT ON COLUMN stock_forecasts.end_date IS '报告期';
COMMENT ON COLUMN stock_forecasts.type IS '预告类型';
COMMENT ON COLUMN stock_forecasts.p_change_min IS '净利润变动下限(%)';
COMMENT ON COLUMN stock_forecasts.p_change_max IS '净利润变动上限(%)';
COMMENT ON COLUMN stock_forecasts.net_profit_min IS '净利润下限';
COMMENT ON COLUMN stock_forecasts.net_profit_max IS '净利润上限';
COMMENT ON COLUMN stock_forecasts.last_parent_net IS '上年同期净利润';
COMMENT ON COLUMN stock_forecasts.summary IS '业绩变动摘要';
COMMENT ON COLUMN stock_forecasts.change_reason IS '业绩变动原因';
CREATE INDEX idx_stock_forecasts_ts_code ON stock_forecasts(ts_code);
CREATE INDEX idx_stock_forecasts_ann_date ON stock_forecasts(ann_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_forecasts_ts_ann ON stock_forecasts(ts_code, ann_date);


-- 业绩快报数据表
CREATE TABLE stock_expresses (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    revenue NUMERIC(18,4),
    operate_profit NUMERIC(18,4),
    total_profit NUMERIC(18,4),
    n_income NUMERIC(18,4),
    total_assets NUMERIC(18,4),
    total_hldr_eqy_exc_min_int NUMERIC(18,4),
    diluted_eps NUMERIC(12,4),
    yoy_eps NUMERIC(16,4),
    yoy_net_profit NUMERIC(16,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date)
);
COMMENT ON TABLE stock_expresses IS '业绩快报数据';
COMMENT ON COLUMN stock_expresses.ts_code IS 'TS代码';
COMMENT ON COLUMN stock_expresses.ann_date IS '公告日期';
COMMENT ON COLUMN stock_expresses.end_date IS '报告期';
COMMENT ON COLUMN stock_expresses.revenue IS '营业收入';
COMMENT ON COLUMN stock_expresses.operate_profit IS '营业利润';
COMMENT ON COLUMN stock_expresses.total_profit IS '利润总额';
COMMENT ON COLUMN stock_expresses.n_income IS '净利润';
COMMENT ON COLUMN stock_expresses.total_assets IS '总资产';
COMMENT ON COLUMN stock_expresses.total_hldr_eqy_exc_min_int IS '股东权益';
COMMENT ON COLUMN stock_expresses.diluted_eps IS '稀释每股收益';
COMMENT ON COLUMN stock_expresses.yoy_eps IS 'EPS同比(%)';
COMMENT ON COLUMN stock_expresses.yoy_net_profit IS '净利润同比(%)';
CREATE INDEX idx_stock_expresses_ts_code ON stock_expresses(ts_code);
CREATE INDEX idx_stock_expresses_ann_date ON stock_expresses(ann_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_expresses_ts_ann ON stock_expresses(ts_code, ann_date);


-- 分红送股数据表
CREATE TABLE stock_dividends (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    div_proc TEXT,
    stk_div NUMERIC(18,4),
    stk_bo_rate NUMERIC(12,4),
    stk_co_rate NUMERIC(12,4),
    cash_div NUMERIC(18,4),
    cash_div_tax NUMERIC(18,4),
    record_date TIMESTAMPTZ,
    ex_date TIMESTAMPTZ,
    pay_date TIMESTAMPTZ,
    div_listdate TIMESTAMPTZ,
    imp_ann_date TIMESTAMPTZ,
    base_share NUMERIC(18,4),
    base_vol NUMERIC(18,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, div_proc)
);
COMMENT ON TABLE stock_dividends IS '分红送股数据';
COMMENT ON COLUMN stock_dividends.ts_code IS 'TS代码';
COMMENT ON COLUMN stock_dividends.ann_date IS '公告日期';
COMMENT ON COLUMN stock_dividends.end_date IS '报告期';
COMMENT ON COLUMN stock_dividends.div_proc IS '分红预案';
COMMENT ON COLUMN stock_dividends.stk_div IS '每股送转';
COMMENT ON COLUMN stock_dividends.cash_div IS '每股分红';
COMMENT ON COLUMN stock_dividends.record_date IS '股权登记日';
COMMENT ON COLUMN stock_dividends.ex_date IS '除权除息日';
COMMENT ON COLUMN stock_dividends.pay_date IS '派息日';
COMMENT ON COLUMN stock_dividends.div_listdate IS '分红实施公告日';
COMMENT ON COLUMN stock_dividends.imp_ann_date IS '实施公告日';
COMMENT ON COLUMN stock_dividends.base_share IS '基准股本';
COMMENT ON COLUMN stock_dividends.base_vol IS '基准成交量';
CREATE INDEX idx_stock_dividends_ts_code ON stock_dividends(ts_code);
CREATE INDEX idx_stock_dividends_ann_date ON stock_dividends(ann_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dividends_unique ON stock_dividends(ts_code, ann_date, div_proc);


-- 财务指标数据表
CREATE TABLE stock_fina_indicators (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ NOT NULL,
    eps NUMERIC(18,4),
    roe NUMERIC(16,4),
    roa NUMERIC(16,4),
    roic NUMERIC(16,4),
    grossprofit_margin NUMERIC(16,4),
    netprofit_margin NUMERIC(16,4),
    debt_to_assets NUMERIC(16,4),
    current_ratio NUMERIC(16,4),
    quick_ratio NUMERIC(16,4),
    assets_turn NUMERIC(16,4),
    op_cycle NUMERIC(18,4),
    turnover_days NUMERIC(18,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, end_date)
);
COMMENT ON TABLE stock_fina_indicators IS '财务指标数据';
COMMENT ON COLUMN stock_fina_indicators.ts_code IS 'TS代码';
COMMENT ON COLUMN stock_fina_indicators.ann_date IS '公告日期';
COMMENT ON COLUMN stock_fina_indicators.end_date IS '报告期';
COMMENT ON COLUMN stock_fina_indicators.eps IS '每股收益';
COMMENT ON COLUMN stock_fina_indicators.roe IS '净资产收益率(%)';
COMMENT ON COLUMN stock_fina_indicators.roa IS '总资产收益率(%)';
COMMENT ON COLUMN stock_fina_indicators.grossprofit_margin IS '毛利率(%)';
COMMENT ON COLUMN stock_fina_indicators.netprofit_margin IS '净利率(%)';
COMMENT ON COLUMN stock_fina_indicators.debt_to_assets IS '资产负债率(%)';
CREATE INDEX idx_stock_fina_indicators_ts_code ON stock_fina_indicators(ts_code);
CREATE INDEX idx_stock_fina_indicators_ann_date ON stock_fina_indicators(ann_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fina_indicator_unique ON stock_fina_indicators(ts_code, end_date);


-- 审计意见数据表
CREATE TABLE stock_audit_opinions (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ NOT NULL,
    audit_result VARCHAR(200),
    audit_fees NUMERIC(18,4),
    audit_agency VARCHAR(200),
    audit_sign VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, end_date)
);
COMMENT ON TABLE stock_audit_opinions IS '审计意见数据';
COMMENT ON COLUMN stock_audit_opinions.ts_code IS 'TS代码';
COMMENT ON COLUMN stock_audit_opinions.ann_date IS '公告日期';
COMMENT ON COLUMN stock_audit_opinions.end_date IS '报告期';
COMMENT ON COLUMN stock_audit_opinions.audit_result IS '审计结果';
COMMENT ON COLUMN stock_audit_opinions.audit_fees IS '审计费用';
COMMENT ON COLUMN stock_audit_opinions.audit_agency IS '会计师事务所';
COMMENT ON COLUMN stock_audit_opinions.audit_sign IS '签字会计师';
CREATE INDEX idx_stock_audit_opinions_ts_code ON stock_audit_opinions(ts_code);
CREATE INDEX idx_stock_audit_opinions_ann_date ON stock_audit_opinions(ann_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_opinion_unique ON stock_audit_opinions(ts_code, end_date);


-- 主营业务构成数据表
CREATE TABLE stock_business_incomes (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    bz_item VARCHAR(200),
    bz_code VARCHAR(10),
    bz_sales NUMERIC(18,4),
    bz_profit NUMERIC(18,4),
    bz_cost NUMERIC(18,4),
    curr_type VARCHAR(10),
    type VARCHAR(5),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, end_date, bz_item, bz_code)
);
COMMENT ON TABLE stock_business_incomes IS '主营业务构成数据';
COMMENT ON COLUMN stock_business_incomes.ts_code IS 'TS代码';
COMMENT ON COLUMN stock_business_incomes.end_date IS '报告期';
COMMENT ON COLUMN stock_business_incomes.bz_item IS '主营业务项目';
COMMENT ON COLUMN stock_business_incomes.bz_code IS '来源类型(P产品/D地区/I行业)';
COMMENT ON COLUMN stock_business_incomes.bz_sales IS '主营收入';
COMMENT ON COLUMN stock_business_incomes.bz_profit IS '主营利润';
COMMENT ON COLUMN stock_business_incomes.bz_cost IS '主营成本';
COMMENT ON COLUMN stock_business_incomes.curr_type IS '货币代码';
COMMENT ON COLUMN stock_business_incomes.type IS '类型(P/D/I)';
CREATE INDEX idx_stock_business_incomes_ts_code ON stock_business_incomes(ts_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_biz_income_unique ON stock_business_incomes(ts_code, end_date, bz_item, bz_code);


-- ETF份额数据表
CREATE TABLE etf_shares (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date TIMESTAMPTZ NOT NULL,
    fund_size NUMERIC(18,4),
    fund_vol NUMERIC(18,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);
COMMENT ON TABLE etf_shares IS 'ETF份额数据';
COMMENT ON COLUMN etf_shares.ts_code IS 'ETF代码';
COMMENT ON COLUMN etf_shares.trade_date IS '交易日期';
COMMENT ON COLUMN etf_shares.fund_size IS '基金规模(份)';
COMMENT ON COLUMN etf_shares.fund_vol IS '基金份额变动';
CREATE INDEX idx_etf_shares_ts_code ON etf_shares(ts_code);
CREATE INDEX idx_etf_shares_trade_date ON etf_shares(trade_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_etf_share_unique ON etf_shares(ts_code, trade_date);



-- 股票停复牌信息表 (Tushare suspend_d 接口)
CREATE TABLE stock_suspend_info (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date TIMESTAMPTZ NOT NULL,
    suspend_timing VARCHAR(100),
    suspend_type VARCHAR(2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date, suspend_type)
);
COMMENT ON TABLE stock_suspend_info IS '股票停复牌信息（每日）';
COMMENT ON COLUMN stock_suspend_info.ts_code IS 'TS代码';
COMMENT ON COLUMN stock_suspend_info.trade_date IS '停复牌日期';
COMMENT ON COLUMN stock_suspend_info.suspend_timing IS '日内停牌时间段';
COMMENT ON COLUMN stock_suspend_info.suspend_type IS '停复牌类型：S-停牌，R-复牌';
CREATE INDEX idx_stock_suspend_info_ts_code ON stock_suspend_info(ts_code);
CREATE INDEX idx_stock_suspend_info_trade_date ON stock_suspend_info(trade_date);

-- 沪深港通股票列表
CREATE TABLE stock_hsgt (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    type VARCHAR(5) NOT NULL,
    name VARCHAR(100),
    type_name VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date, type)
);
CREATE INDEX idx_stock_hsgt_ts_code ON stock_hsgt(ts_code);
CREATE INDEX idx_stock_hsgt_type ON stock_hsgt(type);

COMMENT ON TABLE stock_hsgt IS '沪深港通股票列表（Tushare stock_hsgt 接口）';
COMMENT ON COLUMN stock_hsgt.ts_code IS '股票代码';
COMMENT ON COLUMN stock_hsgt.trade_date IS '交易日期';
COMMENT ON COLUMN stock_hsgt.type IS '类型: HK_SZ(深股通)/SZ_HK(港股通深)/HK_SH(沪股通)/SH_HK(港股通沪)';
COMMENT ON COLUMN stock_hsgt.name IS '股票名称';
COMMENT ON COLUMN stock_hsgt.type_name IS '类型名称: 深股通/港股通深/沪股通/港股通沪';

-- ST风险警示板股票
CREATE TABLE stock_st_risk (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    pub_date DATE,
    imp_date DATE NOT NULL,
    st_type VARCHAR(10),
    st_reason VARCHAR(500),
    st_explain TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, imp_date)
);
CREATE INDEX idx_stock_st_risk_ts_code ON stock_st_risk(ts_code);

COMMENT ON TABLE stock_st_risk IS 'ST风险警示板股票列表（Tushare st 接口）';
COMMENT ON COLUMN stock_st_risk.ts_code IS '股票代码';
COMMENT ON COLUMN stock_st_risk.name IS '股票名称';
COMMENT ON COLUMN stock_st_risk.pub_date IS '发布日期';
COMMENT ON COLUMN stock_st_risk.imp_date IS '实施日期';
COMMENT ON COLUMN stock_st_risk.st_type IS 'ST类型（ST/*ST等）';
COMMENT ON COLUMN stock_st_risk.st_reason IS 'ST变更原因';
COMMENT ON COLUMN stock_st_risk.st_explain IS 'ST变更详细原因';

-- 财报披露日期
CREATE TABLE financial_disclosure_dates (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    end_date DATE NOT NULL,
    pre_date DATE,
    actual_date DATE,
    modify_date VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, end_date)
);
CREATE INDEX idx_disclosure_dates_ts_code ON financial_disclosure_dates(ts_code);
CREATE INDEX idx_disclosure_dates_end_date ON financial_disclosure_dates(end_date);

COMMENT ON TABLE financial_disclosure_dates IS '财报披露日期表（Tushare disclosure_date 接口）';
COMMENT ON COLUMN financial_disclosure_dates.ts_code IS 'TS股票代码';
COMMENT ON COLUMN financial_disclosure_dates.ann_date IS '最新披露公告日';
COMMENT ON COLUMN financial_disclosure_dates.end_date IS '报告期（每个季度最后一天，如20250630表示中报）';
COMMENT ON COLUMN financial_disclosure_dates.pre_date IS '预计披露日期';
COMMENT ON COLUMN financial_disclosure_dates.actual_date IS '实际披露日期';
COMMENT ON COLUMN financial_disclosure_dates.modify_date IS '披露日期修正记录';

-- 限售股解禁
CREATE TABLE stock_share_float (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    float_date DATE NOT NULL,
    float_share NUMERIC(18, 2),
    float_ratio NUMERIC(8, 4),
    holder_name VARCHAR(200),
    share_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, float_date, holder_name)
);
CREATE INDEX idx_share_float_ts_code ON stock_share_float(ts_code);
CREATE INDEX idx_share_float_date ON stock_share_float(float_date);

COMMENT ON TABLE stock_share_float IS '限售股解禁表（Tushare share_float 接口）';
COMMENT ON COLUMN stock_share_float.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_share_float.ann_date IS '公告日期';
COMMENT ON COLUMN stock_share_float.float_date IS '解禁日期';
COMMENT ON COLUMN stock_share_float.float_share IS '解禁流通股份（股）';
COMMENT ON COLUMN stock_share_float.float_ratio IS '解禁股份占总股本比率';
COMMENT ON COLUMN stock_share_float.holder_name IS '股东名称';
COMMENT ON COLUMN stock_share_float.share_type IS '股份类型';

-- 股东人数
CREATE TABLE stock_stk_holdernumber (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    end_date DATE NOT NULL,
    holder_num INT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, end_date)
);
CREATE INDEX idx_holdernumber_ts_code ON stock_stk_holdernumber(ts_code);

COMMENT ON TABLE stock_stk_holdernumber IS '股东人数表（Tushare stk_holdernumber 接口）';
COMMENT ON COLUMN stock_stk_holdernumber.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_stk_holdernumber.ann_date IS '公告日期';
COMMENT ON COLUMN stock_stk_holdernumber.end_date IS '截止日期';
COMMENT ON COLUMN stock_stk_holdernumber.holder_num IS '股东户数';

-- 前十大股东
CREATE TABLE stock_top10_holders (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    end_date DATE NOT NULL,
    holder_name VARCHAR(200) NOT NULL,
    hold_amount NUMERIC(18, 2),
    hold_ratio NUMERIC(8, 4),
    hold_float_ratio NUMERIC(8, 4),
    hold_change NUMERIC(8, 4),
    holder_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, end_date, holder_name)
);
CREATE INDEX idx_top10_holders_ts_code ON stock_top10_holders(ts_code);

COMMENT ON TABLE stock_top10_holders IS '前十大股东表（Tushare top10_holders 接口）';
COMMENT ON COLUMN stock_top10_holders.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_top10_holders.ann_date IS '公告日期';
COMMENT ON COLUMN stock_top10_holders.end_date IS '报告期';
COMMENT ON COLUMN stock_top10_holders.holder_name IS '股东名称';
COMMENT ON COLUMN stock_top10_holders.hold_amount IS '持有数量（股）';
COMMENT ON COLUMN stock_top10_holders.hold_ratio IS '占总股本比例(%)';
COMMENT ON COLUMN stock_top10_holders.hold_float_ratio IS '占流通股本比例(%)';
COMMENT ON COLUMN stock_top10_holders.hold_change IS '持股变动';
COMMENT ON COLUMN stock_top10_holders.holder_type IS '股东类型';

-- 前十大流通股东
CREATE TABLE stock_top10_float_holders (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    end_date DATE NOT NULL,
    holder_name VARCHAR(200) NOT NULL,
    hold_amount NUMERIC(18, 2),
    hold_ratio NUMERIC(8, 4),
    hold_float_ratio NUMERIC(8, 4),
    hold_change NUMERIC(8, 4),
    holder_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, end_date, holder_name)
);
CREATE INDEX idx_top10_float_holders_ts_code ON stock_top10_float_holders(ts_code);

COMMENT ON TABLE stock_top10_float_holders IS '前十大流通股东表（Tushare top10_floatholders 接口）';
COMMENT ON COLUMN stock_top10_float_holders.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_top10_float_holders.ann_date IS '公告日期';
COMMENT ON COLUMN stock_top10_float_holders.end_date IS '报告期';
COMMENT ON COLUMN stock_top10_float_holders.holder_name IS '股东名称';
COMMENT ON COLUMN stock_top10_float_holders.hold_amount IS '持有数量（股）';
COMMENT ON COLUMN stock_top10_float_holders.hold_ratio IS '占总股本比例(%)';
COMMENT ON COLUMN stock_top10_float_holders.hold_float_ratio IS '占流通股本比例(%)';
COMMENT ON COLUMN stock_top10_float_holders.hold_change IS '持股变动';
COMMENT ON COLUMN stock_top10_float_holders.holder_type IS '股东类型';

-- 股权质押统计
CREATE TABLE stock_pledge_stat (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    end_date DATE NOT NULL,
    pledge_count INT,
    unrest_pledge NUMERIC(18, 2),
    rest_pledge NUMERIC(18, 2),
    total_share NUMERIC(18, 2),
    pledge_ratio NUMERIC(8, 4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, end_date)
);
CREATE INDEX idx_pledge_stat_ts_code ON stock_pledge_stat(ts_code);

COMMENT ON TABLE stock_pledge_stat IS '股权质押统计表（Tushare pledge_stat 接口）';
COMMENT ON COLUMN stock_pledge_stat.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_pledge_stat.end_date IS '截止日期';
COMMENT ON COLUMN stock_pledge_stat.pledge_count IS '质押次数';
COMMENT ON COLUMN stock_pledge_stat.unrest_pledge IS '无限售股质押数量（万股）';
COMMENT ON COLUMN stock_pledge_stat.rest_pledge IS '限售股质押数量（万股）';
COMMENT ON COLUMN stock_pledge_stat.total_share IS '质押总股本（万股）';
COMMENT ON COLUMN stock_pledge_stat.pledge_ratio IS '质押比例(%)';

-- 股东增减持
CREATE TABLE stock_stk_holdertrade (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    ann_date DATE,
    holder_name VARCHAR(200) NOT NULL,
    holder_type VARCHAR(10),
    in_de VARCHAR(2),
    change_vol NUMERIC(18, 2),
    change_ratio NUMERIC(8, 4),
    after_share NUMERIC(18, 2),
    after_ratio NUMERIC(8, 4),
    avg_price NUMERIC(12, 4),
    total_share NUMERIC(18, 2),
    begin_date DATE,
    close_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, ann_date, holder_name, in_de)
);
CREATE INDEX idx_holdertrade_ts_code ON stock_stk_holdertrade(ts_code);
CREATE INDEX idx_holdertrade_ann_date ON stock_stk_holdertrade(ann_date);

COMMENT ON TABLE stock_stk_holdertrade IS '股东增减持表（Tushare stk_holdertrade 接口）';
COMMENT ON COLUMN stock_stk_holdertrade.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_stk_holdertrade.ann_date IS '公告日期';
COMMENT ON COLUMN stock_stk_holdertrade.holder_name IS '股东名称';
COMMENT ON COLUMN stock_stk_holdertrade.holder_type IS '股东类型';
COMMENT ON COLUMN stock_stk_holdertrade.in_de IS '增减持方向（IN增持/DE减持）';
COMMENT ON COLUMN stock_stk_holdertrade.change_vol IS '变动数量（股）';
COMMENT ON COLUMN stock_stk_holdertrade.change_ratio IS '变动比例(%)';
COMMENT ON COLUMN stock_stk_holdertrade.after_share IS '变动后持股';
COMMENT ON COLUMN stock_stk_holdertrade.after_ratio IS '变动后持股比例(%)';
COMMENT ON COLUMN stock_stk_holdertrade.avg_price IS '增/减持均价';
COMMENT ON COLUMN stock_stk_holdertrade.total_share IS '总股本';
COMMENT ON COLUMN stock_stk_holdertrade.begin_date IS '变动开始日期';
COMMENT ON COLUMN stock_stk_holdertrade.close_date IS '变动结束日期';

-- ===================== Phase 3 新增数据类型 =====================

-- 申万行业分类
CREATE TABLE index_sw_classify (
    index_code VARCHAR(20) PRIMARY KEY,
    industry_name VARCHAR(100),
    parent_code VARCHAR(20),
    level VARCHAR(3),
    industry_code VARCHAR(20),
    is_pub VARCHAR(1),
    src VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE index_sw_classify IS '申万行业分类表（Tushare index_classify 接口）';
COMMENT ON COLUMN index_sw_classify.index_code IS '指数代码';
COMMENT ON COLUMN index_sw_classify.industry_name IS '行业名称';
COMMENT ON COLUMN index_sw_classify.parent_code IS '父级代码';
COMMENT ON COLUMN index_sw_classify.level IS '行业层级 L1/L2/L3';
COMMENT ON COLUMN index_sw_classify.industry_code IS '行业代码';
COMMENT ON COLUMN index_sw_classify.is_pub IS '是否发布指数 0/1';
COMMENT ON COLUMN index_sw_classify.src IS '指数来源 SW2014/SW2021';

-- 申万行业成分
CREATE TABLE index_sw_member (
    id VARCHAR(36) PRIMARY KEY,
    l1_code VARCHAR(20),
    l1_name VARCHAR(100),
    l2_code VARCHAR(20),
    l2_name VARCHAR(100),
    l3_code VARCHAR(20),
    l3_name VARCHAR(100),
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    in_date DATE,
    out_date DATE,
    is_new VARCHAR(1),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (l3_code, ts_code, in_date)
);
CREATE INDEX idx_sw_member_ts_code ON index_sw_member(ts_code);

COMMENT ON TABLE index_sw_member IS '申万行业成分表（Tushare index_member_all 接口）';
COMMENT ON COLUMN index_sw_member.l1_code IS '一级行业代码';
COMMENT ON COLUMN index_sw_member.l1_name IS '一级行业名称';
COMMENT ON COLUMN index_sw_member.l2_code IS '二级行业代码';
COMMENT ON COLUMN index_sw_member.l2_name IS '二级行业名称';
COMMENT ON COLUMN index_sw_member.l3_code IS '三级行业代码';
COMMENT ON COLUMN index_sw_member.l3_name IS '三级行业名称';
COMMENT ON COLUMN index_sw_member.ts_code IS 'TS股票代码';
COMMENT ON COLUMN index_sw_member.name IS '股票名称';
COMMENT ON COLUMN index_sw_member.in_date IS '纳入日期';
COMMENT ON COLUMN index_sw_member.out_date IS '剔除日期';
COMMENT ON COLUMN index_sw_member.is_new IS '是否最新 Y/N';

-- 大盘指数每日指标
CREATE TABLE index_dailybasic (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    total_mv NUMERIC(18, 2),
    float_mv NUMERIC(18, 2),
    total_share NUMERIC(18, 2),
    float_share NUMERIC(18, 2),
    free_share NUMERIC(18, 2),
    turnover_rate NUMERIC(8, 4),
    turnover_rate_f NUMERIC(8, 4),
    pe NUMERIC(12, 4),
    pe_ttm NUMERIC(12, 4),
    pb NUMERIC(12, 4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);
CREATE INDEX idx_index_dailybasic_ts_code ON index_dailybasic(ts_code);

COMMENT ON TABLE index_dailybasic IS '大盘指数每日指标表（Tushare index_dailybasic 接口）';
COMMENT ON COLUMN index_dailybasic.ts_code IS '指数代码';
COMMENT ON COLUMN index_dailybasic.trade_date IS '交易日期';
COMMENT ON COLUMN index_dailybasic.total_mv IS '总市值';
COMMENT ON COLUMN index_dailybasic.float_mv IS '流通市值';
COMMENT ON COLUMN index_dailybasic.total_share IS '总股本';
COMMENT ON COLUMN index_dailybasic.float_share IS '流通股本';
COMMENT ON COLUMN index_dailybasic.free_share IS '自由流通股本';
COMMENT ON COLUMN index_dailybasic.turnover_rate IS '换手率(%)';
COMMENT ON COLUMN index_dailybasic.turnover_rate_f IS '自由流通换手率(%)';
COMMENT ON COLUMN index_dailybasic.pe IS '市盈率';
COMMENT ON COLUMN index_dailybasic.pe_ttm IS '市盈率(TTM)';
COMMENT ON COLUMN index_dailybasic.pb IS '市净率';

-- 卖方盈利预测
CREATE TABLE stock_forecast_pro (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    report_date DATE,
    report_title VARCHAR(500),
    report_type VARCHAR(50),
    classify VARCHAR(50),
    org_name VARCHAR(200),
    author_name VARCHAR(100),
    quarter VARCHAR(10),
    op_rt NUMERIC(18, 4),
    op_pr NUMERIC(18, 4),
    tp NUMERIC(18, 4),
    np NUMERIC(18, 4),
    eps NUMERIC(12, 4),
    pe NUMERIC(12, 4),
    rd NUMERIC(8, 4),
    roe NUMERIC(8, 4),
    ev_ebitda NUMERIC(12, 4),
    rating VARCHAR(50),
    max_price NUMERIC(12, 4),
    min_price NUMERIC(12, 4),
    imp_dg VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, report_date, org_name, quarter)
);
CREATE INDEX idx_forecast_pro_ts_code ON stock_forecast_pro(ts_code);
CREATE INDEX idx_forecast_pro_report_date ON stock_forecast_pro(report_date);

COMMENT ON TABLE stock_forecast_pro IS '卖方盈利预测表（Tushare report_rc 接口，需8000积分）';
COMMENT ON COLUMN stock_forecast_pro.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_forecast_pro.name IS '股票名称';
COMMENT ON COLUMN stock_forecast_pro.report_date IS '报告日期';
COMMENT ON COLUMN stock_forecast_pro.report_title IS '报告标题';
COMMENT ON COLUMN stock_forecast_pro.report_type IS '报告类型';
COMMENT ON COLUMN stock_forecast_pro.classify IS '分类';
COMMENT ON COLUMN stock_forecast_pro.org_name IS '机构名称';
COMMENT ON COLUMN stock_forecast_pro.author_name IS '作者姓名';
COMMENT ON COLUMN stock_forecast_pro.quarter IS '预测季度';
COMMENT ON COLUMN stock_forecast_pro.op_rt IS '预测营业收入';
COMMENT ON COLUMN stock_forecast_pro.op_pr IS '预测营业利润';
COMMENT ON COLUMN stock_forecast_pro.tp IS '预测利润总额';
COMMENT ON COLUMN stock_forecast_pro.np IS '预测净利润';
COMMENT ON COLUMN stock_forecast_pro.eps IS '预测每股收益';
COMMENT ON COLUMN stock_forecast_pro.pe IS '预测市盈率';
COMMENT ON COLUMN stock_forecast_pro.rd IS '预测研发费用';
COMMENT ON COLUMN stock_forecast_pro.roe IS '预测净资产收益率';
COMMENT ON COLUMN stock_forecast_pro.ev_ebitda IS '预测EV/EBITDA';
COMMENT ON COLUMN stock_forecast_pro.rating IS '评级';
COMMENT ON COLUMN stock_forecast_pro.max_price IS '目标最高价';
COMMENT ON COLUMN stock_forecast_pro.min_price IS '目标最低价';
COMMENT ON COLUMN stock_forecast_pro.imp_dg IS '隐含涨幅';

-- 沪深港通资金流向
CREATE TABLE stock_moneyflow_hsgt (
    id VARCHAR(36) PRIMARY KEY,
    trade_date DATE NOT NULL UNIQUE,
    ggt_ss NUMERIC(18, 2),
    ggt_sz NUMERIC(18, 2),
    hgt NUMERIC(18, 2),
    sgt NUMERIC(18, 2),
    north_money NUMERIC(18, 2),
    south_money NUMERIC(18, 2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_moneyflow_hsgt IS '沪深港通资金流向表（Tushare moneyflow_hsgt 接口）';
COMMENT ON COLUMN stock_moneyflow_hsgt.trade_date IS '交易日期';
COMMENT ON COLUMN stock_moneyflow_hsgt.ggt_ss IS '港股通（上海）';
COMMENT ON COLUMN stock_moneyflow_hsgt.ggt_sz IS '港股通（深圳）';
COMMENT ON COLUMN stock_moneyflow_hsgt.hgt IS '沪股通';
COMMENT ON COLUMN stock_moneyflow_hsgt.sgt IS '深股通';
COMMENT ON COLUMN stock_moneyflow_hsgt.north_money IS '北向资金';
COMMENT ON COLUMN stock_moneyflow_hsgt.south_money IS '南向资金';

-- 申万行业日线行情
CREATE TABLE index_sw_daily (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    name VARCHAR(100),
    open NUMERIC(12, 4),
    low NUMERIC(12, 4),
    high NUMERIC(12, 4),
    close NUMERIC(12, 4),
    change NUMERIC(12, 4),
    pct_change NUMERIC(8, 4),
    vol NUMERIC(18, 2),
    amount NUMERIC(18, 2),
    pe NUMERIC(12, 4),
    pb NUMERIC(12, 4),
    float_mv NUMERIC(18, 2),
    total_mv NUMERIC(18, 2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);
CREATE INDEX idx_sw_daily_ts_code ON index_sw_daily(ts_code);
CREATE INDEX idx_sw_daily_trade_date ON index_sw_daily(trade_date);

COMMENT ON TABLE index_sw_daily IS '申万行业日线行情表（Tushare sw_daily 接口）';
COMMENT ON COLUMN index_sw_daily.ts_code IS '行业指数代码';
COMMENT ON COLUMN index_sw_daily.trade_date IS '交易日期';
COMMENT ON COLUMN index_sw_daily.name IS '指数名称';
COMMENT ON COLUMN index_sw_daily.pe IS '市盈率';
COMMENT ON COLUMN index_sw_daily.pb IS '市净率';
COMMENT ON COLUMN index_sw_daily.float_mv IS '流通市值（万元）';
COMMENT ON COLUMN index_sw_daily.total_mv IS '总市值（万元）';

-- ------------------------------------------------------------
-- Phase 4: 指数周线 / 技术因子
-- ------------------------------------------------------------

-- 指数周线行情表
CREATE TABLE index_weekly (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    close NUMERIC(12, 4),
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    pre_close NUMERIC(12, 4),
    change NUMERIC(12, 4),
    pct_chg NUMERIC(8, 4),
    vol NUMERIC(18, 2),
    amount NUMERIC(18, 2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);
CREATE INDEX idx_index_weekly_ts_code ON index_weekly(ts_code);
CREATE INDEX idx_index_weekly_trade_date ON index_weekly(trade_date);

COMMENT ON TABLE index_weekly IS '指数周线行情表（Tushare index_weekly 接口）';
COMMENT ON COLUMN index_weekly.ts_code IS 'TS指数代码';
COMMENT ON COLUMN index_weekly.vol IS '成交量（手）';
COMMENT ON COLUMN index_weekly.amount IS '成交额（千元）';

-- 股票技术因子基础版表（~33列，不复权指标）
CREATE TABLE stock_factor_daily (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    close NUMERIC(12, 4),
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    pre_close NUMERIC(12, 4),
    change NUMERIC(12, 4),
    pct_change NUMERIC(8, 4),
    vol NUMERIC(18, 2),
    amount NUMERIC(18, 2),
    adj_factor NUMERIC(18, 6),
    open_hfq NUMERIC(12, 4),
    open_qfq NUMERIC(12, 4),
    close_hfq NUMERIC(12, 4),
    close_qfq NUMERIC(12, 4),
    high_hfq NUMERIC(12, 4),
    high_qfq NUMERIC(12, 4),
    low_hfq NUMERIC(12, 4),
    low_qfq NUMERIC(12, 4),
    pre_close_hfq NUMERIC(12, 4),
    pre_close_qfq NUMERIC(12, 4),
    macd_dif NUMERIC(18, 6),
    macd_dea NUMERIC(18, 6),
    macd NUMERIC(18, 6),
    kdj_k NUMERIC(18, 6),
    kdj_d NUMERIC(18, 6),
    kdj_j NUMERIC(18, 6),
    rsi_6 NUMERIC(18, 6),
    rsi_12 NUMERIC(18, 6),
    rsi_24 NUMERIC(18, 6),
    boll_upper NUMERIC(18, 6),
    boll_mid NUMERIC(18, 6),
    boll_lower NUMERIC(18, 6),
    cci NUMERIC(18, 6),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);
CREATE INDEX idx_stock_factor_daily_ts_code ON stock_factor_daily(ts_code);
CREATE INDEX idx_stock_factor_daily_trade_date ON stock_factor_daily(trade_date);

COMMENT ON TABLE stock_factor_daily IS '股票技术因子基础版（Tushare stk_factor 接口，含MACD/KDJ/RSI/BOLL/CCI）';
COMMENT ON COLUMN stock_factor_daily.adj_factor IS '复权因子';
COMMENT ON COLUMN stock_factor_daily.open_hfq IS '开盘价（后复权）';
COMMENT ON COLUMN stock_factor_daily.open_qfq IS '开盘价（前复权）';
COMMENT ON COLUMN stock_factor_daily.macd_dif IS 'MACD DIF值';
COMMENT ON COLUMN stock_factor_daily.macd_dea IS 'MACD DEA值';
COMMENT ON COLUMN stock_factor_daily.macd IS 'MACD柱值';
COMMENT ON COLUMN stock_factor_daily.kdj_k IS 'KDJ K值';
COMMENT ON COLUMN stock_factor_daily.kdj_d IS 'KDJ D值';
COMMENT ON COLUMN stock_factor_daily.kdj_j IS 'KDJ J值';
COMMENT ON COLUMN stock_factor_daily.rsi_6 IS 'RSI 6日';
COMMENT ON COLUMN stock_factor_daily.rsi_12 IS 'RSI 12日';
COMMENT ON COLUMN stock_factor_daily.rsi_24 IS 'RSI 24日';
COMMENT ON COLUMN stock_factor_daily.boll_upper IS 'BOLL上轨';
COMMENT ON COLUMN stock_factor_daily.boll_mid IS 'BOLL中轨';
COMMENT ON COLUMN stock_factor_daily.boll_lower IS 'BOLL下轨';
COMMENT ON COLUMN stock_factor_daily.cci IS 'CCI商品通道指数';

-- 股票技术因子专业版表（200+列，含三复权版本的所有技术指标）
CREATE TABLE stock_factor_pro_daily (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    -- 基础行情
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    close NUMERIC(12, 4),
    pre_close NUMERIC(12, 4),
    change NUMERIC(12, 4),
    pct_chg NUMERIC(8, 4),
    vol NUMERIC(18, 2),
    amount NUMERIC(18, 2),
    -- 复权价格（后复权/前复权）
    open_hfq NUMERIC(12, 4),
    open_qfq NUMERIC(12, 4),
    high_hfq NUMERIC(12, 4),
    high_qfq NUMERIC(12, 4),
    low_hfq NUMERIC(12, 4),
    low_qfq NUMERIC(12, 4),
    close_hfq NUMERIC(12, 4),
    close_qfq NUMERIC(12, 4),
    pre_close_hfq NUMERIC(12, 4),
    pre_close_qfq NUMERIC(12, 4),
    -- 估值与股本
    turnover_rate NUMERIC(8, 4),
    turnover_rate_f NUMERIC(8, 4),
    volume_ratio NUMERIC(8, 4),
    pe NUMERIC(12, 4),
    pe_ttm NUMERIC(12, 4),
    pb NUMERIC(12, 4),
    ps NUMERIC(12, 4),
    ps_ttm NUMERIC(12, 4),
    dv_ratio NUMERIC(8, 4),
    dv_ttm NUMERIC(8, 4),
    total_share NUMERIC(18, 2),
    float_share NUMERIC(18, 2),
    free_share NUMERIC(18, 2),
    total_mv NUMERIC(18, 2),
    circ_mv NUMERIC(18, 2),
    adj_factor NUMERIC(18, 6),
    -- ASI 振动升降指标
    asi_bfq NUMERIC(18, 6), asi_hfq NUMERIC(18, 6), asi_qfq NUMERIC(18, 6),
    asit_bfq NUMERIC(18, 6), asit_hfq NUMERIC(18, 6), asit_qfq NUMERIC(18, 6),
    -- ATR 真实波幅
    atr_bfq NUMERIC(18, 6), atr_hfq NUMERIC(18, 6), atr_qfq NUMERIC(18, 6),
    -- BBI 多空指数
    bbi_bfq NUMERIC(18, 6), bbi_hfq NUMERIC(18, 6), bbi_qfq NUMERIC(18, 6),
    -- BIAS 乖离率
    bias1_bfq NUMERIC(18, 6), bias1_hfq NUMERIC(18, 6), bias1_qfq NUMERIC(18, 6),
    bias2_bfq NUMERIC(18, 6), bias2_hfq NUMERIC(18, 6), bias2_qfq NUMERIC(18, 6),
    bias3_bfq NUMERIC(18, 6), bias3_hfq NUMERIC(18, 6), bias3_qfq NUMERIC(18, 6),
    -- BOLL 布林带
    boll_upper_bfq NUMERIC(18, 6), boll_upper_hfq NUMERIC(18, 6), boll_upper_qfq NUMERIC(18, 6),
    boll_mid_bfq NUMERIC(18, 6), boll_mid_hfq NUMERIC(18, 6), boll_mid_qfq NUMERIC(18, 6),
    boll_lower_bfq NUMERIC(18, 6), boll_lower_hfq NUMERIC(18, 6), boll_lower_qfq NUMERIC(18, 6),
    -- BRAR 情绪指标
    brar_ar_bfq NUMERIC(18, 6), brar_ar_hfq NUMERIC(18, 6), brar_ar_qfq NUMERIC(18, 6),
    brar_br_bfq NUMERIC(18, 6), brar_br_hfq NUMERIC(18, 6), brar_br_qfq NUMERIC(18, 6),
    -- CCI 商品通道指数
    cci_bfq NUMERIC(18, 6), cci_hfq NUMERIC(18, 6), cci_qfq NUMERIC(18, 6),
    -- CR 能量指标
    cr_bfq NUMERIC(18, 6), cr_hfq NUMERIC(18, 6), cr_qfq NUMERIC(18, 6),
    -- DFMA 动向平均
    dfma_dif_bfq NUMERIC(18, 6), dfma_dif_hfq NUMERIC(18, 6), dfma_dif_qfq NUMERIC(18, 6),
    dfma_difma_bfq NUMERIC(18, 6), dfma_difma_hfq NUMERIC(18, 6), dfma_difma_qfq NUMERIC(18, 6),
    -- DMI 趋向指标
    dmi_adx_bfq NUMERIC(18, 6), dmi_adx_hfq NUMERIC(18, 6), dmi_adx_qfq NUMERIC(18, 6),
    dmi_adxr_bfq NUMERIC(18, 6), dmi_adxr_hfq NUMERIC(18, 6), dmi_adxr_qfq NUMERIC(18, 6),
    dmi_mdi_bfq NUMERIC(18, 6), dmi_mdi_hfq NUMERIC(18, 6), dmi_mdi_qfq NUMERIC(18, 6),
    dmi_pdi_bfq NUMERIC(18, 6), dmi_pdi_hfq NUMERIC(18, 6), dmi_pdi_qfq NUMERIC(18, 6),
    -- 涨跌天数
    downdays NUMERIC(8, 2),
    updays NUMERIC(8, 2),
    -- DPO 区间震荡线
    dpo_bfq NUMERIC(18, 6), dpo_hfq NUMERIC(18, 6), dpo_qfq NUMERIC(18, 6),
    madpo_bfq NUMERIC(18, 6), madpo_hfq NUMERIC(18, 6), madpo_qfq NUMERIC(18, 6),
    -- EMA 指数移动平均
    ema_5_bfq NUMERIC(18, 6), ema_5_hfq NUMERIC(18, 6), ema_5_qfq NUMERIC(18, 6),
    ema_10_bfq NUMERIC(18, 6), ema_10_hfq NUMERIC(18, 6), ema_10_qfq NUMERIC(18, 6),
    ema_20_bfq NUMERIC(18, 6), ema_20_hfq NUMERIC(18, 6), ema_20_qfq NUMERIC(18, 6),
    ema_30_bfq NUMERIC(18, 6), ema_30_hfq NUMERIC(18, 6), ema_30_qfq NUMERIC(18, 6),
    ema_60_bfq NUMERIC(18, 6), ema_60_hfq NUMERIC(18, 6), ema_60_qfq NUMERIC(18, 6),
    ema_90_bfq NUMERIC(18, 6), ema_90_hfq NUMERIC(18, 6), ema_90_qfq NUMERIC(18, 6),
    ema_250_bfq NUMERIC(18, 6), ema_250_hfq NUMERIC(18, 6), ema_250_qfq NUMERIC(18, 6),
    -- EMV 简易波动指标
    emv_bfq NUMERIC(18, 6), emv_hfq NUMERIC(18, 6), emv_qfq NUMERIC(18, 6),
    maemv_bfq NUMERIC(18, 6), maemv_hfq NUMERIC(18, 6), maemv_qfq NUMERIC(18, 6),
    -- EXPMA 指数平均线
    expma_12_bfq NUMERIC(18, 6), expma_12_hfq NUMERIC(18, 6), expma_12_qfq NUMERIC(18, 6),
    expma_50_bfq NUMERIC(18, 6), expma_50_hfq NUMERIC(18, 6), expma_50_qfq NUMERIC(18, 6),
    -- KDJ 随机指标
    kdj_k_bfq NUMERIC(18, 6), kdj_k_hfq NUMERIC(18, 6), kdj_k_qfq NUMERIC(18, 6),
    kdj_d_bfq NUMERIC(18, 6), kdj_d_hfq NUMERIC(18, 6), kdj_d_qfq NUMERIC(18, 6),
    kdj_j_bfq NUMERIC(18, 6), kdj_j_hfq NUMERIC(18, 6), kdj_j_qfq NUMERIC(18, 6),
    -- KTN 肯特纳通道
    ktn_down_bfq NUMERIC(18, 6), ktn_down_hfq NUMERIC(18, 6), ktn_down_qfq NUMERIC(18, 6),
    ktn_mid_bfq NUMERIC(18, 6), ktn_mid_hfq NUMERIC(18, 6), ktn_mid_qfq NUMERIC(18, 6),
    ktn_upper_bfq NUMERIC(18, 6), ktn_upper_hfq NUMERIC(18, 6), ktn_upper_qfq NUMERIC(18, 6),
    -- 极端天数
    lowdays NUMERIC(8, 2),
    topdays NUMERIC(8, 2),
    -- MA 移动平均
    ma_5_bfq NUMERIC(18, 6), ma_5_hfq NUMERIC(18, 6), ma_5_qfq NUMERIC(18, 6),
    ma_10_bfq NUMERIC(18, 6), ma_10_hfq NUMERIC(18, 6), ma_10_qfq NUMERIC(18, 6),
    ma_20_bfq NUMERIC(18, 6), ma_20_hfq NUMERIC(18, 6), ma_20_qfq NUMERIC(18, 6),
    ma_30_bfq NUMERIC(18, 6), ma_30_hfq NUMERIC(18, 6), ma_30_qfq NUMERIC(18, 6),
    ma_60_bfq NUMERIC(18, 6), ma_60_hfq NUMERIC(18, 6), ma_60_qfq NUMERIC(18, 6),
    ma_90_bfq NUMERIC(18, 6), ma_90_hfq NUMERIC(18, 6), ma_90_qfq NUMERIC(18, 6),
    ma_250_bfq NUMERIC(18, 6), ma_250_hfq NUMERIC(18, 6), ma_250_qfq NUMERIC(18, 6),
    -- MACD
    macd_dif_bfq NUMERIC(18, 6), macd_dif_hfq NUMERIC(18, 6), macd_dif_qfq NUMERIC(18, 6),
    macd_dea_bfq NUMERIC(18, 6), macd_dea_hfq NUMERIC(18, 6), macd_dea_qfq NUMERIC(18, 6),
    macd_bfq NUMERIC(18, 6), macd_hfq NUMERIC(18, 6), macd_qfq NUMERIC(18, 6),
    -- MASS 梅斯线
    mass_bfq NUMERIC(18, 6), mass_hfq NUMERIC(18, 6), mass_qfq NUMERIC(18, 6),
    ma_mass_bfq NUMERIC(18, 6), ma_mass_hfq NUMERIC(18, 6), ma_mass_qfq NUMERIC(18, 6),
    -- MFI 资金流量指标
    mfi_bfq NUMERIC(18, 6), mfi_hfq NUMERIC(18, 6), mfi_qfq NUMERIC(18, 6),
    -- MTM 动量线
    mtm_bfq NUMERIC(18, 6), mtm_hfq NUMERIC(18, 6), mtm_qfq NUMERIC(18, 6),
    mtmma_bfq NUMERIC(18, 6), mtmma_hfq NUMERIC(18, 6), mtmma_qfq NUMERIC(18, 6),
    -- OBV 能量潮
    obv_bfq NUMERIC(18, 6), obv_hfq NUMERIC(18, 6), obv_qfq NUMERIC(18, 6),
    -- PSY 心理线
    psy_bfq NUMERIC(18, 6), psy_hfq NUMERIC(18, 6), psy_qfq NUMERIC(18, 6),
    psyma_bfq NUMERIC(18, 6), psyma_hfq NUMERIC(18, 6), psyma_qfq NUMERIC(18, 6),
    -- ROC 变动率
    roc_bfq NUMERIC(18, 6), roc_hfq NUMERIC(18, 6), roc_qfq NUMERIC(18, 6),
    maroc_bfq NUMERIC(18, 6), maroc_hfq NUMERIC(18, 6), maroc_qfq NUMERIC(18, 6),
    -- RSI 相对强弱指标
    rsi_6_bfq NUMERIC(18, 6), rsi_6_hfq NUMERIC(18, 6), rsi_6_qfq NUMERIC(18, 6),
    rsi_12_bfq NUMERIC(18, 6), rsi_12_hfq NUMERIC(18, 6), rsi_12_qfq NUMERIC(18, 6),
    rsi_24_bfq NUMERIC(18, 6), rsi_24_hfq NUMERIC(18, 6), rsi_24_qfq NUMERIC(18, 6),
    -- TAQ 三均线
    taq_down_bfq NUMERIC(18, 6), taq_down_hfq NUMERIC(18, 6), taq_down_qfq NUMERIC(18, 6),
    taq_mid_bfq NUMERIC(18, 6), taq_mid_hfq NUMERIC(18, 6), taq_mid_qfq NUMERIC(18, 6),
    taq_up_bfq NUMERIC(18, 6), taq_up_hfq NUMERIC(18, 6), taq_up_qfq NUMERIC(18, 6),
    -- TRIX 三重指数平滑平均线
    trix_bfq NUMERIC(18, 6), trix_hfq NUMERIC(18, 6), trix_qfq NUMERIC(18, 6),
    trma_bfq NUMERIC(18, 6), trma_hfq NUMERIC(18, 6), trma_qfq NUMERIC(18, 6),
    -- VR 容量比率
    vr_bfq NUMERIC(18, 6), vr_hfq NUMERIC(18, 6), vr_qfq NUMERIC(18, 6),
    -- WR 威廉指标
    wr6_bfq NUMERIC(18, 6), wr6_hfq NUMERIC(18, 6), wr6_qfq NUMERIC(18, 6),
    wr10_bfq NUMERIC(18, 6), wr10_hfq NUMERIC(18, 6), wr10_qfq NUMERIC(18, 6),
    -- XSII 薛斯通道
    xsii_td1_bfq NUMERIC(18, 6), xsii_td1_hfq NUMERIC(18, 6), xsii_td1_qfq NUMERIC(18, 6),
    xsii_td2_bfq NUMERIC(18, 6), xsii_td2_hfq NUMERIC(18, 6), xsii_td2_qfq NUMERIC(18, 6),
    xsii_td3_bfq NUMERIC(18, 6), xsii_td3_hfq NUMERIC(18, 6), xsii_td3_qfq NUMERIC(18, 6),
    xsii_td4_bfq NUMERIC(18, 6), xsii_td4_hfq NUMERIC(18, 6), xsii_td4_qfq NUMERIC(18, 6),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);
CREATE INDEX idx_stock_factor_pro_daily_ts_code ON stock_factor_pro_daily(ts_code);
CREATE INDEX idx_stock_factor_pro_daily_trade_date ON stock_factor_pro_daily(trade_date);

COMMENT ON TABLE stock_factor_pro_daily IS '股票技术因子专业版（Tushare stk_factor_pro 接口，200+指标列含三复权版本）';
COMMENT ON COLUMN stock_factor_pro_daily.asi_bfq IS 'ASI振动升降指标（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.atr_bfq IS 'ATR真实波幅（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.bbi_bfq IS 'BBI多空指数（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.bias1_bfq IS 'BIAS乖离率6日（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.boll_upper_bfq IS 'BOLL上轨（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.brar_ar_bfq IS 'BRAR情绪指标-AR（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.cci_bfq IS 'CCI商品通道指数（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.cr_bfq IS 'CR能量指标（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.dfma_dif_bfq IS 'DFMA动向平均-DIF（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.dmi_adx_bfq IS 'DMI趋向指标-ADX（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.dpo_bfq IS 'DPO区间震荡线（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.ema_5_bfq IS 'EMA指数移动平均5日（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.emv_bfq IS 'EMV简易波动指标（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.expma_12_bfq IS 'EXPMA指数平均线12日（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.kdj_k_bfq IS 'KDJ K值（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.ktn_down_bfq IS 'KTN肯特纳通道下轨（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.ma_5_bfq IS 'MA移动平均5日（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.macd_dif_bfq IS 'MACD DIF值（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.mass_bfq IS 'MASS梅斯线（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.mfi_bfq IS 'MFI资金流量指标（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.mtm_bfq IS 'MTM动量线（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.obv_bfq IS 'OBV能量潮（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.psy_bfq IS 'PSY心理线（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.roc_bfq IS 'ROC变动率（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.rsi_6_bfq IS 'RSI 6日（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.taq_down_bfq IS 'TAQ三均线下轨（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.trix_bfq IS 'TRIX三重指数平滑平均线（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.vr_bfq IS 'VR容量比率（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.wr6_bfq IS 'WR威廉指标6日（不复权）';
COMMENT ON COLUMN stock_factor_pro_daily.xsii_td1_bfq IS 'XSII薛斯通道TD1（不复权）';

-- ==================== 指数技术因子专业版 ====================

CREATE TABLE index_factor_pro_daily (
    id VARCHAR(36) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    close NUMERIC(12, 4),
    pre_close NUMERIC(12, 4),
    change NUMERIC(12, 4),
    pct_change NUMERIC(8, 4),
    vol NUMERIC(18, 2),
    amount NUMERIC(18, 2),
    asi_bfq NUMERIC(18, 6),
    asit_bfq NUMERIC(18, 6),
    atr_bfq NUMERIC(18, 6),
    bbi_bfq NUMERIC(18, 6),
    bias1_bfq NUMERIC(18, 6),
    bias2_bfq NUMERIC(18, 6),
    bias3_bfq NUMERIC(18, 6),
    boll_lower_bfq NUMERIC(18, 6),
    boll_mid_bfq NUMERIC(18, 6),
    boll_upper_bfq NUMERIC(18, 6),
    brar_ar_bfq NUMERIC(18, 6),
    brar_br_bfq NUMERIC(18, 6),
    cci_bfq NUMERIC(18, 6),
    cr_bfq NUMERIC(18, 6),
    dfma_dif_bfq NUMERIC(18, 6),
    dfma_difma_bfq NUMERIC(18, 6),
    dmi_adx_bfq NUMERIC(18, 6),
    dmi_adxr_bfq NUMERIC(18, 6),
    dmi_mdi_bfq NUMERIC(18, 6),
    dmi_pdi_bfq NUMERIC(18, 6),
    downdays NUMERIC(12, 4),
    updays NUMERIC(12, 4),
    dpo_bfq NUMERIC(18, 6),
    madpo_bfq NUMERIC(18, 6),
    ema_bfq_10 NUMERIC(18, 6),
    ema_bfq_20 NUMERIC(18, 6),
    ema_bfq_250 NUMERIC(18, 6),
    ema_bfq_30 NUMERIC(18, 6),
    ema_bfq_5 NUMERIC(18, 6),
    ema_bfq_60 NUMERIC(18, 6),
    ema_bfq_90 NUMERIC(18, 6),
    emv_bfq NUMERIC(18, 6),
    maemv_bfq NUMERIC(18, 6),
    expma_12_bfq NUMERIC(18, 6),
    expma_50_bfq NUMERIC(18, 6),
    kdj_bfq NUMERIC(18, 6),
    kdj_d_bfq NUMERIC(18, 6),
    kdj_k_bfq NUMERIC(18, 6),
    ktn_down_bfq NUMERIC(18, 6),
    ktn_mid_bfq NUMERIC(18, 6),
    ktn_upper_bfq NUMERIC(18, 6),
    lowdays NUMERIC(12, 4),
    topdays NUMERIC(12, 4),
    ma_bfq_10 NUMERIC(18, 6),
    ma_bfq_20 NUMERIC(18, 6),
    ma_bfq_250 NUMERIC(18, 6),
    ma_bfq_30 NUMERIC(18, 6),
    ma_bfq_5 NUMERIC(18, 6),
    ma_bfq_60 NUMERIC(18, 6),
    ma_bfq_90 NUMERIC(18, 6),
    macd_bfq NUMERIC(18, 6),
    macd_dea_bfq NUMERIC(18, 6),
    macd_dif_bfq NUMERIC(18, 6),
    mass_bfq NUMERIC(18, 6),
    ma_mass_bfq NUMERIC(18, 6),
    mfi_bfq NUMERIC(18, 6),
    mtm_bfq NUMERIC(18, 6),
    mtmma_bfq NUMERIC(18, 6),
    obv_bfq NUMERIC(18, 6),
    psy_bfq NUMERIC(18, 6),
    psyma_bfq NUMERIC(18, 6),
    roc_bfq NUMERIC(18, 6),
    maroc_bfq NUMERIC(18, 6),
    rsi_bfq_12 NUMERIC(18, 6),
    rsi_bfq_24 NUMERIC(18, 6),
    rsi_bfq_6 NUMERIC(18, 6),
    taq_down_bfq NUMERIC(18, 6),
    taq_mid_bfq NUMERIC(18, 6),
    taq_up_bfq NUMERIC(18, 6),
    trix_bfq NUMERIC(18, 6),
    trma_bfq NUMERIC(18, 6),
    vr_bfq NUMERIC(18, 6),
    wr_bfq NUMERIC(18, 6),
    wr1_bfq NUMERIC(18, 6),
    xsii_td1_bfq NUMERIC(18, 6),
    xsii_td2_bfq NUMERIC(18, 6),
    xsii_td3_bfq NUMERIC(18, 6),
    xsii_td4_bfq NUMERIC(18, 6),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ts_code, trade_date)
);
CREATE INDEX idx_factor_pro_ts_code ON index_factor_pro_daily(ts_code);
CREATE INDEX idx_factor_pro_trade_date ON index_factor_pro_daily(trade_date);

COMMENT ON TABLE index_factor_pro_daily IS '指数技术因子专业版（Tushare idx_factor_pro 接口）';
COMMENT ON COLUMN index_factor_pro_daily.ts_code IS '指数代码（大盘指数/申万指数/中信指数）';
COMMENT ON COLUMN index_factor_pro_daily.trade_date IS '交易日期';
COMMENT ON COLUMN index_factor_pro_daily.vol IS '成交量（手）';
COMMENT ON COLUMN index_factor_pro_daily.amount IS '成交额（千元）';
COMMENT ON COLUMN index_factor_pro_daily.downdays IS '连跌天数';
COMMENT ON COLUMN index_factor_pro_daily.updays IS '连涨天数';
COMMENT ON COLUMN index_factor_pro_daily.lowdays IS '当前最低价是近多少周期内最低价的最小值';
COMMENT ON COLUMN index_factor_pro_daily.topdays IS '当前最高价是近多少周期内最高价的最大值';
-- 技术指标（均不复权_bfq，基于前复权价格计算）
COMMENT ON COLUMN index_factor_pro_daily.asi_bfq IS '振动升降指标 ASI';
COMMENT ON COLUMN index_factor_pro_daily.atr_bfq IS '真实波动N日平均值 ATR(N=20)';
COMMENT ON COLUMN index_factor_pro_daily.bbi_bfq IS 'BBI多空指标';
COMMENT ON COLUMN index_factor_pro_daily.bias1_bfq IS 'BIAS乖离率(L1=6)';
COMMENT ON COLUMN index_factor_pro_daily.boll_upper_bfq IS '布林带上轨 BOLL(N=20,P=2)';
COMMENT ON COLUMN index_factor_pro_daily.boll_mid_bfq IS '布林带中轨';
COMMENT ON COLUMN index_factor_pro_daily.boll_lower_bfq IS '布林带下轨';
COMMENT ON COLUMN index_factor_pro_daily.brar_ar_bfq IS 'BRAR情绪指标 AR';
COMMENT ON COLUMN index_factor_pro_daily.brar_br_bfq IS 'BRAR情绪指标 BR';
COMMENT ON COLUMN index_factor_pro_daily.cci_bfq IS '顺势指标 CCI(N=14)';
COMMENT ON COLUMN index_factor_pro_daily.cr_bfq IS 'CR价格动量指标(N=20)';
COMMENT ON COLUMN index_factor_pro_daily.dfma_dif_bfq IS '平行线差指标 DIF';
COMMENT ON COLUMN index_factor_pro_daily.dmi_adx_bfq IS '动向指标 ADX';
COMMENT ON COLUMN index_factor_pro_daily.dmi_pdi_bfq IS '动向指标 PDI';
COMMENT ON COLUMN index_factor_pro_daily.dmi_mdi_bfq IS '动向指标 MDI';
COMMENT ON COLUMN index_factor_pro_daily.ema_bfq_5 IS '指数移动平均 EMA(N=5)';
COMMENT ON COLUMN index_factor_pro_daily.ema_bfq_10 IS '指数移动平均 EMA(N=10)';
COMMENT ON COLUMN index_factor_pro_daily.ema_bfq_20 IS '指数移动平均 EMA(N=20)';
COMMENT ON COLUMN index_factor_pro_daily.ema_bfq_60 IS '指数移动平均 EMA(N=60)';
COMMENT ON COLUMN index_factor_pro_daily.ema_bfq_250 IS '指数移动平均 EMA(N=250)';
COMMENT ON COLUMN index_factor_pro_daily.emv_bfq IS '简易波动指标 EMV';
COMMENT ON COLUMN index_factor_pro_daily.expma_12_bfq IS 'EMA指数平均数指标(N1=12)';
COMMENT ON COLUMN index_factor_pro_daily.expma_50_bfq IS 'EMA指数平均数指标(N2=50)';
COMMENT ON COLUMN index_factor_pro_daily.kdj_k_bfq IS 'KDJ指标 K值';
COMMENT ON COLUMN index_factor_pro_daily.kdj_d_bfq IS 'KDJ指标 D值';
COMMENT ON COLUMN index_factor_pro_daily.kdj_bfq IS 'KDJ指标 J值';
COMMENT ON COLUMN index_factor_pro_daily.ktn_upper_bfq IS '肯特纳通道上轨';
COMMENT ON COLUMN index_factor_pro_daily.ktn_mid_bfq IS '肯特纳通道中轨';
COMMENT ON COLUMN index_factor_pro_daily.ktn_down_bfq IS '肯特纳通道下轨';
COMMENT ON COLUMN index_factor_pro_daily.ma_bfq_5 IS '简单移动平均 MA(N=5)';
COMMENT ON COLUMN index_factor_pro_daily.ma_bfq_10 IS '简单移动平均 MA(N=10)';
COMMENT ON COLUMN index_factor_pro_daily.ma_bfq_20 IS '简单移动平均 MA(N=20)';
COMMENT ON COLUMN index_factor_pro_daily.ma_bfq_60 IS '简单移动平均 MA(N=60)';
COMMENT ON COLUMN index_factor_pro_daily.ma_bfq_250 IS '简单移动平均 MA(N=250)';
COMMENT ON COLUMN index_factor_pro_daily.macd_dif_bfq IS 'MACD指标 DIF';
COMMENT ON COLUMN index_factor_pro_daily.macd_dea_bfq IS 'MACD指标 DEA';
COMMENT ON COLUMN index_factor_pro_daily.macd_bfq IS 'MACD指标 MACD柱';
COMMENT ON COLUMN index_factor_pro_daily.mass_bfq IS '梅斯线 MASS';
COMMENT ON COLUMN index_factor_pro_daily.mfi_bfq IS 'MFI资金流量指标(N=14)';
COMMENT ON COLUMN index_factor_pro_daily.mtm_bfq IS '动量指标 MTM(N=12)';
COMMENT ON COLUMN index_factor_pro_daily.obv_bfq IS '能量潮指标 OBV';
COMMENT ON COLUMN index_factor_pro_daily.psy_bfq IS 'PSY心理线(N=12)';
COMMENT ON COLUMN index_factor_pro_daily.roc_bfq IS '变动率指标 ROC(N=12)';
COMMENT ON COLUMN index_factor_pro_daily.rsi_bfq_6 IS 'RSI指标(N=6)';
COMMENT ON COLUMN index_factor_pro_daily.rsi_bfq_12 IS 'RSI指标(N=12)';
COMMENT ON COLUMN index_factor_pro_daily.rsi_bfq_24 IS 'RSI指标(N=24)';
COMMENT ON COLUMN index_factor_pro_daily.taq_up_bfq IS '唐安奇通道上轨(海龟交易)';
COMMENT ON COLUMN index_factor_pro_daily.taq_mid_bfq IS '唐安奇通道中轨';
COMMENT ON COLUMN index_factor_pro_daily.taq_down_bfq IS '唐安奇通道下轨';
COMMENT ON COLUMN index_factor_pro_daily.trix_bfq IS '三重指数平滑平均线 TRIX';
COMMENT ON COLUMN index_factor_pro_daily.vr_bfq IS 'VR容量比率(M1=26)';
COMMENT ON COLUMN index_factor_pro_daily.wr_bfq IS '威廉指标 W%R(N=10)';
COMMENT ON COLUMN index_factor_pro_daily.wr1_bfq IS '威廉指标 W%R(N=6)';
COMMENT ON COLUMN index_factor_pro_daily.xsii_td1_bfq IS '薛斯通道II TD1';
COMMENT ON COLUMN index_factor_pro_daily.xsii_td2_bfq IS '薛斯通道II TD2';
COMMENT ON COLUMN index_factor_pro_daily.xsii_td3_bfq IS '薛斯通道II TD3';
COMMENT ON COLUMN index_factor_pro_daily.xsii_td4_bfq IS '薛斯通道II TD4';
