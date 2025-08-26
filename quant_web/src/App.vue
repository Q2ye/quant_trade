<template>
  <div
    id="app"
    :class="['app-container', { visible: isAppVisible }]"
  >
    <!-- 根据路由元信息选择布局 -->
    <component 
      :is="currentLayout" 
      :active-menu="currentMenu"
      @menu-change="handleMenuChange"
    >
      <router-view />
    </component>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';
import MainLayout from '@/layouts/MainLayout.vue';
import ReportLayout from '@/layouts/ReportLayout.vue';
import StrategyLayout from '@/layouts/StrategyLayout.vue';
import TradeLayout from '@/layouts/TradeLayout.vue';

export default defineComponent({
  name: 'App',
  components: {
    MainLayout,
    ReportLayout,
    StrategyLayout,
    TradeLayout
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();
    const isAppVisible = ref(false);

    // 根据当前路由计算激活的菜单
    const currentMenu = computed(() => {
      const path = route.path;
      if (path.startsWith('/market')) return 'market';
      if (path.startsWith('/strategy')) return 'strategy';
      if (path.startsWith('/trade')) return 'trade';
      if (path.startsWith('/data')) return 'data';
      if (path.startsWith('/basket')) return 'basket'; // 修复股票篮子菜单层级
      return 'market';
    });

    // 根据路由元信息计算当前布局
    const currentLayout = computed(() => {
      // 优先使用当前路由的布局元信息
      const layout = (route.meta.layout as string) || 'main';

      // 映射布局名称到组件
      const layoutMap: Record<string, any> = {
        main: MainLayout,
        strategy: StrategyLayout,
        trade: TradeLayout,
        report: ReportLayout
      };

      return layoutMap[layout] || MainLayout;
    });

    // 处理菜单切换
    const handleMenuChange = (menuId: string) => {
      const routes: Record<string, string> = {
        market: '/market',
        strategy: '/strategy',
        trade: '/trade',
        data: '/data',
        basket: '/basket' // 修复股票篮子菜单层级
      };
      
      if (routes[menuId] && route.path !== routes[menuId]) {
        router.push(routes[menuId]);
      }
    };

    // 设置页面标题
    watch(() => route.meta.title, (newTitle) => {
      if (newTitle) {
        document.title = `${newTitle} - 专业级A股量化交易平台`;
      }
    }, { immediate: true });

    return {
      currentLayout,
      currentMenu,
      isAppVisible,
      handleMenuChange
    };
  },
  mounted() {
    // 应用加载完成后显示
    this.isAppVisible = true;

    // 触发初始数据加载
    const store = useStore();
    store.dispatch('system/loadInitialData');
  }
});
</script>

<style lang="scss">
@use "@/assets/scss/global.scss";
@use "@/assets/scss/variables" as *;

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background-color: var(--background-dark);
  color: var(--text-primary);
  overflow: hidden;
}

#app {
  height: 100vh;
  overflow: hidden;
  opacity: 0;
  transition: opacity 0.5s ease;

  &.visible {
    opacity: 1;
  }
}

.app-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>
[file content end]