<!-- IndustryRankChart.vue — 排名迁移 Bump Chart -->
<script setup lang="ts">
import { computed } from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
]);

import type { SwHeatmapItem } from "@/types/entities/market";

const props = withDefaults(
  defineProps<{
    data: SwHeatmapItem[];
    loading?: boolean;
    error?: boolean;
    selectedCode?: string;
  }>(),
  { data: () => [], loading: false, error: false, selectedCode: "" },
);

const emit = defineEmits<{ select: [code: string, name: string]; retry: [] }>();

const windows = [
  { key: "pct_1d" as keyof SwHeatmapItem, label: "1日" },
  { key: "pct_5d" as keyof SwHeatmapItem, label: "5日" },
  { key: "pct_10d" as keyof SwHeatmapItem, label: "10日" },
  { key: "pct_20d" as keyof SwHeatmapItem, label: "20日" },
  { key: "pct_30d" as keyof SwHeatmapItem, label: "30日" },
  { key: "pct_60d" as keyof SwHeatmapItem, label: "60日" },
];

const bumpOption = computed(() => {
  if (!props.data.length) return null;

  // Compute rank for each industry per window
  const ranks: { name: string; code: string; data: (number | null)[] }[] = [];
  for (const item of props.data) {
    const series: (number | null)[] = [];
    for (const w of windows) {
      const val = (item[w.key] as number | null) ?? null;
      if (val != null) {
        const better = props.data.filter(
          (x) => ((x[w.key] as number | null) ?? -9999) > val,
        ).length;
        series.push(better + 1);
      } else {
        series.push(null);
      }
    }
    ranks.push({ name: item.name, code: item.code, data: series });
  }

  // Sort by latest rank
  ranks.sort((a, b) => {
    const la = a.data.findLast((v) => v != null) ?? 99;
    const lb = b.data.findLast((v) => v != null) ?? 99;
    return (la ?? 99) - (lb ?? 99);
  });

  return {
    grid: { top: 10, right: 40, bottom: 30, left: 70 },
    xAxis: {
      type: "category",
      data: windows.map((w) => w.label),
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "value",
      inverse: true,
      min: 0.5,
      max: props.data.length + 0.5,
      interval: 1,
      axisLabel: { fontSize: 10 },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
    },
    tooltip: { trigger: "item" },
    legend: {
      type: "scroll",
      bottom: 0,
      textStyle: { fontSize: 9 },
      data: ranks.map((r) => r.name),
    },
    series: ranks.map((r) => ({
      name: r.name,
      type: "line",
      data: r.data,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: {
        width: props.selectedCode && r.code === props.selectedCode ? 3 : 1,
      },
      emphasis: { focus: "series", lineStyle: { width: 3 } },
    })),
  };
});

function handleClick(params: any) {
  if (params.seriesName) {
    const item = props.data.find((x) => x.name === params.seriesName);
    if (item) emit("select", item.code, item.name);
  }
}
</script>

<template>
  <div class="bump-chart">
    <n-skeleton v-if="loading" height="420px" width="100%" />
    <n-result v-else-if="error" status="500" title="数据加载失败">
      <template #footer
        ><n-button @click="emit('retry')">重试</n-button></template
      >
    </n-result>
    <n-empty
      v-else-if="!bumpOption"
      description="暂无行业排名数据"
      style="padding: 80px"
    />
    <VChart
      v-else
      :option="bumpOption"
      autoresize
      style="height: 420px"
      @click="handleClick"
    />
  </div>
</template>

<style lang="scss" scoped>
.bump-chart {
  width: 100%;
}
</style>
