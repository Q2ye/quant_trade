/**
 * 策略元数据常量（v3.3 统一提取 — 消除 4 处重复）
 *
 * 来源：原 BUILTIN_META 在 StrategyList, StrategyTemplates, TemplateDetail, StrategyWorkspace 各定义一遍
 */

// 策略生命周期状态
export const STRATEGY_STATUS = {
  DRAFT: 'draft',
  BACKTESTED: 'backtested',
  RUNNING: 'running',
  PAUSED: 'paused',
  STOPPED: 'stopped',
  ERROR: 'error',
} as const

// 状态 → Naive UI Tag 类型
export const STATUS_TYPE_MAP: Record<string, 'default' | 'success' | 'warning' | 'info' | 'error'> = {
  draft: 'default',
  backtested: 'success',
  running: 'success',
  paused: 'info',
  stopped: 'warning',
  error: 'error',
}

// 状态 → 中文标签
export const STATUS_LABEL_MAP: Record<string, string> = {
  draft: '草稿',
  backtested: '已验证',
  running: '运行中',
  paused: '已暂停',
  stopped: '已停止',
  error: '异常',
  retired: '已淘汰',
}

// 已归档状态集合（停止/淘汰策略归入"已归档" Tab，数据保留只读）
// P1 修复：paused 从归档移除（paused 语义=可恢复的暂停，操作含 resume，归"运行中" Tab；否则与归档"只读"冲突）
export const ARCHIVED_STATUSES: string[] = ['stopped', 'retired']

// 每个状态可用的操作按钮
export const STATUS_ACTIONS: Record<string, string[]> = {
  draft: ['edit', 'backtest', 'delete'],
  backtested: ['edit', 'backtest', 'startLive', 'delete'],
  running: ['monitor', 'pause', 'stop'],
  paused: ['monitor', 'resume', 'stop'],
  stopped: ['edit', 'backtest', 'delete'],
  error: ['viewLog', 'edit', 'stop'],
}

// 内置策略模板元数据
export const BUILTIN_STRATEGIES: Record<string, {
  name: string
  type: string
  description: string
  params: Record<string, { label: string; type: string; default: any; min?: number; max?: number }>
}> = {
  ma_cross: {
    name: '双均线策略',
    type: '技术指标',
    description: '经典双均线交叉策略，金叉买入、死叉卖出',
    params: {
      fast_period: { label: '快线周期', type: 'int', default: 5, min: 2, max: 60 },
      slow_period: { label: '慢线周期', type: 'int', default: 20, min: 5, max: 120 },
      position_ratio: { label: '仓位比例', type: 'float', default: 0.1, min: 0.01, max: 1 },
      stop_loss: { label: '止损比例', type: 'float', default: -0.05, min: -0.2, max: 0 },
      take_profit: { label: '止盈比例', type: 'float', default: 0.15, min: 0.01, max: 1 },
    },
  },
  macd: {
    name: 'MACD 策略',
    type: '技术指标',
    description: '基于 MACD 金叉死叉的交易策略',
    params: {
      fast_period: { label: '快线周期', type: 'int', default: 12, min: 2, max: 60 },
      slow_period: { label: '慢线周期', type: 'int', default: 26, min: 5, max: 120 },
      signal_period: { label: '信号周期', type: 'int', default: 9, min: 2, max: 30 },
      stop_loss: { label: '止损比例', type: 'float', default: -0.05, min: -0.2, max: 0 },
      take_profit: { label: '止盈比例', type: 'float', default: 0.15, min: 0.01, max: 1 },
    },
  },
  factor: {
    name: '多因子策略',
    type: 'Alpha 策略',
    description: '多因子选股，z-score 标准化打分',
    params: {
      stock_pool_size: { label: '持仓数量', type: 'int', default: 10, min: 1, max: 50 },
      stop_loss: { label: '止损比例', type: 'float', default: -0.05, min: -0.2, max: 0 },
      take_profit: { label: '止盈比例', type: 'float', default: 0.15, min: 0.01, max: 1 },
    },
  },
  mean_reversion: {
    name: '均值回归策略',
    type: 'Alpha 策略',
    description: '基于 z-score 和 RSI 的均值回归',
    params: {
      zscore_threshold: { label: 'Z 分数阈值', type: 'float', default: 2.0, min: 1.0, max: 4.0 },
      stop_loss: { label: '止损比例', type: 'float', default: -0.05, min: -0.2, max: 0 },
      take_profit: { label: '止盈比例', type: 'float', default: 0.10, min: 0.01, max: 0.5 },
    },
  },
  industry_rotation: {
    name: '行业轮动策略',
    type: '轮动策略',
    description: '申万行业 ETF 轮动，趋势+量价+估值三因子评分',
    params: {
      trend_weight: { label: '趋势权重', type: 'float', default: 0.55, min: 0, max: 1 },
      volume_weight: { label: '量价权重', type: 'float', default: 0.30, min: 0, max: 1 },
      valuation_weight: { label: '估值权重', type: 'float', default: 0.15, min: 0, max: 1 },
      max_positions: { label: '最大持仓数', type: 'int', default: 3, min: 1, max: 10 },
    },
  },
  stock_low_high: {
    name: '低吸轮动策略',
    type: '轮动策略',
    description: '全市场强势股低吸轮动，MACD 金叉+量比+低吸位置',
    params: {
      max_positions: { label: '最大持仓数', type: 'int', default: 3, min: 1, max: 10 },
      stop_loss: { label: '止损比例', type: 'float', default: -0.04, min: -0.2, max: 0 },
      bear_max_pos: { label: '下跌市最大持仓', type: 'int', default: 1, min: 1, max: 5 },
      bear_stop_loss: { label: '下跌市止损', type: 'float', default: -0.04, min: -0.2, max: 0 },
    },
  },
  multi_asset_rotation: {
    name: '多资产轮动策略',
    type: '轮动策略',
    description: '跨资产 ETF 动量轮动，黄金/纳指/日经/港股/债券等 9 个品种',
    params: {
      stop_loss: { label: '止损比例', type: 'float', default: -0.09, min: -0.3, max: 0 },
      intraday_stop_loss: { label: '日内止损比例', type: 'float', default: -0.03, min: -0.1, max: 0 },
      cooling_period: { label: '止损冷却期(天)', type: 'int', default: 3, min: 1, max: 30 },
    },
  },
}

// 参数名 → 中文标签（全局映射）
export const PARAM_LABELS: Record<string, string> = {
  fast_period: '快线周期',
  slow_period: '慢线周期',
  signal_period: '信号周期',
  position_ratio: '仓位比例',
  stop_loss: '止损比例',
  take_profit: '止盈比例',
  trend_weight: '趋势权重',
  volume_weight: '量价权重',
  valuation_weight: '估值权重',
  max_positions: '最大持仓数',
  bear_max_pos: '下跌市最大持仓',
  bear_stop_loss: '下跌市止损',
  intraday_stop_loss: '日内止损',
  cooling_period: '冷却期(天)',
  stock_pool_size: '持仓数量',
  zscore_threshold: 'Z 分数阈值',
  min_volume: '最小成交量',
  volume_ma_period: '量均线周期',
}
