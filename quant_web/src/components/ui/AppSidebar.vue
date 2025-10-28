<template>
  <div class="app-sidebar" :class="{ collapsed: collapsed }">
    <!-- 将导航内容包裹在可滚动容器中 -->
    <div class="sidebar-content">
      <!-- 数据中心 -->
      <div class="nav-section">
        <div class="nav-header">数据中心</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'market' }"
            @click="navigate('/market/overview')"
            @mouseenter="showTooltip($event, '市场概览')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="material-symbols:dashboard" class="nav-icon"/>
          <span class="nav-text">市场概览</span>
        </div>

        <div
            class="nav-item"
            :class="{ active: activeMenu === 'data-sync-overview' }"
            @click="navigate('/data-sync-overview')"
            @mouseenter="showTooltip($event, '同步概览')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:sync" class="nav-icon"/>
          <span class="nav-text">数据同步概览</span>
        </div>
      </div>

      <!-- 策略中心 -->
      <div class="nav-section">
        <div class="nav-header">策略中心</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'strategies' }"
            @click="navigate('/strategies')"
            @mouseenter="showTooltip($event, '策略管理')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="material-symbols:device-hub" class="nav-icon"/>
          <span class="nav-text">策略管理</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'strategy-templates' }"
            @click="navigate('/strategies/templates')"
            @mouseenter="showTooltip($event, '策略模板')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:content-copy" class="nav-icon"/>
          <span class="nav-text">策略模板</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'backtest' }"
            @click="navigate('/strategies/backtest')"
            @mouseenter="showTooltip($event, '回测工作室')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:chart-line" class="nav-icon"/>
          <span class="nav-text">回测工作室</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'research' }"
            @click="navigate('/strategies/factor-research')"
            @mouseenter="showTooltip($event, '因子研究')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="material-symbols:science" class="nav-icon"/>
          <span class="nav-text">因子研究</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'factor-library' }"
            @click="navigate('/strategies/factor-library')"
            @mouseenter="showTooltip($event, '因子库管理')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:tune" class="nav-icon"/>
          <span class="nav-text">因子库管理</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'backtest-period' }"
            @click="navigate('/strategies/backtest-period')"
            @mouseenter="showTooltip($event, '回溯周期')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:calendar-range" class="nav-icon"/>
          <span class="nav-text">回溯周期</span>
        </div>
      </div>

      <!-- 组合管理 -->
      <div class="nav-section">
        <div class="nav-header">组合管理</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'baskets' }"
            @click="navigate('/baskets')"
            @mouseenter="showTooltip($event, '篮子管理')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:basket" class="nav-icon"/>
          <span class="nav-text">篮子管理</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'positions' }"
            @click="navigate('/trading/positions')"
            @mouseenter="showTooltip($event, '持仓管理')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:chart-pie" class="nav-icon"/>
          <span class="nav-text">持仓管理</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'account' }"
            @click="navigate('/trading/account')"
            @mouseenter="showTooltip($event, '账户管理')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:wallet" class="nav-icon"/>
          <span class="nav-text">账户管理</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'portfolio-analysis' }"
            @click="navigate('/portfolio/analysis')"
            @mouseenter="showTooltip($event, '组合分析')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:chart-bar" class="nav-icon"/>
          <span class="nav-text">组合分析</span>
        </div>
      </div>

      <!-- 交易执行 -->
      <div class="nav-section">
        <div class="nav-header">交易执行</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'trading' }"
            @click="navigate('/trading')"
            @mouseenter="showTooltip($event, '交易驾驶舱')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:terminal" class="nav-icon"/>
          <span class="nav-text">交易驾驶舱</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'orders' }"
            @click="navigate('/trading/orders')"
            @mouseenter="showTooltip($event, '订单管理')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:format-list-bulleted" class="nav-icon"/>
          <span class="nav-text">订单管理</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'signals' }"
            @click="navigate('/signals')"
            @mouseenter="showTooltip($event, '信号监控')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:bell" class="nav-icon"/>
          <span class="nav-text">信号监控</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'execution-analysis' }"
            @click="navigate('/trading/execution-analysis')"
            @mouseenter="showTooltip($event, '执行分析')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:speedometer" class="nav-icon"/>
          <span class="nav-text">执行分析</span>
        </div>
      </div>

      <!-- 风险监控 -->
      <div class="nav-section">
        <div class="nav-header">风险监控</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'risk-rules' }"
            @click="navigate('/risk/rules')"
            @mouseenter="showTooltip($event, '风控规则')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:shield-check" class="nav-icon"/>
          <span class="nav-text">风控规则</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'risk-monitor' }"
            @click="navigate('/risk/monitor')"
            @mouseenter="showTooltip($event, '实时监控')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:eye" class="nav-icon"/>
          <span class="nav-text">实时监控</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'risk-events' }"
            @click="navigate('/risk/events')"
            @mouseenter="showTooltip($event, '事件查看')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:alert-circle" class="nav-icon"/>
          <span class="nav-text">事件查看</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'blacklist' }"
            @click="navigate('/risk/blacklist')"
            @mouseenter="showTooltip($event, '黑名单')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:block-helper" class="nav-icon"/>
          <span class="nav-text">黑名单</span>
        </div>
      </div>

      <!-- 绩效分析 -->
      <div class="nav-section">
        <div class="nav-header">绩效分析</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'strategy-performance' }"
            @click="navigate('/performance/strategy')"
            @mouseenter="showTooltip($event, '策略绩效')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:trophy" class="nav-icon"/>
          <span class="nav-text">策略绩效</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'account-performance' }"
            @click="navigate('/performance/account')"
            @mouseenter="showTooltip($event, '账户绩效')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:chart-areaspline" class="nav-icon"/>
          <span class="nav-text">账户绩效</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'performance-comparison' }"
            @click="navigate('/performance/comparison')"
            @mouseenter="showTooltip($event, '绩效对比')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:scale-balance" class="nav-icon"/>
          <span class="nav-text">绩效对比</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'attribution' }"
            @click="navigate('/performance/attribution')"
            @mouseenter="showTooltip($event, '归因分析')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:puzzle" class="nav-icon"/>
          <span class="nav-text">归因分析</span>
        </div>
      </div>

      <!-- 系统管理 -->
      <div class="nav-section">
        <div class="nav-header">系统管理</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'system-monitor' }"
            @click="navigate('/system/monitor')"
            @mouseenter="showTooltip($event, '系统监控')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:monitor-dashboard" class="nav-icon"/>
          <span class="nav-text">系统监控</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'logs' }"
            @click="navigate('/system/logs')"
            @mouseenter="showTooltip($event, '日志查看')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:clipboard-text" class="nav-icon"/>
          <span class="nav-text">日志查看</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'users' }"
            @click="navigate('/system/users')"
            @mouseenter="showTooltip($event, '用户管理')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:account-group" class="nav-icon"/>
          <span class="nav-text">用户管理</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'settings' }"
            @click="navigate('/system/settings')"
            @mouseenter="showTooltip($event, '系统设置')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:cog" class="nav-icon"/>
          <span class="nav-text">系统设置</span>
        </div>
      </div>
    </div>

    <!-- 全局 Tooltip 元素 -->
    <div
        v-if="collapsed"
        class="nav-tooltip"
        :style="tooltipStyle"
        v-show="isTooltipVisible"
    >
      {{ tooltipContent }}
    </div>

    <!-- 缩放按钮 -->
    <div class="sidebar-toggle" @click="toggleCollapse">
      <Icon :icon="collapsed ? 'mdi:chevron-right' : 'mdi:chevron-left'" class="toggle-icon"/>
    </div>
  </div>
