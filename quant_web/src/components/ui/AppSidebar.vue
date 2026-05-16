<!-- 应用侧边栏组件 - 迁移到 Naive UI 和统一图标方案 -->
<template>
  <div class="app-sidebar" :class="{ collapsed: collapsed }">
    <!-- 将导航内容包裹在可滚动容器中 -->
    <div class="sidebar-content">
      <!-- 数据中心 -->
      <div class="nav-section">
        <div class="nav-header">数据中心</div>
        <n-menu
          :options="dataCenterOptions"
          :value="activeMenu"
          @update:value="handleMenuSelect"
        />
      </div>

      <!-- 策略中心 -->
      <div class="nav-section">
        <div class="nav-header">策略中心</div>
        <n-menu
          :options="strategyCenterOptions"
          :value="activeMenu"
          @update:value="handleMenuSelect"
        />
      </div>

      <!-- 组合管理 -->
      <div class="nav-section">
        <div class="nav-header">组合管理</div>
        <n-menu
          :options="portfolioOptions"
          :value="activeMenu"
          @update:value="handleMenuSelect"
        />
      </div>

      <!-- 交易执行 -->
      <div class="nav-section">
        <div class="nav-header">交易执行</div>
        <n-menu
          :options="tradingOptions"
          :value="activeMenu"
          @update:value="handleMenuSelect"
        />
      </div>

      <!-- 风险监控 -->
      <div class="nav-section">
        <div class="nav-header">风险监控</div>
        <n-menu
          :options="riskOptions"
          :value="activeMenu"
          @update:value="handleMenuSelect"
        />
      </div>

      <!-- 绩效分析 -->
      <div class="nav-section">
        <div class="nav-header">绩效分析</div>
        <n-menu
          :options="performanceOptions"
          :value="activeMenu"
          @update:value="handleMenuSelect"
        />
      </div>

      <!-- 系统管理 -->
      <div class="nav-section">
        <div class="nav-header">系统管理</div>
        <n-menu
          :options="systemOptions"
          :value="activeMenu"
          @update:value="handleMenuSelect"
        />
      </div>
    </div>

    <!-- 缩放按钮 -->
    <div class="sidebar-toggle" @click="toggleCollapse">
      <!-- 使用 SmartIcon 组件 -->
      <smart-icon
        :name="collapsed ? 'ChevronRight' : 'ChevronLeft'"
        size="16"
        class="toggle-icon"
      />
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, onMounted, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NMenu, NIcon } from "naive-ui";
// 导入 SmartIcon 组件
import SmartIcon from "../common/SmartIcon.vue";

export default defineComponent({
  name: "AppSidebar",
  components: {
    NMenu,
    NIcon,
    SmartIcon, // 注册 SmartIcon 组件
  },
  emits: ["collapse"],
  setup(_, { emit }) {
    const route = useRoute();
    const router = useRouter();
    const activeMenu = ref("market");
    const collapsed = ref(false);

    // 菜单配置 - 使用 SmartIcon 组件
    const dataCenterOptions = [
      {
        label: "市场概览",
        key: "market",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Grid" }) }),
      },
      {
        label: "同步概览",
        key: "data-sync-overview",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Sync" }) }),
      },
    ];

    const strategyCenterOptions = [
      {
        label: "策略管理",
        key: "strategies",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Cube" }) }),
      },
      {
        label: "策略模板",
        key: "strategy-templates",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Copy" }) }),
      },
      {
        label: "回测工作室",
        key: "backtest",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "TrendingUpOutline" }),
          }),
      },
      {
        label: "因子研究",
        key: "research",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Flask" }) }),
      },
      {
        label: "因子库管理",
        key: "factor-library",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Options" }) }),
      },
      {
        label: "回溯周期",
        key: "backtest-period",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Calendar" }) }),
      },
    ];

    const portfolioOptions = [
      {
        label: "篮子管理",
        key: "baskets",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Basket" }) }),
      },
      {
        label: "持仓管理",
        key: "positions",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "PieChart" }) }),
      },
      {
        label: "账户管理",
        key: "account",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "WalletOutline" }),
          }),
      },
      {
        label: "组合分析",
        key: "portfolio-analysis",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "BarChart" }) }),
      },
    ];

    const tradingOptions = [
      {
        label: "交易驾驶舱",
        key: "trading",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Terminal" }) }),
      },
      {
        label: "订单管理",
        key: "orders",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "List" }) }),
      },
      {
        label: "信号监控",
        key: "signals",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Bell" }) }),
      },
      {
        label: "执行分析",
        key: "execution-analysis",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "Speedometer" }),
          }),
      },
    ];

    const riskOptions = [
      {
        label: "风控规则",
        key: "risk-rules",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "ShieldCheckmark" }),
          }),
      },
      {
        label: "实时监控",
        key: "risk-monitor",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Eye" }) }),
      },
      {
        label: "事件查看",
        key: "risk-events",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "AlertCircle" }),
          }),
      },
      {
        label: "黑名单",
        key: "blacklist",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Ban" }) }),
      },
    ];

    const performanceOptions = [
      {
        label: "策略绩效",
        key: "strategy-performance",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Trophy" }) }),
      },
      {
        label: "账户绩效",
        key: "account-performance",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "AnalyticsOutline" }),
          }),
      },
      {
        label: "绩效对比",
        key: "performance-comparison",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Scale" }) }),
      },
      {
        label: "归因分析",
        key: "attribution",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Puzzle" }) }),
      },
    ];

    const systemOptions = [
      {
        label: "系统监控",
        key: "system-monitor",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Desktop" }) }),
      },
      {
        label: "日志查看",
        key: "logs",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "DocumentText" }),
          }),
      },
      {
        label: "用户管理",
        key: "users",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "People" }) }),
      },
      {
        label: "系统设置",
        key: "settings",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Settings" }) }),
      },
    ];

    const handleMenuSelect = (key) => {
      activeMenu.value = key;
      const routeMap = {
        market: "/market/overview",
        "data-sync-overview": "/data/sync/overview",
        strategies: "/strategies",
        "strategy-templates": "/strategies/templates",
        backtest: "/backtest/studio",
        research: "/research/factor-research",
        "factor-library": "/research/factor-library",
        "backtest-period": "/research/backtest-period",
        baskets: "/baskets",
        positions: "/trade/positions",
        account: "/account",
        "portfolio-analysis": "/portfolio/analysis",
        trading: "/trade",
        orders: "/trade/orders",
        signals: "/signals",
        "execution-analysis": "/trade/execution",
        "risk-rules": "/risk/rules",
        "risk-monitor": "/risk/monitor",
        "risk-events": "/risk/events",
        blacklist: "/risk/blacklist",
        "strategy-performance": "/performance/strategy",
        "account-performance": "/performance/account",
        "performance-comparison": "/performance/comparison",
        attribution: "/performance/attribution",
        "system-monitor": "/system/monitor",
        logs: "/system/logs",
        users: "/system/users",
        settings: "/system/settings",
      };

      if (routeMap[key]) {
        router.push(routeMap[key]);
      }
    };

    const toggleCollapse = () => {
      collapsed.value = !collapsed.value;
      emit("collapse", collapsed.value);
    };

    onMounted(() => {
      // 根据当前路由设置活动菜单
      const path = route.path;
      for (const [key, value] of Object.entries({
        market: "/market/overview",
        "data-sync-overview": "/data/sync/overview",
        strategies: "/strategies",
        "strategy-templates": "/strategies/templates",
        backtest: "/backtest/studio",
        research: "/research/factor-research",
        "factor-library": "/research/factor-library",
        "backtest-period": "/research/backtest-period",
        baskets: "/baskets",
        positions: "/trade/positions",
        account: "/account",
        "portfolio-analysis": "/portfolio/analysis",
        trading: "/trade",
        orders: "/trade/orders",
        signals: "/signals",
        "execution-analysis": "/trade/execution",
        "risk-rules": "/risk/rules",
        "risk-monitor": "/risk/monitor",
        "risk-events": "/risk/events",
        blacklist: "/risk/blacklist",
        "strategy-performance": "/performance/strategy",
        "account-performance": "/performance/account",
        "performance-comparison": "/performance/comparison",
        attribution: "/performance/attribution",
        "system-monitor": "/system/monitor",
        logs: "/system/logs",
        users: "/system/users",
        settings: "/system/settings",
      })) {
        if (path.startsWith(value)) {
          activeMenu.value = key;
          break;
        }
      }
    });

    return {
      activeMenu,
      collapsed,
      dataCenterOptions,
      strategyCenterOptions,
      portfolioOptions,
      tradingOptions,
      riskOptions,
      performanceOptions,
      systemOptions,
      handleMenuSelect,
      toggleCollapse,
    };
  },
});
</script>

