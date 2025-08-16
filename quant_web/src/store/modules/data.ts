import { Module } from 'vuex';
import api,{ HistoricalDataPoint ,FinancialData} from '@/api/data';

import { RootState } from '../types';

interface MarketData {
  indices: Record<string, any>;
  sectorPerformance: any[];
  topGainers: any[];
  topLosers: any[];
}

interface DataState {
  marketData: MarketData;
  realtimeQuotes: Record<string, any>;
  historicalData: Record<string, HistoricalDataPoint[]>;
  financialData: Record<string, FinancialData>;
  etfData: any;
  selectedStock: any;
  dataLoading: boolean;
}

const dataModule: Module<DataState, RootState> = {
  namespaced: true,
  state: {
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
  },
  mutations: {
    SET_MARKET_DATA(state, data: MarketData) {
      state.marketData = data;
    },
    UPDATE_REALTIME_QUOTE(state, payload: { symbol: string; quote: any }) {
      state.realtimeQuotes[payload.symbol] = payload.quote;
    },
    SET_HISTORICAL_DATA(state, payload: { symbol: string; data: HistoricalDataPoint[] }) {
      state.historicalData[payload.symbol] = payload.data;
    },
    SET_FINANCIAL_DATA(state, payload: { symbol: string; data: FinancialData }) {
      state.financialData[payload.symbol] = payload.data;
    },
    SET_ETF_DATA(state, etfData: any) {
      state.etfData = etfData;
    },
    SET_SELECTED_STOCK(state, stock: any) {
      state.selectedStock = stock;
    },
    SET_DATA_LOADING(state, isLoading: boolean) {
      state.dataLoading = isLoading;
    }
  },
  actions: {
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
    async fetchHistoricalData({ commit }, payload: { symbol: string; period?: string; frequency?: string }) {
      try {
        commit('SET_DATA_LOADING', true);
        const data = await api.getHistoricalData(payload.symbol, payload.period, payload.frequency);
        commit('SET_HISTORICAL_DATA', { symbol: payload.symbol, data });
        return data;
      } catch (error) {
        console.error('获取历史数据失败:', error);
        throw error;
      } finally {
        commit('SET_DATA_LOADING', false);
      }
    },
    async fetchFinancialData({ commit }, symbol: string) {
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
    async subscribeRealtimeData({ commit }, symbols: string[]) {
      try {
        api.subscribeRealtime(symbols, (symbol, quote) => {
          commit('UPDATE_REALTIME_QUOTE', { symbol, quote });
        });
      } catch (error) {
        console.error('订阅实时数据失败:', error);
      }
    },
    selectStock({ commit }, stock: any) {
      commit('SET_SELECTED_STOCK', stock);
    }
  },
  getters: {
    getQuote: (state) => (symbol: string) => {
      return state.realtimeQuotes[symbol] || null;
    },
    getHistoricalData: (state) => (symbol: string) => {
      return state.historicalData[symbol] || null;
    },
    getFinancialData: (state) => (symbol: string) => {
      return state.financialData[symbol] || null;
    },
    isMarketOpen: (state) => {
      return state.marketData.indices['SH000001']?.is_open || false;
    }
  }
};

export default dataModule;