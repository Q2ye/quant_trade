// 行情数据状态
import api from '../../api/data';

const state = {
  marketData: {
    indices: {},
    sectorPerformance: [],
    topGainers: [],
    topLosers: []
  },
  realtimeQuotes: {},
  historicalData: {},
  financialData: {},
  etfData: {},
  selectedStock: null,
  dataLoading: false
};

const mutations = {
  SET_MARKET_DATA(state, data) {
    state.marketData = data;
  },

  UPDATE_REALTIME_QUOTE(state, { symbol, quote }) {
    state.realtimeQuotes[symbol] = quote;
  },

  SET_HISTORICAL_DATA(state, { symbol, data }) {
    state.historicalData[symbol] = data;
  },

  SET_FINANCIAL_DATA(state, { symbol, data }) {
    state.financialData[symbol] = data;
  },

  SET_ETF_DATA(state, etfData) {
    state.etfData = etfData;
  },

  SET_SELECTED_STOCK(state, stock) {
    state.selectedStock = stock;
  },

  SET_DATA_LOADING(state, isLoading) {
    state.dataLoading = isLoading;
  }
};

const actions = {
  async fetchMarketData({ commit }) {
    try {
      commit('SET_DATA_LOADING', true);
      const data = await api.getMarketData();
      commit('SET_MARKET_DATA', data);
      return data;
    } catch (error) {
      console.error('获取市场数据失败:', error);
      throw error;
    } finally {
      commit('SET_DATA_LOADING', false);
    }
  },

  async fetchHistoricalData({ commit }, { symbol, period, frequency }) {
    try {
      commit('SET_DATA_LOADING', true);
      const data = await api.getHistoricalData(symbol, period, frequency);
      commit('SET_HISTORICAL_DATA', { symbol, data });
      return data;
    } catch (error) {
      console.error('获取历史数据失败:', error);
      throw error;
    } finally {
      commit('SET_DATA_LOADING', false);
    }
  },

  async fetchFinancialData({ commit }, symbol) {
    try {
      commit('SET_DATA_LOADING', true);
      const data = await api.getFinancialData(symbol);
      commit('SET_FINANCIAL_DATA', { symbol, data });
      return data;
    } catch (error) {
      console.error('获取财务数据失败:', error);
      throw error;
    } finally {
      commit('SET_DATA_LOADING', false);
    }
  },

  async fetchETFData({ commit }) {
    try {
      commit('SET_DATA_LOADING', true);
      const data = await api.getETFData();
      commit('SET_ETF_DATA', data);
      return data;
    } catch (error) {
      console.error('获取ETF数据失败:', error);
      throw error;
    } finally {
      commit('SET_DATA_LOADING', false);
    }
  },

  async subscribeRealtimeData({ commit }, symbols) {
    try {
      await api.subscribeRealtime(symbols, (symbol, quote) => {
        commit('UPDATE_REALTIME_QUOTE', { symbol, quote });
      });
    } catch (error) {
      console.error('订阅实时数据失败:', error);
    }
  },

  async unsubscribeRealtimeData({ commit }, symbols) {
    try {
      await api.unsubscribeRealtime(symbols);
    } catch (error) {
      console.error('取消订阅实时数据失败:', error);
    }
  },

  selectStock({ commit }, stock) {
    commit('SET_SELECTED_STOCK', stock);
  }
};

const getters = {
  getQuote: (state) => (symbol) => {
    return state.realtimeQuotes[symbol] || null;
  },

  getHistoricalData: (state) => (symbol) => {
    return state.historicalData[symbol] || null;
  },

  getFinancialData: (state) => (symbol) => {
    return state.financialData[symbol] || null;
  },

  isMarketOpen: (state) => {
    return state.marketData.indices['SH000001']?.is_open || false;
  }
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
};