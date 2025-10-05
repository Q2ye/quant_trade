// 通用枚举类型定义
export enum Status {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  DELETED = 'deleted',
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export enum Direction {
  BUY = 'buy',
  SELL = 'sell',
  HOLD = 'hold'
}

export enum Frequency {
  DAILY = 'daily',
  WEEKLY = 'weekly',
  MONTHLY = 'monthly',
  MINUTE_1 = '1min',
  MINUTE_5 = '5min',
  MINUTE_15 = '15min',
  MINUTE_30 = '30min',
  MINUTE_60 = '60min'
}

export enum MarketType {
  STOCK = 'stock',
  ETF = 'etf',
  INDEX = 'index',
  FUTURES = 'futures',
  OPTION = 'option'
}

export enum Exchange {
  SSE = 'SSE',    // 上海证券交易所
  SZSE = 'SZSE',  // 深圳证券交易所
  BSE = 'BSE',    // 北京证券交易所
  HKEX = 'HKEX',  // 香港交易所
  NYSE = 'NYSE',  // 纽约证券交易所
  NASDAQ = 'NASDAQ' // 纳斯达克
}

export enum ListStatus {
  LISTED = 'L',      // 上市
  DELISTED = 'D',    // 退市
  SUSPENDED = 'P'    // 暂停上市
}

export enum Currency {
  CNY = 'CNY',  // 人民币
  HKD = 'HKD',  // 港币
  USD = 'USD',  // 美元
  EUR = 'EUR'   // 欧元
}

export enum TimeRange {
  TODAY = 'today',
  YESTERDAY = 'yesterday',
  WEEK = 'week',
  MONTH = 'month',
  QUARTER = 'quarter',
  YEAR = 'year',
  ALL = 'all'
}

export enum SortOrder {
  ASC = 'asc',
  DESC = 'desc'
}

export enum ChartType {
  LINE = 'line',
  BAR = 'bar',
  CANDLE = 'candle',
  AREA = 'area',
  PIE = 'pie',
  SCATTER = 'scatter',
  HEATMAP = 'heatmap'
}

export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export enum NotificationType {
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
  TRADE = 'trade',
  RISK = 'risk',
  SYSTEM = 'system'
}

export enum ThemeMode {
  LIGHT = 'light',
  DARK = 'dark',
  AUTO = 'auto'
}

export enum Language {
  ZH_CN = 'zh-CN',
  EN_US = 'en-US'
}