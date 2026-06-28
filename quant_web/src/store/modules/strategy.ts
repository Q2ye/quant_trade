// quant_web/src/store/modules/strategy.ts
// 策略管理Vuex模块
import { Module } from "vuex";
import { RootState } from "@/types";
import {
  Strategy,
  StrategyRun,
  BacktestResult,
  TradeSignal,
  ApiStrategyPerformance,
  StrategyStatusInfo,
} from "@/types";
import strategyAPI from "@/api/strategy";
import backtestAPI from "@/api/backtest";
import signalsAPI from "@/api/signals";

/**
 * 策略模块状态接口
 */
export interface StrategyState {
  // 策略列表
  strategies: Strategy[];
  strategiesMap: Map<string, Strategy>;

  // 当前选中的策略
  currentStrategy: Strategy | null;

  // 策略运行状态
  strategyRuns: Map<string, StrategyRun[]>;
  activeStrategies: Set<string>; // 正在运行的策略ID

  // 回测结果
  backtestResults: Map<string, BacktestResult>;
  currentBacktest: string | null; // 当前查看的回测ID

  // 策略信号
  strategySignals: Map<string, TradeSignal[]>;

  // 策略绩效
  strategyPerformance: Map<string, ApiStrategyPerformance>;

  // 加载状态
  isLoading: boolean;
  lastUpdate: number;
}

const state: StrategyState = {
  strategies: [],
  strategiesMap: new Map(),
  currentStrategy: null,
  strategyRuns: new Map(),
  activeStrategies: new Set(),
  backtestResults: new Map(),
  currentBacktest: null,
  strategySignals: new Map(),
  strategyPerformance: new Map(),
  isLoading: false,
  lastUpdate: 0,
};

const mutations = {
  /**
   * 设置策略列表
   */
  SET_STRATEGIES(state: StrategyState, strategies: Strategy[]) {
    state.strategies = strategies;
    state.strategiesMap = new Map(strategies.map((s) => [s.id, s]));
  },

  /**
   * 添加策略
   */
  ADD_STRATEGY(state: StrategyState, strategy: Strategy) {
    state.strategies.push(strategy);
    state.strategiesMap.set(strategy.id, strategy);
  },

  /**
   * 更新策略
   */
  UPDATE_STRATEGY(state: StrategyState, strategy: Strategy) {
    const index = state.strategies.findIndex((s) => s.id === strategy.id);
    if (index !== -1) {
      state.strategies.splice(index, 1, strategy);
    }
    state.strategiesMap.set(strategy.id, strategy);
  },

  /**
   * 删除策略
   */
  REMOVE_STRATEGY(state: StrategyState, strategyId: string) {
    state.strategies = state.strategies.filter((s) => s.id !== strategyId);
    state.strategiesMap.delete(strategyId);
    state.strategyRuns.delete(strategyId);
    state.backtestResults.delete(strategyId);
    state.strategySignals.delete(strategyId);
    state.strategyPerformance.delete(strategyId);
    state.activeStrategies.delete(strategyId);
  },

  /**
   * 设置当前策略
   */
  SET_CURRENT_STRATEGY(state: StrategyState, strategy: Strategy | null) {
    state.currentStrategy = strategy;
  },

  /**
   * 更新策略状态
   */
  UPDATE_STRATEGY_STATUS(
    state: StrategyState,
    payload: { strategyId: string; status: "running" | "stopped" | "error" },
  ) {
    const strategy = state.strategiesMap.get(payload.strategyId);
    if (strategy) {
      strategy.status = payload.status;

      if (payload.status === "running") {
        state.activeStrategies.add(payload.strategyId);
      } else {
        state.activeStrategies.delete(payload.strategyId);
      }
    }
  },

  /**
   * 添加策略运行记录
   */
  ADD_STRATEGY_RUN(
    state: StrategyState,
    payload: { strategyId: string; run: StrategyRun },
  ) {
    if (!state.strategyRuns.has(payload.strategyId)) {
      state.strategyRuns.set(payload.strategyId, []);
    }
    state.strategyRuns.get(payload.strategyId)!.push(payload.run);
  },

  /**
   * 设置回测结果
   */
  SET_BACKTEST_RESULT(
    state: StrategyState,
    payload: { strategyId: string; result: BacktestResult },
  ) {
    state.backtestResults.set(payload.strategyId, payload.result);
  },

  /**
   * 设置当前回测
   */
  SET_CURRENT_BACKTEST(state: StrategyState, backtestId: string | null) {
    state.currentBacktest = backtestId;
  },

  /**
   * 添加策略信号
   */
  ADD_STRATEGY_SIGNAL(state: StrategyState, signal: TradeSignal) {
    if (!state.strategySignals.has(signal.strategy_id)) {
      state.strategySignals.set(signal.strategy_id, []);
    }

    const signals = state.strategySignals.get(signal.strategy_id)!;
    signals.unshift(signal); // 新的信号放在前面

    // 保持最多1000个信号
    if (signals.length > 1000) {
      signals.splice(1000);
    }
  },

  /**
   * 设置策略信号列表
   */
  SET_STRATEGY_SIGNALS(
    state: StrategyState,
    payload: { strategyId: string; signals: TradeSignal[] },
  ) {
    state.strategySignals.set(payload.strategyId, payload.signals);
  },

  /**
   * 更新策略绩效
   */
  UPDATE_STRATEGY_PERFORMANCE(
    state: StrategyState,
    payload: { strategyId: string; performance: ApiStrategyPerformance },
  ) {
    state.strategyPerformance.set(payload.strategyId, payload.performance);
  },

  /**
   * 设置加载状态
   */
  SET_LOADING(state: StrategyState, loading: boolean) {
    state.isLoading = loading;
  },

  /**
   * 清理过期信号（超过24小时）
   */
  CLEANUP_OLD_SIGNALS(state: StrategyState) {
    const twentyFourHoursAgo = Date.now() - 24 * 60 * 60 * 1000;

    for (const [strategyId, signals] of state.strategySignals.entries()) {
      const filtered = signals.filter(
        (signal) => new Date(signal.signal_time).getTime() > twentyFourHoursAgo,
      );
      state.strategySignals.set(strategyId, filtered);
    }
  },
};

