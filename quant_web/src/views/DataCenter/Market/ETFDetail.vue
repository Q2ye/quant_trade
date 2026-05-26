<!--ETF详情页 - 基于 Naive UI 重构-->
<template>
  <div class="etf-detail bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">{{ etf.name }} ({{ etf.code }})</h1>
          <p class="page-description">
            <span class="current-price">{{ etf.price }}</span>
            <span :class="['price-change', etf.change > 0 ? 'positive' : 'negative']">
              {{ etf.change > 0 ? "+" : "" }}{{ etf.change }} ({{ etf.change > 0 ? "+" : "" }}{{ etf.changePercent }}%)
            </span>
          </p>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="showBasketSelector = true">加入篮子</n-button>
          <n-button class="action-btn" @click="goBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <n-spin :show="loading">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadETFData">重试</n-button>
        </template>
      </n-result>

      <div v-else class="etf-content">
        <!-- 左侧图表区域 -->
        <div class="chart-section">
          <n-card class="chart-container" title="价格走势">
            <template #header-extra>
              <div class="chart-controls">
                <n-radio-group v-model:value="timePeriod" size="small">
                  <n-radio-button value="1D">1日</n-radio-button>
                  <n-radio-button value="1W">1周</n-radio-button>
                  <n-radio-button value="1M">1月</n-radio-button>
                  <n-radio-button value="3M">3月</n-radio-button>
                  <n-radio-button value="1Y">1年</n-radio-button>
                </n-radio-group>
                <n-radio-group v-model:value="chartType" size="small">
                  <n-radio-button value="line">分时</n-radio-button>
                  <n-radio-button value="candlestick">K线</n-radio-button>
                </n-radio-group>
              </div>
            </template>
            <div class="chart-wrapper">
              <div id="etfChart" class="chart"></div>
            </div>
          </n-card>

          <n-card class="indicator-selector" title="技术指标">
            <n-select
              v-model:value="selectedIndicator"
              placeholder="选择技术指标"
              size="small"
              :options="indicatorOptions"
            />
          </n-card>
        </div>

        <!-- 右侧信息区域 -->
        <div class="info-section">
          <n-card class="etf-tabs">
            <n-tabs v-model:value="activeTab" type="line">
              <n-tab-pane name="basic" tab="基本信息">
                <div class="basic-info">
                  <div class="info-row">
                    <div class="info-item">
                      <span class="info-label">基金全称</span>
                      <span class="info-value">{{ etf.fullName }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">基金管理人</span>
                      <span class="info-value">{{ etf.mgrName }}</span>
                    </div>
                  </div>
                  <div class="info-row">
                    <div class="info-item">
                      <span class="info-label">跟踪指数</span>
                      <span class="info-value"
                        >{{ etf.indexName }} ({{ etf.indexCode }})</span
                      >
                    </div>
                    <div class="info-item">
                      <span class="info-label">基金规模</span>
                      <span class="info-value">{{ etf.fundSize }}亿元</span>
                    </div>
                  </div>
                  <div class="info-row">
                    <div class="info-item">
                      <span class="info-label">管理费率</span>
                      <span class="info-value">{{ etf.expenseRatio }}%</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">托管费率</span>
                      <span class="info-value">{{ etf.custodyFee }}%</span>
                    </div>
                  </div>
                  <div class="info-row">
                    <div class="info-item">
                      <span class="info-label">成立日期</span>
                      <span class="info-value">{{ etf.setupDate }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">上市日期</span>
                      <span class="info-value">{{ etf.listDate }}</span>
                    </div>
                  </div>
                </div>

                <n-card class="market-data" title="盘口数据">
                  <div class="quota-data">
                    <div class="quota-row">
                      <div class="quota-item">
                        <span class="quota-label">今开</span>
                        <span class="quota-value">{{ etf.open }}</span>
                      </div>
                      <div class="quota-item">
                        <span class="quota-label">最高</span>
                        <span class="quota-value">{{ etf.high }}</span>
                      </div>
                      <div class="quota-item">
                        <span class="quota-label">最低</span>
                        <span class="quota-value">{{ etf.low }}</span>
                      </div>
                    </div>
                    <div class="quota-row">
                      <div class="quota-item">
                        <span class="quota-label">昨收</span>
                        <span class="quota-value">{{ etf.preClose }}</span>
                      </div>
                      <div class="quota-item">
                        <span class="quota-label">成交量</span>
                        <span class="quota-value">{{ etf.volume }}万手</span>
                      </div>
                      <div class="quota-item">
                        <span class="quota-label">成交额</span>
                        <span class="quota-value">{{ etf.amount }}万元</span>
                      </div>
                    </div>
                    <div class="quota-row">
                      <div class="quota-item">
                        <span class="quota-label">净值</span>
                        <span class="quota-value">{{ etf.nav }}</span>
                      </div>
                      <div class="quota-item">
                        <span class="quota-label">溢价率</span>
                        <span
                          :class="[
                            'quota-value',
                            etf.premiumRate > 0 ? 'positive' : 'negative',
                          ]"
                        >
                          {{ etf.premiumRate > 0 ? "+" : ""
                          }}{{ etf.premiumRate }}%
                        </span>
                      </div>
                      <div class="quota-item">
                        <span class="quota-label">换手率</span>
                        <span class="quota-value">{{ etf.turnoverRate }}%</span>
                      </div>
                    </div>
                  </div>
                </n-card>
              </n-tab-pane>

              <n-tab-pane name="constituents" tab="成分股">
                <n-card>
                  <n-data-table
                    :columns="constituentColumns"
                    :data="constituents"
                    :max-height="400"
                    :virtual-scroll="true"
                  />
                </n-card>
              </n-tab-pane>

              <n-tab-pane name="industry" tab="行业分布">
                <n-card>
                  <div class="industry-chart">
                    <div
                      id="industryChart"
                      class="chart"
                      style="height: 400px"
                    ></div>
                  </div>
                </n-card>
              </n-tab-pane>

              <n-tab-pane name="news" tab="相关资讯">
                <n-card>
                  <div class="news-list">
                    <div v-for="item in news" :key="item.id" class="news-item">
                      <div class="news-title">{{ item.title }}</div>
                      <div class="news-meta">
                        <span class="news-time">{{ item.time }}</span>
                        <span class="news-source">{{ item.source }}</span>
                      </div>
                    </div>
                  </div>
                </n-card>
              </n-tab-pane>
            </n-tabs>
          </n-card>
        </div>
      </div>
    </n-spin>

    <!-- 篮子选择弹窗 -->
    <BasketSelectorDialog
      :show="showBasketSelector"
      :stock="{ symbol: etf.code, name: etf.name }"
      @update:show="showBasketSelector = $event"
      @added="onAddedToBasket"
    />
  </div>
</template>

<script>
import { defineComponent, ref, onMounted, onBeforeUnmount, h } from "vue";
import {
  NCard,
  NButton,
  NIcon,
  NTabs,
  NTabPane,
  NRadioGroup,
  NRadioButton,
  NSelect,
  NDataTable,
  NSpin,
  NResult,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import BasketSelectorDialog from "@/components/basket/BasketSelectorDialog.vue";
import * as echarts from "echarts";

export default defineComponent({
  name: "ETFDetail",
  components: {
    SmartIcon,
    BasketSelectorDialog,
  },
  props: {
    code: {
      type: String,
      required: true,
    },
  },
  setup(props) {
    const message = useMessage();
    const loading = ref(false);
    const error = ref(false);

    const etf = ref({
      code: "510300",
      name: "沪深300ETF",
      fullName: "华泰柏瑞沪深300交易型开放式指数证券投资基金",
      price: "3.875",
      change: 0.78,
      changePercent: 0.44,
      open: "3.850",
      high: "3.880",
      low: "3.845",
      preClose: "3.845",
      volume: "12345.67",
      amount: "47890.12",
      nav: "3.872",
      premiumRate: 0.08,
      turnoverRate: 12.34,
      mgrName: "华泰柏瑞基金",
      indexCode: "000300.SH",
      indexName: "沪深300指数",
      fundSize: "850.25",
      expenseRatio: 0.5,
      custodyFee: 0.1,
      setupDate: "2012-05-04",
      listDate: "2012-05-28",
    });

    const showBasketSelector = ref(false);
    const timePeriod = ref("1D");
    const chartType = ref("line");
    const selectedIndicator = ref("volume");
    const activeTab = ref("basic");

    const indicatorOptions = [
      { label: "成交量", value: "volume" },
      { label: "MACD", value: "macd" },
      { label: "RSI", value: "rsi" },
      { label: "布林带", value: "boll" },
    ];

    const constituents = ref([
      {
        code: "600519",
        name: "贵州茅台",
        weight: 0.0523,
        industry: "食品饮料",
        close: "1785.45",
        change: 0.44,
      },
      {
        code: "300750",
        name: "宁德时代",
        weight: 0.0315,
        industry: "电力设备",
        close: "185.67",
        change: 1.23,
      },
      {
        code: "000858",
        name: "五粮液",
        weight: 0.0241,
        industry: "食品饮料",
        close: "152.34",
        change: -0.56,
      },
      {
        code: "601318",
        name: "中国平安",
        weight: 0.0218,
        industry: "非银金融",
        close: "45.67",
        change: 0.89,
      },
      {
        code: "600036",
        name: "招商银行",
        weight: 0.0195,
        industry: "银行",
        close: "32.45",
        change: 0.31,
      },
      {
        code: "000333",
        name: "美的集团",
        weight: 0.0156,
        industry: "家用电器",
        close: "56.78",
        change: -0.12,
      },
      {
        code: "601888",
        name: "中国中免",
        weight: 0.0142,
        industry: "商贸零售",
        close: "87.65",
        change: 2.34,
      },
      {
        code: "601012",
        name: "隆基绿能",
        weight: 0.0137,
        industry: "电力设备",
        close: "23.45",
        change: -1.23,
      },
    ]);

    const news = ref([
      {
        id: 1,
        title: "沪深300ETF规模突破850亿元，创历史新高",
        time: "2023-08-10 09:30",
        source: "证券时报",
      },
      {
        id: 2,
        title: "机构资金持续流入宽基ETF，市场信心逐步恢复",
        time: "2023-08-09 14:25",
        source: "财经网",
      },
      {
        id: 3,
        title: "沪深300指数成分股调整在即，多只个股将受益",
        time: "2023-08-08 18:40",
        source: "东方财富",
      },
      {
        id: 4,
        title: "ETF互联互通扩容，外资加速配置A股核心资产",
        time: "2023-08-07 10:15",
        source: "中国证券报",
      },
    ]);

    const chart = ref(null);
    const industryChart = ref(null);

    // 成分股表格列定义
    const constituentColumns = [
      {
        title: "股票代码",
        key: "code",
        width: 120,
      },
      {
        title: "股票名称",
        key: "name",
        width: 150,
      },
      {
        title: "权重",
        key: "weight",
        width: 100,
        render: (row) => (row.weight * 100).toFixed(2) + "%",
      },
      {
        title: "行业",
        key: "industry",
        width: 120,
      },
      {
        title: "最新价",
        key: "close",
        width: 100,
      },
      {
        title: "涨跌幅",
        key: "change",
        width: 100,
        render: (row) => {
          const isPositive = row.change > 0;
          return h(
            "span",
            {
              class: isPositive ? "positive" : "negative",
            },
            `${isPositive ? "+" : ""}${row.change}%`,
          );
        },
      },
      {
        title: "操作",
        key: "actions",
        width: 100,
        render: (row) =>
          h(
            NButton,
            {
              type: "primary",
              size: "small",
              text: true,
              onClick: () => viewStockDetail(row),
            },
            { default: () => "查看" },
          ),
      },
    ];

    const goBack = () => {
      window.history.back();
    };

    const onAddedToBasket = (_basketId) => {
      message.success("已添加到篮子");
    };

    const viewStockDetail = (stock) => {
      console.log("查看股票详情:", stock.code);
      // 实际项目中这里会导航到股票详情页
    };

    const loadETFData = async () => {
      loading.value = true;
      error.value = false;
      try {
        await new Promise((r) => setTimeout(r, 300));
        initChart();
        initIndustryChart();
      } catch {
        error.value = true;
      } finally {
        loading.value = false;
      }
    };

    const initChart = () => {
      const chartDom = document.getElementById("etfChart");
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
        },
        yAxis: {
          scale: true,
        },
        series: [
          {
            type: "line",
            data: [
              3.85, 3.855, 3.862, 3.868, 3.865, 3.87, 3.875, 3.872, 3.868,
              3.875,
            ],
            smooth: true,
            lineStyle: {
              color: "#2196F3",
              width: 2,
            },
            areaStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  {
                    offset: 0,
                    color: "rgba(33, 150, 243, 0.3)",
                  },
                  {
                    offset: 1,
                    color: "rgba(33, 150, 243, 0.1)",
                  },
                ],
              },
            },
            symbol: "none",
          },
        ],
        tooltip: {
          trigger: "axis",
          axisPointer: {
            type: "cross",
          },
        },
      };

      chart.value.setOption(option);
    };

    const initIndustryChart = () => {
      const chartDom = document.getElementById("industryChart");
      if (!chartDom) return;

      industryChart.value = echarts.init(chartDom);

      const option = {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          formatter: "{a} <br/>{b}: {c} ({d}%)",
        },
        legend: {
          orient: "vertical",
          right: 10,
          top: "center",
        },
        series: [
          {
            name: "行业分布",
            type: "pie",
            radius: ["40%", "70%"],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 6,
              borderWidth: 2,
            },
            label: {
              show: false,
              position: "center",
            },
            emphasis: {
              label: {
                show: true,
                fontSize: "18",
                fontWeight: "bold",
              },
            },
            labelLine: {
              show: false,
            },
            data: [
              { value: 28.5, name: "金融" },
              { value: 18.2, name: "信息技术" },
              { value: 15.8, name: "工业" },
              { value: 12.3, name: "主要消费" },
              { value: 8.7, name: "医药卫生" },
              { value: 7.2, name: "原材料" },
              { value: 4.5, name: "能源" },
              { value: 4.8, name: "其他" },
            ],
          },
        ],
      };

      industryChart.value.setOption(option);
    };

    const handleResize = () => {
      if (chart.value) {
        chart.value.resize();
      }
      if (industryChart.value) {
        industryChart.value.resize();
      }
    };

    onMounted(() => {
      loadETFData();
      window.addEventListener("resize", handleResize);
    });

    onBeforeUnmount(() => {
      if (chart.value) {
        chart.value.dispose();
      }
      if (industryChart.value) {
        industryChart.value.dispose();
      }
      window.removeEventListener("resize", handleResize);
    });

    return {
      loading,
      error,
      etf,
      showBasketSelector,
      timePeriod,
      chartType,
      selectedIndicator,
      activeTab,
      indicatorOptions,
      constituents,
      news,
      constituentColumns,
      goBack,
      onAddedToBasket,
      viewStockDetail,
      loadETFData,
    };
  },
});
</script>
<style scoped lang="scss">
@use "@/styles/naive-variables" as *;

