<!-- MarketDashboard.vue - Naive UI 实现的市场仪表盘 -->
<template>
  <div class="market-dashboard-page scrollbar-hide">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场仪表盘</h1>
          <p class="page-description">股票、ETF、指数一站式市场概览与分析</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshAllData" :loading="loading" quaternary>
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
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="refreshAllData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <!-- 筛选条件区域 -->
        <div class="filter-section">
          <n-card class="filter-card">
            <div class="filter-content">
              <n-grid :cols="24" :x-gap="12" :y-gap="12">
                <!-- 数据维度 -->
                <n-gi :span="6">
                  <div class="filter-item">
                    <label class="filter-label" for="data-dimension"
                      >数据维度</label
                    >
                    <n-select
                      id="data-dimension"
                      v-model:value="activeDimension"
                      :options="dimensionOptions"
                      class="filter-select"
                      @update:value="handleDimensionChange"
                    />
                  </div>
                </n-gi>

                <!-- 市场板块 -->
                <n-gi :span="6">
                  <div class="filter-item market-sector-item">
                    <label class="filter-label" for="market-sector"
                      >市场板块</label
                    >
                    <n-select
                      id="market-sector"
                      v-model:value="filters.market"
                      :options="marketOptions"
                      class="filter-select market-sector-select"
                      multiple
                      placeholder="请选择"
                      @update:value="handleFilterChange"
                    />
                  </div>
                </n-gi>

                <!-- 排序方式 -->
                <n-gi :span="6">
                  <div class="filter-item sort-method-item">
                    <label class="filter-label" for="sort-method"
                      >排序方式</label
                    >
                    <n-select
                      id="sort-method"
                      v-model:value="sortBy"
                      :options="sortOptions"
                      class="filter-select sort-method-select"
                      @update:value="handleSortChange"
                    />
                  </div>
                </n-gi>

                <!-- 搜索框 -->
                <n-gi :span="6">
                  <div class="filter-item">
                    <label class="filter-label" for="search-input">搜索</label>
                    <n-input
                      id="search-input"
                      v-model:value="searchKeyword"
                      placeholder="搜索代码或名称..."
                      class="search-input"
                      clearable
                      @input="handleSearch"
                    >
                      <template #prefix>
                        <SmartIcon name="Search" />
                      </template>
                    </n-input>
                  </div>
                </n-gi>

                <!-- 操作按钮 -->
                <n-gi :span="24">
                  <div class="filter-actions">
                    <n-space>
                      <n-button @click="exportData" class="export-btn">
                        <template #icon>
                          <SmartIcon name="Download" />
                        </template>
                        导出数据
                      </n-button>
                      <n-button @click="resetFilters" class="reset-btn">
                        <template #icon>
                          <SmartIcon name="Close" />
                        </template>
                        重置筛选
                      </n-button>
                    </n-space>
                  </div>
                </n-gi>
              </n-grid>
            </div>
          </n-card>
        </div>

        <!-- 统计概览区域 -->
        <div class="stats-overview">
          <n-grid :cols="4" :x-gap="16" :y-gap="16" responsive="screen">
            <n-gi>
              <n-card class="stats-card" hoverable>
                <div class="stats-content">
                  <div class="stats-icon stocks">
                    <SmartIcon name="TrendingUp" />
                  </div>
                  <div class="stats-info">
                    <div class="stats-value">
                      {{ stats.totalStocks.toLocaleString() }}
                    </div>
                    <div class="stats-label">股票总数</div>
                  </div>
                </div>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card class="stats-card" hoverable>
                <div class="stats-content">
                  <div class="stats-icon etfs">
                    <SmartIcon name="PieChart" />
                  </div>
                  <div class="stats-info">
                    <div class="stats-value">
                      {{ stats.totalETFs.toLocaleString() }}
                    </div>
                    <div class="stats-label">ETF总数</div>
                  </div>
                </div>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card class="stats-card" hoverable>
                <div class="stats-content">
                  <div class="stats-icon indexes">
                    <SmartIcon name="BarChart" />
                  </div>
                  <div class="stats-info">
                    <div class="stats-value">
                      {{ stats.totalIndexes.toLocaleString() }}
                    </div>
                    <div class="stats-label">指数总数</div>
                  </div>
                </div>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card class="stats-card" hoverable>
                <div class="stats-content">
                  <div class="stats-icon market-cap">
                    <SmartIcon name="Currency" />
                  </div>
                  <div class="stats-info">
                    <div class="stats-value">
                      {{ formatMarketCap(stats.totalMarketCap) }}
                    </div>
                    <div class="stats-label">总市值</div>
                  </div>
                </div>
              </n-card>
            </n-gi>
          </n-grid>
        </div>

        <!-- 数据表格区域 -->
        <div class="data-section">
          <n-card class="data-card" hoverable>
            <template #header>
              <div class="data-card-header">
                <h3 class="data-card-title">{{ getTableTitle() }}</h3>
                <n-space>
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <n-button size="small" @click="toggleViewMode">
                        <template #icon>
                          <SmartIcon
                            :name="viewMode === 'table' ? 'Grid' : 'Table'"
                          />
                        </template>
                        {{ viewMode === "table" ? "卡片视图" : "表格视图" }}
                      </n-button>
                    </template>
                    {{
                      viewMode === "table" ? "切换到卡片视图" : "切换到表格视图"
                    }}
                  </n-tooltip>
                </n-space>
              </div>
            </template>

            <!-- 表格视图 -->
            <div v-if="viewMode === 'table'" class="table-container">
              <n-data-table
                :columns="getTableColumns()"
                :data="paginatedData"
                :loading="loading"
                :pagination="paginationReactive"
                :bordered="false"
                :row-class-name="getRowClassName"
                @update:sorter="handleSorterChange"
                @update:page="handlePageChange"
                @update:page-size="handlePageSizeChange"
                virtual-scroll
                :max-height="600"
              />
            </div>

            <!-- 卡片视图 -->
            <div v-else class="card-view-container">
              <n-empty
                v-if="filteredData.length === 0"
                description="暂无数据"
                class="empty-state"
              />
              <n-grid v-else :cols="responsiveCols" :x-gap="16" :y-gap="16">
                <n-gi v-for="item in paginatedData" :key="getItemKey(item)">
                  <n-card
                    class="data-card-item"
                    hoverable
                    @click="handleItemClick(item)"
                  >
                    <div class="card-content">
                      <div class="card-header">
                        <div class="item-code">{{ getItemCode(item) }}</div>
                        <div class="item-name">{{ getItemName(item) }}</div>
                      </div>
                      <div class="card-body">
                        <div
                          class="item-price"
                          :class="getPriceChangeClass(item)"
                        >
                          {{ getItemPrice(item) }}
                        </div>
                        <div
                          class="item-change"
                          :class="getPriceChangeClass(item)"
                        >
                          {{ getItemChange(item) }}
                        </div>
                      </div>
                      <div class="card-footer">
                        <n-tag
                          size="small"
                          :bordered="false"
                          class="item-market"
                        >
                          {{ getItemMarket(item) }}
                        </n-tag>
                        <div class="item-extra">{{ getItemExtra(item) }}</div>
                      </div>
                    </div>
                  </n-card>
                </n-gi>
              </n-grid>

              <!-- 卡片视图分页 -->
              <div class="pagination-wrapper" v-if="filteredData.length > 0">
                <n-pagination
                  v-model:page="pagination.page"
                  :page-count="pagination.pageCount"
                  :page-size="pagination.pageSize"
                  :page-sizes="pagination.pageSizes"
                  show-size-picker
                  @update:page="handlePageChange"
                  @update:page-size="handlePageSizeChange"
                />
              </div>
            </div>
          </n-card>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  type DataTableColumns,
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NGridItem,
  NGrid,
  NInput,
  NPagination,
  NSelect,
  NSpace,
  NTag,
  NTooltip,
  NResult,
  useDialog,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import marketAPI from "@/api/market";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();

