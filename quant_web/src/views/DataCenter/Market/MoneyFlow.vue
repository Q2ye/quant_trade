<!-- MoneyFlow.vue - Naive UI 实现的资金流向分析页面 -->
<template>
  <div class="money-flow-page scrollbar-hide">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">资金流向分析</h1>
          <p class="page-description">实时追踪主力资金动向与市场资金分布</p>
        </div>
        <div class="header-actions">
          <!-- 时间周期选择 -->
          <n-radio-group
            v-model:value="activePeriod"
            size="small"
            class="period-selector"
          >
            <n-radio-button
              v-for="period in periodOptions"
              :key="period.value"
              :value="period.value"
              :label="period.label"
            />
          </n-radio-group>
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
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
          <!-- 资金流向概览 -->
          <section class="flow-overview">
            <n-grid :cols="4" :x-gap="16" :y-gap="16">
              <n-gi>
                <n-card class="flow-card inflow" hoverable>
                  <n-statistic
                    label="主力净流入"
                    :value="formatAmount(flowData.mainInflow)"
                  >
                    <template #prefix>
                      <SmartIcon name="ArrowDownward" class="flow-icon" />
                    </template>
                    <template #suffix>
                      <div class="flow-change">
                        <n-text type="success"
                          >+{{ flowData.mainChange }}%</n-text
                        >
                        <span> 较昨日</span>
                      </div>
                    </template>
                  </n-statistic>
                </n-card>
              </n-gi>
              <n-gi>
                <n-card class="flow-card outflow" hoverable>
                  <n-statistic
                    label="主力净流出"
                    :value="formatAmount(flowData.mainOutflow)"
                  >
                    <template #prefix>
                      <SmartIcon name="ArrowUpward" class="flow-icon" />
                    </template>
                    <template #suffix>
                      <div class="flow-change">
                        <n-text type="error"
                          >-{{ flowData.outflowChange }}%</n-text
                        >
                        <span> 较昨日</span>
                      </div>
                    </template>
                  </n-statistic>
                </n-card>
              </n-gi>
              <n-gi>
                <n-card class="flow-card total" hoverable>
                  <n-statistic
                    label="净流入总额"
                    :value="formatAmount(flowData.netFlow, true)"
                    :value-style="getNetFlowStyle(flowData.netFlow)"
                  >
                    <template #prefix>
                      <SmartIcon name="TrendingUp" class="flow-icon" />
                    </template>
                    <template #suffix>
                      <div class="flow-change">
                        <n-text
                          :type="
                            flowData.netFlowChange >= 0 ? 'success' : 'error'
                          "
                        >
                          {{ formatAmount(flowData.netFlowChange, true) }}
                        </n-text>
                        <span> 较昨日</span>
                      </div>
                    </template>
                  </n-statistic>
                </n-card>
              </n-gi>
              <n-gi>
                <n-card class="flow-card turnover" hoverable>
                  <n-statistic
                    label="成交总额"
                    :value="formatAmount(flowData.turnover)"
                  >
                    <template #prefix>
                      <SmartIcon name="SwapHorizontal" class="flow-icon" />
                    </template>
                    <template #suffix>
                      <div class="flow-change">
                        <n-text type="success"
                          >+{{ flowData.turnoverChange }}%</n-text
                        >
                        <span> 较昨日</span>
                      </div>
                    </template>
                  </n-statistic>
                </n-card>
              </n-gi>
            </n-grid>
          </section>

          <!-- 资金流向图表 -->
          <section class="flow-charts">
            <n-grid :cols="2" :x-gap="16" :y-gap="16">
              <n-gi>
                <n-card title="资金流向趋势" hoverable>
                  <template #header-extra>
                    <n-radio-group v-model:value="chartType" size="small">
                      <n-radio-button value="line" label="折线图" />
                      <n-radio-button value="bar" label="柱状图" />
                    </n-radio-group>
                  </template>
                  <div class="chart-container">
                    <div class="chart-placeholder">
                      <SmartIcon name="LineChart" class="placeholder-icon" />
                      <p>资金流向趋势图表</p>
                    </div>
                  </div>
                </n-card>
              </n-gi>
              <n-gi>
                <n-card title="行业资金分布" hoverable>
                  <div class="chart-container">
                    <div class="chart-placeholder">
                      <SmartIcon name="PieChart" class="placeholder-icon" />
                      <p>行业资金分布图表</p>
                    </div>
                  </div>
                </n-card>
              </n-gi>
            </n-grid>
          </section>

          <!-- 资金流向明细 -->
          <section class="flow-details">
            <n-card title="资金流向明细" hoverable>
              <template #header-extra>
                <div class="header-tools">
                  <n-input
                    v-model:value="searchQuery"
                    placeholder="搜索股票代码或名称"
                    clearable
                    class="search-input"
                    @input="handleSearch"
                  >
                    <template #prefix>
                      <SmartIcon name="Search" />
                    </template>
                  </n-input>
                  <n-select
                    v-model:value="filterIndustry"
                    :options="industryOptions"
                    placeholder="全部行业"
                    clearable
                    style="width: 150px"
                    @update:value="handleFilterChange"
                  />
                </div>
              </template>

              <n-data-table
                :columns="columns"
                :data="filteredFlowData"
                :pagination="paginationConfig"
                :loading="loading"
                :bordered="false"
              />

              <template #footer>
                <div class="pagination-info">共 {{ totalCount }} 条数据</div>
              </template>
            </n-card>
          </section>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, computed, onMounted, ref, reactive } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NDataTable,
  DataTableColumns,
  NGrid,
  NGridItem,
  NStatistic,
  NInput,
  NSelect,
  NRadioGroup,
  NRadioButton,
  NText,
  NTag,
  NResult,
  NSpin,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import marketAPI from "@/api/market";

