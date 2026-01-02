// quant_web/src/types/api/events.ts
// 策略管理API类型定义
import {
  Strategy,
  BacktestResult,
  StrategyPerformance,
  StrategyTemplate,
  TradeSignal,
  BacktestConfig
} from '@/types/entities/strategy';
import {ApiResponse, PaginatedResponse, PaginationParams, StrategyStatusInfo} from "@/types/api";

/**
 * 创建策略请求参数
 */
export interface CreateStrategyRequest {
  name: string;                      // 策略名称
  description: string;               // 策略描述
  code: string;                      // 策略代码
  parameters: Record<string, any>;   // 策略参数
  category?: string;                 // 策略分类
  tags?: string[];                   // 策略标签
}

/**
 * 更新策略请求参数
 */
export interface UpdateStrategyRequest {
  name?: string;                     // 策略名称
  description?: string;              // 策略描述
  code?: string;                     // 策略代码
  parameters?: Record<string, any>;  // 策略参数
  category?: string;                 // 策略分类
  tags?: string[];                   // 策略标签
}

/**
 * 回测请求参数
 */
export interface BacktestRequest {
  strategyId: string;                // 策略ID
  startDate: string;                 // 开始日期
  endDate: string;                   // 结束日期
  initialCapital: number;            // 初始资金
  commission: number;                // 手续费率
  slippage: number;                  // 滑点
  universe?: string[];               // 股票池
  parameters?: Record<string, any>;  // 回测参数覆盖
}

/**
 * 策略查询参数
 */
export interface StrategyQueryParams extends PaginationParams {
  name?: string;                     // 策略名称模糊查询
  category?: string;                 // 策略分类筛选
  status?: string;                   // 策略状态筛选
  tags?: string[];                   // 标签筛选
}

/**
 * 策略运行参数
 */
export interface RunStrategyRequest {
  strategyId: string;                // 策略ID
  initialCapital?: number;           // 初始资金
  parameters?: Record<string, any>;  // 运行参数
}

/**
 * 策略停止参数
 */
export interface StopStrategyRequest {
  strategyId: string;                // 策略ID
  reason?: string;                   // 停止原因
}

// 响应类型定义
export interface StrategyListResponse extends PaginatedResponse<Strategy> {}
export interface StrategyDetailResponse extends ApiResponse<Strategy> {}
export interface BacktestResponse extends ApiResponse<BacktestResult> {}
export interface StrategyStatusResponse extends ApiResponse<StrategyStatusInfo> {}
export interface StrategySignalResponse extends ApiResponse<TradeSignal[]> {}
export interface StrategyPerformanceResponse extends ApiResponse<StrategyPerformance> {}
export interface StrategyTemplateResponse extends ApiResponse<StrategyTemplate[]> {}