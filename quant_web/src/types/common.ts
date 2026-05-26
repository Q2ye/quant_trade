/**
 * types/common.ts — 通用类型（枚举 + 基础 API/实体类型 + 工具类型）
 * 由 types/enums/ + types/api/base + types/api/response + types/entities/base + types/utils/ 合并
 */

// ============================================================================
// 通用枚举（来源：types/enums/common.enum.ts）
// ============================================================================

export enum Status {
  ACTIVE = "active",
  INACTIVE = "inactive",
  DELETED = "deleted",
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
}

export enum Direction {
  BUY = "buy",
  SELL = "sell",
  HOLD = "hold",
}

export enum Frequency {
  DAILY = "daily",
  WEEKLY = "weekly",
  MONTHLY = "monthly",
  MINUTE_1 = "1min",
  MINUTE_5 = "5min",
  MINUTE_15 = "15min",
  MINUTE_30 = "30min",
  MINUTE_60 = "60min",
}

export enum MarketType {
  STOCK = "stock",
  ETF = "etf",
  INDEX = "index",
  FUTURES = "futures",
  OPTION = "option",
}

export enum Exchange {
  SSE = "SSE",
  SZSE = "SZSE",
  BSE = "BSE",
  HKEX = "HKEX",
  NYSE = "NYSE",
  NASDAQ = "NASDAQ",
}

export enum ListStatus {
  LISTED = "L",
  DELISTED = "D",
  SUSPENDED = "P",
}

export enum Currency {
  CNY = "CNY",
  HKD = "HKD",
  USD = "USD",
  EUR = "EUR",
}

export enum TimeRange {
  TODAY = "today",
  YESTERDAY = "yesterday",
  WEEK = "week",
  MONTH = "month",
  QUARTER = "quarter",
  YEAR = "year",
  ALL = "all",
}

export enum SortOrder {
  ASC = "asc",
  DESC = "desc",
}

export enum ChartType {
  LINE = "line",
  BAR = "bar",
  CANDLE = "candle",
  AREA = "area",
  PIE = "pie",
  SCATTER = "scatter",
  HEATMAP = "heatmap",
}

export enum RiskLevel {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  CRITICAL = "critical",
}

export enum NotificationType {
  INFO = "info",
  SUCCESS = "success",
  WARNING = "warning",
  ERROR = "error",
  TRADE = "trade",
  RISK = "risk",
  SYSTEM = "system",
}

export enum ThemeMode {
  LIGHT = "light",
  DARK = "dark",
  AUTO = "auto",
}

export enum Language {
  ZH_CN = "zh-CN",
  EN_US = "en-US",
}

// ============================================================================
// 策略枚举（来源：types/enums/strategy.enum.ts）
// ============================================================================

export enum StrategyStatus {
  DRAFT = "draft",
  RUNNING = "running",
  STOPPED = "stopped",
  PAUSED = "paused",
  ERROR = "error",
  DISABLED = "disabled",
}

export enum StrategyType {
  ALPHA = "alpha",
  CTA = "cta",
  ARBITRAGE = "arbitrage",
  MARKET_MAKING = "market_making",
  FACTOR = "factor",
  ML = "machine_learning",
  QUANT = "quantitative",
  MANUAL = "manual",
}

export enum StrategyCategory {
  STOCK_SELECTION = "stock_selection",
  TIMING = "timing",
  PORTFOLIO = "portfolio",
  HEDGING = "hedging",
  ARBITRAGE = "arbitrage",
  HIGH_FREQUENCY = "high_frequency",
  EVENT_DRIVEN = "event_driven",
}

export enum BacktestStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
}

export enum SignalType {
  BUY = "buy",
  SELL = "sell",
  HOLD = "hold",
  SHORT = "short",
  COVER = "cover",
  ALERT = "alert",
}

export enum SignalStrength {
  WEAK = "weak",
  MEDIUM = "medium",
  STRONG = "strong",
  VERY_STRONG = "very_strong",
}

export enum ParameterType {
  NUMBER = "number",
  STRING = "string",
  BOOLEAN = "boolean",
  ARRAY = "array",
  OBJECT = "object",
  SELECT = "select",
}

export enum OptimizationMethod {
  GRID = "grid",
  GENETIC = "genetic",
  BAYESIAN = "bayesian",
  RANDOM = "random",
}

