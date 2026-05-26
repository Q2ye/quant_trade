<template>
  <n-spin :show="loading" class="strategy-performance">
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

    <template v-else>
      <div class="page-header">
        <div class="header-content">
          <div class="title-section">
            <h1 class="page-title">策略绩效</h1>
          </div>
          <div class="header-actions">
          <n-select
            v-model:value="selectedStrategy"
            placeholder="选择策略"
            :options="strategyOptions"
            style="width: 200px"
          />
          <n-date-picker
            v-model:value="dateRange"
            type="daterange"
            :is-date-disabled="() => false"
            style="width: 240px; margin-left: 10px"
          />
          <n-button type="primary" @click="loadPerformanceData">
            <Icon icon="ep:search" /> 查询
          </n-button>
          <n-button @click="exportReport">
            <Icon icon="ep:download" /> 导出报告
          </n-button>
          <n-button class="action-btn" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
        </div>
      </div>

      <div class="main-content">
      <n-grid :x-gap="16" :cols="24" class="performance-overview">
        <n-grid-item :span="6">
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="getReturnClass(performance.totalReturn)"
              >
                {{ formatPercent(performance.totalReturn) }}
              </div>
              <div class="metric-label">累计收益</div>
            </div>
          </n-card>
        </n-grid-item>
        <n-grid-item :span="6">
          <n-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value">
                {{
                  performance.annualReturn
                    ? formatPercent(performance.annualReturn)
                    : "--"
                }}
              </div>
              <div class="metric-label">年化收益</div>
            </div>
          </n-card>
        </n-grid-item>
        <n-grid-item :span="6">
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="getDrawdownClass(performance.maxDrawdown)"
              >
                {{ formatPercent(performance.maxDrawdown) }}
              </div>
              <div class="metric-label">最大回撤</div>
            </div>
          </n-card>
        </n-grid-item>
        <n-grid-item :span="6">
          <n-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value">
                {{
                  performance.sharpeRatio
                    ? performance.sharpeRatio.toFixed(2)
                    : "--"
                }}
              </div>
              <div class="metric-label">夏普比率</div>
            </div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <n-grid :x-gap="16" :cols="24" class="chart-row">
        <n-grid-item :span="12">
          <n-card class="chart-card">
            <template #header>
              <div class="chart-header">
                <span>净值曲线</span>
                <n-radio-group v-model:value="chartType" size="small">
                  <n-radio-button value="cumulative" label="累计收益" />
                  <n-radio-button value="daily" label="每日收益" />
                </n-radio-group>
              </div>
            </template>
            <div ref="equityChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>
        <n-grid-item :span="12">
          <n-card class="chart-card">
            <template #header>
              <div class="chart-header"><span>回撤分析</span></div>
            </template>
            <div ref="drawdownChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <n-card class="metrics-card">
        <template #header><span>详细绩效指标</span></template>
        <n-data-table
          :data="performanceMetrics"
          :columns="metricsColumns"
          :loading="loading"
          :bordered="false"
          striped
        />
      </n-card>

      <n-card class="heatmap-card">
        <template #header><span>月度收益热力图</span></template>
        <div
          ref="heatmapChart"
          class="chart-container"
          style="height: 400px"
        ></div>
      </n-card>
    </div>
    </template>
  </n-spin>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from "vue";
import { useRouter } from "vue-router";
import { useMessage } from "naive-ui";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import * as echarts from "echarts";

const message = useMessage();
const router = useRouter();
const loading = ref(false);
const error = ref(false);
const selectedStrategy = ref("");
const dateRange = ref<any>(null);
const chartType = ref("cumulative");
const equityChart = ref<HTMLElement>();
const drawdownChart = ref<HTMLElement>();
const heatmapChart = ref<HTMLElement>();

const strategyList = ref([
  { id: "1", name: "双均线策略" },
  { id: "2", name: "动量反转策略" },
  { id: "3", name: "均值回归策略" },
]);
const strategyOptions = computed(() =>
  strategyList.value.map((s) => ({ label: s.name, value: s.id })),
);

const performance = reactive({
  totalReturn: 0.1542,
  annualReturn: 0.2345,
  maxDrawdown: -0.0876,
  sharpeRatio: 1.23,
  winRate: 0.634,
  profitFactor: 1.89,
});

const performanceMetrics = ref([
  {
    metric: "累计收益率",
    value: 0.1542,
    description: "策略从开始到现在的总收益率",
    benchmark: 0.1023,
  },
  {
    metric: "年化收益率",
    value: 0.2345,
    description: "折算成年度的收益率",
    benchmark: 0.1567,
  },
  {
    metric: "最大回撤",
    value: -0.0876,
    description: "策略净值从最高点到最低点的最大跌幅",
    benchmark: -0.1234,
  },
  {
    metric: "夏普比率",
    value: 1.23,
    description: "每承受一单位风险产生的超额收益",
    benchmark: 0.89,
  },
  {
    metric: "索提诺比率",
    value: 1.89,
    description: "只考虑下行风险的调整后收益",
    benchmark: 1.23,
  },
  {
    metric: "胜率",
    value: 0.634,
    description: "盈利交易次数占总交易次数的比例",
    benchmark: 0.523,
  },
  {
    metric: "盈亏比",
    value: 1.45,
    description: "平均盈利与平均亏损的比例",
    benchmark: 1.21,
  },
  {
    metric: "利润因子",
    value: 1.89,
    description: "总盈利与总亏损的比值",
    benchmark: 1.34,
  },
  {
    metric: "年化波动率",
    value: 0.1876,
    description: "策略收益率的年化标准差",
    benchmark: 0.2345,
  },
]);

