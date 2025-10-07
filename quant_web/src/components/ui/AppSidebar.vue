<template>
  <div class="app-sidebar" :class="{ collapsed: collapsed }">
    <!-- 将导航内容包裹在可滚动容器中 -->
    <div class="sidebar-content">
      <!-- 所有导航部分保持不变 -->
      <!-- 数据中心 -->
      <div class="nav-section">
        <div class="nav-header">数据中心</div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'market' }"
            @click="navigate('/market/stocks')"
            @mouseenter="showTooltip($event, '市场数据')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="material-symbols:candlestick-chart" class="nav-icon"/>
          <span class="nav-text">市场数据</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'data-sync' }"
            @click="navigate('/data-sync')"
            @mouseenter="showTooltip($event, '数据同步')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:sync" class="nav-icon"/>
          <span class="nav-text">数据同步</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'data-quality' }"
            @click="navigate('/data-quality')"
            @mouseenter="showTooltip($event, '数据质量')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:check-circle" class="nav-icon"/>
          <span class="nav-text">数据质量</span>
        </div>
        <div
            class="nav-item"
            :class="{ active: activeMenu === 'sync-history' }"
            @click="navigate('/data-sync/history')"
            @mouseenter="showTooltip($event, '同步历史')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:history" class="nav-icon"/>
          <span class="nav-text">同步历史</span>
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
            :class="{ active: activeMenu === 'strategy-templates' }"
            @click="navigate('/strategies/templates')"
            @mouseenter="showTooltip($event, '策略模板')"
            @mouseleave="hideTooltip"
        >
          <Icon icon="mdi:content-copy" class="nav-icon"/>
          <span class="nav-text">策略模板</span>
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

    <!-- 缩放按钮移到侧边栏外层，不包含在滚动内容中 -->
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

// 修复后的设置活动菜单函数
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

        // 根据新菜单结构更新路径匹配逻辑 - 增强数据同步相关路径的匹配
        if (path.startsWith("/dashboard")) activeMenu.value = "dashboard";
        else if (path.includes("/backtest")) activeMenu.value = "backtest";
        else if (path.includes("/factor-research")) activeMenu.value = "research";
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
        } else if (path.startsWith("/market")) activeMenu.value = "market";
        else if (path.startsWith("/data-sync")) {
          // 修复：精确匹配数据同步路径
          if (path === "/data-sync" || path.startsWith("/data-sync/")) {
            activeMenu.value = "data-sync";
          }
          console.log('数据同步路径匹配结果:', activeMenu.value);
        } else if (path.startsWith("/data-quality")) activeMenu.value = "data-quality";
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
        else if (path.startsWith("/strategies/templates")) activeMenu.value = "strategy-templates";
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
    // 安全的导航函数 - 添加调试信息
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
            // 触发自定义事件或使用其他方式刷新数据
            console.log('强制刷新数据同步页面数据');
          }
        } else if (err?.message?.includes('Avoided redundant navigation')) {
          console.log('重复导航，已忽略:', path);
        } else {
          console.error('导航错误:', err);
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
.app-sidebar {
  width: var(--sidebar-width, 240px);
  height: 100%;
  background-color: var(--secondary-bg, #1f2937);
  color: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  position: relative;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);

  /* 隐藏滚动条但保持滚动功能 */
  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }

  &.collapsed {
    width: var(--sidebar-collapsed-width, 64px);

    /* 在折叠状态下允许 Tooltip 溢出 */
    overflow: visible;

    /* 确保滚动容器也允许溢出 */
    .sidebar-content {
      overflow: visible;
    }

    /* 确保导航部分允许溢出 */
    .nav-section {
      overflow: visible;
    }

    /* 确保导航项允许溢出 */
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
  padding-bottom: var(--footer-height, 40px);
  /* 隐藏滚动条但保持滚动功能 */
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
  color: var(--text-secondary, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  margin: 0 12px 8px;
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
  margin: 2px 8px;
  border-radius: 6px;
  position: relative;

  &:hover {
    background-color: rgba(79, 156, 249, 0.2);
    color: #fff;
    transform: translateX(2px);
  }

  &.active {
    background-color: rgba(79, 156, 249, 0.2);
    border-left-color: var(--accent-color, #4f9cf9);
    color: #fff;
    /* 文字加粗+阴影 */
    .nav-text {
      font-weight: 800; /* 比默认的500更粗 */
      text-shadow: 0 1px 0.1px rgba(0, 0, 0, 0.2); /* 文字阴影增加立体感 */
    }

    /* 图标放大+加深颜色 */
    .nav-icon {
      width: 22px;
      height: 22px;
      color: #3a89e9; /* 比默认主色稍深 */
      transform: scale(1.2); /* 轻微放大 */
    }

    /* 底部边框突出（适合横向导航） */
    border-bottom: 2px solid var(--accent-color, #4f9cf9);
  }

  .nav-icon {
    margin-right: 12px;
    width: 20px;
    height: 20px;
    color: var(--accent-color, #4f9cf9);
    flex-shrink: 0;
  }

  .nav-text {
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

/* 全局 Tooltip 样式 */
.nav-tooltip {
  position: fixed;
  background: rgb(25, 43, 63);
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  z-index: 1002;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  pointer-events: none;
  border: 1px solid rgba(255, 255, 255, 0.2);
  animation: fadeIn 0.2s ease;

  /* 添加小箭头 */
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
    border-right: 6px solid rgb(25, 43, 63);
  }
}

/* 折叠状态样式 */
.app-sidebar.collapsed {
  width: var(--sidebar-collapsed-width, 64px);
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
    padding: 12px;
    margin: 2px 8px;
    border-radius: 8px;
    position: relative;

    .nav-icon {
      margin-right: 0;
      width: 22px;
      height: 22px;
    }
  }

  .nav-section {
    margin-bottom: 8px;
  }

  /* 确保滚动容器也允许滚动 */
  .sidebar-content {
    overflow-y: auto;
    overflow-x: hidden;
  }
}

/* 缩放按钮 - 调整位置和大小 */
.sidebar-toggle {
  position: absolute;
  top: 16px;
  bottom: var(--footer-height, 40px);
  right: 8px;
  width: 18px;
  height: 18px;
  background-color: var(--accent-color, #4f9cf9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  transition: all 0.3s ease;
  z-index: 1003;
  border: 2px solid var(--secondary-bg, #1f2937);

  &:hover {
    background-color: var(--accent-hover, #3a8de4);
    transform: scale(1.1);
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.3);
  }

  .toggle-icon {
    width: 12px;
    height: 12px;
  }
}

/* 折叠状态下调整按钮位置 */
.app-sidebar.collapsed .sidebar-toggle {
  left: calc(var(--sidebar-collapsed-width, 64px) - 10px);
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

/* 确保 CSS 变量有回退值 */
:root {
  --sidebar-width: 240px;
  --sidebar-collapsed-width: 64px;
  --secondary-bg: #1f2937;
  --text-primary: #f3f4f6;
  --text-secondary: #9ca3af;
  --accent-color: #4f9cf9;
  --accent-hover: #3a8de4;
  --footer-height: 40px;
}
</style>