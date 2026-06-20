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

    <n-empty
      v-else-if="empty"
      description="该策略暂无绩效数据，请先运行回测"
      style="padding: 60px 0"
    >
      <template #extra>
        <n-button type="primary" @click="router.push('/backtest')">前往回测</n-button>
      </template>
    </n-empty>

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
            <n-button size="small" @click="router.push('/performance/comparison')" quaternary>
              加入对比
            </n-button>
            <n-button size="small" @click="router.push('/performance/attribution')" quaternary>
              归因分析
            </n-button>
            <n-button class="action-btn" @click="router.push('/performance')" quaternary>
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
import { ref, reactive, computed, onMounted, onUnmounted, h, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useMessage } from "naive-ui";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import strategyAPI from "@/api/strategy";
import performanceAPI from "@/api/performance";
import * as echarts from "echarts";

const props = defineProps<{ id?: string }>();

const message = useMessage();
const router = useRouter();
const route = useRoute();
const loading = ref(false);
const error = ref(false);
const empty = ref(false);
const selectedStrategy = ref("");
const dateRange = ref<any>(null);
const chartType = ref("cumulative");
const equityChart = ref<HTMLElement>();
const drawdownChart = ref<HTMLElement>();
const heatmapChart = ref<HTMLElement>();

// Real data stores from API
const equityCurveData = ref<Array<{ date: string; equity: number; benchmark?: number }>>([]);
const drawdownCurveData = ref<Array<{ date: string; drawdown: number }>>([]);
const monthlyReturnsData = ref<Record<string, number>>({});

const strategyList = ref<any[]>([]);
const strategyOptions = computed(() =>
  strategyList.value.map((s: any) => ({
    label: s.name ?? s.strategy_name ?? String(s.id),
    value: String(s.id),
  })),
);

const performance = reactive({
  totalReturn: 0,
  annualReturn: 0,
  maxDrawdown: 0,
  sharpeRatio: 0,
  winRate: 0,
  profitFactor: 0,
});

