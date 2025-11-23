<template>
  <n-config-provider>
    <n-loading-bar-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <n-message-provider>
            <component :is="currentLayout">
              <router-view />
            </component>
          </n-message-provider>
        </n-notification-provider>
      </n-dialog-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>

<script lang="ts">
import { defineComponent, computed } from "vue";
import { useRoute } from "vue-router";
import MainLayout from "@/layouts/MainLayout.vue";
import ReportLayout from "@/layouts/ReportLayout.vue";
import EmptyLayout from "@/layouts/EmptyLayout.vue";

// 引入 Naive UI 组件
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  NLoadingBarProvider
} from 'naive-ui';

export default defineComponent({
  name: "App",
  components: {
    MainLayout,
    ReportLayout,
    EmptyLayout,
    NConfigProvider,
    NMessageProvider,
    NDialogProvider,
    NNotificationProvider,
    NLoadingBarProvider
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