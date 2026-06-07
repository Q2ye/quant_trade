"""
数据库仓库模块统一导出入口

本模块按照领域驱动设计原则，将所有数据访问逻辑封装在Repository中。
Repository提供统一的数据访问接口，屏蔽底层数据库细节，确保业务逻辑与数据访问解耦。

领域划分：
1. account/     - 账户管理领域：账户、资产、绩效、资金结算等
2. analysis/    - 分析领域：因子分析、监控预警、绩效分析等
3. market/      - 市场数据领域：股票、行情、财务、公司、ETF、基金、指数等
4. operation/   - 运营管理领域：文件、任务、工作流、篮子等
5. strategy/    - 策略领域：策略管理、回测、信号等
6. system/      - 系统管理领域：用户、权限、配置、运维等
7. trading/     - 交易领域：订单、持仓、风控、交易支持等
8. cache/       - 缓存数据领域：缓存管理、分布式锁等
9. hyper_tables/- 超表管理领域：时序数据专用工具

设计原则：
1. 一表一仓库：每个数据库表对应一个Repository类
2. 领域驱动：按照业务领域组织Repository
3. 统一接口：所有Repository继承自RepositoryBase基类
4. 依赖倒置：通过Repository接口访问数据，不直接依赖具体实现
"""

from .base import (
    BaseRepository,
    HyperRepositoryBase,
    PaginationParams,
    PaginationResult,
    QueryBuilder,
    FilterCondition,
    SortCondition,
    QueryParams,
    RepositoryError
)
from .types import (
    RepositoryResult,
    FilterOperator,
    DateRange,
    DateTimeRange,
    DatabaseConfig,
    BulkOperationResult,
    UpsertResult,
    CacheStrategy,
    CacheConfig
)
from .utils import (
    get_db_session,
    execute_with_session,
    build_select_query,
    build_count_query,
    build_exists_query,
    build_pagination_query,
    execute_query,
    fetch_one,
    fetch_all,
    fetch_paginated,
    fetch_dict,
    fetch_scalar,
    batch_insert,
    batch_update,
    batch_upsert,
    batch_delete,
    model_to_dict,
    dict_to_model,
    rows_to_dict_list,
    result_to_repository_result,
    ensure_date,
    ensure_datetime,
    QueryCache,
    NotFoundError,
    AlreadyExistsError,
    ValidationError,
    handle_repository_operation
)

# 导出基础类和工具类
__all__ = [
    # 基类
    'BaseRepository',
    'HyperRepositoryBase',
    'QueryBuilder',

    # 类型定义
    'RepositoryResult',
    'PaginationParams',
    'PaginationResult',
    'FilterOperator',
    'FilterCondition',
    'SortCondition',
    'QueryParams',
    'DateRange',
    'DateTimeRange',
    'DatabaseConfig',
    'BulkOperationResult',
    'UpsertResult',
    'CacheStrategy',
    'CacheConfig',

    # 工具函数
    'get_db_session',
    'execute_with_session',
    'build_select_query',
    'build_count_query',
    'build_exists_query',
    'build_pagination_query',
    'execute_query',
    'fetch_one',
    'fetch_all',
    'fetch_paginated',
    'fetch_dict',
    'fetch_scalar',
    'batch_insert',
    'batch_update',
    'batch_upsert',
    'batch_delete',
    'model_to_dict',
    'dict_to_model',
    'rows_to_dict_list',
    'result_to_repository_result',
    'ensure_date',
    'ensure_datetime',
    'QueryCache',

    # 异常类
    'RepositoryError',
    'NotFoundError',
    'AlreadyExistsError',
    'ValidationError',
    'handle_repository_operation'
]

