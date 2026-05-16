<template>
  <div class="signal-table">
    <div class="toolbar">
      <NInput
        v-model:value="searchText"
        placeholder="搜索股票代码/名称"
        clearable
        size="small"
        style="width: 200px; margin-right: 10px"
      />

      <NSelect
        v-model:value="filterStatus"
        :options="statusOptions"
        placeholder="信号状态"
        clearable
        size="small"
        style="width: 120px; margin-right: 10px"
      />

      <NSelect
        v-model:value="filterDirection"
        :options="directionOptions"
        placeholder="交易方向"
        clearable
        size="small"
        style="width: 100px"
      />

      <NButton
        type="error"
        size="small"
        style="margin-left: auto"
        @click="clearExpired"
      >
        清除过期信号
      </NButton>
    </div>

    <NDataTable
      :data="filteredSignals"
      :columns="columns"
      :max-height="500"
      :bordered="false"
      :single-line="false"
      @update:checked-row-keys="
        (keys: any[]) => {
          if (keys.length) handleRowClick(keys[0]);
        }
      "
    />

    <div class="pagination">
      <NPagination
        :page="currentPage"
        :page-size="pageSize"
        :item-count="totalSignals"
        @update:page="(p: number) => (currentPage = p)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h } from "vue";
import {
  NInput,
  NSelect,
  NButton,
  NDataTable,
  NPagination,
  NProgress,
  NTag,
} from "naive-ui";
import type { DataTableColumn } from "naive-ui";

interface Signal {
  id: number;
  symbol: string;
  name: string;
  direction: string;
  strength: number;
  price: number;
  triggerTime: string;
  status: string;
  lastPrice: number;
  change: number;
}

const props = withDefaults(
  defineProps<{
    signals?: Signal[];
  }>(),
  {
    signals: () => [],
  },
);

const emit = defineEmits<{
  "row-click": [row: Signal];
  trade: [signal: Signal];
  dismiss: [signal: Signal];
  "clear-expired": [];
}>();

const searchText = ref("");
const filterStatus = ref("");
const filterDirection = ref("");
const currentPage = ref(1);
const pageSize = ref(15);

const statusOptions = [
  { label: "待交易", value: "PENDING" },
  { label: "已确认", value: "CONFIRMED" },
  { label: "已过期", value: "EXPIRED" },
];

const directionOptions = [
  { label: "买入", value: "BUY" },
  { label: "卖出", value: "SELL" },
];

const demoSignals: Signal[] = [
  {
    id: 1,
    symbol: "600519.SH",
    name: "贵州茅台",
    direction: "BUY",
    strength: 92,
    price: 1850.5,
    triggerTime: "2023-08-12 10:15:23",
    status: "PENDING",
    lastPrice: 1850.5,
    change: 1.25,
  },
  {
    id: 2,
    symbol: "000858.SZ",
    name: "五粮液",
    direction: "BUY",
    strength: 85,
    price: 172.8,
    triggerTime: "2023-08-12 09:42:11",
    status: "PENDING",
    lastPrice: 172.8,
    change: 2.15,
  },
  {
    id: 3,
    symbol: "601318.SH",
    name: "中国平安",
    direction: "SELL",
    strength: 78,
    price: 48.25,
    triggerTime: "2023-08-11 14:28:45",
    status: "CONFIRMED",
    lastPrice: 48.25,
    change: -0.82,
  },
  {
    id: 4,
    symbol: "600036.SH",
    name: "招商银行",
    direction: "BUY",
    strength: 65,
    price: 32.6,
    triggerTime: "2023-08-11 11:15:30",
    status: "EXPIRED",
    lastPrice: 32.6,
    change: -0.35,
  },
  {
    id: 5,
    symbol: "300750.SZ",
    name: "宁德时代",
    direction: "BUY",
    strength: 88,
    price: 232.8,
    triggerTime: "2023-08-10 13:45:22",
    status: "PENDING",
    lastPrice: 232.8,
    change: 3.25,
  },
];

const signalsData = ref<Signal[]>([...demoSignals, ...props.signals]);

