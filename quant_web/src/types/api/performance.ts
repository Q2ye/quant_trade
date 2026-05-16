// quant_web/src/types/api/performance.ts

import {
  StrategyPerformance,
  PerformanceMetrics,
} from "@/types/entities/performance";
import { EquityPoint } from "@/types/api/strategy";

/**
 * 策略列表项
 */
export interface StrategyListItem {
  strategyId: string;
  strategyName: string;
  totalReturn: number;
  annualReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  status: string;
}

/**
 * 当前策略详情
 */
export interface CurrentStrategy {
  id: string | null;
  detail: any;
  tradeRecords: any[];
}

/**
 * API响应格式
 */
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

/**
 * 绩效对比结果
 */
export interface PerformanceComparison {
  strategies: Array<{
    strategy_id: string;
    strategy_name: string;
    performance: StrategyPerformance;
  }>;
  benchmark: {
    code: string;
    name: string;
    performance: StrategyPerformance;
  };
  period: {
    start_date: string;
    end_date: string;
  };
}

/**
 * 账户信息（用于API响应）
 */
export interface AccountInfo {
  equityCurve: EquityPoint[];
  metrics: PerformanceMetrics;
}
