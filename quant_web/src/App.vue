<script lang="ts">
import { defineComponent, computed, ref, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import MainLayout from "@/layouts/MainLayout.vue";
import ReportLayout from "@/layouts/ReportLayout.vue";
import StrategyLayout from "@/layouts/StrategyLayout.vue";
import TradeLayout from "@/layouts/TradeLayout.vue";
import EmptyLayout from "@/layouts/EmptyLayout.vue";

export default defineComponent({
  name: "App",
  components: {
    MainLayout,
    ReportLayout,
    StrategyLayout,
    TradeLayout,
    EmptyLayout,
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();
    const isAppVisible = ref(false);

    // 根据当前路由计算激活的菜单
    const currentMenu = computed(() => {
      const path = route.path;
      if (path.startsWith("/dashboard")) return "dashboard";
      if (path.startsWith("/strategy")) return "strategy";
      if (path.startsWith("/kline")) return "kline";
      if (path.startsWith("/report")) return "report";
      if (path.startsWith("/basket")) return "basket";
      return "dashboard";
    });

    // 根据路由元信息计算当前布局
    const currentLayout = computed(() => {
      // 优先使用当前路由的布局元信息
      const layout = (route.meta.layout as string) || "main";

      // 映射布局名称到组件
      const layoutMap: Record<string, any> = {
        main: MainLayout,
        strategy: StrategyLayout,
        trade: TradeLayout,
        report: ReportLayout,
        empty: EmptyLayout,
      };

      return layoutMap[layout] || MainLayout;
    });

    // 处理菜单切换
    const handleMenuChange = (menuId: string) => {
      const routes: Record<string, string> = {
        dashboard: "/dashboard",
        strategy: "/strategy",
        kline: "/kline",
        report: "/report",
        basket: "/basket",
      };

      if (routes[menuId] && route.path !== routes[menuId]) {
        router.push(routes[menuId]);
      }
    };

    // 设置页面标题
    watch(
      () => route.meta.title,
      (newTitle) => {
        if (newTitle) {
          document.title = `${newTitle} - 专业级A股量化交易平台`;
        }
      },
      { immediate: true },
    );

    // 应用加载完成后显示
    onMounted(() => {
      isAppVisible.value = true;

      // 只在需要时触发初始数据加载
      if (route.path !== '/login') {
        // 检查是否有token，有token才加载数据
        const token = localStorage.getItem('token');
        if (token) {
          // 使用setTimeout避免阻塞主线程
          setTimeout(() => {
            store.dispatch("system/loadInitialData").catch((error: any) => {
              console.error("初始数据加载失败:", error);
            });
          }, 100);
        }
      }
    });

    return {
      currentLayout,
      currentMenu,
      isAppVisible,
      handleMenuChange,
    };
  }
});
</script>