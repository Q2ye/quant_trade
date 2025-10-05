// 绩效分析
// quant_web/src/store/modules/performance.ts

import { Module } from 'vuex';
import { PerformanceState } from '@/types/state/module-states/performance-state';
import {
  StrategyListItem,
  PerformanceComparison
} from "@/types/api/performance";

// 导入绩效分析API服务
import performanceApi from '@/api/performance';
import {RootState} from "@/types";
import {AccountPerformance, StrategyPerformance} from "@/types/entities";

/**
 * 绩效分析Vuex模块
 * 负责管理策略和账户的绩效数据，包括：
 * - 账户绩效数据管理
 * - 策略绩效数据管理
 * - 绩效对比分析
 * - 策略列表管理
 * - 当前策略详情管理
 */
const performanceModule: Module<PerformanceState, RootState> = {
  // 启用命名空间，避免与其他模块的action/mutation命名冲突
  namespaced: true,

  /**
   * 模块状态定义
   * 存储绩效分析相关的所有数据状态
   */
  state: {
    // 账户绩效数据，按accountId索引存储
    accountPerformance: {},

    // 策略绩效数据，按strategyId索引存储
    strategyPerformance: {},

    // 策略对比分析结果数据
    comparisonData: null,

    // 分析报告缓存，按报告key索引
    analysisReports: {},

    // 加载状态管理，分别控制不同模块的loading状态
    loading: {
      account: false,      // 账户绩效加载状态
      strategy: false,     // 策略绩效加载状态
      comparison: false    // 对比分析加载状态
    },

    // 策略列表数据
    tlist: [],

    // 当前选中的策略详情
    currentStrategy: {
      id: null,           // 策略ID
      detail: {},         // 策略详细信息
      tradeRecords: []    // 策略交易记录
    }
  },

  /**
   * 状态变更方法
   * 所有状态变更都必须通过mutation进行，确保状态变更是同步的
   */
  mutations: {
    /**
     * 设置账户绩效数据
     * @param state - 模块状态
     * @param payload - 包含账户ID和绩效数据的负载对象
     * @param payload.accountId - 账户ID
     * @param payload.performance - 账户绩效数据
     */
    SET_ACCOUNT_PERFORMANCE(state, payload: { accountId: string; performance: AccountPerformance }) {
      state.accountPerformance[payload.accountId] = payload.performance;
    },

    /**
     * 设置策略绩效数据
     * @param state - 模块状态
     * @param payload - 包含策略ID和绩效数据的负载对象
     * @param payload.strategyId - 策略ID
     * @param payload.performance - 策略绩效数据
     */
    SET_STRATEGY_PERFORMANCE(state, payload: { strategyId: string; performance: StrategyPerformance }) {
      state.strategyPerformance[payload.strategyId] = payload.performance;
    },

    /**
     * 设置策略对比分析数据
     * @param state - 模块状态
     * @param data - 绩效对比分析结果数据
     */
    SET_COMPARISON_DATA(state, data: PerformanceComparison | null) {
      state.comparisonData = data;
    },

    /**
     * 设置分析报告数据
     * @param state - 模块状态
     * @param payload - 包含报告key和报告数据的负载对象
     * @param payload.key - 报告唯一标识key
     * @param payload.report - 报告数据
     */
    SET_ANALYSIS_REPORT(state, payload: { key: string; report: any }) {
      state.analysisReports[payload.key] = payload.report;
    },

    /**
     * 设置加载状态
     * @param state - 模块状态
     * @param payload - 包含加载类型和状态的负载对象
     * @param payload.type - 加载类型（account/strategy/comparison）
     * @param payload.value - 加载状态值（true/false）
     */
    SET_LOADING(state, payload: { type: keyof PerformanceState['loading']; value: boolean }) {
      state.loading[payload.type] = payload.value;
    },

    /**
     * 设置策略列表数据
     * @param state - 模块状态
     * @param list - 策略列表数据数组
     */
    SET_STRATEGY_LIST(state, list: StrategyListItem[]) {
      state.tlist = list;
    },

    /**
     * 设置当前选中的策略详情
     * @param state - 模块状态
     * @param payload - 包含策略ID和详情的负载对象
     * @param payload.id - 策略ID
     * @param payload.detail - 策略详细信息
     */
    SET_CURRENT_STRATEGY(state, payload: { id: string; detail: any }) {
      state.currentStrategy.id = payload.id;
      state.currentStrategy.detail = payload.detail;
    },

    /**
     * 设置当前策略的交易记录
     * @param state - 模块状态
     * @param trades - 交易记录数组
     */
    SET_CURRENT_STRATEGY_TRADES(state, trades: any[]) {
      state.currentStrategy.tradeRecords = trades;
    }
  },

  /**
   * 异步操作方法
   * 处理所有与后端的异步交互，调用API并提交mutation更新状态
   */
  actions: {
    /**
     * 获取账户绩效数据
     * @param context - Vuex上下文对象
     * @param context.commit - 提交mutation的方法
     * @param accountId - 账户ID
     * @returns 账户绩效数据Promise
     */
    async fetchAccountPerformance({ commit }, accountId: string) {
      // 设置账户加载状态为true
      commit('SET_LOADING', { type: 'account', value: true });
      try {
        // 调用API获取账户绩效数据
        const performance = await performanceApi.getAccountPerformance();
        // 提交mutation更新状态
        commit('SET_ACCOUNT_PERFORMANCE', { accountId, performance });
        return performance;
      } catch (error) {
        console.error('获取账户绩效失败:', error);
        throw error;
      } finally {
        // 无论成功失败，最终都要关闭加载状态
        commit('SET_LOADING', { type: 'account', value: false });
      }
    },

    /**
     * 获取策略绩效数据
     * @param context - Vuex上下文对象
     * @param context.commit - 提交mutation的方法
     * @param strategyId - 策略ID
     * @returns 策略绩效数据Promise
     */
    async fetchStrategyPerformance({ commit }, strategyId: string) {
      // 设置策略加载状态为true
      commit('SET_LOADING', { type: 'strategy', value: true });
      try {
        // 调用API获取策略绩效数据
        const performance = await performanceApi.getStrategyPerformance(strategyId);
        // 提交mutation更新状态
        commit('SET_STRATEGY_PERFORMANCE', { strategyId, performance });
        return performance;
      } catch (error) {
        console.error('获取策略绩效失败:', error);
        throw error;
      } finally {
        // 关闭策略加载状态
        commit('SET_LOADING', { type: 'strategy', value: false });
      }
    },

    /**
     * 执行策略绩效对比分析
     * @param context - Vuex上下文对象
     * @param context.commit - 提交mutation的方法
     * @param payload - 对比分析参数
     * @param payload.strategyIds - 要对比的策略ID数组
     * @param payload.benchmark - 基准策略代码（可选）
     * @param payload.startDate - 开始日期（可选）
     * @param payload.endDate - 结束日期（可选）
     * @returns 对比分析结果Promise
     */
    async compareStrategies({ commit }, payload: { strategyIds: string[]; benchmark?: string; startDate?: string; endDate?: string }) {
      // 设置对比分析加载状态为true
      commit('SET_LOADING', { type: 'comparison', value: true });
      try {
        // 调用API进行策略对比分析
        const comparisonData = await performanceApi.comparePerformance(
          payload.strategyIds,
          {
            benchmark: payload.benchmark,
            start_date: payload.startDate,
            end_date: payload.endDate
          }
        );
        // 提交mutation更新对比分析结果
        commit('SET_COMPARISON_DATA', comparisonData);
        return comparisonData;
      } catch (error) {
        console.error('策略对比失败:', error);
        throw error;
      } finally {
        // 关闭对比分析加载状态
        commit('SET_LOADING', { type: 'comparison', value: false });
      }
    },

    /**
     * 获取策略列表数据
     * @param context - Vuex上下文对象
     * @param context.commit - 提交mutation的方法
     * @returns 策略列表数据Promise
     */
    async fetchStrategyList({ commit }) {
      try {
        // 这里需要根据实际情况调用API获取策略列表
        // const response = await api.getStrategyList();

        // 模拟数据 - 实际项目中应替换为真实API调用
        const mockList: StrategyListItem[] = [
          {
            strategyId: '1',
            strategyName: '动量策略',
            totalReturn: 0.456,
            annualReturn: 0.152,
            sharpeRatio: 1.234,
            maxDrawdown: -0.156,
            status: 'running'
          },
          {
            strategyId: '2',
            strategyName: '均值回归策略',
            totalReturn: 0.234,
            annualReturn: 0.089,
            sharpeRatio: 0.987,
            maxDrawdown: -0.089,
            status: 'stopped'
          }
        ];
        // 提交mutation更新策略列表
        commit('SET_STRATEGY_LIST', mockList);
        return mockList;
      } catch (error) {
        console.error('获取策略列表失败:', error);
        throw error;
      }
    },

    /**
     * 获取当前策略的详细信息
     * @param context - Vuex上下文对象
     * @param context.commit - 提交mutation的方法
     * @param strategyId - 策略ID
     * @returns 策略详情数据Promise
     */
    async fetchCurrentStrategyDetail({ commit }, strategyId: string) {
      try {
        // 获取策略详情
        const detail = await performanceApi.getStrategyPerformance(strategyId);
        // 提交mutation更新当前策略
        commit('SET_CURRENT_STRATEGY', { id: strategyId, detail });
        return detail;
      } catch (error) {
        console.error('获取策略详情失败:', error);
        throw error;
      }
    }
  },

  /**
   * 计算属性getters
   * 提供对状态的派生数据和便捷访问方法
   */
  getters: {
    /**
     * 获取指定策略的核心绩效指标
     * @param state - 模块状态
     * @returns 函数，接收strategyId参数，返回策略核心指标
     */
    getStrategyMetrics: (state) => (strategyId: string) => {
      const performance = state.strategyPerformance[strategyId];
      if (!performance) return null;
      return {
        total_return: performance.metrics.total_return,
        sharpe_ratio: performance.metrics.sharpe_ratio,
        max_drawdown: performance.metrics.max_drawdown
      };
    },

    /**
     * 获取指定账户的绩效数据
     * @param state - 模块状态
     * @returns 函数，接收accountId参数，返回账户绩效数据
     */
    getAccountPerformance: (state) => (accountId: string) => {
      return state.accountPerformance[accountId];
    },

    /**
     * 获取指定类型的加载状态
     * @param state - 模块状态
     * @returns 函数，接收type参数，返回对应加载状态
     */
    isLoading: (state) => (type: keyof PerformanceState['loading']) => {
      return state.loading[type];
    },

    /**
     * 获取策略列表数据
     * @param state - 模块状态
     * @returns 策略列表数组
     */
    getStrategyList: (state) => {
      return state.tlist;
    },

    /**
     * 获取当前选中的策略信息
     * @param state - 模块状态
     * @returns 当前策略对象
     */
    getCurrentStrategy: (state) => {
      return state.currentStrategy;
    },

    /**
     * 获取策略对比分析数据
     * @param state - 模块状态
     * @returns 对比分析数据
     */
    getComparisonData: (state) => {
      return state.comparisonData;
    }
  }
};

export default performanceModule;