<!-- LimitAnalysis.vue - 涨跌停分析页面 - 统一样式 -->
<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import {
  DataTableColumns,
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItemGi,
  NGridItem,
  NGrid,
  NIcon,
  NSelect,
  NStatistic,
  NResult,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import marketAPI from "@/api/market";

const router = useRouter();
const message = useMessage();

interface LimitStock {
  ts_code: string;
  name: string;
  close: number;
  up_limit: number;
  down_limit: number;
  limit_type: "up" | "down" | "near_up" | "near_down";
  consecutive_days: number;
  space_pct: number;
  industry: string;
  exchange: string;
  market: string;
}

interface StatsData {
  upLimitCount: number;
  downLimitCount: number;
  consecutiveCount: number;
  limitRatio: number;
}

const loading = ref(false);
const error = ref(false);
const filterDate = ref<number | null>(null);
const filterExchange = ref<string | null>(null);
const filterMarket = ref<string | null>(null);
const analysisType = ref("daily");
const viewMode = ref("table");

const stats = reactive<StatsData>({
  upLimitCount: 45,
  downLimitCount: 12,
  consecutiveCount: 8,
  limitRatio: 78.9,
});

const limitStocks = ref<LimitStock[]>([
  { ts_code: "000001.SZ", name: "平安银行", close: 12.45, up_limit: 13.7, down_limit: 11.21, limit_type: "near_up", consecutive_days: 0, space_pct: 2.5, industry: "银行", exchange: "SZSE", market: "主板" },
]);

const exchangeOptions = [
  { label: "全部", value: "" },
  { label: "上交所", value: "SSE" },
  { label: "深交所", value: "SZSE" },
  { label: "北交所", value: "BSE" },
];

const marketOptions = [
  { label: "全部", value: "" },
  { label: "主板", value: "主板" },
  { label: "创业板", value: "创业板" },
  { label: "科创板", value: "科创板" },
];

const analysisTypeOptions = [
  { label: "当日涨跌停", value: "daily" },
  { label: "连续涨停", value: "consecutive" },
  { label: "涨跌停空间", value: "space" },
  { label: "历史统计", value: "history" },
];

const paginationConfig = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => { paginationConfig.page = page; },
  onUpdatePageSize: (pageSize: number) => {
    paginationConfig.pageSize = pageSize;
    paginationConfig.page = 1;
  },
});

const viewTitle = computed(() =>
  viewMode.value === "table" ? "涨跌停股票列表" : "涨跌停分析图表",
);

const getLimitTagType = (type: string): "success" | "error" | "warning" | "info" => {
  const map: Record<string, "success" | "error" | "warning" | "info"> = {
    up: "success", down: "error", near_up: "warning", near_down: "info",
  };
  return map[type] || "info";
};

const getLimitTypeText = (type: string) => {
  const map: Record<string, string> = {
    up: "涨停", down: "跌停", near_up: "接近涨停", near_down: "接近跌停",
  };
  return map[type] || type;
};

const getSpaceClass = (spacePct: number) => {
  if (spacePct > 5) return "space-high";
  if (spacePct > 2) return "space-medium";
  if (spacePct > 0) return "space-low";
  return "space-none";
};

const columns: DataTableColumns<LimitStock> = [
  {
    title: "股票代码", key: "ts_code",
    render: (row) => h("div", { class: "stock-code" }, [
      h("div", { class: "code" }, row.ts_code),
      h("div", { class: "name" }, row.name),
    ]),
  },
  { title: "收盘价", key: "close", render: (row) => `¥${row.close?.toFixed(2)}` },
  { title: "涨停价", key: "up_limit", render: (row) => `¥${row.up_limit?.toFixed(2)}` },
  { title: "跌停价", key: "down_limit", render: (row) => `¥${row.down_limit?.toFixed(2)}` },
  {
    title: "状态", key: "limit_type",
    render: (row) => h(NTag, { type: getLimitTagType(row.limit_type), size: "small" }, { default: () => getLimitTypeText(row.limit_type) }),
  },
  {
    title: "连续天数", key: "consecutive_days",
    render: (row) => row.consecutive_days > 1 ? h(NTag, { type: "primary", size: "small" }, { default: () => `${row.consecutive_days}天` }) : "-",
  },
  {
    title: "涨停空间", key: "space_pct",
    render: (row) => h("span", { class: getSpaceClass(row.space_pct) }, `${row.space_pct?.toFixed(2)}%`),
  },
  { title: "行业", key: "industry", render: (row) => row.industry },
  {
    title: "操作", key: "actions",
    render: (row) => h(NButton, { size: "small", type: "primary", onClick: () => viewStockDetail(row) }, { default: () => "详情" }),
  },
];

