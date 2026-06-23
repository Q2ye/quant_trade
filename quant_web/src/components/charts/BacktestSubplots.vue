<!-- BacktestSubplots.vue — 回测三子图：累计收益率 + 每日盈亏 + 每日成交额，共享X轴 -->
<script setup lang="ts">
import { computed } from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, BarChart, CustomChart } from "echarts/charts";
import {
  TooltipComponent, GridComponent, LegendComponent, DataZoomComponent,
  AxisPointerComponent,
} from "echarts/components";
use([CanvasRenderer, LineChart, BarChart, CustomChart, TooltipComponent, GridComponent, LegendComponent, DataZoomComponent, AxisPointerComponent]);

export interface EquityPoint { date: string; value: number; }
export interface BenchmarkPoint { date: string; value: number; }
export interface DailyPnLPoint { trade_date: string; daily_return: number; daily_pnl: number; }
export interface TurnoverPoint { trade_date: string; turnover: number; }
export interface DrawdownPoint { date: string; value: number; }

const props = withDefaults(defineProps<{
  equity: EquityPoint[];
  benchmark?: BenchmarkPoint[];
  dailyReturns: DailyPnLPoint[];
  dailyTurnover: TurnoverPoint[];
  drawdown?: DrawdownPoint[];
  height?: number;
  loading?: boolean;
  error?: boolean;
}>(), {
  equity: () => [], benchmark: () => [], dailyReturns: () => [], dailyTurnover: () => [], drawdown: () => [],
  height: 680, loading: false, error: false,
});

