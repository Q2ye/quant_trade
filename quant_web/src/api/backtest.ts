import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import type {
  CreateBacktestTaskRequest,
  BacktestQueryParams,
  ParameterOptimizeRequest,
} from "@/types";

const BASE = "/quantTrade/backtest";

/**
 * 将前端 camelCase 请求转换为后端 snake_case 格式
 */
function toSnakeCase(config: CreateBacktestTaskRequest): Record<string, any> {
  return {
    name: config.name,
    strategy_id: config.strategyId,
    start_date: config.startDate,
    end_date: config.endDate,
    initial_capital: config.initialCapital,
    commission_rate: config.commission,
    slippage_rate: config.slippage,
    parameters: {
      ...(config.parameters || {}),
      universe: config.universe || [],
      benchmark: config.benchmark || "000300.SH",
    },
  };
}

export default {
  /**
   * 创建回测任务
   * POST /quantTrade/backtest/tasks
   */
  async createTask(config: CreateBacktestTaskRequest): Promise<{ task_id: string }> {
    const body = toSnakeCase(config);
    return request.post(`${BASE}/tasks`, body).then(handleResponse).then((res: any) => res.data);
  },

  /**
   * 获取回测任务列表
   * GET /quantTrade/backtest/tasks
   */
  async getTasks(params?: BacktestQueryParams): Promise<any[]> {
    return request
      .get(`${BASE}/tasks`, { params })
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 获取回测任务详情
   * GET /quantTrade/backtest/tasks/{taskId}
   */
  async getTask(taskId: string): Promise<any> {
    return request
      .get(`${BASE}/tasks/${taskId}`)
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 取消回测任务
   * POST /quantTrade/backtest/tasks/{taskId}/cancel
   */
  async cancelTask(taskId: string): Promise<any> {
    return request
      .post(`${BASE}/tasks/${taskId}/cancel`)
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 获取净值曲线
   * GET /quantTrade/backtest/tasks/{taskId}/equity
   */
  async getEquityCurve(taskId: string): Promise<any[]> {
    return request
      .get(`${BASE}/tasks/${taskId}/equity`)
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 获取交易记录
   * GET /quantTrade/backtest/tasks/{taskId}/trades
   */
  async getTrades(taskId: string, params?: { skip?: number; limit?: number }): Promise<any[]> {
    return request
      .get(`${BASE}/tasks/${taskId}/trades`, { params })
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 获取持仓快照
   * GET /quantTrade/backtest/tasks/{taskId}/positions
   */
  async getPositions(taskId: string, tradeDate?: string): Promise<any[]> {
    return request
      .get(`${BASE}/tasks/${taskId}/positions`, {
        params: tradeDate ? { trade_date: tradeDate } : undefined,
      })
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 获取回测结果/绩效报告
   * GET /quantTrade/backtest/tasks/{taskId}/result
   */
  async getResult(taskId: string): Promise<any> {
    return request
      .get(`${BASE}/tasks/${taskId}/result`)
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 参数优化
   * POST /quantTrade/backtest/optimize
   */
  async optimizeParameters(req: ParameterOptimizeRequest): Promise<any> {
    return request
      .post(`${BASE}/optimize`, {
        strategy_id: req.strategyId,
        parameters: req.parameterRanges,
        optimization_method: "grid",
      })
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  /**
   * 健康检查
   * GET /quantTrade/backtest/health
   */
  async healthCheck(): Promise<any> {
    return request.get(`${BASE}/health`).then(handleResponse);
  },
};
