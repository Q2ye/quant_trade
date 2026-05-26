<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NSelect,
  NInputNumber,
  NProgress,
  NAlert,
  NDataTable,
} from "naive-ui";
import type { DataTableColumn } from "naive-ui";
import { useChart } from "@/composables/useChart";
import { useMessage } from "naive-ui";

const message = useMessage();

interface OptimizationConfig {
  parameter: string;
  range: [number, number];
  step: number;
  metric: string;
}

interface OptimizationResult {
  parameter: string;
  value: number;
  metricValue: number;
}

const optimizationConfig = reactive<OptimizationConfig>({
  parameter: "window",
  range: [10, 50],
  step: 5,
  metric: "sharpeRatio",
});

const optimizationResults = ref<OptimizationResult[]>([]);
const isOptimizing = ref(false);
const optimizationProgress = ref(0);
const chartRef = ref<HTMLDivElement>();
const heatmapRef = ref<HTMLDivElement>();

const availableParameters = [
  { value: "window", label: "移动平均窗口" },
  { value: "threshold", label: "交易阈值" },
  { value: "stopLoss", label: "止损比例" },
];

const availableMetrics = [
  { value: "sharpeRatio", label: "夏普比率", maximize: true },
  { value: "annualReturn", label: "年化收益率", maximize: true },
  { value: "maxDrawdown", label: "最大回撤", maximize: false },
  { value: "winRate", label: "胜率", maximize: true },
];

const runOptimization = async () => {
  if (isOptimizing.value) return;
  isOptimizing.value = true;
  optimizationProgress.value = 0;
  optimizationResults.value = [];

  try {
    const [start, end] = optimizationConfig.range;
    const steps = Math.floor((end - start) / optimizationConfig.step) + 1;
    for (let i = 0; i < steps; i++) {
      const value = start + i * optimizationConfig.step;
      await new Promise((resolve) => setTimeout(resolve, 500));
      const metricValue = simulateMetricValue(value, optimizationConfig.metric);
      optimizationResults.value.push({
        parameter: optimizationConfig.parameter,
        value,
        metricValue,
      });
      optimizationProgress.value = ((i + 1) / steps) * 100;
    }
    message.success("参数优化完成");
    initOptimizationChart();
    initHeatmapChart();
  } catch (error) {
    message.error("参数优化失败");
  } finally {
    isOptimizing.value = false;
  }
};

const simulateMetricValue = (paramValue: number, metric: string): number => {
  switch (metric) {
    case "sharpeRatio":
      return Math.sin(paramValue / 10) * 1.5 + 1.5 + Math.random() * 0.3;
    case "annualReturn":
      return Math.cos(paramValue / 15) * 0.3 + 0.2 + Math.random() * 0.1;
    case "maxDrawdown":
      return (
        Math.abs(Math.sin(paramValue / 8)) * 0.2 + 0.05 + Math.random() * 0.05
      );
    case "winRate":
      return Math.sin(paramValue / 12) * 0.2 + 0.5 + Math.random() * 0.1;
    default:
      return 0;
  }
};

const initOptimizationChart = () => {
  if (!chartRef.value || optimizationResults.value.length === 0) return;
  const { initChart } = useChart();
const chart = initChart(chartRef.value);
if (!chart) return;
chart.setOption({
    title: { text: "参数优化结果" },
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        const param = params[0];
        return `${optimizationConfig.parameter}: ${param.value}<br/>${getMetricLabel(optimizationConfig.metric)}: ${param.data.toFixed(4)}`;
      },
    },
    xAxis: {
      type: "value",
      name: getParameterLabel(optimizationConfig.parameter),
    },
    yAxis: { type: "value", name: getMetricLabel(optimizationConfig.metric) },
    series: [
      {
        data: optimizationResults.value.map((r) => [r.value, r.metricValue]),
        type: "line",
        smooth: true,
        symbolSize: 8,
        lineStyle: { width: 3 },
        itemStyle: { color: "#5470c6" },
      },
    ],
  });
};

const initHeatmapChart = () => {
  if (!heatmapRef.value) return;
  const xData = [10, 20, 30, 40, 50];
  const yData = [0.01, 0.02, 0.03, 0.04, 0.05];
  const heatmapData: number[][] = [];
  for (let i = 0; i < xData.length; i++) {
    for (let j = 0; j < yData.length; j++) {
      heatmapData.push([i, j, Math.random()]);
    }
  }
  const { initChart: initHeatmap } = useChart();
const chart = initHeatmap(heatmapRef.value);
if (!chart) return;
chart.setOption({
    title: { text: "双参数优化热力图" },
    tooltip: { position: "top" },
    grid: { height: "50%", top: "10%" },
    xAxis: { type: "category", data: xData, splitArea: { show: true } },
    yAxis: { type: "category", data: yData, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: "15%",
    },
    series: [
      {
        name: "Punch Card",
        type: "heatmap",
        data: heatmapData,
        label: { show: true },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: "rgba(0, 0, 0, 0.5)" },
        },
      },
    ],
  });
};

const bestParameter = computed(() => {
  if (optimizationResults.value.length === 0) return null;
  const metricConfig = availableMetrics.find(
    (m) => m.value === optimizationConfig.metric,
  );
  if (!metricConfig) return null;
  return optimizationResults.value.reduce((best, current) => {
    if (metricConfig.maximize)
      return current.metricValue > best.metricValue ? current : best;
    return current.metricValue < best.metricValue ? current : best;
  });
});

