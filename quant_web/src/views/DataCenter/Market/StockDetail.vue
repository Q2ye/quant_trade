<!--StockDetail.vue - Naive UI 实现的个股详情页-->
<template>
  <div class="stock-detail-page scrollbar-hide">
    <n-spin :show="loading">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <!-- 页面标题 -->
        <div class="page-header">
          <div class="header-content">
            <div class="title-section">
              <h1 class="page-title">{{ stock.name }} ({{ stock.code }})</h1>
              <p class="page-description">
                当前价 {{ stock.price }} |
                <span :class="stock.change > 0 ? 'text-up' : 'text-down'">
                  {{ stock.change > 0 ? '+' : '' }}{{ stock.change }} ({{ stock.change > 0 ? '+' : '' }}{{ stock.changePercent }}%)
                </span>
              </p>
            </div>
            <div class="header-actions">
              <n-button class="action-btn" @click="showBasketSelector = true" quaternary>
                <template #icon><SmartIcon name="Basket" /></template>
              </n-button>
              <n-button class="action-btn" @click="goBack" quaternary>
                <template #icon><SmartIcon name="ArrowLeft" /></template>
              </n-button>
            </div>
          </div>
        </div>

        <div class="stock-content">
          <!-- 左侧图表区域 -->
          <div class="chart-section">
            <n-card class="chart-container">
              <template #header>
                <div class="chart-header">
                  <div class="time-filters">
                    <n-radio-group v-model:value="timePeriod" size="small">
                      <n-radio-button value="1D">1日</n-radio-button>
                      <n-radio-button value="1W">1周</n-radio-button>
                      <n-radio-button value="1M">1月</n-radio-button>
                      <n-radio-button value="3M">3月</n-radio-button>
                      <n-radio-button value="1Y">1年</n-radio-button>
                    </n-radio-group>
                  </div>
                  <div class="chart-type">
                    <n-radio-group v-model:value="chartType" size="small">
                      <n-radio-button value="candlestick">K线</n-radio-button>
                      <n-radio-button value="line">分时</n-radio-button>
                    </n-radio-group>
                  </div>
                </div>
              </template>
              <div class="chart-wrapper">
                <div id="stockChart" class="chart"></div>
              </div>
            </n-card>

            <n-card class="indicator-selector">
              <n-select
                v-model:value="selectedIndicator"
                placeholder="选择技术指标"
                size="small"
              >
                <n-option label="MACD" value="macd"></n-option>
                <n-option label="KDJ" value="kdj"></n-option>
                <n-option label="RSI" value="rsi"></n-option>
                <n-option label="BOLL" value="boll"></n-option>
                <n-option label="成交量" value="volume"></n-option>
              </n-select>
            </n-card>
          </div>

          <!-- 右侧信息区域 -->
          <div class="info-section">
            <n-tabs v-model:value="activeTab" class="stock-tabs" type="line">
              <n-tab-pane name="quota" tab="盘口数据">
                <div class="quota-data">
                  <n-grid :cols="3" :x-gap="12" :y-gap="12">
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">今开</span>
                          <span class="quota-value">{{ stock.open }}</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">最高</span>
                          <span class="quota-value">{{ stock.high }}</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">最低</span>
                          <span class="quota-value">{{ stock.low }}</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">昨收</span>
                          <span class="quota-value">{{ stock.preClose }}</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">成交量</span>
                          <span class="quota-value">{{ stock.volume }}手</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">成交额</span>
                          <span class="quota-value">{{ stock.amount }}万</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">市盈率</span>
                          <span class="quota-value">{{ stock.pe }}</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">市净率</span>
                          <span class="quota-value">{{ stock.pb }}</span>
                        </div>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card size="small">
                        <div class="quota-item">
                          <span class="quota-label">总市值</span>
                          <span class="quota-value"
                            >{{ stock.marketCap }}亿</span
                          >
                        </div>
                      </n-card>
                    </n-gi>
                  </n-grid>
                </div>

                <n-card class="order-book" title="买卖五档" size="small">
                  <div class="order-table">
                    <div
                      class="order-row"
                      v-for="(bid, index) in bids"
                      :key="'bid' + index"
                    >
                      <div class="order-type buy">买{{ index + 1 }}</div>
                      <div class="order-price">{{ bid.price }}</div>
                      <div class="order-volume">{{ bid.volume }}</div>
                    </div>
                    <div class="divider"></div>
                    <div
                      class="order-row"
                      v-for="(ask, index) in asks"
                      :key="'ask' + index"
                    >
                      <div class="order-type sell">卖{{ index + 1 }}</div>
                      <div class="order-price">{{ ask.price }}</div>
                      <div class="order-volume">{{ ask.volume }}</div>
                    </div>
                  </div>
                </n-card>
              </n-tab-pane>

              <n-tab-pane name="financial" tab="财务数据">
                <n-card>
                  <n-data-table
                    :columns="financialColumns"
                    :data="financialData"
                    :bordered="false"
                    size="small"
                  />
                </n-card>
              </n-tab-pane>

              <n-tab-pane name="news" tab="公司资讯">
                <div class="news-list">
                  <n-card
                    v-for="item in news"
                    :key="item.id"
                    class="news-item"
                    size="small"
                    hoverable
                  >
                    <div class="news-title">{{ item.title }}</div>
                    <div class="news-meta">
                      <n-space>
                        <span class="news-time">{{ item.time }}</span>
                        <span class="news-source">{{ item.source }}</span>
                      </n-space>
                    </div>
                  </n-card>
                </div>
              </n-tab-pane>
            </n-tabs>
          </div>
        </div>
      </template>
    </n-spin>

    <!-- 篮子选择弹窗 -->
    <BasketSelectorDialog
      :show="showBasketSelector"
      :stock="{ symbol: stock.code, name: stock.name }"
      @update:show="showBasketSelector = $event"
      @added="onAddedToBasket"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, h } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";