// 类型定义
interface BaseItem {
  ts_code: string;
  name: string;
  market: string;
  current_price?: number;
  change?: number;
  change_percent?: number;
}

interface StockItem extends BaseItem {
  area: string;
  industry: string;
  market_cap?: number;
  list_date: string;
}

interface ETFItem extends BaseItem {
  mgr_name: string;
  index_name: string;
  fund_size?: number;
  expense_ratio?: number;
}

interface IndexItem extends BaseItem {
  fullname: string;
  publisher: string;
  category: string;
  base_point: number;
}

type DataItem = StockItem | ETFItem | IndexItem;
type SortOrder = "ascend" | "descend" | false;

// 响应式数据
const loading = ref(false);
const error = ref(false);
const activeDimension = ref<"stocks" | "etfs" | "indexes">("stocks");
const viewMode = ref<"table" | "card">("table");
const searchKeyword = ref("");
const sortBy = ref("code");
const sortOrder = ref<SortOrder>(false);

const filters = reactive({
  market: [] as string[],
  industry: [] as string[],
  area: [] as string[],
});

const stats = reactive({
  totalStocks: 4856,
  totalETFs: 589,
  totalIndexes: 234,
  totalMarketCap: 85670000000000,
});

// 分页配置
const createPagination = () => ({
  page: 1,
  pageSize: 20,
  pageCount: 1,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
});

