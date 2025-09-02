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
    component: () => import('@/views/Trade/Dashboard.vue'),
    meta: { menu: 'dashboard', layout: 'main', title: '交易驾驶舱' }
  },
  {
    path: '/strategy',
    name: 'StrategyList',
    component: () => import('@/views/Strategy/StrategyList.vue'),
    meta: { menu: 'strategy', layout: 'main', title: '策略列表' }
  },
  {
    path: '/strategy/create',
    name: 'StrategyCreate',
    component: () => import('@/views/Strategy/StrategyEditor.vue'),
    meta: { menu: 'strategy', layout: 'main', title: '创建策略' }
  },
  {
    path: '/strategy/edit/:id',
    name: 'StrategyEdit',
    component: () => import('@/views/Strategy/StrategyEditor.vue'),
    props: true,
    meta: { menu: 'strategy', layout: 'main', title: '编辑策略' }
  },
  {
    path: '/strategy/backtest/:id',
    name: 'BacktestReport',
    component: () => import('@/views/Strategy/BacktestReport.vue'),
    props: true,
    meta: { menu: 'strategy', layout: 'report', title: '回测报告' }
  },
  {
    path: '/strategy/risk',
    name: 'RiskManagement',
    component: () => import('@/views/Strategy/RiskManagement.vue'),
    meta: { menu: 'strategy', layout: 'main', title: '风险管理' }
  },
  {
    path: '/kline',
    name: 'KLine',
    component: () => import('@/views/Market/StockDetail.vue'),
    meta: { menu: 'kline', layout: 'main', title: '智能K线' }
  },
  {
    path: '/basket',
    name: 'BasketList',
    component: () => import('@/views/Basket/BasketList.vue'),
    meta: { menu: 'basket', layout: 'main', title: '篮子列表' }
  },
  {
    path: '/basket/create',
    name: 'BasketCreate',
    component: () => import('@/views/Basket/BasketEditor.vue'),
    meta: { menu: 'basket', layout: 'main', title: '创建篮子' }
  },
  {
    path: '/basket/edit/:id',
    name: 'BasketEdit',
    component: () => import('@/views/Basket/BasketEditor.vue'),
    props: true,
    meta: { menu: 'basket', layout: 'main', title: '编辑篮子' }
  },
  {
    path: '/basket/detail/:id',
    name: 'BasketDetail',
    component: () => import('@/views/Basket/BasketDetail.vue'),
    props: true,
    meta: { menu: 'basket', layout: 'main', title: '篮子详情' }
  },
  {
    path: '/report',
    name: 'ReportList',
    component: () => import('@/views/Strategy/BacktestReport.vue'),
    meta: { menu: 'report', layout: 'report', title: '回测报告' }
  },
  {
    path: '/performance',
    name: 'Performance',
    component: () => import('@/views/Strategy/BacktestReport.vue'),
    meta: { menu: 'performance', layout: 'main', title: '绩效分析' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/System/Settings.vue'),
    meta: { menu: 'settings', layout: 'main', title: '系统设置' }
  },
  {
    path: '/risk',
    name: 'RiskControl',
    component: () => import('@/views/Strategy/RiskManagement.vue'),
    meta: { menu: 'risk', layout: 'main', title: '风险控制' }
  },
  {
    path: '/monitor',
    name: 'SystemMonitor',
    component: () => import('@/views/System/Monitor.vue'),
    meta: { menu: 'monitor', layout: 'main', title: '系统监控' }
  },
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
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
];