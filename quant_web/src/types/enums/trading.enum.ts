// 交易相关枚举类型定义
export enum OrderType {
  LIMIT = 'limit',          // 限价单
  MARKET = 'market',        // 市价单
  STOP = 'stop',            // 止损单
  STOP_LIMIT = 'stop_limit', // 止损限价单
  TRAILING_STOP = 'trailing_stop', // 跟踪止损单
  ICEBERG = 'iceberg',      // 冰山订单
  TWAP = 'twap',            // 时间加权平均价格
  VWAP = 'vwap'             // 成交量加权平均价格
}

export enum OrderStatus {
  SUBMITTED = 'submitted',          // 已提交
  PENDING = 'pending',              // 待处理
  ACCEPTED = 'accepted',            // 已接受
  PARTIAL_FILLED = 'partial_filled', // 部分成交
  FILLED = 'filled',                // 全部成交
  CANCELLED = 'cancelled',          // 已撤销
  REJECTED = 'rejected',            // 已拒绝
  EXPIRED = 'expired'               // 已过期
}

export enum OrderDirection {
  BUY = 'buy',              // 买入
  SELL = 'sell',            // 卖出
  SHORT_SELL = 'short_sell' // 卖空
}

export enum PositionSide {
  LONG = 'long',            // 多头
  SHORT = 'short',          // 空头
  NET = 'net'               // 净头寸
}

export enum TradeType {
  OPEN = 'open',            // 开仓
  CLOSE = 'close',          // 平仓
  CLOSE_TODAY = 'close_today', // 平今仓
  CLOSE_YESTERDAY = 'close_yesterday' // 平昨仓
}

export enum CommissionType {
  PERCENT = 'percent',      // 百分比
  FIXED = 'fixed',          // 固定金额
  TIERED = 'tiered'         // 阶梯式
}

export enum SlippageType {
  FIXED = 'fixed',          // 固定滑点
  PERCENT = 'percent',      // 百分比滑点
  VOLUME_WEIGHTED = 'volume_weighted' // 成交量加权
}

export enum BasketOrderStatus {
  PENDING = 'pending',      // 等待中
  EXECUTING = 'executing',  // 执行中
  PARTIAL = 'partial',      // 部分完成
  COMPLETED = 'completed',  // 已完成
  CANCELLED = 'cancelled',  // 已取消
  FAILED = 'failed'         // 失败
}

export enum ExecutionMode {
  MANUAL = 'manual',        // 手动执行
  AUTO = 'auto',            // 自动执行
  SEMI_AUTO = 'semi_auto'   // 半自动执行
}

export enum AccountType {
  CASH = 'cash',            // 现金账户
  MARGIN = 'margin',        // 保证金账户
  CREDIT = 'credit'         // 信用账户
}

export enum SettlementType {
  T0 = 'T0',                // T+0结算
  T1 = 'T1',                // T+1结算
  T2 = 'T2'                 // T+2结算
}