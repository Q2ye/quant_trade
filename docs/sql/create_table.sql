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
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(100) NOT NULL,
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
COMMENT ON COLUMN sys_users.id IS '用户ID（自增主键）';
COMMENT ON COLUMN sys_users.username IS '用户名（唯一）';
COMMENT ON COLUMN sys_users.password_hash IS '密码哈希值（BCrypt加密）';
COMMENT ON COLUMN sys_users.email IS '用户邮箱';
COMMENT ON COLUMN sys_users.phone IS '手机号码';
COMMENT ON COLUMN sys_users.real_name IS '用户真实姓名';
COMMENT ON COLUMN sys_users.role IS '用户角色：admin-管理员, user-普通用户, guest-访客';
COMMENT ON COLUMN sys_users.is_active IS '账户是否激活';
COMMENT ON COLUMN sys_users.last_login IS '最后登录时间';
COMMENT ON COLUMN sys_users.created_at IS '账户创建时间';
COMMENT ON COLUMN sys_users.updated_at IS '账户信息最后更新时间';

-- 用户权限表
CREATE TABLE sys_permissions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id) ON DELETE CASCADE,
    module VARCHAR(50) NOT NULL,
    can_read BOOLEAN DEFAULT FALSE,
    can_write BOOLEAN DEFAULT FALSE,
    can_execute BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_permissions IS '用户细粒度权限表';
COMMENT ON COLUMN sys_permissions.user_id IS '外键，关联用户ID';
COMMENT ON COLUMN sys_permissions.module IS '权限所属模块（如strategy, basket, trading, market）';
COMMENT ON COLUMN sys_permissions.can_read IS '是否可读';
COMMENT ON COLUMN sys_permissions.can_write IS '是否可写';
COMMENT ON COLUMN sys_permissions.can_execute IS '是否可执行（如交易、回测）';

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
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
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
    ts_code VARCHAR(20) PRIMARY KEY REFERENCES stock_basic(ts_code),
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
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL REFERENCES stock_company(ts_code),
    ann_date DATE NOT NULL,
    name VARCHAR(50) NOT NULL,
    gender CHAR(1),
    lev VARCHAR(20),
    title VARCHAR(100) NOT NULL,
    edu VARCHAR(20),
    national VARCHAR(20),
    birthday DATE,
    begin_date DATE,
    end_date DATE,
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
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL REFERENCES stock_company(ts_code),
    ann_date DATE NOT NULL,
    end_date DATE NOT NULL,
    name VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    reward NUMERIC(18, 2) NOT NULL,
    hold_vol BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stk_rewards IS '上市公司管理层薪酬与持股明细表';
COMMENT ON COLUMN stk_rewards.ts_code IS 'TS股票代码（e.g. 600000.SH）';
COMMENT ON COLUMN stk_rewards.ann_date IS '公告发布日期';
COMMENT ON COLUMN stk_rewards.end_date IS '报告期截止日期';
COMMENT ON COLUMN stk_rewards.name IS '管理层成员姓名';
COMMENT ON COLUMN stk_rewards.title IS '担任职务（e.g. 董事长/财务总监）';
COMMENT ON COLUMN stk_rewards.reward IS '年度税前报酬总额（单位：元）';
COMMENT ON COLUMN stk_rewards.hold_vol IS '期末直接持股数量（单位：股）';
COMMENT ON COLUMN stk_rewards.created_at IS '数据入库时间（自动记录）';
COMMENT ON COLUMN stk_rewards.updated_at IS '数据最后更新时间（自动更新）';

-- ------------------------------------------------------------
-- 1.3 账户相关表
-- ------------------------------------------------------------

-- 账户信息表
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    account_number VARCHAR(50) NOT NULL UNIQUE,
    account_name VARCHAR(100) NOT NULL,
    user_id INT NOT NULL REFERENCES sys_users(id),
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

-- ------------------------------------------------------------
-- 1.4 策略管理模块
-- ------------------------------------------------------------

