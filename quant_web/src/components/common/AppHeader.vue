<!-- 应用头部组件 - 迁移到 Naive UI 和统一图标方案 -->
<template>
  <header class="app-header">
    <div class="logo-section">
      <div class="logo" @click="$router.push('/market/dashboard')">
        <img src="/logo.svg" class="logo-img" alt="一念量化" />
        <span class="logo-text">一念量化</span>
      </div>
    </div>

    <div class="status-section">
      <!-- 市场状态 -->
      <div class="status-item market-status">
        <div class="status-indicator status-open"></div>
        <div class="market-data">
          <span class="market-name">上证</span>
          <span class="market-value">3,245.68</span>
          <n-tag :type="getMarketChangeType('positive')" size="small">
            +1.25%
          </n-tag>
        </div>
        <div class="market-data">
          <span class="market-name">深证</span>
          <span class="market-value">10,845.32</span>
          <n-tag :type="getMarketChangeType('positive')" size="small">
            +0.87%
          </n-tag>
        </div>
        <div class="market-data">
          <span class="market-name">创业</span>
          <span class="market-value">2,245.67</span>
          <n-tag :type="getMarketChangeType('negative')" size="small">
            -0.23%
          </n-tag>
        </div>
      </div>

      <!-- 交易时段状态 -->
      <div class="status-item trading-session">
        <!-- 使用 SmartIcon 组件 -->
        <smart-icon name="Time" :size="16" class="session-icon" />
        <span>交易时段: 09:30-11:30</span>
      </div>
    </div>

    <!-- 头部小部件 -->
    <div class="header-widgets">
      <!-- 策略状态 -->
      <n-tooltip placement="bottom">
        <template #trigger>
          <div class="header-widget strategy-status">
            <div class="widget-content">
              <smart-icon
                name="Settings"
                :size="16"
                :class="['widget-icon', `icon-${strategyStatus.health}`]"
              />
              <span class="widget-count"
                >{{ strategyStatus.running }}/{{ strategyStatus.total }}</span
              >
              <div class="status-dot" :class="strategyStatus.health"></div>
            </div>
          </div>
        </template>
        运行中策略: {{ strategyStatus.running }}/{{ strategyStatus.total
        }}<br />
        健康状态: {{ getHealthText(strategyStatus.health) }}
      </n-tooltip>

      <!-- 信号状态 -->
      <n-tooltip placement="bottom">
        <template #trigger>
          <div class="header-widget signal-status">
            <div class="widget-content">
              <smart-icon
                name="NotificationsOutline"
                :size="16"
                class="widget-icon icon-primary"
              />
              <span class="widget-count"
                >{{ signalStats.triggered }}/{{ signalStats.today }}</span
              >
            </div>
          </div>
        </template>
        今日信号: {{ signalStats.today }}个<br />
        已触发: {{ signalStats.triggered }}个
      </n-tooltip>

      <!-- 订单状态 -->
      <n-tooltip placement="bottom">
        <template #trigger>
          <div class="header-widget order-status">
            <div class="widget-content">
              <smart-icon
                name="SwapVertical"
                :size="16"
                class="widget-icon icon-primary"
              />
              <span class="widget-count"
                >{{ orderStats.executed }}/{{ orderStats.pending }}</span
              >
            </div>
          </div>
        </template>
        待处理订单: {{ orderStats.pending }}个<br />
        已执行: {{ orderStats.executed }}个
      </n-tooltip>

      <!-- 风险等级 -->
      <n-tooltip placement="bottom">
        <template #trigger>
          <div class="header-widget risk-level" :class="riskLevel.class">
            <div class="widget-content">
              <smart-icon
                name="ShieldCheckmark"
                :size="16"
                :class="['widget-icon', `icon-${riskLevel.class}`]"
              />
              <span class="widget-count">{{ riskLevel.text }}</span>
            </div>
          </div>
        </template>
        当前风险等级: {{ riskLevel.text }}<br />
        {{ getRiskDescription(riskLevel.text) }}
      </n-tooltip>
    </div>

    <div class="time-section">
      <div class="current-date">{{ formattedDate }}</div>
      <div class="current-time">{{ formattedTime }}</div>
    </div>

    <div class="user-section">
      <n-dropdown
        :show="userMenuVisible"
        :on-update:show="(v) => userMenuVisible = v"
        placement="bottom-end"
        :options="userMenuOptions"
        @select="handleCommand"
      >
        <div class="user-dropdown">
          <div class="user-info">
            <div class="user-avatar">
              <n-avatar round size="small">
                <!-- 使用 SmartIcon 组件 -->
                <smart-icon name="Person" />
              </n-avatar>
            </div>
            <span class="user-name">{{ userName }}</span>
            <!-- 使用 SmartIcon 组件 -->
            <smart-icon name="ChevronDown" :size="16" class="dropdown-icon" />
          </div>
        </div>
      </n-dropdown>
    </div>
  </header>
