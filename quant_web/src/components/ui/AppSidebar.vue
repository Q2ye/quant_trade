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
          :class="{ active: activeMenu === 'strategies' }"
          @click="navigate('/strategies')"
      >
        <i class="fas fa-project-diagram"></i>
        <span class="nav-text">策略管理</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'backtest' }"
          @click="navigate('/strategies/backtest')"
      >
        <i class="fas fa-chart-line"></i>
        <span class="nav-text">回测工作室</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'trading' }"
          @click="navigate('/trading')"
      >
        <i class="fas fa-terminal"></i>
        <span class="nav-text">交易执行</span>
      </div>
    </div>

    <div class="nav-section">
      <div class="nav-header">数据分析</div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'baskets' }"
          @click="navigate('/baskets')"
      >
        <i class="fas fa-basket-shopping"></i>
        <span class="nav-text">股票篮子</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'performance' }"
          @click="navigate('/performance/account')"
      >
        <i class="fas fa-analytics"></i>
        <span class="nav-text">绩效分析</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'market' }"
          @click="navigate('/market/stocks')"
      >
        <i class="fas fa-chart-candlestick"></i>
        <span class="nav-text">市场数据</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'research' }"
          @click="navigate('/strategies/factor-research')"
      >
        <i class="fas fa-flask"></i>
        <span class="nav-text">因子研究</span>
      </div>
    </div>

    <div class="nav-section">
      <div class="nav-header">系统管理</div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'data-sync' }"
          @click="navigate('/data-sync')"
      >
        <i class="fas fa-database"></i>
        <span class="nav-text">数据同步</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'risk' }"
          @click="navigate('/risk/rules')"
      >
        <i class="fas fa-shield-alt"></i>
        <span class="nav-text">风险管理</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'signals' }"
          @click="navigate('/signals')"
      >
        <i class="fas fa-bell"></i>
        <span class="nav-text">信号监控</span>
      </div>
      <div
          class="nav-item"
          :class="{ active: activeMenu === 'system' }"
          @click="navigate('/system/monitor')"
      >
        <i class="fas fa-cog"></i>
        <span class="nav-text">系统监控</span>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="system-info">
        <span>CPU: {{ systemInfo.cpu }}%</span>
        <span>内存: {{ systemInfo.memory }}%</span>
      </div>
      <div class="version">v1.0.0</div>
    </div>
  </div>
</template>

<script>
import { ref, watch, onMounted, onUnmounted, reactive } from "vue";
import { useRoute, useRouter } from "vue-router";