const pagination = reactive(createPagination());

// 为 NDataTable 创建兼容的分页配置
const paginationReactive = computed(() => ({
  page: pagination.page,
  pageSize: pagination.pageSize,
  pageCount: pagination.pageCount,
  itemCount: pagination.itemCount,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (pageSize: number) => handlePageSizeChange(pageSize),
}));

// 响应式列数
const responsiveCols = computed(() => {
  if (typeof window === "undefined") return 4;
  const width = window.innerWidth;
  if (width < 768) return 1;
  if (width < 1024) return 2;
  if (width < 1440) return 3;
  return 4;
});

// 模拟数据
const allData = ref<Record<string, DataItem[]>>({
  stocks: [],
  etfs: [],
  indexes: [],
});

const tableData = computed(() => allData.value[activeDimension.value] || []);

// 过滤后的数据
const filteredData = computed(() => {
  let data = [...tableData.value];

  // 关键词搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase();
    data = data.filter(
      (item) =>
        item.ts_code.toLowerCase().includes(keyword) ||
        item.name.toLowerCase().includes(keyword),
    );
  }

  // 市场筛选
  if (filters.market.length > 0) {
    data = data.filter((item) => filters.market.includes(item.market));
  }

  // 排序
  if (sortBy.value && sortOrder.value) {
    data.sort((a, b) => {
      let aVal: any, bVal: any;

      switch (sortBy.value) {
        case "code":
          aVal = a.ts_code;
          bVal = b.ts_code;
          break;
        case "name":
          aVal = a.name;
          bVal = b.name;
          break;
        case "price":
          aVal = a.current_price || 0;
          bVal = b.current_price || 0;
          break;
        case "change":
          aVal = a.change_percent || 0;
          bVal = b.change_percent || 0;
          break;
        case "market_cap":
          aVal = (a as StockItem).market_cap || 0;
          bVal = (b as StockItem).market_cap || 0;
          break;
        default:
          return 0;
      }

      if (sortOrder.value === "ascend") {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
  }

  return data;
});

// 分页数据
const paginatedData = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize;
  const end = start + pagination.pageSize;
  return filteredData.value.slice(start, end);
});

// 选项配置
const dimensionOptions = [
  { label: "股票市场", value: "stocks" },
  { label: "ETF基金", value: "etfs" },
  { label: "指数行情", value: "indexes" },
];

const marketOptions = [
  { label: "主板", value: "主板" },
  { label: "创业板", value: "创业板" },
  { label: "科创板", value: "科创板" },
  { label: "北交所", value: "北交所" },
];

const sortOptions = [
  { label: "代码", value: "code" },
  { label: "名称", value: "name" },
  { label: "最新价", value: "price" },
  { label: "涨跌幅", value: "change" },
  { label: "市值", value: "market_cap" },
];

// 计算方法
const getTableTitle = () => {
  const titles = {
    stocks: "股票列表",
    etfs: "ETF基金列表",
    indexes: "指数行情列表",
  };
  return titles[activeDimension.value];
};

