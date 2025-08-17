import {createRouter, createWebHistory, Router} from 'vue-router';
import {routes} from './routes'; // 命名导入
import {authGuard, dataReadyGuard} from './guard';

const getBaseUrl = (): string => {
    // 优先从环境变量获取
    return import.meta.env.BASE_URL;

};

const router: Router = createRouter({
    history: createWebHistory(getBaseUrl()),
    routes,
    scrollBehavior(_to, _from, savedPosition) {
        // 保持滚动位置
        if (savedPosition) {
            return savedPosition;
        }
        // 新页面滚动到顶部
        return {top: 0};
    }
});

// 调整守卫执行顺序
router.beforeEach((_to, _from, _next) => {
    router.beforeEach((to, from, next) => dataReadyGuard(to, from, next));
    router.beforeEach((to, from, next) => authGuard(to, from, next));
});

export default router;