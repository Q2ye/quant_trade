// quant_web/src/api/strategy.ts
// 策略管理API服务
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  ApiStrategy,
  ApiStrategyPerformance,
} from "@/types";
import {
  ApiResponse,
  PaginatedResponse,
  PaginationParams,
  ApiStrategyStatusInfo,
} from "@/types";

// ============================================================
// 请求/响应类型定义
// ============================================================

export interface CreateStrategyRequest {
  name: string;
  description: string;
  code: string;
  parameters: Record<string, any>;
  category?: string;
  tags?: string[];
}

export interface UpdateStrategyRequest {
  name?: string;
  description?: string;
  code?: string;
  parameters?: Record<string, any>;
  category?: string;
  tags?: string[];
}

export interface BacktestRequest {
  strategyId: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  commission: number;
  slippage: number;
  universe?: string[];
  parameters?: Record<string, any>;
}

export interface StrategyQueryParams extends PaginationParams {
  name?: string;
  category?: string;
  status?: string;
  tags?: string[];
}

export interface RunStrategyRequest {
  strategyId: string;
  initialCapital?: number;
  parameters?: Record<string, any>;
}

export interface StopStrategyRequest {
  strategyId: string;
  reason?: string;
}

export interface StrategyListResponse extends PaginatedResponse<ApiStrategy> {}
export interface StrategyDetailResponse extends ApiResponse<ApiStrategy> {}
export interface StrategyStatusResponse extends ApiResponse<ApiStrategyStatusInfo> {}
export interface StrategyPerformanceResponse extends ApiResponse<ApiStrategyPerformance> {}

// ============================================================
// API 方法
// ============================================================

export default {
  async getStrategies(params?: StrategyQueryParams): Promise<ApiStrategy[]> {
    return request
      .get("/quantTrade/strategy", { params })
      .then(handleResponse)
      .then((data: any) => data.data);
  },

  async getStrategy(id: string): Promise<ApiStrategy> {
    return request
      .get(`/quantTrade/strategy/${id}`)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async createStrategy(data: CreateStrategyRequest): Promise<ApiStrategy> {
    return request
      .post("/quantTrade/strategy", data)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async updateStrategy(id: string, data: UpdateStrategyRequest): Promise<ApiStrategy> {
    return request
      .put(`/quantTrade/strategy/${id}`, data)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async deleteStrategy(id: string): Promise<void> {
    return request
      .delete(`/quantTrade/strategy/${id}`)
      .then(handleResponse);
  },

  async startStrategy(id: string, params?: Record<string, any>): Promise<ApiStrategyStatusInfo> {
    return request
      .post(`/quantTrade/strategy/${id}/start`, params || {})
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },

  async stopStrategy(id: string): Promise<ApiStrategyStatusInfo> {
    return request
      .post(`/quantTrade/strategy/${id}/stop`)
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },

  async getStrategyPerformance(id: string): Promise<ApiStrategyPerformance> {
    return request
      .get(`/quantTrade/strategy/${id}/performance`)
      .then(handleResponse)
      .then((data: StrategyPerformanceResponse) => data.data);
  },

  async getStrategyStatus(id: string): Promise<ApiStrategyStatusInfo> {
    return request
      .get(`/quantTrade/strategy/${id}/status`)
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },
};