export enum FactorType {
  VALUE = "value",
  GROWTH = "growth",
  QUALITY = "quality",
  MOMENTUM = "momentum",
  VOLATILITY = "volatility",
  LIQUIDITY = "liquidity",
  TECHNICAL = "technical",
  FUNDAMENTAL = "fundamental",
}

// ============================================================================
// 交易枚举（来源：types/enums/trading.enum.ts）
// ============================================================================

export enum OrderType {
  LIMIT = "limit",
  MARKET = "market",
  STOP = "stop",
  STOP_LIMIT = "stop_limit",
  TRAILING_STOP = "trailing_stop",
  ICEBERG = "iceberg",
  TWAP = "twap",
  VWAP = "vwap",
}

export enum OrderStatus {
  SUBMITTED = "submitted",
  PENDING = "pending",
  ACCEPTED = "accepted",
  PARTIAL_FILLED = "partial_filled",
  FILLED = "filled",
  CANCELLED = "cancelled",
  REJECTED = "rejected",
  EXPIRED = "expired",
}

export enum OrderDirection {
  BUY = "buy",
  SELL = "sell",
  SHORT_SELL = "short_sell",
}

export enum PositionSide {
  LONG = "long",
  SHORT = "short",
  NET = "net",
}

export enum TradeType {
  OPEN = "open",
  CLOSE = "close",
  CLOSE_TODAY = "close_today",
  CLOSE_YESTERDAY = "close_yesterday",
}

export enum CommissionType {
  PERCENT = "percent",
  FIXED = "fixed",
  TIERED = "tiered",
}

export enum SlippageType {
  FIXED = "fixed",
  PERCENT = "percent",
  VOLUME_WEIGHTED = "volume_weighted",
}

export enum BasketOrderStatus {
  PENDING = "pending",
  EXECUTING = "executing",
  PARTIAL = "partial",
  COMPLETED = "completed",
  CANCELLED = "cancelled",
  FAILED = "failed",
}

export enum ExecutionMode {
  MANUAL = "manual",
  AUTO = "auto",
  SEMI_AUTO = "semi_auto",
}

export enum AccountType {
  CASH = "cash",
  MARGIN = "margin",
  CREDIT = "credit",
}

export enum SettlementType {
  T0 = "T0",
  T1 = "T1",
  T2 = "T2",
}

// ============================================================================
// 系统枚举（来源：types/enums/system.enum.ts）
// ============================================================================

export enum DataSource {
  TUSHARE = "tushare",
  BAOSTOCK = "baostock",
  WIND = "wind",
  JQDATA = "jqdata",
  CUSTOM = "custom",
}

export enum DataType {
  STOCK_BASIC = "stock_basic",
  STOCK_DAILY = "stock_daily",
  STOCK_MINUTE = "stock_minute",
  STOCK_FINANCIAL = "stock_financial",
  ETF_BASIC = "etf_basic",
  ETF_DAILY = "etf_daily",
  INDEX_DAILY = "index_daily",
  MONEY_FLOW = "money_flow",
  FACTOR_DATA = "factor_data",
}

export enum SyncTaskStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
}

export enum LogLevel {
  DEBUG = "debug",
  INFO = "info",
  WARNING = "warning",
  ERROR = "error",
  CRITICAL = "critical",
}

export enum SystemModule {
  AUTH = "auth",
  USER = "user",
  STRATEGY = "strategy",
  TRADING = "trading",
  DATA = "data",
  RISK = "risk",
  PERFORMANCE = "performance",
  SYSTEM = "system",
}

export enum HealthStatus {
  HEALTHY = "healthy",
  DEGRADED = "degraded",
  UNHEALTHY = "unhealthy",
  UNKNOWN = "unknown",
}

export enum ComponentType {
  DATABASE = "database",
  REDIS = "redis",
  API = "api",
  STRATEGY_ENGINE = "strategy_engine",
  DATA_SERVICE = "data_service",
  TRADING_ENGINE = "trading_engine",
  RISK_ENGINE = "risk_engine",
}

export enum AuditAction {
  LOGIN = "login",
  LOGOUT = "logout",
  CREATE = "create",
  READ = "read",
  UPDATE = "update",
  DELETE = "delete",
  EXECUTE = "execute",
}

