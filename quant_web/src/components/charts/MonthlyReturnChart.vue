<!-- MonthlyReturnChart.vue — 月度收益热力图（thermal calendar）
     行=年份、列=月份，单元格颜色=收益（红涨绿跌，深度=幅度），悬停显示 YYYY-MM +X.X% -->
<script setup lang="ts">
import { computed } from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { HeatmapChart } from "echarts/charts";
import { TooltipComponent, GridComponent, VisualMapComponent } from "echarts/components";
use([CanvasRenderer, HeatmapChart, TooltipComponent, GridComponent, VisualMapComponent]);

export interface MonthlyReturnPoint {
  month: string; // 'YYYY-MM'
  return: number; // ratio (e.g. 0.05 = +5%)
}

const props = withDefaults(
  defineProps<{
    data: MonthlyReturnPoint[];
    title?: string;
    height?: number;
    loading?: boolean;
    error?: boolean;
    unit?: "percent" | "amount";
  }>(),
  { data: () => [], title: "月度收益", height: 300, loading: false, error: false, unit: "percent" },
);

const emit = defineEmits<{ retry: [] }>();
const hasData = computed(() => props.data.length > 0);

const MONTHS = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"];

const chartOption = computed(() => {
  if (!props.data.length) return undefined;
  // 年份（最新在上）
  const years = [...new Set(props.data.map((d) => d.month.slice(0, 4)))].sort().reverse();
  const toVal = (r: number) => (props.unit === "percent" ? r * 100 : r);
  const dataMap = new Map(props.data.map((d) => [d.month, toVal(d.return)]));

  // 构建热力矩阵 [monthIdx, yearIdx, returnPct]
  const heatData: Array<[number, number, number]> = [];
  for (let yi = 0; yi < years.length; yi++) {
    for (let mi = 0; mi < 12; mi++) {
      const key = `${years[yi]}-${MONTHS[mi]}`;
      const val = dataMap.get(key);
      if (val !== undefined && val !== null) {
        heatData.push([mi, yi, Number(val.toFixed(2))]);
      }
    }
  }
  const maxAbs = Math.max(1, ...heatData.map((d) => Math.abs(d[2])));

  return {
    grid: { left: 46, right: 12, top: 10, bottom: 40 },
    xAxis: {
      type: "category" as const,
      data: MONTHS.map((m) => `${Number(m)}月`),
      splitArea: { show: false },
      axisLabel: { fontSize: 10, color: "#8898b8" },
      axisLine: { lineStyle: { color: "#30363d" } },
    },
    yAxis: {
      type: "category" as const,
      data: years,
      splitArea: { show: false },
      axisLabel: { fontSize: 11, color: "#8898b8" },
      axisLine: { lineStyle: { color: "#30363d" } },
    },
    tooltip: {
      formatter: (p: any) => {
        const d = p.data;
        if (!d) return "";
        const year = years[d[1]];
        const month = MONTHS[d[0]];
        const val = d[2];
        const label = props.unit === "percent" ? "月度收益率" : "月收益";
        const text = props.unit === "percent"
          ? `${val > 0 ? "+" : ""}${val.toFixed(2)}%`
          : `${val > 0 ? "+" : ""}¥${Number(val).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
        return `${year}-${month}<br/>${label} <b style="color:${val >= 0 ? "#f0483e" : "#18a058"}">${text}</b>`;
      },
    },
    visualMap: {
      min: -maxAbs,
      max: maxAbs,
      show: false,
      inRange: { color: ["#16a34a", "#24292f", "#ef4444"] }, // 绿(亏) → 中性 → 红(赚)
    },
    series: [
      {
        type: "heatmap" as const,
        data: heatData,
        label: {
          show: true,
          fontSize: 9,
          color: "#ffffff",
          formatter: (p: any) => {
            const v = p.data[2];
            if (v === 0) return "";
            if (props.unit === "amount") {
              const abs = Math.abs(v);
              const w = abs >= 10000 ? `${(v / 10000).toFixed(1)}万` : v.toFixed(0);
              return (v > 0 ? "+" : "") + w;
            }
            return (v > 0 ? "+" : "") + v.toFixed(1) + "%";
          },
        },
        itemStyle: { borderColor: "#161b22", borderWidth: 2 },
        emphasis: { itemStyle: { borderColor: "#448aff", borderWidth: 2 } },
      },
    ],
  };
});
</script>

<template>
  <div class="monthly-heatmap-container">
    <div v-if="title" class="chart-title-bar"><h5>{{ title }}</h5></div>
    <n-skeleton v-if="loading" :height="height + 'px'" width="100%" />
    <n-result v-else-if="error" status="500" title="月度收益加载失败">
      <template #footer><n-button type="primary" size="small" @click="emit('retry')">重试</n-button></template>
    </n-result>
    <n-empty v-else-if="!hasData" description="暂无月度收益数据" style="padding: 30px" />
    <v-chart v-else :option="chartOption" autoresize :style="{ height: height + 'px', width: '100%' }" />
  </div>
</template>

<style lang="scss" scoped>
.monthly-heatmap-container { width: 100%; position: relative; zoom: 1.25; }
.chart-title-bar h5 { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
</style>