const getParameterLabel = (param: string) =>
  availableParameters.find((p) => p.value === param)?.label || param;
const getMetricLabel = (metric: string) =>
  availableMetrics.find((m) => m.value === metric)?.label || metric;

const resultColumns: DataTableColumn<any>[] = [
  {
    key: "value",
    title: computed(() => getParameterLabel(optimizationConfig.parameter))
      .value,
    sorter: true,
  },
  {
    key: "metricValue",
    title: computed(() => getMetricLabel(optimizationConfig.metric)).value,
    sorter: true,
    render: (row: OptimizationResult) => row.metricValue.toFixed(4),
  },
];

const resetOptimization = () => {
  optimizationResults.value = [];
  isOptimizing.value = false;
  optimizationProgress.value = 0;
};

onMounted(() => {
  initOptimizationChart();
  initHeatmapChart();
});
</script>

<template>
  <div class="parameter-optimize">
    <div class="optimize-header">
      <h3>策略参数优化</h3>
      <div class="header-actions">
        <NButton
          size="small"
          :disabled="isOptimizing"
          @click="resetOptimization"
          >重置</NButton
        >
        <NButton
          type="primary"
          size="small"
          :loading="isOptimizing"
          :disabled="isOptimizing"
          @click="runOptimization"
        >
          {{ isOptimizing ? "优化中..." : "开始优化" }}
        </NButton>
      </div>
    </div>

    <div class="optimize-config">
      <NCard class="config-card">
        <template #header><span>优化配置</span></template>
        <NForm
          :model="optimizationConfig"
          label-placement="left"
          label-width="100px"
        >
          <NFormItem label="优化参数">
            <NSelect
              v-model:value="optimizationConfig.parameter"
              :options="availableParameters"
            />
          </NFormItem>
          <NFormItem label="参数范围">
            <div class="range-inputs">
              <NInputNumber
                v-model:value="optimizationConfig.range[0]"
                :min="1"
                :max="optimizationConfig.range[1] - 1"
              />
              <span class="range-separator">至</span>
              <NInputNumber
                v-model:value="optimizationConfig.range[1]"
                :min="optimizationConfig.range[0] + 1"
              />
            </div>
          </NFormItem>
          <NFormItem label="步长">
            <NInputNumber
              v-model:value="optimizationConfig.step"
              :min="1"
              :max="optimizationConfig.range[1] - optimizationConfig.range[0]"
            />
          </NFormItem>
          <NFormItem label="优化指标">
            <NSelect
              v-model:value="optimizationConfig.metric"
              :options="availableMetrics"
            />
          </NFormItem>
        </NForm>
      </NCard>
    </div>

    <div v-if="isOptimizing" class="optimize-progress">
      <NProgress
        :percentage="optimizationProgress"
        :status="optimizationProgress === 100 ? 'success' : undefined"
      />
      <div class="progress-text">
        正在优化参数: {{ optimizationConfig.parameter }} ({{
          optimizationProgress.toFixed(0)
        }}%)
      </div>
    </div>

    <div v-if="bestParameter" class="best-result">
      <NAlert type="success" title="最佳参数建议">
        <p>
          {{ getParameterLabel(bestParameter.parameter) }}:
          <strong>{{ bestParameter.value }}</strong>
        </p>
        <p>
          {{ getMetricLabel(optimizationConfig.metric) }}:
          <strong>{{ bestParameter.metricValue.toFixed(4) }}</strong>
        </p>
      </NAlert>
    </div>

    <div class="optimize-results">
      <div class="result-chart">
        <h4>单参数优化曲线</h4>
        <div ref="chartRef" class="chart-container"></div>
      </div>
      <div class="result-heatmap">
        <h4>双参数优化热力图</h4>
        <div ref="heatmapRef" class="chart-container"></div>
      </div>
    </div>

    <div v-if="optimizationResults.length > 0" class="results-table">
      <h4>详细优化结果</h4>
      <NDataTable
        :data="optimizationResults"
        :columns="resultColumns"
        :max-height="300"
        :bordered="false"
      />
    </div>
  </div>
</template>

<style scoped>
.parameter-optimize {
  padding: 20px;
  background: var(--n-body-color);
  min-height: 100%;
}

.optimize-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--n-border-color);
}

.optimize-config {
  margin-bottom: 20px;
}
.config-card {
  max-width: 500px;
}

.range-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-separator {
  color: var(--n-text-color-3);
  margin: 0 8px;
}

.optimize-progress {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--n-color-embedded);
  border-radius: 6px;
}

.progress-text {
  text-align: center;
  margin-top: 8px;
  color: var(--n-text-color-3);
}

.best-result {
  margin-bottom: 20px;
}

.optimize-results {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.result-chart,
.result-heatmap {
  background: var(--n-color-embedded);
  border-radius: 6px;
  padding: 16px;
}

.result-chart h4,
.result-heatmap h4 {
  margin: 0 0 16px 0;
  color: var(--n-text-color-1);
}

.chart-container {
  height: 300px;
}
.results-table h4 {
  margin-bottom: 16px;
  color: var(--n-text-color-1);
}

@media (max-width: 1200px) {
  .optimize-results {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .optimize-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .range-inputs {
    flex-direction: column;
    align-items: flex-start;
  }
  .range-separator {
    margin: 8px 0;
  }
}
</style>
