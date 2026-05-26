// quant_web/src/api/risk.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import { ApiResponse, PaginatedResponse, RiskAlertMessage } from "@/types";
import { RiskRule } from "@/types";

/**
 * 风险管理API服务
 * 提供风险规则配置、风险事件监控和风险预警功能
 */

export interface RiskEvent {
  id: number;
  rule_id: number;
  strategy_id?: string;
  user_id: number;
  event_type: string;
  event_message: string;
  trigger_value: any;
  action_taken?: string;
  created_at: string;
}

export interface RiskRuleCreate {
  rule_name: string;
  rule_type: string;
  condition: any;
  action: string;
  is_active?: boolean;
}

export interface RiskQueryParams {
  level?: "low" | "medium" | "high" | "critical";
  type?: string;
  start_time?: string;
  end_time?: string;
  page?: number;
  limit?: number;
}

export default {
  /**
   * 获取风险规则列表
   * @param token 认证令牌
   * @returns 风险规则数组
   */
  async getRiskRules(token: string): Promise<RiskRule[]> {
    return request
      .get("/quantTrade/risk/rules", { params: { token } })
      .then(handleResponse)
      .then((data: ApiResponse<RiskRule[]>) => data.data);
  },

  /**
   * 创建风险规则
   * @param ruleData 规则创建参数
   * @param token 认证令牌
   * @returns 新创建的风险规则
   */
  async createRiskRule(
    ruleData: RiskRuleCreate,
    token: string,
  ): Promise<RiskRule> {
    return request
      .post("/quantTrade/risk/rules", ruleData, { params: { token } })
      .then(handleResponse)
      .then((data: ApiResponse<RiskRule>) => data.data);
  },

  /**
   * 更新风险规则
   * @param ruleId 规则ID
   * @param ruleData 规则更新参数
   * @param token 认证令牌
   * @returns 更新后的风险规则
   */
  async updateRiskRule(
    ruleId: number,
    ruleData: Partial<RiskRuleCreate>,
    token: string,
  ): Promise<RiskRule> {
    return request
      .put(`/risk/rules/${ruleId}`, ruleData, { params: { token } })
      .then(handleResponse)
      .then((data: ApiResponse<RiskRule>) => data.data);
  },

  /**
   * 删除风险规则
   * @param ruleId 规则ID
   * @param token 认证令牌
   * @returns 删除操作结果
   */
  async deleteRiskRule(ruleId: number, token: string): Promise<void> {
    return request
      .delete(`/risk/rules/${ruleId}`, { params: { token } })
      .then(handleResponse);
  },

  /**
   * 获取风险事件列表
   * @param params 查询参数
   * @returns 风险事件数组
   */
  async getRiskEvents(
    params?: RiskQueryParams,
  ): Promise<PaginatedResponse<RiskEvent>> {
    return request
      .get("/quantTrade/risk/events", { params })
      .then(handleResponse)
      .then((data: PaginatedResponse<RiskEvent>) => data);
  },

  /**
   * 获取实时风险预警
   * @returns 风险预警消息数组
   */
  async getRiskAlerts(): Promise<RiskAlertMessage[]> {
    return request
      .get("/quantTrade/risk/alerts")
      .then(handleResponse)
      .then((data: ApiResponse<RiskAlertMessage[]>) => data.data);
  },

  /**
   * 确认风险预警
   * @param alertId 预警ID
   * @returns 确认操作结果
   */
  async acknowledgeRiskAlert(alertId: string): Promise<void> {
    return request
      .post(`/risk/alerts/${alertId}/acknowledge`)
      .then(handleResponse);
  },

  /**
   * 获取风险指标统计
   * @returns 风险统计信息
   */
  async getRiskMetrics(): Promise<{
    total_alerts: number;
    high_risk_count: number;
    today_events: number;
    active_rules: number;
  }> {
    return request
      .get("/quantTrade/risk/metrics")
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data.data);
  },
};