export enum ResourceType {
  USER = "user",
  STRATEGY = "strategy",
  ORDER = "order",
  POSITION = "position",
  BASKET = "basket",
  SYSTEM = "system",
}

export enum CacheKey {
  MARKET_DATA = "market_data",
  USER_SESSION = "user_session",
  STRATEGY_STATUS = "strategy_status",
  RISK_LIMITS = "risk_limits",
  SYSTEM_CONFIG = "system_config",
}

// ============================================================================
// 用户枚举（来源：types/enums/user.enum.ts）
// ============================================================================

export enum UserRole {
  SUPER_ADMIN = "super_admin",
  ADMIN = "admin",
  USER = "user",
  GUEST = "guest",
  READ_ONLY = "read_only",
}

export enum PermissionLevel {
  NONE = "none",
  READ = "read",
  WRITE = "write",
  EXECUTE = "execute",
  ADMIN = "admin",
}

export enum UserStatus {
  ACTIVE = "active",
  INACTIVE = "inactive",
  SUSPENDED = "suspended",
  LOCKED = "locked",
  DELETED = "deleted",
}

export enum LoginMethod {
  PASSWORD = "password",
  SMS = "sms",
  EMAIL = "email",
  SSO = "sso",
  API_KEY = "api_key",
}

export enum VerificationType {
  EMAIL = "email",
  PHONE = "phone",
  TWO_FACTOR = "two_factor",
  KYC = "kyc",
}

export enum PreferenceCategory {
  GENERAL = "general",
  TRADING = "trading",
  NOTIFICATION = "notification",
  DISPLAY = "display",
  RISK = "risk",
}

export enum DashboardView {
  OVERVIEW = "overview",
  TRADING = "trading",
  RESEARCH = "research",
  PERFORMANCE = "performance",
  RISK = "risk",
}

export enum NotificationChannel {
  EMAIL = "email",
  SMS = "sms",
  PUSH = "push",
  WEBHOOK = "webhook",
  IN_APP = "in_app",
}

// ============================================================================
// 枚举工具函数（来源：types/enums/index.ts）
// ============================================================================

export const getEnumKeys = <T extends Record<string, any>>(enumObj: T): Array<keyof T> => {
  return Object.keys(enumObj).filter((key) => isNaN(Number(key))) as Array<keyof T>;
};

export const getEnumValues = <T extends Record<string, any>>(enumObj: T): Array<T[keyof T]> => {
  return getEnumKeys(enumObj).map((key) => enumObj[key]);
};

export const getEnumKeyByValue = <T extends Record<string, any>>(enumObj: T, value: T[keyof T]): keyof T | undefined => {
  return getEnumKeys(enumObj).find((key) => enumObj[key] === value);
};

export const enumToOptions = <T extends Record<string, any>>(
  enumObj: T,
  labelMap?: Record<keyof T, string>,
): Array<{ label: string; value: T[keyof T] }> => {
  return getEnumKeys(enumObj).map((key) => ({
    label: labelMap?.[key] || key.toString(),
    value: enumObj[key],
  }));
};

// 中文标签映射
export const StrategyStatusLabel: Record<string, string> = {
  [StrategyStatus.DRAFT]: "草稿",
  [StrategyStatus.RUNNING]: "运行中",
  [StrategyStatus.STOPPED]: "已停止",
  [StrategyStatus.PAUSED]: "暂停",
  [StrategyStatus.ERROR]: "错误",
  [StrategyStatus.DISABLED]: "禁用",
};

export const OrderStatusLabel: Record<string, string> = {
  [OrderStatus.SUBMITTED]: "已提交",
  [OrderStatus.PENDING]: "待处理",
  [OrderStatus.ACCEPTED]: "已接受",
  [OrderStatus.PARTIAL_FILLED]: "部分成交",
  [OrderStatus.FILLED]: "全部成交",
  [OrderStatus.CANCELLED]: "已撤销",
  [OrderStatus.REJECTED]: "已拒绝",
  [OrderStatus.EXPIRED]: "已过期",
};

export const UserRoleLabel: Record<string, string> = {
  [UserRole.SUPER_ADMIN]: "超级管理员",
  [UserRole.ADMIN]: "管理员",
  [UserRole.USER]: "普通用户",
  [UserRole.GUEST]: "访客",
  [UserRole.READ_ONLY]: "只读用户",
};

