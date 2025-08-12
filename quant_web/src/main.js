import {createApp} from 'vue';
import App from './App.vue';
import router from './router/index.js';
import store from './store/index.js';
import i18n from './locales/index.js';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import * as echarts from 'echarts';
import {authGuard, dataReadyGuard} from './router/guard.js';

const app = createApp(App);
app.config.globalProperties.$echarts = echarts;
app.use(store);
app.use(router);
app.use(i18n);
app.use(ElementPlus);
// 注册全局指令
import resize from './directives/resize.js';

app.directive('resize', resize);
// 注册路由守卫
router.beforeEach(authGuard);
router.beforeEach(dataReadyGuard);
app.mount('#app');