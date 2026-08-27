<!--
  应用侧边栏组件 (AppSidebar)

  职责：渲染左侧导航菜单，包含 5 个功能分区，支持展开/折叠切换。
  - 展开态：220px 宽，显示菜单图标 + 中文标签
  - 折叠态：52px 宽，仅显示图标，选中项蓝色高亮居中
  - 折叠按钮位于顶部右侧，半透明玻璃态

  依赖：
  - Naive UI: NMenu, NIcon（菜单渲染）
  - SmartIcon: 统一图标组件（@iconify/vue 封装）
  - Vue Router: 路由导航

  事件：
  - @collapse: 向父组件通知折叠状态变更（MainLayout 同步 workspace 宽度）
-->
<template>
  <div class="app-sidebar" :class="{ collapsed: collapsed }">
    <!--
      可滚动菜单容器
      折叠时 nav-header（分区标题）隐藏，n-menu 仅显示图标
    -->
    <div class="sidebar-content">
      <!-- ================================================================
          分区一：数据中心 — 市场概览 / 同步概览
      ================================================================ -->
      <div class="nav-section">
        <div class="nav-header">数据中心</div>
        <n-menu :options="dataCenterOptions" :value="dataMenuValue" @update:value="navigateTo" />
      </div>

      <!-- ================================================================
          分区二：策略中心 — 策略管理 / 模板 / 回测 / 因子研究
      ================================================================ -->
      <div class="nav-section">
        <div class="nav-header">策略中心</div>
        <n-menu :options="strategyCenterOptions" :value="strategyMenuValue" @update:value="navigateTo" />
      </div>

      <!-- ================================================================
          分区三：交易与持仓 — 驾驶舱 / 信号 / 组合实盘 / 绩效中心
      ================================================================ -->
      <div class="nav-section">
        <div class="nav-header">交易与持仓</div>
        <n-menu :options="tradingOptions" :value="tradingMenuValue" @update:value="navigateTo" />
      </div>

      <!-- ================================================================
          分区五：风险监控 — 风控规则 / 实时监控 / 事件查看 / 黑名单
      ================================================================ -->
      <div class="nav-section">
        <div class="nav-header">风险监控</div>
        <n-menu :options="riskOptions" :value="riskMenuValue" @update:value="navigateTo" />
      </div>

      <!-- ================================================================
          分区五：系统管理 — 系统监控 / 日志 / 用户 / 设置
      ================================================================ -->
      <div class="nav-section">
        <div class="nav-header">系统管理</div>
        <n-menu :options="systemOptions" :value="systemMenuValue" @update:value="navigateTo" />
      </div>
    </div>

    <!--
      折叠切换按钮
      - 展开态：显示 ChevronLeft（← 折叠），right 定位在侧边栏右边缘
      - 折叠态：显示 ChevronRight（→ 展开），left 定位跟随折叠宽度
      - 半透明玻璃态：backdrop-filter blur + 低不透明度背景
    -->
    <div class="sidebar-toggle" @click="toggleCollapse">
      <smart-icon
        :name="collapsed ? 'ChevronRight' : 'ChevronLeft'"
        :size="11"
        class="toggle-icon"
      />
    </div>
  </div>
</template>

<script>
/**
 * AppSidebar 组件逻辑
 *
 * 核心职责：
 * 1. 管理 7 组菜单配置（icon 使用 h(NIcon) + SmartIcon 组合渲染）
 * 2. 维护 activeMenu（当前选中菜单 key）和 collapsed（折叠状态）
 * 3. 菜单点击 → 更新 activeMenu → vue-router 导航
 * 4. onMounted 时根据当前 route.path 反向激活对应菜单项
 */
import { defineComponent, ref, onMounted, watch, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NMenu, NIcon } from "naive-ui";
import SmartIcon from "../common/SmartIcon.vue";