.etf-detail {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.current-price {
  font-size: 1.25rem;
  font-weight: 600;
  margin-right: 12px;
  color: var(--n-text-color-1);
}

.price-change {
  font-size: 1.125rem;
  font-weight: 600;
}

.positive {
  color: $stock-up-color;
}

.negative {
  color: $stock-down-color;
}

.etf-content {
  display: flex;
  gap: spacer(4);

  @include media-breakpoint-down(lg) {
    flex-direction: column;
  }
}

.chart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: spacer(4);
}

.chart-container {
  border-radius: var(--n-border-radius);
  overflow: hidden;
}

.chart-controls {
  display: flex;
  gap: spacer(3);
}

.chart-wrapper {
  height: 400px;
  padding: spacer(2);
}

#etfChart {
  width: 100%;
  height: 100%;
}

.indicator-selector {
  border-radius: var(--n-border-radius);
}

.info-section {
  width: 400px;

  @include media-breakpoint-down(lg) {
    width: 100%;
  }
}

.etf-tabs {
  border-radius: var(--n-border-radius);
  overflow: hidden;
}

.basic-info {
  padding: spacer(4);
}

.info-row {
  display: flex;
  margin-bottom: spacer(3);
}

.info-item {
  flex: 1;
  padding: spacer(2);
}