const getTableColumns = (): DataTableColumns<DataItem> => {
  const baseColumns: DataTableColumns<DataItem> = [
    {
      title: "代码",
      key: "ts_code",
      width: 120,
      sorter: true,
      fixed: "left",
    },
    {
      title: "名称",
      key: "name",
      width: 150,
      sorter: true,
      ellipsis: {
        tooltip: true,
      },
    },
    {
      title: "最新价",
      key: "current_price",
      width: 100,
      sorter: true,
      render: (rowData: DataItem) =>
        rowData.current_price ? `¥${rowData.current_price.toFixed(2)}` : "-",
    },
    {
      title: "涨跌幅",
      key: "change_percent",
      width: 100,
      sorter: true,
      render: (rowData: DataItem) => {
        if (!rowData.change_percent) return "-";
        const color =
          rowData.change_percent >= 0
            ? "var(--n-success-color)"
            : "var(--n-error-color)";
        const sign = rowData.change_percent >= 0 ? "+" : "";
        return h(
          "span",
          { style: { color, fontWeight: "bold" } },
          `${sign}${rowData.change_percent.toFixed(2)}%`,
        );
      },
    },
  ];

  const dimensionColumns: Record<string, DataTableColumns<DataItem>> = {
    stocks: [
      ...baseColumns,
      {
        title: "市值(亿)",
        key: "market_cap",
        width: 120,
        sorter: true,
        render: (rowData: DataItem) =>
          (rowData as StockItem).market_cap
            ? ((rowData as StockItem).market_cap! / 100000000).toFixed(2)
            : "-",
      },
      {
        title: "行业",
        key: "industry",
        width: 120,
        ellipsis: {
          tooltip: true,
        },
      },
      {
        title: "地区",
        key: "area",
        width: 80,
      },
      {
        title: "操作",
        key: "actions",
        width: 100,
        fixed: "right",
        render: (rowData: DataItem) =>
          h(
            NButton,
            {
              size: "small",
              type: "primary",
              onClick: (e: Event) => {
                e.stopPropagation();
                handleItemClick(rowData);
              },
            },
            { default: () => "详情" },
          ),
      },
    ],
    etfs: [
      ...baseColumns,
      {
        title: "管理人",
        key: "mgr_name",
        width: 120,
      },
      {
        title: "跟踪指数",
        key: "index_name",
        width: 150,
        ellipsis: {
          tooltip: true,
        },
      },
      {
        title: "规模(亿)",
        key: "fund_size",
        width: 100,
        render: (rowData: DataItem) =>
          (rowData as ETFItem).fund_size
            ? ((rowData as ETFItem).fund_size! / 100000000).toFixed(2)
            : "-",
      },
    ],
    indexes: [
      ...baseColumns,
      {
        title: "全称",
        key: "fullname",
        width: 200,
        ellipsis: {
          tooltip: true,
        },
      },
      {
        title: "发布方",
        key: "publisher",
        width: 120,
      },
      {
        title: "分类",
        key: "category",
        width: 100,
      },
    ],
  };

  return dimensionColumns[activeDimension.value] || baseColumns;
};

// 方法
const handleBack = () => {
  router.push("/market/overview");
};

const refreshAllData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await Promise.all([loadTableData(), loadStatsData()]);
    message.success("数据刷新成功");
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleDimensionChange = () => {
  pagination.page = 1;
  loadTableData();
};

const handleFilterChange = () => {
  pagination.page = 1;
  updatePagination();
};

const handleSortChange = () => {
  updatePagination();
};

const handleSearch = () => {
  pagination.page = 1;
  updatePagination();
};

const handleSorterChange = (sorter: any) => {
  if (sorter) {
    sortBy.value = sorter.columnKey;
    sortOrder.value = sorter.order;
  } else {
    sortOrder.value = false;
  }
  updatePagination();
};

const handlePageChange = (page: number) => {
  pagination.page = page;
};

const handlePageSizeChange = (size: number) => {
  pagination.pageSize = size;
  pagination.page = 1;
  updatePagination();
};

const toggleViewMode = () => {
  viewMode.value = viewMode.value === "table" ? "card" : "table";
};

const exportData = () => {
  dialog.info({
    title: "导出数据",
    content: "确定要导出当前数据吗？",
    positiveText: "导出",
    negativeText: "取消",
    onPositiveClick: () => {
      const dataStr = JSON.stringify(filteredData.value, null, 2);
      const dataBlob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `market_data_${activeDimension.value}_${new Date().getTime()}.json`;
      link.click();
      URL.revokeObjectURL(url);
      message.success("数据导出成功");
    },
  });
};

const resetFilters = () => {
  searchKeyword.value = "";
  filters.market = [];
  filters.industry = [];
  filters.area = [];
  sortBy.value = "code";
  sortOrder.value = false;
  pagination.page = 1;
  updatePagination();
  message.info("筛选条件已重置");
};

const formatMarketCap = (value: number) => {
  if (value >= 1000000000000) {
    return (value / 1000000000000).toFixed(2) + "万亿";
  } else if (value >= 100000000) {
    return (value / 100000000).toFixed(2) + "亿";
  }
  return value.toLocaleString();
};

const getRowClassName = (row: DataItem, index: number) => {
  return index % 2 === 0 ? "even-row" : "odd-row";
};

const handleItemClick = (item: DataItem) => {
  const routes = {
    stocks: `/market/stock/${item.ts_code}`,
    etfs: `/market/etf/${item.ts_code}`,
    indexes: `/market/index/${item.ts_code}`,
  };
  router.push(routes[activeDimension.value]);
};

