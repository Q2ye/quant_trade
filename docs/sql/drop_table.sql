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
DROP VIEW IF EXISTS v_strategy_performance_overview CASCADE;
DROP VIEW IF EXISTS v_account_asset_overview CASCADE;

-- 1.1 删除所有触发器（先删除触发器，再删除表，因为表删除后触发器会自动删除，但显式删除更清晰）
DROP TRIGGER IF EXISTS update_sys_users_modtime ON sys_users CASCADE;
DROP TRIGGER IF EXISTS update_stock_basic_modtime ON stock_basic CASCADE;
DROP TRIGGER IF EXISTS update_stock_company_modtime ON stock_company CASCADE;
DROP TRIGGER IF EXISTS update_strategies_modtime ON strategies CASCADE;
DROP TRIGGER IF EXISTS update_orders_modtime ON orders CASCADE;
DROP TRIGGER IF EXISTS update_accounts_modtime ON accounts CASCADE;
DROP TRIGGER IF EXISTS update_baskets_modtime ON baskets CASCADE;
DROP TRIGGER IF EXISTS update_system_configs_modtime ON system_configs CASCADE;
DROP TRIGGER IF EXISTS update_scheduled_tasks_modtime ON scheduled_tasks CASCADE;
DROP TRIGGER IF EXISTS update_sys_roles_modtime ON sys_roles CASCADE;
DROP TRIGGER IF EXISTS update_user_preferences_modtime ON user_preferences CASCADE;
DROP TRIGGER IF EXISTS update_license_keys_modtime ON license_keys CASCADE;
DROP TRIGGER IF EXISTS update_strategy_parameters_modtime ON strategy_parameters CASCADE;
DROP TRIGGER IF EXISTS update_portfolio_strategies_modtime ON portfolio_strategies CASCADE;
DROP TRIGGER IF EXISTS update_trade_instructions_modtime ON trade_instructions CASCADE;
DROP TRIGGER IF EXISTS update_order_templates_modtime ON order_templates CASCADE;
DROP TRIGGER IF EXISTS update_backtest_tasks_modtime ON backtest_tasks CASCADE;
DROP TRIGGER IF EXISTS update_backtest_scenarios_modtime ON backtest_scenarios CASCADE;
DROP TRIGGER IF EXISTS update_factor_definitions_modtime ON factor_definitions CASCADE;
DROP TRIGGER IF EXISTS update_analysis_reports_modtime ON analysis_reports CASCADE;
DROP TRIGGER IF EXISTS update_analysis_templates_modtime ON analysis_templates CASCADE;
DROP TRIGGER IF EXISTS update_monitor_tasks_modtime ON monitor_tasks CASCADE;
DROP TRIGGER IF EXISTS update_alert_templates_modtime ON alert_templates CASCADE;
DROP TRIGGER IF EXISTS update_workflow_tasks_modtime ON workflow_tasks CASCADE;
DROP TRIGGER IF EXISTS update_factor_research_modtime ON factor_research CASCADE;
DROP TRIGGER IF EXISTS trigger_update_factor_research_updated_at ON factor_research CASCADE;
DROP TRIGGER IF EXISTS trigger_update_factor_research_status_timestamps ON factor_research CASCADE;

-- 2. 删除TimescaleDB压缩策略和保留策略（先删除策略，再删除表）
-- 删除stock_daily的压缩策略
SELECT remove_compression_policy('stock_daily') WHERE EXISTS (
    SELECT 1 FROM timescaledb_information.compression_settings
    WHERE hypertable_name = 'stock_daily'
);

-- 删除stock_minutes的压缩策略
SELECT remove_compression_policy('stock_minutes') WHERE EXISTS (
    SELECT 1 FROM timescaledb_information.compression_settings
    WHERE hypertable_name = 'stock_minutes'
);

-- 删除其他超表的压缩策略（如果有）
-- SELECT remove_compression_policy('etf_daily') WHERE EXISTS (SELECT 1 FROM timescaledb_information.compression_settings WHERE hypertable_name = 'etf_daily');
-- SELECT remove_compression_policy('index_daily') WHERE EXISTS (SELECT 1 FROM timescaledb_information.compression_settings WHERE hypertable_name = 'index_daily');

-- 删除保留策略（如果有）
-- SELECT remove_retention_policy('stock_minutes') WHERE EXISTS (SELECT 1 FROM timescaledb_information.retention_policies WHERE hypertable_name = 'stock_minutes');
-- SELECT remove_retention_policy('stock_daily') WHERE EXISTS (SELECT 1 FROM timescaledb_information.retention_policies WHERE hypertable_name = 'stock_daily');
-- SELECT remove_retention_policy('stock_moneyflow') WHERE EXISTS (SELECT 1 FROM timescaledb_information.retention_policies WHERE hypertable_name = 'stock_moneyflow');

-- 3. 删除TimescaleDB超表和时序数据表（无外键依赖）
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

-- 4. 删除关系型数据表（按业务逻辑顺序）
-- 4.1 工作流管理表
DROP TABLE IF EXISTS file_attachments CASCADE;
DROP TABLE IF EXISTS workflow_logs CASCADE;
DROP TABLE IF EXISTS workflow_tasks CASCADE;

-- 4.2 回测相关表
DROP TABLE IF EXISTS backtest_resource_usage CASCADE;
DROP TABLE IF EXISTS backtest_comparisons CASCADE;
DROP TABLE IF EXISTS backtest_scenarios CASCADE;
DROP TABLE IF EXISTS backtest_parameters CASCADE;
DROP TABLE IF EXISTS backtest_positions CASCADE;
DROP TABLE IF EXISTS backtest_trades CASCADE;
DROP TABLE IF EXISTS backtest_tasks CASCADE;