import {
  NButton,
  NCard,
  NTabs,
  NTabPane,
  NRadioGroup,
  NRadioButton,
  NSelect,
  NGrid,
  NGridItem,
  NDataTable,
  DataTableColumns,
  NSpace,
  NSpin,
  NResult,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import BasketSelectorDialog from "@/components/basket/BasketSelectorDialog.vue";

const router = useRouter();
const message = useMessage();

const loading = ref(false);
const error = ref(false);

// 响应式数据
const stock = ref({
  code: "600519",
  name: "贵州茅台",
  price: "1785.45",
  change: 7.89,
  changePercent: 0.44,
  open: "1770.00",
  high: "1790.50",
  low: "1765.80",
  preClose: "1777.56",
  volume: "54321",
  amount: "968.42",
  pe: "38.45",
  pb: "12.78",
  marketCap: "22400",
});

const showBasketSelector = ref(false);
const timePeriod = ref("1D");
const chartType = ref("candlestick");
const selectedIndicator = ref("volume");
const activeTab = ref("quota");
const chart = ref<echarts.ECharts | null>(null);

const bids = ref([
  { price: "1785.44", volume: "15" },
  { price: "1785.43", volume: "32" },
  { price: "1785.42", volume: "28" },
  { price: "1785.41", volume: "45" },
  { price: "1785.40", volume: "36" },
]);

const asks = ref([
  { price: "1785.45", volume: "42" },
  { price: "1785.46", volume: "31" },
  { price: "1785.47", volume: "25" },
  { price: "1785.48", volume: "38" },
  { price: "1785.49", volume: "29" },
]);

interface FinancialItem {
  item: string;
  value: string;
  change: string;
}

const financialData = ref<FinancialItem[]>([
  { item: "营业收入", value: "1275.54亿", change: "+16.53%" },
  { item: "净利润", value: "627.16亿", change: "+19.42%" },
  { item: "每股收益", value: "49.93元", change: "+19.42%" },
  { item: "毛利率", value: "91.62%", change: "+0.85%" },
  { item: "净资产收益率", value: "31.41%", change: "+1.26%" },
]);

const financialColumns: DataTableColumns<FinancialItem> = [
  { title: "项目", key: "item" },
  { title: "数值", key: "value" },
  {
    title: "同比变化",
    key: "change",
    render(row) {
      const isPositive = row.change.includes("+");
      return h(
        "span",
        {
          style: {
            color: isPositive
              ? "var(--n-success-color)"
              : "var(--n-error-color)",
          },
        },
        row.change,
      );
    },
  },
];

const news = ref([
  {
    id: 1,
    title: "贵州茅台2023年净利润同比增长19.42%，超市场预期",
    time: "2023-08-10 09:30",
    source: "证券时报",
  },
  {
    id: 2,
    title: "茅台集团与华为达成战略合作，共建智慧酒业",
    time: "2023-08-09 14:25",
    source: "财经网",
  },
  {
    id: 3,
    title: "北向资金连续5日增持贵州茅台，累计净买入超20亿元",
    time: "2023-08-08 18:40",
    source: "东方财富",
  },
  {
    id: 4,
    title: "贵州茅台拟10派192.93元，分红总额超240亿元",
    time: "2023-08-07 10:15",
    source: "中国证券报",
  },
]);

// 方法
const goBack = () => {
  router.go(-1);
};

const onAddedToBasket = (_basketId: string) => {
  message.success("已添加到篮子");
};

const initChart = () => {
  const chartDom = document.getElementById("stockChart");
  if (!chartDom) return;

  chart.value = echarts.init(chartDom);

  const option = {
    backgroundColor: "transparent",
    grid: {
      left: "10%",
      right: "10%",
      bottom: "15%",
      top: "10%",
    },
    xAxis: {
      type: "category",
      data: [
        "09:30",
        "10:00",
        "10:30",
        "11:00",
        "11:30",
        "13:00",
        "13:30",
        "14:00",
        "14:30",
        "15:00",
      ],
      axisLine: {
        lineStyle: { color: "#333333" },
      },
      axisLabel: {
        color: "#888888",
      },
    },
    yAxis: {
      scale: true,
      axisLine: {
        lineStyle: { color: "#333333" },
      },
      splitLine: {
        lineStyle: { color: "rgba(255, 255, 255, 0.08)" },
      },
      axisLabel: {
        color: "#888888",
      },
    },
    series: [
      {
        type: "candlestick",
        data: [
          [1770, 1780, 1765, 1775],
          [1775, 1785, 1772, 1782],
          [1782, 1788, 1778, 1785],
          [1785, 1790, 1782, 1783],
          [1783, 1786, 1778, 1780],
          [1780, 1788, 1775, 1785],
          [1785, 1790, 1780, 1788],
          [1788, 1792, 1785, 1787],
          [1787, 1789, 1780, 1782],
          [1782, 1785, 1778, 1785],
        ],
        itemStyle: {
          color: "#FF5252",
          color0: "#00E676",
          borderColor: "#FF5252",
          borderColor0: "#00E676",
        },
      },
    ],
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
      },
      backgroundColor: "rgba(30, 30, 30, 0.95)",
      borderColor: "#444444",
      textStyle: {
        color: "#e0e0e0",
      },
    },
  };

  chart.value.setOption(option);
};

