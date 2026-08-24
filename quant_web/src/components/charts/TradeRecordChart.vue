<!-- TradeRecordChart.vue — 成交记录图（lightweight-charts）
     价格参考线（每日均价）+ 买卖标记（SignalMarkerPrimitive）+ 悬停明细 -->
<script setup lang="ts">
import { watch, onMounted, onBeforeUnmount, nextTick, computed, ref } from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import {
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesPrimitive,
  type LineData,
  type Time,
} from "lightweight-charts";
import { useChartLifecycle } from "@/composables/useChartLifecycle";
import { usePrimitiveManager } from "@/composables/usePrimitiveManager";
import { SignalMarkerPrimitive } from "./primitives/SignalMarker";
import type { SignalMarkerData } from "./primitives/types";

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
    height?: number;
    loading?: boolean;
    error?: boolean;
    title?: string;
    symbol: string;
  }>(),
  { trades: () => [], height: 300, loading: false, error: false, title: "成交记录", symbol: "" },
);

const emit = defineEmits<{ retry: [] }>();
const hasData = computed(() => props.trades.length > 0);

const {
  chartContainer,
  createChartInstance,
  destroyChart,
  handleResize,
  bindGlobalEvents,
  unbindGlobalEvents,
  getChart,
} = useChartLifecycle({ height: props.height, timeScale: { timeVisible: false } });

const primitiveManager = usePrimitiveManager();
let chart: IChartApi | null = null;
let priceSeries: ISeriesApi<"Line", Time> | null = null;
// 悬停明细（2026-08：显示当日成交）
const tradeTooltip = ref<{ x: number; y: number; date: string; lines: string[]; visible: boolean } | null>(null);
let _tooltipTimer: ReturnType<typeof setTimeout> | null = null;
let _dayTradesCache = new Map<string, TradeRecord[]>();

function toTimeEpoch(dateStr: string): Time {
  const s = (dateStr?.slice(0, 10) || dateStr);
  return (Math.floor(new Date(s + "T00:00:00Z").getTime() / 1000)) as Time;
}

/** 每日均价参考线 + 当日成交明细缓存 + 买卖标记 */
function buildData() {
  const byDay = new Map<string, TradeRecord[]>();
  props.trades.forEach((t) => {
    const d = t.date?.slice(0, 10) || "";
    if (!d) return;
    if (!byDay.has(d)) byDay.set(d, []);
    byDay.get(d)!.push(t);
  });
  const dates = [...byDay.keys()].sort();
  _dayTradesCache = byDay;

  const lineData: LineData[] = dates.map((d) => {
    const trades = byDay.get(d)!;
    const avg = trades.reduce((a, t) => a + t.price, 0) / trades.length;
    return { time: toTimeEpoch(d), value: Number(avg.toFixed(4)) };
  });

  // 买卖标记（2026-08 修复：轻量图标记替代 echarts 散点，buy 信息明确展示）
  const markers: ISeriesPrimitive<Time>[] = props.trades.map((t, i) => {
    const d = t.date?.slice(0, 10) || "";
    const day = byDay.get(d);
    const refPrice = day ? day.reduce((a, x) => a + x.price, 0) / day.length : t.price;
    const isBuy = t.direction === "buy";
    const data: SignalMarkerData = {
      id: `tr-marker-${i}`,
      type: "signalMarker",
      time: toTimeEpoch(d) as Time,
      price: refPrice,
      direction: isBuy ? "buy" : "sell",
      shape: isBuy ? "arrowUp" : "arrowDown",
      color: isBuy ? "#ef5350" : "#26a69a",
      text: `${isBuy ? "买" : "卖"} ${t.symbol || ""} x${t.quantity}`,
    };
    return new SignalMarkerPrimitive(data);
  });

  return { lineData, markers };
}

