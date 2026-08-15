// quant_web/src/api/strategy.ts
// 策略管理API服务
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import { ApiStrategy, ApiStrategyPerformance } from "@/types";
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
  status?: string;
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
  run_mode?: string;
  tags?: string[];
}

export interface RunStrategyRequest {
  strategyId: string;
  initialCapital?: number;
  parameters?: Record<string, any>;
  run_mode?: string;
  execution_mode?: string;
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
      .get("/quantTrade/strategy", {
        params: { page: 1, page_size: 50, ...params },
      })
      .then(handleResponse)
      .then((data: any) => data.data);
  },

  async getStrategy(id: string): Promise<ApiStrategy> {
    if (!id || id === "undefined" || id === "null") {
      console.warn("[strategyAPI] getStrategy called with invalid id:", id);
      return Promise.reject(new Error(`Invalid strategy id: ${id}`));
    }
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

  async updateStrategy(
    id: string,
    data: UpdateStrategyRequest,
  ): Promise<ApiStrategy> {
    if (!id || id === "undefined" || id === "null") {
      console.warn("[strategyAPI] updateStrategy called with invalid id:", id);
      return Promise.reject(new Error(`Invalid strategy id: ${id}`));
    }
    return request
      .put(`/quantTrade/strategy/${id}`, data)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async cloneStrategy(id: string, newName?: string): Promise<{ id: string; name: string }> {
    return request
      .post(`/quantTrade/strategy/${id}/clone`, { new_name: newName })
      .then(handleResponse)
      .then((data: any) => data.data);
  },

  async deleteStrategy(id: string): Promise<void> {
    return request.delete(`/quantTrade/strategy/${id}`).then(handleResponse);
  },

  async startStrategy(
    id: string,
    params?: Record<string, any>,
  ): Promise<ApiStrategyStatusInfo> {
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

  async compileStrategy(id: string): Promise<ApiStrategy> {
    return request
      .post(`/quantTrade/strategy/${id}/compile`)
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },

  async pauseStrategy(id: string): Promise<ApiStrategyStatusInfo> {
    return request
      .post(`/quantTrade/strategy/${id}/pause`)
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },

  async resumeStrategy(id: string): Promise<ApiStrategyStatusInfo> {
    return request
      .post(`/quantTrade/strategy/${id}/resume`)
      .then(handleResponse)
      .then((data: StrategyStatusResponse) => data.data);
  },

  // ---- 内置策略 API (v2.3) ----

  async getBuiltinStrategies(): Promise<any[]> {
    return request
      .get("/quantTrade/strategy/builtin")
      .then(handleResponse)
      .then((data: any) => data.data ?? []);
  },

  // ---- 策略模板 API ----

  async getTemplates(params?: {
    strategy_type?: string; page?: number; page_size?: number;
  }): Promise<any[]> {
    return request
      .get("/quantTrade/strategy/templates", { params: { page: 1, page_size: 50, ...params } })
      .then(handleResponse)
      .then((data: any) => data.data ?? []);
  },

  async getTemplate(id: string): Promise<any> {
    return request
      .get(`/quantTrade/strategy/templates/${id}`)
      .then(handleResponse)
      .then((data: any) => data.data);
  },

  async createTemplate(data: {
    name: string; strategy_type: string; code_template: string;
    description?: string; default_parameters?: Record<string, any>;
    category?: string;
  }): Promise<any> {
    return request
      .post("/quantTrade/strategy/templates", data)
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  async updateTemplate(id: string, data: Record<string, any>): Promise<any> {
    return request
      .put(`/quantTrade/strategy/templates/${id}`, data)
      .then(handleResponse)
      .then((res: any) => res.data);
  },

  async deleteTemplate(id: string): Promise<void> {
    return request
      .delete(`/quantTrade/strategy/templates/${id}`)
      .then(handleResponse);
  },

  async createFromTemplate(
    templateId: string,
    name: string,
    customParameters?: Record<string, any>,
  ): Promise<ApiStrategy> {
    return request
      .post(`/quantTrade/strategy/templates/${templateId}/create-strategy`, {
        name,
        custom_parameters: customParameters,
      })
      .then(handleResponse)
      .then((data: StrategyDetailResponse) => data.data);
  },


  // --- 信号确认 ---

  async getPendingSignals(params?: { strategy_id?: string }): Promise<any[]> {
    return request
      .get("/quantTrade/signals/pending", { params })
      .then(handleResponse)
      .then((res: any) => res.data || []);
  },

  async confirmSignal(signalId: string, data: {
    fill_price: number; fill_quantity: number; fill_time: string;
  }): Promise<any> {
    return request
      .post(`/quantTrade/signals/${signalId}/confirm`, data)
      .then(handleResponse);
  },

  async cancelSignal(signalId: string, reason?: string): Promise<any> {
    return request
      .post(`/quantTrade/signals/${signalId}/cancel`, { reason: reason || "" })
      .then(handleResponse);
  },

  async getStrategyPositions(strategyId: string): Promise<any[]> {
    return request
      .get(`/quantTrade/strategy/${strategyId}/positions`)
      .then(handleResponse)
      .then((res: any) => res.data || []);
  },

  // ---- 特征集 API (v3.4) ----

  async getFeatureSets(params?: { category?: string }): Promise<any[]> {
    return request
      .get("/quantTrade/strategy/feature-sets", { params: { page: 1, page_size: 50, ...params } })
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  async getAvailableFactors(): Promise<any[]> {
    return request
      .get("/quantTrade/strategy/available-factors")
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  // ---- 模型训练 API (v3.4) ----

  async trainLgbModel(params: {
    feature_set_ids?: string[];
    feature_codes?: string[];
    etf_pool?: string[];
    label_N?: number;
    label_X?: number;
    label_Y?: number;
    num_leaves?: number;
    max_depth?: number;
    learning_rate?: number;
    n_estimators?: number;
    reg_alpha?: number;
    reg_lambda?: number;
  }): Promise<any> {
    return request
      .post("/quantTrade/strategy/train/lgb", params)
      .then(handleResponse);
  },
};
