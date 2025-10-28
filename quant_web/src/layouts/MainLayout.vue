<template>
  <div class="main-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <!-- 顶部状态栏 -->
    <AppHeader class="app-header page-header-anti-bleed" />

    <!-- 侧边栏和工作区容器 -->
    <div class="layout-container">
      <!-- 左侧导航栏 -->
      <AppSidebar
        class="app-sidebar sidebar-anti-bleed"
        :class="{ collapsed: sidebarCollapsed }"
        @collapse="handleSidebarCollapse"
      />

      <!-- 中间工作区 -->
      <main class="workspace sidebar-content-adapter">
        <div class="workspace-content">
          <router-view />
        </div>
      </main>
    </div>

    <!-- 底部状态栏 -->
    <footer class="app-footer no-bleed-through">
      <div class="footer-content">
        <div class="footer-section">
          <i class="fas fa-microchip"></i>
          <span>CPU: {{ systemStats.cpuUsage }}% | 内存: {{ systemStats.memoryUsage }}%</span>
        </div>
        <div class="footer-section">
          <i class="fas fa-network-wired"></i>
          <span>数据连接: {{ systemStats.dataStatus }}</span>
        </div>
        <div class="footer-section">
          <i class="fas fa-exchange-alt"></i>
          <span>交易通道: {{ systemStats.tradeStatus }}</span>
        </div>
        <div class="footer-log">
          <i class="fas fa-terminal"></i>
          <span>{{ systemStats.lastLog }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/ui/AppHeader.vue'
import AppSidebar from '../components/ui/AppSidebar.vue'

export default {
  name: "MainLayout",
  components: {
    AppHeader,
    AppSidebar
  },
  setup() {
    const route = useRoute()
    const sidebarCollapsed = ref(false)
    const systemStats = reactive({
      cpuUsage: 0,
      memoryUsage: 0,
      dataStatus: '正常',
      tradeStatus: '已连接',
      lastLog: '[2023-08-20 09:30:05] 策略引擎启动成功'
    })

    const handleSidebarCollapse = (collapsed: boolean) => {
      sidebarCollapsed.value = collapsed
    }

    // 模拟系统状态更新
    let statsInterval: number
    onMounted(() => {
      statsInterval = setInterval(() => {
        systemStats.cpuUsage = Math.floor(Math.random() * 30) + 30
        systemStats.memoryUsage = Math.floor(Math.random() * 20) + 50
      }, 5000) as unknown as number
    })

    onUnmounted(() => {
      clearInterval(statsInterval)
    })

    return {
      sidebarCollapsed,
      systemStats,
      handleSidebarCollapse
    }
  }
}
</script>

<style lang="scss" scoped>
@use 'sass:map';
@use '@/assets/scss/themes' as *;
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as local_mix;

.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: theme-color("primary-bg");
  position: relative;
  transition: background-color theme-animation("transition-normal");
}

.layout-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
  min-height: 0;
}

.workspace {
  flex: 1;
  overflow-y: auto;
  //margin-left: 0;
  width: calc(100% - #{theme-layout("sidebar-width")});
  transition: all theme-animation("transition-normal");
  background: theme-color("primary-bg");

  .workspace-content {
    min-height: 100%;
    //padding: theme-layout("content-padding");

    @include local_mix.media-breakpoint-down(md) {
      padding: map.get($spacers, 3);
    }

    @include local_mix.media-breakpoint-down(sm) {
      padding: map.get($spacers, 2);
    }
  }

  .sidebar-collapsed & {
    margin-left: 0;
    width: calc(100% - #{theme-layout("sidebar-collapsed-width")});
  }
}

.app-footer {
  height: 30px;
  background-color: theme-color("toolbar-bg");
  border-top: theme-border("border-width") solid theme-color("border-color");
  display: flex;
  align-items: center;
  padding: 0 map.get($spacers, 3);
  font-size: theme-typography("font-size-base") * 0.85;
  color: theme-color("text-secondary");
  flex-shrink: 0;
  position: relative;
  z-index: 100;

  .footer-content {
    display: flex;
    align-items: center;
    width: 100%;
    max-width: 1400px;
    margin: 0 auto;
  }

  .footer-section {
    display: flex;
    align-items: center;
    margin-right: map.get($spacers, 4);
    white-space: nowrap;

    i {
      margin-right: map.get($spacers, 1);
      color: theme-color("accent-color");
      font-size: theme-typography("font-size-base") * 0.8;
    }

    span {
      font-size: theme-typography("font-size-base") * 0.8;
      color: theme-color("text-secondary");
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

    i {
      margin-right: map.get($spacers, 1);
      color: theme-color("accent-color");
      font-size: theme-typography("font-size-base") * 0.8;
    }

    span {
      font-size: theme-typography("font-size-base") * 0.8;
      color: theme-color("text-secondary");
    }
  }
}

// 响应式设计
@include local_mix.media-breakpoint-down(lg) {
  .workspace {
    margin-left: theme-layout("sidebar-collapsed-width");
    width: calc(100% - #{theme-layout("sidebar-collapsed-width")});

    .sidebar-collapsed & {
      margin-left: 0;
      width: 100%;
    }
  }
}

@include local_mix.media-breakpoint-down(md) {
  .app-footer {
    .footer-content {
      justify-content: space-between;
    }

    .footer-section {
      margin-right: map.get($spacers, 3);

      &:nth-child(3) {
        display: none;
      }
    }

    .footer-log {
      max-width: 200px;
    }
  }
}

@include local_mix.media-breakpoint-down(sm) {
  .workspace {
    margin-left: 0;
    width: 100%;

    .sidebar-collapsed & {
      //margin-left: theme-layout("sidebar-collapsed-width");
      width: calc(100% - #{theme-layout("sidebar-collapsed-width")});
    }
  }

  .app-footer {
    padding: 0 map.get($spacers, 2);

    .footer-section {
      margin-right: map.get($spacers, 2);

      &:nth-child(2) {
        display: none;
      }

      span {
        font-size: theme-typography("font-size-base") * 0.7;
      }
    }

    .footer-log {
      max-width: 150px;

      span {
        font-size: theme-typography("font-size-base") * 0.7;
      }
    }
  }

  .workspace .workspace-content {
    padding: map.get($spacers, 2);
  }
}

// 侧边栏折叠动画优化
.sidebar-content-adapter {
  transition: all theme-animation("transition-normal");

  .sidebar-collapsed & {
    transform: theme-animation("hover-transform");
    //opacity: 0.95;
  }
}

// 主题过渡
.main-layout {
  transition: background-color theme-animation("transition-normal");
}

// 滚动条样式
.workspace {
  @include local_mix.custom-scrollbar;
}
</style>