import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";

const BASE = "/quantTrade/composite";

export interface StrategyConfigItem {
  strategy_id: string;
  allocator_id?: string;
}

export interface CompositeGroup {
  id: string;
  name: string;
  account_id?: string;
  strategy_ids: StrategyConfigItem[];
  current_regime: number;
  current_allocation?: Record<string, number>;
  status: string;
  last_rebalance_at?: string;
  created_at?: string;
}

export interface CompositeTriggerResult {
  composite_group_id: string;
  trade_date: string;
  regime: number;
  allocation: Record<string, number>;
  strategies_triggered: string[];
  skipped_strategies: string[];
  total_signals: number;
  conflicts: any[];
  signals: any[];
}

export interface RebalanceResult {
  composite_group_id: string;
  regime: number;
  previous_allocation: Record<string, number>;
  new_allocation: Record<string, number>;
  capital_changes: Array<{
    strategy_id: string;
    allocator_id: string;
    old_capital: number;
    new_capital: number;
    weight: number;
  }>;
}

export default {
  // 账户列表（组合共享账户下拉选择用）
  async getAccounts(): Promise<Array<{ id: string; account_number: string; account_name: string; status?: string }>> {
    return request.get("/quantTrade/account/list").then(handleResponse);
  },
  // ---- 组合分组 CRUD ----
  async createGroup(data: {
    name: string;
    account_id?: string;
    strategy_configs: StrategyConfigItem[];
    allocator_config?: Record<string, any>;
  }): Promise<CompositeGroup> {
    return request
      .post(`${BASE}/groups`, data)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  async listGroups(): Promise<CompositeGroup[]> {
    return request
      .get(`${BASE}/groups`)
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  async getGroup(groupId: string): Promise<CompositeGroup> {
    return request
      .get(`${BASE}/groups/${groupId}`)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  async updateGroup(groupId: string, data: {
    name?: string;
    strategy_configs?: StrategyConfigItem[];
    allocator_config?: Record<string, any>;
  }): Promise<CompositeGroup> {
    return request
      .put(`${BASE}/groups/${groupId}`, data)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  async deleteGroup(groupId: string): Promise<void> {
    return request.delete(`${BASE}/groups/${groupId}`).then(handleResponse);
  },

  // ---- 成员管理 ----
  async addStrategy(groupId: string, data: {
    strategy_id: string;
    allocator_id?: string;
    w0: number;
    w1: number;
    w2: number;
  }): Promise<any> {
    return request
      .post(`${BASE}/groups/${groupId}/strategies`, data)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  async removeStrategy(groupId: string, strategyId: string): Promise<any> {
    return request
      .delete(`${BASE}/groups/${groupId}/strategies/${strategyId}`)
      .then(handleResponse)
      .then((res: any) => res?.data ?? res);
  },

  // ---- 净值曲线 ----
  async getNav(groupId: string): Promise<Array<{
    trade_date: string;
    total_nav: number;
    daily_return: number;
    regime: number;
    allocation?: Record<string, number>;
    per_strategy?: Record<string, number>;
  }>> {
    return request
      .get(`${BASE}/groups/${groupId}/nav`)
      .then(handleResponse)
      .then((res: any) => res.data ?? []);
  },

  // ---- 触发 & Rebalance ----
  async trigger(data: {
    composite_group_id: string;
    trade_date: string;
    end_date?: string;
    symbols?: string[];
  }): Promise<CompositeTriggerResult> {
    return request
      .post(`${BASE}/trigger`, data)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  async rebalance(groupId: string): Promise<RebalanceResult> {
    return request
      .post(`${BASE}/rebalance`, { composite_group_id: groupId })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  // ---- Capital 调整 ----
  async adjustCapital(strategyId: string, newCapital: number): Promise<any> {
    return request
      .post(`${BASE}/strategies/${strategyId}/capital`, {
        strategy_id: strategyId,
        new_capital: newCapital,
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },
};