export default defineComponent({
  name: "AppSidebar",
  components: {
    NMenu,
    NIcon,
    SmartIcon,
  },
  emits: ["collapse"],
  setup(_, { emit }) {
    const route = useRoute();
    const router = useRouter();

    /** 侧边栏折叠状态：false=展开(220px)，true=折叠(52px) */
    const collapsed = ref(false);

    // 每个分区独立的选中状态，避免多 n-menu 共享 v-model 互相覆盖
    const dataMenuValue = ref(null);
    const strategyMenuValue = ref(null);
    const tradingMenuValue = ref(null);
    const riskMenuValue = ref(null);
    const systemMenuValue = ref(null);

    // =====================================================================
    // 菜单配置（5 组）
    // 每个菜单项：label(中文标签) / key(唯一标识) / icon(渲染函数)
    // icon 使用 h(NIcon, null, { default: () => h(SmartIcon, { name }) })
    // NIcon 是 Naive UI 的图标容器，SmartIcon 负责按名称查找 Iconify 图标
    // =====================================================================

    /** 数据中心菜单 — 2 项 */
    const dataCenterOptions = [
      {
        label: "市场概览",
        key: "market",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Grid" }) }),
      },
      {
        label: "数据同步",
        key: "data-sync-overview",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Sync" }) }),
      },
    ];

    /**
     * 策略中心菜单 — 4 项（按工作流排序：因子→策略→回测）
     * 每项指向一个枢纽页面，页面内以卡片形式展示子功能入口
     */
    const strategyCenterOptions = [
      {
        label: "因子研究",
        key: "strategy-factors",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Flask" }) }),
      },
      {
        label: "策略构建",
        key: "strategy-build",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Cube" }) }),
      },
      {
        label: "模型训练",
        key: "strategy-train",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Cog" }) }),
      },
      {
        label: "回测验证",
        key: "strategy-backtest",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "TrendingUpOutline" }),
          }),
      },
    ];

    /** 交易与持仓菜单 — 4 项（驾驶舱 / 信号 / 组合实盘 / 绩效中心）
     *  绩效中心为驾驶舱大页唯一入口（回测排行/账户绩效/健康为页内钻取） */
    const tradingOptions = [
      {
        label: "交易驾驶舱",
        key: "trading-workspace",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Grid" }) }),
      },
      {
        label: "信号管理",
        key: "signals",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "NotificationsOutline" }) }),
      },
      {
        label: "组合实盘",
        key: "trade-composite",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "WalletOutline" }),
          }),
      },
      {
        label: "绩效中心",
        key: "performance-dashboard",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Trophy" }) }),
      },
    ];

    /** 风险监控菜单 — 4 项（健康与报警已并入绩效中心钻取） */
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

    /** 系统管理菜单 — 4 项 */
    const systemOptions = [
      {
        label: "系统仪表盘",
        key: "system-dashboard",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "Desktop" }) }),
      },
      {
        label: "用户管理",
        key: "users",
        icon: () =>
          h(NIcon, null, { default: () => h(SmartIcon, { name: "People" }) }),
      },
      {
        label: "系统日志",
        key: "logs",
        icon: () =>
          h(NIcon, null, {
            default: () => h(SmartIcon, { name: "DocumentText" }),
          }),
      },
    ];

    // =====================================================================
    // 菜单 key → 路由路径映射（28 项，watch / onMounted 共用）
    // =====================================================================
    const routeMap = {
      market: "/market/overview",
      "data-sync-overview": "/data/sync",
      strategies: "/strategies",
      "strategy-templates": "/strategies/templates",
      "strategy-risk": "/strategies/risk",
      "strategy-factors": "/strategy/factors",
      "strategy-build": "/strategy/build",
      "strategy-train": "/strategies/train",
      "strategy-backtest": "/strategy/backtest",
      "trading-workspace": "/trade/workspace",
      "trade-composite": "/trade/composite",
      signals: "/signals",
      "risk-rules": "/risk/rules",
      "risk-monitor": "/risk/monitor",
      "risk-events": "/risk/events",
      blacklist: "/risk/blacklist",
      // 绩效中心唯一菜单项；/performance/* 前缀匹配 → 钻取页访问时「绩效中心」保持高亮
      "performance-dashboard": "/performance",
      "system-dashboard": "/system/dashboard",
      users: "/system/users",
      logs: "/system/logs",
    };

    /** 根据当前 path 反向查找菜单 key */
    const findMenuKey = (path) => {
      let bestKey = null;
      let bestLen = 0;
      for (const [key, routePath] of Object.entries(routeMap)) {
        if (path.startsWith(routePath) && routePath.length > bestLen) {
          bestKey = key;
          bestLen = routePath.length;
        }
      }
      return bestKey;
    };

    /** 菜单 key → 所属分区映射 */
    const keyToSection = (key) => {
      if (dataCenterOptions.some((o) => o.key === key)) return "data";
      if (strategyCenterOptions.some((o) => o.key === key)) return "strategy";
      if (tradingOptions.some((o) => o.key === key)) return "trading";
      if (riskOptions.some((o) => o.key === key)) return "risk";
      if (systemOptions.some((o) => o.key === key)) return "system";
      return null;
    };

    /** 根据 key 设置对应分区的 local value，其他分区清空 */
    const setActiveKey = (key) => {
      dataMenuValue.value = null;
      strategyMenuValue.value = null;
      tradingMenuValue.value = null;
      riskMenuValue.value = null;
      systemMenuValue.value = null;
      if (!key) return;
      const section = keyToSection(key);
      if (section === "data") dataMenuValue.value = key;
      else if (section === "strategy") strategyMenuValue.value = key;
      else if (section === "trading") tradingMenuValue.value = key;
      else if (section === "risk") riskMenuValue.value = key;
      else if (section === "system") systemMenuValue.value = key;
    };

    /** 菜单点击 → 路由导航 */
    const navigateTo = (key) => {
      const target = routeMap[key];
      if (!target) return;
      if (route.path === target || route.path.startsWith(target + "/")) return;
      router.push(target).catch((err) => {
        if (err.name !== "NavigationDuplicated") {
          console.warn("[AppSidebar] 路由跳转失败:", err);
        }
      });
    };

    // 浏览器前进/后退 → 同步各分区菜单高亮
    watch(
      () => route.path,
      (path) => {
        const key = findMenuKey(path);
        setActiveKey(key);
      },
    );

    /**
     * 切换折叠状态
     */
    const toggleCollapse = () => {
      collapsed.value = !collapsed.value;
      emit("collapse", collapsed.value);
    };

    // =====================================================================
    // 生命周期：页面初始化时同步菜单高亮
    // =====================================================================
    onMounted(() => {
      setActiveKey(findMenuKey(route.path));
    });

    return {
      collapsed,
      dataCenterOptions,
      strategyCenterOptions,
      tradingOptions,
      riskOptions,
      systemOptions,
      dataMenuValue,
      strategyMenuValue,
      tradingMenuValue,
      riskMenuValue,
      systemMenuValue,
      navigateTo,
      toggleCollapse,
    };
  },
});
</script>

