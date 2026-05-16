// 实体类型统一导出
// 注意：basket.ts 的 BacktestResult、performance.ts 的 BacktestTrade/StrategyPerformance
// 与 strategy.ts 同名冲突，后者优先（其余通过具体路径导入）
export * from "./base";
export type {
  BasketItem,
  BasketStatistics,
  BasketPerformance,
  Basket,
  CreateBasketRequest,
  UpdateBasketRequest,
  BasketQueryParams,
  RealtimeBasketData,
  SimpleBasketItem,
  SimpleBasket,
  StockData,
} from "./basket";
export type {
  AccountDailyPerformance,
  StrategyDailyPerformance,
  PerformanceMetrics,
  EquityPoint,
  AccountPerformance,
} from "./performance";
export * from "./data";
// dashboard.ts 的 Trade/Position 与 trading.ts 冲突，显式导出其余类型
export type {
  DashboardData,
  PerformanceChartItem,
  RiskMatrix,
  PositionDistribution,
  IndustryExposure,
  RealTimeSignal,
  MarketSentiment,
  RealTimeDataEvent,
} from "./dashboard";
export * from "./risk";
export * from "./strategy";
// system.ts 的 DataSyncTask 与 data.ts 冲突，显式排除
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
} from "./system";
export * from "./trading";
export * from "./user";
