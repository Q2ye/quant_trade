import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";

const BASE = "/quantTrade/backtest";

// ============================================================
// 类型定义 — 与后端 BacktestResult.to_dict() 对齐
// ============================================================

/** 回测任务摘要（列表项） */
export interface BacktestTaskSummary {
  task_id: string;
  name?: string;
  strategy_id: string;
  strategy_name?: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_return?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  created_at?: string;
  updated_at?: string;
  progress?: number;
  progress_percent?: number;
  error_message?: string;
}

/** 回测结果 — 对齐后端 BacktestResult.to_dict() */
export interface BacktestTaskResult {
  task_id: string;
  strategy_id: string;
  total_return: number;
  annual_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  num_trades: number;
  avg_trade_return: number;
  volatility: number;
  equity_curve: Array<{ trade_date: string; total_assets: number; cumulative_return: number }>;
  drawdown_curve: Array<{ trade_date: string; drawdown: number }>;
  trades: Array<{
    trade_id: string; ts_code: string; direction: string;
    price: number; quantity: number; amount: number;
    commission: number; stamp_tax: number; transfer_fee: number; trade_date: string;
  }>;
  monthly_returns: Array<{ month: string; return: number }>;
  benchmark_curve: Array<{ trade_date: string; cumulative_return: number; total_assets: number }>;
  excess_metrics: {
    alpha: number;
    beta: number;
    information_ratio: number;
    tracking_error: number;
    excess_annual_return: number;
    benchmark_annual_return: number;
    low_confidence: boolean;
    aligned_days: number;
  };
}

/** 创建回测任务参数 */
export interface BacktestCreateParams {
  name?: string;
  strategy_id?: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  commission_rate?: number;
  slippage_rate?: number;
  symbols?: string[];
  benchmark?: string;
  parameters?: Record<string, any>;
  /** 组合回测参数 */
  strategy_configs?: Array<{
    strategy_id: string;
    allocator_id?: string;
    parameters?: Record<string, any>;
  }>;
  /** P0 固定 Regime */
  force_regime?: number;
  allocator_params?: Record<string, any>;
}

