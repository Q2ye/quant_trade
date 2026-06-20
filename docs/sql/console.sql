SELECT
    schemaname AS 模式,
    tablename  AS 表名,
    pg_size_pretty(pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(tablename))) AS 物理大小
FROM pg_tables
WHERE schemaname NOT IN (
    'pg_catalog', 'information_schema',
    '_timescaledb_catalog', '_timescaledb_internal'   -- 关键排除
)
  AND pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(tablename)) > 0
ORDER BY pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(tablename)) DESC;

SELECT id, task_id, status, start_time FROM data_sync_tasks WHERE status = 'running';

----------------------------------------------
--需要同步的数据表--------
-- 股票基础表
select * from stock_basic;
select count(*) from stock_basic;
-- A股日线行情表（TimescaleDB超表）
select * from  stock_daily;
select count(*) from stock_daily;
delete from stock_daily;
-- 月线行情表（TimescaleDB超表）
select * from stock_monthly;
select count(*) from stock_monthly;
-- 周线行情表（TimescaleDB超表）
select * from stock_weekly;
select count(*) from stock_weekly;
-- ST股票列表表
select * from stock_st_list;
select count(*) from stock_st_list;

-- 指数基本信息表
select * from index_basic;
select count(*) from index_basic;
-- 指数日线行情数据（TimescaleDB超表）
select * from index_daily;
select count(*) from index_daily;

-- 指数成分股权重表
select * from index_weight;
select count(*) from index_weight;
-- 复权因子表（TimescaleDB超表）
select * from stock_adj_factor where ts_code='000030.SZ';
select count(*) from stock_adj_factor;
delete from stock_adj_factor;
-- 交易日历史表
select * from trade_calendar;
select count(*) from trade_calendar;

-- ETF基础信息表
select * from etf_basic where ts_code like '159227%';
select count(*) from etf_basic;
delete from etf_basic;
-- ETF份额数据表
select * from  etf_shares;
select count(*) from  etf_shares;
-- ETF日线行情表（TimescaleDB超表）
select * from  etf_daily;
select count(*) from  etf_daily;
-- ETF复权因子（TimescaleDB超表）
select * from  fund_adj_factor;
select count(*) from  fund_adj_factor;

-- 指数技术因子专业版
select * from  index_factor_pro_daily;
select count(*) from  index_factor_pro_daily;
-- 每日涨跌停价格表（TimescaleDB超表）
select * from  stock_daily_limit;
select count(*) from  stock_daily_limit;

-- 每日指标表（TimescaleDB超表）
select * from stock_daily_basic;
select count(*) from stock_daily_basic;
delete from stock_daily_basic;
-- 个股资金流向表
select * from stock_moneyflow;
select count(*) from stock_moneyflow;
delete from stock_moneyflow;
-- 加唯一约束
ALTER TABLE stock_moneyflow
ADD CONSTRAINT uq_stock_moneyflow_code_date UNIQUE (ts_code, trade_date);
-- 财务报表主表 利润表 现金流量表
-- 财务报表主表
select * from  financial_statements;
select count(*) from financial_statements;
-- 业绩预告数据表
select * from  stock_forecasts;
select count(*) from  stock_forecasts;
-- 业绩快报数据表
select * from  stock_expresses;
select count(*) from  stock_expresses;
-- 分红送股数据表
select * from  stock_dividends;
select count(*) from  stock_dividends;
-- 财务指标数据表
select * from  stock_fina_indicators;
select count(*) from  stock_fina_indicators;

-- 审计意见数据表
select * from stock_audit_opinions;
select count(*) from stock_audit_opinions;

-- CPI 居民消费价格指数
select * from macro_cpi;
select count(*) from macro_cpi;

-- PPI 工业生产者出厂价格指数
select * from macro_ppi;
select count(*) from macro_ppi;

-- GDP 国内生产总值
select * from macro_gdp;
select count(*) from macro_gdp;

-- 主营业务构成数据表
select * from  stock_business_incomes;
select count(*) from  stock_business_incomes;
-- 业绩预告数据表
select * from  stock_forecasts;
select count(*) from  stock_forecasts;
-- 业绩快报数据表
select * from  stock_expresses;
select count(*) from  stock_expresses;

-- 上市公司管理层表
select * from  stk_managers;
select count(*) from  stk_managers;
-- 上市公司管理层薪酬和持股信息
select * from  stk_rewards;
select count(*) from  stk_rewards;

-- 沪深港通股票列表
select * from  stock_hsgt;
select count(*) from  stock_hsgt;
-- ST风险警示板股票
select * from  stock_st_risk;
select count(*) from  stock_st_risk;
-- 财报披露日期
select * from  financial_disclosure_dates;
select count(*) from  financial_disclosure_dates;
-- 限售股解禁
select * from  stock_share_float;
select count(*) from  stock_share_float;
-- 前十大流通股东
select * from  stock_top10_float_holders;
select count(*) from  stock_top10_float_holders;
-- 前十大股东
select * from  stock_top10_holders;
select count(*) from  stock_top10_holders;

-- 因子定义表
select * from factor_definitions;

-- 股票技术因子基础版表（~33列，不复权指标）
select * from  stock_factor_daily;
select count(*) from  stock_factor_daily;
-- 股票技术因子专业版表（200+列，含三复权版本的所有技术指标）
select * from  stock_factor_pro_daily;
    select count(*) from  stock_factor_pro_daily;
-- 回测任务
select * from backtest_tasks;
-- 回测参数
select * from backtest_parameters;
select * from backtest_result;

