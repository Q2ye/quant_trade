<!-- DailyPnLChart.vue — 每日盈亏柱状图（ECharts）-->
<script setup lang="ts">
import { computed } from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart } from "echarts/charts";
import { TooltipComponent, GridComponent } from "echarts/components";
use([CanvasRenderer, BarChart, TooltipComponent, GridComponent]);

export interface DailyPnLPoint {
  trade_date: string;
  daily_return: number;
  daily_pnl: number;
}

const props = withDefaults(
  defineProps<{
    data: DailyPnLPoint[];
    height?: number;
    loading?: boolean;
    error?: boolean;
    title?: string;
  }>(),
  { data: () => [], height: 260, loading: false, error: false, title: "每日盈亏" },
);

const emit = defineEmits<{ retry: [] }>();
const hasData = computed(() => props.data.length > 0);

const chartOption = computed(() => {
  if (!props.data.length) return null;
  const dates = props.data.map((d) => d.trade_date?.slice(5) ?? "");
  const pnls = props.data.map((d) => d.daily_pnl ?? 0);
  return {
    grid: { top: 10, right: 10, bottom: 25, left: 55 },
    xAxis: {
      type: "category" as const,
      data: dates,
      axisLabel: { fontSize: 9, interval: Math.floor(dates.length / 8) },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, formatter: (v: number) => (v / 1e4).toFixed(0) + "万" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    },
    tooltip: {
      trigger: "axis" as const,
      formatter: (params: any) => {
        const p = params[0];
        const val = p.value;
        const idx = p.dataIndex;
        const ret = props.data[idx]?.daily_return ?? 0;
        return `${props.data[idx]?.trade_date ?? ""}<br/>盈亏: ${val > 0 ? "+" : ""}${(val / 1e4).toFixed(2)}万<br/>收益率: ${(ret * 100).toFixed(2)}%`;
      },
    },
    series: [
      {
        type: "bar" as const,
        data: pnls.map((v: number) => ({
          value: v,
          itemStyle: { color: v >= 0 ? "rgba(239,83,80,0.7)" : "rgba(38,166,154,0.7)" },
        })),
      },
    ],
  };
});
</script>

<template>
  <div class="daily-pnl-container">
    <div v-if="title" class="chart-title-bar"><h5>{{ title }}</h5></div>
    <n-skeleton v-if="loading" :height="height + 'px'" width="100%" />
    <n-result v-else-if="error" status="500" title="每日盈亏加载失败">
      <template #footer><n-button type="primary" size="small" @click="emit('retry')">重试</n-button></template>
    </n-result>
    <n-empty v-else-if="!hasData" description="暂无每日盈亏数据" style="padding: 30px" />
    <v-chart v-else :option="chartOption" autoresize :style="{ height: height + 'px', width: '100%' }" />
  </div>
</template>

<style lang="scss" scoped>
.daily-pnl-container { width: 100%; position: relative; zoom: 1.25; }
.chart-title-bar h5 { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
</style>
