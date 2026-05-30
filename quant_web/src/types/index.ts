// types/index.ts — 统一类型导出入口
// 策略：源文件保留原名，barrel 层通过 `as` 别名解决跨模块同名冲突

// ============================================================================
// 通用基础类型（枚举、API 基类、实体基类、工具类型）
// ============================================================================
export * from "./common";

// ============================================================================
// 领域 API 类型 — 无冲突模块直接全量导出
// ============================================================================
export * from "./api-backtest";
export * from "./api-basket";
// api-data 显式导出（MarketStatusResponse 与 api-dashboard 冲突，用别名）
export type {
  StockQueryParams,
  QuoteQueryParams,
  KLineData,
  FinancialQueryParams,
  DataSyncRequest,
  DataSyncTask,
  IndexInfo,
  SectorInfo,
  HistoricalDataQueryParams,
  HistoricalDataResponse,
  MultiSymbolHistoricalDataResponse,
  HistoricalDataStats,
  HistoricalDataCompareParams,
  HistoricalDataCompareResult,
  StockListResponse,
  StockDetailResponse,
  QuoteDataResponse,
  FinancialDataResponse,
  DataSyncResponse,
  DataSyncListResponse,
  IndexListResponse,
  SectorListResponse,
  HistoricalDataListResponse,
  HistoricalDataStatsResponse,
  HistoricalDataCompareResponse,
  MarketStatusResponse as DataMarketStatusResponse,
  StockBasicInfo,
  MoneyFlowData,
} from "./api-data";
export * from "./api-dashboard";
export * from "./api-websocket";
export * from "./api-trade";

// ============================================================================
// 领域实体类型（无冲突） — 全量导出
// ============================================================================
export * from "./entities-risk";

// ============================================================================
// 领域 API 类型 — 存在冲突，显式别名导出
// ============================================================================

// api-performance: 无冲突（ApiResponse 重定义已在源文件移除），直接按名导出
export type { StrategyListItem, CurrentStrategy, PerformanceComparison, AccountInfo } from "./api-performance";

// api-shared: StrategyPerformance / BacktestResult 与 entities 冲突
export type {
  StrategyPerformance as ApiStrategyPerformance,
  BacktestResult as ApiBacktestResult,
} from "./api-shared";

// api-strategy: Strategy / StrategyStatusInfo / EquityPoint / BacktestTrade / BacktestPosition 与 entities 冲突
export type {
  CreateStrategyRequest,
  UpdateStrategyRequest,
  BacktestRequest,
  StrategyQueryParams,
  RunStrategyRequest,
  StopStrategyRequest,
  StrategySignal,
  StrategyListResponse,
  StrategyDetailResponse,
  BacktestResponse,
  StrategyStatusResponse,
  StrategySignalResponse,
  StrategyPerformanceResponse,
  // 冲突项别名
  Strategy as ApiStrategy,
  StrategyStatusInfo as ApiStrategyStatusInfo,
  EquityPoint as ApiEquityPoint,
  BacktestTrade as ApiBacktestTrade,
  BacktestPosition as ApiBacktestPosition,
} from "./api-strategy";

// api-system: SystemSettingsResponse = SystemConfigResponse 重命名（避免与 common.ts SystemConfigResponse 冲突）
export type {
  SystemLogQueryParams,
  SystemConfigUpdate,
  SystemLogsResponse,
  SystemMetricsResponse,
  ScheduledTasksResponse,
  SystemSettingsResponse,
  DataSourceStatusResponse,
  SystemBackupResponse,
  SystemBackupListResponse,
  SystemHealthResponse,
} from "./api-system";

// api-user: LoginRequest / RegisterRequest / ChangePasswordRequest / LoginResponse / UserPermission 与 entities-user 冲突
export type {
  // 无冲突 — 直接导出
  UserInfo,
  UserQueryParams,
  CreateUserRequest,
  UpdateUserRequest,
  UpdateUserPermissionRequest,
  UserInfoResponse,
  UserListResponse,
  PermissionResponse,
  // 冲突项 — 使用 Api* 前缀别名
  LoginRequest as ApiLoginRequest,
  RegisterRequest as ApiRegisterRequest,
  ChangePasswordRequest as ApiChangePasswordRequest,
  LoginResponse as ApiLoginResponse,
  UserPermission as ApiUserPermission,
} from "./api-user";

