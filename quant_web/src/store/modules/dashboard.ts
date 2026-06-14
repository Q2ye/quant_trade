// quant_web/src/store/modules/dashboard.ts
// 仪表盘
import { Module } from "vuex";
import { RootState, DashboardState } from "@/types";
import { DashboardData, RealTimeDataEvent } from "@/types";
import dashboardAPI from "@/api/dashboard";

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
        var: 0,
      },
      realTimeSignals: [],
      marketSentiment: {
        advancing: 0,
        declining: 0,
        unchanged: 0,
        volume: 0,
        northbound: 0,
        marketHeat: 0,
      },
      positions: [],
      todayTrades: [],
    },
    realTimeUpdates: [],
    loading: false,
    lastUpdate: "",
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
      const index = state.dashboardData.positions.findIndex(
        (p) => p.symbol === position.symbol,
      );
      if (index !== -1) {
        state.dashboardData.positions.splice(index, 1, position);
      } else {
        state.dashboardData.positions.push(position);
      }
    },
    UPDATE_MARKET_SENTIMENT(state, sentiment: any) {
      state.dashboardData.marketSentiment = {
        ...state.dashboardData.marketSentiment,
        ...sentiment,
      };
    },
  },
  actions: {
    async loadDashboardData({ commit }) {
      commit("SET_LOADING", true);
      try {
        const [dashData, marketStatus] = await Promise.all([
          dashboardAPI.getDashboardData().catch(() => null),
          dashboardAPI.getMarketStatus().catch(() => null),
        ]);

        const dashboard: DashboardData = {
          totalAssets: dashData?.accountInfo?.totalAsset ?? 0,
          dailyPnL: dashData?.accountInfo?.dailyPnl ?? 0,
          positionValue: 0,
          availableCash: dashData?.accountInfo?.cash ?? 0,
          returnRate: dashData?.accountInfo?.dailyReturn ?? 0,
          performanceChart: [],
          riskMatrix: {
            positionDistribution: [],
            industryExposure: [],
            var: 0,
          },
          realTimeSignals: [],
          marketSentiment: {
            advancing: 0,
            declining: 0,
            unchanged: 0,
            volume: 0,
            northbound: 0,
            marketHeat: 0,
          },
          positions: (dashData?.positions ?? []) as any[],
          todayTrades: (dashData?.todayTrades ?? []) as any[],
        };

        commit("SET_DASHBOARD_DATA", dashboard);
        commit("SET_LAST_UPDATE", new Date().toISOString());
        return dashboard;
      } catch (error) {
        console.error("加载仪表盘数据失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", false);
      }
    },
    async refreshMarketData({ commit }) {
      try {
        const marketStatus = await dashboardAPI
          .getMarketStatus()
          .catch(() => null);
        if (marketStatus) {
          commit("UPDATE_MARKET_SENTIMENT", marketStatus);
          commit("ADD_REALTIME_UPDATE", {
            type: "market",
            symbol: "market",
            data: marketStatus,
            timestamp: Date.now(),
          });
        }
      } catch (error) {
        console.error("刷新市场数据失败:", error);
      }
    },
  },
  getters: {
    performanceChartData: (state) => {
      return state.dashboardData.performanceChart;
    },
    positionSummary: (state) => {
      return {
        total: state.dashboardData.positions.length,
        marketValue: state.dashboardData.positionValue,
        dailyPnL: state.dashboardData.dailyPnL,
      };
    },
    marketOverview: (state) => {
      const sentiment = state.dashboardData.marketSentiment;
      return {
        advancing: sentiment.advancing,
        declining: sentiment.declining,
        advanceDeclineRatio: sentiment.advancing / (sentiment.declining || 1),
      };
    },
  },
};

export default dashboardModule;
