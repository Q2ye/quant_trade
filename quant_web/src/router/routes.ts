// routes.ts
import { RouteRecordRaw } from 'vue-router';
import Login from '@/views/Login.vue'; // 添加Login组件导入

const lazy = (path: string) => () => import(`@/${path}.vue`);


// 使用命名导出
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { menu: 'dashboard', layout: 'main', title: '交易驾驶舱' },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: lazy('views/Trade/Dashboard'),
        meta: { title: '交易驾驶舱' }
      }
    ]
  },
  {
    path: '/strategy',
    component: () => import('@/layouts/StrategyLayout.vue'),
    meta: { menu: 'strategy', layout: 'strategy', title: '策略工作室' },
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
    path: '/kline',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { menu: 'kline', layout: 'main', title: '智能K线' },
    children: [
      {
        path: '',
        name: 'KLine',
        component: lazy('views/Market/StockDetail'),
        meta: { title: '智能K线' }
      }
    ]
  },
  {
    path: '/basket',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { menu: 'basket', layout: 'main', title: '股票篮子' },
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
    path: '/report',
    component: () => import('@/layouts/ReportLayout.vue'),
    meta: { menu: 'report', layout: 'report', title: '回测报告' },
    children: [
      {
        path: '',
        name: 'ReportList',
        component: lazy('views/Strategy/BacktestReport'),
        meta: { title: '回测报告' }
      }
    ]
  },
  {
    path: '/performance',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { menu: 'performance', layout: 'main', title: '绩效分析' },
    children: [
      {
        path: '',
        name: 'Performance',
        component: lazy('views/Strategy/BacktestReport'),
        meta: { title: '绩效分析' }
      }
    ]
  },
  {
    path: '/settings',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { menu: 'settings', layout: 'main', title: '系统设置' },
    children: [
      {
        path: '',
        name: 'Settings',
        component: lazy('views/System/Settings'),
        meta: { title: '系统设置' }
      }
    ]
  },
  {
    path: '/risk',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { menu: 'risk', layout: 'main', title: '风险控制' },
    children: [
      {
        path: '',
        name: 'RiskManagement',
        component: lazy('views/Strategy/RiskManagement'),
        meta: { title: '风险控制' }
      }
    ]
  },
  {
    path: '/monitor',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { menu: 'monitor', layout: 'main', title: '系统监控' },
    children: [
      {
        path: '',
        name: 'SystemMonitor',
        component: lazy('views/System/Monitor'),
        meta: { title: '系统监控' }
      }
    ]
  },
  {
    path: '/login',
    name: 'Login',
    component: Login, // 使用导入的Login组件
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