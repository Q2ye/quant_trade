<!-- MonthlyReturnChart.vue — lightweight-charts 月度收益柱状图（从 vue-echarts 迁移）
     使用 HistogramSeries，基于时间轴，正收益绿色 / 负收益红色 -->
<script setup lang="ts">
import { computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { NEmpty } from "naive-ui";
import {
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type HistogramData,
  type Time,
} from "lightweight-charts";
import { useChartLifecycle } from "@/composables/useChartLifecycle";

export interface MonthlyReturnPoint {
  month: string; // 'YYYY-MM'
  return: number; // ratio (e.g. 0.05 = +5%)
}

const props = withDefaults(
  defineProps<{
    data: MonthlyReturnPoint[];
    title?: string;
    height?: number;
  }>(),
  {
    data: () => [],
    title: "月度收益",
    height: 300,
  },
);

const hasData = computed(() => props.data.length > 0);

const {
  chartContainer,
  createChartInstance,
  destroyChart,
  handleResize,
  bindGlobalEvents,
  unbindGlobalEvents,
  getChart,
} = useChartLifecycle({
  height: props.height,
  timeScale: { timeVisible: false },
  rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
});

let chart: IChartApi | null = null;
let series: ISeriesApi<"Histogram", Time> | null = null;

/** Convert 'YYYY-MM' to lightweight-charts Time (first day of month) */
function monthToTime(month: string): Time {
  const m = month.slice(0, 7); // 'YYYY-MM'
  return `${m}-01` as Time; // first day of month
}

function toHistogramData(data: MonthlyReturnPoint[]): HistogramData[] {
  return data.map((d) => {
    const pct = d.return * 100; // ratio → percentage
    return {
      time: monthToTime(d.month),
      value: Math.round(pct * 100) / 100, // round to 2 decimal places
      color: pct >= 0 ? "rgba(24,160,88,0.65)" : "rgba(208,48,80,0.65)",
    };
  });
}

function renderChart() {
  const el = chartContainer.value;
  if (!el) return;
  const w = el.clientWidth;
  if (!w || w <= 0 || !props.data.length) return;

  const isNew = !chart;
  if (isNew) {
    chart = createChartInstance();
    if (!chart) return;

    series = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "custom",
        formatter: (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`,
      },
    }) as ISeriesApi<"Histogram", Time>;
  }

  series!.setData(toHistogramData(props.data));
  chart!.timeScale().fitContent();
}

watch(
  () => props.data,
  async (val) => {
    if (!val?.length) {
      destroyChart();
      chart = null;
      series = null;
      return;
    }
    await nextTick();
    renderChart();
  },
  { deep: true, immediate: true },
);

onMounted(() => {
  bindGlobalEvents();
});

onBeforeUnmount(() => {
  destroyChart();
  chart = null;
  series = null;
  unbindGlobalEvents();
});

defineExpose({
  fitContent() { chart?.timeScale().fitContent(); },
  resize() { handleResize(); },
  getChart,
});
</script>

<template>
  <div class="monthly-return-wrapper">
    <div v-if="title" class="chart-header">
      <h5 class="chart-title">{{ title }}</h5>
    </div>
    <n-empty
      v-if="!hasData"
      description="暂无月度收益数据"
      size="small"
      style="padding: 20px 0"
    />
    <div
      v-show="hasData"
      ref="chartContainer"
      class="monthly-chart"
      :style="{ height: height + 'px' }"
    />
  </div>
</template>

<style lang="scss" scoped>
.monthly-return-wrapper {
  width: 100%;
  zoom: 1.25; /* 抵消 html { zoom: 0.8 }，恢复 chart 内部坐标系统与 OS 鼠标一致 */
}
.chart-header {
  margin-bottom: 8px;
}
.chart-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.monthly-chart {
  width: 100%;
}
</style>
