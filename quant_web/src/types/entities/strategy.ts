// quant_web/src/types/entities/events.ts
// 策略相关实体
import { BaseEntity } from "./base";
import { PerformanceMetrics, EquityPoint } from "@/types";

/**
 * 策略实例
 */
export interface Strategy extends BaseEntity {
  name: string; // 策略名称
  user_id: string; // 创建者用户ID
  description: string; // 策略描述
  class_name: string; // 策略类名（Python类名）
  module_path: string; // 策略文件路径
  status: "running" | "stopped" | "error"; // 运行状态
  parameters: Record<string, any>; // 策略参数（JSON格式）
  version?: string; // 策略版本
  category?: string; // 策略分类
  tags?: string[]; // 策略标签
  last_run?: string; // 最后运行时间
  next_run?: string; // 下次运行时间
}

/**
 * 策略运行记录
 */
export interface StrategyRun extends BaseEntity {
  strategy_id: string; // 策略ID
  started_at: string; // 开始时间
  stopped_at?: string; // 结束时间
  status: "running" | "completed" | "stopped" | "error"; // 运行状态
  log_path?: string; // 日志文件路径
  error_message?: string; // 错误信息
  performance?: PerformanceMetrics; // 运行绩效
}

/**
 * 回测任务
 */
export interface BacktestTask extends BaseEntity {
  id: string; // 任务ID
  user_id: string; // 用户ID
  strategy_id: string; // 策略ID
  name: string; // 回测名称
  description?: string; // 回测描述
  status: "pending" | "running" | "completed" | "failed" | "cancelled"; // 任务状态
  config: BacktestConfig; // 回测配置
  progress: number; // 进度（0-100）
  result?: BacktestResult; // 回测结果
  error_message?: string; // 错误信息
  started_at?: string; // 开始时间
  completed_at?: string; // 完成时间
}

/**
 * 回测配置参数
 */
export interface BacktestConfig {
  start_date: string; // 开始日期
  end_date: string; // 结束日期
  initial_capital: number; // 初始资金
  commission: number; // 手续费率
  slippage: number; // 滑点设置
  universe: string[]; // 股票池
  benchmark?: string; // 基准指数
  frequency: "daily" | "minute" | "weekly" | "monthly"; // 数据频率
}

/**
 * 回测结果
 */
export interface BacktestResult {
  id: string; // 结果ID
  strategy_id: string; // 策略ID
  total_return: number; // 总收益率
  annual_return: number; // 年化收益率
  sharpe_ratio: number; // 夏普比率
  max_drawdown: number; // 最大回撤
  win_rate: number; // 胜率
  total_trades: number; // 总交易次数
  equity_curve: EquityPoint[]; // 净值曲线
  trades: BacktestTrade[]; // 交易记录
  performance: PerformanceMetrics; // 绩效指标
  benchmark_comparison?: BenchmarkComparison; // 基准对比
}

/**
 * 回测交易记录
 */
export interface BacktestTrade {
  timestamp: string; // 交易时间
  symbol: string; // 标的代码
  direction: "buy" | "sell"; // 交易方向
  price: number; // 交易价格
  volume: number; // 交易数量
  commission: number; // 手续费
  trade_id?: string; // 交易ID
}

/**
 * 回测持仓
 */
export interface BacktestPosition {
  date: string; // 日期
  symbol: string; // 标的代码
  volume: number; // 持仓数量
  costPrice: number; // 成本价
  marketValue: number; // 市值
}

/**
 * 基准对比分析
 */
export interface BenchmarkComparison {
  strategy_return: number; // 策略收益率
  benchmark_return: number; // 基准收益率
  alpha: number; // 阿尔法（超额收益）
  beta: number; // 贝塔（市场相关性）
  information_ratio: number; // 信息比率
  tracking_error: number; // 跟踪误差
}

/**
 * 策略交易信号
 */
export interface TradeSignal {
  id: string; // 信号ID
  strategy_id: string; // 策略ID
  ts_code: string; // 标的代码
  signal_type: "buy" | "sell" | "hold"; // 信号类型
  signal_time: string; // 信号时间
  price?: number; // 触发价格
  strength?: number; // 信号强度（0-1）
  reason?: string; // 信号原因
  created_at: string; // 创建时间
}

/**
 * 策略模板
 */
export interface StrategyTemplate {
  id: string; // 模板ID
  name: string; // 模板名称
  description: string; // 模板描述
  category: string; // 策略分类
  code_template: string; // 代码模板
  parameters: StrategyParameter[]; // 参数配置
  tags: string[]; // 标签
}

/**
 * 策略参数定义
 */
export interface StrategyParameter {
  name: string; // 参数名称
  type: "number" | "string" | "boolean" | "array"; // 参数类型
  default: any; // 默认值
  min?: number; // 最小值（数字类型）
  max?: number; // 最大值（数字类型）
  step?: number; // 步长（数字类型）
  options?: any[]; // 可选值（选择类型）
  description: string; // 参数描述
}

/**
 * 策略状态信息
 */
export interface StrategyStatusInfo {
  strategyId: string; // 策略ID
  status: "running" | "stopped" | "error"; // 运行状态
  startedAt?: string; // 启动时间
  stoppedAt?: string; // 停止时间
  errorMessage?: string; // 错误信息
  performance?: StrategyPerformance; // 实时绩效
}

/**
 * 策略绩效
 */
export interface StrategyPerformance {
  total_return: number; // 总收益
  daily_return: number; // 日收益
  sharpe_ratio: number; // 夏普比率
  max_drawdown: number; // 最大回撤
  win_rate: number; // 胜率
  total_trades: number; // 总交易数
  position_count: number; // 持仓数量
  last_updated: string; // 最后更新时间
}
