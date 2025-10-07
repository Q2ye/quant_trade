<template>
  <header class="app-header">
    <div class="logo-section">
      <div class="logo">
        <Icon icon="mdi:robot" class="logo-icon"/>
        <span class="logo-text">量化交易平台</span>
      </div>
    </div>

    <div class="status-section">
      <!-- 市场状态 -->
      <div class="status-item market-status">
        <div class="status-indicator status-open"></div>
        <div class="market-data">
          <span class="market-name">上证</span>
          <span class="market-value">3,245.68</span>
          <span class="market-change positive">+1.25%</span>
        </div>
        <div class="market-data">
          <span class="market-name">深证</span>
          <span class="market-value">10,845.32</span>
          <span class="market-change positive">+0.87%</span>
        </div>
        <div class="market-data">
          <span class="market-name">创业</span>
          <span class="market-value">2,245.67</span>
          <span class="market-change negative">-0.23%</span>
        </div>
      </div>

      <!-- 交易时段状态 -->
      <div class="status-item trading-session">
        <Icon icon="mdi:clock-outline" class="session-icon"/>
        <span>交易时段: 09:30-11:30</span>
      </div>
    </div>

    <!-- 修复：简化widgets容器，确保单行显示 -->
    <div class="header-widgets">
      <!-- 策略状态 -->
      <div class="header-widget strategy-status"
           :title="`运行中策略: ${strategyStatus.running}/${strategyStatus.total}\n健康状态: ${getHealthText(strategyStatus.health)}`">
        <div class="widget-content">
          <Icon icon="mdi:cog" class="widget-icon"/>
          <span class="widget-count">{{ strategyStatus.running }}/{{ strategyStatus.total }}</span>
          <div class="status-dot" :class="strategyStatus.health"></div>
        </div>
      </div>

      <!-- 信号状态 -->
      <div class="header-widget signal-status"
           :title="`今日信号: ${signalStats.today}个\n已触发: ${signalStats.triggered}个`">
        <div class="widget-content">
          <Icon icon="mdi:bell-outline" class="widget-icon"/>
          <span class="widget-count">{{ signalStats.triggered }}/{{ signalStats.today }}</span>
        </div>
      </div>

      <!-- 订单状态 -->
      <div class="header-widget order-status"
           :title="`待处理订单: ${orderStats.pending}个\n已执行: ${orderStats.executed}个`">
        <div class="widget-content">
          <Icon icon="mdi:swap-horizontal" class="widget-icon"/>
          <span class="widget-count"> {{ orderStats.executed }} / {{ orderStats.pending }}</span>
        </div>
      </div>

      <!-- 风险等级 -->
      <div class="header-widget risk-level" :class="riskLevel.class"
           :title="`当前风险等级: ${riskLevel.text}\n${getRiskDescription(riskLevel.text)}`">
        <div class="widget-content">
          <Icon icon="mdi:shield-check-outline" class="widget-icon"/>
          <span class="widget-count">{{ riskLevel.text }}</span>
        </div>
      </div>
    </div>

    <div class="time-section">
      <div class="current-date">{{ formattedDate }}</div>
      <div class="current-time">{{ formattedTime }}</div>
    </div>

    <div class="user-section">
      <div class="user-dropdown" @click="toggleUserMenu">
        <div class="user-info">
          <div class="user-avatar">
            <Icon icon="mdi:account-circle" class="avatar-icon"/>
          </div>
          <span class="user-name">{{ userName }}</span>
          <Icon icon="mdi:chevron-down" class="dropdown-icon" :class="{ rotated: userMenuOpen }"/>
        </div>

        <div class="user-menu" v-show="userMenuOpen">
          <div class="menu-item" @click="handleCommand('profile')">
            <Icon icon="mdi:account-outline" class="menu-icon"/>
            <span>个人中心</span>
          </div>
          <div class="menu-item" @click="handleCommand('settings')">
            <Icon icon="mdi:cog-outline" class="menu-icon"/>
            <span>系统设置</span>
          </div>
          <div class="menu-divider"></div>
          <div class="menu-item" @click="handleCommand('logout')">
            <Icon icon="mdi:logout" class="menu-icon"/>
            <span>退出登录</span>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script>
import {computed, onMounted, onUnmounted, ref} from "vue";
import {useRouter} from "vue-router";
import {Icon} from '@iconify/vue'