const filteredList = computed(() => {
  return signalsData.value.filter((signal) => {
    const matchesSearch =
      !searchText.value ||
      signal.symbol.includes(searchText.value) ||
      signal.name.includes(searchText.value);
    const matchesStatus =
      !filterStatus.value || signal.status === filterStatus.value;
    const matchesDirection =
      !filterDirection.value || signal.direction === filterDirection.value;
    return matchesSearch && matchesStatus && matchesDirection;
  });
});

const filteredSignals = computed(() => {
  return filteredList.value.slice(
    (currentPage.value - 1) * pageSize.value,
    currentPage.value * pageSize.value,
  );
});

const totalSignals = computed(() => filteredList.value.length);

const getStrengthColor = (strength: number) => {
  if (strength > 90) return "#f56c6c";
  if (strength > 80) return "#e6a23c";
  if (strength > 70) return "#5cb87a";
  return "#909399";
};

const getStatusTagType = (status: string) => {
  const m: Record<string, "warning" | "success" | "info"> = {
    PENDING: "warning",
    CONFIRMED: "success",
    EXPIRED: "info",
  };
  return m[status] || "error";
};

const getStatusText = (status: string) => {
  const m: Record<string, string> = {
    PENDING: "待交易",
    CONFIRMED: "已确认",
    EXPIRED: "已过期",
  };
  return m[status] || status;
};

const columns: DataTableColumn<any>[] = [
  { key: "symbol", title: "代码", width: 80 },
  { key: "name", title: "名称", width: 120 },
  {
    key: "direction",
    title: "方向",
    width: 80,
    render: (row: Signal) =>
      h(
        "span",
        { class: row.direction === "BUY" ? "buy" : "sell" },
        row.direction === "BUY" ? "买入" : "卖出",
      ),
  },
  {
    key: "strength",
    title: "信号强度",
    width: 100,
    render: (row: Signal) =>
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "4px" } },
        [
          h(NProgress, {
            percentage: row.strength,
            color: getStrengthColor(row.strength),
            showIndicator: false,
          }),
          h("span", { class: "strength-value" }, `${row.strength}%`),
        ],
      ),
  },
  {
    key: "price",
    title: "触发价格",
    width: 100,
    render: (row: Signal) => row.price.toFixed(2),
  },
  { key: "triggerTime", title: "触发时间", width: 160 },
  {
    key: "status",
    title: "状态",
    width: 100,
    render: (row: Signal) =>
      h(
        NTag,
        { type: getStatusTagType(row.status), size: "small" },
        { default: () => getStatusText(row.status) },
      ),
  },
  {
    key: "actions",
    title: "操作",
    width: 120,
    render: (row: Signal) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        row.status === "PENDING"
          ? h(
              NButton,
              {
                size: "tiny",
                type: "primary",
                onClick: (e: Event) => {
                  e.stopPropagation();
                  confirmTrade(row);
                },
              },
              { default: () => "交易" },
            )
          : null,
        row.status === "PENDING"
          ? h(
              NButton,
              {
                size: "tiny",
                type: "error",
                onClick: (e: Event) => {
                  e.stopPropagation();
                  dismissSignal(row);
                },
              },
              { default: () => "忽略" },
            )
          : null,
      ]),
  },
];

const handleRowClick = (row: Signal) => {
  emit("row-click", row);
};
const confirmTrade = (signal: Signal) => {
  emit("trade", signal);
};

const dismissSignal = (signal: Signal) => {
  const index = signalsData.value.findIndex((s) => s.id === signal.id);
  if (index !== -1) {
    signalsData.value[index].status = "EXPIRED";
    emit("dismiss", signal);
  }
};

const clearExpired = () => {
  signalsData.value = signalsData.value.filter((s) => s.status !== "EXPIRED");
  emit("clear-expired");
};
</script>

<style scoped>
.signal-table {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.toolbar {
  margin-bottom: 15px;
  display: flex;
}

:deep(.buy) {
  color: #f56c6c;
  font-weight: bold;
}
:deep(.sell) {
  color: #5cb87a;
  font-weight: bold;
}

.strength-value {
  font-size: 12px;
  color: var(--n-text-color-2);
}

.pagination {
  margin-top: 15px;
  display: flex;
  justify-content: center;
}
</style>
