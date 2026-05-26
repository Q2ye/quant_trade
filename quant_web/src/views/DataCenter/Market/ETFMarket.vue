<!-- ETFMarket.vue - ETF行情页 - 统一样式 -->
<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref, nextTick } from "vue";
import {
  NButton,
  NCard,
  NDataTable,
  NInput,
  NSelect,
  NSpin,
  NResult,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import BasketSelectorDialog from "@/components/basket/BasketSelectorDialog.vue";
import * as echarts from "echarts";

const message = useMessage();

const loading = ref(false);
const error = ref(false);
const selectedCategory = ref("all");
const searchKeyword = ref("");

const categoryOptions = [
  { label: "全部", value: "all" },
  { label: "股票型", value: "stock" },
  { label: "债券型", value: "bond" },
  { label: "商品型", value: "commodity" },
  { label: "货币型", value: "currency" },
  { label: "跨境型", value: "overseas" },
];

interface ETFRow {
  code: string;
  name: string;
  category: string;
  price: string;
  change: number;
  volume: string;
  amount: string;
  index: string;
}

const topRisingETFs = ref<ETFRow[]>([
  { code: "515790", name: "光伏ETF", category: "股票型", price: "1.245", change: 3.75, volume: "12345", amount: "5432", index: "中证光伏产业指数" },
  { code: "159995", name: "芯片ETF", category: "股票型", price: "1.087", change: 2.94, volume: "23456", amount: "6543", index: "国证半导体芯片指数" },
  { code: "515030", name: "新能源车ETF", category: "股票型", price: "1.325", change: 2.32, volume: "34567", amount: "7654", index: "中证新能源汽车指数" },
  { code: "512480", name: "半导体ETF", category: "股票型", price: "0.985", change: 1.96, volume: "45678", amount: "8765", index: "中证全指半导体指数" },
  { code: "512000", name: "券商ETF", category: "股票型", price: "0.876", change: 1.85, volume: "56789", amount: "9876", index: "中证全指证券公司指数" },
]);

const allETFs = ref<ETFRow[]>([
  { code: "510300", name: "沪深300ETF", category: "股票型", price: "3.875", change: 0.78, volume: "123456", amount: "12345", index: "沪深300指数" },
  { code: "510050", name: "上证50ETF", category: "股票型", price: "2.765", change: 0.45, volume: "98765", amount: "8765", index: "上证50指数" },
  { code: "159915", name: "创业板ETF", category: "股票型", price: "2.345", change: 1.25, volume: "87654", amount: "7654", index: "创业板指数" },
  { code: "515790", name: "光伏ETF", category: "股票型", price: "1.245", change: 3.75, volume: "12345", amount: "5432", index: "中证光伏产业指数" },
  { code: "159995", name: "芯片ETF", category: "股票型", price: "1.087", change: 2.94, volume: "23456", amount: "6543", index: "国证半导体芯片指数" },
  { code: "511010", name: "国债ETF", category: "债券型", price: "130.456", change: 0.12, volume: "3456", amount: "4321", index: "上证5年期国债指数" },
  { code: "518800", name: "黄金ETF", category: "商品型", price: "4.325", change: 0.45, volume: "4567", amount: "3210", index: "上海金现货合约" },
  { code: "511990", name: "货币ETF", category: "货币型", price: "100.025", change: 0.01, volume: "5678", amount: "2109", index: "银行间市场利率" },
  { code: "513500", name: "标普500ETF", category: "跨境型", price: "1.345", change: -0.25, volume: "6789", amount: "1098", index: "标普500指数" },
]);

const showBasketSelector = ref(false);
const selectedETFRow = ref<ETFRow | null>(null);

let flowChart: echarts.ECharts | null = null;
let categoryChart: echarts.ECharts | null = null;

const filteredETFs = computed(() => {
  let result = allETFs.value;
  if (selectedCategory.value !== "all") {
    result = result.filter((etf) => etf.category === selectedCategory.value);
  }
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter((etf) => etf.code.toLowerCase().includes(kw) || etf.name.toLowerCase().includes(kw));
  }
  return result;
});

const topRisingColumns = [
  { title: "代码", key: "code", width: 80 },
  { title: "名称", key: "name" },
  { title: "最新价", key: "price" },
  {
    title: "涨跌幅", key: "change",
    render: (row: ETFRow) => h("span", { class: row.change > 0 ? "text-up" : "text-down" }, `${row.change > 0 ? "+" : ""}${row.change}%`),
  },
  { title: "成交量(万)", key: "volume" },
  {
    title: "操作", key: "actions",
    render: (row: ETFRow) => h(NButton, { size: "small", onClick: () => viewETFDetail(row) }, { default: () => "详情" }),
  },
];

const etfListColumns = [
  { title: "代码", key: "code", width: 100 },
  { title: "名称", key: "name" },
  { title: "类型", key: "category", width: 100 },
  { title: "最新价", key: "price", width: 100 },
  {
    title: "涨跌幅", key: "change", width: 120,
    render: (row: ETFRow) => h("span", { class: row.change > 0 ? "text-up" : "text-down" }, `${row.change > 0 ? "+" : ""}${row.change}%`),
  },
  { title: "成交量(万)", key: "volume", width: 120 },
  { title: "成交额(万)", key: "amount", width: 120 },
  { title: "跟踪指数", key: "index", width: 180 },
  {
    title: "操作", key: "actions", width: 150,
    render: (row: ETFRow) => h("div", { class: "action-buttons" }, [
      h(NButton, { size: "small", onClick: () => viewETFDetail(row) }, { default: () => "详情" }),
      h(NButton, { size: "small", type: "primary", onClick: () => openBasketSelector(row), style: { marginLeft: "8px" } }, { default: () => "加篮子" }),
    ]),
  },
];

