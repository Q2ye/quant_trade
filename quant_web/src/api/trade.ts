// quant_web/src/api/trade.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  PlaceOrderRequest,
  OrderQueryParams,
  TradeQueryParams,
  ApiResponse,
  PaginatedResponse,
  BatchOrderResponse,
} from "@/types";
import { Account, Order, Position } from "@/types";

export interface TradePerformance {
  total_profit: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  avg_profit_per_trade: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
}

export default {
  async getAccountInfo(): Promise<Account[]> {
    return request
      .get("/quantTrade/trade/account")
      .then(handleResponse)
      .then((data: ApiResponse<Account[]>) => data.data);
  },

  async getPositions(): Promise<Position[]> {
    return request
      .get("/quantTrade/trade/positions")
      .then(handleResponse)
      .then((data: ApiResponse<Position[]>) => data.data);
  },

  async getOrders(
    params?: OrderQueryParams,
  ): Promise<PaginatedResponse<Order[]>> {
    return request
      .get("/quantTrade/trade/orders", { params })
      .then(handleResponse)
      .then((data: PaginatedResponse<Order[]>) => data);
  },

  async createOrder(orderData: PlaceOrderRequest): Promise<Order> {
    return request
      .post("/quantTrade/trade/orders", orderData)
      .then(handleResponse)
      .then((data: ApiResponse<Order>) => data.data);
  },

  async cancelOrder(orderId: string): Promise<void> {
    return request
      .post(`/quantTrade/trade/orders/${orderId}/cancel`)
      .then(handleResponse);
  },

  async createBatchOrders(
    orders: PlaceOrderRequest[],
    basketId?: string,
  ): Promise<BatchOrderResponse> {
    return request
      .post("/quantTrade/trade/orders/batch", { orders, basket_id: basketId })
      .then(handleResponse)
      .then((data: BatchOrderResponse) => data);
  },

  async getTradeRecords(
    params?: TradeQueryParams,
  ): Promise<PaginatedResponse<Trade[]>> {
    return request
      .get("/quantTrade/trade/trades", { params })
      .then(handleResponse)
      .then((data: PaginatedResponse<Trade[]>) => data);
  },

  async executeTradeSignal(signalData: {
    strategy_id: string;
    symbol: string;
    signal_type: "buy" | "sell";
    price?: number;
    volume: number;
  }): Promise<Order> {
    return request
      .post("/quantTrade/trade/signals/execute", signalData)
      .then(handleResponse)
      .then((data: ApiResponse<Order>) => data.data);
  },

  async getTradePerformance(accountId: string): Promise<TradePerformance> {
    return request
      .get(`/quantTrade/analysis/performance/account/${accountId}`)
      .then(handleResponse)
      .then((data: ApiResponse<TradePerformance>) => data.data);
  },

  async getRealtimeTradeData(symbol: string): Promise<any> {
    return request
      .get(`/quantTrade/trade/realtime/${symbol}`)
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data.data);
  },

  async getTradeStatistics(params?: {
    start_date?: string;
    end_date?: string;
    strategy_id?: string;
  }): Promise<{
    total_trades: number;
    successful_trades: number;
    total_volume: number;
    total_amount: number;
    avg_trade_size: number;
  }> {
    return request
      .get("/quantTrade/trade/statistics", { params })
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data.data);
  },

  // ==================== 手动成交录入 ====================

  async recordTrade(record: {
    signal_id?: string;
    strategy_id?: string;
    ts_code: string;
    direction: string;
    price: number;
    quantity: number;
    trade_date: string;
    fees?: {
      commission?: number;
      stamp_duty?: number;
      transfer_fee?: number;
    };
  }): Promise<any> {
    return request
      .post("/quantTrade/trade/trades/record", record)
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data);
  },

  async recordBatchTrades(trades: Array<{
    signal_id?: string;
    ts_code: string;
    direction: string;
    price: number;
    quantity: number;
    trade_date: string;
    fees?: { commission?: number; stamp_duty?: number; transfer_fee?: number };
  }>): Promise<any> {
    return request
      .post("/quantTrade/trade/trades/record/batch", { trades })
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data);
  },

  // ==================== 信号管理 ====================

  async getSignals(params?: {
    status?: string;
    signal_type?: string;
    page?: number;
    page_size?: number;
  }): Promise<any> {
    return request
      .get("/quantTrade/trade/signals", { params })
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data);
  },

  async reviewSignal(signalId: string, action: string, comment?: string, rejectReason?: string): Promise<any> {
    return request
      .put(`/quantTrade/trade/signals/${signalId}/review`, { action, comment, reject_reason: rejectReason })
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data);
  },

  // v3.4: 信号链路追溯（候选→信号→订单→成交）
  async getSignalTrace(signalId: string): Promise<any> {
    return request
      .get(`/quantTrade/signals/${signalId}/trace`)
      .then(handleResponse)
      .then((data: any) => data?.data ?? data);
  },

  // 买卖 FIFO 配对追溯
  async getRoundTrips(accountId: string, tsCode?: string): Promise<any> {
    return request
      .get("/quantTrade/trade/round-trips", {
        params: { account_id: accountId, ts_code: tsCode },
      })
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data?.data ?? data);
  },
};

// 信号拒绝原因（与后端 SignalRejectReason 枚举对齐）
export const SIGNAL_REJECT_REASONS = [
  { label: "人工审核拒绝", value: "manual_rejected" },
  { label: "跳空高开（不追高）", value: "gap_up_chase" },
  { label: "跳空低开/破位（不接飞刀）", value: "gap_down_break" },
  { label: "资金不足", value: "insufficient_funds" },
];

// 拒绝原因枚举值 → 中文（后端 reason 存英文枚举前缀，前端展示时映射中文）
const REJECT_REASON_LABELS: Record<string, string> = {
  manual_rejected: "人工审核拒绝",
  gap_up_chase: "跳空高开",
  gap_down_break: "跳空低开",
  insufficient_funds: "资金不足",
  confirm_failed: "确认失败",
  volume_confirm_failed: "量能不足",
  expired_unconfirmed: "过期未确认",
  bull_market_give_up: "牛市让位",
  deleted: "已删除",
};

// 将 reason 的英文枚举前缀映射为中文（纯 code 或 "code: 详情" 均支持）
export function formatRejectReason(reason?: string | null): string {
  if (!reason) return "--";
  // 纯枚举 code（如 "gap_down_break"）→ 直接映射中文
  if (REJECT_REASON_LABELS[reason]) return REJECT_REASON_LABELS[reason];
  // "code: 详情"（如 "confirm_failed: 收盘12.53 ≤ 信号价13.52"）→ 映射 code + 保留详情
  const m = reason.match(/^([a-z_]+):\s*(.*)$/);
  if (m) {
    const label = REJECT_REASON_LABELS[m[1]];
    if (label) return m[2] ? `${label}：${m[2]}` : label;
  }
  return reason;
}
