<script setup lang="ts">
import { ref, computed } from "vue";
import { NTabs, NTabPane, NDataTable } from "naive-ui";

interface LogEntry {
  time: string;
  level: string;
  message: string;
}

interface SignalEntry {
  id: number;
  time: string;
  symbol: string;
  type: string;
  price: number;
}

const activeTab = ref("logs");

const logs = ref<LogEntry[]>([
  { time: "09:30:05", level: "info", message: "策略初始化完成" },
  {
    time: "09:35:22",
    level: "trade",
    message: "买入 600519.SH @1800.50 数量:100",
  },
  { time: "10:15:47", level: "warning", message: "波动率超过阈值" },
]);

const variables = ref<Record<string, any>>({
  security: "600519.SH",
  short_ma: 1795.34,
  long_ma: 1782.15,
  position: 100,
  cash: 24567.89,
  portfolio_value: 180245.67,
});

const signals = ref<SignalEntry[]>([
  { id: 1, time: "09:35:22", symbol: "600519.SH", type: "buy", price: 1800.5 },
  { id: 2, time: "10:15:47", symbol: "000001.SZ", type: "sell", price: 14.8 },
  { id: 3, time: "11:20:15", symbol: "600036.SH", type: "buy", price: 35.25 },
]);

const variableColumns = [
  { title: "变量名", key: "name", width: 120 },
  { title: "值", key: "value" },
  { title: "类型", key: "type", width: 80 },
];

const variableData = computed(() =>
  Object.entries(variables.value).map(([key, val]) => ({
    name: key,
    value: typeof val === "number" ? val.toFixed(2) : String(val),
    type: typeof val,
  })),
);

const logLevelClass = (level: string) => ({
  "log-info": level === "info",
  "log-trade": level === "trade",
  "log-warning": level === "warning",
  "log-error": level === "error",
});

const signalTypeText = (type: string) =>
  type === "buy" ? "买入信号" : "卖出信号";
</script>

<template>
  <div class="variable-monitor">
    <n-tabs v-model:value="activeTab" type="line" size="small">
      <n-tab-pane name="logs" tab="运行日志" />
      <n-tab-pane name="variables" tab="变量监控" />
      <n-tab-pane name="signals" tab="信号时间轴" />
    </n-tabs>

    <div class="tab-content">
      <div v-if="activeTab === 'logs'" class="log-container">
        <div v-for="(log, index) in logs" :key="index" class="log-item">
          <span class="log-time">[{{ log.time }}]</span>
          <span :class="['log-message', logLevelClass(log.level)]">
            {{ log.message }}
          </span>
        </div>
      </div>

      <div v-if="activeTab === 'variables'" class="variables-container">
        <n-data-table
          :columns="variableColumns"
          :data="variableData"
          :bordered="false"
          size="small"
        />
      </div>

      <div v-if="activeTab === 'signals'" class="signals-container">
        <div class="signal-timeline">
          <div
            v-for="signal in signals"
            :key="signal.id"
            class="signal-event"
            :class="signal.type"
          >
            <div class="signal-time">{{ signal.time }}</div>
            <div class="signal-info">
              <span class="signal-symbol">{{ signal.symbol }}</span>
              <span class="signal-type">{{ signalTypeText(signal.type) }}</span>
              <span class="signal-price">{{ signal.price.toFixed(2) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.variable-monitor {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  font-size: 12px;
}

.tab-content {
  flex: 1;
  overflow: auto;
  padding: 5px;
  background-color: #f8f8f8;
}

.log-container {
  display: flex;
  flex-direction: column;
}

.log-item {
  padding: 5px 3px;
  border-bottom: 1px solid #eee;
  line-height: 1.4;
}

.log-time {
  color: #909399;
  margin-right: 8px;
}

.log-message {
  font-family: "Consolas", monospace;
}

.log-info {
  color: #606266;
}
.log-trade {
  color: #67c23a;
  font-weight: bold;
}
.log-warning {
  color: #e6a23c;
}
.log-error {
  color: #f56c6c;
  font-weight: bold;
}

.signal-event {
  padding: 8px 5px;
  border-left: 3px solid;
  margin-bottom: 8px;
  background-color: white;
}

.buy {
  border-left-color: #f56c6c;
}
.sell {
  border-left-color: #67c23a;
}

.signal-time {
  color: #909399;
  font-size: 11px;
  margin-bottom: 3px;
}

.signal-info {
  display: flex;
  gap: 10px;
}

.signal-symbol {
  font-weight: bold;
}
</style>
