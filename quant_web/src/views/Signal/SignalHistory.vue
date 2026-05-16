<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { NTag, NButton, NSpin, NEmpty } from "naive-ui";
import { useMessage } from "naive-ui";
import type { TradingSignal as Signal } from "@/types/entities/trading";

const message = useMessage();
const signals = ref<Signal[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

const filterParams = ref({
  startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).getTime(),
  endDate: Date.now(),
  signalType: null as string | null,
});

const signalTypeOptions = [
  { label: "买入", value: "buy" },
  { label: "卖出", value: "sell" },
  { label: "持有", value: "hold" },
];

const mockSignals: Signal[] = [
  {
    id: "1",
    strategy_id: "ma_cross_001",
    ts_code: "600519.SH",
    symbol: "600519",
    name: "贵州茅台",
    signal_type: "buy",
    signal_time: "2024-01-15 14:30:00",
    current_price: 1850.5,
    strength: 0.85,
    reason: "双均线金叉买入信号",
    confidence: 0.92,
    status: "executed",
  },
  {
    id: "2",
    strategy_id: "rsi_strategy",
    ts_code: "000858.SZ",
    symbol: "000858",
    name: "五粮液",
    signal_type: "sell",
    signal_time: "2024-01-15 10:15:00",
    current_price: 152.3,
    strength: 0.72,
    reason: "RSI超卖区域卖出",
    confidence: 0.85,
    status: "executed",
  },
];

const columns = [
  {
    title: "信号时间",
    key: "signal_time",
    width: 180,
    render: (row: Signal) => new Date(row.signal_time).toLocaleString(),
  },
  { title: "策略ID", key: "strategy_id", width: 150 },
  { title: "股票代码", key: "ts_code", width: 120 },
  {
    title: "信号类型",
    key: "signal_type",
    width: 100,
    render: (row: Signal) => {
      const isBuy = row.signal_type === "buy";
      const isSell = row.signal_type === "sell";
      return h(
        NTag,
        {
          type: isBuy ? "success" : isSell ? "error" : "info",
          size: "small",
        },
        { default: () => (isBuy ? "买入" : isSell ? "卖出" : "持有") },
      );
    },
  },
  {
    title: "触发价格",
    key: "current_price",
    width: 120,
    render: (row: Signal) => `¥${row.current_price?.toFixed(2)}`,
  },
  {
    title: "信号强度",
    key: "strength",
    width: 120,
    render: (row: Signal) => `${Math.round((row.strength || 0) * 100)}%`,
  },
  {
    title: "信号原因",
    key: "reason",
    minWidth: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: "后续表现",
    key: "performance",
    width: 120,
    render: () => h("span", { style: { color: "#10B981" } }, "+2.5%"),
  },
];

const fetchSignalHistory = async () => {
  loading.value = true;
  error.value = null;
  try {
    signals.value = mockSignals.filter((signal) => {
      const d = new Date(signal.signal_time).getTime();
      return (
        d >= filterParams.value.startDate && d <= filterParams.value.endDate
      );
    });
  } catch (err) {
    error.value = "获取历史信号失败";
    message.error("获取历史信号失败");
  } finally {
    loading.value = false;
  }
};

const exportSignals = () => {
  const csvContent = signals.value
    .map(
      (s: Signal) =>
        `${s.strategy_id},${s.ts_code},${s.signal_type},${s.signal_time},${s.current_price},${s.strength},"${s.reason}"`,
    )
    .join("\n");
  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `signals_${new Date().toISOString().split("T")[0]}.csv`;
  a.click();
  window.URL.revokeObjectURL(url);
};

onMounted(() => {
  fetchSignalHistory();
});
</script>

<template>
  <div class="signal-history bg-gradient-mesh bg-noise">
    <div class="history-header">
      <h3>历史信号分析</h3>
      <div class="filter-controls">
        <n-date-picker
          v-model:value="filterParams.startDate"
          type="date"
          placeholder="开始日期"
          style="width: 150px"
          value-format="yyyy-MM-dd"
        />
        <n-date-picker
          v-model:value="filterParams.endDate"
          type="date"
          placeholder="结束日期"
          style="width: 150px"
          value-format="yyyy-MM-dd"
        />
        <n-select
          v-model:value="filterParams.signalType"
          placeholder="信号类型"
          clearable
          style="width: 120px"
          :options="signalTypeOptions"
        />
        <n-button type="primary" @click="fetchSignalHistory">查询</n-button>
        <n-button @click="exportSignals">导出CSV</n-button>
      </div>
    </div>

    <!-- Loading -->
    <n-spin v-if="loading" class="table-spin" />

    <!-- Error -->
    <n-empty v-else-if="error" description="数据加载失败">
      <template #extra>
        <n-button size="small" @click="fetchSignalHistory">重试</n-button>
      </template>
    </n-empty>

    <!-- Empty -->
    <n-empty v-else-if="signals.length === 0" description="暂无信号数据" />

    <!-- Data -->
    <n-data-table
      v-else
      :columns="columns"
      :data="signals"
      :bordered="false"
      size="small"
    />
  </div>
</template>

<style scoped>
.signal-history {
  padding: 20px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}

.history-header h3 {
  margin: 0;
  color: var(--n-text-color-1);
}

.filter-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.table-spin {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}
</style>