<style lang="scss" scoped>
/*
 * ============================================================================
 * AppSidebar 样式分层
 *
 * 第一层 — 侧边栏容器（.app-sidebar）
 * 第二层 — 滚动内容区（.sidebar-content）+ 导航分区（.nav-section / .nav-header）
 * 第三层 — 折叠切换按钮（.sidebar-toggle）
 * 第四层 — Naive UI 菜单覆盖（:deep(.n-menu) — 展开态 + 折叠态）
 * ============================================================================
 */

/* ==========================================================================
   第一层：侧边栏容器
   展开 240px，折叠 64px，无过渡瞬间切换（避免菜单图标拉伸）
   背景使用 Naive UI CSS 变量 var(--n-card-color)，跟随主题
   ========================================================================== */
.app-sidebar {
  width: var(--sidebar-expanded-width, 240px);
  height: 100%;
  background-color: var(--n-card-color);
  color: var(--n-text-color-1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  box-shadow: var(--n-box-shadow-1);
  border-right: 1px solid var(--n-border-color);

  /* 平滑折叠/展开动画：宽度过渡 + GPU 合成层 */
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: width;

  /* 隐藏滚动条但保持滚动功能（Firefox + IE + WebKit） */
  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }

  /* 折叠态：宽度切换为 64px */
  &.collapsed {
    width: var(--sidebar-collapsed-width, 64px);
    overflow: hidden;
  }
}

/* ==========================================================================
   第二层：滚动内容区 + 导航分区
   ========================================================================== */

/* 菜单滚动容器 — 占据除按钮外的全部高度，底部留 40px 给折叠按钮让位 */
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

/* 每个导航分区之间的间距 */
.nav-section {
  margin-bottom: 8px;
  flex-shrink: 0;
}

