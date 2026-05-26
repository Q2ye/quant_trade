<template>
  <div class="trading-dashboard bg-gradient-mesh bg-noise">
    <ParticleBackground />
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">交易驾驶舱</h1>
        </div>
        <div class="header-actions">
          <n-button size="small" text class="workspace-btn" @click="router.push('/trade/workspace')">
            <template #icon><SmartIcon name="Grid" /></template>
            工作台
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Error -->
      <n-result
        v-if="pageState === 'error'"
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

      <!-- Data (always rendered, loading overlays via n-spin) -->
      <template v-else>
        <!-- Row 1: three equal cards -->
        <n-spin :show="pageState === 'loading'" class="row-spin">
          <n-grid :x-gap="16" :y-gap="16" :cols="24" class="top-row">
          <!-- Account Overview -->
          <n-grid-item :span="8">
            <n-card class="overview-card">
              <template #header>
                <div class="card-header-row">
                  <SmartIcon name="Wallet" class="card-header-icon" />
                  <span>账户概览</span>
                  <n-select
                    v-model:value="selectedAccountId"
                    size="tiny"
                    style="width: 130px; margin-left: auto"
                    :options="accountOptions"
                  />
                </div>
              </template>
              <div class="account-summary">
                <div class="account-stat-row">
                  <span class="stat-label">总资产</span>
                  <span class="stat-value">¥{{ accountStats.totalAsset.toLocaleString() }}</span>
                </div>
                <div class="account-stat-row">
                  <span class="stat-label">可用资金</span>
                  <span class="stat-value">¥{{ accountStats.availableCash.toLocaleString() }}</span>
                </div>
                <div class="account-stat-row">
                  <span class="stat-label">持仓市值</span>
                  <span class="stat-value">¥{{ accountStats.marketValue.toLocaleString() }}</span>
                </div>
                <div class="account-divider" />
                <div class="account-stat-row">
                  <span class="stat-label">当日盈亏</span>
                  <span class="stat-value" :class="dailyPnl >= 0 ? 'text-up' : 'text-down'">
                    {{ dailyPnl >= 0 ? '+' : '' }}¥{{ dailyPnl.toLocaleString() }}
                  </span>
                </div>
                <div class="account-stat-row">
                  <span class="stat-label">当日收益率</span>
                  <span class="stat-value" :class="dailyPnlRatio >= 0 ? 'text-up' : 'text-down'">
                    {{ dailyPnlRatio >= 0 ? '+' : '' }}{{ dailyPnlRatio.toFixed(2) }}%
                  </span>
                </div>
              </div>
              <div v-if="positions.length > 0" class="mini-holdings">
                <div class="holdings-title">持仓概览</div>
                <div
                  v-for="p in positions.slice(0, 3)"
                  :key="p.symbol"
                  class="mini-holding"
                  @click="setSelectedSymbol(p.symbol)"
                >
                  <span class="mini-name">{{ p.name }}</span>
                  <span
                    class="mini-pnl"
                    :class="(p.currentPrice - p.costPrice) >= 0 ? 'text-up' : 'text-down'"
                  >
                    {{ (((p.currentPrice - p.costPrice) / p.costPrice) * 100).toFixed(1) }}%
                  </span>
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <!-- Signal Flow -->
          <n-grid-item :span="8">
            <n-card class="signal-card">
              <template #header>
                <div class="card-header-row">
                  <SmartIcon name="Lightning" class="card-header-icon" />
                  <span>实时信号流</span>
                  <n-tag size="tiny" type="success" :bordered="false" round>
                    {{ signalCount }} 条
                  </n-tag>
                </div>
              </template>
              <div v-if="signals.length === 0" class="card-empty">
                <n-empty description="暂无交易信号" size="small" />
              </div>
              <div v-else class="signal-list">
                <div
                  v-for="s in signals"
                  :key="s.id"
                  class="signal-item"
                  :class="{ 'signal-selected': s.symbol === selectedSymbol }"
                  @click="handleSignalClick(s)"
                >
                  <div class="signal-top">
                    <n-tag
                      size="tiny"
                      :type="s.direction === 'buy' ? 'success' : 'error'"
                      :bordered="false"
                    >
                      {{ s.direction === 'buy' ? '买' : '卖' }}
                    </n-tag>
                    <span class="signal-stock">{{ s.symbolName }}</span>
                    <span class="signal-time">{{ s.time }}</span>
                  </div>
                  <div class="signal-bottom">
                    <span class="signal-strategy">{{ s.strategy }}</span>
                    <span
                      class="signal-strength"
                      :class="s.strength >= 0.7 ? 'text-up' : 'text-secondary'"
                    >
                      强度 {{ (s.strength * 100).toFixed(0) }}%
                    </span>
                  </div>
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <!-- Risk Indicators -->
          <n-grid-item :span="8">
            <n-card class="risk-card">
              <template #header>
                <div class="card-header-row">
                  <SmartIcon name="ShieldCheckmark" class="card-header-icon" />
                  <span>关键风险指标</span>
                  <n-button size="tiny" text @click="router.push('/risk/monitor')">
                    风控
                    <template #icon><SmartIcon name="ChevronRight" /></template>
                  </n-button>
                </div>
              </template>
              <div class="risk-grid">
                <div class="risk-item">
                  <span class="risk-label">VaR (95%)</span>
                  <span class="risk-value">¥{{ riskIndicators.var95.toLocaleString() }}</span>
                </div>
                <div class="risk-item">
                  <span class="risk-label">最大回撤</span>
                  <span class="risk-value text-down">{{ (riskIndicators.maxDrawdown * 100).toFixed(1) }}%</span>
                </div>
                <div class="risk-item">
                  <span class="risk-label">行业集中度</span>
                  <span class="risk-value">{{ (riskIndicators.concentration * 100).toFixed(0) }}%</span>
                </div>
                <div class="risk-item">
                  <span class="risk-label">杠杆率</span>
                  <span class="risk-value">{{ (riskIndicators.leverage * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-spin>

      <!-- Row 2: Chart + Order sidebar -->
      <n-spin :show="pageState === 'loading'" class="row-spin">
        <n-grid :x-gap="16" :cols="24" class="bottom-row">
          <n-grid-item :span="18">
            <n-card class="chart-card">
              <template #header>
                <div class="card-header-row">
                  <span>K线图表 — {{ selectedSymbol || "请选择标的" }}</span>
                  <n-select
                    v-model:value="chartPeriod"
                    size="tiny"
                    style="width: 90px"
                    :options="periodOptions"
                  />
                </div>
              </template>
              <div class="chart-wrapper">
                <KLineChart
                  :symbol="selectedSymbol"
                  :period="chartPeriod"
                  @chart-click="handleChartClick"
                  @data-loaded="handleKLineDataLoaded"
                />
              </div>
            </n-card>
          </n-grid-item>

          <n-grid-item :span="6">
            <n-card class="order-card">
              <template #header>
                <div class="card-header-row">
                  <SmartIcon name="Cart" class="card-header-icon" />
                  <span>快速下单</span>
                </div>
              </template>
              <OrderForm
                :initial-symbol="selectedSymbol"
                :initial-side="routeSide"
                :initial-direction="prefillDirection"
                @preview-order="handleOrderPreview"
              />
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-spin>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, defineAsyncComponent } from "vue";
import { useRouter, useRoute } from "vue-router";
import { NCard, NButton, NTag, NSelect, NSpin, NResult, NEmpty, NGrid, NGridItem, useMessage } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import OrderForm from "@/components/trade/OrderForm.vue";
import KLineChart from "@/components/charts/KLineChart.vue";

const ParticleBackground = defineAsyncComponent(
  () => import("@/components/three/ParticleBackground.vue"),
);

const router = useRouter();
const route = useRoute();
const message = useMessage();

// ============================================================
// Route query → cross-page linking from Workspace
// ============================================================
const routeSymbol = computed(() => (route.query.symbol as string) || "");
const routeSide = computed(() => (route.query.side as "buy" | "sell") || undefined);

// ============================================================
// State
// ============================================================
const pageState = ref<"loading" | "error" | "empty" | "data">("loading");
const selectedSymbol = ref("600519.SH");
const chartPeriod = ref("daily");
const periodOptions = [
  { label: "1分", value: "1min" },
  { label: "5分", value: "5min" },
  { label: "日线", value: "daily" },
];

// ============================================================
// Account
// ============================================================
const selectedAccountId = ref("1");
const accounts = ref([
  { id: 1, account_name: "主交易账户", broker: "华泰证券", total_asset: 1000000, available_cash: 350000, market_value: 650000, account_number: "A0001" },
] as any[]);
const accountOptions = computed(() =>
  accounts.value.map((a: any) => ({ label: a.account_name, value: String(a.id) })),
);
const accountStats = computed(() => {
  const acc = accounts.value.find((a: any) => String(a.id) === selectedAccountId.value);
  return {
    totalAsset: acc?.total_asset ?? 0,
    availableCash: acc?.available_cash ?? 0,
    marketValue: acc?.market_value ?? 0,
  };
});
const dailyPnl = ref(12580);
const dailyPnlRatio = ref(1.28);

// ============================================================
// Positions
// ============================================================
const positions = ref([
  { symbol: "600519.SH", name: "贵州茅台", volume: 100, costPrice: 1750, currentPrice: 1850 },
  { symbol: "000858.SZ", name: "五粮液", volume: 200, costPrice: 150, currentPrice: 155 },
  { symbol: "300750.SZ", name: "宁德时代", volume: 300, costPrice: 210, currentPrice: 205 },
]);

// ============================================================
// Signal flow
// ============================================================
const signals = ref([
  { id: "S01", symbol: "600519.SH", symbolName: "贵州茅台", direction: "buy", strategy: "均线突破", strength: 0.85, time: "09:35:12" },
  { id: "S02", symbol: "000858.SZ", symbolName: "五粮液", direction: "sell", strategy: "RSI背离", strength: 0.72, time: "09:38:04" },
  { id: "S03", symbol: "601318.SH", symbolName: "中国平安", direction: "buy", strategy: "量价共振", strength: 0.91, time: "09:41:22" },
  { id: "S04", symbol: "300750.SZ", symbolName: "宁德时代", direction: "sell", strategy: "MACD死叉", strength: 0.63, time: "09:45:08" },
  { id: "S05", symbol: "600036.SH", symbolName: "招商银行", direction: "buy", strategy: "突破回踩", strength: 0.78, time: "09:50:15" },
]);
const signalCount = computed(() => signals.value.length);

// Signal click → prefill order form
const prefillDirection = ref<"buy" | "sell" | undefined>(undefined);

const handleSignalClick = (s: any) => {
  setSelectedSymbol(s.symbol);
  prefillDirection.value = s.direction as "buy" | "sell";
};

// ============================================================
// Risk indicators
// ============================================================
const riskIndicators = ref({
  var95: 23500,
  maxDrawdown: 0.068,
  concentration: 0.42,
  leverage: 0.65,
});

// ============================================================
// Actions
// ============================================================
const setSelectedSymbol = (symbol: string) => {
  selectedSymbol.value = symbol;
};

const handleOrderPreview = (order: any) => {
  message.info(
    `预览订单: ${order.name} ${order.direction} ${order.quantity}股 ` +
    `${order.type} ${typeof order.price === 'number' ? '¥' + order.price : order.price} ` +
    `金额 ¥${order.amount.toLocaleString()}`
  );
};
const handleChartClick = (data: any) => { /* future: set order price */ };
const handleKLineDataLoaded = (data: any) => {};

const loadDashboardData = async () => {
  pageState.value = "loading";
  try {
    await new Promise((resolve) => setTimeout(resolve, 600));
    if (routeSymbol.value) {
      selectedSymbol.value = routeSymbol.value;
    }
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
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

/* ============================================================
   Row spacing
   ============================================================ */
.row-spin {
  margin-bottom: 16px;
}
.top-row {
  align-items: stretch;
  align-items: stretch;

  :deep(.n-card) {
    height: 100%;
  }
}
.bottom-row {
  margin-bottom: 16px;

  :deep(.n-card) {
    height: 100%;
  }
}

/* ============================================================
   Card header
   ============================================================ */
.card-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-header-icon {
  font-size: 16px;
  color: var(--n-primary-color);
}
.card-empty {
  padding: 20px 0;
}

.workspace-btn {
  padding: 0 12px;
}

/* ============================================================
   Account overview
   ============================================================ */
.account-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.account-stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}
.stat-label {
  font-size: 13px;
  color: var(--n-text-color-3);
}
.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1);
  font-variant-numeric: tabular-nums;
}
.account-divider {
  height: 1px;
  background: var(--n-divider-color);
  margin: 4px 0;
}

.mini-holdings {
  margin-top: 12px;
}
.holdings-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color-3);
  margin-bottom: 6px;
}
.mini-holding {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}
.mini-holding:hover {
  background: rgba(68, 138, 255, 0.08);
}
.mini-name {
  font-size: 12px;
  color: var(--n-text-color-2);
}
.mini-pnl {
  font-size: 12px;
  font-weight: 500;
}

