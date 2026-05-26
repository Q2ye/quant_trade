<script setup lang="ts">
import { ref, onMounted, computed, h } from "vue";
import { useMessage, NButton, NResult } from "naive-ui";

const message = useMessage();
interface Position {
  id: number;
  ts_code: string;
  name: string;
  volume: number;
  available_volume: number;
  cost_price: number;
  current_price: number;
  market_value: number;
  profit_loss: number;
  profit_loss_ratio: number;
  last_update: string;
}

const positions = ref<Position[]>([]);
const loading = ref(false);
const error = ref(false);

const totalStats = computed(() => {
  const totalMV = positions.value.reduce((s, p) => s + p.market_value, 0);
  const totalPL = positions.value.reduce((s, p) => s + p.profit_loss, 0);
  const totalCost = positions.value.reduce(
    (s, p) => s + p.cost_price * p.volume,
    0,
  );
  return {
    totalMarketValue: totalMV,
    totalProfitLoss: totalPL,
    totalProfitLossRatio: totalCost > 0 ? (totalPL / totalCost) * 100 : 0,
  };
});

const columns = [
  { title: "股票代码", key: "ts_code", width: 100 },
  { title: "股票名称", key: "name", width: 120 },
  {
    title: "持仓数量",
    key: "volume",
    width: 100,
    render: (row: Position) => row.volume.toLocaleString(),
  },
  {
    title: "可用数量",
    key: "available_volume",
    width: 100,
    render: (row: Position) => row.available_volume.toLocaleString(),
  },
  {
    title: "成本价",
    key: "cost_price",
    width: 100,
    render: (row: Position) => `¥${row.cost_price.toFixed(2)}`,
  },
  {
    title: "当前价",
    key: "current_price",
    width: 100,
    render: (row: Position) => `¥${row.current_price.toFixed(2)}`,
  },
  {
    title: "市值",
    key: "market_value",
    width: 120,
    render: (row: Position) => `¥${row.market_value.toLocaleString()}`,
  },
  {
    title: "浮动盈亏",
    key: "profit_loss",
    width: 120,
    render: (row: Position) =>
      h(
        "span",
        { class: row.profit_loss >= 0 ? "positive" : "negative" },
        `¥${row.profit_loss.toLocaleString()}`,
      ),
  },
  {
    title: "盈亏比例",
    key: "profit_loss_ratio",
    width: 100,
    render: (row: Position) =>
      h(
        "span",
        { class: row.profit_loss_ratio >= 0 ? "positive" : "negative" },
        `${row.profit_loss_ratio.toFixed(2)}%`,
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 100,
    render: (row: Position) =>
      h(
        NButton,
        { size: "small", type: "error", onClick: () => closePosition(row) },
        { default: () => "平仓" },
      ),
  },
];

const fetchPositions = async () => {
  loading.value = true;
  try {
    positions.value = [
      {
        id: 1,
        ts_code: "600519.SH",
        name: "贵州茅台",
        volume: 100,
        available_volume: 100,
        cost_price: 1750.0,
        current_price: 1850.5,
        market_value: 185050,
        profit_loss: 10050,
        profit_loss_ratio: 5.74,
        last_update: "2024-01-15 15:00:00",
      },
      {
        id: 2,
        ts_code: "000858.SZ",
        name: "五粮液",
        volume: 500,
        available_volume: 500,
        cost_price: 148.0,
        current_price: 152.3,
        market_value: 76150,
        profit_loss: 2150,
        profit_loss_ratio: 2.91,
        last_update: "2024-01-15 15:00:00",
      },
    ];
    error.value = false;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const closePosition = async (position: Position) =>
  message.info(`平仓操作: ${position.name} ${position.volume}股`);
const refreshPositions = async () => {
  await fetchPositions();
  message.success("持仓信息已刷新");
};

onMounted(() => fetchPositions());
</script>

<template>
  <div class="position-management bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">持仓管理</h1>
        </div>
        <div class="header-actions">
          <span>持仓市值: ¥{{ totalStats.totalMarketValue.toLocaleString() }}</span>
          <span :class="totalStats.totalProfitLoss >= 0 ? 'positive' : 'negative'">
            总盈亏: ¥{{ totalStats.totalProfitLoss.toLocaleString() }} ({{ totalStats.totalProfitLossRatio.toFixed(2) }}%)
          </span>
          <n-button @click="refreshPositions">刷新</n-button>
        </div>
      </div>
    </div>

    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取持仓列表失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="fetchPositions">重试</n-button></template
      >
    </n-result>
    <n-spin v-else :show="loading">
      <n-empty v-if="positions.length === 0" description="暂无持仓" />
      <n-data-table
        v-else
        :columns="columns"
        :data="positions"
        :bordered="false"
        size="small"
      />
    </n-spin>
  </div>
</template>

<style scoped>
.position-management {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.positive {
  color: #67c23a;
}
.negative {
  color: #f56c6c;
}
</style>
