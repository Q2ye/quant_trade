// 路由定义
import { lazy } from '../utils/lazyLoad.js';

const routes = [
  {
    path: '/',
    redirect: '/market'
  },
  {
    path: '/market',
    component: lazy('layouts/MainLayout'),
    meta: { menu: 'market' },
    children: [
      {
        path: '',
        name: 'Market',
        component: lazy('views/Market/Index')
      },
      {
        path: 'stock/:code',
        name: 'StockDetail',
        component: lazy('views/Market/StockDetail'),
        props: true
      },
      {
        path: 'etf',
        name: 'ETFMarket',
        component: lazy('views/Market/ETFMarket')
      },
      {
        path: 'index',
        name: 'IndexBoard',
        component: lazy('views/Market/IndexBoard')
      }
    ]
  },
  {
    path: '/strategy',
    component: lazy('layouts/StrategyLayout'),
    meta: { menu: 'strategy' },
    children: [
      {
        path: '',
        name: 'StrategyList',
        component: lazy('views/Strategy/StrategyList')
      },
      {
        path: 'create',
        name: 'StrategyCreate',
        component: lazy('views/Strategy/StrategyEditor')
      },
      {
        path: 'edit/:id',
        name: 'StrategyEdit',
        component: lazy('views/Strategy/StrategyEditor'),
        props: true
      },
      {
        path: 'backtest/:id',
        name: 'BacktestReport',
        component: lazy('views/Strategy/BacktestReport'),
        props: true
      },
      {
        path: 'risk',
        name: 'RiskManagement',
        component: lazy('views/Strategy/RiskManagement')
      }
    ]
  },
  {
    path: '/basket',
    component: lazy('layouts/MainLayout'),
    meta: { menu: 'basket' },
    children: [
      {
        path: '',
        name: 'BasketList',
        component: lazy('views/Basket/BasketList')
      },
      {
        path: 'create',
        name: 'BasketCreate',
        component: lazy('views/Basket/BasketEditor')
      },
      {
        path: 'edit/:id',
        name: 'BasketEdit',
        component: lazy('views/Basket/BasketEditor'),
        props: true
      },
      {
        path: 'detail/:id',
        name: 'BasketDetail',
        component: lazy('views/Basket/BasketDetail'),
        props: true
      }
    ]
  },
  {
    path: '/trade',
    component: lazy('layouts/TradeLayout'),
    meta: { menu: 'trade' },
    children: [
      {
        path: '',
        name: 'TradeDashboard',
        component: lazy('views/Trade/Dashboard')
      },
      {
        path: 'positions',
        name: 'Positions',
        component: lazy('views/Trade/Position')
      },
      {
        path: 'orders',
        name: 'Orders',
        component: lazy('views/Trade/OrderHistory')
      },
      {
        path: 'execute',
        name: 'TradeExecute',
        component: lazy('views/Trade/TradeExecution')
      }
    ]
  },
  {
    path: '/system',
    component: lazy('layouts/MainLayout'),
    meta: { menu: 'system' },
    children: [
      {
        path: 'monitor',
        name: 'SystemMonitor',
        component: lazy('views/System/Monitor')
      },
      {
        path: 'logs',
        name: 'LogViewer',
        component: lazy('views/System/LogViewer')
      },
      {
        path: 'data',
        name: 'DataSync',
        component: lazy('views/System/DataSync')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: lazy('views/System/Settings')
      }
    ]
  },
  {
    path: '*',
    redirect: '/market'
  }
];

export default routes;