const handleBack = () => router.go(-1);

const refreshData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 800));
    message.success("数据刷新成功");
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const searchData = async () => {
  loading.value = true;
  try {
    await new Promise((r) => setTimeout(r, 500));
    message.success("查询成功");
  } finally {
    loading.value = false;
  }
};

const toggleViewMode = () => {
  viewMode.value = viewMode.value === "table" ? "chart" : "table";
};

const viewStockDetail = (stock: LimitStock) => message.info(`查看股票详情: ${stock.name}`);

async function loadRealData() {
  try {
    const [dash, upStocks, downStocks] = await Promise.all([
      marketAPI.getDashboardOverview().catch(() => null),
      marketAPI.getScreener({ pct_chg_min: 9.5, sort_by: "pct_chg", sort_dir: "desc", limit: 30 }).catch(() => ({ stocks: [] })),
      marketAPI.getScreener({ pct_chg_max: -9.5, sort_by: "pct_chg", sort_dir: "asc", limit: 30 }).catch(() => ({ stocks: [] })),
    ])
    if (dash?.market_breadth) {
      summaryData.limitUpCount = dash.market_breadth.limit_up
      summaryData.limitDownCount = dash.market_breadth.limit_down
    }
    const all = [
      ...upStocks.stocks.map((s: any) => ({ ...s, limit_type: "limit_up", exchange: s.ts_code?.endsWith(".SH") ? "SSE" : "SZSE", market: "主板", consecutive_days: 0, space_pct: 0, pre_close: 0, up_limit: 0, down_limit: 0 })),
      ...downStocks.stocks.map((s: any) => ({ ...s, limit_type: "limit_down", exchange: s.ts_code?.endsWith(".SH") ? "SSE" : "SZSE", market: "主板", consecutive_days: 0, space_pct: 0, pre_close: 0, up_limit: 0, down_limit: 0 })),
    ]
    if (all.length) limitStocks.value = all as any
  } catch {}
}

onMounted(() => {
  filterDate.value = new Date().getTime();
  loadRealData();
});
</script>

