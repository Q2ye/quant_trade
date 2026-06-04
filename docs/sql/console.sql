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

-- 指数基本信息表
select * from index_basic;
select count(*) from index_basic;
-- 指数日线行情数据（TimescaleDB超表）
select * from index_daily;
select count(*) from index_daily;
-- 复权因子表（TimescaleDB超表）
select * from stock_adj_factor where ts_code='000030.SZ';
select count(*) from stock_adj_factor;
delete from stock_adj_factor;
-- 交易日历史表
select * from trade_calendar;
select count(*) from trade_calendar;


-- 每日指标表（TimescaleDB超表）
select * from stock_daily_basic;
select count(*) from stock_daily_basic;
delete from stock_daily_basic;
-- 个股资金流向表
select * from stock_moneyflow;
select count(*) from stock_moneyflow;

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

-- 主营业务构成数据表
select * from  stock_business_incomes;
select count(*) from  stock_business_incomes;
-- ETF份额数据表
select * from  etf_shares;
select count(*) from  etf_shares;



-- A股日线行情表（TimescaleDB超表）
select * from  stock_daily;
select count(*) from stock_daily;
delete from stock_daily;

-- 回测任务
select * from backtest_tasks;

-- 回测参数
select * from backtest_parameters;

-- 因子
select * from factor_definitions;
-- 同步任务表
select * from data_sync_tasks;
-- 用户
select * from sys_users;



ALTER TABLE data_sync_tasks DROP CONSTRAINT IF EXISTS data_sync_tasks_status_check;

ALTER TABLE data_sync_tasks ADD CONSTRAINT data_sync_tasks_status_check
CHECK (status = ANY (ARRAY['pending', 'running', 'completed', 'failed', 'cancelled']));

SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint WHERE conname = 'data_sync_tasks_status_check';
-- 数据质量检查记录表
select * from data_quality_checks where id='63270bf1-2d49-484d-8e82-cf34e6360d3a'







