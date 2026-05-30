// WebSocket消息类型定义
import { ApiResponse } from "./common";

/**
 * WebSocket连接状态
 */
export interface WebSocketConnection {
  isConnected: boolean; // 连接状态
  lastActivity: number; // 最后活动时间
  reconnectAttempts: number; // 重连尝试次数
}

/**
 * WebSocket订阅请求
 */
export interface WebSocketSubscribeRequest {
  channels: string[]; // 订阅频道
  symbols?: string[]; // 订阅标的
  parameters?: Record<string, any>; // 订阅参数
}

/**
 * WebSocket取消订阅请求
 */
export interface WebSocketUnsubscribeRequest {
  channels: string[]; // 取消订阅频道
  symbols?: string[]; // 取消订阅标的
}

/**
 * 实时行情消息
 */
export interface RealTimeQuoteMessage {
  symbol: string; // 标的代码
  name: string; // 标的名称
  price: number; // 最新价格
  change: number; // 涨跌额
  changePercent: number; // 涨跌幅
  volume: number; // 成交量
  amount: number; // 成交额
  timestamp: string; // 时间戳
  bidPrice?: number; // 买一价
  askPrice?: number; // 卖一价
  high: number; // 当日最高
  low: number; // 当日最低
  open: number; // 开盘价
  preClose: number; // 前收价
}

/**
 * 分时数据消息
 */
export interface TimeShareMessage {
  symbol: string; // 标的代码
  timestamp: string; // 时间戳
  price: number; // 价格
  volume: number; // 成交量
  amount: number; // 成交额
  avgPrice: number; // 均价
}

/**
 * K线数据消息
 */
export interface KLineMessage {
  symbol: string; // 标的代码
  frequency: string; // K线周期
  timestamp: string; // 时间戳
  open: number; // 开盘价
  high: number; // 最高价
  low: number; // 最低价
  close: number; // 收盘价
  volume: number; // 成交量
  amount: number; // 成交额
}

/**
 * 交易信号消息
 */
export interface SignalMessage {
  strategyId: string; // 策略ID
  strategyName: string; // 策略名称
  symbol: string; // 标的代码
  symbolName: string; // 标的名称
  signalType: "buy" | "sell" | "hold" | "cancel"; // 信号类型
  price: number; // 信号价格
  volume: number; // 信号数量
  timestamp: string; // 信号时间
  reason: string; // 信号原因
  strength: number; // 信号强度
}

/**
 * 订单状态消息
 */
export interface OrderStatusMessage {
  orderId: string; // 订单ID
  symbol: string; // 标的代码
  status: string; // 订单状态
  filledVolume: number; // 已成交数量
  avgPrice?: number; // 平均成交价
  timestamp: string; // 更新时间
}

/**
 * 成交回报消息
 */
export interface TradeMessage {
  tradeId: string; // 成交ID
  orderId: string; // 订单ID
  symbol: string; // 标的代码
  direction: "buy" | "sell"; // 买卖方向
  price: number; // 成交价格
  volume: number; // 成交数量
  timestamp: string; // 成交时间
}

/**
 * 系统状态消息
 */
export interface SystemStatusMessage {
  component: string; // 组件名称
  status: "normal" | "warning" | "error"; // 状态
  message: string; // 状态消息
  timestamp: string; // 时间戳
}

/**
 * 风险预警消息
 */
export interface RiskAlertMessage {
  alertId: string; // 预警ID
  level: "low" | "medium" | "high" | "critical"; // 预警级别
  type: string; // 预警类型
  message: string; // 预警消息
  symbol?: string; // 关联标的
  strategyId?: string; // 关联策略
  timestamp: string; // 时间戳
}

// WebSocketMessage imported from ./common

// 消息类型常量
export const WebSocketMessageTypes = {
  // 行情相关
  REAL_TIME_QUOTE: "real_time_quote",
  TIME_SHARE: "time_share",
  KLINE: "kline",
  // 交易相关
  SIGNAL: "signal",
  ORDER_STATUS: "order_status",
  TRADE: "trade",
  // 系统相关
  SYSTEM_STATUS: "system_status",
  RISK_ALERT: "risk_alert",
  // 数据同步
  SYNC_EVENT: "sync_event",
  // 控制相关
  SUBSCRIBE_ACK: "subscribe_ack",
  UNSUBSCRIBE_ACK: "unsubscribe_ack",
  HEARTBEAT: "heartbeat",
  ERROR: "error",
} as const;

export interface SyncEventMessage {
  _event: "data_sync_started" | "data_sync_progress" | "data_sync_completed" | "data_sync_failed" | "data_sync_cancelled";
  task_id: string;
  sync_type?: string;
  progress?: number;
  record_count?: number;
  error_message?: string;
  timestamp?: string;
  [key: string]: any;
}

export interface TradeRecord {
  // 成交记录唯一标识
  id: string;
  // 股票代码
  symbol: string;
  // 成交价格
  price: number;
  // 成交数量
  quantity: number;
  // 成交时间戳
  timestamp: string;
  // 买卖方向
  side: "buy" | "sell";
  // 关联订单ID（可选）
  orderId?: string;
  // 策略ID（可选）
  strategyId?: string;
  // 手续费（可选）
  commission?: number;
}

// 响应类型定义
export interface WebSocketSubscribeResponse extends ApiResponse<{
  subscribedChannels: string[]; // 已订阅频道
  subscribedSymbols: string[]; // 已订阅标的
}> {}

export interface WebSocketConnectionResponse extends ApiResponse<WebSocketConnection> {}
