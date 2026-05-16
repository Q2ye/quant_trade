<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import {
  NCard,
  NSelect,
  NDatePicker,
  NDataTable,
  NTabs,
  NTabPane,
  NSpace,
  NSpin,
  NResult,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { Line } from "@antv/g2plot";

interface PerformanceMetric {
  name: string;
  strategy1: number;
  strategy2: number;
  benchmark: number;
}

const loading = ref(false);
const error = ref(false);
const comparisonData = ref<PerformanceMetric[]>([]);
const selectedStrategies = ref<string[]>([]);
const dateRange = ref<[string, string] | null>(null);

const strategyOptions = [
  { label: "双均线策略", value: "strategy1" },
  { label: "动量反转策略", value: "strategy2" },
  { label: "沪深300", value: "benchmark" },
];

const metrics = [
  { name: "年化收益率", strategy1: 0.156, strategy2: 0.234, benchmark: 0.089 },
  { name: "夏普比率", strategy1: 1.23, strategy2: 1.89, benchmark: 0.76 },
  { name: "最大回撤", strategy1: -0.156, strategy2: -0.089, benchmark: -0.234 },
  { name: "波动率", strategy1: 0.189, strategy2: 0.156, benchmark: 0.201 },
  { name: "胜率", strategy1: 0.623, strategy2: 0.712, benchmark: 0.534 },
  { name: "盈亏比", strategy1: 1.45, strategy2: 1.89, benchmark: 1.23 },
];

const metricColumns: DataTableColumns<PerformanceMetric> = [
  { title: "指标", key: "name" },
  {
    title: "策略1",
    key: "strategy1",
    render: (row) => {
      const cls = row.strategy1 >= 0 ? "positive" : "negative";
      return h("span", { class: cls }, `${(row.strategy1 * 100).toFixed(2)}%`);
    },
  },
  {
    title: "策略2",
    key: "strategy2",
    render: (row) => {
      const cls = row.strategy2 >= 0 ? "positive" : "negative";
      return h("span", { class: cls }, `${(row.strategy2 * 100).toFixed(2)}%`);
    },
  },
  {
    title: "基准",
    key: "benchmark",
    render: (row) => {
      const cls = row.benchmark >= 0 ? "positive" : "negative";
      return h("span", { class: cls }, `${(row.benchmark * 100).toFixed(2)}%`);
    },
  },
];

const loadComparisonData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((resolve) => setTimeout(resolve, 800));
    comparisonData.value = metrics;
  } catch (err) {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const renderChart = () => {
  const container = document.getElementById("performanceChart");
  if (!container) return;

  const data = [
    { period: "2023-01", strategy1: 1.0, strategy2: 1.0, benchmark: 1.0 },
    { period: "2023-02", strategy1: 1.056, strategy2: 1.089, benchmark: 1.023 },
    { period: "2023-03", strategy1: 1.123, strategy2: 1.234, benchmark: 1.045 },
  ];

  const linePlot = new Line("performanceChart", {
    data,
    xField: "period",
    yField: "value",
    seriesField: "category",
    yAxis: {
      label: {
        formatter: (v) => `${(Number(v) * 100 - 100).toFixed(1)}%`,
      },
    },
    legend: {
      position: "top",
    },
    smooth: true,
    animation: {
      appear: {
        animation: "path-in",
        duration: 1000,
      },
    },
  });

  linePlot.render();
};

onMounted(() => {
  loadComparisonData();
  // 等待 DOM 渲染后初始化图表
  setTimeout(() => {
    renderChart();
  }, 200);
});
</script>

<template>
  <n-spin :show="loading" class="performance-comparison-page">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取对比数据失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="loadComparisonData">重试</n-button></template
      >
    </n-result>

    <n-card v-else title="策略绩效对比">
      <template #header-extra>
        <n-space>
          <n-select
            v-model:value="selectedStrategies"
            multiple
            placeholder="选择对比策略"
            style="width: 300px"
            :options="strategyOptions"
          />

          <n-date-picker
            v-model:formatted-value="dateRange"
            type="daterange"
            clearable
          />
        </n-space>
      </template>

      <n-tabs>
        <n-tab-pane name="chart" tab="净值曲线">
          <div id="performanceChart" style="height: 400px"></div>
        </n-tab-pane>

        <n-tab-pane name="metrics" tab="绩效指标">
          <n-data-table
            :data="comparisonData"
            :columns="metricColumns"
            :pagination="false"
            :row-key="(row: PerformanceMetric) => row.name"
          />
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </n-spin>
</template>

<style scoped>
.performance-comparison-page {
  padding: 24px;
}

.positive {
  color: var(--color-stock-up);
}

.negative {
  color: var(--color-stock-down);
}
</style>
