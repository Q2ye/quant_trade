// Strategy shared constants — shared param definitions for StrategyList and StrategyEditor
export const PARAM_LABELS: Record<string, string> = {
  fastPeriod: "快线周期",
  slowPeriod: "慢线周期",
  tradeSize: "仓位比例",
};

export const PARAM_DESCS: Record<string, string> = {
  fastPeriod: "短期均线周期，通常5-20",
  slowPeriod: "长期均线周期，通常20-60",
  tradeSize: "每次交易仓位比例，0-1之间",
};

export const PARAM_MINS: Record<string, number> = {
  fastPeriod: 1,
  slowPeriod: 5,
  tradeSize: 0.1,
};

export const PARAM_MAXS: Record<string, number> = {
  fastPeriod: 50,
  slowPeriod: 100,
  tradeSize: 1.0,
};

export const PARAM_STEPS: Record<string, number> = {
  fastPeriod: 1,
  slowPeriod: 5,
  tradeSize: 0.05,
};

export const STRATEGY_TYPE_OPTIONS = [
  { label: "趋势跟踪", value: "trend" },
  { label: "套利策略", value: "arbitrage" },
  { label: "市场中性", value: "market_neutral" },
];

export const STRATEGY_STATUS_MAP: Record<string, string> = {
  running: "success",
  stopped: "default",
  error: "error",
};

export const STRATEGY_STATUS_TEXT: Record<string, string> = {
  running: "运行中",
  stopped: "已停止",
  error: "异常",
};