const emit = defineEmits<{ retry: [] }>();
const hasData = computed(() => props.equity.length > 0);
const chartOption = computed(() => {
  if (!props.equity.length) return null;

  // 收集所有日期，构建统一X轴
  const dateSet = new Set<string>();
  props.equity.forEach((p) => dateSet.add(p.date));
  props.dailyReturns.forEach((p) => dateSet.add(p.trade_date));
  props.dailyTurnover.forEach((p) => dateSet.add(p.trade_date));
  const allDates = [...dateSet].sort();

  // 日期格式化（只显示月-日）
  const dateLabels = allDates.map((d) => d.slice(5));

  // 策略收益线
  const eqMap = new Map<string, number>();
  props.equity.forEach((p) => eqMap.set(p.date, p.value));
  const eqData = allDates.map((d) => {
    const v = eqMap.get(d);
    return v != null ? Number(v.toFixed(2)) : null;
  });

  // 基准收益线
  const bmMap = new Map<string, number>();
  props.benchmark.forEach((p) => bmMap.set(p.date, p.value));
  const bmData = allDates.map((d) => {
    const v = bmMap.get(d);
    return v != null ? Number(v.toFixed(2)) : null;
  });

  // 超额收益
  const excessData = allDates.map((_d, i) => {
    const e = eqData[i];
    const b = bmData[i];
    return e != null && b != null ? Number((e - b).toFixed(2)) : null;
  });

  // 每日盈亏
  const pnlMap = new Map<string, number>();
  props.dailyReturns.forEach((p) => pnlMap.set(p.trade_date, p.daily_pnl));
  const pnlData = allDates.map((d) => {
    const v = pnlMap.get(d);
    return v != null ? Number(v.toFixed(2)) : null;
  });
  const pnlColors = pnlData.map((v) => v != null ? (v >= 0 ? "rgba(239,83,80,0.7)" : "rgba(38,166,154,0.7)") : "transparent");

  // 回撤数据
  const ddMap = new Map<string, number>();
  props.drawdown.forEach((p) => ddMap.set(p.date, p.value));
  const ddData = allDates.map((d) => ddMap.get(d) ?? null);

  // 每日成交额
  const toMap = new Map<string, number>();
  props.dailyTurnover.forEach((p) => toMap.set(p.trade_date, p.turnover));
  const toData = allDates.map((d) => {
    const v = toMap.get(d);
    return v != null ? Number(v.toFixed(2)) : null;
  });

  const labelInterval = Math.max(1, Math.floor(allDates.length / 8));

  return {
    grid: [
      { top: 50, bottom: "68%", left: 55, right: 40 },     // ① 累计收益率（增大高度）
      { top: "35%", bottom: "58%", left: 55, right: 40 },  // ② 回撤分析
      { top: "46%", bottom: "32%", left: 55, right: 40 },  // ③ 每日盈亏
      { top: "69%", bottom: 30, left: 55, right: 40 },     // ④ 每日成交额
    ],
    xAxis: [
      { gridIndex: 0, type: "category" as const, data: dateLabels, axisLabel: { show: false }, axisTick: { show: false } },
      { gridIndex: 1, type: "category" as const, data: dateLabels, axisLabel: { show: false }, axisTick: { show: false } },
      { gridIndex: 2, type: "category" as const, data: dateLabels, axisLabel: { show: false }, axisTick: { show: false } },
      { gridIndex: 3, type: "category" as const, data: dateLabels, axisLabel: { fontSize: 9, interval: labelInterval }, axisTick: { show: false } },
    ],
    yAxis: [
      { gridIndex: 0, type: "value" as const, interval: 10, axisLabel: { fontSize: 10, formatter: (v: number) => v.toFixed(0) + "%" }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } } },
      { gridIndex: 1, type: "value" as const, interval: 0.1, axisLabel: { fontSize: 10, formatter: (v: number) => (v * 100).toFixed(0) + "%" }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } }, inverse: true },
      { gridIndex: 2, type: "value" as const, axisLabel: { fontSize: 10, formatter: (v: number) => (v / 1e4).toFixed(0) + "万" }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } } },
      { gridIndex: 3, type: "value" as const, axisLabel: { fontSize: 10, formatter: (v: number) => (v / 1e4).toFixed(0) + "万" }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } } },
    ],
    legend: { top: 5, textStyle: { fontSize: 10, color: "#a0a0a0" }, data: ["策略收益", "基准收益", "超额收益"] },
    tooltip: {
      trigger: "axis" as const,
      formatter: (params: any) => {
        const items = Array.isArray(params) ? params : [params];
        const d = allDates[items[0]?.dataIndex] ?? "";
        let html = `<strong>${d}</strong><br/>`;
        for (const p of items) {
          if (p.seriesName === "每日盈亏") {
            const v = p.value;
            html += `${p.marker} ${p.seriesName}: ${v != null ? (v >= 0 ? "+" : "") + (v / 1e4).toFixed(2) + "万" : "-"}<br/>`;
          } else if (p.seriesName === "每日成交额") {
            html += `${p.marker} ${p.seriesName}: ${p.value != null ? (p.value / 1e4).toFixed(2) + "万" : "-"}<br/>`;
          } else {
            html += `${p.marker} ${p.seriesName}: ${p.value != null ? p.value.toFixed(2) + "%" : "-"}<br/>`;
          }
        }
        return html;
      },
    },
    graphic: [
      { type: "text" as const, right: 4, top: "8%", style: { text: "累\n计\n收\n益\n率", fill: "#888", fontSize: 10, lineHeight: 14 } },
      { type: "text" as const, right: 4, top: "35%", style: { text: "回\n撤\n分\n析", fill: "#888", fontSize: 10, lineHeight: 14 } },
      { type: "text" as const, right: 4, top: "54%", style: { text: "每\n日\n盈\n亏", fill: "#888", fontSize: 10, lineHeight: 14 } },
      { type: "text" as const, right: 4, top: "79%", style: { text: "每\n日\n成\n交\n额", fill: "#888", fontSize: 10, lineHeight: 14 } },
    ],
    dataZoom: [
      { type: "inside" as const, xAxisIndex: [0, 1, 2, 3], start: 0, end: 100 },
    ],
    series: [
      // 子图1: 累计收益率
      { name: "策略收益", type: "line" as const, xAxisIndex: 0, yAxisIndex: 0, data: eqData, symbol: "none", color: "#ef5350", lineStyle: { width: 2 }, itemStyle: { color: "#ef5350" }, connectNulls: true },
      { name: "基准收益", type: "line" as const, xAxisIndex: 0, yAxisIndex: 0, data: bmData, symbol: "none", color: "#448aff", lineStyle: { width: 1.5, type: "dashed" }, itemStyle: { color: "#448aff" }, connectNulls: true },
      { name: "超额收益", type: "line" as const, xAxisIndex: 0, yAxisIndex: 0, data: excessData, symbol: "none", color: "#ff9800", lineStyle: { width: 1, type: "dotted" }, itemStyle: { color: "#ff9800" }, connectNulls: true, areaStyle: { color: "rgba(255,152,0,0.08)" } },
      // 子图2: 回撤分析（面积图，负值向下填充）
      { name: "回撤", type: "line" as const, xAxisIndex: 1, yAxisIndex: 1, data: ddData, symbol: "none", color: "#ef4444", lineStyle: { width: 1.5 }, itemStyle: { color: "#ef4444" }, areaStyle: { color: "rgba(239,68,68,0.15)" }, connectNulls: true },
      // 子图3: 每日盈亏
      { name: "每日盈亏", type: "bar" as const, xAxisIndex: 2, yAxisIndex: 2, data: pnlData.map((v, i) => ({ value: v ?? 0, itemStyle: { color: pnlColors[i] || "transparent" } })) },
      // 子图4: 每日成交额
      { name: "每日成交额", type: "bar" as const, xAxisIndex: 3, yAxisIndex: 3, data: toData.map((v) => ({ value: v ?? 0, itemStyle: { color: "rgba(68,138,255,0.6)" } })) },
    ],
  };
});
</script>

<template>
  <div class="backtest-subplots">
    <n-skeleton v-if="loading" :height="height + 'px'" width="100%" />
    <n-result v-else-if="error" status="500" title="图表加载失败">
      <template #footer><n-button type="primary" size="small" @click="emit('retry')">重试</n-button></template>
    </n-result>
    <n-empty v-else-if="!hasData" description="暂无数据" style="padding: 40px" />
    <v-chart v-else :option="chartOption" autoresize :style="{ height: height + 'px', width: '100%' }" />
  </div>
</template>

<style lang="scss" scoped>
.backtest-subplots { width: 100%; position: relative; zoom: 1.25; }
</style>
