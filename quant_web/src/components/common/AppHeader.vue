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
        <div
          class="status-indicator"
          :class="isMarketOpen ? 'status-open' : 'status-closed'"
        ></div>
        <div
          v-for="idx in marketIndices"
          :key="idx.code"
          class="market-data"
        >
          <span class="market-name">{{ idx.name }}</span>
          <span class="market-value">{{ idx.value }}</span>
          <n-tag
            v-if="idx.change != null"
            :type="getMarketChangeType(idx.change)"
            size="small"
          >
            {{ formatPct(idx.change) }}
          </n-tag>
        </div>
      </div>

      <!-- 交易时段状态 -->
      <div class="status-item trading-session">
        <!-- 使用 SmartIcon 组件 -->
        <smart-icon name="Time" :size="16" class="session-icon" />
        <span>{{ sessionText }}</span>
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
// 真实数据源 API
import strategyAPI from "@/api/strategy";
import { monitorAPI } from "@/api/monitor";
import riskAPI from "@/api/risk";
import marketAPI from "@/api/market";
import tradeAPI from "@/api/trade";

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

    // 市场指数（真实数据，加载前占位）
    const marketIndices = ref([
      { name: "上证", code: "000001.SH", value: "--", change: null },
      { name: "深证", code: "399001.SZ", value: "--", change: null },
      { name: "创业", code: "399006.SZ", value: "--", change: null },
    ]);

    // 交易时段
    const isMarketOpen = ref(false);
    const sessionText = ref("交易时段: --");

    // 策略状态
    const strategyStatus = ref({
      running: 0,
      total: 0,
      health: "healthy",
    });

    // 信号统计
    const signalStats = ref({
      today: 0,
      triggered: 0,
    });

    // 订单统计
    const orderStats = ref({
      pending: 0,
      executed: 0,
    });

    // 风险等级
    const riskLevel = ref({ class: "risk-medium", text: "--" });

    // 用户名：优先从 user store 持久化数据读取，回退 prop 默认值
    const userName = computed(() => {
      try {
        const raw = localStorage.getItem("user");
        if (raw) {
          const u = JSON.parse(raw);
          if (u?.username) return u.username;
          if (u?.name) return u.name;
        }
      } catch {
        /* ignore malformed storage */
      }
      return props.userName;
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

    // 市场涨跌类型 — A 股红涨绿跌：正→红(error)，负→绿(success)
    const getMarketChangeType = (change) => {
      return Number(change) >= 0 ? "error" : "success";
    };

    // 涨跌幅格式化（pct_chg 已是百分比单位）
    const formatPct = (v) => {
      const n = Number(v);
      if (Number.isNaN(n)) return "--";
      return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
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

    // 更新交易时段（A 股：09:30-11:30 / 13:00-15:00）
    const updateSession = () => {
      const now = new Date();
      const minutes = now.getHours() * 60 + now.getMinutes();
      const day = now.getDay();
      const isWeekend = day === 0 || day === 6;
      if (isWeekend) {
        isMarketOpen.value = false;
        sessionText.value = "休市（周末）";
        return;
      }
      if (minutes >= 570 && minutes < 690) {
        isMarketOpen.value = true;
        sessionText.value = "交易时段: 09:30-11:30";
      } else if (minutes >= 780 && minutes < 900) {
        isMarketOpen.value = true;
        sessionText.value = "交易时段: 13:00-15:00";
      } else if (minutes < 570) {
        isMarketOpen.value = false;
        sessionText.value = "未开盘";
      } else if (minutes < 780) {
        isMarketOpen.value = false;
        sessionText.value = "午间休市";
      } else {
        isMarketOpen.value = false;
        sessionText.value = "已收盘";
      }
    };

    // ---- 真实数据加载（失败时保留占位，不抛错） ----

    async function loadMarketIndices() {
      await Promise.all(
        marketIndices.value.map(async (item) => {
          try {
            const detail = await marketAPI.getIndexDetail(item.code);
            if (detail && detail.close != null) {
              item.value = Number(detail.close).toLocaleString("zh-CN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              });
            }
            if (detail && detail.pct_chg != null) {
              item.change = Number(detail.pct_chg);
            }
          } catch {
            /* 保留 "--" 占位 */
          }
        }),
      );
    }

    async function loadStrategyStatus() {
      try {
        const list = (await strategyAPI.getStrategies()) || [];
        const arr = Array.isArray(list) ? list : [];
        strategyStatus.value.total = arr.length;
        strategyStatus.value.running = arr.filter(
          (s) => s?.status === "running",
        ).length;
      } catch {
        /* 保留占位 */
      }
      try {
        const health = (await monitorAPI.getStrategyHealth()) || [];
        const arr = Array.isArray(health) ? health : [];
        const statuses = arr.map((h) => h?.status).filter(Boolean);
        if (statuses.includes("stop") || statuses.includes("danger")) {
          strategyStatus.value.health = "danger";
        } else if (statuses.includes("warning")) {
          strategyStatus.value.health = "warning";
        } else {
          strategyStatus.value.health = "healthy";
        }
      } catch {
        /* 保留占位 */
      }
    }

    // 从分页响应中防御性提取列表（兼容多种响应包裹）
    function pickList(res) {
      const items = res?.data?.items ?? res?.items ?? res?.data ?? res ?? [];
      return Array.isArray(items) ? items : [];
    }

    async function loadSignalStats() {
      try {
        const res = await tradeAPI.getSignals({ page: 1, page_size: 200 });
        const list = pickList(res);
        const today = new Date().toISOString().slice(0, 10);
        signalStats.value.today = list.filter((s) => {
          const t = s?.signal_time ?? s?.created_at ?? "";
          return String(t).slice(0, 10) === today;
        }).length;
        const triggered = new Set([
          "confirmed",
          "executed",
          "filled",
          "partial",
        ]);
        signalStats.value.triggered = list.filter((s) =>
          triggered.has(s?.signal_status ?? s?.status),
        ).length;
      } catch {
        /* 保留占位 */
      }
    }

    async function loadOrderStats() {
      try {
        const res = await tradeAPI.getOrders({ page_size: 200 });
        const list = pickList(res);
        const pending = new Set(["pending", "submitted", "partial"]);
        const executed = new Set(["filled", "executed", "done", "completed"]);
        orderStats.value.pending = list.filter((o) =>
          pending.has(o?.status ?? o?.order_status),
        ).length;
        orderStats.value.executed = list.filter((o) =>
          executed.has(o?.status ?? o?.order_status),
        ).length;
      } catch {
        /* 保留占位 */
      }
    }

    async function loadRiskLevel() {
      try {
        const metrics = await riskAPI.getRiskMetrics();
        const level = String(
          metrics?.overall_risk_level ?? "",
        ).toLowerCase();
        const map = {
          low: { class: "risk-low", text: "低" },
          medium: { class: "risk-medium", text: "中" },
          high: { class: "risk-high", text: "高" },
          低: { class: "risk-low", text: "低" },
          中: { class: "risk-medium", text: "中" },
          高: { class: "risk-high", text: "高" },
        };
        riskLevel.value = map[level] ?? { class: "risk-medium", text: "--" };
      } catch {
        /* 保留占位 */
      }
    }

    // 刷新全部真实数据
    const refreshAll = () => {
      loadMarketIndices();
      loadStrategyStatus();
      loadSignalStats();
      loadOrderStats();
      loadRiskLevel();
    };

    let timeInterval;
    let dataInterval;

    onMounted(() => {
      updateTime();
      updateSession();
      timeInterval = setInterval(() => {
        updateTime();
        updateSession();
      }, 1000);
      refreshAll();
      dataInterval = setInterval(refreshAll, 30000); // 每 30 秒刷新真实数据
    });

    onUnmounted(() => {
      if (timeInterval) clearInterval(timeInterval);
      if (dataInterval) clearInterval(dataInterval);
    });

    const handleCommand = (key) => {
      if (key === "logout") {
        router.push("/login");
      } else if (key === "profile") {
        router.push("/market/dashboard");
      }
    };

    return {
      formattedTime,
      formattedDate,
      marketIndices,
      isMarketOpen,
      sessionText,
      strategyStatus,
      signalStats,
      orderStats,
      riskLevel,
      userMenuOptions,
      handleCommand,
      getHealthText,
      getRiskDescription,
      getMarketChangeType,
      formatPct,
      userName,
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

.status-closed {
  background-color: var(--n-text-color-3);
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
