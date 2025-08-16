import {createRouter, createWebHistory, Router} from 'vue-router';
import routes from './routes';
import {authGuard, dataReadyGuard} from './guard';

// 获取基础 URL 的替代方案
const getBaseUrl = () => {
    // 从环境变量获取（需要配置构建工具）
    // if (import.meta.env.BASE_URL) {
    //     return import.meta.env.BASE_URL;
    // }

    // 从 window 对象获取（适用于生产环境）
    if (window.location.pathname.startsWith('/quant_web/')) {
        return '/quant_web/';
    }

    // 默认值
    return '/';
};

const router: Router = createRouter({
    history: createWebHistory(getBaseUrl()), // 使用替代方案
    routes
});

// 注册路由守卫
router.beforeEach(authGuard);
router.beforeEach(dataReadyGuard);

export default router;