<template>
  <div class="main-layout">
    <!-- 顶部状态栏 -->
    <AppHeader class="app-header" />

    <div class="main-content">
      <!-- 左侧导航栏 -->
      <AppSidebar
        class="app-sidebar"
        :class="{ collapsed: sidebarCollapsed }"
        @collapse="handleSidebarCollapse"
      />

      <!-- 中间工作区 -->
      <div class="workspace" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
        <router-view />
      </div>
    </div>

    <!-- 底部状态栏 -->
    <footer class="app-footer">
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
@use '@/assets/scss/global.scss';

.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--primary-bg);
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
  min-height: 0; /* 重要：确保flex容器可以缩小 */
}

.workspace {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background-color: var(--primary-bg);
  transition: margin-left 0.3s ease;
  margin-left: 0;

  &.sidebar-collapsed {
    margin-left: calc(var(--sidebar-collapsed-width) - var(--sidebar-width));
  }
}

.app-footer {
  height: var(--footer-height);
  background-color: var(--secondary-bg);
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  padding: 0 20px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0; /* 重要：防止底部状态栏被压缩 */

  .footer-section {
    display: flex;
    align-items: center;
    margin-right: 20px;

    i {
      margin-right: 6px;
      color: var(--accent-color);
    }
  }

  .footer-log {
    margin-left: auto;
    display: flex;
    align-items: center;
  }
}
</style>