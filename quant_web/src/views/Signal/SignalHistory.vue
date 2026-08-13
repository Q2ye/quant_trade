<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { NTag, NButton, NSpin, NEmpty } from "naive-ui";
import { useMessage } from "naive-ui";
import type { TradingSignal as Signal } from "@/types";
import signalsAPI from "@/api/signals";
import SignalTraceModal from "@/components/trade/SignalTraceModal.vue";

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

const columns = [
  {
    title: "信号时间",
    key: "signal_time",
    width: 150,
    // 修复: new Date().toLocaleString() 受浏览器时区/locale 影响 + 格式与其它页不一致；
    // 统一为 ISO 字符串 slice（+08 本地时间），与 SignalMonitor/Confirm 一致
    render: (row: Signal) => (row.signal_time || "").toString().slice(0, 16).replace("T", " ") || "--",
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
  // v3.4: 操作列（追溯链路）
  {
    title: "操作",
    key: "actions",
    width: 90,
    render: (row: any) =>
      h(NButton, { size: "tiny", quaternary: true, onClick: () => openTrace(row) }, { default: () => "追溯" }),
  },
];

// v3.4: 信号链路追溯
const showTrace = ref(false);
const traceSignalId = ref("");
const openTrace = (row: any) => {
  traceSignalId.value = row.signal_id || row.id;
  showTrace.value = true;
};

const fetchSignalHistory = async () => {
  loading.value = true;
  error.value = null;
  try {
    const res = await signalsAPI.getSignals({
      start_time: new Date(filterParams.value.startDate).toISOString(),
      end_time: new Date(filterParams.value.endDate).toISOString(),
      signal_type: filterParams.value.signalType as any,
    });
    const items = (res as any)?.items ?? (Array.isArray(res) ? res : []);
    signals.value = items.map((s: any) => ({
      ...s,
      id: s.id ?? s.signal_id ?? "",
      current_price: s.current_price ?? s.price ?? 0,
      strength: s.strength ?? s.confidence ?? 0,
    }));
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
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">历史信号分析</h1>
        </div>
        <div class="header-actions">
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

    <!-- v3.4: 信号链路追溯 -->
    <SignalTraceModal
      :show="showTrace"
      :signal-id="traceSignalId"
      @update:show="showTrace = $event"
    />
  </div>
</template>

<style scoped>
.signal-history {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.table-spin {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}
</style>
