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
  NSelect,
  NStatistic,
  NEmpty,
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

const stats = reactive<StatsData>({
  upLimitCount: 0,
  downLimitCount: 0,
  consecutiveCount: 0,
  limitRatio: 0,
});

const limitStocks = ref<LimitStock[]>([]);

// ---- computed: paginated & filtered rows ----
const upStocks = computed(() =>
  limitStocks.value.filter((s) => s.limit_type === "up"),
);
const downStocks = computed(() =>
  limitStocks.value.filter((s) => s.limit_type === "down"),
);
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

const paginationConfig = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => {
    paginationConfig.page = page;
  },
  onUpdatePageSize: (pageSize: number) => {
    paginationConfig.pageSize = pageSize;
    paginationConfig.page = 1;
  },
});

const getLimitTypeText = (type: string) => {
  const map: Record<string, string> = {
    up: "涨停",
    down: "跌停",
    near_up: "接近涨停",
    near_down: "接近跌停",
  };
  return map[type] || type;
};

const getSpaceClass = (spacePct: number) => {
  if (spacePct > 5) return "space-high";
  if (spacePct > 2) return "space-medium";
  if (spacePct > 0) return "space-low";
  return "space-none";
};

const baseCols = (type: string): DataTableColumns<LimitStock> => [
  {
    title: "股票代码",
    key: "ts_code",
    render: (row) =>
      h(
        "div",
        {
          class: "stock-code",
          style: "cursor:pointer",
          onClick: () => viewStockDetail(row),
        },
        [
          h("div", { class: "code" }, row.ts_code),
          h("div", { class: "name" }, row.name),
        ],
      ),
  },
  {
    title: "收盘价",
    key: "close",
    render: (row: any) => `¥${row.close?.toFixed(2)}`,
  },
  {
    title: type === "up" ? "涨停价" : "跌停价",
    key: type === "up" ? "up_limit" : "down_limit",
    render: (row: any) =>
      `¥${(type === "up" ? row.up_limit : row.down_limit)?.toFixed(2)}`,
  },
  {
    title: "连续天数",
    key: "consecutive_days",
    render: (row: any) =>
      row.consecutive_days >= 1
        ? h(
            NTag,
            {
              type: row.consecutive_days >= 3 ? "error" : "warning",
              size: "small",
            },
            {
              default: () =>
                row.consecutive_days === 1
                  ? "首日"
                  : `${row.consecutive_days}天`,
            },
          )
        : "-",
  },
  {
    title: type === "up" ? "封单空间" : "跌停空间",
    key: "space_pct",
    render: (row: any) =>
      h(
        "span",
        { class: getSpaceClass(row.space_pct) },
        `${row.space_pct?.toFixed(2)}%`,
      ),
  },
  { title: "行业", key: "industry", render: (row: any) => row.industry },
];
const columnsUp = baseCols("up");
const columnsDown = baseCols("down");
const rowProps = (row: LimitStock) => ({
  style: "cursor:pointer",
  onClick: () => viewStockDetail(row),
});

const handleBack = () => router.go(-1);