export default {
  name: "AppSidebar",
  emits: ["collapse"],
  setup(_, { emit }) {
    const route = useRoute();
    const router = useRouter();
    const activeMenu = ref("dashboard");
    const collapsed = ref(false);
    const systemInfo = reactive({
      cpu: 42,
      memory: 65
    });

    let isComponentMounted = true;
    let routeWatchStop = null;

    // 安全的设置活动菜单函数
    const setActiveMenu = () => {
      if (!isComponentMounted) return;

      try {
        const path = route?.path || "";
        const meta = route?.meta || {};

        // 优先使用路由meta中定义的menu字段
        if (meta.menu) {
          activeMenu.value = meta.menu;
          return;
        }

        // 简化的路径匹配逻辑
        if (path.startsWith("/dashboard")) activeMenu.value = "dashboard";
        else if (path.includes("/backtest")) activeMenu.value = "backtest";
        else if (path.includes("/factor-research")) activeMenu.value = "research";
        else if (path.startsWith("/strategies")) activeMenu.value = "strategies";
        else if (path.startsWith("/trading")) activeMenu.value = "trading";
        else if (path.startsWith("/baskets")) activeMenu.value = "baskets";
        else if (path.startsWith("/performance")) activeMenu.value = "performance";
        else if (path.startsWith("/market")) activeMenu.value = "market";
        else if (path.startsWith("/data-sync")) activeMenu.value = "data-sync";
        else if (path.startsWith("/risk")) activeMenu.value = "risk";
        else if (path.startsWith("/signals")) activeMenu.value = "signals";
        else if (path.startsWith("/system")) activeMenu.value = "system";
        else activeMenu.value = "";
      } catch (error) {
        console.warn('设置活动菜单时出错:', error);
        activeMenu.value = "";
      }
    };

    // 安全的导航函数
    const navigate = (path) => {
      if (!isComponentMounted || !path) return;

      // 检查路径是否有效
      if (typeof path !== 'string') {
        console.error('导航路径无效:', path);
        return;
      }

      // 检查是否已经是当前路由
      if (route.path === path) {
        return;
      }

      // 使用 nextTick 确保在下一个事件循环中导航，避免与当前渲染周期冲突
      setTimeout(() => {
        if (!isComponentMounted) return;

        router.push(path).catch(err => {
          // 忽略导航重复的错误
          if (err?.name === 'NavigationDuplicated') {
            console.log('重复导航，已忽略:', path);
          } else if (err?.message?.includes('Avoided redundant navigation')) {
            // 这是重复导航的另一种形式
            console.log('重复导航，已忽略:', path);
          } else {
            console.error('导航错误:', err);
          }
        });
      }, 0);
    };

    const toggleCollapse = () => {
      if (!isComponentMounted) return;
      collapsed.value = !collapsed.value;
      emit("collapse", collapsed.value);
    };

    // 模拟系统信息更新
    const startSystemInfoUpdate = () => {
      if (!isComponentMounted) return;

      const updateInterval = setInterval(() => {
        if (!isComponentMounted) {
          clearInterval(updateInterval);
          return;
        }

        // 模拟系统信息变化
        systemInfo.cpu = Math.max(10, Math.min(90, systemInfo.cpu + (Math.random() - 0.5) * 10));
        systemInfo.memory = Math.max(20, Math.min(80, systemInfo.memory + (Math.random() - 0.5) * 5));
      }, 5000);

      return updateInterval;
    };

    onMounted(() => {
      isComponentMounted = true;
      setActiveMenu();

      // 启动系统信息更新
      const updateInterval = startSystemInfoUpdate();

      // 监听路由变化 - 使用更安全的配置
      routeWatchStop = watch(
        () => route.path,
        (newPath, oldPath) => {
          if (!isComponentMounted) return;

          // 添加防抖，避免频繁更新
          setTimeout(() => {
            if (isComponentMounted) {
              setActiveMenu();
            }
          }, 10);
        },
        {
          immediate: false, // 不在初始化时立即执行
          flush: 'post' // 在DOM更新后执行，避免与渲染冲突
        }
      );

      // 清理函数
      return () => {
        if (updateInterval) {
          clearInterval(updateInterval);
        }
      };
    });

    onUnmounted(() => {
      isComponentMounted = false;

      // 停止路由监听
      if (routeWatchStop) {
        routeWatchStop();
        routeWatchStop = null;
      }
    });

    return {
      activeMenu,
      collapsed,
      systemInfo,
      setActiveMenu,
      toggleCollapse,
      navigate,
    };
  },
};
</script>

<style lang="scss" scoped>
.app-sidebar {
  width: var(--sidebar-width, 240px);
  height: 100vh;
  background-color: var(--secondary-bg, #1f2937);
  color: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  position: relative;

  &.collapsed {
    width: var(--sidebar-collapsed-width, 64px);
  }
}

.nav-section {
  margin-bottom: 20px;
  flex-shrink: 0;
}

.nav-header {
  padding: 15px 20px 10px;
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  color: var(--text-primary, #f3f4f6);
  text-decoration: none;
  transition: all 0.2s ease;
  cursor: pointer;
  border-left: 3px solid transparent;
  user-select: none;

  &:hover {
    background-color: rgba(79, 156, 249, 0.1);
    color: #fff;
  }

  &.active {
    background-color: rgba(79, 156, 249, 0.2);
    border-left-color: var(--accent-color, #4f9cf9);
    color: #fff;
  }

  i {
    margin-right: 12px;
    width: 20px;
    text-align: center;
    color: var(--accent-color, #4f9cf9);
    flex-shrink: 0;
  }
}

.app-sidebar.collapsed {
  .nav-text {
    display: none;
  }

  .nav-header {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: 12px;

    i {
      margin-right: 0;
    }
  }
}

.sidebar-footer {
  margin-top: auto;
  padding: 15px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
  flex-shrink: 0;

  .system-info {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }

  .version {
    text-align: center;
    font-weight: 500;
  }
}

/* 添加响应式设计 */
@media (max-height: 600px) {
  .app-sidebar {
    overflow-y: auto;
  }

  .nav-section {
    margin-bottom: 15px;
  }

  .nav-item {
    padding: 10px 20px;
  }
}

/* 确保 CSS 变量有回退值 */
:root {
  --sidebar-width: 240px;
  --sidebar-collapsed-width: 64px;
  --secondary-bg: #1f2937;
  --text-primary: #f3f4f6;
  --text-secondary: #9ca3af;
  --accent-color: #4f9cf9;
}
</style>