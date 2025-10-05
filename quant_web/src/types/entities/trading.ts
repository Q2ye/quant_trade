// quant_web/src/types/entities/trading.ts
// 交易相关实体

import {BaseEntity, OrderDirection, OrderStatus, OrderType} from './base';

/**
 * 委托订单
 */
export interface Order extends BaseEntity {
    order_id: string;              // 订单ID（平台生成）
    account_id: string;            // 账户ID
    user_id: string;               // 用户ID
    strategy_id?: string;          // 策略ID（如为策略下单）
    ts_code: string;               // 标的TS代码
    symbol: string;                // 标的交易代码
    name: string;                  // 标的名称
    order_type: OrderType;         // 订单类型
    direction: OrderDirection;     // 买卖方向
    price?: number;                // 委托价格（市价单可为空）
    volume: number;                // 委托数量（股）
    filled_volume: number;         // 已成交数量
    avg_filled_price?: number;     // 平均成交价
    status: OrderStatus;           // 订单状态
    submitted_at: string;          // 提交时间
    cancelled_at?: string;         // 撤销时间
    expires_at?: string;           // 过期时间
    reason?: string;               // 状态原因
    basket_id?: string;            // 篮子ID
    created_by?: string;           // 下单用户
}
/**
 * 成交记录
 */
export interface Trade extends BaseEntity {
    trade_id: string;              // 成交ID（券商生成）
    account_id: string;            // 账户ID
    order_id: string;              // 关联订单ID
    ts_code: string;               // 标的代码
    symbol: string;                // 标的交易代码
    name: string;                  // 标的名称
    price: number;                 // 成交价格
    volume: number;                // 成交数量
    amount: number;                // 成交金额
    commission: number;            // 佣金费用
    tax: number;                   // 印花税
    trade_time: string;            // 成交时间
    direction: OrderDirection;     // 买卖方向
    strategy_id?: string;          // 策略ID
}
/**
 * 持仓信息
 */
export interface Position extends BaseEntity {
    id: string;                    // 持仓ID
    user_id: string;               // 用户ID
    account_id: string;            // 账户ID
    ts_code: string;               // 标的代码
    symbol: string;                // 标的交易代码
    name: string;                  // 标的名称
    volume: number;                // 持仓数量
    available_volume: number;      // 可用数量（考虑T+1）
    cost_price: number;            // 成本价
    current_price: number;         // 当前价
    market_value: number;          // 持仓市值
    profit: number;                // 浮动盈亏
    profit_rate: number;           // 盈亏比例
    last_update: string;           // 最后更新时间
    industry?: string;             // 行业
}

/**
 * 账户信息
 */
export interface Account extends BaseEntity {
    id: string;                    // 账户ID
    user_id: string;               // 用户ID
    total_asset: number;           // 总资产
    cash: number;                  // 现金余额
    available_cash: number;        // 可用现金
    frozen_cash: number;           // 冻结资金
    market_value: number;          // 持仓市值
    today_pnl: number;             // 当日盈亏
    total_pnl: number;             // 累计盈亏
    today_commission: number;      // 当日佣金
    total_commission: number;      // 累计佣金
    today_return: number;          // 当日收益率
    total_return: number;          // 总收益率
    position_rate: number;         // 仓位比例
}

/**
 * 交易信号
 */
export interface TradingSignal {
    id: string;                    // 信号ID
    strategy_id: string;           // 策略ID
    ts_code: string;               // 标的代码
    symbol: string;                // 标的交易代码
    name: string;                  // 标的名称
    signal_type: 'buy' | 'sell' | 'hold'; // 信号类型
    signal_time: string;           // 信号时间
    current_price: number;         // 当前价格
    target_price?: number;         // 目标价格
    volume?: number;               // 建议数量
    strength: number;              // 信号强度
    reason: string;                // 信号原因
    confidence: number;            // 置信度
    status: 'pending' | 'executed' | 'expired' | 'cancelled'; // 信号状态
}

/**
 * 篮子订单
 */
export interface BasketOrder {
    id: string;                    // 篮子订单ID
    basket_id: string;             // 关联篮子ID
    name: string;                  // 订单名称
    status: 'pending' | 'executing' | 'completed' | 'cancelled'; // 订单状态
    total_value: number;           // 总委托金额
    executed_value: number;        // 已执行金额
    progress: number;              // 执行进度
    created_at: string;            // 创建时间
    completed_at?: string;         // 完成时间
    items: BasketOrderItem[];      // 订单项列表
}

/**
 * 篮子订单项
 */
export interface BasketOrderItem {
    id: string;                    // 订单项ID
    basket_order_id: string;       // 关联篮子订单ID
    ts_code: string;               // 标的代码
    symbol: string;                // 标的交易代码
    name: string;                  // 标的名称
    target_weight: number;         // 目标权重
    target_volume: number;         // 目标数量
    executed_volume: number;       // 已执行数量
    avg_price?: number;            // 平均成交价
    status: 'pending' | 'partial' | 'filled' | 'cancelled'; // 执行状态
}