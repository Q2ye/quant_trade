<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, h } from "vue";
import { NTag, NButton, NProgress, NSpin, NResult } from "naive-ui";
import { useMessage } from "naive-ui";
import type { TradingSignal as Signal } from "@/types";

const message = useMessage();
const loading = ref(false);
const error = ref(false);

const signals = ref<Signal[]>([]);
const wsConnection = ref<WebSocket | null>(null);
const isConnecting = ref(false);
const reconnectAttempts = ref(0);
const maxReconnectAttempts = 5;
const reconnectTimer = ref<number | null>(null);

const WS_OPEN = WebSocket.OPEN;

const todaySignalsCount = computed(() => {
  const today = new Date().toDateString();
  return signals.value.filter(
    (s) => new Date(s.signal_time).toDateString() === today,
  ).length;
});

const getWebSocketUrl = (): string => {
  if (import.meta.env.VITE_APP_ENV === "development") {
    return `ws://localhost:8000/api/ws/signals`;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/signals`;
};

const signalTypeMap: Record<string, { color: string; text: string }> = {
  buy: { color: "#10B981", text: "买入" },
  sell: { color: "#EF4444", text: "卖出" },
  hold: { color: "#3B82F6", text: "持有" },
};

const getSignalTypeInfo = (signalType: string) => {
  return signalTypeMap[signalType] || { color: "#F59E0B", text: "未知" };
};

const columns = [
  {
    title: "信号时间",
    key: "signal_time",
    width: 180,
    render: (row: Signal) => new Date(row.signal_time).toLocaleString(),
  },
  {
    title: "策略",
    key: "strategy_id",
    width: 120,
    render: (row: Signal) =>
      h(NTag, { size: "small" }, { default: () => row.strategy_id || "--" }),
  },
  {
    title: "标的",
    key: "ts_code",
    width: 100,
    render: (row: Signal) => h("strong", {}, row.ts_code || row.symbol || "--"),
  },
  {
    title: "信号类型",
    key: "signal_type",
    width: 100,
    render: (row: Signal) => {
      const info = getSignalTypeInfo(row.signal_type);
      return h(
        NTag,
        { type: "info", color: { color: info.color, textColor: "#fff" } },
        { default: () => info.text },
      );
    },
  },
  {
    title: "触发价格",
    key: "current_price",
    width: 100,
    render: (row: Signal) => `¥${row.current_price?.toFixed(2) || "--"}`,
  },
  {
    title: "信号强度",
    key: "strength",
    width: 140,
    render: (row: Signal) => {
      const pct = Math.round((row.strength || 0) * 100);
      const color = pct > 70 ? "#10B981" : pct > 40 ? "#F59E0B" : "#EF4444";
      return h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h(NProgress, {
            type: "line",
            percentage: pct,
            showIndicator: false,
            height: 6,
            color,
            style: { width: "80px" },
          }),
          h("span", {}, `${pct}%`),
        ],
      );
    },
  },
  {
    title: "信号原因",
    key: "reason",
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row: Signal) => row.reason || "--",
  },
  {
    title: "操作",
    key: "action",
    width: 120,
    fixed: "right",
    render: (row: Signal) => {
      const isBuy = row.signal_type === "buy";
      return h(
        NButton,
        {
          size: "small",
          type: isBuy ? "success" : "error",
          onClick: () => handleQuickTrade(row),
        },
        {
          default: () =>
            isBuy
              ? "快速买入"
              : row.signal_type === "sell"
                ? "快速卖出"
                : "执行操作",
        },
      );
    },
  },
];

const rowClassName = (row: Signal) =>
  `signal-row-${row.signal_type || "default"}`;

const cleanupWebSocket = () => {
  if (wsConnection.value) {
    wsConnection.value.onopen = null;
    wsConnection.value.onmessage = null;
    wsConnection.value.onerror = null;
    wsConnection.value.onclose = null;
    if (wsConnection.value.readyState === WebSocket.OPEN) {
      wsConnection.value.close(1000, "正常关闭");
    }
    wsConnection.value = null;
  }
  if (reconnectTimer.value) {
    clearTimeout(reconnectTimer.value);
    reconnectTimer.value = null;
  }
  isConnecting.value = false;
};

const connectWebSocket = () => {
  if (isConnecting.value) return;
  try {
    cleanupWebSocket();
    const wsUrl = getWebSocketUrl();
    isConnecting.value = true;
    wsConnection.value = new WebSocket(wsUrl);

    wsConnection.value.onopen = () => {
      isConnecting.value = false;
      reconnectAttempts.value = 0;
      message.success("实时信号连接已建立");
    };

    wsConnection.value.onmessage = (event) => {
      try {
        const signalData = JSON.parse(event.data);
        if (!signalData.signal_type || !signalData.ts_code) return;
        const newSignal = {
          ...signalData,
          id: Date.now() + Math.random(),
          timestamp: new Date(),
          signal_time: signalData.signal_time || new Date().toISOString(),
          strength: signalData.strength || 0,
          current_price: signalData.current_price || 0,
        };
        signals.value.unshift(newSignal);
        if (signals.value.length > 100) {
          signals.value = signals.value.slice(0, 100);
        }
      } catch (parseError) {
        console.error("解析信号数据失败:", parseError, event.data);
      }
    };

    wsConnection.value.onerror = () => {
      isConnecting.value = false;
      if (reconnectAttempts.value === 0) {
        message.error("信号连接失败，正在重连...");
      }
    };

    wsConnection.value.onclose = (event) => {
      isConnecting.value = false;
      if (
        event.code !== 1000 &&
        reconnectAttempts.value < maxReconnectAttempts
      ) {
        reconnectAttempts.value++;
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttempts.value),
          30000,
        );
        reconnectTimer.value = Number(
          setTimeout(() => {
            connectWebSocket();
          }, delay),
        );
      } else if (reconnectAttempts.value >= maxReconnectAttempts) {
        message.warning("信号连接失败，请检查服务器状态");
      }
    };
  } catch (error) {
    console.error("WebSocket连接失败:", error);
    isConnecting.value = false;
    message.error("WebSocket连接失败");
  }
};

const manualReconnect = () => {
  reconnectAttempts.value = 0;
  connectWebSocket();
};

const handleQuickTrade = (signal: Signal) => {
  const symbol = signal.ts_code || signal.symbol || "unknown";
  window.open(
    `/trading?symbol=${encodeURIComponent(symbol)}&action=${signal.signal_type}`,
    "_blank",
  );
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    connectWebSocket();
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadData();
});

onUnmounted(() => {
  cleanupWebSocket();
});
</script>

<template>
  <div class="signal-monitor bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">实时信号监控</h1>
        </div>
        <div class="header-actions">
          <span class="signal-stat">今日信号: {{ todaySignalsCount }}</span>
          <span class="signal-stat">活跃策略: 12</span>
          <span class="signal-stat"
            >连接状态:
            <n-tag
              :type="wsConnection?.readyState === WS_OPEN ? 'success' : 'error'"
              size="small"
            >
              {{ wsConnection?.readyState === WS_OPEN ? "已连接" : "未连接" }}
            </n-tag>
          </span>
          <n-button
            v-if="wsConnection?.readyState !== WS_OPEN"
            @click="manualReconnect"
            size="small"
            :loading="isConnecting"
          >
            重新连接
          </n-button>
        </div>
      </div>
    </div>

    <n-spin :show="loading">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-data-table
          v-if="signals.length > 0"
          :columns="columns"
          :data="signals"
          :row-class-name="rowClassName"
          :max-height="600"
          :bordered="false"
          size="small"
        />

        <div v-else class="empty-state">
          <n-empty
            v-if="wsConnection?.readyState === WS_OPEN"
            description="等待接收实时信号..."
          />
          <n-empty v-else description="连接已断开，无法接收实时信号">
            <template #extra>
              <n-button @click="manualReconnect" :loading="isConnecting"
                >重新连接</n-button
              >
            </template>
          </n-empty>
        </div>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.signal-monitor {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.signal-stat {
  font-size: 13px;
  color: var(--n-text-color-2);
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

:deep(.signal-row-buy) {
  background-color: rgba(16, 185, 129, 0.05);
}

:deep(.signal-row-sell) {
  background-color: rgba(239, 68, 68, 0.05);
}

:deep(.signal-row-hold) {
  background-color: rgba(59, 130, 246, 0.05);
}

:deep(.signal-row-default) {
  background-color: rgba(245, 158, 11, 0.05);
}
</style>
