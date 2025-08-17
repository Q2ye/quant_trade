import { RouteRecordRaw } from 'vue-router';
import { lazy } from '@/utils/lazyLoad';

// 使用命名导出
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/market'
  },
  {
    path: '/market',
    component: lazy('layouts/MainLayout'),
    meta: { menu: 'market', layout: 'main' },
    children: [
      {
        path: '',
        name: 'Market',
        component: lazy('views/Market/Index'),
        meta: { title: '行情中心' }
      },
      {
        path: 'stock/:code',
        name: 'StockDetail',
        component: lazy('views/Market/StockDetail'),
        props: true,
        meta: { title: '个股详情' }
      },
      {
        path: 'etf',
        name: 'ETFMarket',
        component: lazy('views/Market/ETFMarket'),
        meta: { title: 'ETF行情' }
      },
      {
        path: 'index',
        name: 'IndexBoard',
        component: lazy('views/Market/IndexBoard'),
        meta: { title: '指数看板' }
      }
    ]
  },
  {
    path: '/strategy',
    component: lazy('layouts/StrategyLayout'),
    meta: { menu: 'strategy', layout: 'strategy' },
    children: [
      {
        path: '',
        name: 'StrategyList',
        component: lazy('views/Strategy/StrategyList'),
        meta: { title: '策略列表' }
      },
      {
        path: 'create',
        name: 'StrategyCreate',
        component: lazy('views/Strategy/StrategyEditor'),
        meta: { title: '创建策略' }
      },
      {
        path: 'edit/:id',
        name: 'StrategyEdit',
        component: lazy('views/Strategy/StrategyEditor'),
        props: true,
        meta: { title: '编辑策略' }
      },
      {
        path: 'backtest/:id',
        name: 'BacktestReport',
        component: lazy('views/Strategy/BacktestReport'),
        props: true,
        meta: { title: '回测报告', layout: 'report' }
      },
      {
        path: 'risk',
        name: 'RiskManagement',
        component: lazy('views/Strategy/RiskManagement'),
        meta: { title: '风险管理' }
      }
    ]
  },
  {
    path: '/basket',
    component: lazy('layouts/MainLayout'),
    meta: { menu: 'basket', layout: 'main' },
    children: [
      {
        path: '',
        name: 'BasketList',
        component: lazy('views/Basket/BasketList'),
        meta: { title: '篮子列表' }
      },
      {
        path: 'create',
        name: 'BasketCreate',
        component: lazy('views/Basket/BasketEditor'),
        meta: { title: '创建篮子' }
      },
      {
        path: 'edit/:id',
        name: 'BasketEdit',
        component: lazy('views/Basket/BasketEditor'),
        props: true,
        meta: { title: '编辑篮子' }
      },
      {
        path: 'detail/:id',
        name: 'BasketDetail',
        component: lazy('views/Basket/BasketDetail'),
        props: true,
        meta: { title: '篮子详情' }
      }
    ]
  },
  {
    path: '/trade',
    component: lazy('layouts/TradeLayout'),
    meta: { menu: 'trade', layout: 'trade' },
    children: [
      {
        path: '',
        name: 'TradeDashboard',
        component: lazy('views/Trade/Dashboard'),
        meta: { title: '交易驾驶舱' }
      },
      {
        path: 'positions',
        name: 'Positions',
        component: lazy('views/Trade/Position'),
        meta: { title: '持仓明细' }
      },
      {
        path: 'orders',
        name: 'Orders',
        component: lazy('views/Trade/OrderHistory'),
        meta: { title: '订单记录' }
      },
      {
        path: 'execute',
        name: 'TradeExecute',
        component: lazy('views/Trade/TradeExecution'),
        meta: { title: '交易执行' }
      }
    ]
  },
  {
    path: '/system',
    component: lazy('layouts/MainLayout'),
    meta: { menu: 'system', layout: 'main' },
    children: [
      {
        path: 'monitor',
        name: 'SystemMonitor',
        component: lazy('views/System/Monitor'),
        meta: { title: '系统监控' }
      },
      {
        path: 'logs',
        name: 'LogViewer',
        component: lazy('views/System/LogViewer'),
        meta: { title: '日志查看' }
      },
      {
        path: 'data',
        name: 'DataSync',
        component: lazy('views/System/DataSync'),
        meta: { title: '数据同步' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: lazy('views/System/Settings'),
        meta: { title: '系统设置' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/market'
  }
];