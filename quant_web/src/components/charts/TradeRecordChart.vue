<!-- TradeRecordChart.vue — 成交记录图：收盘价折线 + 买卖标记 -->
<script setup lang="ts">
import { computed } from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, ScatterChart } from "echarts/charts";
import { TooltipComponent, GridComponent, LegendComponent } from "echarts/components";
use([CanvasRenderer, LineChart, ScatterChart, TooltipComponent, GridComponent, LegendComponent]);

export interface TradeRecord {
  id: string;
  symbol: string;
  direction: "buy" | "sell";
  date: string;
  price: number;
  quantity: number;
}

const props = withDefaults(
  defineProps<{
    trades: TradeRecord[];
    closePrices?: Array<{ date: string; price: number }>;
    height?: number;
    loading?: boolean;
    error?: boolean;
    title?: string;
    symbol: string;
  }>(),
  { trades: () => [], closePrices: () => [], height: 300, loading: false, error: false, title: "成交记录", symbol: "" },
);

const emit = defineEmits<{ retry: [] }>();
const hasData = computed(() => props.trades.length > 0);

const chartOption = computed(() => {
  const trades = props.trades;

  // 从成交记录中提取日期→均价作为参考价格线
  const priceByDate = new Map<string, number[]>();
  trades.forEach((t) => {
    const d = t.date?.slice(0, 10) || "";
    if (!priceByDate.has(d)) priceByDate.set(d, []);
    priceByDate.get(d)!.push(t.price);
  });
  const allDates = [...priceByDate.keys()].sort();
  const lineData = allDates.map((d) => {
    const prices = priceByDate.get(d)!;
    return prices.reduce((a, b) => a + b, 0) / prices.length;
  });

  const buyTrades = trades.filter((t) => t.direction === "buy");
  const sellTrades = trades.filter((t) => t.direction === "sell");

  const buyCoords = buyTrades.map((t) => {
    const idx = allDates.indexOf(t.date?.slice(0, 10));
    return idx >= 0 ? [idx, t.price] : null;
  }).filter(Boolean) as [number, number][];

  const sellCoords = sellTrades.map((t) => {
    const idx = allDates.indexOf(t.date?.slice(0, 10));
    return idx >= 0 ? [idx, t.price] : null;
  }).filter(Boolean) as [number, number][];

  const maxInterval = Math.floor(allDates.length / 6);

  return {
    grid: { top: 25, right: 10, bottom: 25, left: 55 },
    legend: { top: 2, textStyle: { fontSize: 10, color: "#a0a0a0" }, data: ["收盘价", "买入", "卖出"] },
    xAxis: {
      type: "category" as const, data: allDates,
      axisLabel: { fontSize: 9, interval: maxInterval > 0 ? maxInterval : 1 },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10 },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    },
    tooltip: {
      trigger: "axis" as const,
      formatter: (params: any) => {
        const items = Array.isArray(params) ? params : [params];
        return items.map((p: any) => {
          if (p.seriesName === "收盘价") return `${allDates[p.dataIndex]}<br/>均价: ${p.value?.toFixed(2) ?? "-"}`;
          if (p.seriesName === "买入" || p.seriesName === "卖出") return `${p.seriesName}: ${p.value?.[1]?.toFixed?.(2) ?? "-"}`;
          return "";
        }).join("<br/>");
      },
    },
    series: [
      {
        name: "收盘价", type: "line" as const, data: lineData,
        connectNulls: true, symbol: "none",
        lineStyle: { color: "#7C3AED", width: 1.5 },
      },
      {
        name: "买入", type: "scatter" as const, data: buyCoords,
        symbolSize: 10, itemStyle: { color: "#ef5350" },
        symbol: "triangle",
      },
      {
        name: "卖出", type: "scatter" as const, data: sellCoords,
        symbolSize: 10, itemStyle: { color: "#26a69a" },
        symbol: "triangle",
        symbolRotate: 180,
      },
    ],
  };
});
</script>

<template>
  <div class="trade-record-container">
    <div v-if="title" class="chart-title-bar"><h5>{{ title }}{{ symbol ? ` — ${symbol}` : "" }}</h5></div>
    <n-skeleton v-if="loading" :height="height + 'px'" width="100%" />
    <n-result v-else-if="error" status="500" title="成交记录加载失败">
      <template #footer><n-button type="primary" size="small" @click="emit('retry')">重试</n-button></template>
    </n-result>
    <n-empty v-else-if="!hasData" description="暂无成交记录" style="padding: 30px" />
    <v-chart v-else :option="chartOption" autoresize :style="{ height: height + 'px', width: '100%' }" />
  </div>
</template>

<style lang="scss" scoped>
.trade-record-container { width: 100%; position: relative; zoom: 1.25; }
.chart-title-bar h5 { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
</style>
