<script setup lang="ts">
import { computed } from 'vue'
import { useLayoutStore } from '@/store/modules/layout'
import Navigation from './Navigation.vue'
import UserMenu from './UserMenu.vue'

const layoutStore = useLayoutStore()

// 切换侧边栏折叠状态
const toggleSidebar = () => {
  layoutStore.setSidebarCollapsed(!layoutStore.sidebarCollapsed)
}

// 页面标题
const pageTitle = computed(() => {
  // 这里可以根据当前路由动态设置标题
  return '量化交易平台'
})

// 系统状态
const systemStatus = computed(() => {
  return {
    connected: true, // WebSocket连接状态
    lastUpdate: new Date().toLocaleTimeString(),
    marketStatus: '交易中' // 市场状态
  }
})
</script>

<template>
  <div class="app-header">
    <!-- 左侧：Logo和菜单切换 -->
    <div class="header-left">
      <div class="sidebar-toggle" @click="toggleSidebar">
        <el-icon>
          <Expand v-if="layoutStore.sidebarCollapsed" />
          <Fold v-else />
        </el-icon>
      </div>

      <div class="logo">
        <img src="@/assets/logo.png" alt="Logo" class="logo-img" />
        <span class="logo-text">{{ pageTitle }}</span>
      </div>
    </div>

    <!-- 中间：面包屑和系统状态 -->
    <div class="header-center">
      <el-breadcrumb separator="/" class="breadcrumb">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>当前页面</el-breadcrumb-item>
      </el-breadcrumb>

      <div class="system-status">
        <el-tag
          :type="systemStatus.connected ? 'success' : 'danger'"
          size="small"
        >
          {{ systemStatus.connected ? '已连接' : '未连接' }}
        </el-tag>
        <span class="status-text">市场: {{ systemStatus.marketStatus }}</span>
        <span class="update-time">最后更新: {{ systemStatus.lastUpdate }}</span>
      </div>
    </div>

    <!-- 右侧：用户菜单和工具 -->
    <div class="header-right">
      <!-- 快捷工具 -->
      <div class="quick-tools">
        <el-tooltip content="全屏" placement="bottom">
          <el-button text circle>
            <el-icon><FullScreen /></el-icon>
          </el-button>
        </el-tooltip>

        <el-tooltip content="消息通知" placement="bottom">
          <el-button text circle>
            <el-icon><Bell /></el-icon>
            <el-badge :value="5" class="badge" />
          </el-button>
        </el-tooltip>

        <el-tooltip content="系统设置" placement="bottom">
          <el-button text circle>
            <el-icon><Setting /></el-icon>
          </el-button>
        </el-tooltip>
      </div>

      <!-- 用户菜单 -->
      <UserMenu />
    </div>
  </div>

  <!-- 导航菜单 -->
  <Navigation />
</template>

<style scoped>
.app-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.sidebar-toggle:hover {
  background-color: var(--el-fill-color-light);
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-img {
  width: 32px;
  height: 32px;
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
  color: var(--el-text-color-primary);
}

.header-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.breadcrumb {
  font-size: 14px;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.status-text {
  margin: 0 8px;
}

.update-time {
  font-size: 11px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-tools {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-right: 16px;
}

.badge {
  position: absolute;
  top: -5px;
  right: -5px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .app-header {
    padding: 0 8px;
  }

  .logo-text {
    display: none;
  }

  .header-center {
    display: none;
  }

  .quick-tools {
    margin-right: 8px;
  }
}
</style>