export default {
  name: "AppHeader",
  components: {
    Icon
  },
  props: {
    userName: {
      type: String,
      default: "用户"
    }
  },
  setup(props) {
    const router = useRouter();
    const currentTime = ref(new Date());
    const userMenuOpen = ref(false);

    // 策略状态 - 修复：确保数据正确
    const strategyStatus = ref({
      running: 3,
      total: 5,
      health: 'healthy'
    });

    // 信号统计 - 修复：确保数据正确
    const signalStats = ref({
      today: 12,
      triggered: 8
    });

    // 订单统计 - 修复：确保数据正确
    const orderStats = ref({
      pending: 2,
      executed: 15
    });

    // 风险等级 - 修复：确保数据正确
    const riskLevel = computed(() => {
      const levels = {
        low: {class: 'risk-low', text: '低'},
        medium: {class: 'risk-medium', text: '中'},
        high: {class: 'risk-high', text: '高'}
      };
      return levels.medium;
    });

    // 获取健康状态文本
    const getHealthText = (health) => {
      const healthMap = {
        healthy: '正常',
        warning: '警告',
        danger: '危险'
      };
      return healthMap[health] || '未知';
    };

    // 获取风险等级描述
    const getRiskDescription = (riskLevel) => {
      const descriptions = {
        '低': '保守策略，风险可控',
        '中': '平衡策略，适度风险',
        '高': '激进策略，高风险'
      };
      return descriptions[riskLevel] || '风险等级未知';
    };

    // 时间格式化
    const formattedTime = ref("");
    const formattedDate = ref("");

    const updateTime = () => {
      currentTime.value = new Date();
      formattedTime.value = currentTime.value.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      });
      formattedDate.value = currentTime.value.toLocaleDateString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        weekday: "short"
      });
    };

    // 模拟交易状态更新
    const updateTradingStatus = () => {
      const healthStates = ['healthy', 'warning', 'danger'];
      strategyStatus.value.health = healthStates[Math.floor(Math.random() * 3)];
      signalStats.value.today = Math.max(5, Math.min(20, signalStats.value.today + (Math.random() > 0.5 ? 1 : -1)));
      orderStats.value.pending = Math.max(0, Math.min(5, orderStats.value.pending + (Math.random() > 0.7 ? 1 : -1)));
    };

    // 切换用户菜单
    const toggleUserMenu = () => {
      userMenuOpen.value = !userMenuOpen.value;
    };

    // 点击外部关闭菜单
    const closeUserMenu = (event) => {
      if (!event.target.closest('.user-dropdown')) {
        userMenuOpen.value = false;
      }
    };

    let timeInterval;
    let tradingInterval;

    onMounted(() => {
      updateTime();
      timeInterval = setInterval(updateTime, 1000);
      tradingInterval = setInterval(updateTradingStatus, 10000);
      document.addEventListener('click', closeUserMenu);
    });

    onUnmounted(() => {
      clearInterval(timeInterval);
      clearInterval(tradingInterval);
      document.removeEventListener('click', closeUserMenu);
    });

    const handleCommand = (command) => {
      userMenuOpen.value = false;
      if (command === "logout") {
        router.push("/login");
      } else if (command === "settings") {
        router.push("/system/settings");
      } else if (command === "profile") {
        router.push("/user/profile");
      }
    };

    return {
      formattedTime,
      formattedDate,
      strategyStatus,
      signalStats,
      orderStats,
      riskLevel,
      userMenuOpen,
      toggleUserMenu,
      handleCommand,
      getHealthText,
      getRiskDescription,
      userName: props.userName
    };
  },
};
</script>

