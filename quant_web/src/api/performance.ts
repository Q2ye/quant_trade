// quant_web/src/api/performance.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import { ApiResponse } from "@/types";
import { AccountInfo, PerformanceComparison } from "@/types";
import { ApiStrategyPerformance } from "@/types";

export default {
  /**
   * 获取策略绩效数据
   * @param strategyId 策略ID
   * @param params 查询参数
   * @returns 策略绩效数据
   */
  async getStrategyPerformance(
    strategyId: string,
    params?: {
      start_date?: string;
      end_date?: string;
    },
  ): Promise<ApiStrategyPerformance> {
    return request
      .get(`/quantTrade/analysis/performance/strategy/${strategyId}`, {
        params,
      })
      .then(handleResponse)
      .then((data: ApiResponse<ApiStrategyPerformance>) => data.data);
  },

  /**
   * 获取账户绩效数据
   * @param params 查询参数
   * @returns 账户绩效数据
   */
  async getAccountPerformance(
    accountId?: string,
    params?: {
      start_date?: string;
      end_date?: string;
    },
  ): Promise<AccountInfo> {
    const id = accountId || "default";
    return request
      .get(`/quantTrade/analysis/performance/account/${id}`, { params })
      .then(handleResponse)
      .then((data: ApiResponse<AccountInfo>) => data.data);
  },

  /**
   * 绩效对比分析
   * @param strategyIds 策略ID数组
   * @param params 对比参数
   * @returns 绩效对比结果
   */
  async comparePerformance(
    strategyIds: string[],
    params: {
      benchmark?: string;
      start_date?: string;
      end_date?: string;
    },
  ): Promise<PerformanceComparison> {
    return request
      .post(
        "/quantTrade/analysis/comparison/strategies",
        { strategyIds },
        { params },
      )
      .then(handleResponse)
      .then((data: ApiResponse<PerformanceComparison>) => data.data);
  },

  /**
   * 获取实时绩效数据（WebSocket备用接口）
   * @param strategyId 策略ID
   * @returns 实时绩效数据
   */
  async getRealtimePerformance(
    strategyId: string,
  ): Promise<ApiStrategyPerformance> {
    return request
      .get(`/quantTrade/analysis/strategy/${strategyId}/realtime`)
      .then(handleResponse)
      .then((data: ApiResponse<ApiStrategyPerformance>) => data.data);
  },

  /**
   * 获取策略归因分析
   * @param strategyId 策略ID
   * @returns 归因分析结果
   */
  async getAttribution(strategyId: string): Promise<any> {
    return request
      .get(`/quantTrade/analysis/attribution/strategy/${strategyId}`)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },
};
