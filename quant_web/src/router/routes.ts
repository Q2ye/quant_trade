// routes.ts
import { RouteRecordRaw } from "vue-router";
import Login from "@/views/Login.vue";

export const routes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/market/dashboard",
  },
  {
    path: "/dashboard",
    redirect: "/market/dashboard",
  },

  // ═══════════════════════════════════════════════
  // 市场数据 — Dashboard 入口 + 8 子页面 (hideInMenu)
  // ═══════════════════════════════════════════════

  // 旧路由 Redirect
  { path: "/market/overview", redirect: "/market/dashboard" },
  { path: "/market/macro", redirect: "/market/dashboard" },
  { path: "/market/limit-events", redirect: "/market/limit-analysis" },
  { path: "/market/financial", redirect: "/market/financial-compare" },
  { path: "/market/etf-market", redirect: "/market/etf" },
  {
    path: "/market/etf/:code",
    redirect: (to: any) => `/market/etf?focus=${to.params.code}`,
  },
  {
    path: "/market/index/:code",
    redirect: (to: any) => `/market/index?focus=${to.params.code}`,
  },
  { path: "/market/industry-strength", redirect: "/market/industry" },

  // 市场总览 (侧边栏唯一入口)
  {
    path: "/market/dashboard",
    name: "MarketDashboard",
    component: () => import("@/views/DataCenter/Market/MarketDashboard.vue"),
    meta: { menu: "market", layout: "main", title: "市场总览" },
  },
  // 个股详情 (钻取进入)
  {
    path: "/market/stock/:code",
    name: "StockDetail",
    component: () => import("@/views/DataCenter/Market/StockDetail.vue"),
    props: true,
    meta: {
      menu: "market",
      layout: "main",
      title: "个股详情",
      hideInMenu: true,
    },
  },
  // 指数分析 Hub
  {
    path: "/market/index",
    name: "IndexAnalysis",
    component: () => import("@/views/DataCenter/Market/IndexDetail.vue"),
    meta: {
      menu: "market",
      layout: "main",
      title: "指数分析",
      hideInMenu: true,
    },
  },
  // 行业分析
  {
    path: "/market/industry",
    name: "IndustryAnalysis",
    component: () => import("@/views/DataCenter/Market/IndustryAnalysis.vue"),
    meta: {
      menu: "market",
      layout: "main",
      title: "行业分析",
      hideInMenu: true,
    },
  },
  // 选股器
  {
    path: "/market/screener",
    name: "StockScreener",
    component: () => import("@/views/DataCenter/Market/StockScreener.vue"),
    meta: { menu: "market", layout: "main", title: "选股器", hideInMenu: true },
  },
  // ETF Hub
  {
    path: "/market/etf",
    name: "ETFMarket",
    component: () => import("@/views/DataCenter/Market/ETFMarket.vue"),
    meta: {
      menu: "market",
      layout: "main",
      title: "ETF 市场",
      hideInMenu: true,
    },
  },
  // 资金流向
  {
    path: "/market/money-flow",
    name: "MoneyFlow",
    component: () => import("@/views/DataCenter/Market/MoneyFlow.vue"),
    meta: {
      menu: "market",
      layout: "main",
      title: "资金流向",
      hideInMenu: true,
    },
  },
  // 涨跌停分析
  {
    path: "/market/limit-analysis",
    name: "LimitAnalysis",
    component: () => import("@/views/DataCenter/Market/LimitAnalysis.vue"),
    meta: {
      menu: "market",
      layout: "main",
      title: "涨跌停分析",
      hideInMenu: true,
    },
  },
  // 财务对比
  {
    path: "/market/financial-compare",
    name: "FinancialCompare",
    component: () => import("@/views/DataCenter/Market/FinancialHub.vue"),
    meta: {
      menu: "market",
      layout: "main",
      title: "财务对比",
      hideInMenu: true,
    },
  },

  // 数据中心
  {
    path: "/data/sync/overview",
    redirect: "/data/sync",
  },
  {
    path: "/data/sync/quality",
    name: "DataQuality",
    component: () => import("@/views/DataCenter/DataSync/DataQuality.vue"),
    meta: { menu: "", layout: "main", title: "数据质量", hideInMenu: true },
  },
  {
    path: "/data/sync",
    name: "DataSync",
    component: () => import("@/views/DataCenter/DataSync/DataSync.vue"),
    meta: { menu: "data-sync-overview", layout: "main", title: "数据同步" },
  },
  {
    path: "/data/sync/history",
    name: "SyncHistory",
    component: () => import("@/views/DataCenter/DataSync/SyncHistory.vue"),
    meta: { menu: "", layout: "main", title: "同步历史记录", hideInMenu: true },
  },
  {
    path: "/data/sync/history/:taskId",
    name: "SyncDetail",
    component: () => import("@/views/DataCenter/DataSync/SyncDetail.vue"),
    meta: { menu: "data-sync-overview", layout: "main", title: "同步任务详情" },
  },

  // 策略中心 — 旧路由 Redirect
  { path: "/strategy/build", redirect: "/strategies" },
  { path: "/strategy/backtest", redirect: "/backtest" },
  { path: "/strategy/factors", redirect: "/factors" },
  { path: "/backtest/studio", redirect: "/backtest" },
  { path: "/research/factor-research", redirect: "/factors" },
  { path: "/research/factor-library", redirect: "/factors" },
  { path: "/research/backtest-period", redirect: "/backtest" },

  // 策略中心
  {
    path: "/backtest",
    name: "BacktestWorkspace",
    component: () => import("@/views/StrategyCenter/Backtest/BacktestWorkspace.vue"),
    meta: { menu: "backtest-hub", layout: "main", title: "回测工作台" },
  },
  {
    path: "/factors",
    name: "FactorDashboard",
    component: () => import("@/views/StrategyCenter/FactorDashboard.vue"),
    meta: { menu: "factor-hub", layout: "main", title: "因子研究" },
  },
  {
    path: "/strategy/factors",
    redirect: "/factors",
  },
  {
    path: "/strategies/versions/:id",
    name: "StrategyVersions",
    component: () =>
      import("@/views/StrategyCenter/Build/StrategyVersions.vue"),
    meta: { menu: "strategies", layout: "main", title: "版本管理", hideInMenu: true },
  },
  {
    path: "/strategies/templates",
    name: "StrategyTemplates",
    component: () =>
      import("@/views/StrategyCenter/Build/StrategyTemplates.vue"),
    meta: { menu: "strategy-templates", layout: "main", title: "策略模板" },
  },
  {
    path: "/strategies",
    name: "StrategyList",
    component: () => import("@/views/StrategyCenter/Build/StrategyList.vue"),
    meta: { menu: "strategies", layout: "main", title: "策略列表" },
  },
  {
    // 编辑模式：URL 中的 :id 是后端生成的策略 UUID
    path: "/strategies/workspace/:id",
    name: "StrategyWorkspace",
    component: () => import("@/views/StrategyCenter/StrategyWorkspace.vue"),
    meta: { menu: "strategies", layout: "strategy", title: "策略工作台", hideInMenu: true },
  },
  {
    // 创建模式：无动态参数，新策略 ID 由后端在保存时生成
    path: "/strategies/workspace/new",
    name: "StrategyWorkspaceCreate",
    component: () => import("@/views/StrategyCenter/StrategyWorkspace.vue"),
    meta: { menu: "strategies", layout: "strategy", title: "新建策略", hideInMenu: true },
  },
  { path: "/strategies/create", redirect: "/strategies/workspace/new" },
  { path: "/strategies/edit/:id", redirect: (to: any) => `/strategies/workspace/${to.params.id}` },
  {
    path: "/strategies/portfolio",
    name: "PortfolioBuilder",
    component: () => import("@/views/StrategyCenter/Build/PortfolioBuilder.vue"),
    meta: { menu: "strategies", layout: "main", title: "策略组合" },
  },
  {
    path: "/strategies/risk/:id?",
    name: "StrategyRisk",
    component: () => import("@/views/StrategyCenter/Build/RiskManagement.vue"),
    props: true,
    meta: { menu: "strategy-risk", layout: "main", title: "策略风控" },
  },
  {
    path: "/backtest/report/:taskId",
    name: "BacktestReport",
    component: () =>
      import("@/views/StrategyCenter/Backtest/BacktestReport.vue"),
    props: true,
    meta: { menu: "backtest", layout: "report", title: "回测报告" },
  },
  {
    path: "/backtest/config",
    name: "BacktestConfig",
    component: () =>
      import("@/views/StrategyCenter/Backtest/BacktestConfig.vue"),
    meta: { menu: "backtest", layout: "main", title: "回测配置" },
  },
  // 交易工作台（统一集成篮子/订单/持仓/账户）
  {
    path: "/trade/workspace",
    name: "TradingWorkspace",
    component: () => import("@/views/TradeCenter/Workspace.vue"),
    meta: { menu: "trading-workspace", layout: "main", title: "交易工作台" },
  },
  // 旧路由重定向到工作台（保留路由名兼容）
  {
    path: "/baskets",
    redirect: { path: "/trade/workspace", query: { tab: "baskets" } },
  },
  {
    path: "/trade/orders",
    redirect: { path: "/trade/workspace", query: { tab: "orders" } },
  },
  {
    path: "/trade/positions",
    redirect: { path: "/trade/workspace", query: { tab: "positions" } },
  },
  {
    path: "/account",
    redirect: { path: "/trade/workspace", query: { tab: "account" } },
  },

  // 篮子独立页面（创建/编辑/详情）
  {
    path: "/baskets/create",
    name: "BasketCreate",
    component: () => import("@/views/TradeCenter/Basket/BasketEditor.vue"),
    meta: { menu: "baskets", layout: "main", title: "创建篮子" },
  },
  {
    path: "/baskets/edit/:id",
    name: "BasketEdit",
    component: () => import("@/views/TradeCenter/Basket/BasketEditor.vue"),
    props: true,
    meta: { menu: "baskets", layout: "main", title: "编辑篮子" },
  },
  {
    path: "/baskets/detail/:id",
    name: "BasketDetail",
    component: () => import("@/views/TradeCenter/Basket/BasketDetail.vue"),
    props: true,
    meta: { menu: "baskets", layout: "main", title: "篮子详情" },
  },

  // 交易执行
  {
    path: "/trade/execution",
    name: "ExecutionAnalysis",
    component: () =>
      import("@/views/TradeCenter/Execution/ExecutionAnalysis.vue"),
    meta: { menu: "execution-analysis", layout: "main", title: "执行分析" },
  },
  {
    path: "/trade",
    name: "TradingDashboard",
    component: () => import("@/views/TradeCenter/Trading/TradingDashboard.vue"),
    meta: { menu: "trading", layout: "main", title: "交易驾驶舱" },
  },

  // 监控中心
  {
    path: "/monitor/alerts",
    name: "AlertCenter",
    component: () => import("@/views/MonitorCenter/AlertCenter.vue"),
    meta: { menu: "monitor-alerts", layout: "main", title: "报警中心" },
  },

  // 风险监控
  {
    path: "/risk/monitor",
    name: "RiskMonitor",
    component: () => import("@/views/Risk/RiskMonitor.vue"),
    meta: { menu: "risk-monitor", layout: "main", title: "实时监控" },
  },
  {
    path: "/risk/rules",
    name: "RiskRules",
    component: () => import("@/views/Risk/RiskRules.vue"),
    meta: { menu: "risk-rules", layout: "main", title: "风控规则" },
  },
  {
    path: "/risk/events",
    name: "RiskEvents",
    component: () => import("@/views/Risk/RiskEvents.vue"),
    meta: { menu: "risk-events", layout: "main", title: "风控事件" },
  },
  {
    path: "/risk/blacklist",
    name: "RiskBlacklist",
    component: () => import("@/views/Risk/BlacklistManagement.vue"),
    meta: { menu: "blacklist", layout: "main", title: "黑名单管理" },
  },

  // 绩效分析
  {
    path: "/performance",
    name: "PerformanceHub",
    component: () =>
      import("@/views/StrategyCenter/Performance/PerformanceHub.vue"),
    meta: { menu: "performance-hub", layout: "main", title: "绩效总览" },
  },
  {
    path: "/performance/strategy",
    name: "StrategyPerformance",
    component: () =>
      import("@/views/StrategyCenter/Performance/StrategyPerformance.vue"),
    meta: {
      menu: "strategy-performance",
      layout: "main",
      title: "策略绩效",
      hideInMenu: true,
    },
  },
  {
    path: "/performance/attribution",
    name: "AttributionAnalysis",
    component: () =>
      import("@/views/StrategyCenter/Performance/AttributionAnalysis.vue"),
    meta: {
      menu: "attribution",
      layout: "main",
      title: "归因分析",
      hideInMenu: true,
    },
  },
  {
    path: "/performance/strategy/:id",
    name: "StrategyPerformanceDetail",
    component: () =>
      import("@/views/StrategyCenter/Performance/StrategyPerformance.vue"),
    props: true,
    meta: {
      menu: "strategy-performance",
      layout: "main",
      title: "策略绩效详情",
      hideInMenu: true,
    },
  },
  {
    path: "/performance/account",
    name: "AccountPerformance",
    component: () =>
      import("@/views/TradeCenter/Account/AccountPerformance.vue"),
    meta: {
      menu: "account-performance",
      layout: "main",
      title: "账户绩效",
      hideInMenu: true,
    },
  },
  {
    path: "/performance/comparison",
    name: "PerformanceComparison",
    component: () =>
      import("@/views/StrategyCenter/Performance/PerformanceComparison.vue"),
    meta: {
      menu: "performance-comparison",
      layout: "main",
      title: "绩效对比",
      hideInMenu: true,
    },
  },

  // 信号监控
  {
    path: "/signals",
    name: "SignalMonitor",
    component: () => import("@/views/Signal/SignalMonitor.vue"),
    meta: { menu: "signals", layout: "main", title: "信号监控" },
  },
  {
    path: "/signals/history",
    name: "SignalHistory",
    component: () => import("@/views/Signal/SignalHistory.vue"),
    meta: { menu: "signals", layout: "main", title: "信号历史" },
  },
  {
    path: "/signals/timeline",
    name: "SignalTimeline",
    component: () => import("@/views/Signal/SignalTimeline.vue"),
    meta: { menu: "signals", layout: "main", title: "信号时间线" },
  },

  // 系统管理
  {
    path: "/system/monitor",
    name: "SystemMonitor",
    component: () => import("@/views/System/Monitor.vue"),
    meta: { menu: "system-monitor", layout: "main", title: "系统监控" },
  },
  {
    path: "/system/logs",
    name: "SystemLogs",
    component: () => import("@/views/System/LogViewer.vue"),
    meta: { menu: "logs", layout: "main", title: "系统日志" },
  },
  {
    path: "/system/settings",
    name: "SystemSettings",
    component: () => import("@/views/System/Settings.vue"),
    meta: { menu: "settings", layout: "main", title: "系统设置" },
  },
  {
    path: "/system/users",
    name: "UserManagement",
    component: () => import("@/views/System/UserManagement.vue"),
    meta: { menu: "users", layout: "main", title: "用户管理" },
  },
  {
    path: "/system/data-sync",
    name: "SystemDataSync",
    component: () => import("@/views/System/DataSync.vue"),
    meta: { menu: "settings", layout: "main", title: "数据同步配置" },
  },

  // 重定向路由
  {
    path: "/redirect",
    name: "Redirect",
    component: () => import("@/views/Redirect.vue"),
    meta: { layout: "empty" },
  },

  // 登录页面
  {
    path: "/login",
    name: "Login",
    component: Login,
    meta: {
      title: "登录",
      layout: "empty",
      requiresAuth: false,
    },
  },

  // 注册页面
  {
    path: "/register",
    name: "Register",
    component: () => import("@/views/Register.vue"),
    meta: {
      title: "注册",
      layout: "empty",
      requiresAuth: false,
    },
  },

  // 404页面
  {
    path: "/:pathMatch(.*)*",
    name: "NotFound",
    component: () => import("@/views/Error/NotFound.vue"),
    meta: { layout: "empty", title: "页面未找到" },
  },
];