<style lang="scss" scoped>
.app-header {
  height: 50px; /* 减少高度 */
  background: linear-gradient(135deg, var(--secondary-bg) 0%, #2d3748 100%);
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  position: relative;
  gap: 20px; /* 添加间距控制 */
}

.logo-section {
  flex-shrink: 0;

  .logo {
    display: flex;
    align-items: center;
    font-size: 18px; /* 减小字体 */
    font-weight: bold;
    color: var(--accent-color);

    .logo-icon {
      margin-right: 8px;
      width: 24px; /* 减小图标 */
      height: 24px;
      color: #22D3EE;
    }

    .logo-text {
      background: linear-gradient(135deg, #60A5FA 50%, #3B82F6 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
  }
}

.status-section {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 20px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;

  &.market-status {
    display: flex;
    align-items: center;
    gap: 16px;

    .status-indicator {
      width: 8px; /* 减小指示器 */
      height: 8px;
      border-radius: 50%;

      &.status-open {
        background-color: var(--success-color);
        box-shadow: 0 0 4px var(--success-color);
      }
    }

    .market-data {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px; /* 减小字体 */
      .market-name {
        color: var(--text-secondary);
        font-weight: 500;
      }

      .market-value {
        color: var(--text-primary);
        font-weight: 600;
      }

      .market-change {
        font-weight: 600;

        &.positive {
          color: var(--success-color);
        }

        &.negative {
          color: var(--danger-color);
        }
      }
    }
  }

  &.trading-session {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px; /* 减小字体 */
    color: var(--text-secondary);

    .session-icon {
      width: 12px; /* 减小图标 */
      height: 12px;
      color: var(--accent-color);
    }
  }
}

/* 修复：优化widgets容器，确保单行显示 */
.header-widgets {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.header-widget {
  min-width: 70px; /* 减小宽度 */
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
  position: relative;
  cursor: help; /* 添加帮助光标 */

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    transform: translateY(-1px);
  }

  .widget-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 6px 8px; /* 减小内边距 */
    gap: 2px;
    position: relative;
  }

  .widget-icon {
    width: 14px; /* 减小图标 */
    height: 14px;
    color: var(--accent-color);
  }

  .widget-count {
    font-size: 14px; /* 减小字体 */
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
  }

  .widget-label {
    color: var(--text-secondary);
    font-size: 10px; /* 减小字体 */
    line-height: 1;
  }

  &.strategy-status {
    .status-dot {
      position: absolute;
      top: 4px;
      right: 4px;
      width: 6px; /* 减小圆点 */
      height: 6px;
      border-radius: 50%;

      &.healthy {
        background-color: var(--success-color);
        box-shadow: 0 0 4px var(--success-color);
      }

      &.warning {
        background-color: var(--warning-color);
        box-shadow: 0 0 4px var(--warning-color);
      }

      &.danger {
        background-color: var(--danger-color);
        box-shadow: 0 0 4px var(--danger-color);
      }
    }
  }

  &.risk-level {
    .widget-count {
      font-size: 13px; /* 减小字体 */
    }

    &.risk-low {
      border-color: var(--success-color);

      .widget-icon, .widget-count {
        color: var(--success-color);
      }
    }

    &.risk-medium {
      border-color: var(--warning-color);

      .widget-icon, .widget-count {
        color: var(--warning-color);
      }
    }

    &.risk-high {
      border-color: var(--danger-color);

      .widget-icon, .widget-count {
        color: var(--danger-color);
      }
    }
  }
}

.time-section {
  flex-shrink: 0;
  text-align: center;

  .current-date {
    font-size: 11px; /* 减小字体 */
    color: var(--text-secondary);
    margin-bottom: 1px;
  }

  .current-time {
    font-size: 14px; /* 减小字体 */
    font-weight: 600;
    color: var(--text-primary);
    font-family: 'Courier New', monospace;
  }
}

.user-section {
  flex-shrink: 0;

  .user-dropdown {
    position: relative;
    cursor: pointer;
  }

  .user-info {
    display: flex;
    align-items: center;
    padding: 6px 10px; /* 减小内边距 */
    border-radius: 6px;
    transition: all 0.3s ease;
    background: rgba(255, 255, 255, 0.05);

    &:hover {
      background: rgba(255, 255, 255, 0.1);
    }

    .user-avatar {
      width: 24px; /* 减小头像 */
      height: 24px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--accent-color);

      .avatar-icon {
        width: 16px; /* 减小图标 */
        height: 16px;
        color: white;
      }
    }

    .user-name {
      margin: 0 8px;
      font-size: 13px; /* 减小字体 */
      color: var(--text-primary);
      font-weight: 500;
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .dropdown-icon {
      width: 16px; /* 减小图标 */
      height: 16px;
      color: var(--text-secondary);
      transition: transform 0.3s ease;

      &.rotated {
        transform: rotate(180deg);
      }
    }
  }

  .user-menu {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 4px;
    background: rgb(15, 26, 38);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgb(25, 43, 63, 0.15);
    min-width: 140px;
    z-index: 1000;
    overflow: hidden;

    .menu-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px; /* 减小内边距 */
      font-size: 13px; /* 减小字体 */
      color: var(--text-primary);
      transition: background-color 0.2s ease;
      cursor: pointer;

      &:hover {
        background: rgba(79, 156, 249, 0.2);
      }

      .menu-icon {
        width: 16px; /* 减小图标 */
        height: 16px;
        color: var(--text-secondary);
      }
    }

    .menu-divider {
      height: 1px;
      background: var(--border-color);
      margin: 4px 0;
    }
  }
}

/* 仅保留中大屏幕适配 */
@media (max-width: 1200px) {
  .status-section .market-status {
    display: none;
  }
  .status-section .trading-session {
    display: none;
  }
  .header-widgets {
    gap: 10px;

    .header-widget {
      min-width: 65px;

      .widget-content {
        padding: 5px 6px;
      }

      .widget-count {
        font-size: 13px;
      }
    }
  }
}

@media (max-width: 992px) {
  .header-widgets {
    gap: 8px;

    .header-widget {
      min-width: 60px;

      .widget-content {
        padding: 4px 5px;
      }

      .widget-count {
        font-size: 12px;
      }
    }
  }
  .time-section {
    display: none;
  }
}
</style>