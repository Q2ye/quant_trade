// main.ts
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './store';
import i18n from './locales';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import * as echarts from 'echarts';

import Antd from 'ant-design-vue';
import { Icon } from '@iconify/vue';



// 注册全局指令
import resize from './directives/resize';

const app = createApp(App);

// 注册图标组件
app.component('Icon', Icon);

// 设置全局属性
app.config.globalProperties.$echarts = echarts;

// 使用插件
app.use(store);
app.use(router);
app.use(i18n);
app.use(ElementPlus);
app.use(Antd);

// 注册指令
app.directive('resize', resize);

// 在应用挂载前加载主题
async function initializeApp() {
  try {
    // 挂载应用
    app.mount('#app');

    // 发送应用就绪事件
    document.dispatchEvent(new Event('vue-app-ready'));

  } catch (error) {
    console.error('Failed to initialize app:', error);
    // 即使主题加载失败也继续挂载应用
    app.mount('#app');
  }
}

// 启动应用
initializeApp().catch(error => {
  console.error('Failed to initialize app:', error);
});
