/**
 * 仪表盘状态类型定义
 * 负责管理交易仪表盘的各种实时数据和图表状态
 * 对应 store/modules/dashboard.ts 中的状态结构
 */

import { DashboardData, RealTimeDataEvent } from '@/types/entities/dashboard';

/**
 * 仪表盘状态接口
 * 包含仪表盘所有实时数据、加载状态和配置信息
 */
export interface DashboardState {
  /**
   * 仪表盘核心数据
   * 包含资产信息、绩效图表、风险矩阵等关键数据
   */
  dashboardData: DashboardData;

  /**
   * 实时更新数据流
   * 存储市场数据、信号、价格等实时更新事件
   * 最多保留50条记录，采用先进先出策略
   */
  realTimeUpdates: RealTimeDataEvent[];

  /**
   * 全局加载状态
   * 控制仪表盘数据的加载指示器
   */
  loading: boolean;

  /**
   * 最后更新时间
   * 记录数据最后刷新的时间戳，用于显示数据新鲜度
   */
  lastUpdate: string;
}

/**
 * 仪表盘状态默认值
 * 用于初始化仪表盘状态
 */
export const defaultDashboardState: DashboardState = {
  dashboardData: {
    totalAssets: 0,
    dailyPnL: 0,
    positionValue: 0,
    availableCash: 0,
    returnRate: 0,
    performanceChart: [],
    riskMatrix: {
      positionDistribution: [],
      industryExposure: [],
      var: 0
    },
    realTimeSignals: [],
    marketSentiment: {
      advancing: 0,
      declining: 0,
      unchanged: 0,
      volume: 0,
      northbound: 0,
      marketHeat: 0
    },
    positions: [],
    todayTrades: []
  },
  realTimeUpdates: [],
  loading: false,
  lastUpdate: ''
};

/**
 * 仪表盘状态工具函数
 */
export const DashboardStateUtils = {
  /**
   * 检查是否需要刷新数据
   * @param state 仪表盘状态
   * @param threshold 刷新阈值（毫秒），默认5分钟
   * @returns 是否需要刷新
   */
  shouldRefresh(state: DashboardState, threshold: number = 5 * 60 * 1000): boolean {
    if (!state.lastUpdate) return true;
    const lastUpdateTime = new Date(state.lastUpdate).getTime();
    const currentTime = Date.now();
    return currentTime - lastUpdateTime > threshold;
  },

  /**
   * 获取最新实时更新
   * @param state 仪表盘状态
   * @param count 获取数量，默认10条
   * @returns 最新的实时更新记录
   */
  getLatestUpdates(state: DashboardState, count: number = 10): RealTimeDataEvent[] {
    return state.realTimeUpdates.slice(0, count);
  },

  /**
   * 根据类型过滤实时更新
   * @param state 仪表盘状态
   * @param type 更新类型
   * @returns 过滤后的更新记录
   */
  filterUpdatesByType(state: DashboardState, type: string): RealTimeDataEvent[] {
    return state.realTimeUpdates.filter(update => update.type === type);
  },

  /**
   * 获取仪表盘关键指标
   * @param state 仪表盘状态
   * @returns 关键指标对象
   */
  getKeyMetrics(state: DashboardState) {
    const data = state.dashboardData;
    return {
      totalAssets: data.totalAssets,
      dailyPnL: data.dailyPnL,
      positionValue: data.positionValue,
      availableCash: data.availableCash,
      returnRate: data.returnRate,
      positionCount: data.positions.length,
      signalCount: data.realTimeSignals.length
    };
  }
};

/**
 * 仪表盘状态类型保护函数
 */
export function isDashboardState(state: any): state is DashboardState {
  return (
    state &&
    typeof state === 'object' &&
    'dashboardData' in state &&
    'realTimeUpdates' in state &&
    'loading' in state &&
    'lastUpdate' in state
  );
}

/**
 * 仪表盘状态验证函数
 */
export function validateDashboardState(state: any): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!state) {
    errors.push('状态对象不能为空');
    return { isValid: false, errors };
  }

  if (typeof state.loading !== 'boolean') {
    errors.push('loading 必须是布尔类型');
  }

  if (typeof state.lastUpdate !== 'string') {
    errors.push('lastUpdate 必须是字符串类型');
  }

  if (!Array.isArray(state.realTimeUpdates)) {
    errors.push('realTimeUpdates 必须是数组类型');
  }

  if (!state.dashboardData) {
    errors.push('dashboardData 不能为空');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}