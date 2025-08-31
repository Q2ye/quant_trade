// index.ts
import { createRouter, createWebHistory, Router } from 'vue-router';
import { routes } from './routes';
import { authGuard, dataReadyGuard, layoutGuard } from './guard';

const getBaseUrl = (): string => {
    // 优先从环境变量获取
    return import.meta.env.BASE_URL;

};

const router: Router = createRouter({
  history: createWebHistory(getBaseUrl()),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }
    return { top: 0 };
  }
});

// 正确注册路由守卫
router.beforeEach(authGuard);
router.beforeEach(dataReadyGuard);
router.beforeEach(layoutGuard);

export default router;