<style lang="scss" scoped>
.app-sidebar {
  width: 240px;
  height: 100%;
  background-color: var(--n-card-color);
  color: var(--n-text-color-1);
  display: flex;
  flex-direction: column;
  transition: width 0.3s var(--n-bezier);
  overflow: hidden;
  position: relative;
  box-shadow: var(--n-box-shadow-1);
  border-right: 1px solid var(--n-border-color);

  /* 隐藏滚动条但保持滚动功能 */
  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }

  &.collapsed {
    width: 64px;
    overflow: visible;
  }
}

/* 可滚动内容区域 */
.sidebar-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: 40px;
  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }
}

.nav-section {
  margin-bottom: 16px;
  flex-shrink: 0;
}

.nav-header {
  padding: 16px 20px 8px;
  font-size: 12px;
  color: var(--n-text-color-3);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  border-bottom: 1px solid var(--n-divider-color);
  margin: 0 8px 8px;
}

/* 折叠状态样式 */
.app-sidebar.collapsed {
  width: 64px;
  overflow: visible;

  .nav-header {
    display: none;
  }

  .nav-section {
    margin-bottom: 8px;
  }

  .sidebar-content {
    overflow-y: auto;
    overflow-x: hidden;
  }
}

/* 缩放按钮 */
.sidebar-toggle {
  position: absolute;
  bottom: 16px;
  right: 12px;
  width: 24px;
  height: 24px;
  background: var(--n-primary-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  box-shadow: var(--n-box-shadow-1);
  transition: all 0.3s var(--n-bezier);
  z-index: 1003;
  border: 2px solid var(--n-card-color);

  &:hover {
    transform: scale(1.1);
    box-shadow: var(--n-box-shadow-2);
  }
}

/* 折叠状态下调整按钮位置 */
.app-sidebar.collapsed .sidebar-toggle {
  left: calc(64px - 12px);
}

/* 自定义菜单样式覆盖 */
:deep(.n-menu) {
  .n-menu-item {
    margin: 2px 8px;
    border-radius: 6px;

    &.n-menu-item--selected {
      background-color: var(--n-primary-color);
      color: white;

      .n-menu-item-content__icon {
        color: white;
      }
    }

    .n-menu-item-content {
      padding: 8px 12px;

      &__icon {
        margin-right: 8px;
      }
    }
  }
}

/* 折叠状态下的菜单样式 */
.app-sidebar.collapsed :deep(.n-menu) {
  .n-menu-item-content {
    justify-content: center;
    padding: 8px;

    &__icon {
      margin-right: 0;
    }

    &__text {
      display: none;
    }
  }
}
</style>
