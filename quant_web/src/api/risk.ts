// quant_web/src/api/risk.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";

/**
 * 风险管理API服务
 * 提供风险规则配置、风险事件监控和风险预警功能
 *
 * 后端响应格式（success_response 包裹）：
 *   { code: "SUCCESS", message: "操作成功", data: <实际数据>, detail: null, timestamp: "..." }
 * 本模块各方法自动解包 .data 字段
 */

// ==================== 规范类型定义（唯一真相源） ====================

/** 风控规则 */
export interface RiskRule {
  name: string;           // 规则名称（唯一标识）
  description: string;    // 规则描述
  enabled: boolean;       // 是否启用
  rule_type: string;      // 规则分类: position/account/blacklist/market
}

/** 风控事件 */
export interface RiskEvent {
  id?: number;
  event_type: string;          // 事件类型
  rule_name?: string;          // 触发规则名
  metric_name?: string;        // 相关指标名
  current_value?: number;      // 当前值
  threshold_value?: number;    // 阈值
  level: string;               // 告警级别: normal/warning/critical
  message: string;             // 事件描述
  signal_data?: Record<string, any>;  // 触发时的信号数据
  created_at?: string;         // 创建时间
}

/** 风险告警 */
export interface RiskAlert {
  id?: string;
  alert_type: string;
  level: string;           // warning / critical
  title: string;
  message: string;
  acknowledged: boolean;
  created_at?: string;
}

/** 风险指标 */
export interface RiskMetricsData {
  metrics: Record<string, number>;
  overall_risk_level: string;
  breach_count: number;
  breaches: Array<{ metric: string; value: number; threshold: number; level: string }>;
  drawdown?: number;
  position_ratio?: number;
  var?: number;
  volatility?: number;
  sharpe_ratio?: number;
}

/** 风险阈值 */
export interface RiskThresholdItem {
  metric_name: string;
  warning_threshold: number;
  critical_threshold: number;
  description: string;
  is_active: boolean;
}

/** 信号检查请求 */
export interface SignalCheckRequest {
  ts_code?: string;
  direction?: string;
  quantity?: number;
  price?: number;
  trade_amount?: number;
  total_asset?: number;
  available_cash?: number;
  position_value?: number;
  [key: string]: any;
}

/** 信号检查结果 */
export interface SignalCheckResult {
  passed: boolean;
  message: string;
}

/** 分页信息 */
export interface Pagination {
  page: number;
  page_size: number;
  total: number;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  pagination: Pagination;
}

// ==================== API 响应解包辅助 ====================

/**
 * 从 success_response 包裹中提取 data 字段
 * 后端格式: { code, message, data: <实际数据>, detail, timestamp }
 */
function unwrap<T>(response: any): T {
  if (response && typeof response === 'object' && 'data' in response) {
    return response.data as T;
  }
  return response as unknown as T;
}

// 类型安全的 API 辅助方法
function apiGet<T>(url: string, params?: any): Promise<T> {
  return request.get(url, { params }).then(handleResponse).then((res: any) => unwrap<T>(res));
}
function apiPost<T>(url: string, data?: any): Promise<T> {
  return request.post(url, data).then(handleResponse).then((res: any) => unwrap<T>(res));
}
function apiPut<T>(url: string, data?: any): Promise<T> {
  return request.put(url, data).then(handleResponse).then((res: any) => unwrap<T>(res));
}

// ==================== API 方法 ====================

export default {
  // --- 规则管理 ---

  /** 获取所有风控规则 */
  async getRiskRules(): Promise<{ rules: RiskRule[]; total: number }> {
    return apiGet("/quantTrade/risk/rules");
  },

  /** 启用/禁用规则 */
  async toggleRiskRule(ruleName: string, enabled: boolean): Promise<{ rule_name: string; enabled: boolean }> {
    return apiPut(`/quantTrade/risk/rules/${encodeURIComponent(ruleName)}`, { enabled });
  },

  // --- 信号检查 ---

  /** 对交易信号执行风控检查 */
  async checkSignal(signalData: SignalCheckRequest): Promise<SignalCheckResult> {
    return apiPost("/quantTrade/risk/check", signalData);
  },

  // --- 风险指标 ---

  /** 获取实时风险指标 */
  async getRiskMetrics(): Promise<RiskMetricsData> {
    return apiGet("/quantTrade/risk/metrics");
  },

  // --- 风险事件 ---

  /** 分页查询风险事件 */
  async getRiskEvents(params?: {
    level?: string;
    rule_name?: string;
    start_time?: string;
    end_time?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<RiskEvent>> {
    return apiGet("/quantTrade/risk/events", params);
  },

  // --- 告警 ---

  /** 获取活跃的风险告警 */
  async getRiskAlerts(params?: {
    alert_level?: string;
  }): Promise<PaginatedResponse<RiskAlert>> {
    return apiGet("/quantTrade/risk/alerts", params);
  },

  /** 确认风险告警 */
  async acknowledgeRiskAlert(alertId: string): Promise<{ alert_id: string; acknowledged: boolean }> {
    return apiPost(`/quantTrade/risk/alerts/${alertId}/acknowledge`);
  },

  // --- 阈值配置 ---

  /** 获取阈值配置 */
  async getThresholds(): Promise<{ thresholds: RiskThresholdItem[] }> {
    return apiGet("/quantTrade/risk/thresholds");
  },

  /** 更新阈值 */
  async updateThreshold(
    metricName: string,
    data: {
      warning_threshold?: number;
      critical_threshold?: number;
      description?: string;
      is_active?: boolean;
    }
  ): Promise<RiskThresholdItem> {
    return apiPut(`/quantTrade/risk/thresholds/${encodeURIComponent(metricName)}`, data);
  },

  /** 健康检查 */
  async healthCheck(): Promise<{ status: string; module: string; timestamp: string }> {
    return apiGet("/quantTrade/risk/health");
  },
};