const getReturnClass = (v: number) => (v >= 0 ? "positive" : "negative");
const getDrawdownClass = (d: number) =>
  d <= -0.1 ? "negative" : d <= -0.05 ? "warning" : "positive";

const getMetricClass = (metric: string, value: number) => {
  if (metric.includes("回撤") || metric.includes("波动率"))
    return value <= -0.1 ? "negative" : value <= -0.05 ? "warning" : "positive";
  return value >= 0 ? "positive" : "negative";
};

const formatPercent = (value: number | null | undefined) => {
  if (value === null || value === undefined) return "--";
  return `${(value * 100).toFixed(2)}%`;
};

const formatMetricValue = (metric: string, value: number) => {
  if (metric.includes("率") && !metric.includes("波动率"))
    return formatPercent(value);
  if (typeof value === "number") return value.toFixed(4);
  return value || "--";
};

const metricsColumns = computed(() => [
  { title: "指标名称", key: "metric", width: 200 },
  {
    title: "数值",
    key: "value",
    width: 150,
    render(row: any) {
      return h(
        "span",
        { class: getMetricClass(row.metric, row.value) },
        formatMetricValue(row.metric, row.value),
      );
    },
  },
  { title: "说明", key: "description" },
  {
    title: "基准",
    key: "benchmark",
    width: 150,
    render(row: any) {
      return formatMetricValue(row.metric, row.benchmark);
    },
  },
]);

const loadPerformanceData = async () => {
  if (!selectedStrategy.value) {
    message.warning("请选择策略");
    return;
  }
  loading.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    error.value = false;
    message.success("数据加载成功");
    initCharts();
  } catch (err) {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const exportReport = () => message.info("导出报告功能开发中");

let equityChartInstance: any = null;
let drawdownChartInstance: any = null;
let heatmapChartInstance: any = null;

const initCharts = () => {
  if (equityChart.value) {
    equityChartInstance = echarts.init(equityChart.value);
    equityChartInstance.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["策略净值", "基准净值"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: {
        type: "category",
        data: [
          "2023-01",
          "2023-02",
          "2023-03",
          "2023-04",
          "2023-05",
          "2023-06",
          "2023-07",
          "2023-08",
          "2023-09",
          "2023-10",
          "2023-11",
          "2023-12",
        ],
      },
      yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
      series: [
        {
          name: "策略净值",
          type: "line",
          data: [
            2.1, 5.3, 8.7, 6.2, 12.4, 15.2, 13.8, 16.5, 14.2, 17.8, 15.4, 18.2,
          ],
          itemStyle: { color: "#5470c6" },
          smooth: true,
        },
        {
          name: "基准净值",
          type: "line",
          data: [
            1.2, 3.4, 5.6, 4.3, 8.9, 10.2, 9.8, 11.5, 10.1, 12.3, 11.2, 12.8,
          ],
          itemStyle: { color: "#91cc75" },
          smooth: true,
        },
      ],
    });
  }
  if (drawdownChart.value) {
    drawdownChartInstance = echarts.init(drawdownChart.value);
    drawdownChartInstance.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["回撤幅度"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: {
        type: "category",
        data: [
          "2023-01",
          "2023-02",
          "2023-03",
          "2023-04",
          "2023-05",
          "2023-06",
          "2023-07",
          "2023-08",
          "2023-09",
          "2023-10",
          "2023-11",
          "2023-12",
        ],
      },
      yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
      series: [
        {
          name: "回撤幅度",
          type: "line",
          data: [
            -1.2, -2.1, -4.3, -3.2, -5.6, -3.8, -6.2, -4.5, -3.9, -2.8, -4.1,
            -2.5,
          ],
          itemStyle: { color: "#ee6666" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(238,102,102,0.5)" },
              { offset: 1, color: "rgba(238,102,102,0.1)" },
            ]),
          },
        },
      ],
    });
  }
  if (heatmapChart.value) {
    heatmapChartInstance = echarts.init(heatmapChart.value);
    const months = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ];
    const years = ["2020", "2021", "2022", "2023"];
    const data: any[] = [];
    years.forEach((year, yIndex) =>
      months.forEach((month, mIndex) =>
        data.push([mIndex, yIndex, ((Math.random() - 0.5) * 20).toFixed(1)]),
      ),
    );
    heatmapChartInstance.setOption({
      tooltip: { position: "top" },
      grid: { height: "80%", top: "10%" },
      xAxis: { type: "category", data: months, splitArea: { show: true } },
      yAxis: { type: "category", data: years, splitArea: { show: true } },
      visualMap: {
        min: -10,
        max: 10,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: "0%",
        inRange: {
          color: [
            "#c23531",
            "#d48265",
            "#91c7ae",
            "#749f83",
            "#ca8622",
            "#bda29a",
          ],
        },
      },
      series: [
        {
          name: "月度收益",
          type: "heatmap",
          data,
          label: { show: true },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" },
          },
        },
      ],
    });
  }
};

onMounted(() => {
  if (strategyList.value.length > 0)
    selectedStrategy.value = strategyList.value[0].id;
  loadPerformanceData();
});
</script>

<style lang="scss" scoped>
.strategy-performance {
  padding: 0;
  height: 100%;
  overflow-y: auto;

}
/* .page-header 已迁移至全局样式（global.scss） */

.performance-overview {
  margin-bottom: 20px;
}
.metric-content {
  text-align: center;
}
.metric-content .metric-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}
.metric-content .metric-label {
  color: var(--n-text-color-3);
  font-size: 14px;
}
.positive {
  color: #67c23a;
}
.negative {
  color: #f56c6c;
}
.warning {
  color: #e6a23c;
}
.chart-row {
  margin-bottom: 20px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chart-container {
  height: 300px;
}
.metrics-card,
.heatmap-card {
  margin-bottom: 20px;
}
</style>
