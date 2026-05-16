<template>
  <div class="position bg-gradient-mesh bg-noise">
    <n-card>
      <template #header>
        <div class="card-header">
          <span>当前持仓</span>
          <n-button text @click="refreshPositions">刷新</n-button>
        </div>
      </template>

      <n-spin :show="loading">
        <n-result
          v-if="error"
          status="500"
          title="数据加载失败"
          description="请检查网络连接后重试"
        >
          <template #footer>
            <n-button type="primary" @click="loadPositions">重试</n-button>
          </template>
        </n-result>

        <n-data-table
          v-else
          :columns="columns"
          :data="positions"
          :bordered="false"
          size="small"
          :max-height="500"
        />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { useMessage, NButton, NSpin, NResult } from "naive-ui";

const emit = defineEmits<{ trade: [data: any] }>();
const message = useMessage();
const loading = ref(false);
const error = ref(false);

const positions = ref([
  {
    symbol: "600519.SH",
    name: "贵州茅台",
    quantity: 200,
    costPrice: 1700.25,
    currentPrice: 1850.5,
    change: 0.028,
    marketValue: 370100.0,
    pnl: 30050.0,
    pnlRatio: 0.088,
  },
  {
    symbol: "000858.SZ",
    name: "五粮液",
    quantity: 500,
    costPrice: 165.8,
    currentPrice: 172.3,
    change: 0.015,
    marketValue: 86150.0,
    pnl: 3250.0,
    pnlRatio: 0.039,
  },
  {
    symbol: "601318.SH",
    name: "中国平安",
    quantity: 1000,
    costPrice: 48.75,
    currentPrice: 50.2,
    change: 0.012,
    marketValue: 50200.0,
    pnl: 1450.0,
    pnlRatio: 0.03,
  },
]);

const columns = [
  { title: "代码", key: "symbol", width: 100 },
  { title: "名称", key: "name", width: 120 },
  { title: "数量", key: "quantity", width: 100, align: "right" },
  {
    title: "成本价",
    key: "costPrice",
    width: 120,
    align: "right",
    render: (row: any) => row.costPrice.toFixed(2),
  },
  {
    title: "当前价",
    key: "currentPrice",
    width: 120,
    align: "right",
    render: (row: any) =>
      h(
        "span",
        { style: { color: row.change >= 0 ? "#f56c6c" : "#67c23a" } },
        row.currentPrice.toFixed(2),
      ),
  },
  {
    title: "涨跌幅",
    key: "change",
    width: 120,
    align: "right",
    render: (row: any) =>
      h(
        "span",
        { style: { color: row.change >= 0 ? "#f56c6c" : "#67c23a" } },
        `${(row.change * 100).toFixed(2)}%`,
      ),
  },
  {
    title: "市值",
    key: "marketValue",
    width: 120,
    align: "right",
    render: (row: any) => row.marketValue.toFixed(2),
  },
  {
    title: "浮动盈亏",
    key: "pnl",
    width: 150,
    align: "right",
    render: (row: any) =>
      h(
        "span",
        { style: { color: row.pnl >= 0 ? "#f56c6c" : "#67c23a" } },
        `${row.pnl.toFixed(2)} (${(row.pnlRatio * 100).toFixed(2)}%)`,
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 120,
    render: (row: any) =>
      row.quantity > 0
        ? h(
            NButton,
            { size: "small", type: "error", onClick: () => handleSell(row) },
            { default: () => "卖出" },
          )
        : null,
  },
];

const loadPositions = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const refreshPositions = () =>
  loadPositions().then(() => message.success("持仓数据已刷新"));

const handleSell = (position: any) =>
  emit("trade", {
    symbol: position.symbol,
    name: position.name,
    price: position.currentPrice,
    defaultQuantity: -Math.min(100, position.quantity),
  });

onMounted(() => loadPositions());
</script>

<style scoped>
.position {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