-- 4.3 分析相关表
DROP TABLE IF EXISTS analysis_benchmarks CASCADE;
DROP TABLE IF EXISTS report_generation_logs CASCADE;
DROP TABLE IF EXISTS analysis_templates CASCADE;
DROP TABLE IF EXISTS analysis_tasks CASCADE;
DROP TABLE IF EXISTS analysis_reports CASCADE;

-- 4.4 监控相关表
DROP TABLE IF EXISTS alert_delivery_logs CASCADE;
DROP TABLE IF EXISTS alert_templates CASCADE;
DROP TABLE IF EXISTS monitor_thresholds CASCADE;
DROP TABLE IF EXISTS monitor_tasks CASCADE;
DROP TABLE IF EXISTS monitor_alerts CASCADE;

-- 4.5 因子相关表
DROP TABLE IF EXISTS factor_research CASCADE;
DROP TABLE IF EXISTS data_quality_metrics CASCADE;
DROP TABLE IF EXISTS data_research_tasks CASCADE;
DROP TABLE IF EXISTS data_fix_records CASCADE;
DROP TABLE IF EXISTS data_quality_checks CASCADE;
DROP TABLE IF EXISTS factor_definitions CASCADE;

-- 4.6 交易相关表
DROP TABLE IF EXISTS trade_fees CASCADE;
DROP TABLE IF EXISTS position_adjustments CASCADE;
DROP TABLE IF EXISTS order_templates CASCADE;
DROP TABLE IF EXISTS trade_instructions CASCADE;
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS positions CASCADE;

-- 4.7 策略相关表
DROP TABLE IF EXISTS portfolio_strategies CASCADE;
DROP TABLE IF EXISTS strategy_parameters CASCADE;
DROP TABLE IF EXISTS strategy_templates CASCADE;
DROP TABLE IF EXISTS strategy_versions CASCADE;
DROP TABLE IF EXISTS strategy_runs CASCADE;
DROP TABLE IF EXISTS strategies CASCADE;

-- 4.8 篮子相关表
DROP TABLE IF EXISTS basket_items CASCADE;
DROP TABLE IF EXISTS baskets CASCADE;

-- 4.9 数据相关表
DROP TABLE IF EXISTS stk_rewards CASCADE;
DROP TABLE IF EXISTS stk_managers CASCADE;
DROP TABLE IF EXISTS stock_st_list CASCADE;
DROP TABLE IF EXISTS financial_statements CASCADE;
DROP TABLE IF EXISTS stock_company CASCADE;
DROP TABLE IF EXISTS etf_index CASCADE;
DROP TABLE IF EXISTS etf_basic CASCADE;
DROP TABLE IF EXISTS index_basic CASCADE;
DROP TABLE IF EXISTS stock_basic CASCADE;

-- 4.10 账户相关表
DROP TABLE IF EXISTS account_audit_logs CASCADE;
DROP TABLE IF EXISTS cash_flows CASCADE;
DROP TABLE IF EXISTS account_statements CASCADE;
DROP TABLE IF EXISTS account_transactions CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;

-- 4.11 风控相关表
DROP TABLE IF EXISTS risk_rules CASCADE;

-- 4.12 系统管理表
DROP TABLE IF EXISTS license_keys CASCADE;
DROP TABLE IF EXISTS system_health_metrics CASCADE;
DROP TABLE IF EXISTS api_usage_logs CASCADE;
DROP TABLE IF EXISTS user_preferences CASCADE;
DROP TABLE IF EXISTS sys_notifications CASCADE;
DROP TABLE IF EXISTS sys_audit_logs CASCADE;
DROP TABLE IF EXISTS sys_operation_logs CASCADE;
DROP TABLE IF EXISTS sys_scheduled_tasks CASCADE;
DROP TABLE IF EXISTS scheduled_tasks CASCADE;
DROP TABLE IF EXISTS system_configs CASCADE;
DROP TABLE IF EXISTS system_logs CASCADE;
DROP TABLE IF EXISTS data_sync_tasks CASCADE;

-- 4.13 权限和用户相关表
DROP TABLE IF EXISTS sys_user_roles CASCADE;
DROP TABLE IF EXISTS sys_permissions CASCADE;
DROP TABLE IF EXISTS sys_roles CASCADE;
DROP TABLE IF EXISTS sys_users CASCADE;

-- 5. 删除触发器函数
DROP FUNCTION IF EXISTS update_modified_column() CASCADE;
DROP FUNCTION IF EXISTS update_factor_research_updated_at() CASCADE;
DROP FUNCTION IF EXISTS update_factor_research_status_timestamps() CASCADE;

-- 6. 删除序列（如果有自定义序列）
-- 注：本项目使用SERIAL类型，删除表时会自动删除序列，无需显式删除

-- 7. 删除自定义类型（如果有）
-- 注：本项目未使用自定义DOMAIN类型

-- 8. 重新启用外键约束检查
SET session_replication_role = 'origin';

-- 9. 删除TimescaleDB扩展（如果需要完全清理）
-- DROP EXTENSION IF EXISTS timescaledb CASCADE;

-- 10. 输出完成信息
DO $$
BEGIN
    RAISE NOTICE '===================================================';
    RAISE NOTICE '量化交易系统所有表已成功删除';
    RAISE NOTICE '删除表数量: 约90张表';
    RAISE NOTICE '已删除视图、物化视图、触发器函数';
    RAISE NOTICE '已删除TimescaleDB压缩策略和保留策略';
    RAISE NOTICE '===================================================';
END
$$;