function renderChart() {
  const el = chartContainer.value;
  if (!el) return;
  const w = el.clientWidth;
  if (!w || w <= 0 || !props.trades.length) return;

  const isNew = !chart;
  if (isNew) {
    // 时间轴配置经 useChartLifecycle options 传入（createChartInstance 不接受参数）
    chart = createChartInstance();
    if (!chart) return;

    priceSeries = chart.addSeries(LineSeries, {
      color: "#7C3AED",
      lineWidth: 2 as const,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 3,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    }) as ISeriesApi<"Line", Time>;

    primitiveManager.bind(priceSeries, () => {
      if (chart) {
        const r = chart.timeScale().getVisibleLogicalRange();
        if (r) chart.timeScale().setVisibleLogicalRange(r);
      }
    });

    // 悬停明细：显示当日全部成交（买入信息完整展示）
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || param.point === undefined) {
        tradeTooltip.value = null;
        return;
      }
      const dateStr = new Date((param.time as number) * 1000).toISOString().slice(0, 10);
      const dayTrades = _dayTradesCache.get(dateStr);
      if (dayTrades && dayTrades.length > 0) {
        const lines = dayTrades.map((t) =>
          `${t.direction === "buy" ? "买入" : "卖出"} ${t.symbol || ""} ${t.quantity}股 @${t.price.toFixed(2)}`,
        );
        tradeTooltip.value = { x: param.point.x, y: param.point.y, date: dateStr, lines, visible: true };
        if (_tooltipTimer) clearTimeout(_tooltipTimer);
        _tooltipTimer = setTimeout(() => { tradeTooltip.value = null; }, 3000);
      }
    });
  }

  const { lineData, markers } = buildData();
  priceSeries!.setData(lineData);
  const items = markers.map((m) => {
    const dataId = (m as any).getData?.()?.id || (m as any)._data?.id;
    return { id: dataId || `tr-p-${Math.random().toString(36).slice(2, 8)}`, primitive: m };
  });
  primitiveManager.syncPrimitives(items);

  if (lineData.length > 0) {
    chart!.timeScale().setVisibleRange({ from: lineData[0].time, to: lineData[lineData.length - 1].time });
  }
}

watch(
  () => props.trades,
  async (val) => {
    if (!val?.length) {
      primitiveManager.detachAll();
      destroyChart();
      chart = null;
      priceSeries = null;
      return;
    }
    await nextTick();
    renderChart();
  },
  { deep: true, immediate: true },
);

onMounted(() => bindGlobalEvents());

onBeforeUnmount(() => {
  primitiveManager.dispose();
  if (_tooltipTimer) clearTimeout(_tooltipTimer);
  destroyChart();
  chart = null;
  priceSeries = null;
  unbindGlobalEvents();
});

defineExpose({
  resize() { handleResize(); },
  getChart,
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
    <div
      v-show="hasData && !loading && !error"
      ref="chartContainer"
      class="trade-chart"
      :style="{ height: height + 'px' }"
    />
    <!-- 悬停明细 -->
    <div
      v-if="tradeTooltip?.visible"
      class="trade-tooltip"
      :style="{ left: tradeTooltip.x + 10 + 'px', top: tradeTooltip.y + 8 + 'px' }"
    >
      <div class="tt-date">{{ tradeTooltip.date }}</div>
      <div v-for="(ln, i) in tradeTooltip.lines" :key="i" class="tt-line">{{ ln }}</div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.trade-record-container { width: 100%; position: relative; zoom: 1.25; }
.chart-title-bar h5 { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
.trade-chart { width: 100%; }
.trade-tooltip {
  position: absolute; z-index: 10; pointer-events: none;
  background: var(--color-bg-card, rgba(18, 24, 40, 0.95));
  border: 1px solid var(--color-primary, #448aff); border-radius: 6px;
  padding: 6px 10px; font-size: 11px; line-height: 1.7; white-space: nowrap;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
}
.tt-date { font-weight: 600; color: var(--color-primary, #448aff); margin-bottom: 3px; font-size: 12px; }
.tt-line { color: var(--color-text-secondary, #8898b8); font-variant-numeric: tabular-nums; }
</style>
