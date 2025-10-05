<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useLayoutStore } from '@/store/modules/layout'

const router = useRouter()
const route = useRoute()
const layoutStore = useLayoutStore()

// 导航菜单项
const menuItems = ref([
  {
    name: 'dashboard',
    label: '仪表盘',
    icon: 'DataBoard',
    path: '/dashboard'
  },
  {
    name: 'strategy',
    label: '策略管理',
    icon: 'TrendCharts',
    path: '/strategy',
    children: [
      { name: 'strategy-list', label: '策略列表', path: '/strategy/list' },
      { name: 'strategy-editor', label: '策略编辑器', path: '/strategy/editor' },
      { name: 'backtest-studio', label: '回测工作室', path: '/strategy/backtest' }
    ]
  },
  {
    name: 'basket',
    label: '篮子管理',
    icon: 'Box',
    path: '/basket'
  },
  {
    name: 'trade',
    label: '交易执行',
    icon: 'ShoppingCart',
    path: '/trade',
    children: [
      { name: 'trading-cockpit', label: '交易驾驶舱', path: '/trade/cockpit' },
      { name: 'order-management', label: '订单管理', path: '/trade/orders' },
      { name: 'position-management', label: '持仓管理', path: '/trade/positions' }
    ]
  },
  {
    name: 'market',
    label: '市场数据',
    icon: 'Histogram',
    path: '/market'
  },
  {
    name: 'performance',
    label: '绩效分析',
    icon: 'PieChart',
    path: '/performance'
  },
  {
    name: 'risk',
    label: '风险管理',
    icon: 'Warning',
    path: '/risk'
  },
  {
    name: 'system',
    label: '系统管理',
    icon: 'Setting',
    path: '/system'
  }
])

// 当前激活的菜单
const activeMenu = computed(() => route.name as string)

// 处理菜单点击
const handleMenuClick = (item: any) => {
  if (item.path && !item.children) {
    router.push(item.path)
    // 移动端点击菜单后自动收起
    if (window.innerWidth < 768) {
      layoutStore.setSidebarCollapsed(true)
    }
  }
}

// 处理子菜单点击
const handleSubMenuClick = (subItem: any) => {
  router.push(subItem.path)
  if (window.innerWidth < 768) {
    layoutStore.setSidebarCollapsed(true)
  }
}
</script>

<template>
  <div class="navigation-menu">
    <el-menu
      :default-active="activeMenu"
      :collapse="layoutStore.sidebarCollapsed"
      class="sidebar-menu"
      background-color="#001529"
      text-color="#rgba(255, 255, 255, 0.65)"
      active-text-color="#1890ff"
    >
      <div class="menu-logo" v-if="!layoutStore.sidebarCollapsed">
        <h2>量化交易平台</h2>
      </div>

      <template v-for="item in menuItems" :key="item.name">
        <!-- 有子菜单的项 -->
        <el-sub-menu
          v-if="item.children"
          :index="item.name"
        >
          <template #title>
            <el-icon>
              <component :is="item.icon" />
            </el-icon>
            <span>{{ item.label }}</span>
          </template>

          <el-menu-item
            v-for="child in item.children"
            :key="child.name"
            :index="child.name"
            @click="handleSubMenuClick(child)"
          >
            {{ child.label }}
          </el-menu-item>
        </el-sub-menu>

        <!-- 没有子菜单的项 -->
        <el-menu-item
          v-else
          :index="item.name"
          @click="handleMenuClick(item)"
        >
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <template #title>{{ item.label }}</template>
        </el-menu-item>
      </template>
    </el-menu>
  </div>
</template>

<style scoped>
.navigation-menu {
  height: 100%;
}

.sidebar-menu {
  height: 100%;
  border: none;
}

.menu-logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #002140;
}

.menu-logo h2 {
  color: #fff;
  margin: 0;
  font-size: 18px;
  font-weight: bold;
}

/* 菜单项样式调整 */
:deep(.el-menu-item) {
  height: 48px;
  line-height: 48px;
}

:deep(.el-sub-menu__title) {
  height: 48px;
  line-height: 48px;
}

/* 激活状态样式 */
:deep(.el-menu-item.is-active) {
  background-color: #1890ff !important;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .sidebar-menu:not(.el-menu--collapse) {
    width: 240px;
  }
}
</style>