// 根状态类型定义
// 整合所有模块状态，构成完整的应用状态树

import { UserState } from "./state-user-state";
import { StrategyState } from "./state-strategy-state";
import { BasketState } from "./state-basket-state";
import { TradeState } from "./state-trade-state";
import { DataState } from "./state-data-state";
import { SystemState } from "./state-system-state";
import { LayoutState } from "./state-layout-state";
import { DashboardState } from "./state-dashboard-state";
import { PerformanceState } from "./state-performance-state";
import { RiskState } from "./state-risk-state";
import { StrategyStudioState } from "./state-strategy-studio-state";

/**
 * 应用根状态接口
 * 定义了整个Vuex状态管理的完整数据结构
 * 每个属性对应一个功能模块的状态管理
 */
export interface RootState {
  /**
   * 用户认证状态模块
   * 管理用户登录、权限、个人信息等
   */
  user: UserState;

  /**
   * 策略管理状态模块
   * 管理策略的创建、编辑、执行、监控等
   */
  strategy: StrategyState;

  /**
   * 篮子管理状态模块
   * 管理股票篮子的创建、成分股配置、权重调整等
   */
  basket: BasketState;

  /**
   * 交易执行状态模块
   * 管理订单、持仓、账户资金、成交记录等
   */
  trade: TradeState;

  /**
   * 数据管理状态模块
   * 管理行情数据、财务数据、数据同步任务等
   */
  data: DataState;

  /**
   * 系统管理状态模块
   * 管理系统配置、用户管理、日志监控、系统健康等
   */
  system: SystemState;

  /**
   * 布局状态模块
   * 管理界面布局、主题、侧边栏、导航等UI状态
   */
  layout: LayoutState;

  /**
   * 仪表盘状态模块
   * 管理首页仪表盘的实时数据、图表、监控面板等
   */
  dashboard: DashboardState;

  /**
   * 绩效分析状态模块
   * 管理策略绩效、账户绩效、对比分析、归因分析等
   */
  performance: PerformanceState;

  /**
   * 风险管理状态模块
   * 管理风控规则、风险监控、风险事件、黑名单等
   */
  risk: RiskState;

  /**
   * 策略工作室状态模块
   * 管理回测、参数优化、因子研究等高级功能
   */
  strategyStudio: StrategyStudioState;
}

/**
 * 状态模块键名类型
 * 用于类型安全的模块访问
 */
export type StateModuleKey = keyof RootState;

/**
 * 状态初始化工具函数
 * 创建完整的初始状态对象，用于Vuex store初始化
 */