</template>

<script>
import { defineComponent, ref, computed, onMounted, onUnmounted, h } from "vue";
import { useRouter } from "vue-router";
import { NIcon, NTooltip, NTag, NDropdown, NAvatar } from "naive-ui";
// 导入 SmartIcon 组件
import SmartIcon from "../common/SmartIcon.vue";

export default defineComponent({
  name: "AppHeader",
  components: {
    NIcon,
    NTooltip,
    NTag,
    NDropdown,
    NAvatar,
    SmartIcon, // 注册 SmartIcon 组件
  },
  props: {
    userName: {
      type: String,
      default: "用户",
    },
  },
  setup(props) {
    const router = useRouter();
    const currentTime = ref(new Date());
    const formattedTime = ref("");
    const formattedDate = ref("");

    // 策略状态
    const strategyStatus = ref({
      running: 3,
      total: 5,
      health: "healthy",
    });

    // 用户菜单可见性
    const userMenuVisible = ref(false);

    // 信号统计
    const signalStats = ref({
      today: 12,
      triggered: 8,
    });

    // 订单统计
    const orderStats = ref({
      pending: 2,
      executed: 15,
    });

    // 风险等级
    const riskLevel = computed(() => {
      const levels = {
        low: { class: "risk-low", text: "低" },
        medium: { class: "risk-medium", text: "中" },
        high: { class: "risk-high", text: "高" },
      };
      return levels.medium;
    });

    // 用户菜单选项
    const userMenuOptions = [
      {
        label: "个人中心",
        key: "profile",
        icon: () => h(SmartIcon, { name: "Person" }),
      },
      {
        type: "divider",
        key: "d1",
      },
      {
        label: "退出登录",
        key: "logout",
        icon: () => h(SmartIcon, { name: "LogOut" }),
      },
    ];

    // 获取健康状态文本
    const getHealthText = (health) => {
      const healthMap = {
        healthy: "正常",
        warning: "警告",
        danger: "危险",
      };
      return healthMap[health] || "未知";
    };

    // 获取风险等级描述
    const getRiskDescription = (riskLevel) => {
      const descriptions = {
        低: "保守策略，风险可控",
        中: "平衡策略，适度风险",
        高: "激进策略，高风险",
      };
      return descriptions[riskLevel] || "风险等级未知";
    };

    // 获取市场变化类型 — A 股红涨绿跌：正→红(error)，负→绿(success)
    const getMarketChangeType = (change) => {
      return change === "positive" ? "error" : "success";
    };

    // 时间格式化
    const formatTime = (date) => {
      try {
        return date.toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        });
      } catch (error) {
        const hours = String(date.getHours()).padStart(2, "0");
        const minutes = String(date.getMinutes()).padStart(2, "0");
        const seconds = String(date.getSeconds()).padStart(2, "0");
        return `${hours}:${minutes}:${seconds}`;
      }
    };

    const formatDate = (date) => {
      try {
        return date.toLocaleDateString("zh-CN", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          weekday: "short",
        });
      } catch (error) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
        const weekday = weekdays[date.getDay()];
        return `${year}/${month}/${day} 周${weekday}`;
      }
    };

    // 更新时间显示
    const updateTime = () => {
      currentTime.value = new Date();
      formattedTime.value = formatTime(currentTime.value);
      formattedDate.value = formatDate(currentTime.value);
    };

    // 模拟交易状态更新
    const updateTradingStatus = () => {
      const healthStates = ["healthy", "warning", "danger"];
      strategyStatus.value.health = healthStates[Math.floor(Math.random() * 3)];
      signalStats.value.today = Math.max(
        5,
        Math.min(20, signalStats.value.today + (Math.random() > 0.5 ? 1 : -1)),
      );
      orderStats.value.pending = Math.max(
        0,
        Math.min(5, orderStats.value.pending + (Math.random() > 0.7 ? 1 : -1)),
      );
    };

    let timeInterval;
    let tradingInterval;

    onMounted(() => {
      updateTime();
      timeInterval = setInterval(updateTime, 1000);
      tradingInterval = setInterval(updateTradingStatus, 10000);
    });

    onUnmounted(() => {
      if (timeInterval) clearInterval(timeInterval);
      if (tradingInterval) clearInterval(tradingInterval);
    });

    const handleCommand = (key) => {
      userMenuVisible.value = false;
      if (key === "logout") {
        router.push("/login");
      } else if (key === "profile") {
        router.push("/market/dashboard");
      }
    };

    return {
      formattedTime,
      formattedDate,
      strategyStatus,
      signalStats,
      orderStats,
      riskLevel,
      userMenuOptions,
      userMenuVisible,
      handleCommand,
      getHealthText,
      getRiskDescription,
      getMarketChangeType,
      userName: props.userName,
    };
  },
});
</script>

