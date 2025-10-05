// quant_web/src/types/entities/basket.ts
import { BaseEntity } from './base';
import { PaginationParams } from '@/types';

/**
 * 篮子成分项：篮子中的单个标的配置
 */
export interface BasketItem {
  id: string;                    // 成分项唯一ID
  basket_id: string;             // 所属篮子ID
  symbol: string;                // 股票代码
  name?: string;                 // 股票名称（可选）
  weight: number;                // 权重（0-1）
  industry?: string;             // 行业（可选）
  current_price?: number;        // 当前价格
  market_value?: number;         // 当前市值
  created_at?: string;           // 创建时间
}

/**
 * 篮子统计信息
 */
export interface BasketStatistics {
  totalStocks: number;               // 总股票数
  totalWeight: number;               // 总权重
  industryDistribution: Record<string, number>; // 行业分布
  marketCapDistribution: {           // 市值分布
    large: number;                   // 大盘股权重
    medium: number;                  // 中盘股权重
    small: number;                   // 小盘股权重
  };
  peStatistics: {                    // PE统计
    average: number;                 // 平均PE
    median: number;                  // 中位数PE
    min: number;                     // 最小PE
    max: number;                     // 最大PE
  };
}

/**
 * 篮子绩效分析
 */
export interface BasketPerformance {
  basketId: string;                  // 篮子ID
  period: string;                    // 分析周期
  returns: number;                   // 总收益率
  volatility: number;                // 波动率
  maxDrawdown: number;               // 最大回撤
  sharpeRatio: number;               // 夏普比率
  alpha?: number;                    // Alpha
  beta?: number;                     // Beta
  informationRatio?: number;         // 信息比率
  annualReturn?: number;             // 年化收益率
}

/**
 * 交易篮子：用于管理一组相关的投资标的
 */
export interface Basket extends BaseEntity {
  id: string;                        // 篮子ID
  name: string;                      // 篮子名称
  description?: string;              // 篮子描述信息
  items: BasketItem[];               // 篮子成分股列表 - 统一使用items
  tags: string[];                    // 标签
  isPublic: boolean;                 // 是否公开
  createdBy: string;                 // 创建者用户ID
  createdAt: string;                 // 创建时间
  updatedAt: string;                 // 更新时间
  statistics?: BasketStatistics;     // 篮子统计信息
  total_weight?: number;             // 总权重（兼容旧字段）
}

/**
 * 创建篮子请求参数
 */
export interface CreateBasketRequest {
  name: string;                      // 篮子名称
  description?: string;              // 篮子描述
  items: BasketItem[];               // 篮子成分
  tags?: string[];                   // 标签
  isPublic?: boolean;                // 是否公开
}

/**
 * 更新篮子请求参数
 */
export interface UpdateBasketRequest {
  name?: string;                     // 篮子名称
  description?: string;              // 篮子描述
  items?: BasketItem[];              // 篮子成分
  tags?: string[];                   // 标签
  isPublic?: boolean;                // 是否公开
}

/**
 * 篮子查询参数
 */
export interface BasketQueryParams extends PaginationParams {
  name?: string;                     // 篮子名称模糊查询
  tags?: string[];                   // 标签筛选
  isPublic?: boolean;                // 公开状态筛选
  createdBy?: string;                // 创建人筛选
}

/**
 * 实时篮子数据
 */
export interface RealtimeBasketData {
  basketId: string;
  currentValue: number;
  dailyChange: number;
  dailyChangePercent: number;
  lastUpdated: string;
}

/**
 * 篮子回测结果
 */
export interface BacktestResult {
  basketId: string;
  period: string;
  returns: number[];
  dates: string[];
  benchmarkReturns?: number[];
}

/**
 * 简化的篮子项（用于store模块）
 */
export interface SimpleBasketItem {
  symbol: string;
  weight: number;
  name?: string;
}

/**
 * 简化的篮子（用于store模块）
 */
export interface SimpleBasket {
  id: string;
  name: string;
  description: string;
  items: SimpleBasketItem[];
}

/**
 * 股票数据
 */
export interface StockData {
  symbol: string;
  name: string;
}

