// quant_web/src/types/api/strategy.ts
// 策略管理API类型定义
import { ApiResponse, PaginatedResponse, PaginationParams } from './base';
import { BacktestResult, StrategyPerformance } from './shared';

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

/**
 * 策略状态信息
 */
export interface StrategyStatusInfo {
  strategyId: string;                // 策略ID
  status: 'running' | 'stopped' | 'error'; // 运行状态
  startedAt?: string;                // 启动时间
  stoppedAt?: string;                // 停止时间
  errorMessage?: string;             // 错误信息
  performance?: StrategyPerformance; // 实时绩效
}

/**
 * 策略信号信息
 */
export interface StrategySignal {
  strategyId: string;                // 策略ID
  timestamp: string;                 // 信号时间
  symbol: string;                    // 标的代码
  signalType: 'buy' | 'sell' | 'hold'; // 信号类型
  price: number;                     // 信号价格
  strength: number;                  // 信号强度
  reason: string;                    // 信号原因
}

// 实体类型（从entities导入或本地定义）
export interface Strategy {
  id: string;
  name: string;
  description: string;
  code: string;
  parameters: Record<string, any>;
  category: string;
  tags: string[];
  status: string;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
}

export interface EquityPoint {
  date: string;
  equity: number;
  return: number;
}

export interface BacktestTrade {
  timestamp: string;
  symbol: string;
  direction: 'buy' | 'sell';
  price: number;
  volume: number;
  commission: number;
}

export interface BacktestPosition {
  date: string;
  symbol: string;
  volume: number;
  costPrice: number;
  marketValue: number;
}

// 响应类型定义
export interface StrategyListResponse extends PaginatedResponse<Strategy> {}
export interface StrategyDetailResponse extends ApiResponse<Strategy> {}
export interface BacktestResponse extends ApiResponse<BacktestResult> {}
export interface StrategyStatusResponse extends ApiResponse<StrategyStatusInfo> {}
export interface StrategySignalResponse extends ApiResponse<StrategySignal[]> {}
export interface StrategyPerformanceResponse extends ApiResponse<StrategyPerformance> {}