// quant_web/src/api/monitor.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";

/** 策略健康检查结果（基建设计 §三） */
export interface StrategyHealthItem {
  strategy_id: string;
  name: string;
  status: "healthy" | "warning" | "stop" | "insufficient" | "not_found";
  alerts: string[];
  metrics: {
    recent_days: number;
    history_days: number;
    recent_return: number;
    recent_mdd: number;
    hist_avg_return: number | null;
    hist_max_mdd: number | null;
    recent_signal_count: number;
    hist_monthly_signal_avg: number | null;
  };
}

/** 实盘监控「三个数」汇总（当日盈亏 / 总回撤 / 可用资金 + 阈值预警） */
export interface LiveSummary {
  daily_pnl: number;
  daily_return: number;
  drawdown: number;
  available_cash: number;
  total_balance: number;
  available_cash_ratio: number;
  overall_level: "normal" | "warning" | "critical";
  alerts: Array<{
    metric: string;
    label: string;
    value: number;
    level: "normal" | "warning" | "critical";
    warning_threshold: number;
    critical_threshold: number;
    unit: string;
  }>;
}

/** 监控中心 API */
export const monitorAPI = {
  /** 策略健康度检查：不传 strategyId 查全部运行中策略 */
  async getStrategyHealth(strategyId = ""): Promise<StrategyHealthItem[]> {
    return request
      .get("/quantTrade/monitor/strategies/health", {
        params: strategyId ? { strategy_id: strategyId } : {},
      })
      .then(handleResponse)
      .then((res: any) => {
        const data = res?.data ?? res;
        return Array.isArray(data) ? data : [];
      });
  },

  /** 实盘监控「三个数」汇总 */
  async getLiveSummary(): Promise<LiveSummary | null> {
    return request
      .get("/quantTrade/monitor/live-summary")
      .then(handleResponse)
      .then((res: any) => res?.data ?? res ?? null)
      .catch(() => null);
  },
};
