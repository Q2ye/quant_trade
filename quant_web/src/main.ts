import {createApp} from 'vue';
import App from './App.vue';
import router from './router';
import store from './store';
import i18n from './locales';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import * as echarts from 'echarts';

import Antd from 'ant-design-vue'
import { Icon } from '@iconify/vue'
// 注册全局指令
import resize from './directives/resize';

const app = createApp(App);

app.component('Icon', Icon)
// 设置全局属性
app.config.globalProperties.$echarts = echarts;

// 使用插件
app.use(store);
app.use(router);
app.use(i18n);
app.use(ElementPlus);
app.use(Antd)

// 注册指令
app.directive('resize', resize);

app.mount('#app');

// 发送应用就绪事件
document.dispatchEvent(new Event('vue-app-ready'));
