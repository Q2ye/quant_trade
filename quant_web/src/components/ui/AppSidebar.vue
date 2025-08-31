<template>
  <div class="app-sidebar" :class="{ collapsed: collapsed }">
    <div class="nav-section">
      <div class="nav-header">核心功能</div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'dashboard' }"
          @click="navigate('/dashboard')"
      >
        <i class="fas fa-th-large"></i>
        <span class="nav-text">交易驾驶舱</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'strategy' }"
          @click="navigate('/strategy')"
      >
        <i class="fas fa-project-diagram"></i>
        <span class="nav-text">策略工作室</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'kline' }"
          @click="navigate('/kline')"
      >
        <i class="fas fa-chart-candlestick"></i>
        <span class="nav-text">智能K线</span>
      </div>
    </div>

    <div class="nav-section">
      <div class="nav-header">数据分析</div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'report' }"
          @click="navigate('/report')"
      >
        <i class="fas fa-chart-line"></i>
        <span class="nav-text">回测报告</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'basket' }"
          @click="navigate('/basket')"
      >
        <i class="fas fa-basket-shopping"></i>
        <span class="nav-text">股票篮子</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'performance' }"
          @click="navigate('/performance')"
      >
        <i class="fas fa-analytics"></i>
        <span class="nav-text">绩效分析</span>
      </div>
    </div>

    <div class="nav-section">
      <div class="nav-header">系统管理</div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'settings' }"
          @click="navigate('/settings')"
      >
        <i class="fas fa-cog"></i>
        <span class="nav-text">系统设置</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: 'risk' === activeMenu }"
          @click="navigate('/risk')"
      >
        <i class="fas fa-sliders-h"></i>
        <span class="nav-text">风险控制</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'monitor' }"
          @click="navigate('/monitor')"
      >
        <i class="fas fa-terminal"></i>
        <span class="nav-text">系统监控</span>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="system-info">
        <span>CPU: 42%</span>
        <span>内存: 65%</span>
      </div>
      <div class="version">v1.0.0</div>
    </div>
  </div>
</template>

<script>
import {ref, watch} from "vue";
import {useRoute, useRouter} from "vue-router";

export default {
  name: "AppSidebar",
  emits: ["collapse"],
  setup(_, {emit}) {
    const route = useRoute();
    const router = useRouter();
    const activeMenu = ref("dashboard");
    const collapsed = ref(false);

    watch(
        () => route.path,
        () => {
          setActiveMenu();
        },
    );

    const setActiveMenu = () => {
      const path = route.path;
      if (path.startsWith("/dashboard")) activeMenu.value = "dashboard";
      else if (path.startsWith("/strategy")) activeMenu.value = "strategy";
      else if (path.startsWith("/kline")) activeMenu.value = "kline";
      else if (path.startsWith("/report")) activeMenu.value = "report";
      else if (path.startsWith("/basket")) activeMenu.value = "basket";
      else if (path.startsWith("/performance"))
        activeMenu.value = "performance";
      else if (path.startsWith("/settings")) activeMenu.value = "settings";
      else if (path.startsWith("/risk")) activeMenu.value = "risk";
      else if (path.startsWith("/monitor")) activeMenu.value = "monitor";
      else activeMenu.value = "";
    };

    const toggleCollapse = () => {
      collapsed.value = !collapsed.value;
      emit("collapse", collapsed.value);
    };

    const navigate = (path) => {
      router.push(path);
    };

    // 立即设置一次活动菜单
    setActiveMenu();

    return {
      activeMenu,
      collapsed,
      setActiveMenu,
      toggleCollapse,
      navigate,
    };
  },
};
</script>

<style lang="scss" scoped>
.app-sidebar {
  width: var(--sidebar-width);
  height: 100vh;
  background-color: var(--secondary-bg);
  color: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  overflow: hidden;

  &.collapsed {
    width: var(--sidebar-collapsed-width);
  }
}

.nav-section {
  margin-bottom: 20px;
}

.nav-header {
  padding: 15px 20px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  color: var(--text-primary);
  text-decoration: none;
  transition: background-color 0.2s;
  cursor: pointer;

  &:hover {
    background-color: rgba(79, 156, 249, 0.1);
  }

  &.active {
    background-color: rgba(79, 156, 249, 0.2);
    border-left: 3px solid var(--accent-color);
  }

  i {
    margin-right: 12px;
    width: 20px;
    text-align: center;
    color: var(--accent-color);
  }
}

.app-sidebar.collapsed {
  .nav-text {
    display: none;
  }

  .nav-header {
    display: none;
  }
}

.sidebar-footer {
  margin-top: auto;
  padding: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);

  .system-info {
    display: flex;
    justify-content: space-between;
    margin-bottom: 5px;
  }

  .version {
    text-align: center;
  }
}
</style>