export function createInitialState(): RootState {
  return {
    user: {
      token: null,
      userInfo: null,
      permissions: [],
      lastLogin: null,
      isAuthenticated: false,
      loading: {
        login: false,
        logout: false,
        profile: false,
      },
      error: {
        login: null,
        register: null,
        profile: null,
      },
      session: {
        rememberMe: false,
        autoLogin: false,
        sessionTimeout: 120, // 默认2小时
      },
    },
    strategy: {
      strategyList: [],
      currentStrategy: null,
      strategyTemplates: [],
      strategyStatus: new Map(),
      parameterEditing: {
        currentParameters: {},
        originalParameters: {},
        hasChanges: false,
      },
      codeEditing: {
        currentCode: "",
        originalCode: "",
        hasChanges: false,
        syntaxErrors: [],
      },
      loading: {
        list: false,
        detail: false,
        templates: false,
        create: false,
        update: false,
        delete: false,
        start: false,
        stop: false,
      },
      error: {
        list: null,
        detail: null,
        create: null,
        update: null,
        delete: null,
        operation: null,
      },
    },
    basket: {
      currentBasketId: null,
      basketList: [],
      currentBasket: null,
      basketItems: [],
      loading: {
        list: false,
        detail: false,
        items: false,
        create: false,
        update: false,
        delete: false,
      },
      error: {
        list: null,
        detail: null,
        create: null,
        update: null,
        delete: null,
      },
      pagination: {
        page: 1,
        pageSize: 20,
        total: 0,
      },
      filters: {
        keyword: "",
        sortField: "createdAt",
        sortOrder: "desc",
      },
    },
    trade: {
      account: {
        info: {
          accountId: "",
          broker: "",
          type: "",
          status: "",
        },
        capital: {
          totalAssets: 0,
          netAssets: 0,
          availableCash: 0,
          frozenCash: 0,
          marketValue: 0,
        },
        today: {
          pnl: 0,
          commission: 0,
          tradeCount: 0,
        },
      },
      positions: {
        list: [],
        statistics: {
          totalValue: 0,
          totalPnl: 0,
          positionCount: 0,
          concentration: 0,
        },
      },
      orders: {
        current: [],
        history: [],
        statistics: {
          todayOrders: 0,
          todayTrades: 0,
          successRate: 0,
        },
      },
      trades: {
        list: [],
      },
      tradingCockpit: {
        quickTrade: {
          symbol: "",
          direction: "buy",
          priceType: "limit",
          price: 0,
          volume: 0,
          amount: 0,
        },
        chartTrading: {
          selectedSymbol: "",
          chartType: "kline",
          indicators: [],
        },
      },
      loading: {
        account: false,
        positions: false,
        orders: false,
        trades: false,
        trading: false,
      },
    },
    data: {
      syncTasks: {
        tasks: [],
        statistics: {
          lastSyncTime: null,
          totalSynced: 0,
          successRate: 0,
        },
      },
      marketData: {
        subscriptions: [],
        cache: new Map(),
      },
      financialData: {
        loadedData: new Map(),
        updateTime: null,
      },
      dataQuality: {
        completeness: {
          daily: 0,
          minute: 0,
          financial: 0,
        },
        latency: {
          marketData: 0,
          financialData: 0,
        },
      },
      loading: {
        syncTasks: false,
        marketData: false,
        financialData: false,
      },
    },
    system: {
      systemConfig: {
        trading: {
          defaultCommission: 0.0003,
          defaultSlippage: 0.001,
          tradeConfirm: true,
          autoCancelTimeout: 300,
        },
        risk: {
          maxPositionRatio: 0.2,
          maxDailyLoss: 0.05,
          enableBlacklist: true,
        },
        data: {
          autoSync: true,
          syncInterval: 300,
          keepHistoryDays: 365,
        },
        notification: {
          enableEmail: false,
          enableWechat: true,
          criticalAlerts: true,
        },
      },
      userManagement: {
        users: [],
        editingUser: null,
      },
      systemMonitor: {
        resources: {
          cpuUsage: 0,
          memoryUsage: 0,
          diskUsage: 0,
          networkUsage: 0,
        },
        services: [],
        database: {
          connections: 0,
          queryPerformance: 0,
          size: 0,
        },
      },
      systemLogs: {
        logs: [],
        filters: {
          level: [],
          module: [],
          dateRange: {
            start: "",
            end: "",
          },
          keyword: "",
        },
        pagination: {
          page: 1,
          pageSize: 50,
          total: 0,
        },
      },
      loading: {
        config: false,
        users: false,
        monitor: false,
        logs: false,
      },
    },
    layout: {
      topNavigation: {
        logo: "",
        platformName: "量化交易系统",
        marketIndicators: [],
        search: {
          placeholder: "搜索股票、策略...",
          recentSearches: [],
          hotSearches: [],
        },
        notifications: [],
        user: null,
        systemStatus: {
          connected: false,
          status: "unknown",
          message: "",
        },
      },
      siderNavigation: {
        collapsed: false,
        activeKey: "",
        openKeys: [],
        menuItems: [],
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
        quickActions: [],
      },
      theme: "light",
      language: "zh-CN",
      sidebar: {
        collapsed: false,
        width: 200,
        collapsedWidth: 64,
      },
      header: {
        height: 60,
        fixed: true,
        showBreadcrumb: true,
      },
      tabs: {
        enabled: true,
        list: [],
        activeTab: "",
      },
      layoutMode: "sidemenu",
      content: {
        padding: 20,
        backgroundColor: "#ffffff",
      },
      settings: {
        showSettings: false,
        fixedHeader: true,
        showTagsView: true,
        showSidebarLogo: true,
        showFooter: true,
      },
    },
    dashboard: {
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
    performance: {
      // 修复：使用正确的PerformanceState结构
      accountPerformance: {},
      strategyPerformance: {},
      comparisonData: null,
      analysisReports: {},
      loading: {
        account: false,
        strategy: false,
        comparison: false,
      },
      // 修复：使用正确的属性名
      tlist: [],
      currentStrategy: {
        id: null,
        detail: {},
        tradeRecords: [],
      },
    },
    risk: {
      riskRules: {
        rules: [],
        editingRule: null,
      },
      realTimeMonitoring: {
        accountRisk: {
          totalRisk: 0,
          positionRisk: 0,
          concentrationRisk: 0,
          liquidityRisk: 0,
        },
        strategyRisks: new Map(),
        marketRisk: {
          volatility: 0,
          correlation: 0,
          sentiment: 0,
        },
      },
      riskEvents: {
        events: [],
        statistics: {
          today: 0,
          critical: 0,
          unresolved: 0,
        },
      },
      blacklist: {
        stocks: [],
      },
      riskReports: {
        daily: null,
        weekly: null,
        monthly: null,
      },
      loading: {
        rules: false,
        monitoring: false,
        events: false,
        blacklist: false,
      },
    },
    strategyStudio: {
      backtestConfig: {
        basic: {
          strategyId: "",
          name: "",
          description: "",
        },
        timeRange: {
          startDate: "",
          endDate: "",
          frequency: "daily",
        },
        capital: {
          initial: 1000000,
          commission: 0.0003,
          slippage: 0.001,
        },
        universe: {
          type: "single",
          symbols: [],
          basketId: null,
        },
      },
      backtestTasks: {
        tasks: [],
        currentTaskId: null,
      },
      backtestResults: {
        performance: null,
        equityCurve: [],
        trades: [],
        positions: [],
        viewConfig: {
          selectedCharts: [],
          timeRange: {},
          comparisonBenchmark: null,
        },
      },
      parameterOptimization: {
        config: {
          parameters: new Map(),
          objective: "sharpe",
          method: "grid",
        },
        results: {
          bestParameters: null,
          parameterSpace: [],
          convergence: [],
        },
      },
      factorResearch: {
        factors: [],
        researchResults: {
          icAnalysis: null,
          factorReturns: null,
          correlation: null,
        },
      },
      loading: {
        backtest: false,
        optimization: false,
        research: false,
      },
    },
  };
}
