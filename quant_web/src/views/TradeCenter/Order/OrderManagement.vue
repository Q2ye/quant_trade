<script setup lang="ts">
import { ref, onMounted, computed, h } from "vue";
import { useMessage, NTag, NButton, NResult } from "naive-ui";

const message = useMessage();
interface Order {
  order_id: string;
  strategy_id?: string;
  ts_code: string;
  order_type: string;
  direction: string;
  price: number;
  volume: number;
  status: string;
  submitted_at: string;
  filled_volume?: number;
  filled_amount?: number;
}

const statusMap: Record<
  string,
  { text: string; type: "info" | "warning" | "success" | "default" | "error" }
> = {
  submitted: { text: "已报", type: "info" },
  partial_filled: { text: "部成", type: "warning" },
  filled: { text: "已成", type: "success" },
  cancelled: { text: "已撤", type: "default" },
  rejected: { text: "废单", type: "error" },
};

const orders = ref<Order[]>([]);
const filterStatus = ref("all");
const loading = ref(false);
const error = ref(false);

const statusOptions = [
  { label: "全部状态", value: "all" },
  { label: "已报", value: "submitted" },
  { label: "部成", value: "partial_filled" },
  { label: "已成", value: "filled" },
  { label: "已撤", value: "cancelled" },
];

const columns = [
  { title: "订单ID", key: "order_id", width: 140 },
  {
    title: "策略ID",
    key: "strategy_id",
    width: 120,
    render: (row: Order) => row.strategy_id || "手动",
  },
  { title: "标的代码", key: "ts_code", width: 100 },
  {
    title: "方向",
    key: "direction",
    width: 80,
    render: (row: Order) =>
      h(
        NTag,
        { type: row.direction === "buy" ? "success" : "error", size: "small" },
        { default: () => (row.direction === "buy" ? "买入" : "卖出") },
      ),
  },
  {
    title: "类型",
    key: "order_type",
    width: 80,
    render: (row: Order) => (row.order_type === "limit" ? "限价" : "市价"),
  },
  {
    title: "价格",
    key: "price",
    width: 100,
    render: (row: Order) =>
      row.price > 0 ? `¥${row.price.toFixed(2)}` : "市价",
  },
  { title: "数量", key: "volume", width: 100 },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row: Order) =>
      h(
        NTag,
        { type: statusMap[row.status]?.type || "default" },
        { default: () => statusMap[row.status]?.text },
      ),
  },
  { title: "提交时间", key: "submitted_at", width: 180 },
  {
    title: "操作",
    key: "op",
    width: 120,
    render: (row: Order) =>
      row.status === "submitted" || row.status === "partial_filled"
        ? h(
            NButton,
            { size: "small", type: "error", onClick: () => cancelOrder(row) },
            { default: () => "撤单" },
          )
        : h("span", { style: { color: "var(--n-text-color-3)" } }, "--"),
  },
];

const fetchOrders = async () => {
  loading.value = true;
  try {
    orders.value = [
      {
        order_id: "O20240115001",
        strategy_id: "ma_cross_001",
        ts_code: "600519.SH",
        order_type: "limit",
        direction: "buy",
        price: 1850.0,
        volume: 100,
        status: "submitted",
        submitted_at: "2024-01-15 14:30:00",
      },
      {
        order_id: "O20240115002",
        ts_code: "000858.SZ",
        order_type: "market",
        direction: "sell",
        price: 0,
        volume: 200,
        status: "filled",
        submitted_at: "2024-01-15 10:15:00",
        filled_volume: 200,
        filled_amount: 31000,
      },
    ];
    error.value = false;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const cancelOrder = async (order: Order) => {
  order.status = "cancelled";
  message.success("撤单请求已发送");
};

const batchCancel = async () => {
  const pendingOrders = orders.value.filter((o) => o.status === "submitted");
  if (pendingOrders.length === 0) {
    message.warning("没有可撤单的订单");
    return;
  }
  pendingOrders.forEach((o) => (o.status = "cancelled"));
  message.success(`已撤销 ${pendingOrders.length} 个订单`);
};

const filteredOrders = computed(() =>
  filterStatus.value === "all"
    ? orders.value
    : orders.value.filter((o) => o.status === filterStatus.value),
);

onMounted(() => fetchOrders());
</script>

<template>
  <div class="order-management bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">订单管理</h1>
        </div>
        <div class="header-actions">
          <n-select v-model:value="filterStatus" style="width: 120px" :options="statusOptions" />
          <n-button @click="batchCancel" type="warning">批量撤单</n-button>
          <n-button @click="fetchOrders">刷新</n-button>
        </div>
      </div>
    </div>

    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取订单列表失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="fetchOrders">重试</n-button></template
      >
    </n-result>
    <n-spin v-else :show="loading">
      <n-empty v-if="filteredOrders.length === 0" description="暂无订单" />
      <n-data-table
        v-else
        :columns="columns"
        :data="filteredOrders"
        :bordered="false"
        size="small"
      />
    </n-spin>
  </div>
</template>

<style scoped>
.order-management {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}
</style>
