// quant_web/src/store/modules/events.ts
import { Module } from 'vuex';
import api, { defaultRealtimeService } from '@/api/data';
import {
  HistoricalDataPoint,
  FinancialData,
  StockBasic
} from '@/types/entities/data';
import { RootState } from '@/types';

/**
 * 市场数据结构定义
 */
interface MarketData {
  indices: Record<string, any>;
  sectorPerformance: any[];
  topGainers: any[];
  topLosers: any[];
}

/**
 * 数据模块状态接口
 */
interface DataState {
  marketData: MarketData;
  realtimeQuotes: Record<string, any>;
  historicalData: Record<string, HistoricalDataPoint[]>;
  financialData: Record<string, FinancialData[]>; // 改为存储财务数据数组
  etfData: any;
  selectedStock: any;
  dataLoading: boolean;
  stockList: StockBasic[]; // 新增：股票列表
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
    financialData: {}, // 现在存储的是 FinancialData[] 而不是单个 FinancialData
    etfData: {},
    selectedStock: null,
    dataLoading: false,
    stockList: [] // 初始化股票列表
  },

  mutations: {
    /**
     * 设置市场数据
     * @param state - 模块状态
     * @param data - 市场数据
     */
    SET_MARKET_DATA(state: DataState, data: MarketData) {
      state.marketData = data;
    },

    /**
     * 更新实时行情数据
     * @param state - 模块状态
     * @param payload - 包含股票代码和行情数据的对象
     */
    UPDATE_REALTIME_QUOTE(state: DataState, payload: { symbol: string; quote: any }) {
      state.realtimeQuotes[payload.symbol] = payload.quote;
    },

    /**
     * 设置历史数据
     * @param state - 模块状态
     * @param payload - 包含股票代码和历史数据的对象
     */
    SET_HISTORICAL_DATA(state: DataState, payload: { symbol: string; data: HistoricalDataPoint[] }) {
      state.historicalData[payload.symbol] = payload.data;
    },

    /**
     * 设置财务数据（多个报告期）
     * @param state - 模块状态
     * @param payload - 包含股票代码和财务数据数组的对象
     */
    SET_FINANCIAL_DATA(state: DataState, payload: { symbol: string; data: FinancialData[] }) {
      state.financialData[payload.symbol] = payload.data;
    },

    /**
     * 设置ETF数据
     * @param state - 模块状态
     * @param etfData - ETF数据
     */
    SET_ETF_DATA(state: DataState, etfData: any) {
      state.etfData = etfData;
    },

    /**
     * 设置选中的股票
     * @param state - 模块状态
     * @param stock - 股票信息
     */
    SET_SELECTED_STOCK(state: DataState, stock: any) {
      state.selectedStock = stock;
    },

    /**
     * 设置数据加载状态
     * @param state - 模块状态
     * @param isLoading - 是否正在加载
     */
    SET_DATA_LOADING(state: DataState, isLoading: boolean) {
      state.dataLoading = isLoading;
    },

    /**
     * 设置股票列表
     * @param state - 模块状态
     * @param stocks - 股票列表
     */
    SET_STOCK_LIST(state: DataState, stocks: StockBasic[]) {
      state.stockList = stocks;
    }
  },

  actions: {
    /**
     * 获取市场数据
     * @param commit - Vuex commit 函数
     */
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

    /**
     * 获取历史数据
     * @param commit - Vuex commit 函数
     * @param payload - 参数对象
     * @param payload.symbol - 股票代码
     * @param payload.period - 时间周期
     * @param payload.frequency - 数据频率
     */
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

    /**
     * 获取财务数据（多个报告期）
     * @param commit - Vuex commit 函数
     * @param symbol - 股票代码
     */
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

    /**
     * 获取最新财务数据（单个报告期）
     * @param commit - Vuex commit 函数
     * @param symbol - 股票代码
     */
    async fetchLatestFinancialData({ commit }, symbol: string) {
      try {
        commit('SET_DATA_LOADING', true);
        const data = await api.getLatestFinancialData(symbol);
        if (data) {
          // 将单个财务数据包装为数组存储
          commit('SET_FINANCIAL_DATA', { symbol, data: [data] });
        }
        return data;
      } catch (error) {
        console.error('获取最新财务数据失败:', error);
        throw error;
      } finally {
        commit('SET_DATA_LOADING', false);
      }
    },

    /**
     * 获取ETF数据
     * @param commit - Vuex commit 函数
     */
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

    /**
     * 获取股票列表
     * @param commit - Vuex commit 函数
     * @param payload - 查询参数
     */
    async fetchStockList({ commit }, payload: { exchange?: string; industry?: string; page?: number; pageSize?: number } = {}) {
      try {
        commit('SET_DATA_LOADING', true);
        const data = await api.getStockList(
          payload.exchange,
          payload.industry,
          payload.page,
          payload.pageSize
        );
        commit('SET_STOCK_LIST', data);
        return data;
      } catch (error) {
        console.error('获取股票列表失败:', error);
        throw error;
      } finally {
        commit('SET_DATA_LOADING', false);
      }
    },

    /**
     * 订阅实时数据
     * @param commit - Vuex commit 函数
     * @param symbols - 股票代码数组
     */
    async subscribeRealtimeData({ commit }, symbols: string[]) {
      try {
        api.subscribeRealtime(symbols, (symbol: string, quote: any) => {
          commit('UPDATE_REALTIME_QUOTE', { symbol, quote });
        });
      } catch (error) {
        console.error('订阅实时数据失败:', error);
      }
    },

    /**
     * 取消订阅实时数据
     * @param commit -  Vuex commit 函数
     * @param symbols - 股票代码数组
     */
    async unsubscribeRealtimeData({ commit }, symbols: string[]) {
      try {
        api.unsubscribeRealtime(symbols);
      } catch (error) {
        console.error('取消订阅实时数据失败:', error);
      }
    },

    /**
     * 选择股票
     * @param commit - Vuex commit 函数
     * @param stock - 股票信息
     */
    selectStock({ commit }, stock: any) {
      commit('SET_SELECTED_STOCK', stock);
    },

    /**
     * 清理实时数据服务资源
     */
    destroyRealtimeService() {
      defaultRealtimeService.destroy();
    }
  },

  getters: {
    /**
     * 获取指定股票的实时行情
     * @param state - 模块状态
     * @returns 返回一个函数，该函数接收股票代码并返回行情数据
     */
    getQuote: (state: DataState) => (symbol: string) => {
      return state.realtimeQuotes[symbol] || null;
    },

    /**
     * 获取指定股票的历史数据
     * @param state - 模块状态
     * @returns 返回一个函数，该函数接收股票代码并返回历史数据
     */
    getHistoricalData: (state: DataState) => (symbol: string) => {
      return state.historicalData[symbol] || null;
    },

    /**
     * 获取指定股票的财务数据（返回数组）
     * @param state - 模块状态
     * @returns 返回一个函数，该函数接收股票代码并返回财务数据数组
     */
    getFinancialData: (state: DataState) => (symbol: string) => {
      return state.financialData[symbol] || null;
    },

    /**
     * 获取指定股票的最新财务数据
     * @param state - 模块状态
     * @returns 返回一个函数，该函数接收股票代码并返回最新财务数据
     */
    getLatestFinancialData: (state: DataState) => (symbol: string) => {
      const financials = state.financialData[symbol];
      return financials && financials.length > 0 ? financials[0] : null;
    },

    /**
     * 获取股票列表
     * @param state - 模块状态
     */
    stockList: (state: DataState) => {
      return state.stockList;
    },

    /**
     * 判断市场是否开放
     * @param state - 模块状态
     */
    isMarketOpen: (state: DataState) => {
      return state.marketData.indices['SH000001']?.is_open || false;
    }
  }
};

export default dataModule;