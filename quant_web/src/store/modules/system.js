import api from '../../api/strategy';

const state = {
  currentStrategy: null,
  strategies: [],
  backtestParams: {
    startDate: '2020-01-01',
    endDate: '2023-12-31',
    initialCapital: 100000,
    commission: 0.0003,
    slippage: 0.01
  },
  backtestResults: null,
  runningStrategies: []
};

const mutations = {
  SET_CURRENT_STRATEGY(state, strategy) {
    state.currentStrategy = strategy;
  },
  SET_STRATEGIES(state, strategies) {
    state.strategies = strategies;
  },
  SET_BACKTEST_PARAMS(state, params) {
    state.backtestParams = params;
  },
  SET_BACKTEST_RESULTS(state, results) {
    state.backtestResults = results;
  },
  ADD_RUNNING_STRATEGY(state, strategy) {
    state.runningStrategies.push(strategy);
  },
  REMOVE_RUNNING_STRATEGY(state, strategyId) {
    state.runningStrategies = state.runningStrategies.filter(s => s.id !== strategyId);
  }
};

const actions = {
  async fetchStrategies({ commit }) {
    try {
      const strategies = await api.getStrategies();
      commit('SET_STRATEGIES', strategies);
      return strategies;
    } catch (error) {
      console.error('获取策略列表失败:', error);
      throw error;
    }
  },

  async loadStrategy({ commit }, strategyId) {
    try {
      const strategy = await api.getStrategy(strategyId);
      commit('SET_CURRENT_STRATEGY', strategy);
      return strategy;
    } catch (error) {
      console.error('加载策略失败:', error);
      throw error;
    }
  },

  async saveStrategy({ state }) {
    try {
      const strategy = state.currentStrategy;
      await api.saveStrategy(strategy);
      return strategy;
    } catch (error) {
      console.error('保存策略失败:', error);
      throw error;
    }
  },

  async runBacktest({ commit, state }) {
    try {
      const { currentStrategy, backtestParams } = state;
      const results = await api.runBacktest({
        strategyId: currentStrategy.id,
        code: currentStrategy.code,
        params: currentStrategy.params,
        ...backtestParams
      });
      commit('SET_BACKTEST_RESULTS', results);
      return results;
    } catch (error) {
      console.error('回测执行失败:', error);
      throw error;
    }
  },

  async startStrategy({ commit }, strategyId) {
    try {
      await api.startStrategy(strategyId);
      commit('ADD_RUNNING_STRATEGY', strategyId);
      return true;
    } catch (error) {
      console.error('启动策略失败:', error);
      throw error;
    }
  },

  async stopStrategy({ commit }, strategyId) {
    try {
      await api.stopStrategy(strategyId);
      commit('REMOVE_RUNNING_STRATEGY', strategyId);
      return true;
    } catch (error) {
      console.error('停止策略失败:', error);
      throw error;
    }
  }
};

export default {
  namespaced: true,
  state,
  mutations,
  actions
};