// ============================================================================
// 领域实体类型 — 与 API 层冲突的显式别名导出
// ============================================================================

// entities-basket: BacktestResult 与 entities-strategy 冲突 → BasketBacktestResult
export type {
  Basket,
  BasketItem,
  BasketPerformance,
  BasketStatistics,
  CreateBasketRequest,
  UpdateBasketRequest,
  BasketQueryParams,
  RealtimeBasketData,
  SimpleBasketItem,
  SimpleBasket,
  StockData,
  BacktestResult as BasketBacktestResult,
} from "./entities-basket";

// entities-dashboard: Position / Trade 与 entities-trading 冲突 → DashboardPosition / DashboardTrade
export type {
  DashboardData,
  DashboardOverview,
  MarketStatus,
  PerformanceChartItem,
  RiskMatrix,
  PositionDistribution,
  IndustryExposure,
  RealTimeSignal,
  MarketSentiment,
  RealTimeDataEvent,
  Position as DashboardPosition,
  Trade as DashboardTrade,
} from "./entities-dashboard";

// entities-data: DataSyncRequest / DataSyncTask 与 api-data 冲突 → DataSyncRequestParams / DataSyncTaskInfo
export type {
  StockBasic,
  StockCompany,
  StockDaily,
  StockMinutes,
  StockMoneyflow,
  ETFBasic,
  ETFDaily,
  FinancialData,
  HistoricalDataPoint,
  RealTimeQuote,
  IndexData,
  MarketOverview,
  DataQueryParams,
  DataSyncRequest as DataSyncRequestParams,
  DataSyncTask as DataSyncTaskInfo,
} from "./entities-data";

// entities-performance: StrategyPerformance / EquityPoint / BacktestTrade 与 api-shared / api-strategy 冲突
export type {
  PerformanceMetrics,
  AccountDailyPerformance,
  StrategyDailyPerformance,
  AccountPerformance,
  StrategyPerformance,
  EquityPoint,
  BacktestTrade,
} from "./entities-performance";

// entities-strategy: 大量与 API 层冲突
export type {
  Strategy,
  StrategyRun,
  BacktestConfig,
  BacktestResult,
  BacktestPosition,
  BenchmarkComparison,
  TradeSignal,
  StrategyTemplate,
  StrategyParameter,
  StrategyStatusInfo,
  BacktestTask as StrategyBacktestTask,
  BacktestTrade as StrategyBacktestTrade,
  StrategyPerformance as StrategyPerformanceMetrics,
} from "./entities-strategy";

// entities-system: DataSyncTask 与 api-data / entities-data 冲突 → SystemDataSyncTask
export type {
  SystemLog,
  SystemSetting,
  SystemHealth,
  ComponentHealth,
  AuditLog,
  SystemMetrics,
  ScheduledTask,
  DataSourceStatus,
  SystemBackupRequest,
  SystemBackup,
  DataSyncTask as SystemDataSyncTask,
} from "./entities-system";

// entities-trading: 无冲突（Position / Trade 由 dashboard 侧别名处理）
export type {
  Account,
  Position,
  Trade,
  Order,
  BasketOrder,
  BasketOrderItem,
  TradingSignal,
} from "./entities-trading";

// entities-user: LoginRequest / RegisterRequest / ChangePasswordRequest / LoginResponse / UserPermission 与 api-user 冲突
export type {
  User,
  UserPreferences,
  ResetPasswordRequest,
  LoginRequest as EntityLoginRequest,
  RegisterRequest as EntityRegisterRequest,
  ChangePasswordRequest as EntityChangePasswordRequest,
  LoginResponse as EntityLoginResponse,
  UserPermission as EntityUserPermission,
} from "./entities-user";

// ============================================================================
// 工具类型 — 无显式冲突
// ============================================================================
export * from "./utils-charts";
export * from "./utils-form";
export * from "./utils-table";
export * from "./utils-vuex";
export * from "./utils-userConverter";

// ============================================================================
// 状态类型
// ============================================================================
export * from "./state-root-state";
export * from "./state-basket-state";
export * from "./state-dashboard-state";
export * from "./state-data-state";
export * from "./state-layout-state";
export * from "./state-performance-state";
export * from "./state-risk-state";
export * from "./state-strategy-state";
export * from "./state-strategy-studio-state";
export * from "./state-system-state";
export * from "./state-trade-state";
export * from "./state-user-state";
