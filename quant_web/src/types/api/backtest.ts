// 回测管理API类型定义
// quant_web/src/types/api/events.ts
import { ApiResponse } from "@/types";
import { PaginatedResponse, PaginationParams, TimeRangeParams } from "./base";
import { BacktestResult, StrategyPerformance } from "./shared";

/**
 * 回测任务创建参数
 */
export interface CreateBacktestTaskRequest {
  name: string; // 回测任务名称
  strategyId: string; // 策略ID
  startDate: string; // 开始日期
  endDate: string; // 结束日期
  initialCapital: number; // 初始资金
  commission: number; // 手续费率
  slippage: number; // 滑点
  universe: string[]; // 股票池
  parameters?: Record<string, any>; // 策略参数覆盖
  benchmark?: string; // 基准指数
}

/**
 * 回测任务查询参数
 */
export interface BacktestQueryParams extends PaginationParams, TimeRangeParams {
  strategyId?: string; // 策略ID筛选
  status?: string; // 状态筛选
  name?: string; // 任务名称模糊查询
}

/**
 * 回测任务信息
 */
export interface BacktestTask {
  id: string; // 任务ID
  name: string; // 任务名称
  strategyId: string; // 策略ID
  strategyName: string; // 策略名称
  status: "pending" | "running" | "completed" | "failed" | "cancelled"; // 任务状态
  progress: number; // 进度百分比
  parameters: BacktestParameters; // 回测参数
  result?: BacktestResult; // 回测结果
  errorMessage?: string; // 错误信息
  startedAt?: string; // 开始时间
  completedAt?: string; // 完成时间
  createdAt: string; // 创建时间
  createdBy: string; // 创建用户
}

/**
 * 回测参数详情
 */
export interface BacktestParameters {
  startDate: string; // 开始日期
  endDate: string; // 结束日期
  initialCapital: number; // 初始资金
  commission: number; // 手续费率
  slippage: number; // 滑点
  universe: string[]; // 股票池
  benchmark?: string; // 基准指数
  strategyParameters: Record<string, any>; // 策略参数
}

/**
 * 回测对比参数
 */
export interface BacktestCompareRequest {
  taskIds: string[]; // 回测任务ID列表
  metrics: string[]; // 对比指标
}

/**
 * 参数优化请求
 */
export interface ParameterOptimizeRequest {
  strategyId: string; // 策略ID
  parameterRanges: {
    // 参数范围
    [key: string]: {
      min: number; // 最小值
      max: number; // 最大值
      step: number; // 步长
    };
  };
  optimizationTarget: string; // 优化目标指标
  startDate: string; // 开始日期
  endDate: string; // 结束日期
  initialCapital: number; // 初始资金
}

/**
 * 参数优化结果
 */
export interface ParameterOptimizeResult {
  taskId: string; // 优化任务ID
  strategyId: string; // 策略ID
  bestParameters: Record<string, any>; // 最优参数
  bestPerformance: StrategyPerformance; // 最优绩效
  parameterResults: Array<{
    // 参数组合结果
    parameters: Record<string, any>;
    performance: StrategyPerformance;
  }>;
  optimizationTarget: string; // 优化目标
  completedAt: string; // 完成时间
}

// 响应类型定义
export interface BacktestTaskResponse extends ApiResponse<BacktestTask> {}
export interface BacktestListResponse extends PaginatedResponse<BacktestTask> {}
export interface BacktestResultResponse extends ApiResponse<BacktestResult> {}
export interface BacktestCompareResponse extends ApiResponse<{
  tasks: BacktestTask[];
  comparison: Record<string, any>;
}> {}
export interface ParameterOptimizeResponse extends ApiResponse<ParameterOptimizeResult> {}
export interface BacktestProgressResponse extends ApiResponse<{
  taskId: string;
  progress: number;
  status: string;
  currentStep?: string;
}> {}