export default {
  /**
   * 创建回测任务
   * POST /quantTrade/backtest/tasks
   */
  async createTask(
    config: BacktestCreateParams,
  ): Promise<{ task_id: string }> {
    return request
      .post(`${BASE}/tasks`, {
        name: config.name,
        strategy_id: config.strategy_id,
        start_date: config.start_date,
        end_date: config.end_date,
        initial_capital: config.initial_capital,
        commission_rate: config.commission_rate,
        slippage_rate: config.slippage_rate,
        symbols: config.symbols,
        benchmark: config.benchmark,
        parameters: config.parameters,
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 创建组合回测任务 — 多策略共享资金池
   * POST /quantTrade/backtest/composite
   */
  async createCompositeTask(
    config: BacktestCreateParams,
  ): Promise<{ task_id: string }> {
    return request
      .post(`${BASE}/composite`, {
        name: config.name,
        strategy_configs: config.strategy_configs,
        start_date: config.start_date,
        end_date: config.end_date,
        initial_capital: config.initial_capital,
        commission_rate: config.commission_rate,
        slippage_rate: config.slippage_rate,
        symbols: config.symbols,
        benchmark: config.benchmark,
        force_regime: config.force_regime,
        allocator_params: config.allocator_params,
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 获取回测任务列表
   * GET /quantTrade/backtest/tasks
   */
  async getTasks(params?: {
    status?: string; page?: number; page_size?: number; strategy_id?: string;
  }): Promise<BacktestTaskSummary[]> {
    return request
      .get(`${BASE}/tasks`, {
        params: { page: 1, page_size: 50, ...params },
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  /**
   * 获取回测任务详情
   * GET /quantTrade/backtest/tasks/{taskId}
   */
  async getTask(taskId: string): Promise<BacktestTaskSummary> {
    return request
      .get(`${BASE}/tasks/${taskId}`)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 取消回测任务
   * POST /quantTrade/backtest/tasks/{taskId}/cancel
   */
  async cancelTask(taskId: string): Promise<BacktestTaskSummary> {
    return request
      .post(`${BASE}/tasks/${taskId}/cancel`)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 删除回测任务
   * DELETE /quantTrade/backtest/tasks/{taskId}
   */
  async deleteTask(taskId: string): Promise<void> {
    return request.delete(`${BASE}/tasks/${taskId}`).then(handleResponse);
  },

  /**
   * 获取净值曲线
   * GET /quantTrade/backtest/tasks/{taskId}/equity
   */
  async getEquityCurve(taskId: string): Promise<BacktestTaskResult["equity_curve"]> {
    return request
      .get(`${BASE}/tasks/${taskId}/equity`)
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  /**
   * 获取交易记录
   * GET /quantTrade/backtest/tasks/{taskId}/trades
   */
  async getTrades(
    taskId: string,
    params?: { skip?: number; limit?: number },
  ): Promise<BacktestTaskResult["trades"]> {
    return request
      .get(`${BASE}/tasks/${taskId}/trades`, { params })
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  /**
   * 获取持仓快照
   * GET /quantTrade/backtest/tasks/{taskId}/positions
   */
  async getPositions(
    taskId: string,
    tradeDate?: string,
  ): Promise<any[]> {
    return request
      .get(`${BASE}/tasks/${taskId}/positions`, {
        params: tradeDate ? { trade_date: tradeDate } : undefined,
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  /**
   * 获取回测结果/绩效报告
   * GET /quantTrade/backtest/tasks/{taskId}/result
   */
  async getResult(taskId: string): Promise<BacktestTaskResult> {
    return request
      .get(`${BASE}/tasks/${taskId}/result`)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 批量获取回测结果
   * POST /quantTrade/backtest/tasks/results/batch
   */
  async getBatchResults(taskIds: string[]): Promise<Record<string, any>> {
    return request
      .post(`${BASE}/tasks/results/batch`, { task_ids: taskIds })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 参数优化
   * POST /quantTrade/backtest/optimize
   */
  async optimizeParameters(req: {
    strategyId: string;
    parameterRanges?: Record<string, { min: number; max: number; step: number }>;
    optimizationTarget?: string;
    startDate?: string;
    endDate?: string;
    initialCapital?: number;
  }): Promise<{ task_id?: string }> {
    return request
      .post(`${BASE}/optimize`, {
        strategy_id: req.strategyId,
        parameters: req.parameterRanges,
        optimization_method: "grid",
        optimization_target: req.optimizationTarget,
        start_date: req.startDate,
        end_date: req.endDate,
        initial_capital: req.initialCapital,
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 快速回测：一步完成
   * POST /quantTrade/backtest/quick
   */
  async quickBacktest(
    config: BacktestCreateParams,
  ): Promise<BacktestTaskResult> {
    return request
      .post(`${BASE}/quick`, {
        name: config.name,
        strategy_id: config.strategy_id,
        start_date: config.start_date,
        end_date: config.end_date,
        initial_capital: config.initial_capital,
        commission_rate: config.commission_rate,
        slippage_rate: config.slippage_rate,
        symbols: config.symbols,
        benchmark: config.benchmark,
        parameters: config.parameters,
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 导出回测报告
   * GET /quantTrade/backtest/tasks/{taskId}/report/export
   */
  async exportReport(
    taskId: string,
    format: 'json' | 'csv' = 'json',
  ): Promise<any> {
    return request
      .get(`${BASE}/tasks/${taskId}/report/export`, {
        params: { report_format: format },
      })
      .then(handleResponse);
  },

  /**
   * 健康检查
   * GET /quantTrade/backtest/health
   */
  async healthCheck(): Promise<{ status: string }> {
    return request.get(`${BASE}/health`).then(handleResponse);
  },
};