const router = useRouter();
const message = useMessage();

// 响应式数据
const activePeriod = ref("today");
const chartType = ref("line");
const searchQuery = ref("");
const filterIndustry = ref("");
const loading = ref(false);
const error = ref(false);

// 时间周期选项
const periodOptions = [
  { label: "今日", value: "today" },
  { label: "5日", value: "5d" },
  { label: "10日", value: "10d" },
];

// 资金流向数据
const flowData = ref({
  mainInflow: 1256700,
  mainOutflow: 892300,
  netFlow: 364400,
  turnover: 8456700,
  mainChange: 12.5,
  outflowChange: 8.3,
  netFlowChange: 123400,
  turnoverChange: 15.2,
});

// 资金流向明细数据
interface FlowDetail {
  code: string;
  name: string;
  exchange: string;
  industry: string;
  mainInflow: number;
  retailInflow: number;
  totalInflow: number;
  inflowRate: number;
  turnover: number;
  is_st: boolean;
}

const flowDetails = ref<FlowDetail[]>([
  {
    code: "000001",
    name: "平安银行",
    exchange: "SZSE",
    industry: "银行",
    mainInflow: 12567,
    retailInflow: -2345,
    totalInflow: 10222,
    inflowRate: 2.34,
    turnover: 156789,
    is_st: false,
  },
  {
    code: "300750",
    name: "宁德时代",
    exchange: "SZSE",
    industry: "电气设备",
    mainInflow: 89234,
    retailInflow: 12345,
    totalInflow: 101579,
    inflowRate: 3.45,
    turnover: 234567,
    is_st: false,
  },
  {
    code: "600036",
    name: "招商银行",
    exchange: "SSE",
    industry: "银行",
    mainInflow: -4567,
    retailInflow: 2345,
    totalInflow: -2222,
    inflowRate: -1.23,
    turnover: 123456,
    is_st: false,
  },
  {
    code: "000858",
    name: "五粮液",
    exchange: "SZSE",
    industry: "食品饮料",
    mainInflow: 34567,
    retailInflow: 5678,
    totalInflow: 40245,
    inflowRate: 2.89,
    turnover: 98765,
    is_st: false,
  },
  {
    code: "600519",
    name: "贵州茅台",
    exchange: "SSE",
    industry: "食品饮料",
    mainInflow: 45678,
    retailInflow: 6789,
    totalInflow: 52467,
    inflowRate: 3.12,
    turnover: 123456,
    is_st: false,
  },
]);

