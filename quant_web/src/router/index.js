import Vue from 'vue';
import Router from 'vue-router';
import routes from './routes'; // 导入统一路由配置
import { authGuard, dataReadyGuard } from './guard'; // 导入路由守卫

Vue.use(Router);

const router = new Router({
  mode: 'history', // 推荐使用history模式
  base: process.env.BASE_URL,
  routes // 使用统一路由配置
});

// 注册路由守卫
router.beforeEach(authGuard);
router.beforeEach(dataReadyGuard);

export default router;