const initFlowChart = () => {
  const dom = document.getElementById("etf-fund-flow-chart");
  if (!dom) return;
  flowChart = echarts.init(dom);
  flowChart.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { data: ["流入", "流出"], right: 10, top: 10, textStyle: { color: "#888888" } },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: { type: "category", data: ["周一", "周二", "周三", "周四", "周五"] },
    yAxis: { type: "value", name: "亿元" },
    series: [
      { name: "流入", type: "bar", stack: "total", data: [12.3, 15.2, 8.7, 17.8, 13.5], itemStyle: { color: "#67c23a" } },
      { name: "流出", type: "bar", stack: "total", data: [-8.5, -7.2, -6.8, -9.3, -7.9], itemStyle: { color: "#f56c6c" } },
    ],
  });
};

const initCategoryChart = () => {
  const dom = document.getElementById("etf-category-chart");
  if (!dom) return;
  categoryChart = echarts.init(dom);
  categoryChart.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "item", formatter: "{a} <br/>{b}: {c} ({d}%)" },
    legend: { orient: "vertical", right: 10, top: "center", textStyle: { color: "#888888" } },
    series: [{
      name: "ETF分类", type: "pie", radius: ["40%", "70%"],
      itemStyle: { borderRadius: 6, borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 18, fontWeight: "bold" } },
      data: [
        { value: 156, name: "股票型" },
        { value: 32, name: "债券型" },
        { value: 28, name: "商品型" },
        { value: 24, name: "货币型" },
        { value: 45, name: "跨境型" },
      ],
    }],
  });
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    await nextTick();
    initFlowChart();
    initCategoryChart();
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const refreshData = () => loadData().then(() => message.success("ETF数据已刷新"));
const viewETFDetail = (etf: ETFRow) => message.info(`查看ETF详情: ${etf.code}`);

const openBasketSelector = (etf: ETFRow) => {
  selectedETFRow.value = etf;
  showBasketSelector.value = true;
};

const onAddedToBasket = (_basketId: string) => {
  message.success("已添加到篮子");
  selectedETFRow.value = null;
};

const handleResize = () => {
  flowChart?.resize();
  categoryChart?.resize();
};

onMounted(() => {
  loadData();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  flowChart?.dispose();
  categoryChart?.dispose();
  window.removeEventListener("resize", handleResize);
});
</script>

<template>
  <div class="etf-market-page scrollbar-hide">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">ETF行情</h1>
          <p class="page-description">实时追踪 ETF 基金行情、资金流向与分类分布</p>
        </div>
        <div class="header-actions">
          <n-select
            v-model:value="selectedCategory"
            :options="categoryOptions"
            placeholder="选择分类"
            style="width: 140px"
          />
          <n-input
            v-model:value="searchKeyword"
            placeholder="搜索ETF名称或代码"
            clearable
            style="width: 200px"
          >
            <template #prefix><SmartIcon name="Search" /></template>
          </n-input>
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
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
            <n-button type="primary" @click="loadData">重试</n-button>
          </template>
        </n-result>

        <template v-else>
          <!-- ETF 数据网格 -->
          <div class="etf-grid">
            <n-card class="grid-card" title="ETF资金流向">
              <div id="etf-fund-flow-chart" class="chart"></div>
            </n-card>

            <n-card class="grid-card" title="ETF分类分布">
              <div id="etf-category-chart" class="chart"></div>
            </n-card>

            <n-card class="grid-card" title="ETF涨幅榜">
              <n-data-table :columns="topRisingColumns" :data="topRisingETFs" :bordered="false" size="small" />
            </n-card>
          </div>

          <!-- ETF 列表 -->
          <n-card class="etf-list-card" title="ETF列表">
            <n-data-table :columns="etfListColumns" :data="filteredETFs" :bordered="false" size="small" />
          </n-card>
        </template>
      </n-spin>
    </div>

    <!-- 篮子选择弹窗 -->
    <BasketSelectorDialog
      v-if="selectedETFRow"
      :show="showBasketSelector"
      :stock="{ symbol: selectedETFRow.code, name: selectedETFRow.name }"
      @update:show="showBasketSelector = $event"
      @added="onAddedToBasket"
    />
  </div>
</template>

<style scoped lang="scss">
.etf-market-page {
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

.chart {
  width: 100%;
  height: 300px;
}

.etf-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  padding: 0 24px;
  margin-bottom: 24px;
}

.grid-card {
  transition: all 0.3s ease;
}

.etf-list-card {
  margin: 0 24px;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

:deep(.text-up) {
  color: var(--color-stock-up, #FF5252);
  font-weight: 600;
}

:deep(.text-down) {
  color: var(--color-stock-down, #00E676);
  font-weight: 600;
}

@media (max-width: 1024px) {
  .etf-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .etf-grid {
    padding: 0 12px;
    grid-template-columns: 1fr;
  }

  .etf-list-card {
    margin: 0 12px;
  }
}

@media (max-width: 480px) {
  .chart { height: 200px; }
}
</style>