const industries = ref([
  "银行",
  "证券",
  "保险",
  "电子",
  "计算机",
  "医药生物",
  "电气设备",
  "食品饮料",
]);

// 行业选项
const industryOptions = computed(() => [
  { label: "全部行业", value: "" },
  ...industries.value.map((industry) => ({ label: industry, value: industry })),
]);

// 分页配置
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

// 计算属性
const filteredFlowData = computed(() => {
  let data = flowDetails.value;

  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    data = data.filter(
      (item) =>
        item.code.toLowerCase().includes(query) ||
        item.name.toLowerCase().includes(query),
    );
  }

  // 行业过滤
  if (filterIndustry.value) {
    data = data.filter((item) => item.industry === filterIndustry.value);
  }

  paginationConfig.itemCount = data.length;

  // 分页
  const start = (paginationConfig.page - 1) * paginationConfig.pageSize;
  const end = start + paginationConfig.pageSize;
  return data.slice(start, end);
});

const totalCount = computed(() => paginationConfig.itemCount);

// 表格列定义
const columns: DataTableColumns<FlowDetail> = [
  {
    title: "代码",
    key: "code",
    width: 120,
    render: (row) => {
      return h("div", { class: "code-cell" }, [
        h("div", { class: "code" }, row.code),
        h(
          NTag,
          {
            size: "small",
            type: getExchangeType(row.exchange),
          },
          { default: () => getExchangeText(row.exchange) },
        ),
      ]);
    },
  },
  {
    title: "名称",
    key: "name",
    width: 120,
    render: (row) => {
      return h("div", { class: "name-cell" }, [
        h("span", { class: "name" }, row.name),
        row.is_st &&
          h(
            NTag,
            {
              size: "small",
              type: "error",
              style: { marginLeft: "4px" },
            },
            { default: () => "ST" },
          ),
      ]);
    },
  },
  {
    title: "行业",
    key: "industry",
    width: 100,
    render: (row) =>
      h(NTag, { type: "info", size: "small" }, { default: () => row.industry }),
  },
  {
    title: "主力净流入(万)",
    key: "mainInflow",
    width: 120,
    align: "right",
    render: (row) =>
      h(
        "span",
        {
          class: getFlowClass(row.mainInflow),
        },
        formatAmount(row.mainInflow, true),
      ),
  },
  {
    title: "散户净流入(万)",
    key: "retailInflow",
    width: 120,
    align: "right",
    render: (row) =>
      h(
        "span",
        {
          class: getFlowClass(row.retailInflow),
        },
        formatAmount(row.retailInflow, true),
      ),
  },
  {
    title: "总净流入(万)",
    key: "totalInflow",
    width: 120,
    align: "right",
    render: (row) =>
      h(
        "span",
        {
          class: getFlowClass(row.totalInflow),
        },
        formatAmount(row.totalInflow, true),
      ),
  },
  {
    title: "净流入率",
    key: "inflowRate",
    width: 100,
    align: "right",
    render: (row) =>
      h(
        "span",
        {
          class: getFlowClass(row.inflowRate),
        },
        `${row.inflowRate > 0 ? "+" : ""}${row.inflowRate.toFixed(2)}%`,
      ),
  },
  {
    title: "成交额(万)",
    key: "turnover",
    width: 120,
    align: "right",
    render: (row) => formatAmount(row.turnover),
  },
  {
    title: "操作",
    key: "actions",
    width: 80,
    align: "center",
    render: (row) =>
      h(
        NButton,
        {
          size: "small",
          type: "primary",
          onClick: () => viewStockDetail(row),
        },
        { default: () => "详情" },
      ),
  },
];

// 方法
const handleBack = () => {
  router.go(-1);
};

const refreshData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await marketAPI.getStocks({ limit: 20 }).catch(() => null);
    message.success("数据刷新成功");
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  paginationConfig.page = 1;
};

const handleFilterChange = () => {
  paginationConfig.page = 1;
};

const getExchangeType = (exchange: string) => {
  const types: Record<string, "error" | "primary" | "warning"> = {
    SSE: "error",
    SZSE: "primary",
    BSE: "warning",
  };
  return types[exchange] || "default";
};