# ============================================
# 账户管理领域 (account/)
# ============================================
try:
    from .account import (
        AccountRepository,
        AccountDailyPerformanceRepository,
        StrategyDailyPerformanceRepository,
        AccountTransactionRepository,
        AccountStatementRepository,
        CashFlowRepository
    )

    # 导出账户管理领域的所有Repository
    ACCOUNT_REPOSITORIES = {
        'account_repo': AccountRepository,
        'account_performance_repo': AccountDailyPerformanceRepository,
        'strategy_performance_repo': StrategyDailyPerformanceRepository,
        'account_transaction_repo': AccountTransactionRepository,
        'account_statement_repo': AccountStatementRepository,
        'cash_flow_repo': CashFlowRepository
    }

    __all__.extend([
        'AccountRepository',
        'AccountDailyPerformanceRepository',
        'StrategyDailyPerformanceRepository',
        'AccountTransactionRepository',
        'AccountStatementRepository',
        'CashFlowRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import account repositories: {e}")
    ACCOUNT_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    AccountRepository = None
    AccountDailyPerformanceRepository = None
    StrategyDailyPerformanceRepository = None
    AccountTransactionRepository = None
    AccountStatementRepository = None
    CashFlowRepository = None

# ============================================
# 分析领域 (analysis/)
# ============================================
try:
    from .analysis import (
        DataFixRecordRepository,
        DataQualityCheckRepository,
        DataQualityMetricRepository,
        FactorDataRepository,
        FactorDefinitionRepository,
        MonitorAlertRepository,
        MonitorThresholdRepository,
        AlertTemplateRepository,
        AlertDeliveryLogRepository,
        AnalysisReportRepository,
        AnalysisTaskRepository,
        AnalysisTemplateRepository,
        AnalysisBenchmarkRepository
    )

    # 导出分析领域的所有Repository
    ANALYSIS_REPOSITORIES = {
        'data_fix_record_repo': DataFixRecordRepository,
        'data_quality_check_repo': DataQualityCheckRepository,
        'data_quality_metric_repo': DataQualityMetricRepository,
        'factor_data_repo': FactorDataRepository,
        'factor_definition_repo': FactorDefinitionRepository,
        'monitor_alert_repo': MonitorAlertRepository,
        'monitor_threshold_repo': MonitorThresholdRepository,
        'alert_template_repo': AlertTemplateRepository,
        'alert_delivery_log_repo': AlertDeliveryLogRepository,
        'analysis_report_repo': AnalysisReportRepository,
        'analysis_task_repo': AnalysisTaskRepository,
        'analysis_template_repo': AnalysisTemplateRepository,
        'analysis_benchmark_repo': AnalysisBenchmarkRepository
    }

    __all__.extend([
        'DataFixRecordRepository',
        'DataQualityCheckRepository',
        'DataQualityMetricRepository',
        'FactorDataRepository',
        'FactorDefinitionRepository',
        'MonitorAlertRepository',
        'MonitorThresholdRepository',
        'AlertTemplateRepository',
        'AlertDeliveryLogRepository',
        'AnalysisReportRepository',
        'AnalysisTaskRepository',
        'AnalysisTemplateRepository',
        'AnalysisBenchmarkRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import analysis repositories: {e}")
    ANALYSIS_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    DataFixRecordRepository = None
    DataQualityCheckRepository = None
    DataQualityMetricRepository = None
    FactorDataRepository = None
    FactorDefinitionRepository = None
    MonitorAlertRepository = None
    MonitorThresholdRepository = None
    AlertTemplateRepository = None
    AlertDeliveryLogRepository = None
    AnalysisReportRepository = None
    AnalysisTaskRepository = None
    AnalysisTemplateRepository = None
    AnalysisBenchmarkRepository = None

# ============================================
# 市场数据领域 (market/)
# ============================================
try:
    from .market import (
        # 股票数据
        StockBasicRepository,
        # 公司信息
        CompanyRepository,
        STListRepository,
        # ETF数据
        ETFRepository,
        # 指数数据
        IndexBasicRepository,
        IndexWeightRepository,
        IndexRepository,

        # 行情数据
        StockDailyRepository,
        StockMinuteRepository,
        StockWeeklyRepository,
        StockMonthlyRepository,
        StockAdjFactorRepository,
        StockAdjustedPriceRepository,
        StockDailyLimitRepository,
        EtfDailyRepository,
        EtfMinuteRepository,
        FundAdjFactorRepository,

        # 基本面数据
        StockDailyBasicRepository,
        StockMoneyflowRepository,
        FinancialStatementRepository,
        # 财务衍生
        StockForecastRepository,
        StockExpressRepository,
        StockDividendRepository,
        StockFinaIndicatorRepository,
        StockAuditOpinionRepository,
        StockBusinessIncomeRepository,
        CompanyAnnouncementRepository,
        StockSuspendInfoRepository,
        # ETF
        EtfShareRepository,
        # Phase 1 (P0 轻量)
        StockHsgtRepository,
        StockStRiskRepository,
        DisclosureDateRepository,
        StockShareFloatRepository,
        # Phase 2 (P0 逐股)
        StockHoldernumberRepository,
        StockTop10HoldersRepository,
        StockTop10FloatHoldersRepository,
        StockPledgeStatRepository,
        StockHoldertradeRepository,
        # Phase 3 (P1 申万+预测+资金)
        IndexSwClassifyRepository,
        IndexSwMemberRepository,
        IndexSwDailyRepository,
        IndexDailyBasicRepository,
        StockForecastProRepository,
        StockMoneyflowHsgtRepository,
        # Phase 4 (修复+P2)
        IndexWeeklyRepository,
        StockFactorDailyRepository,
        StockFactorProDailyRepository,
        IndexFactorProDailyRepository,

        # 公司治理
        ManagerRepository,
        RewardRepository,

        # 参考数据
        TradeCalendarRepository,
        BasketRepository
    )

    # 导出市场数据领域的所有Repository
    MARKET_REPOSITORIES = {
        'stock_basic_repo': StockBasicRepository,
        'company_repo': CompanyRepository,
        'st_list_repo': STListRepository,
        'etf_repo': ETFRepository,
        'index_repo': IndexBasicRepository,
        'index_weight_repo': IndexWeightRepository,
        'index_aggregate_repo': IndexRepository,
        'stock_daily_repo': StockDailyRepository,
        'stock_minute_repo': StockMinuteRepository,
        'stock_weekly_repo': StockWeeklyRepository,
        'stock_monthly_repo': StockMonthlyRepository,
        'stock_adj_factor_repo': StockAdjFactorRepository,
        'stock_adjusted_price_repo': StockAdjustedPriceRepository,
        'stock_daily_limit_repo': StockDailyLimitRepository,
        'etf_daily_repo': EtfDailyRepository,
        'etf_minute_repo': EtfMinuteRepository,
        'fund_adj_factor_repo': FundAdjFactorRepository,
        'stock_daily_basic_repo': StockDailyBasicRepository,
        'stock_moneyflow_repo': StockMoneyflowRepository,
        'financial_statement_repo': FinancialStatementRepository,
        'forecast_repo': StockForecastRepository,
        'express_repo': StockExpressRepository,
        'dividend_repo': StockDividendRepository,
        'fina_indicator_repo': StockFinaIndicatorRepository,
        'audit_opinion_repo': StockAuditOpinionRepository,
        'business_income_repo': StockBusinessIncomeRepository,
        'company_announcement_repo': CompanyAnnouncementRepository,
        'suspend_info_repo': StockSuspendInfoRepository,
        'etf_share_repo': EtfShareRepository,
        # Phase 1
        'hsgt_repo': StockHsgtRepository,
        'st_risk_repo': StockStRiskRepository,
        'disclosure_date_repo': DisclosureDateRepository,
        'share_float_repo': StockShareFloatRepository,
        # Phase 2
        'holdernumber_repo': StockHoldernumberRepository,
        'top10_holders_repo': StockTop10HoldersRepository,
        'top10_float_holders_repo': StockTop10FloatHoldersRepository,
        'pledge_stat_repo': StockPledgeStatRepository,
        'holdertrade_repo': StockHoldertradeRepository,
        # Phase 3
        'sw_classify_repo': IndexSwClassifyRepository,
        'sw_member_repo': IndexSwMemberRepository,
        'sw_daily_repo': IndexSwDailyRepository,
        'index_dailybasic_repo': IndexDailyBasicRepository,
        'forecast_pro_repo': StockForecastProRepository,
        'moneyflow_hsgt_repo': StockMoneyflowHsgtRepository,
        # Phase 4
        'index_weekly_repo': IndexWeeklyRepository,
        'factor_daily_repo': StockFactorDailyRepository,
        'factor_pro_daily_repo': StockFactorProDailyRepository,
        'idx_factor_pro_repo': IndexFactorProDailyRepository,
        'manager_repo': ManagerRepository,
        'reward_repo': RewardRepository,
        'trade_calendar_repo': TradeCalendarRepository,
        'basket_repo': BasketRepository
    }

    # 添加到全局导出
    __all__.extend([
        'StockBasicRepository',
        'CompanyRepository',
        'STListRepository',
        'ETFRepository',
        'IndexBasicRepository',
        'IndexWeightRepository',
        'IndexRepository',
        'StockDailyRepository',
        'StockMinuteRepository',
        'StockWeeklyRepository',
        'StockMonthlyRepository',
        'StockAdjFactorRepository',
        'StockAdjustedPriceRepository',
        'StockDailyLimitRepository',
        'EtfDailyRepository',
        'EtfMinuteRepository',
        'FundAdjFactorRepository',
        'StockDailyBasicRepository',
        'StockMoneyflowRepository',
        'FinancialStatementRepository',
        'StockForecastRepository',
        'StockExpressRepository',
        'StockDividendRepository',
        'StockFinaIndicatorRepository',
        'StockAuditOpinionRepository',
        'StockBusinessIncomeRepository',
        'CompanyAnnouncementRepository',
        'StockSuspendInfoRepository',
        'EtfShareRepository',
        'StockHsgtRepository',
        'StockStRiskRepository',
        'DisclosureDateRepository',
        'StockShareFloatRepository',
        'StockHoldernumberRepository',
        'StockTop10HoldersRepository',
        'StockTop10FloatHoldersRepository',
        'StockPledgeStatRepository',
        'StockHoldertradeRepository',
        'IndexSwClassifyRepository',
        'IndexSwMemberRepository',
        'IndexSwDailyRepository',
        'IndexDailyBasicRepository',
        'StockForecastProRepository',
        'StockMoneyflowHsgtRepository',
        'IndexWeeklyRepository',
        'StockFactorDailyRepository',
        'StockFactorProDailyRepository',
        'IndexFactorProDailyRepository',
        'ManagerRepository',
        'RewardRepository',
        'TradeCalendarRepository',
        'BasketRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import market repositories: {e}")
    MARKET_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    StockBasicRepository = None
    CompanyRepository = None
    STListRepository = None
    ETFRepository = None
    IndexBasicRepository = None
    IndexWeightRepository = None
    IndexRepository = None
    StockDailyRepository = None
    StockMinuteRepository = None
    StockWeeklyRepository = None
    StockMonthlyRepository = None
    StockAdjFactorRepository = None
    StockAdjustedPriceRepository = None
    StockDailyLimitRepository = None
    EtfDailyRepository = None
    EtfMinuteRepository = None
    FundAdjFactorRepository = None
    StockDailyBasicRepository = None
    StockMoneyflowRepository = None
    FinancialStatementRepository = None
    StockForecastRepository = None
    StockExpressRepository = None
    StockDividendRepository = None
    StockFinaIndicatorRepository = None
    StockAuditOpinionRepository = None
    StockBusinessIncomeRepository = None
    CompanyAnnouncementRepository = None
    StockSuspendInfoRepository = None
    EtfShareRepository = None
    StockHsgtRepository = None
    StockStRiskRepository = None
    DisclosureDateRepository = None
    StockShareFloatRepository = None
    StockHoldernumberRepository = None
    StockTop10HoldersRepository = None
    StockTop10FloatHoldersRepository = None
    StockPledgeStatRepository = None
    StockHoldertradeRepository = None
    IndexSwClassifyRepository = None
    IndexSwMemberRepository = None
    IndexSwDailyRepository = None
    IndexDailyBasicRepository = None
    StockForecastProRepository = None
    StockMoneyflowHsgtRepository = None
    IndexWeeklyRepository = None
    StockFactorDailyRepository = None
    StockFactorProDailyRepository = None
    IndexFactorProDailyRepository = None
    ManagerRepository = None
    RewardRepository = None
    TradeCalendarRepository = None
    BasketRepository = None

# ============================================
# 运营管理领域 (operation/)
# ============================================
try:
    from .operation import (
        FileAttachmentRepository,
        DataSyncTaskRepository,
        FactorResearchRepository,
        MonitorTaskRepository,
        WorkflowTaskRepository,
        WorkflowLogRepository,
        BasketRepository as OperationBasketRepository,
        BasketItemRepository
    )

    # 导出运营管理领域的所有Repository
    OPERATION_REPOSITORIES = {
        'file_attachment_repo': FileAttachmentRepository,
        'data_sync_task_repo': DataSyncTaskRepository,
        'factor_research_repo': FactorResearchRepository,
        'monitor_task_repo': MonitorTaskRepository,
        'workflow_task_repo': WorkflowTaskRepository,
        'workflow_log_repo': WorkflowLogRepository,
        'basket_repo': OperationBasketRepository,
        'basket_item_repo': BasketItemRepository
    }

    __all__.extend([
        'FileAttachmentRepository',
        'DataSyncTaskRepository',
        'FactorResearchRepository',
        'MonitorTaskRepository',
        'WorkflowTaskRepository',
        'WorkflowLogRepository',
        'OperationBasketRepository',
        'BasketItemRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import operation repositories: {e}")
    OPERATION_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    FileAttachmentRepository = None
    DataSyncTaskRepository = None
    FactorResearchRepository = None
    MonitorTaskRepository = None
    WorkflowTaskRepository = None
    WorkflowLogRepository = None
    OperationBasketRepository = None
    BasketItemRepository = None

# ============================================
# 策略领域 (strategy/)
# ============================================
try:
    from .strategy import (
        BacktestParameterRepository,
        BacktestEquityCurveRepository,
        BacktestComparisonRepository,
        BacktestPositionRepository,
        BacktestResourceUsageRepository,
        BacktestScenarioRepository,
        BacktestTaskRepository,
        BacktestTradeRepository,
        PortfolioStrategyRepository,
        StrategyParameterRepository,
        StrategyRepository,
        StrategyTemplateRepository,
        StrategyVersionRepository,
        SignalRepository
    )

    # 导出策略领域的所有Repository
    STRATEGY_REPOSITORIES = {
        'backtest_parameter_repo': BacktestParameterRepository,
        'backtest_equity_curve_repo': BacktestEquityCurveRepository,
        'backtest_comparison_repo': BacktestComparisonRepository,
        'backtest_position_repo': BacktestPositionRepository,
        'backtest_resource_repo': BacktestResourceUsageRepository,
        'backtest_scenario_repo': BacktestScenarioRepository,
        'backtest_task_repo': BacktestTaskRepository,
        'backtest_trade_repo': BacktestTradeRepository,
        'portfolio_strategy_repo': PortfolioStrategyRepository,
        'strategy_parameter_repo': StrategyParameterRepository,
        'strategy_repo': StrategyRepository,
        'strategy_template_repo': StrategyTemplateRepository,
        'strategy_version_repo': StrategyVersionRepository,
        'signal_repo': SignalRepository
    }

    __all__.extend([
        'BacktestParameterRepository',
        'BacktestEquityCurveRepository',
        'BacktestComparisonRepository',
        'BacktestPositionRepository',
        'BacktestResourceUsageRepository',
        'BacktestScenarioRepository',
        'BacktestTaskRepository',
        'BacktestTradeRepository',
        'PortfolioStrategyRepository',
        'StrategyParameterRepository',
        'StrategyRepository',
        'StrategyTemplateRepository',
        'StrategyVersionRepository',
        'SignalRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import strategy repositories: {e}")
    STRATEGY_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    BacktestParameterRepository = None
    BacktestEquityCurveRepository = None
    BacktestComparisonRepository = None
    BacktestPositionRepository = None
    BacktestResourceUsageRepository = None
    BacktestScenarioRepository = None
    BacktestTaskRepository = None
    BacktestTradeRepository = None
    PortfolioStrategyRepository = None
    StrategyParameterRepository = None
    StrategyRepository = None
    StrategyTemplateRepository = None
    StrategyVersionRepository = None
    SignalRepository = None

# ============================================
# 系统管理领域 (system/)
# ============================================
try:
    from .system import (
        UserRepository,
        RoleRepository,
        PermissionRepository,
        ConfigRepository,
        LogRepository,
        AuditRepository,
        NotificationRepository,
        UserPreferenceRepository,
        ApiUsageLogRepository,
        SystemHealthMetricRepository,
        LicenseKeyRepository,
        ScheduledTaskRepository
    )

    # 导出系统管理领域的所有Repository
    SYSTEM_REPOSITORIES = {
        'user_repo': UserRepository,
        'role_repo': RoleRepository,
        'permission_repo': PermissionRepository,
        'config_repo': ConfigRepository,
        'log_repo': LogRepository,
        'audit_repo': AuditRepository,
        'notification_repo': NotificationRepository,
        'user_preference_repo': UserPreferenceRepository,
        'api_usage_log_repo': ApiUsageLogRepository,
        'system_health_repo': SystemHealthMetricRepository,
        'license_key_repo': LicenseKeyRepository,
        'scheduled_task_repo': ScheduledTaskRepository
    }

    __all__.extend([
        'UserRepository',
        'RoleRepository',
        'PermissionRepository',
        'ConfigRepository',
        'LogRepository',
        'AuditRepository',
        'NotificationRepository',
        'UserPreferenceRepository',
        'ApiUsageLogRepository',
        'SystemHealthMetricRepository',
        'LicenseKeyRepository',
        'ScheduledTaskRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import system repositories: {e}")
    SYSTEM_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    UserRepository = None
    RoleRepository = None
    PermissionRepository = None
    ConfigRepository = None
    LogRepository = None
    AuditRepository = None
    NotificationRepository = None
    UserPreferenceRepository = None
    ApiUsageLogRepository = None
    SystemHealthMetricRepository = None
    LicenseKeyRepository = None
    ScheduledTaskRepository = None

# ============================================
# 交易领域 (trading/)
# ============================================
try:
    from .trading import (
        OrderRepository,
        TradeRepository,
        PositionRepository,
        AccountRepository,
        TradeInstructionRepository,
        OrderTemplateRepository,
        TradeFeeRepository,
        PositionAdjustmentRepository,
        PositionSnapshotRepository,
        RiskRuleRepository,
        RiskEventRepository,
        BlacklistRepository
    )

    # 导出交易领域的所有Repository
    TRADING_REPOSITORIES = {
        'order_repo': OrderRepository,
        'trade_repo': TradeRepository,
        'position_repo': PositionRepository,
        'account_repo': AccountRepository,
        'trade_instruction_repo': TradeInstructionRepository,
        'order_template_repo': OrderTemplateRepository,
        'trade_fee_repo': TradeFeeRepository,
        'position_adjustment_repo': PositionAdjustmentRepository,
        'position_snapshot_repo': PositionSnapshotRepository,
        'risk_rule_repo': RiskRuleRepository,
        'risk_event_repo': RiskEventRepository,
        'blacklist_repo': BlacklistRepository
    }

    __all__.extend([
        'OrderRepository',
        'TradeRepository',
        'PositionRepository',
        'AccountRepository',
        'TradeInstructionRepository',
        'OrderTemplateRepository',
        'TradeFeeRepository',
        'PositionAdjustmentRepository',
        'PositionSnapshotRepository',
        'RiskRuleRepository',
        'RiskEventRepository',
        'BlacklistRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import trading repositories: {e}")
    TRADING_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    OrderRepository = None
    TradeRepository = None
    PositionRepository = None
    AccountRepository = None
    TradeInstructionRepository = None
    OrderTemplateRepository = None
    TradeFeeRepository = None
    PositionAdjustmentRepository = None
    PositionSnapshotRepository = None
    RiskRuleRepository = None
    RiskEventRepository = None
    BlacklistRepository = None

# ============================================
# 缓存数据领域 (cache/)
# ============================================
try:
    from .cache import (
        CacheRepository,
        DistributedLockRepository
    )

    # 导出缓存数据领域的所有Repository
    CACHE_REPOSITORIES = {
        'cache_repo': CacheRepository,
        'distributed_lock_repo': DistributedLockRepository
    }

    __all__.extend([
        'CacheRepository',
        'DistributedLockRepository'
    ])

except ImportError as e:
    print(f"Warning: Failed to import cache repositories: {e}")
    CACHE_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    CacheRepository = None
    DistributedLockRepository = None

# ============================================
# 超表管理领域 (hyper_tables/)
# ============================================
try:
    from .hyper_tables import (
        HyperTableManager,
        TimeBucketManager,
        RetentionPolicyManager,
        ChunkManager
    )

    # 导出超表管理领域的所有Repository
    HYPER_TABLE_REPOSITORIES = {
        'hyper_table_manager': HyperTableManager,
        'time_bucket_manager': TimeBucketManager,
        'retention_policy_manager': RetentionPolicyManager,
        'chunk_manager': ChunkManager
    }

    __all__.extend([
        'HyperTableManager',
        'TimeBucketManager',
        'RetentionPolicyManager',
        'ChunkManager'
    ])

except ImportError as e:
    print(f"Warning: Failed to import hyper table repositories: {e}")
    HYPER_TABLE_REPOSITORIES = {}
    # 定义默认值，避免导入错误时出现未定义变量
    HyperTableManager = None
    TimeBucketManager = None
    RetentionPolicyManager = None
    ChunkManager = None

# ============================================
# Repository工厂函数
# ============================================

def get_repository_by_domain(domain: str) -> dict:
    """
    获取指定领域的Repository

    Args:
        domain: 领域名称（account/analysis/market/operation/strategy/system/trading/cache/hyper_tables）

    Returns:
        dict: 领域内所有Repository名称到类的映射
    """
    domain_mapping = {
        'account': ACCOUNT_REPOSITORIES,
        'analysis': ANALYSIS_REPOSITORIES,
        'market': MARKET_REPOSITORIES,
        'operation': OPERATION_REPOSITORIES,
        'strategy': STRATEGY_REPOSITORIES,
        'system': SYSTEM_REPOSITORIES,
        'trading': TRADING_REPOSITORIES,
        'cache': CACHE_REPOSITORIES,
        'hyper_tables': HYPER_TABLE_REPOSITORIES
    }

    return domain_mapping.get(domain, {})


class RepositoryFactory:
    """
    Repository工厂类

    提供统一的方式创建和管理Repository实例，支持依赖注入和生命周期管理
    """

    def __init__(self):
        """初始化Repository工厂"""
        self._repositories = {}
        self._merge_all_repositories()

    def _merge_all_repositories(self):
        """合并所有领域的Repository"""
        self._repositories.update(ACCOUNT_REPOSITORIES)
        self._repositories.update(ANALYSIS_REPOSITORIES)
        self._repositories.update(MARKET_REPOSITORIES)
        self._repositories.update(OPERATION_REPOSITORIES)
        self._repositories.update(STRATEGY_REPOSITORIES)
        self._repositories.update(SYSTEM_REPOSITORIES)
        self._repositories.update(TRADING_REPOSITORIES)
        self._repositories.update(CACHE_REPOSITORIES)
        self._repositories.update(HYPER_TABLE_REPOSITORIES)

    def create_repository(self, repo_name: str, session) -> BaseRepository:
        """
        创建指定名称的Repository实例

        Args:
            repo_name: Repository名称
            session: SQLAlchemy数据库会话

        Returns:
            BaseRepository: Repository实例

        Raises:
            ValueError: 当Repository名称不存在时
        """
        repo_class = self._repositories.get(repo_name)
        if not repo_class:
            raise ValueError(f"Repository '{repo_name}' not found")

        return repo_class(session)

    def get_available_repositories(self) -> dict:
        """
        获取所有可用的Repository类

        Returns:
            dict: Repository名称到类的映射
        """
        return self._repositories.copy()


# 创建全局Repository工厂实例
repository_factory = RepositoryFactory()

# 添加到导出列表
__all__.append('repository_factory')
__all__.append('RepositoryFactory')

# ============================================
# 简化的导出方式（按领域分组导出）
# ============================================

# 按领域分组导出类
AccountRepositories = type('AccountRepositories', (), ACCOUNT_REPOSITORIES)
AnalysisRepositories = type('AnalysisRepositories', (), ANALYSIS_REPOSITORIES)
MarketRepositories = type('MarketRepositories', (), MARKET_REPOSITORIES)
OperationRepositories = type('OperationRepositories', (), OPERATION_REPOSITORIES)
StrategyRepositories = type('StrategyRepositories', (), STRATEGY_REPOSITORIES)
SystemRepositories = type('SystemRepositories', (), SYSTEM_REPOSITORIES)
TradingRepositories = type('TradingRepositories', (), TRADING_REPOSITORIES)
CacheRepositories = type('CacheRepositories', (), CACHE_REPOSITORIES)
HyperTableRepositories = type('HyperTableRepositories', (), HYPER_TABLE_REPOSITORIES)

# 添加到导出列表
__all__.extend([
    'AccountRepositories',
    'AnalysisRepositories',
    'MarketRepositories',
    'OperationRepositories',
    'StrategyRepositories',
    'SystemRepositories',
    'TradingRepositories',
    'CacheRepositories',
    'HyperTableRepositories',
    "get_repository_by_domain"
])