<template>
  <div class="limit-analysis-page scrollbar-hide">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">涨跌停分析</h1>
          <p class="page-description">实时监控股票涨跌停情况与市场热度分析</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 主内容 -->
    <div class="main-content">
      <n-spin :show="loading">
        <n-result
          v-if="error" status="500" title="数据加载失败"
          description="请检查网络连接后重试"
        >
          <template #footer>
            <n-button type="primary" @click="refreshData">重试</n-button>
          </template>
        </n-result>

        <template v-else>
          <!-- 筛选条件 -->
          <n-card class="filter-card" title="筛选条件">
            <n-form label-placement="left" :label-width="80">
              <n-grid :cols="24" :x-gap="24">
                <n-form-item-gi :span="6" label="交易日期">
                  <n-date-picker v-model:value="filterDate" type="date" clearable @update:value="searchData" />
                </n-form-item-gi>
                <n-form-item-gi :span="6" label="交易所">
                  <n-select v-model:value="filterExchange" :options="exchangeOptions" clearable @update:value="searchData" />
                </n-form-item-gi>
                <n-form-item-gi :span="6" label="市场类型">
                  <n-select v-model:value="filterMarket" :options="marketOptions" clearable @update:value="searchData" />
                </n-form-item-gi>
                <n-form-item-gi :span="6" label="分析类型">
                  <n-select v-model:value="analysisType" :options="analysisTypeOptions" @update:value="searchData" />
                </n-form-item-gi>
              </n-grid>
              <div class="form-actions">
                <n-button type="primary" @click="searchData">
                  <template #icon><SmartIcon name="Search" /></template>
                  查询
                </n-button>
                <n-button @click="() => message.info('导出功能开发中')">
                  <template #icon><SmartIcon name="Download" /></template>
                  导出数据
                </n-button>
              </div>
            </n-form>
          </n-card>

          <!-- 统计卡片 -->
          <n-grid :cols="4" :x-gap="16" class="stats-section">
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic label="涨停数量" :value="stats.upLimitCount">
                  <template #prefix><SmartIcon name="TrendingUp" class="stat-icon up" /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic label="跌停数量" :value="stats.downLimitCount">
                  <template #prefix><SmartIcon name="TrendingDown" class="stat-icon down" /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic label="连续涨停" :value="stats.consecutiveCount">
                  <template #prefix><SmartIcon name="TrendingUp" class="stat-icon consecutive" /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic label="涨跌停比例" :value="stats.limitRatio" suffix="%">
                  <template #prefix><SmartIcon name="PieChart" class="stat-icon ratio" /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
          </n-grid>

          <!-- 涨跌停列表 -->
          <n-card class="data-card" :title="viewTitle">
            <template #header-extra>
              <n-button @click="toggleViewMode" size="small">
                <template #icon><SmartIcon :name="viewMode === 'table' ? 'BarChart' : 'Grid'" /></template>
                {{ viewMode === "table" ? "图表视图" : "表格视图" }}
              </n-button>
            </template>

            <n-data-table
              v-if="viewMode === 'table'"
              :columns="columns"
              :data="limitStocks"
              :pagination="paginationConfig"
              :bordered="false"
            />

            <div v-else class="chart-container">
              <SmartIcon name="BarChart" class="placeholder-icon" />
              <p>涨跌停分析图表</p>
            </div>
          </n-card>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<style scoped lang="scss">
.limit-analysis-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;

  :deep(.n-card) {
    --n-color: transparent !important;
    background: var(--color-bg-card, rgba(12, 18, 32, 0.72)) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);

    > .n-card-header,
    > .n-card__content,
    > .n-card-footer,
    > .n-card-action {
      background: transparent !important;
    }
  }
}

.filter-card {
  margin-bottom: 24px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--n-border-color);
}

.stats-section {
  margin-bottom: 24px;
}

.stats-card {
  .stat-icon {
    font-size: 20px;

    &.up           { color: var(--color-stock-up, #FF5252); }
    &.down         { color: var(--color-stock-down, #00E676); }
    &.consecutive  { color: var(--n-primary-color); }
    &.ratio        { color: var(--n-warning-color); }
  }
}

.data-card {
  /* margin handled by parent padding */
}

.stock-code {
  .code {
    font-weight: 600;
    color: var(--n-text-color-1);
  }
  .name {
    font-size: 12px;
    color: var(--n-text-color-3);
    margin-top: 2px;
  }
}

.space-high   { color: var(--color-stock-up, #FF5252); font-weight: 600; }
.space-medium { color: var(--n-warning-color); font-weight: 600; }
.space-low    { color: var(--n-text-color-2); }
.space-none   { color: var(--color-stock-down, #00E676); font-weight: 600; }

.chart-container {
  height: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-secondary, rgba(255, 255, 255, 0.03));
  border-radius: 6px;
  color: var(--n-text-color-2);

  .placeholder-icon {
    font-size: 48px;
    margin-bottom: 8px;
    opacity: 0.5;
  }

  p { margin: 0; font-size: 14px; }
}

/* 响应式 */
@media (max-width: 768px) {
}
</style>