export const RiskLevelLabel: Record<string, string> = {
  [RiskLevel.LOW]: "低风险",
  [RiskLevel.MEDIUM]: "中风险",
  [RiskLevel.HIGH]: "高风险",
  [RiskLevel.CRITICAL]: "严重风险",
};

// ============================================================================
// 基础 API 类型（来源：types/api/base.ts + types/api/response.ts，取并集）
// ============================================================================

export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
  timestamp: number;
}

export interface PaginatedResponse<T = any> extends ApiResponse<{
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}> {}

export interface PaginationParams {
  page?: number;
  pageSize?: number;
  keyword?: string;
}

export interface TimeRangeParams {
  startTime?: string;
  endTime?: string;
}

export interface SortParams {
  sortField?: string;
  sortOrder?: "asc" | "desc";
}

export interface BaseQueryParams extends PaginationParams, TimeRangeParams, SortParams {}

export interface IdParams {
  id: string;
}

export interface BatchOperationParams {
  ids: string[];
}

export interface FileUploadParams {
  file: File;
  category?: string;
  description?: string;
}

export interface WebSocketMessage<T = any> {
  type: string;
  data: T;
  timestamp: number;
}

export interface FileUploadResponse extends ApiResponse<{
  fileId: string;
  fileName: string;
  fileUrl: string;
  fileSize: number;
}> {}

export interface BatchOperationResponse extends ApiResponse<{
  success: number;
  failed: number;
  errors: Array<{ id: string; message: string }>;
}> {}

export interface SystemConfig {
  key: string;
  value: string;
  description?: string;
  isPublic?: boolean;
}

export interface DictItem {
  label: string;
  value: string;
  color?: string;
  order?: number;
}

export interface DictResponse extends ApiResponse<Record<string, DictItem[]>> {}

export interface SystemConfigResponse extends ApiResponse<SystemConfig[]> {}

export interface HealthCheckResponse extends ApiResponse<{
  status: string;
  version: string;
  timestamp: number;
  dependencies: { database: boolean; redis: boolean; dataSource: boolean };
}> {}

// ============================================================================
// 基础实体类型（来源：types/entities/base.ts）
// ============================================================================

export interface BaseEntity {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface ListResponse<T> {
  data: T[];
  pagination: { page: number; pageSize: number; total: number };
}

// ============================================================================
// 工具类型（来源：types/utils/common.ts + utils/index.ts）
// ============================================================================

export type Nullable<T> = T | null;
export type Optional<T> = { [K in keyof T]?: T[K] };
export type Dictionary<T> = { [key: string]: T };

export interface DateRange {
  start: string;
  end: string;
}

export interface KeyValuePair<K = string, V = any> {
  key: K;
  value: V;
}

// 深度工具类型
export type DeepReadonly<T> = { readonly [K in keyof T]: DeepReadonly<T[K]> };
export type DeepPartial<T> = { [K in keyof T]?: DeepPartial<T[K]> };
export type DeepRequired<T> = { [K in keyof T]-?: DeepRequired<T[K]> };

export type FunctionType = (...args: any[]) => any;
export type ConstructorType<T> = new (...args: any[]) => T;
export type Awaited<T> = T extends Promise<infer U> ? Awaited<U> : T;
export type AsyncFunctionReturnType<T extends (...args: any) => any> = Awaited<ReturnType<T>>;
export type EventHandler<T = any> = (event: T) => void;

export interface DebounceOptions {
  delay?: number;
  leading?: boolean;
  trailing?: boolean;
  maxWait?: number;
}

export interface ThrottleOptions {
  delay?: number;
  leading?: boolean;
  trailing?: boolean;
}

// ============================================================================
// 常用枚举映射（来源：types/enums/index.ts）
// ============================================================================

export const TradingEnums = { OrderType, OrderStatus, OrderDirection, PositionSide, TradeType } as const;
export const StrategyEnums = { StrategyStatus, StrategyType, StrategyCategory, BacktestStatus, SignalType } as const;
export const SystemEnums = { DataSource, DataType, SyncTaskStatus, LogLevel, HealthStatus } as const;
