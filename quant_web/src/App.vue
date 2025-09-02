<template>
  <component :is="currentLayout">
    <router-view />
  </component>
</template>

<script lang="ts">
import { defineComponent, computed } from "vue";
import { useRoute } from "vue-router";
import MainLayout from "@/layouts/MainLayout.vue";
import ReportLayout from "@/layouts/ReportLayout.vue";
import EmptyLayout from "@/layouts/EmptyLayout.vue";

export default defineComponent({
  name: "App",
  components: {
    MainLayout,
    ReportLayout,
    EmptyLayout,
  },
  setup() {
    const route = useRoute();

    // 根据路由元信息计算当前布局
    const currentLayout = computed(() => {
      const layout = (route.meta.layout as string) || "main";

      const layoutMap: Record<string, any> = {
        main: MainLayout,
        report: ReportLayout,
        empty: EmptyLayout,
      };

      return layoutMap[layout] || MainLayout;
    });

    return {
      currentLayout,
    };
  }
});
</script>