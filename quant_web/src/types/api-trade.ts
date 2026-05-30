// quant_web/src/types/api/events.ts
// 交易执行API类型定义
import { ApiResponse, PaginatedResponse, PaginationParams, TimeRangeParams } from "./common";
import { Account, Order, Position } from "./entities-trading";

/**
 * 下单请求参数
 */
export interface PlaceOrderRequest {
  symbol: string; // 标的代码
  direction: "buy" | "sell"; // 买卖方向
  orderType: "limit" | "market" | "stop"; // 订单类型
  price?: number; // 委托价格（限价单必需）
  volume: number; // 委托数量
  strategyId?: string; // 策略ID（策略下单时使用）
  basketId?: string; // 篮子ID（篮子下单时使用）
}

/**
 * 撤单请求参数
 */
export interface CancelOrderRequest {
  orderId: string; // 订单ID
  reason?: string; // 撤单原因
}

/**
 * 批量下单请求
 */
export interface BatchOrderRequest {
  orders: PlaceOrderRequest[]; // 订单列表
  basketId?: string; // 关联篮子ID
}

/**
 * 订单查询参数
 */
export interface OrderQueryParams extends PaginationParams, TimeRangeParams {
  symbol?: string; // 标的代码筛选
  direction?: "buy" | "sell"; // 买卖方向筛选
  orderType?: string; // 订单类型筛选
  status?: string; // 订单状态筛选
  strategyId?: string; // 策略ID筛选
}

/**
 * 成交记录查询参数
 */
export interface TradeQueryParams extends PaginationParams, TimeRangeParams {
  symbol?: string; // 标的代码筛选
  direction?: "buy" | "sell"; // 买卖方向筛选
  orderId?: string; // 订单ID筛选
}

/**
 * 交易统计
 */
export interface TradeStatistics {
  totalTrades: number; // 总交易次数
  winTrades: number; // 盈利交易次数
  lossTrades: number; // 亏损交易次数
  winRate: number; // 胜率
  profitFactor: number; // 盈利因子
  avgProfit: number; // 平均盈利
  avgLoss: number; // 平均亏损
  largestWin: number; // 最大盈利
  largestLoss: number; // 最大亏损
}

// 响应类型定义
export interface OrderResponse extends ApiResponse<Order> {}

export interface OrderListResponse extends PaginatedResponse<Order[]> {}

export interface TradeListResponse extends PaginatedResponse<Trade[]> {}

export interface PositionListResponse extends ApiResponse<Position[]> {}

export interface AccountInfoResponse extends ApiResponse<Account> {}

export interface TradeStatisticsResponse extends ApiResponse<TradeStatistics> {}

export interface BatchOrderResponse extends ApiResponse<{
  success: number; // 成功数量
  failed: number; // 失败数量
  orders: Order[]; // 创建的订单
  errors: Array<{
    // 错误详情
    symbol: string;
    message: string;
  }>;
}> {}
