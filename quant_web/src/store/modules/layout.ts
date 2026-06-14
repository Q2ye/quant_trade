// 界面布局
// src/store/modules/layout.ts
import { Module } from "vuex";
import {
  AlertItem,
  LayoutState,
  RootState,
  TabItem,
  WatchlistItem,
} from "@/types";

const layoutModule: Module<LayoutState, RootState> = {
  namespaced: true,
  state: {
    topNavigation: {
      logo: "/logo.svg",
      platformName: "一念量化",
      marketIndicators: [],
      search: {
        placeholder: "搜索股票、策略、功能...",
        recentSearches: [],
        hotSearches: [],
      },
      notifications: [],
      user: null,
      systemStatus: {
        connected: false,
        status: "normal",
        message: "",
      },
    },
    siderNavigation: {
      collapsed: false,
      activeKey: "dashboard",
      openKeys: ["core", "market", "research", "monitor", "system"],
      menuItems: [
        {
          key: "core",
          label: "核心功能",
          icon: "appstore",
          children: [
            { key: "dashboard",        label: "市场总览",   icon: "dashboard",    path: "/market/dashboard" },
            { key: "strategies",       label: "策略管理",   icon: "strategy",     path: "/strategies" },
            { key: "strategy-build",   label: "策略构建",   icon: "build",        path: "/strategy/build" },
            { key: "baskets",          label: "篮子管理",   icon: "container",    path: "/trade/workspace?tab=baskets" },
            { key: "trading",          label: "交易驾驶舱", icon: "transaction",  path: "/trade" },
          ],
        },
        {
          key: "market",
          label: "市场数据",
          icon: "line-chart",
          children: [
            { key: "market-screener",  label: "选股器",     icon: "search",       path: "/market/screener" },
            { key: "market-etf",       label: "ETF 市场",   icon: "stock",        path: "/market/etf" },
            { key: "market-money",     label: "资金流向",   icon: "fund",         path: "/market/money-flow" },
            { key: "market-limit",     label: "涨跌停分析", icon: "trending",     path: "/market/limit-analysis" },
            { key: "market-finance",   label: "财务对比",   icon: "calculator",   path: "/market/financial-compare" },
          ],
        },
        {
          key: "research",
          label: "研究回测",
          icon: "experiment",
          children: [
            { key: "factor-hub",       label: "因子研究",   icon: "filter",       path: "/strategy/factors" },
            { key: "backtest-hub",     label: "回测验证",   icon: "experiment",   path: "/strategy/backtest" },
          ],
        },
        {
          key: "monitor",
          label: "监控风控",
          icon: "monitor",
          children: [
            { key: "risk-monitor",     label: "风险监控",   icon: "shield",       path: "/risk/monitor" },
            { key: "signals",          label: "信号监控",   icon: "pulse",        path: "/signals" },
            { key: "performance",      label: "绩效分析",   icon: "chart",        path: "/performance" },
          ],
        },
        {
          key: "system",
          label: "系统管理",
          icon: "setting",
          children: [
            { key: "data-sync",        label: "数据同步",   icon: "sync",         path: "/data/sync" },
            { key: "system-monitor",   label: "系统监控",   icon: "monitor",      path: "/system/monitor" },
            { key: "system-logs",      label: "系统日志",   icon: "file-text",    path: "/system/logs" },
            { key: "system-users",     label: "用户管理",   icon: "user",         path: "/system/users" },
            { key: "system-settings",  label: "系统设置",   icon: "setting",      path: "/system/settings" },
          ],
        },
      ],
    },
    mainWorkspace: {
      tabs: [],
      activeTab: "",
      tabHistory: [],
    },
    rightPanel: {
      collapsed: false,
      alerts: [],
      watchlist: [],
      quickActions: [
        {
          id: "sync-events",
          label: "同步数据",
          icon: "sync",
          action: "syncData",
        },
        {
          id: "close-all",
          label: "全部平仓",
          icon: "stop",
          action: "closeAllPositions",
          confirm: true,
        },
      ],
    },
    theme: "dark",
    language: "zh-CN",
  },
  mutations: {
    SET_SIDER_COLLAPSED(state, collapsed: boolean) {
      state.siderNavigation.collapsed = collapsed;
    },
    SET_ACTIVE_MENU(state, activeKey: string) {
      state.siderNavigation.activeKey = activeKey;
    },
    SET_OPEN_KEYS(state, openKeys: string[]) {
      state.siderNavigation.openKeys = openKeys;
    },
    ADD_TAB(state, tab: TabItem) {
      const existingIndex = state.mainWorkspace.tabs.findIndex(
        (t: TabItem) => t.id === tab.id,
      );
      if (existingIndex === -1) {
        state.mainWorkspace.tabs.push(tab);
      }
      state.mainWorkspace.activeTab = tab.id;

      // 维护标签页历史
      state.mainWorkspace.tabHistory = state.mainWorkspace.tabHistory.filter(
        (id: string) => id !== tab.id,
      );
      state.mainWorkspace.tabHistory.push(tab.id);
    },
    CLOSE_TAB(state, tabId: string) {
      state.mainWorkspace.tabs = state.mainWorkspace.tabs.filter(
        (tab: TabItem) => tab.id !== tabId,
      );

      if (state.mainWorkspace.activeTab === tabId) {
        const lastTabId =
          state.mainWorkspace.tabHistory[
            state.mainWorkspace.tabHistory.length - 2
          ];
        state.mainWorkspace.activeTab =
          lastTabId || state.mainWorkspace.tabs[0]?.id || "";
      }
    },
    SET_ACTIVE_TAB(state, tabId: string) {
      state.mainWorkspace.activeTab = tabId;
    },
    UPDATE_TAB_PROPS(state, payload: { tabId: string; props: any }) {
      const tab = state.mainWorkspace.tabs.find(
        (t: TabItem) => t.id === payload.tabId,
      );
      if (tab) {
        tab.props = { ...tab.props, ...payload.props };
      }
    },
    SET_RIGHT_PANEL_COLLAPSED(state, collapsed: boolean) {
      state.rightPanel.collapsed = collapsed;
    },
    ADD_ALERT(state, alert: AlertItem) {
      state.rightPanel.alerts.unshift(alert);
      // 保持最多100条预警
      if (state.rightPanel.alerts.length > 100) {
        state.rightPanel.alerts = state.rightPanel.alerts.slice(0, 100);
      }
    },
    MARK_ALERT_READ(state, alertId: string) {
      const alert = state.rightPanel.alerts.find(
        (a: AlertItem) => a.id === alertId,
      );
      if (alert) {
        alert.read = true;
      }
    },
    CLEAR_ALERTS(state) {
      state.rightPanel.alerts = [];
    },
    SET_WATCHLIST(state, watchlist: WatchlistItem[]) {
      state.rightPanel.watchlist = watchlist;
    },
    SET_THEME(state, theme: string) {
      state.theme = theme;
    },
    SET_LANGUAGE(state, language: string) {
      state.language = language;
    },
    UPDATE_MARKET_INDICATORS(state, indicators: any[]) {
      state.topNavigation.marketIndicators = indicators;
    },
    UPDATE_SYSTEM_STATUS(state, status: any) {
      state.topNavigation.systemStatus = status;
    },
  },
  actions: {
    toggleSider({ commit, state }) {
      commit("SET_SIDER_COLLAPSED", !state.siderNavigation.collapsed);
    },
    toggleRightPanel({ commit, state }) {
      commit("SET_RIGHT_PANEL_COLLAPSED", !state.rightPanel.collapsed);
    },
    openTab({ commit }, tab: TabItem) {
      commit("ADD_TAB", tab);
    },
    closeTab({ commit }, tabId: string) {
      commit("CLOSE_TAB", tabId);
    },
    switchTab({ commit }, tabId: string) {
      commit("SET_ACTIVE_TAB", tabId);
    },
    addAlert({ commit }, alert: Omit<AlertItem, "id" | "read">) {
      const newAlert: AlertItem = {
        ...alert,
        id: `alert-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`,
        read: false,
      };
      commit("ADD_ALERT", newAlert);
    },
    markAlertRead({ commit }, alertId: string) {
      commit("MARK_ALERT_READ", alertId);
    },
    clearAlerts({ commit }) {
      commit("CLEAR_ALERTS");
    },
    changeTheme({ commit }, theme: string) {
      commit("SET_THEME", theme);
    },
    changeLanguage({ commit }, language: string) {
      commit("SET_LANGUAGE", language);
    },
  },
  getters: {
    currentTab: (state) => {
      return state.mainWorkspace.tabs.find(
        (tab: TabItem) => tab.id === state.mainWorkspace.activeTab,
      );
    },
    unreadAlertsCount: (state) => {
      return state.rightPanel.alerts.filter((alert: AlertItem) => !alert.read)
        .length;
    },
    isMobileView: (state) => {
      return state.siderNavigation.collapsed;
    },
  },
};

export default layoutModule;
