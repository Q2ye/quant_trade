import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  DashboardOverview,
  MarketStatus,
  DashboardOverviewResponse,
  MarketStatusResponse,
} from "@/types";

/**
 * 仪表盘API服务
 * 聚合已有后端API：trade/account + trade/positions + trade/orders + analysis/equity-curve
 */
const api = {
  async getDashboardOverview(token: string): Promise<DashboardOverview> {
    return request
      .get("/quantTrade/trade/account")
      .then(handleResponse)
      .then((data: DashboardOverviewResponse) => data.data);
  },

  /**
   * 获取仪表盘完整数据 — 聚合 trade/account + positions + orders
   */
  async getDashboardData(): Promise<{
    accountInfo: {
      totalAsset: number;
      cash: number;
      dailyPnl: number;
      dailyReturn: number;
      positionsCount: number;
      activeStrategies: number;
    };
    recentSignals: Array<{
      name: string;
      symbol: string;
      direction: "buy" | "sell";
      price: number;
    }>;
    positions: Array<{
      symbol: string;
      name: string;
      quantity: number;
      price: number;
      cost: number;
      pnl: number;
      weight: number;
    }>;
    todayTrades: Array<{
      time: string;
      symbol: string;
      direction: "buy" | "sell";
      price: number;
      volume: number;
      amount: number;
    }>;
  }> {
    const [accountRes, positionsRes, ordersRes] = await Promise.all([
      request
        .get("/quantTrade/trade/account")
        .then(handleResponse)
        .catch(() => null),
      request
        .get("/quantTrade/trade/positions")
        .then(handleResponse)
        .catch(() => null),
      request
        .get("/quantTrade/trade/orders", { params: { limit: 20 } })
        .then(handleResponse)
        .catch(() => null),
    ]);

    // Map account data
    const acct = accountRes?.data ?? accountRes ?? {};
    const accountInfo = {
      totalAsset: acct.total_asset ?? acct.totalAsset ?? 0,
      cash: acct.cash ?? acct.available_cash ?? 0,
      dailyPnl: acct.daily_pnl ?? acct.dailyPnl ?? 0,
      dailyReturn: acct.daily_return ?? acct.dailyReturn ?? 0,
      positionsCount: acct.position_count ?? acct.positionsCount ?? 0,
      activeStrategies: acct.active_strategies ?? acct.activeStrategies ?? 0,
    };

    // Map positions
    const posList =
      positionsRes?.data?.items ??
      positionsRes?.data ??
      positionsRes?.items ??
      [];
    const positions = (Array.isArray(posList) ? posList : []).map((p: any) => ({
      symbol: p.ts_code ?? p.symbol ?? "",
      name: p.name ?? p.stock_name ?? "",
      quantity: p.quantity ?? p.volume ?? 0,
      price: p.current_price ?? p.price ?? 0,
      cost: p.cost_price ?? p.avg_cost ?? 0,
      pnl: p.unrealized_pnl ?? p.pnl ?? 0,
      weight: p.weight ?? p.allocation ?? 0,
    }));

    // Map orders to todayTrades
    const orderList =
      ordersRes?.data?.items ?? ordersRes?.data ?? ordersRes?.items ?? [];
    const todayTrades = (Array.isArray(orderList) ? orderList : [])
      .slice(0, 20)
      .map((o: any) => ({
        time: o.created_at ?? o.order_time ?? o.time ?? "",
        symbol: o.ts_code ?? o.symbol ?? "",
        direction: o.order_type ?? o.direction ?? "",
        price: o.price ?? o.order_price ?? 0,
        volume: o.quantity ?? o.volume ?? 0,
        amount:
          o.amount ?? o.trade_amount ?? (o.price ?? 0) * (o.quantity ?? 0),
      }));

    return {
      accountInfo,
      recentSignals: [],
      positions,
      todayTrades,
    };
  },

  /**
   * 获取策略绩效图表数据 — 走 analysis/equity-curve
   */
  async getPerformanceChart(range: string): Promise<{
    dates: string[];
    strategyReturns: number[];
    benchmarkReturns: number[];
  }> {
    return request
      .get("/quantTrade/analysis/equity-curve", { params: { range } })
      .then(handleResponse)
      .then((data: any) => {
        const d = data.data ?? data;
        return {
          dates: d.dates ?? [],
          strategyReturns: d.strategy_returns ?? d.strategyReturns ?? [],
          benchmarkReturns: d.benchmark_returns ?? d.benchmarkReturns ?? [],
        };
      });
  },

  async getMarketStatus(): Promise<MarketStatus> {
    return request
      .get("/quantTrade/data/statistics")
      .then(handleResponse)
      .then((data: MarketStatusResponse) => data.data)
      .catch(() => ({ status: "unknown", updateTime: "" }) as MarketStatus);
  },

  // 以下函数保留用于后续扩展
  async getRealtimeAssets(): Promise<{
    total_asset: number;
    cash: number;
    market_value: number;
    daily_pnl: number;
    timestamp: string;
  }> {
    return request
      .get("/quantTrade/trade/account")
      .then(handleResponse)
      .then((data: any) => {
        const d = data.data ?? data;
        return {
          total_asset: d.total_asset ?? 0,
          cash: d.cash ?? 0,
          market_value: d.market_value ?? 0,
          daily_pnl: d.daily_pnl ?? 0,
          timestamp: d.updated_at ?? new Date().toISOString(),
        };
      });
  },

  async getStrategyStatus(): Promise<
    Array<{
      strategy_id: string;
      strategy_name: string;
      status: "running" | "stopped" | "error";
      pnl_today: number;
      positions_count: number;
    }>
  > {
    return request
      .get("/quantTrade/strategy/status")
      .then(handleResponse)
      .then((data: any) => data.strategies ?? data.data ?? [])
      .catch(() => []);
  },

  async getRecentSignals(limit: number = 10): Promise<
    Array<{
      strategy_id: string;
      symbol: string;
      signal_type: string;
      price: number;
      timestamp: string;
    }>
  > {
    return request
      .get("/quantTrade/trade/orders", { params: { limit } })
      .then(handleResponse)
      .then((data: any) => {
        const items = data.data?.items ?? data.data ?? data.items ?? [];
        return items.slice(0, limit).map((o: any) => ({
          strategy_id: o.strategy_id ?? "",
          symbol: o.ts_code ?? o.symbol ?? "",
          signal_type: o.order_type ?? o.signal_type ?? "",
          price: o.price ?? 0,
          timestamp: o.created_at ?? o.timestamp ?? "",
        }));
      })
      .catch(() => []);
  },

  async getSystemMetrics(): Promise<{
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    database_connections: number;
    active_users: number;
  }> {
    return request
      .get("/quantTrade/monitor/system/metrics")
      .then(handleResponse)
      .then((data: any) => {
        const m = data.metrics ?? data.data ?? data;
        return {
          cpu_usage: m.cpu_usage ?? 0,
          memory_usage: m.memory_usage ?? 0,
          disk_usage: m.disk_usage ?? 0,
          database_connections: m.database_connections ?? 0,
          active_users: m.active_users ?? 0,
        };
      })
      .catch(() => ({
        cpu_usage: 0,
        memory_usage: 0,
        disk_usage: 0,
        database_connections: 0,
        active_users: 0,
      }));
  },
};

export default api;

export const getDashboardData = (token?: string) => api.getDashboardData();

export const getPerformanceChart = (range: string, token?: string) =>
  api.getPerformanceChart(range);
