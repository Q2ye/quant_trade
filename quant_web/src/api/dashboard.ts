import request from '@/utils/request'
import { handleResponse } from '@/utils/responseHandler'
import {
  DashboardOverview,
  MarketStatus,
  DashboardOverviewResponse,
  MarketStatusResponse
} from '@/types'
import {dashboardAPI} from "@/api/index";

/**
 * 仪表盘API服务
 * 提供系统概览、市场状态、实时数据等仪表盘相关功能
 */
export default {
  /**
   * 获取仪表盘概览数据
   * @param token 用户token
   * @returns 仪表盘概览信息
   */
  async getDashboardOverview(token: string): Promise<DashboardOverview> {
    return request.get('/dashboard/overview', {
      params: { token }
    }).then(handleResponse)
      .then((data: DashboardOverviewResponse) => data.data)
  },

  /**
   * 获取仪表盘完整数据（包含账户信息、持仓、信号等）
   * @param token 用户token
   * @returns 完整仪表盘数据
   */
  async getDashboardData(token?: string): Promise<{
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
      direction: 'buy' | 'sell';
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
      direction: 'buy' | 'sell';
      price: number;
      volume: number;
      amount: number;
    }>;
  }> {
    const params = token ? { token } : {};
    return request.get('/dashboard/data', { params })
      .then(handleResponse)
      .then((data: any) => data.data)
  },

  /**
   * 获取策略绩效图表数据
   * @param range 时间范围 '1D' | '1W' | '1M' | '1Y'
   * @param token 用户token
   * @returns 图表数据
   */
  async getPerformanceChart(range: string, token?: string): Promise<{
    dates: string[];
    strategyReturns: number[];
    benchmarkReturns: number[];
  }> {
    const params: any = { range };
    if (token) {
      params.token = token;
    }

    return request.get('/dashboard/performance', { params })
      .then(handleResponse)
      .then((data: any) => data.data)
  },

  /**
   * 获取市场状态信息
   * @returns 各市场交易状态
   */
  async getMarketStatus(): Promise<MarketStatus> {
    return request.get('/dashboard/market-status')
      .then(handleResponse)
      .then((data: MarketStatusResponse) => data.data)
  },

  /**
   * 获取实时资产变动
   * @param token 用户token
   * @returns 实时资产数据
   */
  async getRealtimeAssets(token: string): Promise<{
    total_asset: number;
    cash: number;
    market_value: number;
    daily_pnl: number;
    timestamp: string;
  }> {
    return request.get('/dashboard/realtime-assets', {
      params: { token }
    }).then(handleResponse)
  },

  /**
   * 获取策略运行状态
   * @param token 用户token
   * @returns 策略状态列表
   */
  async getStrategyStatus(token: string): Promise<Array<{
    strategy_id: string;
    strategy_name: string;
    status: 'running' | 'stopped' | 'error';
    pnl_today: number;
    positions_count: number;
  }>> {
    return request.get('/dashboard/strategy-status', {
      params: { token }
    }).then(handleResponse)
      .then((data: { strategies: any[] }) => data.strategies)
  },

  /**
   * 获取最新交易信号
   * @param token 用户token
   * @param limit 数量限制
   * @returns 最新信号列表
   */
  async getRecentSignals(token: string, limit: number = 10): Promise<Array<{
    strategy_id: string;
    symbol: string;
    signal_type: string;
    price: number;
    timestamp: string;
  }>> {
    return request.get('/dashboard/recent-signals', {
      params: { token, limit }
    }).then(handleResponse)
      .then((data: { signals: any[] }) => data.signals)
  },

  /**
   * 获取系统监控数据
   * @returns 系统监控指标
   */
  async getSystemMetrics(): Promise<{
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    database_connections: number;
    active_users: number;
  }> {
    return request.get('/dashboard/system-metrics')
      .then(handleResponse)
      .then((data: { metrics: any }) => data.metrics)
  }
}

// 命名导出，方便按需导入
export const getDashboardData = (token?: string) =>
  dashboardAPI.getDashboardData(token);

export const getPerformanceChart = (range: string, token?: string) =>
  dashboardAPI.getPerformanceChart(range, token);