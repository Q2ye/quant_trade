// 系统相关枚举类型定义
export enum DataSource {
  TUSHARE = "tushare", // Tushare数据源
  BAOSTOCK = "baostock", // Baostock数据源
  WIND = "wind", // Wind数据源
  JQDATA = "jqdata", // 聚宽数据源
  CUSTOM = "custom", // 自定义数据源
}

export enum DataType {
  STOCK_BASIC = "stock_basic", // 股票基本信息
  STOCK_DAILY = "stock_daily", // 股票日线数据
  STOCK_MINUTE = "stock_minute", // 股票分钟数据
  STOCK_FINANCIAL = "stock_financial", // 股票财务数据
  ETF_BASIC = "etf_basic", // ETF基本信息
  ETF_DAILY = "etf_daily", // ETF日线数据
  INDEX_DAILY = "index_daily", // 指数日线数据
  MONEY_FLOW = "money_flow", // 资金流向数据
  FACTOR_DATA = "factor_data", // 因子数据
}

export enum SyncTaskStatus {
  PENDING = "pending", // 等待中
  RUNNING = "running", // 执行中
  COMPLETED = "completed", // 已完成
  FAILED = "failed", // 失败
  CANCELLED = "cancelled", // 已取消
}

export enum LogLevel {
  DEBUG = "debug", // 调试信息
  INFO = "info", // 一般信息
  WARNING = "warning", // 警告信息
  ERROR = "error", // 错误信息
  CRITICAL = "critical", // 严重错误
}

export enum SystemModule {
  AUTH = "auth", // 认证模块
  USER = "user", // 用户模块
  STRATEGY = "strategy", // 策略模块
  TRADING = "trading", // 交易模块
  DATA = "data", // 数据模块
  RISK = "risk", // 风控模块
  PERFORMANCE = "performance", // 绩效模块
  SYSTEM = "system", // 系统模块
}

export enum HealthStatus {
  HEALTHY = "healthy", // 健康
  DEGRADED = "degraded", // 降级
  UNHEALTHY = "unhealthy", // 不健康
  UNKNOWN = "unknown", // 未知
}

export enum ComponentType {
  DATABASE = "database", // 数据库
  REDIS = "redis", // Redis缓存
  API = "api", // API服务
  STRATEGY_ENGINE = "strategy_engine", // 策略引擎
  DATA_SERVICE = "data_service", // 数据服务
  TRADING_ENGINE = "trading_engine", // 交易引擎
  RISK_ENGINE = "risk_engine", // 风控引擎
}

export enum AuditAction {
  LOGIN = "login", // 登录
  LOGOUT = "logout", // 登出
  CREATE = "create", // 创建
  READ = "read", // 读取
  UPDATE = "update", // 更新
  DELETE = "delete", // 删除
  EXECUTE = "execute", // 执行
}

export enum ResourceType {
  USER = "user", // 用户资源
  STRATEGY = "strategy", // 策略资源
  ORDER = "order", // 订单资源
  POSITION = "position", // 持仓资源
  BASKET = "basket", // 篮子资源
  SYSTEM = "system", // 系统资源
}

export enum CacheKey {
  MARKET_DATA = "market_data", // 市场数据缓存
  USER_SESSION = "user_session", // 用户会话缓存
  STRATEGY_STATUS = "strategy_status", // 策略状态缓存
  RISK_LIMITS = "risk_limits", // 风控限制缓存
  SYSTEM_CONFIG = "system_config", // 系统配置缓存
}