// 卡片视图相关方法
const getItemKey = (item: DataItem) => item.ts_code;
const getItemCode = (item: DataItem) => item.ts_code;
const getItemName = (item: DataItem) => item.name;
const getItemPrice = (item: DataItem) =>
  item.current_price ? `¥${item.current_price.toFixed(2)}` : "-";
const getItemChange = (item: DataItem) => {
  if (!item.change_percent) return "-";
  const sign = item.change_percent >= 0 ? "+" : "";
  return `${sign}${item.change_percent.toFixed(2)}%`;
};
const getPriceChangeClass = (item: DataItem) => {
  if (!item.change_percent) return "neutral";
  return item.change_percent >= 0 ? "positive" : "negative";
};
const getItemMarket = (item: DataItem) => item.market;
const getItemExtra = (item: DataItem) => {
  if ("industry" in item) return (item as StockItem).industry;
  if ("mgr_name" in item) return (item as ETFItem).mgr_name;
  if ("publisher" in item) return (item as IndexItem).publisher;
  return "";
};

// 更新分页信息
const updatePagination = () => {
  pagination.itemCount = filteredData.value.length;
  pagination.pageCount = Math.ceil(pagination.itemCount / pagination.pageSize);

  if (pagination.page > pagination.pageCount && pagination.pageCount > 0) {
    pagination.page = pagination.pageCount;
  }
};

const generateMockData = () => ({
  stocks: Array.from({ length: 185 }, (_, i) => ({
    ts_code: `00000${i + 1}.${i % 2 === 0 ? "SH" : "SZ"}`,
    name: `股票${i + 1}`,
    market:
      i % 4 === 0
        ? "主板"
        : i % 4 === 1
          ? "创业板"
          : i % 4 === 2
            ? "科创板"
            : "北交所",
    current_price: 10 + Math.random() * 100,
    change: (Math.random() - 0.5) * 10,
    change_percent: (Math.random() - 0.5) * 20,
    area: i % 3 === 0 ? "北京" : i % 3 === 1 ? "上海" : "深圳",
    industry:
      i % 5 === 0
        ? "科技"
        : i % 5 === 1
          ? "金融"
          : i % 5 === 2
            ? "消费"
            : i % 5 === 3
              ? "医药"
              : "制造",
    market_cap: 1000000000 + Math.random() * 100000000000,
    list_date: "2020-01-01",
  })),
  etfs: Array.from({ length: 89 }, (_, i) => ({
    ts_code: `51${String(i + 1).padStart(4, "0")}.SH`,
    name: `ETF${i + 1}`,
    market: "主板",
    current_price: 1 + Math.random() * 5,
    change: (Math.random() - 0.5) * 0.5,
    change_percent: (Math.random() - 0.5) * 10,
    mgr_name:
      i % 3 === 0 ? "华夏基金" : i % 3 === 1 ? "易方达" : "华泰柏瑞",
    index_name:
      i % 4 === 0
        ? "沪深300"
        : i % 4 === 1
          ? "中证500"
          : i % 4 === 2
            ? "创业板指"
            : "科创50",
    fund_size: 100000000 + Math.random() * 10000000000,
    expense_ratio: 0.1 + Math.random() * 0.5,
  })),
  indexes: Array.from({ length: 67 }, (_, i) => ({
    ts_code: i % 2 === 0 ? `00000${i + 1}.SH` : `39900${i + 1}.SZ`,
    name: i % 2 === 0 ? `上证${i + 1}` : `深证${i + 1}`,
    market: i % 2 === 0 ? "上证" : "深证",
    current_price: 1000 + Math.random() * 5000,
    change: (Math.random() - 0.5) * 100,
    change_percent: (Math.random() - 0.5) * 5,
    fullname: i % 2 === 0 ? `上海证券${i + 1}指数` : `深圳证券${i + 1}指数`,
    publisher: i % 2 === 0 ? "上交所" : "深交所",
    category:
      i % 3 === 0 ? "综合指数" : i % 3 === 1 ? "成份指数" : "主题指数",
    base_point: 1000,
  })),
});

