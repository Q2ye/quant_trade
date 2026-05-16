<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";
import { NSelect, NSwitch, NButton } from "naive-ui";
import { useWebSocket } from "@/composables/useWebSocket";

interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "warning" | "error" | "debug";
  message: string;
  source: string;
}

const logs = ref<LogEntry[]>([]);
const autoScroll = ref(true);
const { subscribe, unsubscribe } = useWebSocket();

const logContainer = ref<HTMLDivElement>();

const addLog = (entry: LogEntry) => {
  logs.value.push(entry);
  if (logs.value.length > 1000) {
    logs.value = logs.value.slice(-500);
  }
  if (autoScroll.value) {
    nextTick(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight;
      }
    });
  }
};

const clearLogs = () => {
  logs.value = [];
};

const exportLogs = () => {
  const content = logs.value
    .map(
      (log) =>
        `[${log.timestamp}] [${log.level.toUpperCase()}] [${log.source}] ${log.message}`,
    )
    .join("\n");
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `strategy-logs-${new Date().toISOString().slice(0, 10)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
};

const filterLevel = ref<"all" | "info" | "warning" | "error">("all");
const levelOptions = [
  { label: "全部", value: "all" },
  { label: "信息", value: "info" },
  { label: "警告", value: "warning" },
  { label: "错误", value: "error" },
];

const filteredLogs = computed(() => {
  if (filterLevel.value === "all") return logs.value;
  return logs.value.filter((log) => log.level === filterLevel.value);
});

const getLevelStyle = (level: string) => {
  switch (level) {
    case "error":
      return { color: "#f56c6c", background: "#fef0f0" };
    case "warning":
      return { color: "#e6a23c", background: "#fdf6ec" };
    case "info":
      return { color: "#409eff", background: "#f0f9ff" };
    case "debug":
      return { color: "#909399", background: "#f4f4f5" };
    default:
      return { color: "#606266", background: "#f4f4f5" };
  }
};

onMounted(() => {
  subscribe("strategy_logs", (data: LogEntry) => {
    addLog(data);
  });
  subscribe("backtest_logs", (data: LogEntry) => {
    addLog(data);
  });
});

onUnmounted(() => {
  unsubscribe("strategy_logs");
  unsubscribe("backtest_logs");
});
</script>

<template>
  <div class="live-feedback-panel">
    <div class="panel-header">
      <h3>实时日志</h3>
      <div class="header-controls">
        <NSelect
          v-model:value="filterLevel"
          :options="levelOptions"
          size="small"
          style="width: 100px"
        />

        <NSwitch v-model:value="autoScroll" size="small" />
        <span class="switch-label">自动滚动</span>

        <NButton size="small" @click="clearLogs">清空</NButton>
        <NButton size="small" @click="exportLogs">导出</NButton>
      </div>
    </div>

    <div ref="logContainer" class="log-container">
      <div
        v-for="log in filteredLogs"
        :key="log.id"
        class="log-entry"
        :style="getLevelStyle(log.level)"
      >
        <span class="timestamp">{{
          new Date(log.timestamp).toLocaleTimeString()
        }}</span>
        <span class="level-badge" :class="log.level">{{
          log.level.toUpperCase()
        }}</span>
        <span class="source">[{{ log.source }}]</span>
        <span class="message">{{ log.message }}</span>
      </div>

      <div v-if="filteredLogs.length === 0" class="empty-logs">
        暂无日志信息
      </div>
    </div>

    <div class="panel-footer">
      <span class="log-count">共 {{ logs.length }} 条日志</span>
      <span v-if="filterLevel !== 'all'" class="filter-count">
        (过滤后: {{ filteredLogs.length }} 条)
      </span>
    </div>
  </div>
</template>

<style scoped>
.live-feedback-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--n-body-color);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--n-border-color);
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.switch-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.log-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  font-family: "Courier New", monospace;
  font-size: 12px;
  line-height: 1.4;
}

.log-entry {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  margin-bottom: 2px;
  border-radius: 3px;
  border-left: 3px solid;
}

.timestamp {
  color: var(--n-text-color-3);
  margin-right: 8px;
  min-width: 80px;
}

.level-badge {
  padding: 1px 4px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: bold;
  margin-right: 8px;
  min-width: 40px;
  text-align: center;
  color: white;
}

.level-badge.error {
  background: #f56c6c;
}
.level-badge.warning {
  background: #e6a23c;
}
.level-badge.info {
  background: #409eff;
}
.level-badge.debug {
  background: #909399;
}

.source {
  color: var(--n-text-color-3);
  margin-right: 8px;
  min-width: 80px;
}

.message {
  flex: 1;
  word-break: break-all;
}

.empty-logs {
  text-align: center;
  color: var(--n-text-color-3);
  padding: 40px;
}

.panel-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--n-border-color);
  font-size: 12px;
  color: var(--n-text-color-3);
}

.log-count {
  margin-right: 8px;
}
</style>