-- 策略实例表
CREATE TABLE strategies (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    user_id INT NOT NULL REFERENCES sys_users(id),
    description TEXT,
    class_name VARCHAR(100) NOT NULL,
    module_path VARCHAR(200) NOT NULL,
    status VARCHAR(20) DEFAULT 'stopped' CHECK (status IN ('running', 'stopped', 'error')),
    parameters JSONB NOT NULL DEFAULT '{}'::JSONB,
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
COMMENT ON COLUMN strategies.status IS '策略运行状态：running-运行中, stopped-已停止, error-异常';
COMMENT ON COLUMN strategies.parameters IS '策略参数（JSON格式，如{"window": 20, "threshold": 0.02}）';

-- 策略运行记录表
CREATE TABLE strategy_runs (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
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

-- ------------------------------------------------------------
-- 1.5 交易管理模块
-- ------------------------------------------------------------

-- 订单表
CREATE TABLE orders (
    order_id VARCHAR(32) PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id),
    account_id INT NOT NULL REFERENCES accounts(id),
    strategy_id VARCHAR(32) REFERENCES strategies(id),
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
    trade_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
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
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id),
    account_id INT NOT NULL REFERENCES accounts(id),
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
    id SERIAL PRIMARY KEY,
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

-- ETF基准指数列表信息
CREATE TABLE etf_index (
    ts_code VARCHAR(20) PRIMARY KEY,
    indx_name VARCHAR(200) NOT NULL,
    indx_csname VARCHAR(100) NOT NULL,
    pub_party_name VARCHAR(200) NOT NULL,
    pub_date CHAR(8) NOT NULL,
    base_date CHAR(8) NOT NULL,
    bp REAL NOT NULL,
    adj_circle VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE etf_index IS 'ETF基准指数列表信息';
COMMENT ON COLUMN etf_index.ts_code IS '指数代码（唯一标识）';
COMMENT ON COLUMN etf_index.indx_name IS '指数全称';
COMMENT ON COLUMN etf_index.indx_csname IS '指数简称';
COMMENT ON COLUMN etf_index.pub_party_name IS '指数发布机构名称';
COMMENT ON COLUMN etf_index.pub_date IS '发布日期（格式：YYYYMMDD）';
COMMENT ON COLUMN etf_index.base_date IS '指数基期（格式：YYYYMMDD）';
COMMENT ON COLUMN etf_index.bp IS '指数基点（单位：点）';
COMMENT ON COLUMN etf_index.adj_circle IS '成份证券调整周期（如：每季度/每半年）';

-- ETF基础信息表
CREATE TABLE etf_basic (
    ts_code VARCHAR(20) PRIMARY KEY,
    csname VARCHAR(100) NOT NULL,
    extname VARCHAR(200) NOT NULL,
    cname VARCHAR(200) NOT NULL,
    index_code VARCHAR(20) REFERENCES etf_index(ts_code),
    index_name VARCHAR(200),
    setup_date DATE NOT NULL,
    list_date DATE,
    list_status CHAR(1) NOT NULL,
    exchange CHAR(2) NOT NULL,
    mgr_name VARCHAR(100) NOT NULL,
    custod_name VARCHAR(100) NOT NULL,
    mgt_fee REAL,
    etf_type VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE etf_basic IS '国内ETF基础信息（含QDII）';
COMMENT ON COLUMN etf_basic.ts_code IS '基金交易代码（带交易所后缀）';
COMMENT ON COLUMN etf_basic.csname IS 'ETF中文简称';
COMMENT ON COLUMN etf_basic.extname IS 'ETF扩位交易所简称';
COMMENT ON COLUMN etf_basic.cname IS '基金中文全称';
COMMENT ON COLUMN etf_basic.index_code IS '跟踪指数代码';
COMMENT ON COLUMN etf_basic.index_name IS '基准指数中文全称';
COMMENT ON COLUMN etf_basic.setup_date IS '设立日期（格式：YYYYMMDD）';
COMMENT ON COLUMN etf_basic.list_date IS '上市日期（格式：YYYYMMDD）';
COMMENT ON COLUMN etf_basic.list_status IS '存续状态（L上市/D退市/P待上市）';
COMMENT ON COLUMN etf_basic.exchange IS '交易所（SH/SZ）';
COMMENT ON COLUMN etf_basic.mgr_name IS '基金管理人简称';
COMMENT ON COLUMN etf_basic.custod_name IS '基金托管人名称';
COMMENT ON COLUMN etf_basic.mgt_fee IS '基金管理费率（百分比）';
COMMENT ON COLUMN etf_basic.etf_type IS '投资通道类型（境内/QDII）';

-- ------------------------------------------------------------
-- 1.8 回测相关表
-- ------------------------------------------------------------

-- 回测任务表
CREATE TABLE backtest_tasks (
    id VARCHAR(32) PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id),
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id),
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
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(32) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
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
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(32) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
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

-- ------------------------------------------------------------
-- 1.9 风控管理模块
-- ------------------------------------------------------------

-- 风控规则表
CREATE TABLE risk_rules (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    parameters TEXT,
    total_records INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE data_sync_tasks IS '数据同步任务记录表';
COMMENT ON COLUMN data_sync_tasks.task_type IS '任务类型：daily-日线, minute-分钟线, financial-财务数据, etc.';
COMMENT ON COLUMN data_sync_tasks.status IS '任务状态：pending-等待中, running-执行中, completed-成功, failed-失败';
COMMENT ON COLUMN data_sync_tasks.start_time IS '任务开始时间';
COMMENT ON COLUMN data_sync_tasks.end_time IS '任务结束时间';
COMMENT ON COLUMN data_sync_tasks.parameters IS '任务参数';
COMMENT ON COLUMN data_sync_tasks.total_records IS '同步数据记录数';
COMMENT ON COLUMN data_sync_tasks.error_message IS '错误信息（如果任务失败）';

-- 系统配置表
CREATE TABLE system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type VARCHAR(50) DEFAULT 'string',
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_by INT REFERENCES sys_users(id),
    updated_by INT REFERENCES sys_users(id),
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL,
    module VARCHAR(50) NOT NULL,
    user_id INT REFERENCES sys_users(id),
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
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id),
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
    id SERIAL PRIMARY KEY,
    audit_type VARCHAR(50) NOT NULL CHECK (audit_type IN ('login', 'logout', 'access', 'data_change', 'config_change', 'security_event')),
    user_id INT REFERENCES sys_users(id),
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
    id SERIAL PRIMARY KEY,
    notification_type VARCHAR(50) NOT NULL CHECK (notification_type IN ('system', 'alert', 'trade', 'strategy', 'data', 'report')),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    sender_type VARCHAR(50) DEFAULT 'system',
    sender_id VARCHAR(100),
    recipient_type VARCHAR(20) DEFAULT 'user' CHECK (recipient_type IN ('user', 'role', 'all')),
    recipient_id INT,
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
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL CHECK (alert_level IN ('critical', 'warning', 'info')),
    source_module VARCHAR(50) NOT NULL,
    source_id VARCHAR(100),
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved', 'suppressed')),
    acknowledged_by INT REFERENCES sys_users(id),
    acknowledged_at TIMESTAMPTZ,
    resolved_by INT REFERENCES sys_users(id),
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
COMMENT ON COLUMN monitor_alerts.metadata IS '报警元数据（JSON格式）';
COMMENT ON COLUMN monitor_alerts.status IS '报警状态';
COMMENT ON COLUMN monitor_alerts.notification_channels IS '通知渠道（email, wechat, dingtalk, sms等）';

CREATE INDEX idx_monitor_alerts_status ON monitor_alerts(status);
CREATE INDEX idx_monitor_alerts_level ON monitor_alerts(alert_level);
CREATE INDEX idx_monitor_alerts_type ON monitor_alerts(alert_type);
CREATE INDEX idx_monitor_alerts_created_at ON monitor_alerts(created_at DESC);
CREATE INDEX idx_monitor_alerts_source ON monitor_alerts(source_module, source_id);

-- ------------------------------------------------------------
-- 1.11 因子相关表
-- ------------------------------------------------------------

-- 因子定义表
CREATE TABLE factor_definitions (
    id SERIAL PRIMARY KEY,
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
    created_by INT REFERENCES sys_users(id),
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

-- ------------------------------------------------------------
-- 1.12 分析相关表
-- ------------------------------------------------------------

-- 分析报告表
CREATE TABLE analysis_reports (
    id SERIAL PRIMARY KEY,
    report_type VARCHAR(50) NOT NULL CHECK (report_type IN ('daily', 'weekly', 'monthly', 'performance', 'risk', 'custom')),
    report_name VARCHAR(200) NOT NULL,
    report_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    report_data JSONB,
    format VARCHAR(20) DEFAULT 'json' CHECK (format IN ('json', 'html', 'pdf', 'excel')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'completed', 'failed')),
    generated_by INT REFERENCES sys_users(id),
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

-- ------------------------------------------------------------
-- 1.13 财务数据表
-- ------------------------------------------------------------

-- 财务报表主表
CREATE TABLE financial_statements (
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL REFERENCES stock_basic(ts_code),
    ann_date DATE NOT NULL,
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
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE financial_statements IS '上市公司财务报表数据';
COMMENT ON COLUMN financial_statements.ts_code IS '股票代码';
COMMENT ON COLUMN financial_statements.ann_date IS '公告日期';
COMMENT ON COLUMN financial_statements.end_date IS '报告期截止日期';
COMMENT ON COLUMN financial_statements.report_type IS '报告类型：Q1-一季报，S1-半年报，Q3-三季报，A-年报';
COMMENT ON COLUMN financial_statements.comp_type IS '公司类型：1-合并报表，2-母公司';

CREATE INDEX idx_financial_statements_ts_code ON financial_statements(ts_code);
CREATE INDEX idx_financial_statements_end_date ON financial_statements(end_date);
CREATE INDEX idx_financial_statements_ann_date ON financial_statements(ann_date);
CREATE INDEX idx_financial_statements_report_type ON financial_statements(report_type);

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

-- ============================================================
-- 第二部分：TimescaleDB时序表
-- 注意：这些表将转换为超表，支持时序数据处理
-- ============================================================

-- ------------------------------------------------------------
-- 2.1 行情数据时序表
-- ------------------------------------------------------------

-- A股日线行情表（TimescaleDB超表）
CREATE TABLE stock_daily (
    id SERIAL,
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(9,3) NOT NULL,
    high NUMERIC(9,3) NOT NULL,
    low NUMERIC(9,3) NOT NULL,
    close NUMERIC(9,3) NOT NULL,
    pre_close NUMERIC(9,3) NOT NULL,
    change NUMERIC(9,3) NOT NULL,
    pct_chg NUMERIC(7,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(14,4) NOT NULL,
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
    id SERIAL,
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
    id SERIAL,
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
    id SERIAL,
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
    id SERIAL,
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    adj_factor NUMERIC(18,10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_adj_factor IS '股票复权因子数据表（TimescaleDB超表）';
COMMENT ON COLUMN stock_adj_factor.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_adj_factor.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_adj_factor.adj_factor IS '复权因子（高精度数值，用于计算复权价格）';

-- A股复权行情表（TimescaleDB超表）
CREATE TABLE stock_adjusted_prices (
    id SERIAL,
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
    id SERIAL,
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    close NUMERIC(9,4) NOT NULL,
    turnover_rate NUMERIC(8,4) NOT NULL,
    turnover_rate_f NUMERIC(8,4) NOT NULL,
    volume_ratio NUMERIC(8,4) NOT NULL,
    pe NUMERIC(12,4),
    pe_ttm NUMERIC(12,4),
    pb NUMERIC(12,4) NOT NULL,
    ps NUMERIC(12,4),
    ps_ttm NUMERIC(12,4),
    dv_ratio NUMERIC(8,4),
    dv_ttm NUMERIC(8,4),
    total_share NUMERIC(16,4) NOT NULL,
    float_share NUMERIC(16,4) NOT NULL,
    free_share NUMERIC(16,4) NOT NULL,
    total_mv NUMERIC(18,4) NOT NULL,
    circ_mv NUMERIC(18,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

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
    id SERIAL,
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    pre_close NUMERIC(9,4) NOT NULL,
    up_limit NUMERIC(9,4) NOT NULL,
    down_limit NUMERIC(9,4) NOT NULL,
    up_percent NUMERIC(5,2),
    down_percent NUMERIC(5,2),
    price_range NUMERIC(9,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

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
    id SERIAL,
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
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
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
    ts_code VARCHAR(20) NOT NULL REFERENCES etf_basic(ts_code),
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
    id SERIAL,
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
    ts_code VARCHAR(20) NOT NULL REFERENCES index_basic(ts_code),
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

-- ------------------------------------------------------------
-- 2.4 绩效和信号时序表
-- ------------------------------------------------------------

-- 账户每日绩效表（TimescaleDB超表）
CREATE TABLE account_daily_performance (
    id SERIAL,
    user_id INT NOT NULL REFERENCES sys_users(id),
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
    id SERIAL,
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id),
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
    id SERIAL,
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id),
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
    id SERIAL,
    task_id VARCHAR(32) NOT NULL REFERENCES backtest_tasks(id),
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
    id SERIAL,
    rule_id INT NOT NULL REFERENCES risk_rules(id),
    strategy_id VARCHAR(32) REFERENCES strategies(id),
    user_id INT NOT NULL REFERENCES sys_users(id),
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
    id SERIAL,
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
CREATE INDEX idx_stock_daily_ts_code ON stock_daily (ts_code);
CREATE INDEX idx_stock_daily_date ON stock_daily (trade_date DESC);
CREATE INDEX idx_stock_minutes_ts_code ON stock_minutes (ts_code);
CREATE INDEX idx_stock_minutes_time ON stock_minutes (trade_time DESC);
CREATE INDEX idx_stock_minutes_freq ON stock_minutes (freq);
CREATE INDEX idx_stock_moneyflow_ts_code ON stock_moneyflow (ts_code);
CREATE INDEX idx_stock_moneyflow_date ON stock_moneyflow (trade_date DESC);
CREATE INDEX idx_etf_daily_ts_code ON etf_daily (ts_code);
CREATE INDEX idx_etf_daily_date ON etf_daily (trade_date DESC);
CREATE INDEX idx_etf_minute_ts_code ON etf_minute (ts_code);
CREATE INDEX idx_etf_minute_time ON etf_minute (trade_time DESC);
CREATE INDEX idx_etf_minute_freq ON etf_minute (freq);
CREATE INDEX idx_index_daily_ts_code ON index_daily (ts_code);
CREATE INDEX idx_index_daily_date ON index_daily (trade_date DESC);

-- 补充索引
CREATE INDEX idx_account_daily_perf_user_date ON account_daily_performance(user_id, trade_date DESC);
CREATE INDEX idx_strategy_daily_perf_strategy_date ON strategy_daily_performance(strategy_id, trade_date DESC);
CREATE INDEX idx_signals_strategy_time ON signals(strategy_id, signal_time DESC);
CREATE INDEX idx_signals_ts_code ON signals(ts_code);
CREATE INDEX idx_backtest_equity_task_date ON backtest_equity_curves(task_id, trade_date DESC);
CREATE INDEX idx_risk_events_created_at ON risk_events(created_at DESC);
CREATE INDEX idx_risk_events_user_id ON risk_events(user_id);
CREATE INDEX idx_factor_data_factor_code ON factor_data(factor_code);
CREATE INDEX idx_factor_data_ts_code ON factor_data(ts_code);
CREATE INDEX idx_factor_data_date ON factor_data(trade_date DESC);
CREATE INDEX idx_trade_calendar_date ON trade_calendar(cal_date DESC);
CREATE INDEX idx_trade_calendar_exchange ON trade_calendar(exchange);

-- 外键索引（优化关联查询）
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_strategy_id ON orders(strategy_id);
CREATE INDEX idx_orders_account_id ON orders(account_id);
CREATE INDEX idx_trades_order_id ON trades(order_id);
CREATE INDEX idx_positions_user_id ON positions(user_id);
CREATE INDEX idx_positions_account_id ON positions(account_id);
CREATE INDEX idx_strategy_runs_strategy_id ON strategy_runs(strategy_id);
CREATE INDEX idx_backtest_trades_task_id ON backtest_trades(task_id);
CREATE INDEX idx_backtest_positions_task_id ON backtest_positions(task_id);

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

-- ============================================================
-- 第八部分：最终检查和更新
-- ============================================================

-- 更新数据库统计信息（提高查询计划器性能）
ANALYZE;

-- 验证表创建完整性
DO $$
DECLARE
    expected_tables INT := 50; -- 预期的表数量
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