async function loadRealData() {
  loading.value = true;
  error.value = false;
  try {
    const result = await marketAPI.getLimitAnalysis({
      trade_date: filterDate.value
        ? new Date(filterDate.value).toISOString().slice(0, 10)
        : undefined,
      exchange: filterExchange.value || undefined,
      board: filterMarket.value || undefined,
    });
    if (result) {
      stats.upLimitCount = result.stats?.limit_up ?? 0;
      stats.downLimitCount = result.stats?.limit_down ?? 0;
      stats.limitRatio = result.stats?.up_down_ratio ?? 0;
      stats.consecutiveCount = result.stats?.consecutive_max ?? 0;
      const all = [
        ...(result.up_stocks || []).map((s: any) => ({
          ts_code: s.ts_code,
          name: s.name,
          close: s.close ?? 0,
          up_limit: s.up_limit ?? 0,
          down_limit: s.down_limit ?? 0,
          limit_type: "up" as const,
          consecutive_days: s.consecutive_days ?? 0,
          space_pct: s.up_limit
            ? +(((s.up_limit - s.close) / s.close) * 100).toFixed(1)
            : 0,
          industry: s.industry || "",
          exchange: s.exchange || "",
          market: s.market || "",
        })),
        ...(result.down_stocks || []).map((s: any) => ({
          ts_code: s.ts_code,
          name: s.name,
          close: s.close ?? 0,
          up_limit: s.up_limit ?? 0,
          down_limit: s.down_limit ?? 0,
          limit_type: "down" as const,
          consecutive_days: s.consecutive_days ?? 0,
          space_pct: s.down_limit
            ? +(((s.close - s.down_limit) / s.down_limit) * 100).toFixed(1)
            : 0,
          industry: s.industry || "",
          exchange: s.exchange || "",
          market: s.market || "",
        })),
      ];
      limitStocks.value = all;
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

const refreshData = () => loadRealData();
const searchData = () => {
  paginationConfig.page = 1;
  loadRealData();
};

const viewStockDetail = (stock: LimitStock) =>
  router.push("/market/stock/" + stock.ts_code);

onMounted(() => {
  // 筛选条件首次进入置空（日期缺省 → 后端自动取最新交易日；交易所/板块默认"全部"）
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
          <n-button
            size="tiny"
            type="primary"
            ghost
            @click="router.push('/strategies/create?template=limit_up')"
            >创建打板策略</n-button
          >
          <n-button
            class="action-btn"
            @click="refreshData"
            :loading="loading"
            quaternary
          >
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
          v-if="error"
          status="500"
          title="数据加载失败"
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
                  <n-date-picker
                    v-model:value="filterDate"
                    type="date"
                    clearable
                    @update:value="searchData"
                  />
                </n-form-item-gi>
                <n-form-item-gi :span="6" label="交易所">
                  <n-select
                    v-model:value="filterExchange"
                    :options="exchangeOptions"
                    clearable
                    @update:value="searchData"
                  />
                </n-form-item-gi>
                <n-form-item-gi :span="6" label="市场类型">
                  <n-select
                    v-model:value="filterMarket"
                    :options="marketOptions"
                    clearable
                    @update:value="searchData"
                  />
                </n-form-item-gi>
              </n-grid>
              <div class="form-actions">
                <n-button type="primary" @click="searchData">
                  <template #icon><SmartIcon name="Search" /></template>
                  查询
                </n-button>
              </div>
            </n-form>
          </n-card>

          <!-- 统计卡片 -->
          <n-grid :cols="4" :x-gap="16" class="stats-section">
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic label="涨停数量" :value="stats.upLimitCount">
                  <template #prefix
                    ><SmartIcon name="TrendingUp" class="stat-icon up"
                  /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic label="跌停数量" :value="stats.downLimitCount">
                  <template #prefix
                    ><SmartIcon name="TrendingDown" class="stat-icon down"
                  /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic label="连续涨停" :value="stats.consecutiveCount">
                  <template #prefix
                    ><SmartIcon name="TrendingUp" class="stat-icon consecutive"
                  /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stats-card">
                <n-statistic
                  label="涨跌停比例"
                  :value="stats.limitRatio"
                  suffix="%"
                >
                  <template #prefix
                    ><SmartIcon name="PieChart" class="stat-icon ratio"
                  /></template>
                </n-statistic>
              </n-card>
            </n-grid-item>
          </n-grid>

          <!-- 涨停列表 -->
          <n-grid :x-gap="16" :cols="2" style="margin-top: 16px">
            <n-grid-item>
              <n-card class="data-card" title="涨停股票">
                <template #header-extra>
                  <n-tag type="error" size="small"
                    >{{ upStocks.length }} 只</n-tag
                  >
                </template>
                <n-empty
                  v-if="!upStocks.length"
                  description="今日无涨停股票"
                  style="padding: 20px"
                />
                <n-data-table
                  v-else
                  :columns="columnsUp"
                  :data="upStocks"
                  :row-props="rowProps"
                  :bordered="false"
                  size="small"
                  max-height="420"
                />
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="data-card" title="跌停股票">
                <template #header-extra>
                  <n-tag type="info" size="small"
                    >{{ downStocks.length }} 只</n-tag
                  >
                </template>
                <n-empty
                  v-if="!downStocks.length"
                  description="今日无跌停股票"
                  style="padding: 20px"
                />
                <n-data-table
                  v-else
                  :columns="columnsDown"
                  :data="downStocks"
                  :row-props="rowProps"
                  :bordered="false"
                  size="small"
                  max-height="420"
                />
              </n-card>
            </n-grid-item>
          </n-grid>
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

    &.up {
      color: var(--color-stock-up, #ff5252);
    }
    &.down {
      color: var(--color-stock-down, #00e676);
    }
    &.consecutive {
      color: var(--n-primary-color);
    }
    &.ratio {
      color: var(--n-warning-color);
    }
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

.space-high {
  color: var(--color-stock-up, #ff5252);
  font-weight: 600;
}
.space-medium {
  color: var(--n-warning-color);
  font-weight: 600;
}
.space-low {
  color: var(--n-text-color-2);
}
.space-none {
  color: var(--color-stock-down, #00e676);
  font-weight: 600;
}

/* 响应式 */
@media (max-width: 768px) {
}
</style>
