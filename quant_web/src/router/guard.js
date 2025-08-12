// 路由守卫
import store from '../store';

export const authGuard = (to, from, next) => {
  const publicPages = ['/login'];
  const authRequired = !publicPages.includes(to.path);
  const isAuthenticated = store.getters['user/isAuthenticated'];

  // 添加登录页重定向逻辑
  if (to.path === '/login' && isAuthenticated) {
    return next('/market');
  }

  if (authRequired && !isAuthenticated) {
    next('/login');
  } else {
    next();
  }
};

export const dataReadyGuard = (to, from, next) => {
  if (store.state.system.dataLoaded) {
    next();
  } else {
    store.dispatch('system/loadInitialData').then(() => {
      next();
    }).catch(error => {
      console.error('Failed to load initial data:', error);
      next('/error?code=data_load_failed');
    });
  }
};