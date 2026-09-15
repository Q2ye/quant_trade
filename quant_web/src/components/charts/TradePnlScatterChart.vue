<!-- TradePnlScatterChart.vue — 盈亏散点图（ECharts）
     x=退出时间, y=单笔盈亏%, 颜色=赚/亏（A股红涨绿跌）, 气泡大小=仓位金额 -->
<script setup lang="ts">
import { computed } from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { ScatterChart } from "echarts/charts";
import { TooltipComponent, GridComponent, DataZoomComponent } from "echarts/components";
use([CanvasRenderer, ScatterChart, TooltipComponent, GridComponent, DataZoomComponent]);

export interface RoundTripPoint {
  symbol: string;
  exitDate: string;
  pnlRate: number;
  holdingDays: number;
  positionSize: number;
  isWin: boolean;
}

const props = withDefaults(
  defineProps<{
    data: RoundTripPoint[];
    height?: number;
    loading?: boolean;
    error?: boolean;
    title?: string;
  }>(),
  { data: () => [], height: 300, loading: false, error: false, title: "盈亏散点图" },
);

const emit = defineEmits<{ retry: [] }>();
const hasData = computed(() => props.data.length > 0);

const chartOption = computed(() => {
  if (!props.data.length) return undefined;
  // 气泡大小=仓位：线性映射直径（6~16px），仓位差异可见且不过度重叠
  const sizeOf = (size: number) => Math.max(6, Math.min(16, 6 + size / 12000));
  const toPoint = (d: RoundTripPoint) => ({
    value: [d.exitDate, d.pnlRate * 100, d.positionSize],
    symbol: d.symbol,
    holdingDays: d.holdingDays,
  });
  return {
    grid: { top: 20, right: 20, bottom: 40, left: 55 },
    xAxis: {
      type: "category" as const,
      data: [...new Set(props.data.map((d) => d.exitDate))].sort(),
      axisLabel: { fontSize: 9, interval: Math.max(0, Math.floor(props.data.length / 10)) },
    },
    yAxis: {
      type: "value" as const,
      name: "单笔盈亏 %",
      axisLabel: { fontSize: 10, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    },
    tooltip: {
      trigger: "item" as const,
      formatter: (p: any) => {
        const d = p.data;
        if (!d) return "";
        const pnl = d.value[1];
        return `${d.symbol}<br/>退出: ${d.value[0]}<br/>盈亏: ${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}%<br/>持仓 ${d.holdingDays} 天<br/>仓位 ¥${(d.value[2] / 1e4).toFixed(1)}万`;
      },
    },
    dataZoom: [{ type: "inside" as const, xAxisIndex: 0, start: 0, end: 100, moveOnMouseMove: false }],
    series: [
      {
        type: "scatter" as const,
        symbol: "circle",
        data: props.data.map(toPoint),
        symbolSize: (v: any) => sizeOf(v[2]),
        itemStyle: {
          // A股红涨绿跌：盈利红、亏损绿
          color: (params: any) =>
            params.data.value[1] >= 0 ? "rgba(239,83,80,0.75)" : "rgba(38,166,154,0.75)",
        },
        emphasis: {
          scale: 1.5,
          itemStyle: { borderColor: "#fff", borderWidth: 1 },
        },
      },
    ],
  };
});
</script>

<template>
  <div class="pnl-scatter-container">
    <div v-if="title" class="chart-title-bar"><h5>{{ title }}</h5></div>
    <n-skeleton v-if="loading" :height="height + 'px'" width="100%" />
    <n-result v-else-if="error" status="500" title="盈亏散点加载失败">
      <template #footer>
        <n-button type="primary" size="small" @click="emit('retry')">重试</n-button>
      </template>
    </n-result>
    <n-empty v-else-if="!hasData" description="暂无成交配对数据" style="padding: 30px" />
    <v-chart v-else :option="chartOption" autoresize :style="{ height: height + 'px', width: '100%' }" />
  </div>
</template>

<style lang="scss" scoped>
.pnl-scatter-container { width: 100%; position: relative; zoom: 1.25; }
.chart-title-bar h5 { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
</style>
