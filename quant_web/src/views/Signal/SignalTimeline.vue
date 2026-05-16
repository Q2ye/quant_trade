<script setup lang="ts">
import { ref, computed } from "vue";
import {
  NTag,
  NButton,
  NSelect,
  NInput,
  NResult,
  NSpin,
  NEmpty,
} from "naive-ui";
import { Icon } from "@iconify/vue";

interface Signal {
  symbol: string;
  type: string;
  time: string;
  price?: number;
  volume?: number;
  strength?: number;
  reason?: string;
}

const props = defineProps<{
  signals: Signal[];
}>();

const loading = ref(false);
const error = ref(false);

const filters = ref({
  type: [] as string[],
  timeRange: "today",
  symbol: "",
});

const signalTypeOptions = [
  { label: "买入", value: "buy" },
  { label: "卖出", value: "sell" },
  { label: "持有", value: "hold" },
];

const timeRangeOptions = [
  { label: "最近1小时", value: "1h" },
  { label: "今天", value: "today" },
  { label: "本周", value: "week" },
  { label: "全部", value: "all" },
];

const signalTypeMap: Record<
  string,
  { type: "success" | "error" | "warning"; label: string }
> = {
  buy: { type: "success", label: "买入" },
  sell: { type: "error", label: "卖出" },
  hold: { type: "warning", label: "持有" },
};

const signalIconMap: Record<string, string> = {
  buy: "ant-design:arrow-up-outlined",
  sell: "ant-design:arrow-down-outlined",
  hold: "ant-design:pause-outlined",
};

const filteredSignals = computed(() => {
  let result = [...props.signals];

  if (filters.value.type.length > 0) {
    result = result.filter((s) => filters.value.type.includes(s.type));
  }

  if (filters.value.symbol) {
    const sym = filters.value.symbol.toUpperCase();
    result = result.filter((s) => s.symbol.includes(sym));
  }

  const now = new Date();
  switch (filters.value.timeRange) {
    case "1h": {
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
      result = result.filter((s) => new Date(s.time) >= oneHourAgo);
      break;
    }
    case "today": {
      const todayStart = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
      );
      result = result.filter((s) => new Date(s.time) >= todayStart);
      break;
    }
    case "week": {
      const weekStart = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      result = result.filter((s) => new Date(s.time) >= weekStart);
      break;
    }
  }

  return result.sort(
    (a, b) => new Date(b.time).getTime() - new Date(a.time).getTime(),
  );
});

const formatTime = (time: string) =>
  new Date(time).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

const clearFilters = () => {
  filters.value = { type: [], timeRange: "today", symbol: "" };
};
</script>