.info-label {
  display: block;
  color: var(--n-text-color-2);
  font-size: $font-size-base * 0.875;
  margin-bottom: spacer(1);
}

.info-value {
  display: block;
  font-size: $font-size-base;
  font-weight: 600;
  color: var(--n-text-color-base);
}

.market-data {
  margin-top: spacer(4);
}

.quota-data {
  padding: spacer(2) 0;
}

.quota-row {
  display: flex;
  margin-bottom: spacer(3);
}

.quota-item {
  flex: 1;
  text-align: center;
  padding: spacer(2);
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  margin: 0 spacer(1);
  transition: all $transition-normal;
}

.quota-label {
  display: block;
  color: var(--n-text-color-2);
  font-size: $font-size-base * 0.875;
  margin-bottom: spacer(1);
}

.quota-value {
  display: block;
  font-size: $font-size-base;
  font-weight: 600;
  color: var(--n-text-color-base);
}

.news-list {
  padding: spacer(2);
}

.news-item {
  padding: spacer(3);
  border-bottom: 1px solid var(--n-border-color);
  cursor: pointer;
  transition: all $transition-normal;

  &:hover {
    background: var(--n-hover-color);
  }

  &:last-child {
    border-bottom: none;
  }
}

.news-title {
  font-size: $font-size-base;
  margin-bottom: spacer(2);
  color: var(--n-text-color-base);
  font-weight: 500;
}

.news-meta {
  display: flex;
  font-size: $font-size-base * 0.875;
  color: var(--n-text-color-2);
}

.news-time {
  margin-right: spacer(3);
}

@include media-breakpoint-down(md) {
  .info-row {
    flex-direction: column;
    gap: spacer(2);
  }

  .info-item {
    padding: spacer(1);
  }

  .quota-row {
    flex-direction: column;
    gap: spacer(2);
  }

  .quota-item {
    margin: 0;
  }

  .price-info {
    flex-direction: column;
    align-items: flex-start;
    gap: spacer(2);
  }

  .chart-controls {
    flex-direction: column;
    gap: spacer(2);
  }
}

@include media-breakpoint-down(sm) {
  .etf-detail {
    padding: spacer(2);
  }

  .chart-wrapper {
    height: 300px;
  }
}
</style>