// 数据加载
const loadTableData = async () => {
  loading.value = true;
  try {
    const stockRes = await marketAPI.getStocks({ limit: 200 }).catch(() => null);
    if (stockRes?.items && stockRes.items.length > 0) {
      const stocks = stockRes.items.map((s: any, i: number) => ({
        ts_code: s.ts_code ?? s.code ?? "",
        name: s.name ?? "",
        market: s.market ?? s.exchange ?? "",
        current_price: s.current_price ?? s.close ?? 0,
        change: s.change ?? 0,
        change_percent: s.pct_chg ?? s.change_percent ?? 0,
        area: s.area ?? "",
        industry: s.industry ?? "",
        market_cap: s.market_cap ?? s.total_mv ?? 0,
        list_date: s.list_date ?? "",
      }));
      allData.value = { stocks, etfs: [], indexes: [] };
    } else {
      allData.value = generateMockData();
    }
    updatePagination();
  } catch {
    allData.value = generateMockData();
    updatePagination();
  } finally {
    loading.value = false;
  }
};

const loadStatsData = async () => {
  await new Promise((resolve) => setTimeout(resolve, 300));
};

// 监听数据变化更新分页
watch([filteredData, pagination.pageSize], updatePagination);

// 生命周期
onMounted(() => {
  loadTableData();
  loadStatsData();
});
</script>

<style scoped lang="scss">
.market-dashboard-page {
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

/* 筛选区域 */
.filter-section {
  padding: 0 24px;
  margin-bottom: 24px;

  .filter-content {
    .filter-item {
      margin-bottom: 8px;

      .filter-label {
        display: block;
        margin-bottom: 4px;
        font-size: 14px;
        font-weight: 500;
        color: var(--n-text-color-2);
      }

      .filter-select {
        width: 100%;
      }

      .search-input {
        width: 100%;
      }
    }

    .filter-actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--n-border-color);
    }
  }
}

/* 统计概览 */
.stats-overview {
  padding: 0 24px;
  margin-bottom: 24px;

  .stats-card {
    .stats-content {
      display: flex;
      align-items: center;
      gap: 16px;

      .stats-icon {
        width: 48px;
        height: 48px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        flex-shrink: 0;

        &.stocks     { background: rgba(103, 194, 58, 0.12);  color: var(--n-success-color); }
        &.etfs       { background: rgba(23, 162, 184, 0.12);  color: var(--n-info-color); }
        &.indexes    { background: rgba(210, 153, 34, 0.12);  color: var(--n-warning-color); }
        &.market-cap { background: rgba(68, 138, 255, 0.12);  color: var(--n-primary-color); }
      }

      .stats-info {
        flex: 1;

        .stats-value {
          font-size: 24px;
          font-weight: 600;
          color: var(--n-text-color-1);
          margin-bottom: 4px;
        }

        .stats-label {
          font-size: 14px;
          color: var(--n-text-color-2);
        }
      }
    }
  }
}

/* 数据表格区域 */
.data-section {
  padding: 0 24px;

  .data-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .data-card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--n-text-color-1);
      margin: 0;
    }
  }

  .table-container {
    overflow-x: auto;

    :deep(.n-data-table) {
      .n-data-table-th {
        background-color: var(--n-color-secondary);
        font-weight: 600;
      }
    }
  }

  .card-view-container {
    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      color: var(--n-text-color-2);
    }

    .data-card-item {
      cursor: pointer;
      transition: all 0.3s ease;

      &:hover {
        border-color: var(--n-primary-color);
        transform: translateY(-2px);
      }

      .card-content {
        .card-header {
          margin-bottom: 12px;

          .item-code {
            font-size: 14px;
            font-weight: 600;
            color: var(--n-primary-color);
            margin-bottom: 4px;
          }

          .item-name {
            font-size: 16px;
            font-weight: 500;
            color: var(--n-text-color-1);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }

        .card-body {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          margin-bottom: 12px;

          .item-price {
            font-size: 20px;
            font-weight: 600;

            &.positive  { color: var(--color-stock-up, #FF5252); }
            &.negative  { color: var(--color-stock-down, #00E676); }
            &.neutral   { color: var(--n-text-color-2); }
          }

          .item-change {
            font-size: 14px;
            font-weight: 500;

            &.positive  { color: var(--color-stock-up, #FF5252); }
            &.negative  { color: var(--color-stock-down, #00E676); }
            &.neutral   { color: var(--n-text-color-2); }
          }
        }

        .card-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;

          .item-market {
            background: rgba(68, 138, 255, 0.12);
            color: var(--n-primary-color);
          }

          .item-extra {
            font-size: 12px;
            color: var(--n-text-color-2);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 100px;
          }
        }
      }
    }

    .pagination-wrapper {
      margin-top: 24px;
      display: flex;
      justify-content: center;
    }
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .filter-section, .stats-overview, .data-section {
    padding: 0 12px;
  }
}
</style>
