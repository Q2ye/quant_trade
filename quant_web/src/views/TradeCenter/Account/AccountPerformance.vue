<script setup lang="ts">
import { ref, reactive, onMounted, computed, h } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import {
  NCard,
  NSelect,
  NDatePicker,
  NDataTable,
  NTabs,
  NTabPane,
  NGrid,
  NGridItem,
  NStatistic,
  NSpace,
  NSpin,
  NResult,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";

interface PerformanceData {
  date: string;
  total_asset: number;
  cash: number;
  market_value: number;
  daily_pnl: number;
  daily_return: number;
  cumulative_return: number;
}

interface Position {
  symbol: string;
  name: string;
  volume: number;
  cost_price: number;
  current_price: number;
  market_value: number;
  pnl: number;
  pnl_ratio: number;
  weight: number;
}

const loading = ref(false);
const router = useRouter();
const error = ref(false);
const performanceData = ref<PerformanceData[]>([]);
const positions = ref<Position[]>([]);
const dateRange = ref<[string, string] | null>(null);
const selectedPeriod = ref("1m");

const periodOptions = [
  { label: "近1周", value: "1w" },
  { label: "近1月", value: "1m" },
  { label: "近3月", value: "3m" },
  { label: "近1年", value: "1y" },
  { label: "全部", value: "all" },
];

const performanceMetrics = reactive({
  totalReturn: 0.156,
  annualizedReturn: 0.234,
  sharpeRatio: 1.89,
  maxDrawdown: -0.089,
  volatility: 0.156,
  winRate: 0.712,
});

const positionColumns: DataTableColumns<Position> = [
  {
    title: "代码",
    key: "symbol",
    width: 100,
  },
  {
    title: "名称",
    key: "name",
    width: 120,
  },
  {
    title: "持仓数量",
    key: "volume",
    width: 100,
    render: (row) => row.volume?.toLocaleString() || "0",
  },
  {
    title: "成本价",
    key: "cost_price",
    width: 100,
    render: (row) => `¥${(row.cost_price || 0).toFixed(2)}`,
  },
  {
    title: "当前价",
    key: "current_price",
    width: 100,
    render: (row) => `¥${(row.current_price || 0).toFixed(2)}`,
  },
  {
    title: "市值",
    key: "market_value",
    width: 120,
    render: (row) => `¥${((row.market_value || 0) / 10000).toFixed(2)}万`,
  },
  {
    title: "盈亏",
    key: "pnl",
    width: 120,
    render: (row) => {
      const isPositive = (row.pnl || 0) >= 0;
      const color = isPositive
        ? "var(--color-stock-up)"
        : "var(--color-stock-down)";
      return h(
        "span",
        { style: { color } },
        `${isPositive ? "+" : ""}¥${(row.pnl || 0).toFixed(2)}`,
      );
    },
  },
  {
    title: "盈亏率",
    key: "pnl_ratio",
    width: 100,
    render: (row) => {
      const isPositive = (row.pnl_ratio || 0) >= 0;
      const color = isPositive
        ? "var(--color-stock-up)"
        : "var(--color-stock-down)";
      return h(
        "span",
        { style: { color } },
        `${isPositive ? "+" : ""}${((row.pnl_ratio || 0) * 100).toFixed(2)}%`,
      );
    },
  },
  {
    title: "权重",
    key: "weight",
    width: 80,
    render: (row) => `${((row.weight || 0) * 100).toFixed(1)}%`,
  },
];

const loadPerformanceData = async () => {
  loading.value = true;
  try {
    const response = await fetch("/quantTrade/performance/account");
    const data = await response.json();
    performanceData.value = data.performance || [];
    positions.value = data.positions || [];
    error.value = false;
  } catch (err) {
    console.error("加载绩效数据失败:", err);
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const currentStats = computed(() => {
  if (!performanceData.value || performanceData.value.length === 0) return null;
  return performanceData.value[performanceData.value.length - 1];
});

const pnlColor = computed(() => {
  return (currentStats.value?.daily_pnl || 0) >= 0
    ? "var(--color-stock-up)"
    : "var(--color-stock-down)";
});

onMounted(() => {
  loadPerformanceData();
});
</script>

<template>
  <div class="account-performance-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">账户绩效</h1>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>
    <div class="main-content">
    <n-spin :show="loading">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取绩效数据失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="loadPerformanceData">重试</n-button></template
      >
    </n-result>

    <n-card v-else title="账户绩效分析">
      <template #header-extra>
        <n-space>
          <n-select
            v-model:value="selectedPeriod"
            style="width: 120px"
            :options="periodOptions"
          />
          <n-date-picker
            v-model:formatted-value="dateRange"
            type="daterange"
            clearable
          />
        </n-space>
      </template>

      <!-- Summary Statistics Row -->
      <n-grid
        :x-gap="16"
        :cols="6"
        responsive="screen"
        style="margin-bottom: 24px"
      >
        <n-grid-item>
          <n-statistic label="总资产">
            ¥{{ (currentStats?.total_asset || 0).toFixed(2) }}
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="现金">
            ¥{{ (currentStats?.cash || 0).toFixed(2) }}
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="持仓市值">
            ¥{{ (currentStats?.market_value || 0).toFixed(2) }}
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="当日盈亏">
            <span :style="{ color: pnlColor }">
              ¥{{ (currentStats?.daily_pnl || 0).toFixed(2) }}
            </span>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="当日收益率">
            <span :style="{ color: pnlColor }">
              {{ ((currentStats?.daily_return || 0) * 100).toFixed(2) }}%
            </span>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="累计收益率">
            <span :style="{ color: pnlColor }">
              {{ ((currentStats?.cumulative_return || 0) * 100).toFixed(2) }}%
            </span>
          </n-statistic>
        </n-grid-item>
      </n-grid>

      <n-tabs>
        <n-tab-pane name="metrics" tab="绩效指标">
          <n-grid :x-gap="16" :cols="3" responsive="screen">
            <n-grid-item>
              <n-card size="small">
                <n-statistic label="总收益率">
                  <span
                    :style="{
                      color:
                        performanceMetrics.totalReturn >= 0
                          ? 'var(--color-stock-up)'
                          : 'var(--color-stock-down)',
                    }"
                  >
                    {{ (performanceMetrics.totalReturn * 100).toFixed(2) }}%
                  </span>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card size="small">
                <n-statistic label="年化收益率">
                  <span
                    :style="{
                      color:
                        performanceMetrics.annualizedReturn >= 0
                          ? 'var(--color-stock-up)'
                          : 'var(--color-stock-down)',
                    }"
                  >
                    {{
                      (performanceMetrics.annualizedReturn * 100).toFixed(2)
                    }}%
                  </span>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card size="small">
                <n-statistic label="夏普比率">
                  {{ performanceMetrics.sharpeRatio.toFixed(2) }}
                </n-statistic>
              </n-card>
            </n-grid-item>
          </n-grid>

          <n-grid
            :x-gap="16"
            :cols="3"
            responsive="screen"
            style="margin-top: 16px"
          >
            <n-grid-item>
              <n-card size="small">
                <n-statistic label="最大回撤">
                  <span style="color: var(--color-stock-down)">
                    {{ (performanceMetrics.maxDrawdown * 100).toFixed(2) }}%
                  </span>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card size="small">
                <n-statistic label="波动率">
                  {{ (performanceMetrics.volatility * 100).toFixed(2) }}%
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card size="small">
                <n-statistic label="胜率">
                  {{ (performanceMetrics.winRate * 100).toFixed(2) }}%
                </n-statistic>
              </n-card>
            </n-grid-item>
          </n-grid>
        </n-tab-pane>

        <n-tab-pane name="positions" tab="持仓分析">
          <n-data-table
            :columns="positionColumns"
            :data="positions"
            :pagination="false"
            :row-key="(row: Position) => row.symbol"
            size="small"
          />
        </n-tab-pane>

        <n-tab-pane name="chart" tab="净值曲线">
          <div class="chart-placeholder">净值曲线图表区域</div>
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </n-spin>
  </div>
  </div>
</template>

<style scoped>
.account-performance-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.chart-placeholder {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--n-text-color-3);
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
}
</style>