/* 分区标题（如"数据中心""策略中心"）— 展开态可见，折叠态渐变消失 */
.nav-header {
  padding: 10px 20px 6px;
  font-size: 12px;
  color: var(--n-text-color-3);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  border-bottom: 1px solid var(--n-divider-color);
  margin: 0 8px 4px;
  white-space: nowrap;
  opacity: 1;
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ==========================================================================
   第二层（续）：折叠状态下的容器变化
   ========================================================================== */
.app-sidebar.collapsed {
  width: var(--sidebar-collapsed-width, 64px);
  overflow: hidden;

  /* 折叠时隐藏分区标题并移除其占位空间 */
  .nav-header {
    opacity: 0;
    pointer-events: none;
    height: 0;
    padding-top: 0;
    padding-bottom: 0;
    margin-top: 0;
    margin-bottom: 0;
    border-bottom: none;
    overflow: hidden;
  }

  /* 折叠时减小分区间距 */
  .nav-section {
    margin-bottom: 4px;
  }

  .sidebar-content {
    overflow-y: auto;
    overflow-x: hidden;
  }
}

/* ==========================================================================
   第三层：折叠切换按钮
   14×14px 圆形，半透明玻璃态，位于侧边栏顶部右侧
   折叠后随侧边栏宽度向左收缩
   ========================================================================== */
.sidebar-toggle {
  position: absolute;
  top: 10px;
  right: 5px;
  width: 14px;
  height: 14px;
  /* 背景：主色系半透明 + 毛玻璃模糊 */
  background: rgba(68, 138, 255, 0.45);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.8);
  box-shadow: var(--n-box-shadow-1);
  transition: all 0.3s var(--n-bezier);
  z-index: 1003;
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);

  /* hover 时背景加深，不缩放（14px 太小，scale 会失真） */
  &:hover {
    background: rgba(68, 138, 255, 0.65);
    box-shadow: var(--n-box-shadow-2);
  }
}

/* 折叠态按钮位置：保持在侧边栏右边缘内 */
.app-sidebar.collapsed .sidebar-toggle {
  right: 1px;
  left: auto;
}

/* ==========================================================================
   第四层：Naive UI 菜单样式覆盖 — 展开态
   菜单项左右 8px margin，圆角 6px，选中项蓝色背景 + 白色文字/图标
   ========================================================================== */
:deep(.n-menu) {
  .n-menu-item {
    margin: 2px 8px;
    border-radius: 6px;

    /* 选中项：深海蓝背景，白色前景（文字 + 图标） */
    &.n-menu-item--selected {
      background-color: var(--n-primary-color);
      color: white;

      .n-menu-item-content__icon {
        color: white;
      }
    }
  }

  .n-menu-item-content {
    padding: 8px 12px;

    /* 图标容器：inline-flex 确保图标自身也居中 */
    &__icon {
      margin-right: 8px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    &-header {
      white-space: nowrap;
      overflow: hidden;
      max-width: 200px;
      opacity: 1;
      transition:
        opacity 0.15s cubic-bezier(0.4, 0, 0.2, 1),
        max-width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
  }
}

/* ==========================================================================
   第四层（续）：Naive UI 菜单样式覆盖 — 折叠态
   仅显示图标，隐藏文字标签和展开箭头，选中色块精确居中
   Naive UI 2.43.2 DOM: icon → __icon / label → -header / arrow → __arrow
   ========================================================================== */
.app-sidebar.collapsed :deep(.n-menu) {
  /* 清除 Naive UI 菜单容器的默认水平 padding */
  padding: 0 !important;

  .n-menu-item {
    margin: 4px 0;
    padding: 0 !important;
    /* 隐藏 Naive UI 选中项左侧的 3px 指示条（该指示条会破坏居中） */
    &::before {
      display: none !important;
    }
  }

  .n-menu-item-content {
    /*
     * Naive UI 默认 display: grid (grid-template-columns: auto 1fr auto)
     * icon 在左侧 auto 列，justify-content 对 grid 无效。
     * 折叠态覆盖为 flex，图标自然居中。
     */
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 10px 0 !important;

    .n-menu-item-content-header {
      opacity: 0;
      max-width: 0;
      overflow: hidden;
      pointer-events: none;
      transition:
        opacity 0.15s cubic-bezier(0.4, 0, 0.2, 1),
        max-width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .n-menu-item-content__arrow {
      opacity: 0;
      max-width: 0;
      overflow: hidden;
      pointer-events: none;
      transition:
        opacity 0.15s cubic-bezier(0.4, 0, 0.2, 1),
        max-width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    &__icon,
    .n-menu-item-content__icon {
      margin: 0 !important;
      font-size: var(--n-icon-size, 18px) !important;
    }
  }
}
</style>
