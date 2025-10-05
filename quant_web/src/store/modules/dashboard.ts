// quant_web/src/store/modules/dashboard.ts
// 仪表盘
import { Module } from 'vuex';
import { RootState, DashboardState } from '@/types';
import {DashboardData, RealTimeDataEvent} from "@/types/entities/dashboard";

const dashboardModule: Module<DashboardState, RootState> = {
  namespaced: true,
  state: {
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
  },
  mutations: {
    SET_DASHBOARD_DATA(state, data: DashboardData) {
      state.dashboardData = data;
    },
    SET_LOADING(state, loading: boolean) {
      state.loading = loading;
    },
    SET_LAST_UPDATE(state, timestamp: string) {
      state.lastUpdate = timestamp;
    },
    ADD_REALTIME_UPDATE(state, update: RealTimeDataEvent) {
      state.realTimeUpdates.unshift(update);
      // 保持最多50条实时更新
      if (state.realTimeUpdates.length > 50) {
        state.realTimeUpdates = state.realTimeUpdates.slice(0, 50);
      }
    },
    UPDATE_POSITION(state, position: any) {
      const index = state.dashboardData.positions.findIndex(p => p.symbol === position.symbol);
      if (index !== -1) {
        state.dashboardData.positions.splice(index, 1, position);
      } else {
        state.dashboardData.positions.push(position);
      }
    },
    UPDATE_MARKET_SENTIMENT(state, sentiment: any) {
      state.dashboardData.marketSentiment = { ...state.dashboardData.marketSentiment, ...sentiment };
    }
  },
  actions: {
    async loadDashboardData({ commit }) {
      commit('SET_LOADING', true);
      try {
        // 模拟API调用
        const mockData: DashboardData = {
          totalAssets: 1250000,
          dailyPnL: 12500,
          positionValue: 980000,
          availableCash: 270000,
          returnRate: 0.045,
          performanceChart: [
            { date: '2024-01', value: 1000000, benchmark: 1000000 },
            { date: '2024-02', value: 1050000, benchmark: 1020000 },
            { date: '2024-03', value: 1100000, benchmark: 1050000 },
            { date: '2024-04', value: 1150000, benchmark: 1080000 },
            { date: '2024-05', value: 1200000, benchmark: 1120000 },
            { date: '2024-06', value: 1250000, benchmark: 1150000 }
          ],
          riskMatrix: {
            positionDistribution: [
              { name: '股票A', value: 300000, percentage: 0.3 },
              { name: '股票B', value: 250000, percentage: 0.25 },
              { name: '股票C', value: 200000, percentage: 0.2 },
              { name: '其他', value: 250000, percentage: 0.25 }
            ],
            industryExposure: [
              { industry: '科技', exposure: 0.4, concentration: 0.6 },
              { industry: '金融', exposure: 0.3, concentration: 0.4 },
              { industry: '消费', exposure: 0.2, concentration: 0.3 },
              { industry: '医药', exposure: 0.1, concentration: 0.2 }
            ],
            var: 50000
          },
          realTimeSignals: [],
          marketSentiment: {
            advancing: 1250,
            declining: 850,
            unchanged: 300,
            volume: 45800000000,
            northbound: 1250000000,
            marketHeat: 0.68
          },
          positions: [],
          todayTrades: []
        };

        commit('SET_DASHBOARD_DATA', mockData);
        commit('SET_LAST_UPDATE', new Date().toISOString());
        return mockData;
      } catch (error) {
        console.error('加载仪表盘数据失败:', error);
        throw error;
      } finally {
        commit('SET_LOADING', false);
      }
    },
    async refreshMarketData({ commit }) {
      try {
        // 模拟市场数据更新
        const update = {
          type: 'market',
          data: {
            advancing: Math.floor(Math.random() * 500) + 1000,
            declining: Math.floor(Math.random() * 500) + 800,
            volume: Math.floor(Math.random() * 100000000000) + 40000000000
          }
        };

        commit('UPDATE_MARKET_SENTIMENT', update.data);
        commit('ADD_REALTIME_UPDATE', {
          type: 'market',
          symbol: 'market',
          data: update,
          timestamp: Date.now()
        });
      } catch (error) {
        console.error('刷新市场数据失败:', error);
      }
    }
  },
  getters: {
    performanceChartData: (state) => {
      return state.dashboardData.performanceChart;
    },
    positionSummary: (state) => {
      return {
        total: state.dashboardData.positions.length,
        marketValue: state.dashboardData.positionValue,
        dailyPnL: state.dashboardData.dailyPnL
      };
    },
    marketOverview: (state) => {
      const sentiment = state.dashboardData.marketSentiment;
      return {
        advancing: sentiment.advancing,
        declining: sentiment.declining,
        advanceDeclineRatio: sentiment.advancing / (sentiment.declining || 1)
      };
    }
  }
};

export default dashboardModule;