-- 因子
select * from factor_definitions;
-- 策略实例表
select * from strategies;
-- 策略版本管理表
select * from strategy_versions;
-- 策略运行记录表
select * from strategy_runs;
-- 策略参数配置表
select * from strategy_parameters;
--
-- 同步任务表
select * from data_sync_tasks where id = 'fb91ee7a-d0a7-4a58-9e87-280a6e4ea730';
-- 用户
select * from sys_users;



ALTER TABLE data_sync_tasks DROP CONSTRAINT IF EXISTS data_sync_tasks_status_check;

ALTER TABLE data_sync_tasks ADD CONSTRAINT data_sync_tasks_status_check
CHECK (status = ANY (ARRAY['pending', 'running', 'completed', 'failed', 'cancelled']));

SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint WHERE conname = 'data_sync_tasks_status_check';
-- 数据质量检查记录表
select * from data_quality_checks where id='63270bf1-2d49-484d-8e82-cf34e6360d3a';



drop table stk_managers



INSERT INTO factor_definitions (id, factor_code, factor_name, factor_type, category, description, formula, parameters, data_requirements, output_type, calculation_frequency, is_public, is_active) VALUES

-- ==================== 趋势类 ====================
('f0010000-0000-0000-0000-000000000001', 'ma_5',    '5日均线',        'technical', '趋势', '5日简单移动平均线', 'SMA(close, 5)', '{"window": 5}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000002', 'ma_20',   '20日均线',       'technical', '趋势', '20日简单移动平均线', 'SMA(close, 20)', '{"window": 20}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000003', 'ema_12',  '12日指数均线',    'technical', '趋势', '12日指数移动平均线', 'EMA(close, 12)', '{"window": 12}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000004', 'ema_26',  '26日指数均线',    'technical', '趋势', '26日指数移动平均线', 'EMA(close, 26)', '{"window": 26}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 动量类 ====================
('f0010000-0000-0000-0000-000000000005', 'macd',    'MACD',           'technical', '动量', 'MACD指标（12/26/9）', 'EMA(close,12)-EMA(close,26)', '{"fast": 12, "slow": 26, "signal": 9}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000006', 'rsi_14',  'RSI(14)',        'technical', '动量', '14日相对强弱指标', 'RSI(close, 14)', '{"window": 14}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000007', 'momentum_1m',  '1月动量',    'technical', '动量', '近1个月价格收益率', '(close - close_21d) / close_21d', '{"window": 21}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000008', 'momentum_3m',  '3月动量',    'technical', '动量', '近3个月价格收益率', '(close - close_63d) / close_63d', '{"window": 63}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000009', 'momentum_6m',  '6月动量',    'technical', '动量', '近6个月价格收益率', '(close - close_126d) / close_126d', '{"window": 126}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 波动率类 ====================
('f0010000-0000-0000-0000-000000000010', 'volatility_1m', '1月波动率',  'technical', '风险', '近1个月日收益率标准差(年化)', 'std(daily_return, 21) * sqrt(252)', '{"window": 21}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000011', 'volatility_3m', '3月波动率',  'technical', '风险', '近3个月日收益率标准差(年化)', 'std(daily_return, 63) * sqrt(252)', '{"window": 63}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000012', 'boll_width', '布林带宽度',     'technical', '风险', '布林带宽度 (upper-lower)/mid', '(boll_upper - boll_lower) / boll_mid', '{"window": 20, "std": 2}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 成交量类 ====================
('f0010000-0000-0000-0000-000000000013', 'volume_ratio_5d',  '5日量比', 'technical', '情绪', '5日均成交量与20日均成交量比值', 'MA(vol,5) / MA(vol,20)', '{"short": 5, "long": 20}', '{"required": ["vol"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000014', 'turnover_5d',      '5日换手率','technical', '情绪', '5日平均换手率', 'MA(turnover_rate, 5)', '{"window": 5}', '{"required": ["turnover_rate"]}', 'float', 'daily', true, true),

-- ==================== 其他技术指标 ====================
('f0010000-0000-0000-0000-000000000015', 'kdj_k',   'KDJ-K',         'technical', '动量', 'KDJ指标K值(9,3,3)', 'SMA(RSV, 3)', '{"n": 9, "m1": 3, "m2": 3}', '{"required": ["high", "low", "close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000016', 'atr_14',  'ATR(14)',       'technical', '风险', '14日平均真实波幅', 'MA(TR, 14)', '{"window": 14}', '{"required": ["high", "low", "close"]}', 'float', 'daily', true, true),

-- ==================== 估值类（基本面因子，依赖 financial_income 表） ====================
('f0010000-0000-0000-0000-000000000017', 'pe_ttm',  '市盈率(TTM)',   'fundamental', '估值', '滚动市盈率', 'market_cap / net_profit_ttm', '{}', '{"required": ["market_cap", "net_profit"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000018', 'pb',      '市净率',        'fundamental', '估值', '市净率', 'market_cap / book_value', '{}', '{"required": ["market_cap", "book_value"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000019', 'roe',     '净资产收益率',    'fundamental', '质量', '净资产收益率', 'net_profit / equity', '{}', '{"required": ["net_profit", "equity"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000020', 'gross_margin', '毛利率',    'fundamental', '质量', '毛利率', '(revenue - cost) / revenue', '{}', '{"required": ["revenue", "cost"]}', 'float', 'monthly', true, true)
ON CONFLICT (factor_code) DO NOTHING;