<template>
  <div class="signal-timeline bg-gradient-mesh bg-noise">
    <div class="timeline-header">
      <h3>信号时间线</h3>
      <div class="filter-controls">
        <div class="filter-group">
          <label>信号类型:</label>
          <n-select
            v-model:value="filters.type"
            :options="signalTypeOptions"
            multiple
            size="small"
            style="width: 160px"
            placeholder="选择信号类型"
          />
        </div>

        <div class="filter-group">
          <label>时间范围:</label>
          <n-select
            v-model:value="filters.timeRange"
            :options="timeRangeOptions"
            size="small"
            style="width: 140px"
          />
        </div>

        <div class="filter-group">
          <label>股票代码:</label>
          <n-input
            v-model:value="filters.symbol"
            placeholder="输入股票代码"
            size="small"
            style="width: 160px"
            clearable
          />
        </div>

        <n-button size="small" @click="clearFilters">清除筛选</n-button>
      </div>
    </div>

    <div class="timeline-content">
      <n-spin :show="loading">
        <n-result
          v-if="error"
          status="500"
          title="数据加载失败"
          description="请检查网络连接后重试"
          size="small"
        />

        <n-empty
          v-else-if="filteredSignals.length === 0"
          description="暂无信号数据"
        />

        <div v-else class="signal-list">
          <div
            v-for="(signal, index) in filteredSignals"
            :key="index"
            class="signal-item"
            :class="signal.type"
          >
            <div class="signal-icon">
              <Icon
                :icon="
                  signalIconMap[signal.type] ||
                  'ant-design:question-circle-outlined'
                "
              />
            </div>

            <div class="signal-content">
              <div class="signal-header">
                <div class="signal-title">
                  <span class="signal-symbol">{{ signal.symbol }}</span>
                  <n-tag
                    :type="signalTypeMap[signal.type]?.type || 'default'"
                    size="small"
                  >
                    {{ signalTypeMap[signal.type]?.label || "未知" }}
                  </n-tag>
                </div>
                <div class="signal-time">{{ formatTime(signal.time) }}</div>
              </div>

              <div
                v-if="signal.price || signal.volume || signal.strength"
                class="signal-details"
              >
                <div v-if="signal.price" class="signal-detail">
                  <Icon icon="ant-design:tag-outlined" />
                  <span>价格: {{ signal.price }}元</span>
                </div>
                <div v-if="signal.volume" class="signal-detail">
                  <Icon icon="ant-design:bar-chart-outlined" />
                  <span>数量: {{ signal.volume }}股</span>
                </div>
                <div v-if="signal.strength" class="signal-detail">
                  <Icon icon="ant-design:dashboard-outlined" />
                  <span>强度: {{ (signal.strength * 100).toFixed(1) }}%</span>
                </div>
              </div>

              <div v-if="signal.reason" class="signal-reason">
                <Icon icon="ant-design:message-outlined" /> {{ signal.reason }}
              </div>
            </div>
          </div>
        </div>
      </n-spin>
    </div>
  </div>
</template>

<style scoped>
.signal-timeline {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  overflow: hidden;
  background-color: var(--n-card-color);
}

.timeline-header {
  padding: 12px 15px;
  background: var(--n-color-embedded);
  border-bottom: 1px solid var(--n-border-color);
}

.timeline-header h3 {
  margin: 0 0 10px;
  color: var(--n-text-color-1);
  font-size: 16px;
}

.filter-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-group label {
  font-size: 12px;
  color: var(--n-text-color-3);
  white-space: nowrap;
}

.timeline-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.signal-list {
  display: flex;
  flex-direction: column;
}

.signal-item {
  display: flex;
  margin-bottom: 15px;
  position: relative;
  padding-left: 30px;
}

.signal-item::before {
  content: "";
  position: absolute;
  left: 15px;
  top: 25px;
  bottom: -15px;
  width: 2px;
  background: var(--n-border-color);
}

.signal-item:last-child::before {
  display: none;
}

.signal-icon {
  position: absolute;
  left: 0;
  top: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  font-size: 14px;
}

.signal-item.buy .signal-icon {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.signal-item.sell .signal-icon {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.signal-item.hold .signal-icon {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.signal-content {
  flex: 1;
  background: var(--n-color-embedded);
  border-radius: 4px;
  padding: 10px 12px;
  border-left: 3px solid transparent;
}

.signal-item.buy .signal-content {
  border-left-color: #10b981;
}

.signal-item.sell .signal-content {
  border-left-color: #ef4444;
}

.signal-item.hold .signal-content {
  border-left-color: #f59e0b;
}

.signal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.signal-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.signal-symbol {
  font-weight: bold;
  color: var(--n-text-color-1);
}

.signal-time {
  font-size: 11px;
  color: var(--n-text-color-3);
}

.signal-details {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

.signal-detail {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--n-text-color-2);
}

.signal-reason {
  padding: 6px 8px;
  background: var(--n-color-hover);
  border-radius: 3px;
  font-size: 12px;
  color: var(--n-text-color-2);
}

@media (max-width: 768px) {
  .filter-controls {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-group {
    width: 100%;
  }

  .signal-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .signal-time {
    margin-top: 4px;
  }
}
</style>
