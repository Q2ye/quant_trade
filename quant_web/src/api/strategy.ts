// quant_web/src/api/strategy.ts
// 策略管理API服务
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  Strategy,
  StrategyPerformance,
} from "@/types/entities/strategy";
import {
  ApiResponse,
  PaginatedResponse,
  PaginationParams,
  StrategyStatusInfo,
} from "@/types/api";

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

export interface StrategyListResponse extends PaginatedResponse<Strategy> {}
export interface StrategyDetailResponse extends ApiResponse<Strategy> {}
export interface StrategyStatusResponse extends ApiResponse<StrategyStatusInfo> {}
export interface StrategyPerformanceResponse extends ApiResponse<StrategyPerformance> {}

// ============================================================
// API 方法
// ============================================================

export default {
  async getStrategies(params?: StrategyQueryParams): Promise<Strategy[]> {
    return request
      .get("/quantTrade/strategy/strategies", { params })
      .then(handleResponse)
      .then((data: StrategyListResponse) => data.data.items);
  },

  async getStrategy(id: string): Promise<Strategy> {
    return request
      .get(`/strategy/strategies/${id}`)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async createStrategy(data: CreateStrategyRequest): Promise<Strategy> {
    return request
      .post("/quantTrade/strategy/strategies", data)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async updateStrategy(id: string, data: UpdateStrategyRequest): Promise<Strategy> {
    return request
      .put(`/strategy/strategies/${id}`, data)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async deleteStrategy(id: string): Promise<void> {
    return request
      .delete(`/strategy/strategies/${id}`)
      .then(handleResponse);
  },

  async startStrategy(id: string, params?: Record<string, any>): Promise<StrategyStatusInfo> {
    return request
      .post(`/strategy/strategies/${id}/start`, params || {})
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },

  async stopStrategy(id: string): Promise<StrategyStatusInfo> {
    return request
      .post(`/strategy/strategies/${id}/stop`)
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },

  async getStrategyPerformance(id: string): Promise<StrategyPerformance> {
    return request
      .get(`/strategy/strategies/${id}/performance`)
      .then(handleResponse)
      .then((data: StrategyPerformanceResponse) => data.data);
  },

  async getStrategyStatus(id: string): Promise<StrategyStatusInfo> {
    return request
      .get(`/strategy/strategies/${id}/status`)
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },
};
