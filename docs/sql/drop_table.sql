-- ============================================================
-- 量化交易系统完整DROP语句
-- 执行顺序：从叶子表到根表，避免外键约束
-- ============================================================

-- 禁用外键约束检查
SET session_replication_role = 'replica';

-- 1. 先删除物化视图和视图
DROP MATERIALIZED VIEW IF EXISTS mv_consecutive_limit_up CASCADE;
DROP VIEW IF EXISTS v_near_up_limit CASCADE;
DROP VIEW IF EXISTS v_stock_info CASCADE;

-- 2. 删除TimescaleDB超表和时序数据表（无外键依赖）
DROP TABLE IF EXISTS backtest_equity_curves CASCADE;
DROP TABLE IF EXISTS risk_events CASCADE;
DROP TABLE IF EXISTS signals CASCADE;
DROP TABLE IF EXISTS strategy_daily_performance CASCADE;
DROP TABLE IF EXISTS account_daily_performance CASCADE;
DROP TABLE IF EXISTS factor_data CASCADE;
DROP TABLE IF EXISTS trade_calendar CASCADE;
DROP TABLE IF EXISTS stock_moneyflow CASCADE;
DROP TABLE IF EXISTS stock_daily_limit CASCADE;
DROP TABLE IF EXISTS stock_daily_basic CASCADE;
DROP TABLE IF EXISTS stock_adj_factor CASCADE;
DROP TABLE IF EXISTS stock_adjusted_prices CASCADE;
DROP TABLE IF EXISTS stock_monthly CASCADE;
DROP TABLE IF EXISTS stock_weekly CASCADE;
DROP TABLE IF EXISTS stock_minutes CASCADE;
DROP TABLE IF EXISTS index_daily CASCADE;
DROP TABLE IF EXISTS fund_adj_factor CASCADE;
DROP TABLE IF EXISTS etf_minute CASCADE;
DROP TABLE IF EXISTS etf_daily CASCADE;
DROP TABLE IF EXISTS stock_daily CASCADE;

-- 3. 删除关系型数据表（按业务逻辑顺序）
-- 3.1 回测相关表
DROP TABLE IF EXISTS backtest_positions CASCADE;
DROP TABLE IF EXISTS backtest_trades CASCADE;
DROP TABLE IF EXISTS backtest_tasks CASCADE;

-- 3.2 分析相关表
DROP TABLE IF EXISTS analysis_reports CASCADE;

-- 3.3 交易相关表
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS positions CASCADE;

-- 3.4 策略相关表
DROP TABLE IF EXISTS strategy_runs CASCADE;
DROP TABLE IF EXISTS strategies CASCADE;

-- 3.5 篮子相关表
DROP TABLE IF EXISTS basket_items CASCADE;
DROP TABLE IF EXISTS baskets CASCADE;

-- 3.6 数据相关表
DROP TABLE IF EXISTS stk_rewards CASCADE;
DROP TABLE IF EXISTS stk_managers CASCADE;
DROP TABLE IF EXISTS stock_st_list CASCADE;
DROP TABLE IF EXISTS financial_statements CASCADE;
DROP TABLE IF EXISTS stock_company CASCADE;
DROP TABLE IF EXISTS etf_index CASCADE;
DROP TABLE IF EXISTS etf_basic CASCADE;
DROP TABLE IF EXISTS index_basic CASCADE;
DROP TABLE IF EXISTS stock_basic CASCADE;

-- 3.7 风控相关表
DROP TABLE IF EXISTS risk_rules CASCADE;

-- 3.8 系统管理表
DROP TABLE IF EXISTS sys_notifications CASCADE;
DROP TABLE IF EXISTS sys_audit_logs CASCADE;
DROP TABLE IF EXISTS monitor_alerts CASCADE;
DROP TABLE IF EXISTS sys_operation_logs CASCADE;
DROP TABLE IF EXISTS sys_scheduled_tasks CASCADE;
DROP TABLE IF EXISTS scheduled_tasks CASCADE;
DROP TABLE IF EXISTS system_configs CASCADE;
DROP TABLE IF EXISTS system_logs CASCADE;
DROP TABLE IF EXISTS data_sync_tasks CASCADE;

-- 3.9 因子定义表
DROP TABLE IF EXISTS factor_definitions CASCADE;

-- 3.10 账户相关表
DROP TABLE IF EXISTS accounts CASCADE;

-- 3.11 权限和用户相关表
DROP TABLE IF EXISTS sys_permissions CASCADE;
DROP TABLE IF EXISTS sys_users CASCADE;

-- 4. 删除触发器函数
DROP FUNCTION IF EXISTS update_modified_column() CASCADE;

-- 5. 重新启用外键约束检查
SET session_replication_role = 'origin';

-- 6. 删除TimescaleDB扩展（如果需要完全清理）
-- DROP EXTENSION IF EXISTS timescaledb CASCADE;

-- 7. 输出完成信息
DO $$
BEGIN
    RAISE NOTICE '===================================================';
    RAISE NOTICE '量化交易系统所有表已成功删除';
    RAISE NOTICE '删除表数量: 约50张表';
    RAISE NOTICE '===================================================';
END
$$;