<style lang="scss" scoped>
.app-header {
  display: flex;
  align-items: center;
  height: 60px;
  padding: 0 16px;
  background-color: var(--n-card-color, #161b22);
  border-bottom: 1px solid var(--n-border-color, #30363d);
  box-shadow: var(--n-box-shadow-1);
  position: sticky;
  top: 0;
  z-index: 1000;
}

.logo-section {
  display: flex;
  align-items: center;
  margin-right: 32px;
}

.logo {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 18px;
  color: var(--n-text-color-1);
  cursor: pointer;
}

.logo-img {
  width: 36px;
  height: 36px;
  margin-right: 12px;
  object-fit: contain;
}

.logo-text {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 0.08em;
  background: linear-gradient(
    135deg,
    var(--n-primary-color, #448aff) 0%,
    #40c4ff 100%
  );
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.status-section {
  display: flex;
  align-items: center;
  flex: 1;
}

.status-item {
  display: flex;
  align-items: center;
  margin-right: 24px;
}

.market-status {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
}

.status-open {
  background-color: var(--n-success-color);
}

.market-data {
  display: flex;
  align-items: center;
  gap: 6px;
}

.market-name {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.market-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.trading-session {
  font-size: 14px;
  color: var(--n-text-color-2);
}

.session-icon {
  margin-right: 6px;
}

.header-widgets {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-right: 24px;
}

.header-widget {
  padding: 6px 12px;
  background-color: var(--n-hover-color);
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s var(--n-bezier);
}

.header-widget:hover {
  background-color: var(--n-pressed-color);
}

.widget-content {
  display: flex;
  align-items: center;
  gap: 6px;
}

.widget-icon {
  color: var(--n-text-color-3);

  &.icon-primary {
    color: var(--n-primary-color);
  }
  &.icon-healthy {
    color: var(--n-success-color);
  }
  &.icon-warning {
    color: var(--n-warning-color);
  }
  &.icon-danger {
    color: var(--n-error-color);
  }
  &.icon-risk-low {
    color: var(--n-success-color);
  }
  &.icon-risk-medium {
    color: var(--n-warning-color);
  }
  &.icon-risk-high {
    color: var(--n-error-color);
  }
}

.widget-count {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-dot.healthy {
  background-color: var(--n-success-color);
}

.status-dot.warning {
  background-color: var(--n-warning-color);
}

.status-dot.danger {
  background-color: var(--n-error-color);
}

.risk-level.risk-low {
  border-left: 3px solid var(--n-success-color);
}

.risk-level.risk-medium {
  border-left: 3px solid var(--n-warning-color);
}

.risk-level.risk-high {
  border-left: 3px solid var(--n-error-color);
}

.time-section {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin-right: 24px;
}

.current-date {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.current-time {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.user-section {
  display: flex;
  align-items: center;
}

.user-dropdown {
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background-color 0.2s var(--n-bezier);
}

.user-dropdown:hover {
  background-color: var(--n-hover-color);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  font-size: 14px;
  color: var(--n-text-color-1);
  font-weight: 500;
}

.dropdown-icon {
  color: var(--n-text-color-3);
  transition: transform 0.2s var(--n-bezier);
}

.user-dropdown:hover .dropdown-icon {
  transform: rotate(180deg);
}
</style>
