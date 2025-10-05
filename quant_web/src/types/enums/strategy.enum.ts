// 策略相关枚举类型定义
export enum StrategyStatus {
  DRAFT = 'draft',          // 草稿
  RUNNING = 'running',      // 运行中
  STOPPED = 'stopped',      // 已停止
  PAUSED = 'paused',        // 暂停
  ERROR = 'error',          // 错误
  DISABLED = 'disabled'     // 禁用
}

export enum StrategyType {
  ALPHA = 'alpha',          // Alpha策略
  CTA = 'cta',              // CTA策略
  ARBITRAGE = 'arbitrage',  // 套利策略
  MARKET_MAKING = 'market_making', // 做市策略
  FACTOR = 'factor',        // 因子策略
  ML = 'machine_learning',  // 机器学习策略
  QUANT = 'quantitative',   // 量化策略
  MANUAL = 'manual'         // 手动策略
}

export enum StrategyCategory {
  STOCK_SELECTION = 'stock_selection',  // 选股策略
  TIMING = 'timing',                    // 择时策略
  PORTFOLIO = 'portfolio',              // 组合策略
  HEDGING = 'hedging',                  // 对冲策略
  ARBITRAGE = 'arbitrage',              // 套利策略
  HIGH_FREQUENCY = 'high_frequency',    // 高频策略
  EVENT_DRIVEN = 'event_driven'         // 事件驱动
}

export enum BacktestStatus {
  PENDING = 'pending',      // 等待中
  RUNNING = 'running',      // 运行中
  COMPLETED = 'completed',  // 已完成
  FAILED = 'failed',        // 失败
  CANCELLED = 'cancelled'   // 已取消
}

export enum SignalType {
  BUY = 'buy',              // 买入信号
  SELL = 'sell',            // 卖出信号
  HOLD = 'hold',            // 持有信号
  SHORT = 'short',          // 做空信号
  COVER = 'cover',          // 平仓信号
  ALERT = 'alert'           // 预警信号
}

export enum SignalStrength {
  WEAK = 'weak',            // 弱信号
  MEDIUM = 'medium',        // 中等信号
  STRONG = 'strong',        // 强信号
  VERY_STRONG = 'very_strong' // 极强信号
}

export enum ParameterType {
  NUMBER = 'number',
  STRING = 'string',
  BOOLEAN = 'boolean',
  ARRAY = 'array',
  OBJECT = 'object',
  SELECT = 'select'
}

export enum OptimizationMethod {
  GRID = 'grid',            // 网格搜索
  GENETIC = 'genetic',      // 遗传算法
  BAYESIAN = 'bayesian',    // 贝叶斯优化
  RANDOM = 'random'         // 随机搜索
}

export enum FactorType {
  VALUE = 'value',          // 价值因子
  GROWTH = 'growth',        // 成长因子
  QUALITY = 'quality',      // 质量因子
  MOMENTUM = 'momentum',    // 动量因子
  VOLATILITY = 'volatility', // 波动率因子
  LIQUIDITY = 'liquidity',  // 流动性因子
  TECHNICAL = 'technical',  // 技术因子
  FUNDAMENTAL = 'fundamental' // 基本面因子
}