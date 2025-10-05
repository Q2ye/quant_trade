// routes.ts
import { RouteRecordRaw } from 'vue-router';
import Login from '@/views/Login.vue';

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard/Overview.vue'),
    meta: { menu: 'dashboard', layout: 'main', title: '总览' }
  },
  // 策略管理
  {
    path: '/strategies',
    name: 'StrategyList',
    component: () => import('@/views/Strategy/StrategyList.vue'),
    meta: { menu: 'strategies', layout: 'main', title: '策略列表' }
  },
  {
    path: '/strategies/create',
    name: 'StrategyCreate',
    component: () => import('@/views/Strategy/StrategyEditor.vue'),
    meta: { menu: 'strategies', layout: 'main', title: '创建策略' }
  },
  {
    path: '/strategies/edit/:id',
    name: 'StrategyEdit',
    component: () => import('@/views/Strategy/StrategyEditor.vue'),
    props: true,
    meta: { menu: 'strategies', layout: 'main', title: '编辑策略' }
  },
  {
    path: '/strategies/backtest',
    name: 'BacktestStudio',
    component: () => import('@/views/Backtest/BacktestStudio.vue'),
    meta: { menu: 'backtest', layout: 'main', title: '回测工作室' }
  },
  {
    path: '/strategies/backtest/report/:taskId',
    name: 'BacktestReport',
    component: () => import('@/views/Backtest/BacktestReport.vue'),
    props: true,
    meta: { menu: 'backtest', layout: 'report', title: '回测报告' }
  },
  {
    path: '/strategies/factor-research',
    name: 'FactorResearch',
    component: () => import('@/views/Research/FactorResearch.vue'),
    meta: { menu: 'research', layout: 'main', title: '因子研究' }
  },
  // 篮子管理
  {
    path: '/baskets',
    name: 'BasketList',
    component: () => import('@/views/Basket/BasketList.vue'),
    meta: { menu: 'baskets', layout: 'main', title: '篮子列表' }
  },
  {
    path: '/baskets/create',
    name: 'BasketCreate',
    component: () => import('@/views/Basket/BasketEditor.vue'),
    meta: { menu: 'baskets', layout: 'main', title: '创建篮子' }
  },
  {
    path: '/baskets/edit/:id',
    name: 'BasketEdit',
    component: () => import('@/views/Basket/BasketEditor.vue'),
    props: true,
    meta: { menu: 'baskets', layout: 'main', title: '编辑篮子' }
  },
  {
    path: '/baskets/detail/:id',
    name: 'BasketDetail',
    component: () => import('@/views/Basket/BasketDetail.vue'),
    props: true,
    meta: { menu: 'baskets', layout: 'main', title: '篮子详情' }
  },
  // 交易执行
  {
    path: '/trading',
    name: 'TradingDashboard',
    component: () => import('@/views/Trade/TradingDashboard.vue'),
    meta: { menu: 'trading', layout: 'main', title: '交易驾驶舱' }
  },
  {
    path: '/trading/orders',
    name: 'OrderManagement',
    component: () => import('@/views/Trade/OrderManagement.vue'),
    meta: { menu: 'trading', layout: 'main', title: '订单管理' }
  },
  {
    path: '/trading/positions',
    name: 'PositionManagement',
    component: () => import('@/views/Trade/PositionManagement.vue'),
    meta: { menu: 'trading', layout: 'main', title: '持仓管理' }
  },
  {
    path: '/trading/account',
    name: 'AccountManagement',
    component: () => import('@/views/Trade/AccountManagement.vue'),
    meta: { menu: 'trading', layout: 'main', title: '账户管理' }
  },
  // 市场数据
  {
    path: '/market/stocks',
    name: 'StockList',
    component: () => import('@/views/Market/StockList.vue'),
    meta: { menu: 'market', layout: 'main', title: '股票列表' }
  },
  {
    path: '/market/stock/:code',
    name: 'StockDetail',
    component: () => import('@/views/Market/StockDetail.vue'),
    props: true,
    meta: { menu: 'market', layout: 'main', title: '个股详情' }
  },
  {
    path: '/market/etfs',
    name: 'ETFList',
    component: () => import('@/views/Market/ETFList.vue'),
    meta: { menu: 'market', layout: 'main', title: 'ETF列表' }
  },
  {
    path: '/market/etf/:code',
    name: 'ETFDetail',
    component: () => import('@/views/Market/ETFDetail.vue'),
    props: true,
    meta: { menu: 'market', layout: 'main', title: 'ETF详情' }
  },
  {
    path: '/market/indexes',
    name: 'IndexList',
    component: () => import('@/views/Market/IndexList.vue'),
    meta: { menu: 'market', layout: 'main', title: '指数列表' }
  },
  {
    path: '/market/index/:code',
    name: 'IndexDetail',
    component: () => import('@/views/Market/IndexDetail.vue'),
    props: true,
    meta: { menu: 'market', layout: 'main', title: '指数详情' }
  },
  // 数据同步
  {
    path: '/data-sync',
    name: 'DataSync',
    component: () => import('@/views/DataSync/DataSync.vue'),
    meta: { menu: 'data-sync', layout: 'main', title: '数据同步' }
  },
  {
    path: '/data-sync/tasks',
    name: 'SyncTaskMonitor',
    component: () => import('@/views/DataSync/TaskMonitor.vue'),
    meta: { menu: 'data-sync', layout: 'main', title: '同步任务监控' }
  },
  {
    path: '/data-sync/history',
    name: 'SyncHistory',
    component: () => import('@/views/DataSync/SyncHistory.vue'),
    meta: { menu: 'data-sync', layout: 'main', title: '同步历史记录' }
  },
  // 系统管理
  {
    path: '/system/monitor',
    name: 'SystemMonitor',
    component: () => import('@/views/System/Monitor.vue'),
    meta: { menu: 'system', layout: 'main', title: '系统监控' }
  },
  {
    path: '/system/logs',
    name: 'SystemLogs',
    component: () => import('@/views/System/LogViewer.vue'),
    meta: { menu: 'system', layout: 'main', title: '系统日志' }
  },
  {
    path: '/system/settings',
    name: 'SystemSettings',
    component: () => import('@/views/System/Settings.vue'),
    meta: { menu: 'system', layout: 'main', title: '系统设置' }
  },
  {
    path: '/system/users',
    name: 'UserManagement',
    component: () => import('@/views/System/UserManagement.vue'),
    meta: { menu: 'system', layout: 'main', title: '用户管理' }
  },
  // 绩效分析
  {
    path: '/performance/strategy/:id',
    name: 'StrategyPerformance',
    component: () => import('@/views/Performance/StrategyPerformance.vue'),
    props: true,
    meta: { menu: 'performance', layout: 'main', title: '策略绩效' }
  },
  {
    path: '/performance/account',
    name: 'AccountPerformance',
    component: () => import('@/views/Performance/AccountPerformance.vue'),
    meta: { menu: 'performance', layout: 'main', title: '账户绩效' }
  },
  {
    path: '/performance/comparison',
    name: 'PerformanceComparison',
    component: () => import('@/views/Performance/PerformanceComparison.vue'),
    meta: { menu: 'performance', layout: 'main', title: '绩效对比' }
  },
  // 风险管理
  {
    path: '/risk/rules',
    name: 'RiskRules',
    component: () => import('@/views/Risk/RiskRules.vue'),
    meta: { menu: 'risk', layout: 'main', title: '风控规则' }
  },
  {
    path: '/risk/events',
    name: 'RiskEvents',
    component: () => import('@/views/Risk/RiskEvents.vue'),
    meta: { menu: 'risk', layout: 'main', title: '风控事件' }
  },
  {
    path: '/risk/blacklist',
    name: 'RiskBlacklist',
    component: () => import('@/views/Risk/BlacklistManagement.vue'),
    meta: { menu: 'risk', layout: 'main', title: '黑名单管理' }
  },
  // 信号监控
  {
    path: '/signals',
    name: 'SignalMonitor',
    component: () => import('@/views/Signal/SignalMonitor.vue'),
    meta: { menu: 'signals', layout: 'main', title: '信号监控' }
  },
  {
    path: '/signals/history',
    name: 'SignalHistory',
    component: () => import('@/views/Signal/SignalHistory.vue'),
    meta: { menu: 'signals', layout: 'main', title: '信号历史' }
  },
  // 登录页面
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: {
      title: '登录',
      layout: 'empty',
      requiresAuth: false
    }
  },
  // 404页面
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/Error/NotFound.vue'),
    meta: { layout: 'empty', title: '页面未找到' }
  }
];