/* ============================================================
   Signal flow
   ============================================================ */
.signal-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.signal-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.04);
  transition: background 0.15s;
}
.signal-item:hover {
  background: rgba(68, 138, 255, 0.06);
  border-color: rgba(68, 138, 255, 0.15);
}
.signal-selected {
  background: rgba(68, 138, 255, 0.12) !important;
  border-color: rgba(68, 138, 255, 0.35) !important;
}
.signal-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.signal-stock {
  font-size: 13px;
  font-weight: 500;
  color: var(--n-text-color-1);
  flex: 1;
}
.signal-time {
  font-size: 11px;
  color: var(--n-text-color-3);
  font-family: monospace;
}
.signal-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.signal-strategy {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.signal-strength {
  font-size: 11px;
  font-weight: 500;
}

/* ============================================================
   Risk indicators
   ============================================================ */
.risk-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.risk-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px;
  border-radius: 6px;
  background: rgba(255,255,255,0.02);
}
.risk-label {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.risk-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
  font-variant-numeric: tabular-nums;
}

/* ============================================================
   Chart + Order
   ============================================================ */
:deep(.chart-card .n-card__content) {
  padding: 8px;
}
.chart-wrapper {
  width: 100%;
  height: 420px;
}
:deep(.order-card .n-card__content) {
  padding: 12px;
}

/* ============================================================
   Responsive
   ============================================================ */
@media (max-width: 1024px) {
  .top-row :deep(.n-grid-item),
  .bottom-row :deep(.n-grid-item) {
    grid-column: span 24;
  }
}
</style>
