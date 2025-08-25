<!--左侧导航栏-->
<template>
  <div
    class="app-sidebar"
    :class="{ collapsed }"
  >
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      background-color="transparent"
      text-color="#b0bec5"
      active-text-color="#1890ff"
      :router="true"
      :unique-opened="true"
    >
      <template
        v-for="menu in menus"
        :key="menu.id"
      >
        <!-- 有子菜单的项 -->
        <el-sub-menu
          v-if="menu.children"
          :index="menu.id"
        >
          <template #title>
            <i :class="menu.icon" />
            <span>{{ menu.name }}</span>
          </template>
          <el-menu-item
            v-for="child in menu.children"
            :key="child.id"
            :index="child.id"
            :route="child.path"
          >
            <i :class="child.icon || 'fas fa-caret-right'" />
            <span>{{ child.name }}</span>
          </el-menu-item>
        </el-sub-menu>

        <!-- 无子菜单的项 -->
        <el-menu-item
          v-else
          :index="menu.id"
          :route="menu.path"
        >
          <i :class="menu.icon" />
          <span>{{ menu.name }}</span>
        </el-menu-item>
      </template>
    </el-menu>

    <div class="sidebar-footer">
      <div class="system-info">
        <span>CPU: 42%</span>
        <span>内存: 65%</span>
      </div>
      <div class="version">
        v1.0.0
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "AppSidebar",
  data() {
    return {
      activeMenu: 'market',
      collapsed: false,
      menus: [
        {
          id: 'market',
          name: '行情中心',
          icon: 'el-icon-data-line',
          children: [
            {id: 'index', name: '大盘指数', path: '/market/index'},
            {id: 'stocks', name: '个股行情', path: '/market/stocks'},
            {id: 'etf', name: 'ETF行情', path: '/market/etf'}
          ]
        },
        {
          id: 'strategy',
          name: '策略工作室',
          icon: 'el-icon-cpu',
          children: [
            {id: 'strategy-list', name: '策略列表', path: '/strategy/list'},
            {id: 'strategy-editor', name: '策略编辑器', path: '/strategy/editor'},
            {id: 'backtest', name: '回测分析', path: '/strategy/backtest'}
          ]
        },
        {
          id: 'basket',
          name: '股票篮子',
          icon: 'el-icon-files',
          path: '/basket'
        },
        {
          id: 'trade',
          name: '交易管理',
          icon: 'el-icon-shopping-cart-full',
          children: [
            {id: 'dashboard', name: '交易驾驶舱', path: '/trade/dashboard'},
            {id: 'position', name: '持仓管理', path: '/trade/position'},
            {id: 'orders', name: '订单记录', path: '/trade/orders'}
          ]
        },
        {
          id: 'system',
          name: '系统管理',
          icon: 'el-icon-setting',
          children: [
            {id: 'monitor', name: '系统监控', path: '/system/monitor'},
            {id: 'logs', name: '日志查看', path: '/system/logs'},
            {id: 'data', name: '数据管理', path: '/system/data'},
            {id: 'settings', name: '系统设置', path: '/system/settings'}
          ]
        }
      ]
    }
  },
  watch: {
    $route() {
      this.setActiveMenu()
    }
  },
  created() {
    this.setActiveMenu()
  },
  methods: {
    setActiveMenu() {
      this.activeMenu = this.$route.path.split('/')[1]
    },

    toggleCollapse() {
      this.collapsed = !this.collapsed
      this.$emit('collapse', this.collapsed)
    },

    navigate(path) {
      this.$router.push(path)
    }
  }
}
</script>

<style scoped>
.app-sidebar {
  width: 220px;
  height: 100vh;
  background-color: #001529;
  color: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  overflow: hidden;
}

.app-sidebar.collapsed {
  width: 64px;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo {
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
  flex: 1;
}

.logo-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #1890ff;
  border-radius: 50%;
  margin-right: 10px;
}

.collapsed .logo-icon {
  margin-right: 0;
}

.logo-text {
  overflow: hidden;
  white-space: nowrap;
}

.collapse-btn {
  background: transparent;
  border: none;
  font-size: 20px;
  color: #fff;
  padding: 0;
  margin-left: 10px;
}

.el-menu {
  flex: 1;
  border-right: none;
}

.el-menu:not(.el-menu--collapse) {
  width: 220px;
}

.el-menu-item,
.el-submenu >>> .el-submenu__title {
  height: 50px;
  line-height: 50px;
}

.el-menu-item i,
.el-submenu >>> .el-submenu__title i {
  color: inherit;
  margin-right: 8px;
  font-size: 18px;
}

.el-menu-item.is-active {
  background-color: #1890ff !important;
  color: #fff !important;
}

.el-menu-item:hover,
.el-submenu >>> .el-submenu__title:hover {
  background-color: rgba(24, 144, 255, 0.2) !important;
}

.sidebar-footer {
  padding: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
}

.system-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.version {
  text-align: center;
}
</style>