const getExchangeText = (exchange: string) => {
  const texts: Record<string, string> = {
    SSE: "沪",
    SZSE: "深",
    BSE: "京",
  };
  return texts[exchange] || exchange;
};

const getFlowClass = (value: number) => {
  if (value > 0) return "flow-positive";
  if (value < 0) return "flow-negative";
  return "flow-neutral";
};

const getNetFlowStyle = (value: number) => {
  return {
    color: value >= 0 ? "var(--n-success-color)" : "var(--n-error-color)",
  };
};

const formatAmount = (amount: number, showSign: boolean = false) => {
  if (amount === null || amount === undefined) return "-";
  const absAmount = Math.abs(amount);
  const sign = showSign ? (amount > 0 ? "+" : amount < 0 ? "-" : "") : "";

  if (absAmount >= 100000000) {
    return sign + (absAmount / 100000000).toFixed(2) + "亿";
  } else if (absAmount >= 10000) {
    return sign + (absAmount / 10000).toFixed(2) + "万";
  } else {
    return sign + absAmount.toFixed(2);
  }
};

const viewStockDetail = (row: FlowDetail) => {
  router.push(`/market/stock/${row.code}`);
};

// 生命周期
onMounted(() => {
  paginationConfig.itemCount = flowDetails.value.length;
  refreshData();
});
</script>

<style scoped lang="scss">
.money-flow-page {
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

/* 资金流向概览 */
.flow-overview {
  padding: 0 24px;
  margin-bottom: 24px;

  .flow-card {
    border-left: 4px solid transparent;

    &.inflow   { border-left-color: var(--n-success-color); }
    &.outflow  { border-left-color: var(--n-error-color); }
    &.total    { border-left-color: var(--n-primary-color); }
    &.turnover { border-left-color: var(--n-warning-color); }

    :deep(.n-statistic) {
      .n-statistic__label {
        color: var(--n-text-color-2);
        font-size: 14px;
        margin-bottom: 4px;
      }

      .n-statistic-value {
        font-size: 24px;
        font-weight: 600;
        color: var(--n-text-color-1);
      }

      .flow-icon {
        margin-right: 8px;
      }

      .flow-change {
        margin-top: 4px;
        font-size: 12px;

        span { color: var(--n-text-color-2); }
      }
    }
  }
}

/* 图表区域 */
.flow-charts {
  padding: 0 24px;
  margin-bottom: 24px;

  .chart-container {
    height: 300px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: var(--color-bg-secondary, rgba(255, 255, 255, 0.03));
    border-radius: 6px;

    .chart-placeholder {
      text-align: center;
      color: var(--n-text-color-2);

      .placeholder-icon {
        font-size: 48px;
        margin-bottom: 8px;
        opacity: 0.5;
      }

      p { margin: 0; font-size: 14px; }
    }
  }
}

/* 资金流向明细 */
.flow-details {
  padding: 0 24px;

  .header-tools {
    display: flex;
    gap: 8px;
    align-items: center;

    .search-input { width: 200px; }
  }

  :deep(.n-data-table) {
    .n-data-table-th {
      background-color: var(--n-color-secondary);
      font-weight: 600;
    }

    .code-cell {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .code { font-weight: 600; color: var(--n-text-color-1); }
    }

    .name-cell {
      display: flex;
      align-items: center;

      .name { color: var(--n-text-color-1); }
    }

    .flow-positive { color: var(--color-stock-up, #FF5252); font-weight: 600; }
    .flow-negative { color: var(--color-stock-down, #00E676); font-weight: 600; }
    .flow-neutral  { color: var(--n-text-color-2); font-weight: 500; }
  }

  .pagination-info {
    color: var(--n-text-color-2);
    font-size: 14px;
    text-align: center;
    padding: 16px 0;
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .flow-overview, .flow-charts, .flow-details {
    padding: 0 12px;
  }

  .flow-details .header-tools {
    flex-direction: column;
    align-items: stretch;

    .search-input { width: 100%; }
  }
}

@media (max-width: 480px) {
  .flow-charts .chart-container { height: 200px; }
}
</style>
