<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { NButton, NCheckboxGroup, NCheckbox, NDataTable } from "naive-ui";
import type { DataTableColumn } from "naive-ui";
import { useChart } from "@/composables/useChart";
import { useStore } from "vuex";

const store = useStore();

interface StrategyResult {
  id: string;
  name: string;
  annualReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  volatility: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  equityCurve: Array<{ date: string; value: number }>;
}

const strategies = ref<StrategyResult[]>([]);
const selectedStrategies = ref<string[]>([]);
const compareMetrics = ref(["annualReturn", "sharpeRatio", "maxDrawdown"]);
const chartRef = ref<HTMLDivElement>();

const availableMetrics = [
  { value: "annualReturn", label: "年化收益率", format: "percent" },
  { value: "sharpeRatio", label: "夏普比率", format: "number" },
  { value: "maxDrawdown", label: "最大回撤", format: "percent" },
  { value: "volatility", label: "波动率", format: "percent" },
  { value: "winRate", label: "胜率", format: "percent" },
  { value: "profitFactor", label: "盈利因子", format: "number" },
  { value: "totalTrades", label: "交易次数", format: "number" },
];

const strategyCheckboxOptions = computed(() =>
  strategies.value.map((s) => ({ label: s.name, value: s.id })),
);

const metricCheckboxOptions = computed(() =>
  availableMetrics.map((m) => ({ label: m.label, value: m.value })),
);

const loadStrategyResults = async () => {
  const results = await store.dispatch("strategy/getStrategyBacktestResults");
  strategies.value = results;
  selectedStrategies.value = results.slice(0, 3).map((s: any) => s.id);
};

const selectedStrategyData = computed(() => {
  return strategies.value.filter((s) =>
    selectedStrategies.value.includes(s.id),
  );
});

const initComparisonChart = () => {
  if (!chartRef.value || selectedStrategyData.value.length === 0) return;
  const { initChart } = useChart();
const chart = initChart(chartRef.value);
if (!chart) return;
chart.setOption({
    title: { text: "策略净值曲线对比" },
    tooltip: { trigger: "axis" },
    legend: { data: selectedStrategyData.value.map((s) => s.name), bottom: 0 },
    grid: { top: 50, right: 50, bottom: 50, left: 50 },
    xAxis: { type: "time", axisLabel: { formatter: "{yyyy}-{MM}-{dd}" } },
    yAxis: { type: "value", axisLabel: { formatter: "{value}" }, scale: true },
    series: selectedStrategyData.value.map((strategy) => ({
      name: strategy.name,
      type: "line",
      data: strategy.equityCurve.map((point) => [point.date, point.value]),
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 },
    })),
  });
};

const formatValue = (value: number, format: string) => {
  switch (format) {
    case "percent":
      return (value * 100).toFixed(2) + "%";
    case "number":
      return value.toFixed(2);
    default:
      return value.toString();
  }
};

const columns = computed<DataTableColumn<any>[]>(() => {
  const cols: DataTableColumn<any>[] = [
    { key: "name", title: "策略名称", fixed: "left" as const },
  ];
  compareMetrics.value.forEach((metric) => {
    const metricInfo = availableMetrics.find((m) => m.value === metric);
    cols.push({
      key: metric,
      title: metricInfo?.label || metric,
      render: (row: any) =>
        formatValue(row[metric], metricInfo?.format || "number"),
    });
  });
  return cols;
});

const exportComparison = () => {
  const report = {
    comparedStrategies: selectedStrategyData.value.map((s) => s.name),
    metrics: compareMetrics.value,
    data: selectedStrategyData.value,
  };
  console.log("导出对比报告:", report);
};

onMounted(async () => {
  await loadStrategyResults();
  initComparisonChart();
});
</script>

<template>
  <div class="multi-strategy-compare">
    <div class="compare-header">
      <h3>多策略对比分析</h3>
      <div class="header-actions">
        <NButton size="small" @click="exportComparison">导出报告</NButton>
      </div>
    </div>

    <div class="compare-controls">
      <div class="control-section">
        <span class="control-label">选择策略:</span>
        <NCheckboxGroup v-model:value="selectedStrategies">
          <NCheckbox
            v-for="s in strategies"
            :key="s.id"
            :value="s.id"
            :label="s.name"
          >
            {{ s.name }}
          </NCheckbox>
        </NCheckboxGroup>
      </div>

      <div class="control-section">
        <span class="control-label">对比指标:</span>
        <NCheckboxGroup v-model:value="compareMetrics">
          <NCheckbox
            v-for="m in availableMetrics"
            :key="m.value"
            :value="m.value"
            :label="m.label"
          >
            {{ m.label }}
          </NCheckbox>
        </NCheckboxGroup>
      </div>
    </div>

    <div class="chart-section">
      <h4>净值曲线对比</h4>
      <div ref="chartRef" class="comparison-chart"></div>
    </div>

    <div class="metrics-table">
      <h4>策略指标对比</h4>
      <NDataTable
        :data="selectedStrategyData"
        :columns="columns"
        :bordered="false"
      />
    </div>

    <div v-if="compareMetrics.length >= 3" class="radar-section">
      <h4>综合能力雷达图</h4>
      <div class="radar-chart">
        <div class="radar-placeholder">
          雷达图展示区域 - 需要集成ECharts雷达图
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.multi-strategy-compare {
  padding: 20px;
  background: var(--n-body-color);
  min-height: 100%;
}

.compare-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--n-border-color);
}

.compare-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 30px;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--n-color-embedded);
  border-radius: 6px;
}

.control-section {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.control-label {
  font-weight: bold;
  min-width: 80px;
  padding-top: 4px;
  color: var(--n-text-color-1);
}

.chart-section {
  margin-bottom: 30px;
}

.chart-section h4 {
  margin-bottom: 16px;
  color: var(--n-text-color-1);
}

.comparison-chart {
  height: 400px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
}

.metrics-table {
  margin-bottom: 30px;
}

.metrics-table h4 {
  margin-bottom: 16px;
  color: var(--n-text-color-1);
}

.radar-section h4 {
  margin-bottom: 16px;
  color: var(--n-text-color-1);
}

.radar-chart {
  height: 300px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.radar-placeholder {
  color: var(--n-text-color-3);
  font-size: 16px;
}

@media (max-width: 768px) {
  .compare-controls {
    flex-direction: column;
    gap: 16px;
  }

  .control-section {
    flex-direction: column;
    align-items: flex-start;
  }

  .control-label {
    margin-bottom: 8px;
  }
}
</style>
