import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import { StrategySignal, ApiResponse, PaginatedResponse } from "@/types";

/**
 * 信号管理API服务
 * 提供交易信号的查询、分析和强度评估功能
 */

export interface SignalQueryParams {
  strategy_id?: string;
  symbol?: string;
  signal_type?: "buy" | "sell" | "hold";
  start_time?: string;
  end_time?: string;
  page?: number;
  limit?: number;
}

export interface SignalStrength {
  symbol: string;
  period: number;
  buy_signals: number;
  sell_signals: number;
  hold_signals: number;
  total_signals: number;
  strength_score: number;
  trend_direction: "bullish" | "bearish" | "neutral";
}

export interface SignalAnalysis {
  total_signals: number;
  buy_ratio: number;
  sell_ratio: number;
  accuracy_rate: number;
  avg_strength: number;
  top_signals: StrategySignal[];
}

export default {
  /**
   * 获取信号列表
   * @param params 查询参数
   * @returns 信号分页结果
   */
  async getSignals(
    params?: SignalQueryParams,
  ): Promise<PaginatedResponse<StrategySignal>> {
    return request
      .get("/quantTrade/strategy/signals/", { params })
      .then(handleResponse)
      .then((data: PaginatedResponse<StrategySignal>) => data);
  },

  /**
   * 获取信号强度分析
   * @param symbol 股票代码
   * @param params 分析参数
   * @returns 信号强度分析结果
   */
  async getSignalStrength(
    symbol: string,
    params?: {
      period?: number;
    },
  ): Promise<SignalStrength> {
    return request
      .get(`/quantTrade/strategy/signals/strength/${symbol}`, { params })
      .then(handleResponse)
      .then((data: ApiResponse<SignalStrength>) => data.data);
  },

  /**
   * 获取信号统计分析
   * @param params 统计参数
   * @returns 信号统计分析结果
   */
  async getSignalAnalysis(params?: {
    strategy_id?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<SignalAnalysis> {
    return request
      .get("/quantTrade/strategy/signals/analysis", { params })
      .then(handleResponse)
      .then((data: ApiResponse<SignalAnalysis>) => data.data);
  },

  /**
   * 获取实时信号流
   * @param strategyId 策略ID（可选）
   * @returns 实时信号数组
   */
  async getRealtimeSignals(strategyId?: string): Promise<StrategySignal[]> {
    const params = strategyId ? { strategy_id: strategyId } : undefined;
    return request
      .get("/quantTrade/strategy/signals/realtime", { params })
      .then(handleResponse)
      .then((data: ApiResponse<StrategySignal[]>) => data.data);
  },

  /**
   * 手动触发信号生成
   * @param symbol 股票代码
   * @param strategyId 策略ID
   * @returns 生成的信号
   */
  async triggerSignal(
    symbol: string,
    strategyId: string,
  ): Promise<StrategySignal> {
    return request
      .post("/quantTrade/strategy/signals/trigger", {
        symbol,
        strategy_id: strategyId,
      })
      .then(handleResponse)
      .then((data: ApiResponse<StrategySignal>) => data.data);
  },

  /**
   * 批量分析信号
   * @param signals 信号数据数组
   * @returns 分析结果
   */
  async analyzeSignalsBatch(signals: Partial<StrategySignal>[]): Promise<{
    analyzed_count: number;
    valid_signals: StrategySignal[];
    recommendations: Array<{
      signal: StrategySignal;
      confidence: number;
      recommendation: "execute" | "review" | "ignore";
    }>;
  }> {
    return request
      .post("/quantTrade/strategy/signals/analyze-batch", { signals })
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data.data);
  },
};
