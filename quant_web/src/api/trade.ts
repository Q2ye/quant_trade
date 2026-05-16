// quant_web/src/api/events.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  PlaceOrderRequest,
  OrderQueryParams,
  TradeQueryParams,
  ApiResponse,
  PaginatedResponse,
  BatchOrderResponse,
} from "@/types/api";
import { Account, Order, Position } from "@/types/entities";

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
    return request.delete(`/trade/orders/${orderId}`).then(handleResponse);
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
      .post("/quantTrade/trade/execute", signalData)
      .then(handleResponse)
      .then((data: ApiResponse<Order>) => data.data);
  },

  async getTradePerformance(accountId: string): Promise<TradePerformance> {
    return request
      .get(`/trade/performance/${accountId}`)
      .then(handleResponse)
      .then((data: ApiResponse<TradePerformance>) => data.data);
  },

  async getRealtimeTradeData(symbol: string): Promise<any> {
    return request
      .get(`/trade/realtime/${symbol}`)
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
};
