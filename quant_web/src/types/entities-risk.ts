// 风险管理实体
// quant_web/src/types/entities/risk.ts
import { BaseEntity } from "./common";

/**
 * 风控规则配置
 */
export interface RiskRule extends BaseEntity {
  rule_name: string; // 规则名称
  rule_type: string; // 规则类型（position_limit/daily_loss_limit等）
  condition: Record<string, any>; // 触发条件（JSON格式）
  action: string; // 执行动作（alert/stop_strategy等）
  is_active: boolean; // 是否启用
  description?: string; // 规则描述
  severity: "low" | "medium" | "high"; // 风险严重程度
}

/**
 * 风控事件记录
 */
export interface RiskEvent extends BaseEntity {
  rule_id: string; // 触发的规则ID
  strategy_id?: string; // 关联策略ID（如为策略触发）
  user_id: string; // 关联用户ID
  event_type: string; // 事件类型
  event_message: string; // 事件描述
  trigger_value: Record<string, any>; // 触发时的数据快照
  action_taken?: string; // 已执行的动作
  resolved_at?: string; // 解决时间
  resolution?: string; // 解决说明
}

/**
 * 风险度量指标
 */
export interface RiskMetrics {
  current_drawdown: number; // 当前回撤
  var_95: number; // 95%置信度的风险价值
  expected_shortfall: number; // 期望损失（条件风险价值）
  portfolio_beta: number; // 组合贝塔值（市场相关性）
  concentration_risk: number; // 集中度风险
  liquidity_risk: number; // 流动性风险
}

/**
 * 持仓风险分析
 */
export interface PositionRisk {
  ts_code: string; // 标的代码
  position: number; // 持仓数量
  market_value: number; // 持仓市值
  unrealized_pnl: number; // 未实现盈亏
  risk_exposure: number; // 风险暴露
  concentration: number; // 集中度（占组合比例）
}

/**
 * 风险阈值配置
 */
export interface RiskThreshold {
  max_position_ratio: number; // 单股最大仓位比例
  max_daily_loss: number; // 单日最大亏损比例
  max_drawdown: number; // 最大回撤阈值
  var_limit: number; // 风险价值限额
  min_liquidity: number; // 最小流动性要求
}