const actions = {
  /**
   * 加载策略列表
   */
  async loadStrategies({ commit }: any) {
    commit("SET_LOADING", true);
    try {
      const strategies = await strategyAPI.getStrategies();
      commit("SET_STRATEGIES", strategies);
      return strategies;
    } catch (error) {
      console.error("加载策略列表失败:", error);
      throw error;
    } finally {
      commit("SET_LOADING", false);
    }
  },

  /**
   * 创建策略
   */
  async createStrategy({ commit }: any, strategyData: Partial<Strategy>) {
    try {
      const strategy = await strategyAPI.createStrategy(strategyData as any);
      commit("ADD_STRATEGY", strategy);
      return strategy;
    } catch (error) {
      console.error("创建策略失败:", error);
      throw error;
    }
  },

  /**
   * 更新策略
   */
  async updateStrategy({ commit }: any, strategyData: Strategy) {
    try {
      const strategy = await strategyAPI.updateStrategy(
        strategyData.id,
        strategyData as any,
      );
      commit("UPDATE_STRATEGY", strategy);
      return strategy;
    } catch (error) {
      console.error("更新策略失败:", error);
      throw error;
    }
  },

  /**
   * 删除策略
   */
  async cloneStrategy({ dispatch }: any, { id, newName }: { id: string; newName?: string }) {
    try {
      const result = await strategyAPI.cloneStrategy(id, newName);
      await dispatch("fetchStrategies");
      return result;
    } catch (error) {
      console.error("克隆策略失败:", error);
      throw error;
    }
  },

  async deleteStrategy({ commit }: any, strategyId: string) {
    try {
      await strategyAPI.deleteStrategy(strategyId);
      commit("REMOVE_STRATEGY", strategyId);
    } catch (error) {
      console.error("删除策略失败:", error);
      throw error;
    }
  },

  /**
   * 启动策略
   */
  async startStrategy(
    { commit, state }: any,
    { strategyId, params }: { strategyId: string; params?: any },
  ) {
    try {
      const result = await strategyAPI.startStrategy(strategyId, params);
      // 检查 API 返回
      if (result && (result as any).success === false) {
        const errMsg = (result as any).error || "启动失败";
        console.error("启动策略失败:", errMsg);
        throw new Error(errMsg);
      }

      commit("UPDATE_STRATEGY_STATUS", { strategyId, status: "running" });

      // v2.0: 立即更新本地策略的 run_mode、execution_mode、account_id
      const strategy = state.strategiesMap.get(strategyId);
      if (strategy) {
        strategy.run_mode = params?.run_mode || "live";
        strategy.execution_mode = params?.execution_mode || "semi_auto";
        strategy.status = "running";
        if (params?.account_id) (strategy as any).account_id = params.account_id;
        if (params?.capital) (strategy as any).allocated_capital = params.capital;
        state.activeStrategies.add(strategyId);
      }

      const run: StrategyRun = {
        id: `run_${Date.now()}`,
        strategy_id: strategyId,
        started_at: new Date().toISOString(),
        status: "running",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      commit("ADD_STRATEGY_RUN", { strategyId, run });
    } catch (error) {
      console.error("启动策略失败:", error);
      throw error;
    }
  },

  /**
   * 停止策略
   */
  async stopStrategy({ commit, state }: any, strategyId: string) {
    try {
      await strategyAPI.stopStrategy(strategyId);
      commit("UPDATE_STRATEGY_STATUS", { strategyId, status: "stopped" });

      const runs = state.strategyRuns.get(strategyId) || [];
      const currentRun = runs.find(
        (run: StrategyRun) => run.status === "running",
      );
      if (currentRun) {
        currentRun.status = "stopped";
        currentRun.stopped_at = new Date().toISOString();
        currentRun.updated_at = new Date().toISOString();
      }
    } catch (error) {
      console.error("停止策略失败:", error);
      throw error;
    }
  },

  /**
   * 运行回测
   */
  async runBacktest(
    { commit }: any,
    { strategyId, config }: { strategyId: string; config: any },
  ) {
    try {
      const result = await backtestAPI.createTask({
        name: `回测_${strategyId}`,
        strategyId,
        ...config,
      } as any);
      commit("SET_BACKTEST_RESULT", { strategyId, result });
      return result;
    } catch (error) {
      console.error("运行回测失败:", error);
      throw error;
    }
  },

  /**
   * 获取策略信号
   */
  async loadStrategySignals(
    { commit }: any,
    { strategyId, limit = 100 }: { strategyId: string; limit?: number },
  ) {
    try {
      const signals = await signalsAPI.getSignals({ strategyId, limit } as any);
      commit("SET_STRATEGY_SIGNALS", { strategyId, signals });
      return signals;
    } catch (error) {
      console.error("获取策略信号失败:", error);
      throw error;
    }
  },

  /**
   * 监控策略性能
   */
  startStrategyMonitoring({ commit, state }: any, strategyId: string) {
    const interval = setInterval(async () => {
      if (state.activeStrategies.has(strategyId)) {
        try {
          const performance =
            await strategyAPI.getStrategyPerformance(strategyId);
          commit("UPDATE_STRATEGY_PERFORMANCE", { strategyId, performance });
        } catch (error) {
          console.error("获取策略性能失败:", error);
        }
      }
    }, 5000);

    return () => clearInterval(interval);
  },

  /**
   * 定期清理旧信号
   */
  startSignalCleanup({ commit }: any) {
    setInterval(() => {
      commit("CLEANUP_OLD_SIGNALS");
    }, 3600000); // 每小时清理一次
  },
};

const getters = {
  /**
   * 获取所有策略
   */
  getAllStrategies: (state: StrategyState) => state.strategies,

  /**
   * 获取运行中的策略
   */
  getActiveStrategies: (state: StrategyState) => {
    return state.strategies.filter((s) => state.activeStrategies.has(s.id));
  },

  /**
   * 获取单个策略
   */
  getStrategyById: (state: StrategyState) => (id: string) => {
    return state.strategiesMap.get(id);
  },

  /**
   * 获取策略运行记录
   */
  getStrategyRuns: (state: StrategyState) => (strategyId: string) => {
    return state.strategyRuns.get(strategyId) || [];
  },

  /**
   * 获取回测结果
   */
  getBacktestResult: (state: StrategyState) => (strategyId: string) => {
    return state.backtestResults.get(strategyId);
  },

  /**
   * 获取策略信号
   */
  getStrategySignals: (state: StrategyState) => (strategyId: string) => {
    return state.strategySignals.get(strategyId) || [];
  },

  /**
   * 获取最新信号
   */
  getLatestSignals:
    (state: StrategyState) =>
    (limit: number = 10) => {
      const allSignals: TradeSignal[] = [];
      for (const signals of state.strategySignals.values()) {
        allSignals.push(...signals.slice(0, 5)); // 每个策略取最新的5个信号
      }

      return allSignals
        .sort(
          (a, b) =>
            new Date(b.signal_time).getTime() -
            new Date(a.signal_time).getTime(),
        )
        .slice(0, limit);
    },

  /**
   * 获取策略性能
   */
  getStrategyPerformance: (state: StrategyState) => (strategyId: string) => {
    return state.strategyPerformance.get(strategyId);
  },

  /**
   * 检查策略是否运行中
   */
  isStrategyRunning: (state: StrategyState) => (strategyId: string) => {
    return state.activeStrategies.has(strategyId);
  },
};

const strategyModule: Module<StrategyState, RootState> = {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
};

export default strategyModule;
