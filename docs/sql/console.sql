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
select * from stock_basic  where ts_code like '001261';

select * from stock_basic  where name ='拓维信息';
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
select * from etf_basic where ts_code like '589980.SH';
select count(*) from etf_basic;
delete from etf_basic;
-- ETF份额数据表
select * from  etf_shares where ts_code = '589980.SH';
select count(*) from  etf_shares;
delete from etf_shares;

SELECT count(*), max(trade_date) FROM etf_shares WHERE ts_code = '159995.SZ';
SELECT count(*), count(DISTINCT ts_code) FROM etf_shares;
-- ETF日线行情表（TimescaleDB超表）

select * from  etf_daily where ts_code ='589980.SH';
select count(*) from  etf_daily where ts_code ='159 027.SZ';
delete from etf_daily;
-- ETF复权因子（TimescaleDB超表）
select * from  fund_adj_factor;
select count(*) from  fund_adj_factor;
delete from fund_adj_factor;
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
-- 1.16 因子研究任务表（补充完整）
select * from factor_research;
-- 因子数据表（TimescaleDB超表）
select * from factor_data;

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
-- 因子数据
select * from factor_data where ts_code = '002384.SZ';
-- 因子任务
select * from factor_research;
select * from factor_research where research_id ='research_419d48bf';
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

-- 交易相关表
select * from accounts;
SELECT * FROM orders ORDER BY submitted_at DESC LIMIT 1;
SELECT * FROM trades ORDER BY trade_time DESC LIMIT 1;
SELECT * FROM trade_fees ORDER BY created_at DESC LIMIT 3;
SELECT * FROM positions WHERE ts_code='000001.SZ';
SELECT * FROM accounts WHERE user_id='...';


ALTER TABLE data_sync_tasks DROP CONSTRAINT IF EXISTS data_sync_tasks_status_check;

ALTER TABLE data_sync_tasks ADD CONSTRAINT data_sync_tasks_status_check
CHECK (status = ANY (ARRAY['pending', 'running', 'completed', 'failed', 'cancelled']));

SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint WHERE conname = 'data_sync_tasks_status_check';
-- 数据质量检查记录表
select * from data_quality_checks where id='63270bf1-2d49-484d-8e82-cf34e6360d3a';

select * from factor_definitions

drop table factor_definitions

-- 清理旧的大小写重复数据
DELETE FROM factor_definitions;


SELECT factor_code, factor_name FROM factor_definitions WHERE factor_code = 'BETA';
SELECT COUNT(*) FROM factor_data WHERE factor_code = 'BETA';
-- 1. etf_basic 表数据概览
SELECT count(*) AS total,
       count(fund_type) AS has_fund_type,
       count(m_fee) AS has_m_fee,
       count(list_date) AS has_list_date,
       count(management) AS has_manager
FROM etf_basic
WHERE list_status = 'L';

-- 2. 抽几条看 fund_type 的实际值分布
SELECT fund_type, count(*) AS cnt
FROM etf_basic
WHERE list_status = 'L'
GROUP BY fund_type
ORDER BY cnt DESC
LIMIT 20;

-- 3. 抽几条看看具体数据
SELECT ts_code, name, fund_type, management, m_fee, list_date
FROM etf_basic
WHERE list_status = 'L'
LIMIT 5;

-- 4. etf_daily 是否真的有数据（核对"K线能加载"的结论）
SELECT count(*) AS total_rows,
       count(DISTINCT ts_code) AS distinct_etfs,
       MIN(trade_date) AS earliest,
       MAX(trade_date) AS latest
FROM etf_daily;
-- 查 159995 是否有份额数据

-- 5. 取几个 ETF 的最新日线，模拟列表子查询逻辑
SELECT ts_code, MAX(trade_date) AS latest_date
FROM etf_daily
WHERE ts_code IN (
    SELECT ts_code FROM etf_basic WHERE list_status = 'L' LIMIT 10
)
GROUP BY ts_code;