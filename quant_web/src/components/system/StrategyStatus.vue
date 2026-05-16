<script setup lang="ts">
import { computed } from "vue";
import { NTag, NButton, NTooltip } from "naive-ui";

interface Strategy {
  id: string;
  name: string;
  status: "running" | "stopped" | "error" | "paused";
  type: string;
  symbols: string[];
  startedAt: string;
  performance?: {
    dailyReturn: number;
    totalReturn: number;
    sharpeRatio: number;
  };
}

interface Props {
  strategies?: Strategy[];
}

const props = withDefaults(defineProps<Props>(), {
  strategies: () => [],
});

const emit = defineEmits<{
  stopStrategy: [id: string];
  startStrategy: [id: string];
  viewDetails: [id: string];
}>();

const safeStrategies = computed(() => {
  if (!props.strategies || !Array.isArray(props.strategies)) {
    return [];
  }
  return props.strategies.filter((s) => s && typeof s === "object" && s.id);
});

const statusMap: Record<
  string,
  { type: "success" | "info" | "error" | "warning" | "default"; text: string }
> = {
  running: { type: "success", text: "运行中" },
  stopped: { type: "default", text: "已停止" },
  error: { type: "error", text: "错误" },
  paused: { type: "warning", text: "暂停" },
};

const formatTime = (time: string) => {
  try {
    return new Date(time).toLocaleString();
  } catch {
    return "无效时间";
  }
};

const formatReturn = (value: number | undefined) => {
  if (value === undefined || value === null) return "0.00%";
  return `${(value * 100).toFixed(2)}%`;
};

const handleStop = (strategy: Strategy) => {
  if (strategy?.status === "running") emit("stopStrategy", strategy.id);
};

const handleStart = (strategy: Strategy) => {
  if (strategy?.status === "stopped") emit("startStrategy", strategy.id);
};

const handleViewDetails = (strategy: Strategy) => {
  if (strategy) emit("viewDetails", strategy.id);
};

const getStrategySymbols = (symbols: string[] | undefined) => {
  if (!symbols || !Array.isArray(symbols) || symbols.length === 0)
    return "无标的";
  return symbols.join(", ");
};
</script>

<template>
  <div class="strategy-status">
    <div
      v-for="strategy in safeStrategies"
      :key="strategy.id"
      class="strategy-item"
    >
      <div class="strategy-header">
        <div class="strategy-info">
          <span class="strategy-name">{{ strategy.name || "未知策略" }}</span>
          <NTag
            :type="statusMap[strategy.status]?.type || 'default'"
            size="small"
          >
            {{ statusMap[strategy.status]?.text || "未知状态" }}
          </NTag>
        </div>
        <div class="strategy-actions">
          <NTooltip>
            <template #trigger>
              <NButton size="tiny" text @click="handleViewDetails(strategy)"
                >详情</NButton
              >
            </template>
            查看详情
          </NTooltip>
          <NButton
            v-if="strategy.status === 'running'"
            size="tiny"
            type="error"
            text
            @click="handleStop(strategy)"
          >
            停止
          </NButton>
          <NButton
            v-else-if="strategy.status === 'stopped'"
            size="tiny"
            type="primary"
            text
            @click="handleStart(strategy)"
          >
            启动
          </NButton>
        </div>
      </div>

      <div class="strategy-details">
        <div class="detail-item">
          <span class="detail-label">类型:</span>
          <span class="detail-value">{{ strategy.type || "未知类型" }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">标的:</span>
          <span class="detail-value">{{
            getStrategySymbols(strategy.symbols)
          }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">启动时间:</span>
          <span class="detail-value">{{ formatTime(strategy.startedAt) }}</span>
        </div>

        <div v-if="strategy.performance" class="performance-metrics">
          <div class="metric-item">
            <span class="metric-label">日收益:</span>
            <span
              class="metric-value"
              :class="{
                positive: strategy.performance.dailyReturn > 0,
                negative: strategy.performance.dailyReturn < 0,
              }"
            >
              {{ formatReturn(strategy.performance.dailyReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">总收益:</span>
            <span
              class="metric-value"
              :class="{
                positive: strategy.performance.totalReturn > 0,
                negative: strategy.performance.totalReturn < 0,
              }"
            >
              {{ formatReturn(strategy.performance.totalReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">夏普比率:</span>
            <span class="metric-value">{{
              strategy.performance.sharpeRatio?.toFixed(2) || "0.00"
            }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="safeStrategies.length === 0" class="empty-state">
      暂无运行中的策略
    </div>
  </div>
</template>

<style scoped>
.strategy-status {
  max-height: 300px;
  overflow-y: auto;
}

.strategy-item {
  padding: 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  margin-bottom: 8px;
  background: var(--n-card-color);
}

.strategy-item:last-child {
  margin-bottom: 0;
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.strategy-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-name {
  font-weight: 500;
  color: var(--n-text-color-1);
}

.strategy-actions {
  display: flex;
  gap: 4px;
}

.strategy-details {
  font-size: 12px;
}

.detail-item {
  display: flex;
  margin-bottom: 4px;
}

.detail-label {
  color: var(--n-text-color-3);
  min-width: 60px;
}

.detail-value {
  color: var(--n-text-color-1);
  flex: 1;
}

.performance-metrics {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--n-border-color);
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.metric-label {
  font-size: 11px;
  color: var(--n-text-color-3);
  margin-bottom: 2px;
}

.metric-value {
  font-size: 12px;
  font-weight: 500;
  font-family: "Courier New", monospace;
}

.positive {
  color: #f56c6c;
}

.negative {
  color: #67c23a;
}

.empty-state {
  text-align: center;
  color: var(--n-text-color-3);
  padding: 20px;
}
</style>
