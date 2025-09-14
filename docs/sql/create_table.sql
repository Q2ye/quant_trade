CREATE TABLE stock_basic (
    ts_code VARCHAR(20) PRIMARY KEY,      -- TS唯一代码 (主键)
    symbol VARCHAR(10) NOT NULL,          -- 股票代码
    name VARCHAR(50) NOT NULL,            -- 股票名称
    area VARCHAR(20),                     -- 地域
    industry VARCHAR(30),                 -- 所属行业
    fullname VARCHAR(100),                -- 股票全称
    enname VARCHAR(100),                  -- 英文全称
    cnspell VARCHAR(50),                  -- 拼音缩写
    market VARCHAR(20) NOT NULL,          -- 市场类型 (主板/创业板/科创板/CDR/北交所)
    exchange VARCHAR(10),                 -- 交易所 (SSE/SZSE/BSE)
    curr_type VARCHAR(10),                -- 交易货币
    list_status CHAR(1) DEFAULT 'L',      -- 上市状态 (L上市/D退市/P暂停上市)
    list_date DATE NOT NULL,              -- 上市日期
    delist_date DATE,                     -- 退市日期
    is_hs CHAR(1),                        -- 沪深港通 (N否/H沪股通/S深股通)
    act_name VARCHAR(50),                 -- 实控人名称
    act_ent_type VARCHAR(50),             -- 实控人企业性质

    -- 添加系统管理字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


CREATE TABLE trade_calendar (
    exchange VARCHAR(10) NOT NULL,        -- 交易所代码
    cal_date DATE NOT NULL,               -- 日历日期
    is_open BOOLEAN NOT NULL DEFAULT FALSE, -- 是否交易
    pretrade_date DATE,                   -- 上一个交易日

    -- 元信息字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 联合主键
    PRIMARY KEY (exchange, cal_date)
);

COMMENT ON TABLE trade_calendar IS '交易所交易日历表';
COMMENT ON COLUMN trade_calendar.exchange IS '交易所代码 (SSE:上交所/SZSE:深交所/CFFEX:中金所/SHFE:上期所/CZCE:郑商所/DCE:大商所/INE:上能源)';
COMMENT ON COLUMN trade_calendar.cal_date IS '日历日期';
COMMENT ON COLUMN trade_calendar.is_open IS '是否交易日 (true:交易/false:休市)';
COMMENT ON COLUMN trade_calendar.pretrade_date IS '上一个交易日';


-- 创建索引优化查询性能
CREATE INDEX idx_trade_calendar_cal_date ON trade_calendar(cal_date);
CREATE INDEX idx_trade_calendar_exchange ON trade_calendar(exchange);
CREATE INDEX idx_trade_calendar_is_open ON trade_calendar(is_open);
CREATE INDEX idx_trade_calendar_pretrade ON trade_calendar(pretrade_date);

-- ST股票列表表
CREATE TABLE stock_st_list (
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,        -- 股票代码
    name VARCHAR(50) NOT NULL,           -- 股票名称
    trade_date DATE NOT NULL,            -- 交易日期
    st_type VARCHAR(10) NOT NULL,        -- 类型（ST/*ST等）
    st_type_name VARCHAR(50) NOT NULL,   -- 类型名称
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 唯一约束
    UNIQUE (ts_code, trade_date)
);

COMMENT ON TABLE stock_st_list IS 'ST股票列表历史记录表';
COMMENT ON COLUMN stock_st_list.ts_code IS '股票TS代码';
COMMENT ON COLUMN stock_st_list.name IS '股票名称';
COMMENT ON COLUMN stock_st_list.trade_date IS '交易日期';
COMMENT ON COLUMN stock_st_list.st_type IS 'ST类型（如：ST/*ST/U等）';
COMMENT ON COLUMN stock_st_list.st_type_name IS '类型名称（如：ST特别处理/*ST退市风险警示等）';

-- 创建索引优化查询性能
CREATE INDEX idx_stock_st_list_ts_code ON stock_st_list(ts_code);
CREATE INDEX idx_stock_st_list_trade_date ON stock_st_list(trade_date);
CREATE INDEX idx_stock_st_list_type ON stock_st_list(st_type);

CREATE TABLE stock_company (
    ts_code VARCHAR(20) PRIMARY KEY,        -- 股票代码 (主键)
    com_name VARCHAR(100) NOT NULL,         -- 公司全称
    com_id VARCHAR(30) NOT NULL,            -- 统一社会信用代码
    exchange VARCHAR(10) NOT NULL,          -- 交易所代码 (SSE/SZSE/BSE)
    chairman VARCHAR(50),                   -- 法人代表
    manager VARCHAR(50),                    -- 总经理
    secretary VARCHAR(50),                  -- 董秘
    reg_capital NUMERIC(15, 2) NOT NULL,    -- 注册资本(万元)
    setup_date DATE NOT NULL,               -- 注册日期
    province VARCHAR(20),                   -- 所在省份
    city VARCHAR(20),                       -- 所在城市
    introduction TEXT,                      -- 公司介绍
    website VARCHAR(100),                   -- 公司主页
    email VARCHAR(100),                     -- 电子邮件
    office VARCHAR(200),                    -- 办公室地址
    employees INT,                          -- 员工人数
    main_business TEXT,                     -- 主要业务及产品
    business_scope TEXT,                    -- 经营范围

    -- 系统管理字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

-- 创建索引优化查询性能
CREATE INDEX idx_stock_company_com_name ON stock_company(com_name);
CREATE INDEX idx_stock_company_exchange ON stock_company(exchange);
CREATE INDEX idx_stock_company_province ON stock_company(province);
CREATE INDEX idx_stock_company_city ON stock_company(city);
CREATE INDEX idx_stock_company_setup_date ON stock_company(setup_date);


CREATE TABLE stk_managers (
    id SERIAL PRIMARY KEY,                 -- 自增主键
    ts_code VARCHAR(20) NOT NULL,          -- TS股票代码
    ann_date DATE NOT NULL,                -- 公告日期
    name VARCHAR(50) NOT NULL,             -- 姓名
    gender CHAR(1),                        -- 性别 (M:男/F:女)
    lev VARCHAR(20),                       -- 岗位类别
    title VARCHAR(100) NOT NULL,           -- 岗位
    edu VARCHAR(20),                       -- 学历
    national VARCHAR(20),                  -- 国籍
    birthday DATE,                         -- 出生年月
    begin_date DATE,                       -- 上任日期
    end_date DATE,                         -- 离任日期
    resume TEXT,                           -- 个人简历

    -- 系统管理字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 唯一约束
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

-- 创建索引优化查询性能
CREATE INDEX idx_stk_managers_ts_code ON stk_managers(ts_code);
CREATE INDEX idx_stk_managers_ann_date ON stk_managers(ann_date);
CREATE INDEX idx_stk_managers_name ON stk_managers(name);
CREATE INDEX idx_stk_managers_title ON stk_managers(title);
CREATE INDEX idx_stk_managers_begin_date ON stk_managers(begin_date);
CREATE INDEX idx_stk_managers_end_date ON stk_managers(end_date);


CREATE TABLE stk_rewards (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(20) NOT NULL,  -- TS股票代码
    ann_date DATE NOT NULL,  -- 公告日期
    end_date DATE NOT NULL,  -- 报告截止日期
    name VARCHAR(50) NOT NULL,  -- 管理层姓名
    title VARCHAR(100) NOT NULL,  -- 职务名称
    reward NUMERIC(18, 2) NOT NULL,  -- 年度报酬（单位：元人民币）
    hold_vol BIGINT NOT NULL,  -- 持股数量（单位：股）
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stk_rewards IS '上市公司管理层薪酬与持股明细表';
COMMENT ON COLUMN stk_rewards.ts_code IS 'TS股票代码（e.g. 600000.SH）';
COMMENT ON COLUMN stk_rewards.ann_date IS '公告发布日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stk_rewards.end_date IS '报告期截止日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stk_rewards.name IS '管理层成员姓名';
COMMENT ON COLUMN stk_rewards.title IS '担任职务（e.g. 董事长/财务总监）';
COMMENT ON COLUMN stk_rewards.reward IS '年度税前报酬总额（单位：元）';
COMMENT ON COLUMN stk_rewards.hold_vol IS '期末直接持股数量（单位：股）';
COMMENT ON COLUMN stk_rewards.created_time IS '数据入库时间（自动记录）';
COMMENT ON COLUMN stk_rewards.updated_time IS '数据最后更新时间（自动更新）';

CREATE TABLE stock_daily (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    trade_date DATE NOT NULL,  -- 交易日期
    open NUMERIC(9,3) NOT NULL,  -- 开盘价
    high NUMERIC(9,3) NOT NULL,  -- 最高价
    low NUMERIC(9,3) NOT NULL,  -- 最低价
    close NUMERIC(9,3) NOT NULL,  -- 收盘价
    pre_close NUMERIC(9,3) NOT NULL,  -- 除权昨收价
    change NUMERIC(9,3) NOT NULL,  -- 涨跌额
    pct_chg NUMERIC(7,4) NOT NULL,  -- 涨跌幅（单位：%）
    vol BIGINT NOT NULL,  -- 成交量（单位：手）
    amount NUMERIC(14,4) NOT NULL,  -- 成交额（单位：千元）
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_daily IS 'A股日线行情表（未复权）';
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
COMMENT ON COLUMN stock_daily.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_daily.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_daily ADD CONSTRAINT uniq_stock_date
UNIQUE (ts_code, trade_date);

-- 自动更新时间的触发器函数
CREATE OR REPLACE FUNCTION update_daily_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_daily_update
BEFORE UPDATE ON stock_daily
FOR EACH ROW EXECUTE FUNCTION update_daily_modified();


CREATE TABLE stock_minutes (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    freq VARCHAR(5) NOT NULL CHECK (freq IN ('1min','5min','15min','30min','60min')),  -- 分钟频度
    trade_time TIMESTAMPTZ NOT NULL,  -- 精确到秒的交易时间
    open NUMERIC(9,4) NOT NULL,  -- 开盘价
    high NUMERIC(9,4) NOT NULL,  -- 最高价
    low NUMERIC(9,4) NOT NULL,  -- 最低价
    close NUMERIC(9,4) NOT NULL,  -- 收盘价
    vol BIGINT NOT NULL,  -- 成交量（单位：手）
    amount NUMERIC(16,4) NOT NULL,  -- 成交金额（单位：元）
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据入库时间
);

COMMENT ON TABLE stock_minutes IS 'A股分钟级行情数据';
COMMENT ON COLUMN stock_minutes.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_minutes.freq IS 'K线频度（1min/5min/15min/30min/60min）';
COMMENT ON COLUMN stock_minutes.trade_time IS '精确交易时间（含日期和时分秒）';
COMMENT ON COLUMN stock_minutes.open IS '分钟周期开盘价';
COMMENT ON COLUMN stock_minutes.high IS '分钟周期最高价';
COMMENT ON COLUMN stock_minutes.low IS '分钟周期最低价';
COMMENT ON COLUMN stock_minutes.close IS '分钟周期收盘价';
COMMENT ON COLUMN stock_minutes.vol IS '成交量（单位：手，1手=100股）';
COMMENT ON COLUMN stock_minutes.amount IS '成交金额（单位：元人民币）';
COMMENT ON COLUMN stock_minutes.created_time IS '数据入库时间（自动记录）';

-- 添加唯一约束防止重复数据
ALTER TABLE stock_minutes ADD CONSTRAINT uniq_minute_bar
UNIQUE (ts_code, freq, trade_time);

-- -- 分区表建议（按年月水平分区）
-- CREATE TABLE stock_minutes_2023 PARTITION OF stock_minutes
-- FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
--
-- -- 自动维护分区函数（示例）
-- CREATE OR REPLACE FUNCTION create_minutes_partition()
-- RETURNS TRIGGER AS $$
-- DECLARE
--     partition_text TEXT;
-- BEGIN
--     partition_text := format(
--         'CREATE TABLE IF NOT EXISTS stock_minutes_%s PARTITION OF stock_minutes FOR VALUES FROM (%L) TO (%L)',
--         to_char(NEW.trade_time, 'YYYY'),
--         date_trunc('year', NEW.trade_time),
--         date_trunc('year', NEW.trade_time) + interval '1 year'
--     );
--     EXECUTE partition_text;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;


CREATE TABLE stock_weekly (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    trade_date DATE NOT NULL,  -- 周线结束日期（每周最后一个交易日）
    open NUMERIC(9,4) NOT NULL,  -- 周开盘价
    high NUMERIC(9,4) NOT NULL,  -- 周最高价
    low NUMERIC(9,4) NOT NULL,  -- 周最低价
    close NUMERIC(9,4) NOT NULL,  -- 周收盘价
    pre_close NUMERIC(9,4) NOT NULL,  -- 上周收盘价
    change NUMERIC(9,4) NOT NULL,  -- 周涨跌额（close - pre_close）
    pct_chg NUMERIC(8,4) NOT NULL,  -- 周涨跌幅（百分比）
    vol BIGINT NOT NULL,  -- 周成交量（单位：手）
    amount NUMERIC(16,4) NOT NULL,  -- 周成交额（单位：元）
    week_start DATE,  -- 周开始日期（周一）
    week_end DATE,  -- 周结束日期（周五）
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_weekly IS 'A股周线行情数据表';
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
COMMENT ON COLUMN stock_weekly.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_weekly.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_weekly ADD CONSTRAINT uniq_weekly_stock
UNIQUE (ts_code, trade_date);

-- 自动填充周开始/结束日期的函数
CREATE OR REPLACE FUNCTION set_week_dates()
RETURNS TRIGGER AS $$
BEGIN
    NEW.week_start = DATE_TRUNC('week', NEW.trade_date)::DATE;
    NEW.week_end = (DATE_TRUNC('week', NEW.trade_date) + INTERVAL '6 days')::DATE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器自动设置周日期
CREATE TRIGGER trg_set_week_dates
BEFORE INSERT OR UPDATE ON stock_weekly
FOR EACH ROW EXECUTE FUNCTION set_week_dates();

-- 自动更新时间触发器
CREATE OR REPLACE FUNCTION update_weekly_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_weekly_update
BEFORE UPDATE ON stock_weekly
FOR EACH ROW EXECUTE FUNCTION update_weekly_modified();


CREATE TABLE stock_monthly (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    trade_date DATE NOT NULL,  -- 月线结束日期（每月最后一个交易日）
    open NUMERIC(9,4) NOT NULL,  -- 月开盘价
    high NUMERIC(9,4) NOT NULL,  -- 月最高价
    low NUMERIC(9,4) NOT NULL,  -- 月最低价
    close NUMERIC(9,4) NOT NULL,  -- 月收盘价
    pre_close NUMERIC(9,4) NOT NULL,  -- 上月收盘价
    change NUMERIC(9,4) NOT NULL,  -- 月涨跌额（close - pre_close）
    pct_chg NUMERIC(8,4) NOT NULL,  -- 月涨跌幅（百分比）
    vol BIGINT NOT NULL,  -- 月成交量（单位：手）
    amount NUMERIC(16,4) NOT NULL,  -- 月成交额（单位：元）
    month_start DATE,  -- 月开始日期（当月第一个交易日）
    month_end DATE,  -- 月结束日期（当月最后一个交易日）
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_monthly IS 'A股月线行情数据表';
COMMENT ON COLUMN stock_monthly.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_monthly.trade_date IS '月线交易日（每月最后一个交易日）';
COMMENT ON COLUMN stock_monthly.open IS '当月第一个交易日开盘价';
COMMENT ON COLUMN stock_monthly.high IS '当月最高价';
COMMENT ON COLUMN stock_monthly.low IS '当月最低价';
COMMENT ON COLUMN stock_monthly.close IS '当月最后一个交易日收盘价（未复权）';
COMMENT ON COLUMN stock_monthly.pre_close IS '上月收盘价（用于计算涨跌幅）';
COMMENT ON COLUMN stock_monthly.change IS '月涨跌额（计算公式：close - pre_close）';
COMMENT ON COLUMN stock_monthly.pct_chg IS '月涨跌幅百分比（计算公式：(close-pre_close)/pre_close）';
COMMENT ON COLUMN stock_monthly.vol IS '月成交量（单位：手，1手=100股）';
COMMENT ON COLUMN stock_monthly.amount IS '月成交额（单位：元人民币）';
COMMENT ON COLUMN stock_monthly.month_start IS '月开始日期（当月第一个交易日）';
COMMENT ON COLUMN stock_monthly.month_end IS '月结束日期（当月最后一个交易日）';
COMMENT ON COLUMN stock_monthly.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_monthly.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_monthly ADD CONSTRAINT uniq_monthly_stock
UNIQUE (ts_code, trade_date);

-- 自动填充月开始/结束日期的函数
CREATE OR REPLACE FUNCTION set_month_dates()
RETURNS TRIGGER AS $$
BEGIN
    NEW.month_start = DATE_TRUNC('month', NEW.trade_date)::DATE;
    NEW.month_end = (DATE_TRUNC('month', NEW.trade_date) + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器自动设置月份日期
CREATE TRIGGER trg_set_month_dates
BEFORE INSERT OR UPDATE ON stock_monthly
FOR EACH ROW EXECUTE FUNCTION set_month_dates();

-- 自动更新时间触发器
CREATE OR REPLACE FUNCTION update_monthly_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_monthly_update
BEFORE UPDATE ON stock_monthly
FOR EACH ROW EXECUTE FUNCTION update_monthly_modified();

CREATE TABLE stock_adjusted_prices (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    trade_date DATE NOT NULL,  -- 交易日期
    asset_type CHAR(1) NOT NULL DEFAULT 'E' CHECK (asset_type IN ('E','I','C','FT','FD','O')),  -- 资产类别
    adj_type VARCHAR(3) CHECK (adj_type IN (NULL, 'qfq', 'hfq')),  -- 复权类型
    freq VARCHAR(4) NOT NULL DEFAULT 'D' CHECK (freq IN ('D','1MIN','5MIN','15MIN','30MIN','60MIN')),  -- 数据频度
    open NUMERIC(9,4) NOT NULL,  -- 开盘价
    high NUMERIC(9,4) NOT NULL,  -- 最高价
    low NUMERIC(9,4) NOT NULL,  -- 最低价
    close NUMERIC(9,4) NOT NULL,  -- 收盘价
    pre_close NUMERIC(9,4) NOT NULL,  -- 昨收价
    change NUMERIC(9,4) NOT NULL,  -- 涨跌额
    pct_chg NUMERIC(8,4) NOT NULL,  -- 涨跌幅
    vol BIGINT NOT NULL,  -- 成交量（单位：手）
    amount NUMERIC(16,4) NOT NULL,  -- 成交额（单位：千元）
    ma_values JSONB,  -- 均线数据（存储不同周期的均线值）
    adj_factor NUMERIC(18,10) NOT NULL,  -- 复权因子（精确存储）
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_adjusted_prices IS 'A股复权行情数据表';
COMMENT ON COLUMN stock_adjusted_prices.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_adjusted_prices.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_adjusted_prices.asset_type IS '资产类别：E股票/I沪深指数/C数字货币/FT期货/FD基金/O期权';
COMMENT ON COLUMN stock_adjusted_prices.adj_type IS '复权类型：qfq(前复权)/hfq(后复权)/NULL(不复权)';
COMMENT ON COLUMN stock_adjusted_prices.freq IS '数据频度：D(日线)/1MIN(1分钟)/5MIN(5分钟)/15MIN(15分钟)/30MIN(30分钟)/60MIN(60分钟)';
COMMENT ON COLUMN stock_adjusted_prices.open IS '开盘价（根据复权类型调整后）';
COMMENT ON COLUMN stock_adjusted_prices.high IS '最高价（根据复权类型调整后）';
COMMENT ON COLUMN stock_adjusted_prices.low IS '最低价（根据复权类型调整后）';
COMMENT ON COLUMN stock_adjusted_prices.close IS '收盘价（根据复权类型调整后）';
COMMENT ON COLUMN stock_adjusted_prices.pre_close IS '昨收价（根据复权类型调整后）';
COMMENT ON COLUMN stock_adjusted_prices.change IS '涨跌额（根据复权类型计算）';
COMMENT ON COLUMN stock_adjusted_prices.pct_chg IS '涨跌幅百分比（根据复权类型计算）';
COMMENT ON COLUMN stock_adjusted_prices.vol IS '成交量（单位：手，1手=100股）';
COMMENT ON COLUMN stock_adjusted_prices.amount IS '成交额（单位：千元人民币）';
COMMENT ON COLUMN stock_adjusted_prices.ma_values IS '均线数据（JSON格式，如{"ma5":12.34, "ma10":12.56}）';
COMMENT ON COLUMN stock_adjusted_prices.adj_factor IS '复权因子（精确值，用于动态计算）';
COMMENT ON COLUMN stock_adjusted_prices.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_adjusted_prices.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_adjusted_prices ADD CONSTRAINT uniq_adjusted_price
UNIQUE (ts_code, trade_date, adj_type, freq);

-- 自动更新时间触发器
CREATE OR REPLACE FUNCTION update_adjusted_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_adjusted_update
BEFORE UPDATE ON stock_adjusted_prices
FOR EACH ROW EXECUTE FUNCTION update_adjusted_modified();


CREATE TABLE stock_adj_factor (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    trade_date DATE NOT NULL,  -- 交易日期
    adj_factor NUMERIC(18,10) NOT NULL,  -- 精确复权因子
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_adj_factor IS '股票复权因子数据表';
COMMENT ON COLUMN stock_adj_factor.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_adj_factor.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_adj_factor.adj_factor IS '复权因子（高精度数值，用于计算复权价格）';
COMMENT ON COLUMN stock_adj_factor.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_adj_factor.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_adj_factor ADD CONSTRAINT uniq_adj_factor
UNIQUE (ts_code, trade_date);

-- 自动更新时间触发器
CREATE OR REPLACE FUNCTION update_adj_factor_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_adj_factor_update
BEFORE UPDATE ON stock_adj_factor
FOR EACH ROW EXECUTE FUNCTION update_adj_factor_modified();


CREATE TABLE stock_daily_basic (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    trade_date DATE NOT NULL,  -- 交易日期
    close NUMERIC(9,4) NOT NULL,  -- 当日收盘价
    turnover_rate NUMERIC(8,4) NOT NULL,  -- 换手率（%）
    turnover_rate_f NUMERIC(8,4) NOT NULL,  -- 换手率（自由流通股）（%）
    volume_ratio NUMERIC(8,4) NOT NULL,  -- 量比
    pe NUMERIC(12,4),  -- 市盈率（总市值/净利润）
    pe_ttm NUMERIC(12,4),  -- 市盈率（TTM）
    pb NUMERIC(12,4) NOT NULL,  -- 市净率（总市值/净资产）
    ps NUMERIC(12,4),  -- 市销率
    ps_ttm NUMERIC(12,4),  -- 市销率（TTM）
    dv_ratio NUMERIC(8,4),  -- 股息率（%）
    dv_ttm NUMERIC(8,4),  -- 股息率（TTM）（%）
    total_share NUMERIC(16,4) NOT NULL,  -- 总股本（万股）
    float_share NUMERIC(16,4) NOT NULL,  -- 流通股本（万股）
    free_share NUMERIC(16,4) NOT NULL,  -- 自由流通股本（万股）
    total_mv NUMERIC(18,4) NOT NULL,  -- 总市值（万元）
    circ_mv NUMERIC(18,4) NOT NULL,  -- 流通市值（万元）
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_daily_basic IS '股票每日基本面指标数据表';
COMMENT ON COLUMN stock_daily_basic.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_daily_basic.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_daily_basic.close IS '当日收盘价（元）';
COMMENT ON COLUMN stock_daily_basic.turnover_rate IS '换手率（%），计算公式：当日成交量/流通总股数×100%';
COMMENT ON COLUMN stock_daily_basic.turnover_rate_f IS '换手率（自由流通股）（%），基于自由流通股本计算';
COMMENT ON COLUMN stock_daily_basic.volume_ratio IS '量比，当日成交量/过去5日平均成交量';
COMMENT ON COLUMN stock_daily_basic.pe IS '市盈率（总市值/净利润），亏损企业为空';
COMMENT ON COLUMN stock_daily_basic.pe_ttm IS '市盈率（TTM，最近12个月），亏损企业为空';
COMMENT ON COLUMN stock_daily_basic.pb IS '市净率（总市值/净资产）';
COMMENT ON COLUMN stock_daily_basic.ps IS '市销率（总市值/营业收入）';
COMMENT ON COLUMN stock_daily_basic.ps_ttm IS '市销率（TTM，最近12个月）';
COMMENT ON COLUMN stock_daily_basic.dv_ratio IS '股息率（%），年度现金分红/总市值×100%';
COMMENT ON COLUMN stock_daily_basic.dv_ttm IS '股息率（TTM）（%），最近12个月现金分红/总市值×100%';
COMMENT ON COLUMN stock_daily_basic.total_share IS '总股本（单位：万股）';
COMMENT ON COLUMN stock_daily_basic.float_share IS '流通股本（单位：万股）';
COMMENT ON COLUMN stock_daily_basic.free_share IS '自由流通股本（单位：万股）';
COMMENT ON COLUMN stock_daily_basic.total_mv IS '总市值（单位：万元）';
COMMENT ON COLUMN stock_daily_basic.circ_mv IS '流通市值（单位：万元）';
COMMENT ON COLUMN stock_daily_basic.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_daily_basic.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_daily_basic ADD CONSTRAINT uniq_daily_basic
UNIQUE (ts_code, trade_date);

-- 自动更新时间触发器
CREATE OR REPLACE FUNCTION update_daily_basic_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_daily_basic_update
BEFORE UPDATE ON stock_daily_basic
FOR EACH ROW EXECUTE FUNCTION update_daily_basic_modified();


CREATE TABLE stock_daily_limit (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码（格式：600000.SH）
    trade_date DATE NOT NULL,  -- 交易日期
    pre_close NUMERIC(9,4) NOT NULL,  -- 昨日收盘价
    up_limit NUMERIC(9,4) NOT NULL,  -- 涨停价
    down_limit NUMERIC(9,4) NOT NULL,  -- 跌停价
    up_percent NUMERIC(5,2) GENERATED ALWAYS AS (ROUND((up_limit / pre_close - 1) * 100, 2)) STORED,  -- 涨停幅度（%）
    down_percent NUMERIC(5,2) GENERATED ALWAYS AS (ROUND((down_limit / pre_close - 1) * 100, 2)) STORED,  -- 跌停幅度（%）
    price_range NUMERIC(9,4) GENERATED ALWAYS AS (up_limit - down_limit) STORED,  -- 当日价格区间
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_daily_limit IS '股票每日涨跌停价格表';
COMMENT ON COLUMN stock_daily_limit.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_daily_limit.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_daily_limit.pre_close IS '昨日收盘价（元）';
COMMENT ON COLUMN stock_daily_limit.up_limit IS '涨停价格（元）';
COMMENT ON COLUMN stock_daily_limit.down_limit IS '跌停价格（元）';
COMMENT ON COLUMN stock_daily_limit.up_percent IS '涨停幅度（%）';
COMMENT ON COLUMN stock_daily_limit.down_percent IS '跌停幅度（%）';
COMMENT ON COLUMN stock_daily_limit.price_range IS '当日价格区间（涨停价-跌停价）';
COMMENT ON COLUMN stock_daily_limit.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_daily_limit.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_daily_limit ADD CONSTRAINT uniq_daily_limit
UNIQUE (ts_code, trade_date);

-- 自动更新时间触发器
CREATE OR REPLACE FUNCTION update_daily_limit_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_daily_limit_update
BEFORE UPDATE ON stock_daily_limit
FOR EACH ROW EXECUTE FUNCTION update_daily_limit_modified();


CREATE TABLE stock_income_core (
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(12) NOT NULL,
    ann_date DATE NOT NULL,
    f_ann_date DATE,
    end_date DATE NOT NULL,
    report_type VARCHAR(10) NOT NULL,
    comp_type CHAR(1) NOT NULL CHECK (comp_type IN ('1','2','3','4')),
    end_type CHAR(1),
    update_flag CHAR(1),
    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 核心利润指标
    total_revenue NUMERIC(20,4),
    revenue NUMERIC(20,4),
    total_cogs NUMERIC(20,4),
    operate_profit NUMERIC(20,4),
    total_profit NUMERIC(20,4),
    n_income NUMERIC(20,4),
    n_income_attr_p NUMERIC(20,4),
    basic_eps NUMERIC(20,4),
    diluted_eps NUMERIC(20,4),

    -- 外键约束
    CONSTRAINT fk_income_core UNIQUE (ts_code, end_date, report_type)
);

COMMENT ON TABLE stock_income_core IS '利润表核心信息表';
COMMENT ON COLUMN stock_income_core.id IS '主键ID';
COMMENT ON COLUMN stock_income_core.ts_code IS 'TS股票代码';
COMMENT ON COLUMN stock_income_core.ann_date IS '公告日期';
COMMENT ON COLUMN stock_income_core.f_ann_date IS '实际公告日期';
COMMENT ON COLUMN stock_income_core.end_date IS '报告期(季度最后一天)';
COMMENT ON COLUMN stock_income_core.report_type IS '报告类型:1合并报表 2单季合并 3调整单季合并表 4调整合并报表 5调整前合并报表 6母公司报表 7母公司单季表 8母公司调整单季表 9母公司调整表 10母公司调整前报表 11调整前合并报表 12母公司调整前报表';
COMMENT ON COLUMN stock_income_core.comp_type IS '公司类型:1一般工商业 2银行 3保险 4证券';
COMMENT ON COLUMN stock_income_core.end_type IS '报告期类型:1报告期 2第一季度 3中期报告 4第三季度 5年度报告';
COMMENT ON COLUMN stock_income_core.update_flag IS '更新标识:0未修改 1更正过';
COMMENT ON COLUMN stock_income_core.created_time IS '数据创建时间';
COMMENT ON COLUMN stock_income_core.updated_time IS '数据更新时间';
COMMENT ON COLUMN stock_income_core.total_revenue IS '营业总收入';
COMMENT ON COLUMN stock_income_core.revenue IS '营业收入';
COMMENT ON COLUMN stock_income_core.total_cogs IS '营业总成本';
COMMENT ON COLUMN stock_income_core.operate_profit IS '营业利润';
COMMENT ON COLUMN stock_income_core.total_profit IS '利润总额';
COMMENT ON COLUMN stock_income_core.n_income IS '净利润(含少数股东损益)';
COMMENT ON COLUMN stock_income_core.n_income_attr_p IS '净利润(不含少数股东损益)';
COMMENT ON COLUMN stock_income_core.basic_eps IS '基本每股收益';
COMMENT ON COLUMN stock_income_core.diluted_eps IS '稀释每股收益';


CREATE TABLE stock_income_revenue (
    id SERIAL PRIMARY KEY,
    core_id INT NOT NULL REFERENCES stock_income_core(id),

    -- 收入类明细
    int_income NUMERIC(20,4),
    prem_earned NUMERIC(20,4),
    comm_income NUMERIC(20,4),
    n_commis_income NUMERIC(20,4),
    n_oth_income NUMERIC(20,4),
    n_oth_b_income NUMERIC(20,4),
    prem_income NUMERIC(20,4),
    out_prem NUMERIC(20,4),
    une_prem_reser NUMERIC(20,4),
    reins_income NUMERIC(20,4),
    n_sec_tb_income NUMERIC(20,4),
    n_sec_uw_income NUMERIC(20,4),
    n_asset_mg_income NUMERIC(20,4),
    oth_b_income NUMERIC(20,4),

    -- 收益类
    fv_value_chg_gain NUMERIC(20,4),
    invest_income NUMERIC(20,4),
    ass_invest_income NUMERIC(20,4),
    forex_gain NUMERIC(20,4),

    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_income_revenue IS '利润表收入明细表';
COMMENT ON COLUMN stock_income_revenue.id IS '主键ID';
COMMENT ON COLUMN stock_income_revenue.core_id IS '关联核心表ID';
COMMENT ON COLUMN stock_income_revenue.int_income IS '利息收入';
COMMENT ON COLUMN stock_income_revenue.prem_earned IS '已赚保费';
COMMENT ON COLUMN stock_income_revenue.comm_income IS '手续费及佣金收入';
COMMENT ON COLUMN stock_income_revenue.n_commis_income IS '手续费及佣金净收入';
COMMENT ON COLUMN stock_income_revenue.n_oth_income IS '其他经营净收益';
COMMENT ON COLUMN stock_income_revenue.n_oth_b_income IS '加:其他业务净收益';
COMMENT ON COLUMN stock_income_revenue.prem_income IS '保险业务收入';
COMMENT ON COLUMN stock_income_revenue.out_prem IS '减:分出保费';
COMMENT ON COLUMN stock_income_revenue.une_prem_reser IS '提取未到期责任准备金';
COMMENT ON COLUMN stock_income_revenue.reins_income IS '其中:分保费收入';
COMMENT ON COLUMN stock_income_revenue.n_sec_tb_income IS '代理买卖证券业务净收入';
COMMENT ON COLUMN stock_income_revenue.n_sec_uw_income IS '证券承销业务净收入';
COMMENT ON COLUMN stock_income_revenue.n_asset_mg_income IS '受托客户资产管理业务净收入';
COMMENT ON COLUMN stock_income_revenue.oth_b_income IS '其他业务收入';
COMMENT ON COLUMN stock_income_revenue.fv_value_chg_gain IS '加:公允价值变动净收益';
COMMENT ON COLUMN stock_income_revenue.invest_income IS '加:投资净收益';
COMMENT ON COLUMN stock_income_revenue.ass_invest_income IS '其中:对联营企业和合营企业的投资收益';
COMMENT ON COLUMN stock_income_revenue.forex_gain IS '加:汇兑净收益';
COMMENT ON COLUMN stock_income_revenue.created_time IS '数据创建时间';
COMMENT ON COLUMN stock_income_revenue.updated_time IS '数据更新时间';


CREATE TABLE stock_income_expenses (
    id SERIAL PRIMARY KEY,
    core_id INT NOT NULL REFERENCES stock_income_core(id),

    -- 成本费用类明细
    oper_cost NUMERIC(20,4),                   -- 减:营业成本
    int_exp NUMERIC(20,4),                     -- 减:利息支出
    comm_exp NUMERIC(20,4),                    -- 减:手续费及佣金支出
    biz_tax_surchg NUMERIC(20,4),              -- 减:营业税金及附加
    sell_exp NUMERIC(20,4),                    -- 减:销售费用
    admin_exp NUMERIC(20,4),                   -- 减:管理费用
    fin_exp NUMERIC(20,4),                     -- 减:财务费用
    assets_impair_loss NUMERIC(20,4),          -- 减:资产减值损失
    prem_refund NUMERIC(20,4),                 -- 退保金
    compens_payout NUMERIC(20,4),              -- 赔付总支出
    reser_insur_liab NUMERIC(20,4),            -- 提取保险责任准备金
    div_payt NUMERIC(20,4),                    -- 保户红利支出
    reins_exp NUMERIC(20,4),                   -- 分保费用
    oper_exp NUMERIC(20,4),                    -- 营业支出
    compens_payout_refu NUMERIC(20,4),         -- 减:摊回赔付支出
    insur_reser_refu NUMERIC(20,4),            -- 减:摊回保险责任准备金
    reins_cost_refund NUMERIC(20,4),           -- 减:摊回分保费用
    other_bus_cost NUMERIC(20,4),              -- 其他业务成本
    rd_exp NUMERIC(20,4),                      -- 研发费用
    non_oper_income NUMERIC(20,4),             -- 加:营业外收入
    non_oper_exp NUMERIC(20,4),                -- 减:营业外支出
    nca_disploss NUMERIC(20,4),                -- 其中:减:非流动资产处置净损失
    income_tax NUMERIC(20,4),                  -- 所得税费用

    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_income_expenses IS '利润表成本费用表';
COMMENT ON COLUMN stock_income_expenses.id IS '主键ID';
COMMENT ON COLUMN stock_income_expenses.core_id IS '关联核心表ID';
COMMENT ON COLUMN stock_income_expenses.oper_cost IS '减:营业成本';
COMMENT ON COLUMN stock_income_expenses.int_exp IS '减:利息支出';
COMMENT ON COLUMN stock_income_expenses.comm_exp IS '减:手续费及佣金支出';
COMMENT ON COLUMN stock_income_expenses.biz_tax_surchg IS '减:营业税金及附加';
COMMENT ON COLUMN stock_income_expenses.sell_exp IS '减:销售费用';
COMMENT ON COLUMN stock_income_expenses.admin_exp IS '减:管理费用';
COMMENT ON COLUMN stock_income_expenses.fin_exp IS '减:财务费用';
COMMENT ON COLUMN stock_income_expenses.assets_impair_loss IS '减:资产减值损失';
COMMENT ON COLUMN stock_income_expenses.prem_refund IS '退保金';
COMMENT ON COLUMN stock_income_expenses.compens_payout IS '赔付总支出';
COMMENT ON COLUMN stock_income_expenses.reser_insur_liab IS '提取保险责任准备金';
COMMENT ON COLUMN stock_income_expenses.div_payt IS '保户红利支出';
COMMENT ON COLUMN stock_income_expenses.reins_exp IS '分保费用';
COMMENT ON COLUMN stock_income_expenses.oper_exp IS '营业支出';
COMMENT ON COLUMN stock_income_expenses.compens_payout_refu IS '减:摊回赔付支出';
COMMENT ON COLUMN stock_income_expenses.insur_reser_refu IS '减:摊回保险责任准备金';
COMMENT ON COLUMN stock_income_expenses.reins_cost_refund IS '减:摊回分保费用';
COMMENT ON COLUMN stock_income_expenses.other_bus_cost IS '其他业务成本';
COMMENT ON COLUMN stock_income_expenses.rd_exp IS '研发费用';
COMMENT ON COLUMN stock_income_expenses.non_oper_income IS '加:营业外收入';
COMMENT ON COLUMN stock_income_expenses.non_oper_exp IS '减:营业外支出';
COMMENT ON COLUMN stock_income_expenses.nca_disploss IS '其中:减:非流动资产处置净损失';
COMMENT ON COLUMN stock_income_expenses.income_tax IS '所得税费用';
COMMENT ON COLUMN stock_income_expenses.created_time IS '数据创建时间';
COMMENT ON COLUMN stock_income_expenses.updated_time IS '数据更新时间';

-- 创建索引优化查询性能 (可根据实际查询模式调整)
CREATE INDEX idx_stock_income_expenses_core_id ON stock_income_expenses(core_id);


CREATE TABLE stock_income_distribution (
    id SERIAL PRIMARY KEY,
    core_id INT NOT NULL REFERENCES stock_income_core(id),

    -- 综合收益
    oth_compr_income NUMERIC(20,4),
    t_compr_income NUMERIC(20,4),
    compr_inc_attr_p NUMERIC(20,4),
    compr_inc_attr_m_s NUMERIC(20,4),

    -- 分配相关
    undist_profit NUMERIC(20,4),
    distable_profit NUMERIC(20,4),
    transfer_surplus_rese NUMERIC(20,4),
    transfer_housing_imprest NUMERIC(20,4),
    transfer_oth NUMERIC(20,4),
    adj_lossgain NUMERIC(20,4),
    withdra_legal_surplus NUMERIC(20,4),
    withdra_legal_pubfund NUMERIC(20,4),
    withdra_biz_devfund NUMERIC(20,4),
    withdra_rese_fund NUMERIC(20,4),
    withdra_oth_ersu NUMERIC(20,4),
    workers_welfare NUMERIC(20,4),
    distr_profit_shrhder NUMERIC(20,4),
    prfshare_payable_dvd NUMERIC(20,4),
    comshare_payable_dvd NUMERIC(20,4),
    capit_comstock_div NUMERIC(20,4),

    -- 其他财务指标
    ebit NUMERIC(20,4),
    ebitda NUMERIC(20,4),
    insurance_exp NUMERIC(20,4),
    fin_exp_int_exp NUMERIC(20,4),
    fin_exp_int_inc NUMERIC(20,4),

    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_income_distribution IS '利润分配与综合收益表';
COMMENT ON COLUMN stock_income_distribution.id IS '主键ID';
COMMENT ON COLUMN stock_income_distribution.core_id IS '关联核心表ID';
COMMENT ON COLUMN stock_income_distribution.oth_compr_income IS '其他综合收益';
COMMENT ON COLUMN stock_income_distribution.t_compr_income IS '综合收益总额';
COMMENT ON COLUMN stock_income_distribution.compr_inc_attr_p IS '归属于母公司(或股东)的综合收益总额';
COMMENT ON COLUMN stock_income_distribution.compr_inc_attr_m_s IS '归属于少数股东的综合收益总额';
COMMENT ON COLUMN stock_income_distribution.undist_profit IS '年初未分配利润';
COMMENT ON COLUMN stock_income_distribution.distable_profit IS '可分配利润';
COMMENT ON COLUMN stock_income_distribution.transfer_surplus_rese IS '盈余公积转入';
COMMENT ON COLUMN stock_income_distribution.transfer_housing_imprest IS '住房周转金转入';
COMMENT ON COLUMN stock_income_distribution.transfer_oth IS '其他转入';
COMMENT ON COLUMN stock_income_distribution.adj_lossgain IS '调整以前年度损益';
COMMENT ON COLUMN stock_income_distribution.withdra_legal_surplus IS '提取法定盈余公积';
COMMENT ON COLUMN stock_income_distribution.withdra_legal_pubfund IS '提取法定公益金';
COMMENT ON COLUMN stock_income_distribution.withdra_biz_devfund IS '提取企业发展基金';
COMMENT ON COLUMN stock_income_distribution.withdra_rese_fund IS '提取储备基金';
COMMENT ON COLUMN stock_income_distribution.withdra_oth_ersu IS '提取任意盈余公积金';
COMMENT ON COLUMN stock_income_distribution.workers_welfare IS '职工奖金福利';
COMMENT ON COLUMN stock_income_distribution.distr_profit_shrhder IS '可供股东分配的利润';
COMMENT ON COLUMN stock_income_distribution.prfshare_payable_dvd IS '应付优先股股利';
COMMENT ON COLUMN stock_income_distribution.comshare_payable_dvd IS '应付普通股股利';
COMMENT ON COLUMN stock_income_distribution.capit_comstock_div IS '转作股本的普通股股利';
COMMENT ON COLUMN stock_income_distribution.ebit IS '息税前利润';
COMMENT ON COLUMN stock_income_distribution.ebitda IS '息税折旧摊销前利润';
COMMENT ON COLUMN stock_income_distribution.insurance_exp IS '保险业务支出';
COMMENT ON COLUMN stock_income_distribution.fin_exp_int_exp IS '财务费用:利息费用';
COMMENT ON COLUMN stock_income_distribution.fin_exp_int_inc IS '财务费用:利息收入';
COMMENT ON COLUMN stock_income_distribution.created_time IS '数据创建时间';
COMMENT ON COLUMN stock_income_distribution.updated_time IS '数据更新时间';



CREATE TABLE stock_income_correction (
    id SERIAL PRIMARY KEY,
    core_id INT NOT NULL REFERENCES stock_income_core(id),

    -- 更正与减值
    net_after_nr_lp_correct NUMERIC(20,4),
    credit_impa_loss NUMERIC(20,4),
    net_expo_hedging_benefits NUMERIC(20,4),
    oth_impair_loss_assets NUMERIC(20,4),
    total_opcost NUMERIC(20,4),
    amodcost_fin_assets NUMERIC(20,4),
    oth_income NUMERIC(20,4),
    asset_disp_income NUMERIC(20,4),
    continued_net_profit NUMERIC(20,4),
    end_net_profit NUMERIC(20,4),
    minority_gain NUMERIC(20,4),

    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_income_correction IS '利润表更正与减值表';
COMMENT ON COLUMN stock_income_correction.id IS '主键ID';
COMMENT ON COLUMN stock_income_correction.core_id IS '关联核心表ID';
COMMENT ON COLUMN stock_income_correction.net_after_nr_lp_correct IS '扣除非经常性损益后的净利润（更正前）';
COMMENT ON COLUMN stock_income_correction.credit_impa_loss IS '信用减值损失';
COMMENT ON COLUMN stock_income_correction.net_expo_hedging_benefits IS '净敞口套期收益';
COMMENT ON COLUMN stock_income_correction.oth_impair_loss_assets IS '其他资产减值损失';
COMMENT ON COLUMN stock_income_correction.total_opcost IS '营业总成本（二）';
COMMENT ON COLUMN stock_income_correction.amodcost_fin_assets IS '以摊余成本计量的金融资产终止确认收益';
COMMENT ON COLUMN stock_income_correction.oth_income IS '其他收益';
COMMENT ON COLUMN stock_income_correction.asset_disp_income IS '资产处置收益';
COMMENT ON COLUMN stock_income_correction.continued_net_profit IS '持续经营净利润';
COMMENT ON COLUMN stock_income_correction.end_net_profit IS '终止经营净利润';
COMMENT ON COLUMN stock_income_correction.minority_gain IS '少数股东损益';
COMMENT ON COLUMN stock_income_correction.created_time IS '数据创建时间';
COMMENT ON COLUMN stock_income_correction.updated_time IS '数据更新时间';



CREATE TABLE stock_moneyflow (
    id SERIAL PRIMARY KEY,  -- 主键ID（自增唯一标识）
    ts_code VARCHAR(12) NOT NULL,  -- 股票代码
    trade_date DATE NOT NULL,  -- 交易日期
    buy_sm_vol INT NOT NULL,  -- 小单买入量（手）
    buy_sm_amount NUMERIC(12,4) NOT NULL,  -- 小单买入金额（万元）
    sell_sm_vol INT NOT NULL,  -- 小单卖出量（手）
    sell_sm_amount NUMERIC(12,4) NOT NULL,  -- 小单卖出金额（万元）
    buy_md_vol INT NOT NULL,  -- 中单买入量（手）
    buy_md_amount NUMERIC(12,4) NOT NULL,  -- 中单买入金额（万元）
    sell_md_vol INT NOT NULL,  -- 中单卖出量（手）
    sell_md_amount NUMERIC(12,4) NOT NULL,  -- 中单卖出金额（万元）
    buy_lg_vol INT NOT NULL,  -- 大单买入量（手）
    buy_lg_amount NUMERIC(12,4) NOT NULL,  -- 大单买入金额（万元）
    sell_lg_vol INT NOT NULL,  -- 大单卖出量（手）
    sell_lg_amount NUMERIC(12,4) NOT NULL,  -- 大单卖出金额（万元）
    buy_elg_vol INT NOT NULL,  -- 特大单买入量（手）
    buy_elg_amount NUMERIC(12,4) NOT NULL,  -- 特大单买入金额（万元）
    sell_elg_vol INT NOT NULL,  -- 特大单卖出量（手）
    sell_elg_amount NUMERIC(12,4) NOT NULL,  -- 特大单卖出金额（万元）
    net_mf_vol INT NOT NULL,  -- 净流入量（手）
    net_mf_amount NUMERIC(12,4) NOT NULL,  -- 净流入额（万元）

    -- 计算字段
    total_vol INT GENERATED ALWAYS AS (buy_sm_vol + buy_md_vol + buy_lg_vol + buy_elg_vol) STORED,  -- 总成交量（手）
    buy_ratio NUMERIC(8,4) GENERATED ALWAYS AS (
        CASE WHEN (buy_sm_vol + buy_md_vol + buy_lg_vol + buy_elg_vol + sell_sm_vol + sell_md_vol + sell_lg_vol + sell_elg_vol) > 0
        THEN (buy_sm_vol + buy_md_vol + buy_lg_vol + buy_elg_vol)::NUMERIC /
             (buy_sm_vol + buy_md_vol + buy_lg_vol + buy_elg_vol + sell_sm_vol + sell_md_vol + sell_lg_vol + sell_elg_vol) * 100
        ELSE 0 END
    ) STORED,  -- 买入占比（%）
    large_net_ratio NUMERIC(8,4) GENERATED ALWAYS AS (
        CASE WHEN (buy_lg_amount + buy_elg_amount + sell_lg_amount + sell_elg_amount) > 0
        THEN (buy_lg_amount + buy_elg_amount - sell_lg_amount - sell_elg_amount) /
             (buy_lg_amount + buy_elg_amount + sell_lg_amount + sell_elg_amount) * 100
        ELSE 0 END
    ) STORED,  -- 大单净流入占比（%）

    created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 数据创建时间
    updated_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 数据更新时间
);

COMMENT ON TABLE stock_moneyflow IS '个股资金流向数据表';
COMMENT ON COLUMN stock_moneyflow.ts_code IS '股票TS代码（含交易所后缀）';
COMMENT ON COLUMN stock_moneyflow.trade_date IS '交易日期（格式：YYYYMMDD）';
COMMENT ON COLUMN stock_moneyflow.buy_sm_vol IS '小单买入量（单位：手，1手=100股），成交额<5万元';
COMMENT ON COLUMN stock_moneyflow.buy_sm_amount IS '小单买入金额（单位：万元人民币），成交额<5万元';
COMMENT ON COLUMN stock_moneyflow.sell_sm_vol IS '小单卖出量（单位：手），成交额<5万元';
COMMENT ON COLUMN stock_moneyflow.sell_sm_amount IS '小单卖出金额（单位：万元），成交额<5万元';
COMMENT ON COLUMN stock_moneyflow.buy_md_vol IS '中单买入量（单位：手），5万元≤成交额<20万元';
COMMENT ON COLUMN stock_moneyflow.buy_md_amount IS '中单买入金额（单位：万元），5万元≤成交额<20万元';
COMMENT ON COLUMN stock_moneyflow.sell_md_vol IS '中单卖出量（单位：手），5万元≤成交额<20万元';
COMMENT ON COLUMN stock_moneyflow.sell_md_amount IS '中单卖出金额（单位：万元），5万元≤成交额<20万元';
COMMENT ON COLUMN stock_moneyflow.buy_lg_vol IS '大单买入量（单位：手），20万元≤成交额<100万元';
COMMENT ON COLUMN stock_moneyflow.buy_lg_amount IS '大单买入金额（单位：万元），20万元≤成交额<100万元';
COMMENT ON COLUMN stock_moneyflow.sell_lg_vol IS '大单卖出量（单位：手），20万元≤成交额<100万元';
COMMENT ON COLUMN stock_moneyflow.sell_lg_amount IS '大单卖出金额（单位：万元），20万元≤成交额<100万元';
COMMENT ON COLUMN stock_moneyflow.buy_elg_vol IS '特大单买入量（单位：手），成交额≥100万元';
COMMENT ON COLUMN stock_moneyflow.buy_elg_amount IS '特大单买入金额（单位：万元），成交额≥100万元';
COMMENT ON COLUMN stock_moneyflow.sell_elg_vol IS '特大单卖出量（单位：手），成交额≥100万元';
COMMENT ON COLUMN stock_moneyflow.sell_elg_amount IS '特大单卖出金额（单位：万元），成交额≥100万元';
COMMENT ON COLUMN stock_moneyflow.net_mf_vol IS '净流入量（单位：手），计算公式：(特大单买入+大单买入+中单买入+小单买入) - (特大单卖出+大单卖出+中单卖出+小单卖出)';
COMMENT ON COLUMN stock_moneyflow.net_mf_amount IS '净流入额（单位：万元），计算公式：(特大单买入金额+大单买入金额+中单买入金额+小单买入金额) - (特大单卖出金额+大单卖出金额+中单卖出金额+小单卖出金额)';
COMMENT ON COLUMN stock_moneyflow.total_vol IS '总成交量（单位：手），所有类型买卖量之和';
COMMENT ON COLUMN stock_moneyflow.buy_ratio IS '买入占比（%），买入量占总成交量的比例';
COMMENT ON COLUMN stock_moneyflow.large_net_ratio IS '大单净流入占比（%），(大单+特大单)净流入额占(大单+特大单)总成交额的比例';
COMMENT ON COLUMN stock_moneyflow.created_time IS '数据首次入库时间';
COMMENT ON COLUMN stock_moneyflow.updated_time IS '数据最后更新时间';

-- 添加唯一约束（防止重复数据）
ALTER TABLE stock_moneyflow ADD CONSTRAINT uniq_moneyflow
UNIQUE (ts_code, trade_date);

-- 自动更新时间触发器
CREATE OR REPLACE FUNCTION update_moneyflow_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_moneyflow_update
BEFORE UPDATE ON stock_moneyflow
FOR EACH ROW EXECUTE FUNCTION update_moneyflow_modified();


CREATE TABLE etf_basic (
    ts_code VARCHAR(20) PRIMARY KEY NOT NULL,
    csname VARCHAR(100) NOT NULL,
    extname VARCHAR(200) NOT NULL,
    cname VARCHAR(200) NOT NULL,
    index_code VARCHAR(20),
    index_name VARCHAR(200),
    setup_date CHAR(8) NOT NULL,
    list_date CHAR(8),
    list_status CHAR(1) NOT NULL,
    exchange CHAR(2) NOT NULL,
    mgr_name VARCHAR(100) NOT NULL,
    custod_name VARCHAR(100) NOT NULL,
    mgt_fee REAL,
    etf_type VARCHAR(10) NOT NULL
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

CREATE TABLE etf_index (
    ts_code VARCHAR(20) PRIMARY KEY NOT NULL,
    indx_name VARCHAR(200) NOT NULL,
    indx_csname VARCHAR(100) NOT NULL,
    pub_party_name VARCHAR(200) NOT NULL,
    pub_date CHAR(8) NOT NULL,
    base_date CHAR(8) NOT NULL,
    bp REAL NOT NULL,
    adj_circle VARCHAR(50) NOT NULL
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


CREATE TABLE etf_minute (
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    freq VARCHAR(10) NOT NULL,
    trade_time TIMESTAMP NOT NULL,
    open NUMERIC(10,4) NOT NULL,
    close NUMERIC(10,4) NOT NULL,
    high NUMERIC(10,4) NOT NULL,
    low NUMERIC(10,4) NOT NULL,
    vol BIGINT NOT NULL,
    amount NUMERIC(16,4) NOT NULL,
    UNIQUE (ts_code, freq, trade_time)
);


CREATE INDEX idx_etf_minute_ts_code ON etf_minute(ts_code);
CREATE INDEX idx_etf_minute_trade_time ON etf_minute(trade_time);
CREATE INDEX idx_etf_minute_freq ON etf_minute(freq);


COMMENT ON TABLE etf_minute IS 'ETF历史分钟行情数据';

COMMENT ON COLUMN etf_minute.id IS '自增主键ID';
COMMENT ON COLUMN etf_minute.ts_code IS 'ETF交易代码（带交易所后缀）';
COMMENT ON COLUMN etf_minute.freq IS '分钟频度（1min/5min/15min/30min/60min）';
COMMENT ON COLUMN etf_minute.trade_time IS '交易时间（精确到分钟）';
COMMENT ON COLUMN etf_minute.open IS '开盘价';
COMMENT ON COLUMN etf_minute.close IS '收盘价';
COMMENT ON COLUMN etf_minute.high IS '最高价';
COMMENT ON COLUMN etf_minute.low IS '最低价';
COMMENT ON COLUMN etf_minute.vol IS '成交量（股数）';
COMMENT ON COLUMN etf_minute.amount IS '成交金额（元）';


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
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_etf_daily_trade_date ON etf_daily(trade_date);
CREATE INDEX idx_etf_daily_ts_code_trade_date ON etf_daily(ts_code, trade_date DESC);

COMMENT ON TABLE etf_daily IS 'ETF日线行情数据';

COMMENT ON COLUMN etf_daily.ts_code IS 'ETF交易代码（带交易所后缀）';
COMMENT ON COLUMN etf_daily.trade_date IS '交易日期（YYYYMMDD格式）';
COMMENT ON COLUMN etf_daily.open IS '开盘价（元）';
COMMENT ON COLUMN etf_daily.high IS '最高价（元）';
COMMENT ON COLUMN etf_daily.low IS '最低价（元）';
COMMENT ON COLUMN etf_daily.close IS '收盘价（元）';
COMMENT ON COLUMN etf_daily.pre_close IS '昨收盘价（元）';
COMMENT ON COLUMN etf_daily.change IS '涨跌额（元）';
COMMENT ON COLUMN etf_daily.pct_chg IS '涨跌幅（%）';
COMMENT ON COLUMN etf_daily.vol IS '成交量（手）';
COMMENT ON COLUMN etf_daily.amount IS '成交额（千元）';


CREATE TABLE fund_adj_factor (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    adj_factor NUMERIC(16,8) NOT NULL,
    PRIMARY KEY (ts_code, trade_date)
);
CREATE INDEX idx_fund_adj_factor_date ON fund_adj_factor(trade_date);
CREATE INDEX idx_fund_adj_factor_ts_code ON fund_adj_factor(ts_code);

COMMENT ON TABLE fund_adj_factor IS '基金复权因子数据';

COMMENT ON COLUMN fund_adj_factor.ts_code IS '基金交易代码（带交易所后缀）';
COMMENT ON COLUMN fund_adj_factor.trade_date IS '交易日期（YYYYMMDD格式）';
COMMENT ON COLUMN fund_adj_factor.adj_factor IS '复权因子（高精度小数）';



CREATE TABLE sys_users (
    id SERIAL PRIMARY KEY,  -- 用户ID（自增主键）
    username VARCHAR(50) NOT NULL UNIQUE,  -- 用户名（唯一）
    password_hash VARCHAR(100) NOT NULL,  -- 密码哈希值
    email VARCHAR(100) NOT NULL UNIQUE,  -- 邮箱
    phone VARCHAR(20),  -- 手机号
    real_name VARCHAR(50),  -- 真实姓名
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'guest')),  -- 用户角色
    is_active BOOLEAN DEFAULT TRUE,  -- 是否激活
    last_login TIMESTAMPTZ,  -- 最后登录时间
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

COMMENT ON TABLE sys_users IS '系统用户信息表';
COMMENT ON COLUMN sys_users.id IS '用户ID（自增主键）';
COMMENT ON COLUMN sys_users.username IS '用户名（唯一）';
COMMENT ON COLUMN sys_users.password_hash IS '密码哈希值（BCrypt加密）';
COMMENT ON COLUMN sys_users.email IS '用户邮箱（唯一）';
COMMENT ON COLUMN sys_users.phone IS '手机号码';
COMMENT ON COLUMN sys_users.real_name IS '用户真实姓名';
COMMENT ON COLUMN sys_users.role IS '用户角色：admin-管理员, user-普通用户, guest-访客';
COMMENT ON COLUMN sys_users.is_active IS '账户是否激活';
COMMENT ON COLUMN sys_users.last_login IS '最后登录时间';
COMMENT ON COLUMN sys_users.created_at IS '账户创建时间';
COMMENT ON COLUMN sys_users.updated_at IS '账户信息最后更新时间';

CREATE TABLE sys_permissions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id) ON DELETE CASCADE,
    module VARCHAR(50) NOT NULL,  -- 模块名：strategy, basket, trading, etc.
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


CREATE TABLE strategies (
    id VARCHAR(32) PRIMARY KEY,  -- 策略ID（UUID或雪花ID）
    name VARCHAR(100) NOT NULL,  -- 策略名称
    user_id INT NOT NULL REFERENCES sys_users(id),  -- 创建者ID
    description TEXT,  -- 策略描述
    class_name VARCHAR(100) NOT NULL,  -- 策略类名
    module_path VARCHAR(200) NOT NULL,  -- 策略文件路径
    status VARCHAR(20) DEFAULT 'stopped' CHECK (status IN ('running', 'stopped', 'error')),  -- 运行状态
    parameters JSONB NOT NULL DEFAULT '{}'::JSONB,  -- 策略参数（JSON格式）
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


CREATE TABLE strategy_runs (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,  -- 开始时间
    stopped_at TIMESTAMPTZ,  -- 结束时间
    status VARCHAR(20) NOT NULL,  -- 最终状态
    log_path TEXT,  -- 日志文件路径
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE strategy_runs IS '策略运行历史记录表';
COMMENT ON COLUMN strategy_runs.strategy_id IS '外键，关联策略ID';
COMMENT ON COLUMN strategy_runs.started_at IS '策略启动时间';
COMMENT ON COLUMN strategy_runs.stopped_at IS '策略停止时间';
COMMENT ON COLUMN strategy_runs.status IS '运行结果状态：completed, stopped, error';
COMMENT ON COLUMN strategy_runs.log_path IS '本次运行日志文件存储路径';


CREATE TABLE orders (
    order_id VARCHAR(32) PRIMARY KEY,  -- 订单ID（平台生成）
    user_id INT NOT NULL REFERENCES sys_users(id),
    strategy_id VARCHAR(32) REFERENCES strategies(id),  -- 可能为空（手动交易）
    ts_code VARCHAR(12) NOT NULL,  -- 标的代码
    order_type VARCHAR(10) NOT NULL CHECK (order_type IN ('limit', 'market', 'stop')),  -- 订单类型
    direction VARCHAR(4) NOT NULL CHECK (direction IN ('buy', 'sell')),  -- 买卖方向
    price NUMERIC(10, 4),  -- 委托价格（市价单可为空）
    volume INT NOT NULL,  -- 委托数量（股）
    status VARCHAR(20) DEFAULT 'submitted' CHECK (status IN ('submitted', 'partial_filled', 'filled', 'cancelled', 'rejected')),  -- 订单状态
    submitted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 提交时间
    cancelled_at TIMESTAMPTZ,  -- 撤单时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE orders IS '委托订单表';
COMMENT ON COLUMN orders.order_id IS '订单唯一ID（平台内部生成）';
COMMENT ON COLUMN orders.user_id IS '下单用户ID';
COMMENT ON COLUMN orders.strategy_id IS '关联策略ID（若为策略下单）';
COMMENT ON COLUMN orders.ts_code IS '股票代码';
COMMENT ON COLUMN orders.order_type IS '订单类型：limit-限价单, market-市价单, stop-止损单';
COMMENT ON COLUMN orders.direction IS '交易方向：buy-买入, sell-卖出';
COMMENT ON COLUMN orders.price IS '委托价格（对于市价单，此字段为NULL）';
COMMENT ON COLUMN orders.volume IS '委托数量（单位：股）';
COMMENT ON COLUMN orders.status IS '订单状态：submitted-已报, partial_filled-部成, filled-已成, cancelled-已撤, rejected-废单';
COMMENT ON COLUMN orders.submitted_at IS '订单提交时间';
COMMENT ON COLUMN orders.cancelled_at IS '订单撤销时间（如果被撤销）';


CREATE TABLE trades (
    trade_id VARCHAR(32) PRIMARY KEY,  -- 成交ID（券商或平台生成）
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    ts_code VARCHAR(12) NOT NULL,
    price NUMERIC(10, 4) NOT NULL,  -- 成交价格
    volume INT NOT NULL,  -- 成交数量
    trade_time TIMESTAMPTZ NOT NULL,  -- 成交时间
    commission NUMERIC(10, 4) NOT NULL,  -- 佣金费用
    tax NUMERIC(10, 4) NOT NULL,  -- 印花税
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


CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id),
    ts_code VARCHAR(12) NOT NULL,
    volume INT NOT NULL DEFAULT 0,  -- 当前持仓数量
    available_volume INT NOT NULL DEFAULT 0,  -- 可用数量（T+1限制）
    cost_price NUMERIC(10, 4) NOT NULL,  -- 持仓成本价
    market_value NUMERIC(16, 4) NOT NULL DEFAULT 0,  -- 当前市值
    last_update TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, ts_code)
);

COMMENT ON TABLE positions IS '用户持仓表';
COMMENT ON COLUMN positions.user_id IS '用户ID';
COMMENT ON COLUMN positions.ts_code IS '股票代码';
COMMENT ON COLUMN positions.volume IS '持仓总数量';
COMMENT ON COLUMN positions.available_volume IS '可用数量（考虑T+1交易制度）';
COMMENT ON COLUMN positions.cost_price IS '平均持仓成本价';
COMMENT ON COLUMN positions.market_value IS '当前市值（动态更新）';
COMMENT ON COLUMN positions.last_update IS '最后更新时间';


-- 创建交易篮子表
CREATE TABLE baskets (
    id VARCHAR NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- 主键约束
    CONSTRAINT baskets_pkey PRIMARY KEY (id)
);

COMMENT ON TABLE baskets IS '交易篮子表';
COMMENT ON COLUMN baskets.id IS '篮子唯一标识符';
COMMENT ON COLUMN baskets.name IS '篮子名称';
COMMENT ON COLUMN baskets.description IS '篮子描述信息';
COMMENT ON COLUMN baskets.created_at IS '记录创建时间';
COMMENT ON COLUMN baskets.updated_at IS '记录最后更新时间';


-- 创建篮子成分表
CREATE TABLE basket_items (
    id SERIAL,
    basket_id VARCHAR NOT NULL,
    ts_code VARCHAR(12) NOT NULL,
    weight FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- 主键约束
    CONSTRAINT basket_items_pkey PRIMARY KEY (id),
    -- 外键约束
    CONSTRAINT basket_items_basket_id_fkey FOREIGN KEY (basket_id)
        REFERENCES baskets (id) ON DELETE CASCADE,
    CONSTRAINT basket_items_ts_code_fkey FOREIGN KEY (ts_code)
        REFERENCES stock_basic (ts_code) ON DELETE CASCADE
);

COMMENT ON TABLE basket_items IS '篮子成分表';
COMMENT ON COLUMN basket_items.id IS '成分项唯一标识符';
COMMENT ON COLUMN basket_items.basket_id IS '关联篮子ID';
COMMENT ON COLUMN basket_items.ts_code IS '股票代码';
COMMENT ON COLUMN basket_items.weight IS '成分在篮子中的权重';
COMMENT ON COLUMN basket_items.created_at IS '记录创建时间';

-- 创建索引优化查询性能
CREATE INDEX idx_basket_items_basket_id ON basket_items (basket_id);
CREATE INDEX idx_basket_items_ts_code ON basket_items (ts_code);


CREATE TABLE risk_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,  -- 规则名称
    rule_type VARCHAR(50) NOT NULL,  -- 规则类型：position_limit, daily_loss_limit, etc.
    condition JSONB NOT NULL,  -- 规则条件（JSON格式）
    action VARCHAR(50) NOT NULL,  -- 触发动作：alert, stop_strategy, etc.
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


CREATE TABLE risk_events (
    id SERIAL PRIMARY KEY,
    rule_id INT NOT NULL REFERENCES risk_rules(id),
    strategy_id VARCHAR(32) REFERENCES strategies(id),
    user_id INT NOT NULL REFERENCES sys_users(id),
    event_type VARCHAR(50) NOT NULL,
    event_message TEXT NOT NULL,
    trigger_value JSONB NOT NULL,  -- 触发时的数据快照
    action_taken VARCHAR(50),  -- 已执行的动作
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE risk_events IS '风控事件触发日志表';
COMMENT ON COLUMN risk_events.rule_id IS '触发的风控规则ID';
COMMENT ON COLUMN risk_events.strategy_id IS '关联策略ID（若为策略触发）';
COMMENT ON COLUMN risk_events.user_id IS '关联用户ID';
COMMENT ON COLUMN risk_events.event_type IS '事件类型（与rule_type对应）';
COMMENT ON COLUMN risk_events.event_message IS '事件描述信息';
COMMENT ON COLUMN risk_events.trigger_value IS '触发时的关键数据（JSON格式，便于复盘）';
COMMENT ON COLUMN risk_events.action_taken IS '系统执行的动作';
COMMENT ON COLUMN risk_events.created_at IS '事件发生时间';


CREATE TABLE account_daily_performance (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES sys_users(id),
    trade_date DATE NOT NULL,  -- 交易日
    total_asset NUMERIC(16, 4) NOT NULL,  -- 总资产
    cash NUMERIC(16, 4) NOT NULL,  -- 现金
    market_value NUMERIC(16, 4) NOT NULL,  -- 股票市值
    daily_pnl NUMERIC(16, 4) NOT NULL,  -- 当日盈亏
    daily_return NUMERIC(10, 6) NOT NULL,  -- 当日收益率
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, trade_date)
);

COMMENT ON TABLE account_daily_performance IS '账户每日绩效快照表';
COMMENT ON COLUMN account_daily_performance.user_id IS '用户ID';
COMMENT ON COLUMN account_daily_performance.trade_date IS '交易日';
COMMENT ON COLUMN account_daily_performance.total_asset IS '总资产（现金 + 股票市值）';
COMMENT ON COLUMN account_daily_performance.cash IS '现金余额';
COMMENT ON COLUMN account_daily_performance.market_value IS '持仓股票总市值';
COMMENT ON COLUMN account_daily_performance.daily_pnl IS '当日盈亏金额';
COMMENT ON COLUMN account_daily_performance.daily_return IS '当日收益率';


CREATE TABLE strategy_daily_performance (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id),
    trade_date DATE NOT NULL,
    daily_return NUMERIC(10, 6) NOT NULL,
    total_return NUMERIC(10, 6) NOT NULL,  -- 累计收益率
    max_drawdown NUMERIC(10, 6) NOT NULL,  -- 最大回撤
    sharpe_ratio NUMERIC(10, 6),  -- 夏普比率
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (strategy_id, trade_date)
);

COMMENT ON TABLE strategy_daily_performance IS '策略每日绩效指标表';
COMMENT ON COLUMN strategy_daily_performance.strategy_id IS '策略ID';
COMMENT ON COLUMN strategy_daily_performance.trade_date IS '交易日';
COMMENT ON COLUMN strategy_daily_performance.daily_return IS '策略当日收益率';
COMMENT ON COLUMN strategy_daily_performance.total_return IS '策略累计收益率（从开始至今）';
COMMENT ON COLUMN strategy_daily_performance.max_drawdown IS '策略最大回撤（截至该日）';
COMMENT ON COLUMN strategy_daily_performance.sharpe_ratio IS '夏普比率（年化）';


CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id),
    ts_code VARCHAR(12) NOT NULL,
    signal_type VARCHAR(10) NOT NULL CHECK (signal_type IN ('buy', 'sell', 'hold')),  -- 信号类型
    signal_time TIMESTAMPTZ NOT NULL,  -- 信号产生时间
    price NUMERIC(10, 4),  -- 信号触发价格
    strength NUMERIC(5, 2),  -- 信号强度（0-1）
    reason TEXT,  -- 信号产生原因
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE signals IS '策略交易信号记录表';
COMMENT ON COLUMN signals.strategy_id IS '产生信号的策略ID';
COMMENT ON COLUMN signals.ts_code IS '股票代码';
COMMENT ON COLUMN signals.signal_type IS '信号类型：buy-买入, sell-卖出, hold-持有';
COMMENT ON COLUMN signals.signal_time IS '信号产生时间（对应K线时间）';
COMMENT ON COLUMN signals.price IS '信号触发时的价格';
COMMENT ON COLUMN signals.strength IS '信号强度（0.00~1.00）';
COMMENT ON COLUMN signals.reason IS '信号产生原因（如：金叉、超卖、因子触发等）';


CREATE TABLE data_sync_tasks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,  -- 任务类型：daily, minute, financial, etc.
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    total_records INT DEFAULT 0,  -- 同步记录数
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE data_sync_tasks IS '数据同步任务记录表';
COMMENT ON COLUMN data_sync_tasks.task_type IS '任务类型：daily-日线, minute-分钟线, financial-财务数据, etc.';
COMMENT ON COLUMN data_sync_tasks.status IS '任务状态：pending-等待中, running-执行中, completed-成功, failed-失败';
COMMENT ON COLUMN data_sync_tasks.start_time IS '任务开始时间';
COMMENT ON COLUMN data_sync_tasks.end_time IS '任务结束时间';
COMMENT ON COLUMN data_sync_tasks.total_records IS '同步数据记录数';
COMMENT ON COLUMN data_sync_tasks.error_message IS '错误信息（如果任务失败）';


-- 回测任务表
CREATE TABLE backtest_tasks (
    id VARCHAR(32) PRIMARY KEY,           -- 任务ID（UUID）
    user_id INT NOT NULL REFERENCES sys_users(id), -- 用户ID
    strategy_id VARCHAR(32) NOT NULL REFERENCES strategies(id), -- 策略ID
    name VARCHAR(100) NOT NULL,           -- 回测名称
    description TEXT,                     -- 回测描述
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    config JSONB NOT NULL DEFAULT '{}'::JSONB, -- 回测配置（时间范围、初始资金、标的等）
    progress FLOAT DEFAULT 0,             -- 进度（0-100）
    result JSONB,                         -- 回测结果（汇总指标）
    error_message TEXT,                   -- 错误信息
    started_at TIMESTAMPTZ,               -- 开始时间
    completed_at TIMESTAMPTZ,             -- 完成时间
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


-- 回测净值曲线表
CREATE TABLE backtest_equity_curves (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(32) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,              -- 交易日
    equity NUMERIC(16, 4) NOT NULL,        -- 当日净值
    cash NUMERIC(16, 4) NOT NULL,          -- 现金
    market_value NUMERIC(16, 4) NOT NULL,  -- 持仓市值
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (task_id, trade_date)
);

COMMENT ON TABLE backtest_equity_curves IS '回测净值曲线表';
COMMENT ON COLUMN backtest_equity_curves.task_id IS '关联的回测任务ID';
COMMENT ON COLUMN backtest_equity_curves.trade_date IS '交易日';
COMMENT ON COLUMN backtest_equity_curves.equity IS '当日总净值';
COMMENT ON COLUMN backtest_equity_curves.cash IS '现金余额';
COMMENT ON COLUMN backtest_equity_curves.market_value IS '持仓市值';



-- 回测交易记录表
CREATE TABLE backtest_trades (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(32) NOT NULL REFERENCES backtest_tasks(id) ON DELETE CASCADE,
    trade_time TIMESTAMPTZ NOT NULL,       -- 交易时间
    ts_code VARCHAR(12) NOT NULL,          -- 标的代码
    direction VARCHAR(4) NOT NULL CHECK (direction IN ('buy', 'sell')), -- 买卖方向
    price NUMERIC(10, 4) NOT NULL,         -- 成交价格
    volume INT NOT NULL,                   -- 成交数量
    value NUMERIC(16, 4) NOT NULL,         -- 成交金额
    commission NUMERIC(10, 4) NOT NULL,    -- 佣金
    tax NUMERIC(10, 4) NOT NULL,           -- 税费
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
    trade_date DATE NOT NULL,              -- 交易日
    ts_code VARCHAR(12) NOT NULL,          -- 标的代码
    volume INT NOT NULL DEFAULT 0,         -- 持仓数量
    cost_price NUMERIC(10, 4) NOT NULL,    -- 成本价
    market_value NUMERIC(16, 4) NOT NULL,  -- 市值
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