const handleResize = () => {
  if (chart.value) {
    chart.value.resize();
  }
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    initChart();
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

// 生命周期
onMounted(() => {
  loadData();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  if (chart.value) {
    chart.value.dispose();
  }
  window.removeEventListener("resize", handleResize);
});
</script>

<style scoped lang="scss">
.stock-detail-page {
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

/* 涨跌色 */
:deep(.text-up) {
  color: var(--color-stock-up, #FF5252);
  font-weight: 600;
}

:deep(.text-down) {
  color: var(--color-stock-down, #00E676);
  font-weight: 600;
}

/* 主要内容区域布局 */
.stock-content {
  display: flex;
  gap: 16px;
  padding: 0 24px;

  @media (max-width: 1024px) {
    flex-direction: column;
  }

  @media (max-width: 768px) {
    padding: 0 12px;
  }
}

/* 图表区域 */
.chart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-container {
  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.chart-wrapper {
  height: 400px;

  #stockChart {
    width: 100%;
    height: 100%;
  }
}

/* 信息区域 */
.info-section {
  width: 400px;

  @media (max-width: 1024px) {
    width: 100%;
  }
}

/* 买卖五档 */
.order-book {
  .order-table {
    display: flex;
    flex-direction: column;
  }
}

.order-row {
  display: flex;
  padding: 0.5rem 0;
  justify-content: space-between;
}

.order-type {
  width: 50px;
  text-align: center;
  font-weight: 600;
}

.buy {
  color: var(--color-stock-up, #FF5252);
}

.sell {
  color: var(--color-stock-down, #00E676);
}

.order-price {
  flex: 1;
  text-align: right;
  padding-right: 1rem;
  color: var(--n-text-color-1);
}

.order-volume {
  width: 80px;
  text-align: right;
  color: var(--n-text-color-2);
}

.divider {
  height: 1px;
  background: var(--n-border-color);
  margin: 0.5rem 0;
}

/* 盘口数据 */
.quota-item {
  text-align: center;

  .quota-label {
    display: block;
    color: var(--n-text-color-2);
    font-size: 0.875rem;
    margin-bottom: 0.25rem;
  }

  .quota-value {
    display: block;
    font-size: 1rem;
    font-weight: 600;
    color: var(--n-text-color-1);
  }
}

/* 新闻列表 */
.news-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.news-title {
  font-size: 1rem;
  margin-bottom: 0.5rem;
  color: var(--n-text-color-1);
  font-weight: 500;
}

.news-meta {
  font-size: 0.875rem;
  color: var(--n-text-color-2);
}

/* 响应式 */
@media (max-width: 768px) {
  .chart-header {
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .quota-data {
    :deep(.n-grid) {
      grid-template-columns: repeat(2, 1fr) !important;
    }
  }
}

@media (max-width: 480px) {
  .chart-wrapper { height: 250px; }

  .quota-data {
    :deep(.n-grid) {
      grid-template-columns: 1fr !important;
    }
  }
}
</style>