</template>

<script>
import {onMounted, onUnmounted, reactive, ref, watch} from "vue";
import {useRoute, useRouter} from "vue-router";
import {Icon} from '@iconify/vue';

export default {
  name: "AppSidebar",
  components: {
    Icon
  },
  emits: ["collapse"],
  setup(_, {emit}) {
    const route = useRoute();
    const router = useRouter();
    const activeMenu = ref("dashboard");
    const collapsed = ref(false);
    const systemInfo = reactive({
      cpu: 42,
      memory: 65
    });

    // Tooltip 相关状态
    const isTooltipVisible = ref(false);
    const tooltipContent = ref("");
    const tooltipStyle = ref({
      top: "0px",
      left: "0px"
    });

    let isComponentMounted = true;
    let routeWatchStop = null;

    // 设置活动菜单函数
    const setActiveMenu = () => {
      if (!isComponentMounted) return;

      try {
        const path = route?.path || "";
        const meta = route?.meta || {};

        console.log('当前路径:', path, '路由meta:', meta);

        // 优先使用路由meta中定义的menu字段
        if (meta.menu) {
          activeMenu.value = meta.menu;
          console.log('使用meta菜单:', meta.menu);
          return;
        }

        // 根据路径精确匹配菜单
        if (path.startsWith("/dashboard")) activeMenu.value = "dashboard";
        else if (path.startsWith("/data-sync-overview")) activeMenu.value = "data-sync-overview";
        else if (path === "/strategies/factor-research") activeMenu.value = "research";
        else if (path === "/strategies/factor-library") activeMenu.value = "factor-library";
        else if (path === "/strategies/backtest-period") activeMenu.value = "backtest-period";
        else if (path.startsWith("/strategies/backtest")) activeMenu.value = "backtest";
        else if (path.startsWith("/strategies/templates")) activeMenu.value = "strategy-templates";
        else if (path.startsWith("/strategies")) activeMenu.value = "strategies";
        else if (path.startsWith("/trading")) {
          if (path.includes("/orders")) activeMenu.value = "orders";
          else if (path.includes("/positions")) activeMenu.value = "positions";
          else if (path.includes("/account")) activeMenu.value = "account";
          else if (path.includes("/execution-analysis")) activeMenu.value = "execution-analysis";
          else activeMenu.value = "trading";
        } else if (path.startsWith("/baskets")) activeMenu.value = "baskets";
        else if (path.startsWith("/performance")) {
          if (path.includes("/strategy")) activeMenu.value = "strategy-performance";
          else if (path.includes("/account")) activeMenu.value = "account-performance";
          else if (path.includes("/comparison")) activeMenu.value = "performance-comparison";
          else if (path.includes("/attribution")) activeMenu.value = "attribution";
          else activeMenu.value = "performance";
        } else if (path.startsWith("/market")) {
          if (path.includes("/stocks")) activeMenu.value = "stocks";
          else if (path.includes("/etfs")) activeMenu.value = "etfs";
          else if (path.includes("/indexes")) activeMenu.value = "indexes";
          else if (path.includes("/industry-strength")) activeMenu.value = "industry-strength";
          else if (path.includes("/money-flow")) activeMenu.value = "money-flow";
          else if (path.includes("/limit-analysis")) activeMenu.value = "limit-analysis";
          else activeMenu.value = "market";
        }
        // 删除原有的数据同步相关菜单匹配
        else if (path.startsWith("/risk")) {
          if (path.includes("/rules")) activeMenu.value = "risk-rules";
          else if (path.includes("/monitor")) activeMenu.value = "risk-monitor";
          else if (path.includes("/events")) activeMenu.value = "risk-events";
          else if (path.includes("/blacklist")) activeMenu.value = "blacklist";
          else activeMenu.value = "risk";
        } else if (path.startsWith("/signals")) activeMenu.value = "signals";
        else if (path.startsWith("/system")) {
          if (path.includes("/monitor")) activeMenu.value = "system-monitor";
          else if (path.includes("/logs")) activeMenu.value = "logs";
          else if (path.includes("/users")) activeMenu.value = "users";
          else if (path.includes("/settings")) activeMenu.value = "settings";
          else activeMenu.value = "system";
        } else if (path.startsWith("/portfolio")) activeMenu.value = "portfolio-analysis";
        else {
          activeMenu.value = "";
          console.log('未匹配到菜单，当前路径:', path);
        }

        console.log('最终激活菜单:', activeMenu.value);
      } catch (error) {
        console.warn('设置活动菜单时出错:', error);
        activeMenu.value = "";
      }
    };


    // 增强的导航函数
    const navigate = (path) => {
      if (!isComponentMounted || !path) return;

      console.log('导航到:', path, '当前路由:', route.path);

      // 检查路径是否有效
      if (typeof path !== 'string') {
        console.error('导航路径无效:', path);
        return;
      }

      // 如果已经是当前路由，强制重新加载组件
      if (route.path === path) {
        console.log('已经是当前路由，强制重新加载');
        // 通过路由跳转到相同路径来触发组件重新渲染
        router.push('/redirect').then(() => {
          setTimeout(() => {
            router.push(path);
          }, 10);
        });
        return;
      }

      // 正常导航
      router.push(path).catch(err => {
        // 忽略导航重复的错误
        if (err?.name === 'NavigationDuplicated') {
          console.log('重复导航，已忽略:', path);
          // 即使是重复导航，也强制刷新数据
          if (path === '/data-sync') {
            console.log('强制刷新数据同步页面数据');
          }
        } else if (err?.message?.includes('Avoided redundant navigation')) {
          console.log('重复导航，已忽略:', path);
        } else {
          console.error('导航错误:', err);
          // 如果导航失败，尝试重新加载页面
          window.location.href = path;
        }
      });
    };

    const toggleCollapse = () => {
      if (!isComponentMounted) return;
      collapsed.value = !collapsed.value;
      emit("collapse", collapsed.value);
    };

    // Tooltip 显示函数
    const showTooltip = (event, content) => {
      if (!collapsed.value || !isComponentMounted) return;

      const navItem = event.currentTarget;
      const rect = navItem.getBoundingClientRect();

      // 计算 tooltip 位置
      const top = rect.top + (rect.height / 2);
      const left = rect.right + 8; // 在导航项右侧 8px 处

      tooltipContent.value = content;
      tooltipStyle.value = {
        top: `${top}px`,
        left: `${left}px`,
        transform: 'translateY(-50%)'
      };
      isTooltipVisible.value = true;
    };

    // Tooltip 隐藏函数
    const hideTooltip = () => {
      if (!isComponentMounted) return;
      isTooltipVisible.value = false;
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
      console.log('侧边栏组件挂载，当前路由:', route.path);
      setActiveMenu();

      // 启动系统信息更新
      const updateInterval = startSystemInfoUpdate();

      // 监听路由变化 - 使用更安全的配置
      routeWatchStop = watch(
          () => route.path,
          (newPath, oldPath) => {
            if (!isComponentMounted) return;

            console.log('路由变化:', oldPath, '->', newPath);

            // 添加防抖，避免频繁更新
            setTimeout(() => {
              if (isComponentMounted) {
                setActiveMenu();
              }
            }, 10);
          },
          {
            immediate: false,
            flush: 'post'
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
      console.log('侧边栏组件卸载');

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
      isTooltipVisible,
      tooltipContent,
      tooltipStyle,
      setActiveMenu,
      toggleCollapse,
      navigate,
      showTooltip,
      hideTooltip,
    };
  },
};
</script>

<style lang="scss" scoped>
// 导入全局变量
@use '@/assets/scss/variables' as *;
@use 'sass:map';

.app-sidebar {
  width: $sidebar-expanded-width;
  height: 100%;
  background-color: $sidebar-bg;
  color: $text-primary;
  display: flex;
  flex-direction: column;
  transition: width $transition-normal;
  overflow: hidden;
  position: relative;
  box-shadow: $card-shadow;
  border-right: $border-width solid $border-color;
  font-size: $sidebar-font-size;

  /* 隐藏滚动条但保持滚动功能 */
  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }

  &.collapsed {
    width: $sidebar-collapsed-width;
    overflow: visible;

    .sidebar-content {
      overflow: visible;
    }

    .nav-section {
      overflow: visible;
    }

    .nav-item {
      overflow: visible;
    }
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
  margin-bottom: map.get($spacers, 3);
  flex-shrink: 0;
}

.nav-header {
  padding: map.get($spacers, 3) map.get($spacers, 4) map.get($spacers, 2);
  font-size: $sidebar-header-font-size;
  color: $text-secondary;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: $font-weight-semibold;
  border-bottom: $border-width solid $border-color;
  margin: 0 map.get($spacers, 2) map.get($spacers, 2);
}

.nav-item {
  display: flex;
  align-items: center;
  padding: map.get($spacers, 2) map.get($spacers, 4);
  color: $text-primary;
  text-decoration: none;
  transition: all $transition-fast;
  cursor: pointer;
  border-left: 3px solid transparent;
  user-select: none;
  margin: 2px map.get($spacers, 2);
  border-radius: $border-radius;
  position: relative;
  font-size: $sidebar-font-size;

  &:hover {
    background-color: $hover-bg;
    color: $accent-color;
    transform: translateX(2px);
  }

  &.active {
    background-color: rgba($active-bg, 0.2);
    border-left-color: $accent-color;
    color: $accent-color;

    .nav-text {
      font-weight: $font-weight-bold;
      text-shadow: 0 1px 0.1px rgba(0, 0, 0, 0.2);
    }

    /* 图标使用系统渐变 */
    .nav-icon {
      background: $page-header-bg;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      transform: scale(1.2);
    }

    border-bottom: 2px solid $accent-color;
  }

  .nav-icon {
    margin-right: map.get($spacers, 2);
    width: $sidebar-icon-size;
    height: $sidebar-icon-size;
    color: $accent-color;
    flex-shrink: 0;
    transition: all $transition-fast;
  }

  .nav-text {
    font-weight: $font-weight-medium;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: $sidebar-font-size;
  }
}

/* 全局 Tooltip 样式 */
.nav-tooltip {
  position: fixed;
  background: $secondary-bg;
  color: $text-primary;
  padding: map.get($spacers, 2) map.get($spacers, 3);
  border-radius: $border-radius;
  font-size: $sidebar-font-size;
  font-weight: $font-weight-medium;
  white-space: nowrap;
  z-index: 1002;
  box-shadow: $hover-shadow;
  pointer-events: none;
  border: $border-width solid $border-color;
  animation: fadeIn $transition-fast ease;

  &::before {
    content: '';
    position: absolute;
    left: -6px;
    top: 50%;
    transform: translateY(-50%);
    width: 0;
    height: 0;
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
    border-right: 6px solid $secondary-bg;
  }
}

/* 折叠状态样式 */
.app-sidebar.collapsed {
  width: $sidebar-collapsed-width;
  overflow: visible;

  .nav-text {
    display: none;
  }

  .nav-header {
    display: none;
  }

  .nav-item {
    overflow: visible;
    justify-content: center;
    padding: map.get($spacers, 2);
    margin: 2px map.get($spacers, 2);
    border-radius: $border-radius;
    position: relative;

    .nav-icon {
      margin-right: 0;
      width: 22px;
      height: 22px;
    }
  }

  .nav-section {
    margin-bottom: map.get($spacers, 2);
  }

  .sidebar-content {
    overflow-y: auto;
    overflow-x: hidden;
  }
}

/* 缩放按钮 */
.sidebar-toggle {
  position: absolute;
  top: 16px;
  bottom: 40px;
  right: 8px;
  width: 18px;
  height: 18px;
  background: $page-header-bg;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  box-shadow: $card-shadow;
  transition: all $transition-normal;
  z-index: 1003;
  border: 2px solid $sidebar-bg;

  &:hover {
    transform: scale(1.1);
    box-shadow: $hover-shadow;
  }

  .toggle-icon {
    width: 12px;
    height: 12px;
  }
}

/* 折叠状态下调整按钮位置 */
.app-sidebar.collapsed .sidebar-toggle {
  left: calc(#{$sidebar-collapsed-width} - 10px);
}

/* Tooltip 淡入动画 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-50%) translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(-50%) translateX(0);
  }
}
</style>