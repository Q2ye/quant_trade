<!-- IndustryTrendChart.vue — 28 条行业线日度趋势，累计收益/日涨跌切换 -->
<script setup lang="ts">
import { computed, ref } from "vue";
import {
  NButtonGroup,
  NButton,
  NSelect,
  NSkeleton,
  NEmpty,
  NResult,
} from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
} from "echarts/components";
use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
]);

import type { IndustryTrendResponse, IndustryTrendSeries } from "@/types/entities/market";

const props = withDefaults(
  defineProps<{
    data: IndustryTrendResponse | null;
    loading?: boolean;
    error?: boolean;
    selectedCode?: string;
  }>(),
  { data: null, loading: false, error: false, selectedCode: "" },
);

const emit = defineEmits<{ select: [code: string, name: string]; retry: [] }>();

const days = ref(60);
const mode = ref<"cumulative" | "daily">("cumulative");
const filter = ref("all"); // all | top5 | bottom5

const daysOptions = [
  { label: "30日", value: 30 },
  { label: "60日", value: 60 },
  { label: "120日", value: 120 },
  { label: "250日", value: 250 },
];

const filterOptions = [
  { label: "全部", value: "all" },
  { label: "涨幅前5", value: "top5" },
  { label: "跌幅前5", value: "bottom5" },
];

function toCumulative(data: (number | null)[]): (number | null)[] {
  let cum = 100;
  return data.map((v) => {
    if (v == null) return null;
    cum *= 1 + v / 100;
    return +(cum - 100).toFixed(2);
  });
}

const chartOption = computed(() => {
  if (!props.data?.series?.length || !props.data?.dates?.length) return null;

  type _Series = IndustryTrendSeries & { _lastVal?: number };
  let series: _Series[] = [...props.data.series];

  // Filter top/bottom 5 based on latest cumulative return
  if (filter.value !== "all") {
    series = series.map((s) => {
      const cum = toCumulative(s.data);
      const last = cum[cum.length - 1];
      return { ...s, _lastVal: last ?? 0 };
    });
    series.sort((a, b) => (b._lastVal ?? 0) - (a._lastVal ?? 0));
    if (filter.value === "top5") series = series.slice(0, 5);
    else series = series.slice(-5).reverse();
  }

  return {
    grid: { top: 10, right: 50, bottom: 40, left: 60 },
    xAxis: {
      type: "category",
      data: props.data.dates.map((d: string) => d.slice(5)),
      axisLabel: { fontSize: 9 },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10, formatter: (v: number) => v + "%" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
    },
    tooltip: { trigger: "axis" },
    legend: {
      type: "scroll",
      bottom: 0,
      textStyle: { fontSize: 10 },
      data: series.map((s) => s.name),
      selected: props.selectedCode
        ? Object.fromEntries(
            series.map((s) => [s.name, s.code === props.selectedCode]),
          )
        : undefined,
    },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
      { type: "slider", bottom: 20, height: 14, start: 0, end: 100 },
    ],
    series: series.map((s, i) => ({
      name: s.name,
      type: "line",
      data: mode.value === "cumulative" ? toCumulative(s.data) : s.data,
      smooth: true,
      symbol: "none",
      lineStyle: {
        width: props.selectedCode && s.code === props.selectedCode ? 3 : 1.2,
      },
      emphasis: {
        focus: "series",
        lineStyle: { width: 3 },
        blur: { lineStyle: { opacity: 0.1 } },
      },
    })),
  };
});

function handleClick(params: any) {
  if (params.seriesName) {
    const s = props.data?.series.find((x) => x.name === params.seriesName);
    if (s) emit("select", s.code, s.name);
  }
}
</script>

<template>
  <div class="trend-chart">
    <!-- Controls -->
    <div class="trend-controls">
      <n-button-group size="tiny">
        <n-button
          v-for="d in daysOptions"
          :key="d.value"
          :type="days === d.value ? 'primary' : 'default'"
          @click="days = d.value"
          >{{ d.label }}</n-button
        >
      </n-button-group>

      <n-button-group size="tiny">
        <n-button
          :type="mode === 'cumulative' ? 'primary' : 'default'"
          @click="mode = 'cumulative'"
          >累计收益</n-button
        >
        <n-button
          :type="mode === 'daily' ? 'primary' : 'default'"
          @click="mode = 'daily'"
          >日涨跌</n-button
        >
      </n-button-group>

      <n-select
        v-model:value="filter"
        :options="filterOptions"
        size="tiny"
        style="width: 100px"
      />
    </div>

    <!-- States -->
    <n-skeleton v-if="loading" height="400px" width="100%" />
    <n-result v-else-if="error" status="500" title="数据加载失败">
      <template #footer
        ><n-button @click="emit('retry')">重试</n-button></template
      >
    </n-result>
    <n-empty
      v-else-if="!chartOption"
      description="暂无行业趋势数据"
      style="padding: 80px"
    />

    <!-- Chart -->
    <VChart
      v-else
      :option="chartOption"
      autoresize
      style="height: 420px"
      @click="handleClick"
    />
  </div>
</template>

<style lang="scss" scoped>
.trend-chart {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trend-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
