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
select * from index_basic where ts_code = '000905.SH';
select count(*) from index_basic;
-- 指数日线行情数据（TimescaleDB超表）
select * from index_daily where ts_code = '159886.SZ';
select count(*) from index_daily;
select * from  index_sw_daily  where ts_code = '881001.WI';

-- 指数成分股权重表
select * from index_weight;
select count(*) from index_weight;
-- 复权因子表（TimescaleDB超表）
select * from stock_adj_factor where ts_code='159886.SZ';
select count(*) from stock_adj_factor;
delete from stock_adj_factor;
-- 交易日历史表
select * from trade_calendar;
select count(*) from trade_calendar;

-- ETF基础信息表
select * from etf_basic where ts_code like '159886.SZ';
select count(*) from etf_basic;
delete from etf_basic;
-- ETF份额数据表
select * from  etf_shares where ts_code = '159886.SZ';
select count(*) from  etf_shares;
delete from etf_shares;

SELECT count(*), max(trade_date) FROM etf_shares WHERE ts_code = '159886.SZ';
SELECT count(*), count(DISTINCT ts_code) FROM etf_shares;
-- ETF日线行情表（TimescaleDB超表）

select * from  etf_daily where ts_code ='159886.SZ';
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

-- 因子
select * from factor_definitions;
-- 因子数据
select * from factor_data where ts_code = '002384.SZ';
-- 因子任务
select * from factor_research;
select * from factor_research where research_id ='research_419d48bf';
-- 策略实例表cd2f4a88-2139-4708-aee5-23dbfd953b20
select * from strategies;
select * from strategy_runs ;
-- 策略版本管理表
select * from strategy_versions;
-- 策略运行记录表
select * from strategy_runs;
-- 策略参数配置表
select * from strategy_parameters;

select * from strategy_templates;
select * from positions;
UPDATE positions SET strategy_id = '2db2c525-502e-489d-8d74-43f89e35a49e'
WHERE strategy_id IS NULL;
--
-- 同步任务表
select * from data_sync_tasks where id = 'fb91ee7a-d0a7-4a58-9e87-280a6e4ea730';
select * from data_sync_tasks where status = 'running';
-- 用户
select * from sys_users;
select * from  accounts;
select * from orders;
select * from trades;
select * from signals where ts_code = '002354.SZ';
select * from  account_daily_performance;


  -- 候选 → 买入信号（子查询）
SELECT * FROM signals WHERE parent_id = '<候选id>';

-- 买入信号 → 候选（父查询）
SELECT * FROM signals WHERE id = '<买入信号.parent_id>';

-- 完整链路：候选 → 信号 → 订单
SELECT c.id AS candidate_id, c.signal_status AS candidate_status,
       s.id AS signal_id, s.signal_status, s.order_id
FROM signals c
LEFT JOIN signals s ON s.parent_id = c.id
WHERE c.id = '<候选id>';

ALTER TABLE data_sync_tasks ADD COLUMN IF NOT EXISTS parent_task_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS idx_data_sync_tasks_parent ON data_sync_tasks(parent_task_id);
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

select * from factor_definitions;


-- 3. 一只典型 ETF 近 20 日 amount 值（确认单位），例如 515170.SH（食品饮料）
SELECT trade_date, close, vol, amount, pct_chg
FROM etf_daily
WHERE ts_code = '515170.SH'
  AND trade_date BETWEEN '2026-06-01' AND '2026-07-02'
ORDER BY trade_date DESC
LIMIT 20;

-- 检查 financial_disclosure_dates 表是否有数据
SELECT COUNT(*), MIN(actual_date), MAX(actual_date)
FROM financial_disclosure_dates;

SELECT COUNT(*) FROM financial_disclosure_dates;

SELECT research_id, factor_code, status, progress, started_at
FROM factor_research
WHERE status = 'running'
ORDER BY created_at DESC;
SELECT * from strategies;
SELECT * from backtest_equity_curves where task_id ='a9797c8f-0879-4c85-9eec-e597375ae563';
SELECT trade_date, close, open, high, low, vol FROM index_daily WHERE ts_code = '000905.SH' ORDER BY trade_date ASC;
-- 策略代码同步到 DB（路径因环境而异，执行前确认）
UPDATE strategies
SET code = pg_read_file('E:/QuantitativeTrading/quant_trade/quant_server/modules/strategy/strategies/etf/bottom_strategy.py')::text,
    updated_at = NOW()
WHERE id = '5277a1fc-a747-4f33-bb95-8056d1e56e24';

select * from  strategies
WHERE id = '5277a1fc-a747-4f33-bb95-8056d1e56e24';


-- 确认 etf_daily 条数是否够
SELECT COUNT(DISTINCT ts_code), MAX(trade_date) FROM etf_daily WHERE trade_date >= '2026-07-27';

SELECT MAX(trade_date) FROM etf_daily;

-- v3.3: status 列已删除，统一使用 signal_status
UPDATE signals SET signal_status = 'executed'
WHERE ts_code IN ('601988.SH', '601939.SH')
  AND strategy_id = '1b6b57a8-d58c-499f-a5fe-7d8c0c91f5a7'
  AND signal_status = 'pending_manual';

-- =============================================================================

-- ============================================================
-- 账户日绩效去重 (account_daily_performance)
-- 目标: 每个 (account_id, trade_date) 保留最新一条，删除其余
-- 执行顺序: 0)校验 → 1)去重 → 2)复查；随后跑一次日终结算刷新为正确值
-- ============================================================

-- 0) 校验：确认重复组数与将删除条数
SELECT COUNT(*) AS duplicate_groups,
       SUM(c - 1) AS rows_to_delete
FROM (
    SELECT account_id, trade_date, COUNT(*) AS c
    FROM account_daily_performance
    GROUP BY account_id, trade_date
    HAVING COUNT(*) > 1
) t;

-- 1) 去重：每个 (account_id, trade_date) 保留 created_at 最新的一条
--    （同 created_at 时按 id 排序兜底，保证幂等）
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY account_id, trade_date
               ORDER BY created_at DESC, id DESC
           ) AS rn
    FROM account_daily_performance
)
DELETE FROM account_daily_performance
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- 2) 复查：应返回 0 行
SELECT account_id, trade_date, COUNT(*) AS c
FROM account_daily_performance
GROUP BY account_id, trade_date
HAVING COUNT(*) > 1;



