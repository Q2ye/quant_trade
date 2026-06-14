<template>
  <div
    class="main-layout bg-gradient-mesh"
    :class="[{ 'sidebar-collapsed': sidebarCollapsed }]"
  >
    <!-- 全局3D粒子背景（position:absolute 填充整个 main-layout） -->
    <ParticleBackground :opacity="0.55" :size="0.025" />

    <!-- 顶部状态栏 -->
    <AppHeader class="app-header" />

    <!-- 侧边栏和工作区容器 -->
    <div class="layout-container">
      <!-- 左侧导航栏 -->
      <AppSidebar
        class="app-sidebar"
        :class="{ collapsed: sidebarCollapsed }"
        @collapse="handleSidebarCollapse"
      />

      <!-- 中间工作区 -->
      <main class="workspace sidebar-content-adapter">
        <div class="workspace-content">
          <router-view v-slot="{ Component, route }">
            <component :is="Component" :key="route.path" />
          </router-view>
        </div>
      </main>
    </div>

    <!-- 底部状态栏 -->
    <footer class="app-footer">
      <div class="footer-content">
        <div class="footer-section">
          <n-icon size="14" class="footer-icon">
            <smart-icon name="CloudDownload" />
          </n-icon>
          <span>{{ systemStats.dataStatus }}</span>
        </div>
        <div class="footer-section">
          <n-icon size="14" class="footer-icon">
            <smart-icon name="SwapHorizontal" />
          </n-icon>
          <span>{{ systemStats.tradeStatus }}</span>
        </div>
        <div class="footer-log">
          <n-icon size="14" class="footer-icon">
            <smart-icon name="Terminal" />
          </n-icon>
          <span>{{ systemStats.lastLog }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script lang="ts">
import {
  defineComponent,
  defineAsyncComponent,
  onMounted,
  onUnmounted,
  reactive,
  ref,
} from "vue";
import { NIcon } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";

import AppHeader from "../components/common/AppHeader.vue";
import AppSidebar from "../components/common/AppSidebar.vue";

const ParticleBackground = defineAsyncComponent(
  () => import("@/components/three/ParticleBackground.vue"),
);

export default defineComponent({
  name: "MainLayout",
  components: {
    AppHeader,
    AppSidebar,
    ParticleBackground,
    NIcon,
    SmartIcon,
  },
  setup() {
    const sidebarCollapsed = ref(false);
    const systemStats = reactive({
      dataStatus: "检测中…",
      tradeStatus: "检测中…",
      lastLog: "",
    });

    const handleSidebarCollapse = (collapsed: boolean) => {
      sidebarCollapsed.value = collapsed;
    };

    // 定期拉取真实系统健康状态
    let statsTimer: number;
    async function updateStats() {
      try {
        const systemAPI = (await import("@/api/system")).default;
        const health = await systemAPI.healthCheck();
        const deps = (health as any)?.dependencies;
        if (deps) {
          systemStats.dataStatus = deps.database ? "数据库正常" : "数据库断连";
          systemStats.tradeStatus = deps.dataSource ? "数据源正常" : "数据源断连";
        }
      } catch {
        systemStats.dataStatus = "状态获取失败";
        systemStats.tradeStatus = "状态获取失败";
      }
      // 当前时间作为最新活动时间
      const now = new Date();
      systemStats.lastLog = `[${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")} ${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}:${String(now.getSeconds()).padStart(2,"0")}] 系统运行中`;
    }
    onMounted(() => {
      updateStats();
      statsTimer = setInterval(updateStats, 30000) as unknown as number; // 每30秒刷新
    });

    onUnmounted(() => {
      clearInterval(statsTimer);
    });

    return {
      tokens,
      sidebarCollapsed,
      systemStats,
      handleSidebarCollapse,
    };
  },
});
</script>

<style lang="scss" scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  height: var(--vh-full);
  max-height: var(--vh-full);
  position: relative;
  overflow: hidden;
}

.layout-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
  z-index: 2;
  min-height: 0;
  height: calc(var(--vh-full) - var(--header-height, 60px) - 30px);
  background: transparent;
}

.workspace {
  width: calc(100% - var(--sidebar-expanded-width, 240px));
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;

  /*
   * .workspace-content — 工作区内容容器
   *
   * 左右内边距由各页面的 .content-section 提供，.page-header 自然贴边
   *   - top: 0    → .page-header 紧贴 AppHeader
   *   - left/right: 0 → .page-header 紧贴侧边栏和 workspace 右边缘
   *   - bottom: 16px → 底部留白，避免内容贴边
   */
  .workspace-content {
    flex: 1;
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    padding: 0 0 16px 0;

    /*
     * 页面根元素 — <router-view> 渲染的页面组件
     * flex: 1 使其填满 .workspace-content 的剩余空间
     * overflow-y: auto 使页面内容超出时出现纵向滚动条
     */
    > * {
      flex: 1;
      overflow-y: auto;
    }
  }

  .sidebar-collapsed & {
    margin-left: 0;
    width: calc(100% - var(--sidebar-collapsed-width, 64px));
  }
}

.app-footer {
  height: 30px;
  background-color: var(--n-card-color);
  border-top: 1px solid var(--n-border-color);
  display: flex;
  align-items: center;
  padding: 0 16px;
  font-size: 12px;
  color: var(--n-text-color-2);
  flex-shrink: 0;
  position: relative;
  z-index: 100;

  .footer-content {
    display: flex;
    align-items: center;
    width: 100%;
    margin: 0 auto;
  }

  .footer-section {
    display: flex;
    align-items: center;
    margin-right: 16px;
    white-space: nowrap;

    .footer-icon {
      margin-right: 4px;
      color: var(--n-primary-color);
    }

    span {
      font-size: 12px;
      color: var(--n-text-color-2);
    }
  }

  .footer-log {
    margin-left: auto;
    display: flex;
    align-items: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 300px;

    .footer-icon {
      margin-right: 4px;
      color: var(--n-primary-color);
    }

    span {
      font-size: 12px;
      color: var(--n-text-color-2);
    }
  }
}

.sidebar-content-adapter {
  transition: all 0.3s ease;

  .sidebar-collapsed & {
    transform: translateX(0);
  }
}

:deep(.n-config-provider) {
  height: 100%;

  & > * {
    height: 100%;
  }
}

:deep(.n-layout) {
  background: transparent;

  &.n-layout--absolute-positioned {
    position: relative;
  }
}

:deep(.n-layout-scroll-container) {
  height: 100%;
  overflow: auto;
}

/* 3D particles: z-index handled internally by ParticleBackground.vue */
</style>
