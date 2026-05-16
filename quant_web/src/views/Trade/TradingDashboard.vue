<template>
  <div class="trading-dashboard bg-gradient-mesh bg-noise">
    <ParticleBackground />
    <div class="dashboard-header">
      <h2>交易驾驶舱</h2>
      <div class="account-info">
        <span>总资产: {{ formatCurrency(account.totalAsset) }}</span>
        <span>可用资金: {{ formatCurrency(account.availableCash) }}</span>
        <span>持仓市值: {{ formatCurrency(account.marketValue) }}</span>
      </div>
    </div>

    <!-- Loading -->
    <template v-if="pageState === 'loading'">
      <n-grid :x-gap="20" :cols="24">
        <n-grid-item v-for="i in 3" :key="i" :span="8">
          <n-card><n-skeleton :text="true" :repeat="4" /></n-card>
        </n-grid-item>
      </n-grid>
    </template>

    <!-- Error -->
    <n-result
      v-else-if="pageState === 'error'"
      status="500"
      title="数据加载失败"
      description="请检查网络连接后重试"
    >
      <template #footer>
        <n-button type="primary" @click="loadDashboardData">重试</n-button>
      </template>
    </n-result>

    <!-- Empty -->
    <n-empty
      v-else-if="pageState === 'empty'"
      description="暂无数据，请先选择交易标的"
    />

    <!-- Data -->
    <template v-else>
      <n-grid :x-gap="20" :cols="24">
        <n-grid-item :span="8">
          <n-card class="order-panel">
            <template #header><span>快速下单</span></template>
            <OrderForm
              :symbol="selectedSymbol"
              @order-submit="handleOrderSubmit"
            />
          </n-card>

          <n-card class="order-list-panel">
            <template #header>
              <div class="card-header">
                <span>当前委托</span>
                <n-button size="small" @click="refreshOrders">刷新</n-button>
              </div>
            </template>
            <OrderList
              :orders="pendingOrders"
              @cancel-order="handleCancelOrder"
            />
          </n-card>
        </n-grid-item>

        <n-grid-item :span="10">
          <n-card class="chart-panel">
            <template #header>
              <div class="card-header">
                <span>K线图表 - {{ selectedSymbol || "请选择标的" }}</span>
                <n-select
                  v-model:value="chartPeriod"
                  size="small"
                  style="width: 100px"
                  :options="periodOptions"
                />
              </div>
            </template>
            <KLineChart
              :symbol="selectedSymbol"
              :period="chartPeriod"
              @chart-click="handleChartClick"
              @data-loaded="handleKLineDataLoaded"
            />
          </n-card>
        </n-grid-item>

        <n-grid-item :span="6">
          <n-card class="market-depth-panel">
            <template #header><span>深度行情</span></template>
            <MarketDepth :symbol="selectedSymbol" />
          </n-card>

          <n-card class="position-panel">
            <template #header><span>持仓列表</span></template>
            <PositionList
              :positions="positions"
              @select-symbol="setSelectedSymbol"
            />
          </n-card>
        </n-grid-item>
      </n-grid>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineAsyncComponent } from "vue";
const ParticleBackground = defineAsyncComponent(
  () => import("@/components/three/ParticleBackground.vue"),
);
import OrderForm from "@/components/trade/OrderForm.vue";
import OrderList from "@/components/trade/OrderList.vue";
import KLineChart from "@/components/charts/KLineChart.vue";
import MarketDepth from "@/components/market/MarketDepth.vue";
import PositionList from "@/components/trade/PositionList.vue";

const pageState = ref<"loading" | "error" | "empty" | "data">("data");
const selectedSymbol = ref("600519.SH");
const chartPeriod = ref("5min");
const periodOptions = [
  { label: "1分", value: "1min" },
  { label: "5分", value: "5min" },
  { label: "日线", value: "daily" },
];

const account = ref({
  totalAsset: 1000000,
  availableCash: 350000,
  marketValue: 650000,
});

const pendingOrders = ref<any[]>([
  {
    id: "O1001",
    symbol: "600519.SH",
    direction: "buy" as const,
    type: "limit",
    price: 1800,
    volume: 100,
    status: "submitted",
  },
  {
    id: "O1002",
    symbol: "000858.SZ",
    direction: "sell" as const,
    type: "market",
    price: null,
    volume: 200,
    status: "submitted",
  },
]);

const positions = ref([
  {
    symbol: "600519.SH",
    name: "贵州茅台",
    volume: 100,
    costPrice: 1750,
    currentPrice: 1850,
  },
  {
    symbol: "000858.SZ",
    name: "五粮液",
    volume: 200,
    costPrice: 150,
    currentPrice: 155,
  },
]);

const formatCurrency = (value: number) => `¥${value.toLocaleString("zh-CN")}`;

const handleOrderSubmit = (order: any) =>
  pendingOrders.value.push({
    id: `O${Date.now()}`,
    ...order,
    status: "submitted",
  });
const handleCancelOrder = (orderId: string) => {
  pendingOrders.value = pendingOrders.value.filter((o) => o.id !== orderId);
};
const refreshOrders = () => {};
const setSelectedSymbol = (symbol: string) => {
  selectedSymbol.value = symbol;
};
const handleChartClick = (data: any) => {};
const handleKLineDataLoaded = (data: any) => {};

const loadDashboardData = async () => {
  pageState.value = "loading";
  try {
    await new Promise((resolve) => setTimeout(resolve, 800));
    pageState.value = "data";
  } catch {
    pageState.value = "error";
  }
};

onMounted(() => {
  loadDashboardData();
});
</script>

<style scoped>
.trading-dashboard {
  padding: 20px;
  background-color: var(--n-body-color);
  min-height: 100vh;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 10px 20px;
  background: var(--n-card-color);
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
.dashboard-header h2 {
  margin: 0;
  color: var(--n-text-color-1);
}

.account-info {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: var(--n-text-color-2);
}

.order-panel,
.order-list-panel,
.chart-panel,
.market-depth-panel,
.position-panel {
  margin-bottom: 20px;
}
.chart-panel {
  min-height: 500px;
}
.market-depth-panel {
  height: 300px;
}
.position-panel {
  height: 300px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
