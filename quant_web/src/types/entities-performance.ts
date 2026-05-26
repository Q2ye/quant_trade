// 绩效分析实体
// quant_web/src/types/entities/performance.ts

/**
 * 账户每日绩效快照
 */
export interface AccountDailyPerformance {
  id: string; // 记录ID
  user_id: string; // 用户ID
  trade_date: string; // 交易日期
  total_asset: number; // 总资产（现金+市值）
  cash: number; // 现金余额
  market_value: number; // 持仓市值
  daily_pnl: number; // 当日盈亏
  daily_return: number; // 当日收益率
  created_at: string; // 创建时间
}

/**
 * 策略每日绩效指标
 */
export interface StrategyDailyPerformance {
  id: string; // 记录ID
  strategy_id: string; // 策略ID
  trade_date: string; // 交易日期
  daily_return: number; // 当日收益率
  total_return: number; // 累计收益率
  max_drawdown: number; // 最大回撤
  sharpe_ratio?: number; // 夏普比率
  created_at: string; // 创建时间
}

/**
 * 综合绩效指标
 */
export interface PerformanceMetrics {
  total_return: number; // 总收益率
  annual_return: number; // 年化收益率
  sharpe_ratio?: number; // 夏普比率（风险调整后收益）
  max_drawdown: number; // 最大回撤
  volatility: number; // 波动率
  win_rate: number; // 胜率
  profit_factor: number; // 盈利因子（总盈利/总亏损）
  total_trades: number; // 总交易次数
  avg_trade: number; // 平均每笔交易收益
  sortino_ratio?: number; // 索提诺比率（只考虑下行风险）
  calmar_ratio?: number; // 卡尔玛比率（年化收益/最大回撤）
}

/**
 * 净值曲线数据点
 */
export interface EquityPoint {
  date: string; // 日期
  equity: number; // 净值
  return: number; // 收益率
  drawdown: number; // 回撤
}

/**
 * 回测交易记录
 */
export interface BacktestTrade {
  id: string; // 交易ID
  trade_time: string; // 交易时间
  ts_code: string; // 标的代码
  direction: "buy" | "sell"; // 交易方向
  price: number; // 成交价格
  volume: number; // 成交数量
  value: number; // 成交金额
  commission: number; // 佣金费用
  tax: number; // 税费
  pnl?: number; // 盈亏金额
}

/**
 * 策略绩效数据
 */
export interface StrategyPerformance {
  equityCurve: EquityPoint[];
  metrics: PerformanceMetrics;
}

/**
 * 账户绩效数据
 */
export interface AccountPerformance {
  equityCurve: EquityPoint[];
  metrics: PerformanceMetrics;
}
