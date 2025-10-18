// routes.ts
import {RouteRecordRaw} from 'vue-router';
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
        meta: {menu: 'dashboard', layout: 'main', title: '总览'}
    },

    // 市场数据
    {
        path: '/market/overview',
        name: 'MarketOverview',
        component: () => import('@/views/Market/MarketOverview.vue'),
        meta: {menu: 'market', layout: 'main', title: '市场概览'}
    },
    {
        path: '/market/stocks',
        name: 'StockList',
        component: () => import('@/views/Market/StockList.vue'),
        meta: {menu: 'market', layout: 'main', title: '股票列表'}
    },
    {
        path: '/market/stock/:code',
        name: 'StockDetail',
        component: () => import('@/views/Market/StockDetail.vue'),
        props: true,
        meta: {menu: 'market', layout: 'main', title: '个股详情'}
    },
    {
        path: '/market/etfs',
        name: 'ETFList',
        component: () => import('@/views/Market/ETFList.vue'),
        meta: {menu: 'market', layout: 'main', title: 'ETF列表'}
    },
    {
        path: '/market/etf/:code',
        name: 'ETFDetail',
        component: () => import('@/views/Market/ETFDetail.vue'),
        props: true,
        meta: {menu: 'market', layout: 'main', title: 'ETF详情'}
    },
    {
        path: '/market/indexes',
        name: 'IndexList',
        component: () => import('@/views/Market/IndexList.vue'),
        meta: {menu: 'market', layout: 'main', title: '指数列表'}
    },
    {
        path: '/market/index/:code',
        name: 'IndexDetail',
        component: () => import('@/views/Market/IndexDetail.vue'),
        props: true,
        meta: {menu: 'market', layout: 'main', title: '指数详情'}
    },
    {
        path: '/market/industry-strength',
        name: 'IndustryStrength',
        component: () => import('@/views/Market/IndustryStrength.vue'),
        meta: {menu: 'market', layout: 'main', title: '行业强弱'}
    },
    {
        path: '/market/money-flow',
        name: 'MoneyFlow',
        component: () => import('@/views/Market/MoneyFlow.vue'),
        meta: {menu: 'market', layout: 'main', title: '资金流向'}
    },
    {
        path: '/market/limit-analysis',
        name: 'LimitAnalysis',
        component: () => import('@/views/Market/LimitAnalysis.vue'),
        meta: {menu: 'market', layout: 'main', title: '涨跌停分析'}
    },

    // 数据中心 - 更新为数据同步总览
    {
        path: '/data-sync-overview',
        name: 'DataSyncOverview',
        component: () => import('@/views/DataSync/DataSyncOverview.vue'),
        meta: {menu: 'data-sync-overview', layout: 'main', title: '同步总览'}
    },
    // 隐藏原有的数据同步相关菜单，但保留路由用于内部跳转
    {
        path: '/data-quality',
        name: 'DataQuality',
        component: () => import('@/views/DataSync/DataQuality.vue'),
        meta: {menu: '', layout: 'main', title: '数据质量', hideInMenu: true}
    },
    {
        path: '/data-sync',
        name: 'DataSync',
        component: () => import('@/views/DataSync/DataSync.vue'),
        meta: {menu: '', layout: 'main', title: '数据同步', hideInMenu: true}
    },
    {
        path: '/data-sync/tasks',
        name: 'SyncTaskMonitor',
        component: () => import('@/views/DataSync/TaskMonitor.vue'),
        meta: {menu: '', layout: 'main', title: '同步任务监控', hideInMenu: true}
    },
    {
        path: '/data-sync/history',
        name: 'SyncHistory',
        component: () => import('@/views/DataSync/SyncHistory.vue'),
        meta: {menu: '', layout: 'main', title: '同步历史记录', hideInMenu: true}
    },

    // 策略中心
    {
        path: '/strategies/templates',
        name: 'StrategyTemplates',
        component: () => import('@/views/Strategy/StrategyTemplates.vue'),
        meta: {menu: 'strategy-templates', layout: 'main', title: '策略模板'}
    },
    {
        path: '/strategies',
        name: 'StrategyList',
        component: () => import('@/views/Strategy/StrategyList.vue'),
        meta: {menu: 'strategies', layout: 'main', title: '策略列表'}
    },
    {
        path: '/strategies/create',
        name: 'StrategyCreate',
        component: () => import('@/views/Strategy/StrategyEditor.vue'),
        meta: {menu: 'strategies', layout: 'main', title: '创建策略'}
    },
    {
        path: '/strategies/edit/:id',
        name: 'StrategyEdit',
        component: () => import('@/views/Strategy/StrategyEditor.vue'),
        props: true,
        meta: {menu: 'strategies', layout: 'main', title: '编辑策略'}
    },
    {
        path: '/strategies/backtest',
        name: 'BacktestStudio',
        component: () => import('@/views/Backtest/BacktestStudio.vue'),
        meta: {menu: 'backtest', layout: 'main', title: '回测工作室'}
    },
    {
        path: '/strategies/backtest/report/:taskId',
        name: 'BacktestReport',
        component: () => import('@/views/Backtest/BacktestReport.vue'),
        props: true,
        meta: {menu: 'backtest', layout: 'report', title: '回测报告'}
    },
    {
        path: '/strategies/factor-research',
        name: 'FactorResearch',
        component: () => import('@/views/Research/FactorResearch.vue'),
        meta: {menu: 'research', layout: 'main', title: '因子研究'}
    },
    {
        path: '/strategies/factor-library',
        name: 'FactorConfig',
        component: () => import('@/views/Research/FactorLibrary.vue'),
        meta: {menu: 'factor-library', layout: 'main', title: '因子库管理'}
    },
    {
        path: '/strategies/backtest-period',
        name: 'BacktestPeriod',
        component: () => import('@/views/Research/BacktestPeriod.vue'),
        meta: {menu: 'backtest-period', layout: 'main', title: '回溯周期'}
    },

    // 组合管理
    {
        path: '/portfolio/analysis',
        name: 'PortfolioAnalysis',
        component: () => import('@/views/Portfolio/PortfolioAnalysis.vue'),
        meta: {menu: 'portfolio-analysis', layout: 'main', title: '组合分析'}
    },
    {
        path: '/baskets',
        name: 'BasketList',
        component: () => import('@/views/Basket/BasketList.vue'),
        meta: {menu: 'baskets', layout: 'main', title: '篮子列表'}
    },
    {
        path: '/baskets/create',
        name: 'BasketCreate',
        component: () => import('@/views/Basket/BasketEditor.vue'),
        meta: {menu: 'baskets', layout: 'main', title: '创建篮子'}
    },
    {
        path: '/baskets/edit/:id',
        name: 'BasketEdit',
        component: () => import('@/views/Basket/BasketEditor.vue'),
        props: true,
        meta: {menu: 'baskets', layout: 'main', title: '编辑篮子'}
    },
    {
        path: '/baskets/detail/:id',
        name: 'BasketDetail',
        component: () => import('@/views/Basket/BasketDetail.vue'),
        props: true,
        meta: {menu: 'baskets', layout: 'main', title: '篮子详情'}
    },

    // 交易执行
    {
        path: '/trading/execution-analysis',
        name: 'ExecutionAnalysis',
        component: () => import('@/views/Trade/ExecutionAnalysis.vue'),
        meta: {menu: 'execution-analysis', layout: 'main', title: '执行分析'}
    },
    {
        path: '/trading',
        name: 'TradingDashboard',
        component: () => import('@/views/Trade/TradingDashboard.vue'),
        meta: {menu: 'trading', layout: 'main', title: '交易驾驶舱'}
    },
    {
        path: '/trading/orders',
        name: 'OrderManagement',
        component: () => import('@/views/Trade/OrderManagement.vue'),
        meta: {menu: 'orders', layout: 'main', title: '订单管理'}
    },
    {
        path: '/trading/positions',
        name: 'PositionManagement',
        component: () => import('@/views/Trade/PositionManagement.vue'),
        meta: {menu: 'positions', layout: 'main', title: '持仓管理'}
    },
    {
        path: '/trading/account',
        name: 'AccountManagement',
        component: () => import('@/views/Trade/AccountManagement.vue'),
        meta: {menu: 'account', layout: 'main', title: '账户管理'}
    },

    // 风险监控
    {
        path: '/risk/monitor',
        name: 'RiskMonitor',
        component: () => import('@/views/Risk/RiskMonitor.vue'),
        meta: {menu: 'risk-monitor', layout: 'main', title: '实时监控'}
    },
    {
        path: '/risk/rules',
        name: 'RiskRules',
        component: () => import('@/views/Risk/RiskRules.vue'),
        meta: {menu: 'risk-rules', layout: 'main', title: '风控规则'}
    },
    {
        path: '/risk/events',
        name: 'RiskEvents',
        component: () => import('@/views/Risk/RiskEvents.vue'),
        meta: {menu: 'risk-events', layout: 'main', title: '风控事件'}
    },
    {
        path: '/risk/blacklist',
        name: 'RiskBlacklist',
        component: () => import('@/views/Risk/BlacklistManagement.vue'),
        meta: {menu: 'blacklist', layout: 'main', title: '黑名单管理'}
    },

    // 绩效分析
    {
        path: '/performance/strategy',
        name: 'StrategyPerformance',
        component: () => import('@/views/Performance/StrategyPerformance.vue'),
        meta: {menu: 'strategy-performance', layout: 'main', title: '策略绩效'}
    },
    {
        path: '/performance/attribution',
        name: 'AttributionAnalysis',
        component: () => import('@/views/Performance/AttributionAnalysis.vue'),
        meta: {menu: 'attribution', layout: 'main', title: '归因分析'}
    },
    {
        path: '/performance/strategy/:id',
        name: 'StrategyPerformanceDetail',
        component: () => import('@/views/Performance/StrategyPerformance.vue'),
        props: true,
        meta: {menu: 'strategy-performance', layout: 'main', title: '策略绩效详情'}
    },
    {
        path: '/performance/account',
        name: 'AccountPerformance',
        component: () => import('@/views/Performance/AccountPerformance.vue'),
        meta: {menu: 'account-performance', layout: 'main', title: '账户绩效'}
    },
    {
        path: '/performance/comparison',
        name: 'PerformanceComparison',
        component: () => import('@/views/Performance/PerformanceComparison.vue'),
        meta: {menu: 'performance-comparison', layout: 'main', title: '绩效对比'}
    },

    // 信号监控
    {
        path: '/signals',
        name: 'SignalMonitor',
        component: () => import('@/views/Signal/SignalMonitor.vue'),
        meta: {menu: 'signals', layout: 'main', title: '信号监控'}
    },
    {
        path: '/signals/history',
        name: 'SignalHistory',
        component: () => import('@/views/Signal/SignalHistory.vue'),
        meta: {menu: 'signals', layout: 'main', title: '信号历史'}
    },

    // 系统管理
    {
        path: '/system/monitor',
        name: 'SystemMonitor',
        component: () => import('@/views/System/Monitor.vue'),
        meta: {menu: 'system-monitor', layout: 'main', title: '系统监控'}
    },
    {
        path: '/system/logs',
        name: 'SystemLogs',
        component: () => import('@/views/System/LogViewer.vue'),
        meta: {menu: 'logs', layout: 'main', title: '系统日志'}
    },
    {
        path: '/system/settings',
        name: 'SystemSettings',
        component: () => import('@/views/System/Settings.vue'),
        meta: {menu: 'settings', layout: 'main', title: '系统设置'}
    },
    {
        path: '/system/users',
        name: 'UserManagement',
        component: () => import('@/views/System/UserManagement.vue'),
        meta: {menu: 'users', layout: 'main', title: '用户管理'}
    },

    // 重定向路由
    {
        path: '/redirect',
        name: 'Redirect',
        component: () => import('@/views/Redirect.vue'),
        meta: {layout: 'empty'}
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
        meta: {layout: 'empty', title: '页面未找到'}
    }
];