const performanceMetrics = ref<any[]>([]);

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
  error.value = false;
  empty.value = false;
  try {
    const params: any = {};
    if (dateRange.value) {
      const [start, end] = Array.isArray(dateRange.value)
        ? dateRange.value
        : [null, null];
      if (start) params.start_date = new Date(start).toISOString().split("T")[0];
      if (end) params.end_date = new Date(end).toISOString().split("T")[0];
    }
    const data: any = await performanceAPI.getStrategyPerformance(
      selectedStrategy.value,
      params,
    );
    if (data === null) {
      // Backend returned success:false — treat as error
      error.value = true;
      return;
    }
    if (data && Object.keys(data).length > 0) {
      performance.totalReturn = data.total_return ?? data.totalReturn ?? 0;
      performance.annualReturn = data.annual_return ?? data.annualReturn ?? 0;
      performance.maxDrawdown = data.max_drawdown ?? data.maxDrawdown ?? 0;
      performance.sharpeRatio = data.sharpe_ratio ?? data.sharpeRatio ?? 0;
      performance.winRate = data.win_rate ?? data.winRate ?? 0;
      performance.profitFactor = data.profit_factor ?? data.profitFactor ?? 0;

      // Store real chart data
      if (data.equity_curve && Array.isArray(data.equity_curve)) {
        equityCurveData.value = data.equity_curve;
      }
      if (data.drawdown_curve && Array.isArray(data.drawdown_curve)) {
        drawdownCurveData.value = data.drawdown_curve;
      }
      if (data.monthly_returns) {
        monthlyReturnsData.value = data.monthly_returns;
      }

      // Build metrics table from rich response
      const metricsList: any[] = [
        {
          metric: "累计收益率",
          value: performance.totalReturn,
          description: "策略从开始到现在的总收益率",
          benchmark: data.benchmark_return ?? "--",
        },
        {
          metric: "年化收益率",
          value: performance.annualReturn,
          description: "折算成年度的收益率",
          benchmark: data.benchmark_annual_return ?? "--",
        },
        {
          metric: "最大回撤",
          value: performance.maxDrawdown,
          description: "策略净值从最高点到最低点的最大跌幅",
          benchmark: "--",
        },
        {
          metric: "夏普比率",
          value: performance.sharpeRatio,
          description: "每承受一单位风险产生的超额收益",
          benchmark: data.benchmark_sharpe ?? "--",
        },
        {
          metric: "Sortino 比率",
          value: data.sortino_ratio ?? 0,
          description: "下行风险调整后的收益",
          benchmark: "--",
        },
        {
          metric: "Calmar 比率",
          value: data.calmar_ratio ?? 0,
          description: "年化收益与最大回撤的比值",
          benchmark: "--",
        },
        {
          metric: "波动率",
          value: data.volatility ?? 0,
          description: "收益率的标准差",
          benchmark: "--",
        },
        {
          metric: "胜率",
          value: performance.winRate,
          description: "盈利交易次数占总交易次数的比例",
          benchmark: "--",
        },
        {
          metric: "利润因子",
          value: performance.profitFactor,
          description: "总盈利与总亏损的比值",
          benchmark: "--",
        },
        {
          metric: "总交易次数",
          value: data.total_trades ?? data.totalTrades ?? 0,
          description: "策略执行的总交易次数",
          benchmark: "--",
        },
      ];
      if (data.alpha !== undefined || data.beta !== undefined) {
        metricsList.push(
          { metric: "Alpha", value: data.alpha ?? 0, description: "超额收益（相对基准）", benchmark: "--" },
          { metric: "Beta", value: data.beta ?? 0, description: "系统性风险暴露", benchmark: "--" },
          { metric: "信息比率", value: data.information_ratio ?? 0, description: "主动管理效率", benchmark: "--" },
        );
      }
      performanceMetrics.value = metricsList;

      if (!data.equity_curve || data.equity_curve.length === 0) {
        empty.value = true;
      }
    } else {
      empty.value = true;
    }
    await nextTick();
    initCharts();
  } catch {
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
  // Dispose existing instances
  equityChartInstance?.dispose();
  drawdownChartInstance?.dispose();
  heatmapChartInstance?.dispose();

  // --- Equity curve with benchmark overlay ---
  if (equityChart.value) {
    equityChartInstance = echarts.init(equityChart.value);
    const eqData = equityCurveData.value;
    const dates = eqData.length > 0
      ? eqData.map((d: any) => d.date || d.trade_date || "")
      : ["2023-01","2023-02","2023-03","2023-04","2023-05","2023-06","2023-07","2023-08","2023-09","2023-10","2023-11","2023-12"];
    const equityValues = eqData.length > 0
      ? eqData.map((d: any) => d.equity ?? d.nav ?? 1)
      : [1.0];
    const benchmarkValues = eqData.length > 0 && eqData[0]?.benchmark !== undefined
      ? eqData.map((d: any) => d.benchmark ?? null)
      : null;

    const series: any[] = [{
      name: "策略净值",
      type: "line",
      data: equityValues,
      itemStyle: { color: "#5470c6" },
      lineStyle: { width: 2 },
      smooth: true,
    }];
    const legendData = ["策略净值"];

    if (benchmarkValues) {
      series.push({
        name: "基准净值",
        type: "line",
        data: benchmarkValues,
        itemStyle: { color: "#91cc75" },
        lineStyle: { width: 2, type: "dashed" },
        smooth: true,
      });
      legendData.push("基准净值");
    }

    equityChartInstance.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: legendData, bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: { type: "category", data: dates, axisLabel: { rotate: dates.length > 12 ? 45 : 0 } },
      yAxis: { type: "value" },
      series,
    });
  }

  // --- Drawdown chart ---
  if (drawdownChart.value) {
    drawdownChartInstance = echarts.init(drawdownChart.value);
    const ddData = drawdownCurveData.value;
    const ddDates = ddData.length > 0
      ? ddData.map((d: any) => d.date || d.trade_date || "")
      : ["2023-01","2023-02","2023-03","2023-04","2023-05","2023-06","2023-07","2023-08","2023-09","2023-10","2023-11","2023-12"];
    const ddValues = ddData.length > 0
      ? ddData.map((d: any) => d.drawdown ?? d.value ?? 0)
      : [0];

    drawdownChartInstance.setOption({
      tooltip: { trigger: "axis", formatter: (p: any) => `${p[0].axisValue}<br/>回撤: ${(p[0].value*100).toFixed(2)}%` },
      legend: { data: ["回撤幅度"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: { type: "category", data: ddDates, axisLabel: { rotate: ddDates.length > 12 ? 45 : 0 } },
      yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${(v*100).toFixed(0)}%` } },
      series: [{
        name: "回撤幅度",
        type: "line",
        data: ddValues,
        itemStyle: { color: "#ee6666" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(238,102,102,0.5)" },
            { offset: 1, color: "rgba(238,102,102,0.05)" },
          ]),
        },
      }],
    });
  }

  // --- Monthly returns heatmap ---
  if (heatmapChart.value) {
    heatmapChartInstance = echarts.init(heatmapChart.value);
    const mr = monthlyReturnsData.value;
    const mrEntries = Object.entries(mr);

    if (mrEntries.length > 0) {
      // Parse "YYYY-MM" keys into year/month grid
      const yearSet = new Set<string>();
      const monthSet = new Set<string>();
      const heatData: any[] = [];
      mrEntries.forEach(([key, val]) => {
        const parts = key.split("-");
        if (parts.length >= 2) {
          const y = parts[0];
          const m = parts[1];
          yearSet.add(y); monthSet.add(m);
          heatData.push([m, y, +(Number(val) * 100).toFixed(2)]);
        }
      });
      const years = Array.from(yearSet).sort();
      const months = Array.from(monthSet).sort((a,b) => parseInt(a)-parseInt(b));
      const maxAbs = Math.max(...heatData.map((d: any) => Math.abs(d[2])), 5);

      heatmapChartInstance.setOption({
        tooltip: { position: "top", formatter: (p: any) => `${p.data[1]}-${p.data[0]}: ${p.data[2]}%` },
        grid: { height: "75%", top: "8%" },
        xAxis: { type: "category", data: months, splitArea: { show: true } },
        yAxis: { type: "category", data: years, splitArea: { show: true } },
        visualMap: {
          min: -maxAbs, max: maxAbs, calculable: true,
          orient: "horizontal", left: "center", bottom: "0%",
          inRange: { color: ["#d03050", "#f6a6a0", "#fafafa", "#a3d9b1", "#18a058"] },
        },
        series: [{
          name: "月度收益",
          type: "heatmap",
          data: heatData,
          label: { show: true, fontSize: 10 },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" } },
        }],
      });
    } else {
      // No data: show placeholder
      heatmapChartInstance.setOption({
        title: { text: "暂无月度收益数据", left: "center", top: "center", textStyle: { color: "#999", fontSize: 14 } },
      });
    }
  }
};

onMounted(async () => {
  try {
    const strategies = await strategyAPI.getStrategies();
    strategyList.value = Array.isArray(strategies) ? strategies : [];
  } catch {
    strategyList.value = [];
  }
  // Priority: props.id > route.params.id > first strategy
  const routeId = props.id || (route.params.id as string);
  if (routeId) {
    // Direct navigation with strategy id — load performance regardless of list state
    selectedStrategy.value = routeId;
    await loadPerformanceData();
    return;
  }
  if (strategyList.value.length > 0) {
    selectedStrategy.value = String(strategyList.value[0].id);
    // Selector mode: user picks from dropdown, don't auto-load
  }
});

onUnmounted(() => {
  equityChartInstance?.dispose();
  drawdownChartInstance?.dispose();
  heatmapChartInstance?.dispose();
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
