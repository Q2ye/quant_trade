<!-- LightweightKLine.vue — lightweight-charts K线图（重构版）
     使用 useChartLifecycle / usePrimitiveManager / useTimeCoordinate
     信号标记通过 SignalMarkerPrimitive 实现（替代 v5.2 移除的 setMarkers） -->
<script setup lang="ts">
import {
  ref,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
  computed,
} from "vue";
import { NSkeleton, NEmpty, NResult, NButton } from "naive-ui";
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesPrimitive,
  type CandlestickData,
  type HistogramData,
  type LineData,
  type Time,
} from "lightweight-charts";
import { useChartLifecycle } from "@/composables/useChartLifecycle";
import { useTimeCoordinate } from "@/composables/useTimeCoordinate";
import { usePrimitiveManager } from "@/composables/usePrimitiveManager";
import { SignalMarkerPrimitive } from "./primitives/SignalMarker";
import type { SignalMarkerData } from "./primitives/types";

// ---- public types ----
export interface SignalMarker {
  time: string; // 'YYYY-MM-DD'
  position: "aboveBar" | "belowBar";
  color: string;
  shape: "arrowUp" | "arrowDown";
  text: string;
  strategyName?: string;
}

interface KLineDataItem {
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  vol: number | null;
}

const props = withDefaults(
  defineProps<{
    data: KLineDataItem[];
    maLines?: number[];
    showVolume?: boolean;
    height?: number;
    loading?: boolean;
    error?: boolean;
    signalMarkers?: SignalMarker[];
    /** 附加绘制原语 (趋势线/水平线/标注等) */
    drawings?: ISeriesPrimitive<Time>[];
  }>(),
  {
    data: () => [],
    maLines: () => [5, 10, 20],
    showVolume: true,
    height: 420,
    loading: false,
    error: false,
    signalMarkers: () => [],
    drawings: () => [],
  },
);

const emit = defineEmits<{
  retry: [];
  crosshair: [
    data: {
      time: string;
      open: number;
      close: number;
      high: number;
      low: number;
      volume: number;
    },
  ];
  timeRangeChange: [range: { from: number; to: number }];
}>();

const hasData = computed(() => props.data.length > 0);

// ---- composables ----
const {
  chartContainer,
  createChartInstance,
  destroyChart,
  handleResize: lifecycleResize,
  handleThemeChange,
  bindGlobalEvents,
  unbindGlobalEvents,
  getChart,
} = useChartLifecycle({ height: props.height });

const { markDirty, updateCache } = useTimeCoordinate();
const primitiveManager = usePrimitiveManager();

let chart: IChartApi | null = null;
let candleSeries: ISeriesApi<"Candlestick", Time> | null = null;
let volumeSeries: ISeriesApi<"Histogram", Time> | null = null;
const maSeriesList: ISeriesApi<"Line", Time>[] = [];

const maColors = ["#ff9800", "#448AFF", "#E040FB", "#00bcd4", "#ff5722"];

// ---- helpers ----
function toTime(d: string): Time {
  return (d?.slice(0, 10) || d) as Time;
}

function transformData(raw: KLineDataItem[]): CandlestickData[] {
  return raw
    .filter(
      (d) =>
        d.open != null && d.close != null && d.low != null && d.high != null,
    )
    .map((d) => ({
      time: toTime(d.trade_date),
      open: d.open!,
      high: d.high!,
      low: d.low!,
      close: d.close!,
    }));
}

function calcMA(data: CandlestickData[], period: number): LineData[] {
  const result: LineData[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    result.push({ time: data[i].time, value: +(sum / period).toFixed(2) });
  }
  return result;
}

// ---- 创建图表实例（K线特有配置） ----
function initKLineChart() {
  const el = chartContainer.value;
  if (!el || chart) return;
  const w = el.clientWidth;
  if (!w || w <= 0) return;

  chart = createChartInstance();
  if (!chart || typeof chart.addSeries !== "function") {
    console.warn("[LightweightKLine] createChart 返回无效实例");
    chart = null;
    return;
  }

  // Candlestick
  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: "#e83939",
    downColor: "#1dbd60",
    borderUpColor: "#e83939",
    borderDownColor: "#1dbd60",
    wickUpColor: "#e83939",
    wickDownColor: "#1dbd60",
  }) as ISeriesApi<"Candlestick", Time>;

  // Volume
  if (props.showVolume) {
    volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#26a69a80",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    }) as ISeriesApi<"Histogram", Time>;
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
  }

  // Bind primitive manager to candle series
  primitiveManager.bind(
    candleSeries,
    () => chart?.timeScale().fitContent(),
  );

  // Crosshair
  chart.subscribeCrosshairMove((param) => {
    if (!param.time || param.point === undefined || !candleSeries) return;
    const cd = param.seriesData.get(candleSeries);
    if (cd) {
      const candle = cd as CandlestickData;
      const idx = param.logical ?? 0;
      const raw = props.data[idx] ?? props.data[0];
      emit("crosshair", {
        time: String(param.time),
        open: candle.open,
        close: candle.close,
        high: candle.high,
        low: candle.low,
        volume: raw?.vol ?? 0,
      });
    }
  });

  // Time range change → emit + dirty check
  chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
    if (range) {
      markDirty();
      updateCache(range, chart!.timeScale().width());
      emit("timeRangeChange", {
        from: typeof range.from === "number" ? range.from : 0,
        to: typeof range.to === "number" ? range.to : 0,
      });
    }
  });

  return chart;
}

// ---- 更新图表数据 ----
function updateChartData() {
  if (!candleSeries) {
    initKLineChart();
  }
  if (!candleSeries || !chart) return;

  const ohlc = transformData(props.data);
  if (!ohlc.length) return;

  candleSeries.setData(ohlc);

  // MA lines — 增量更新
  maSeriesList.forEach((s) => chart!.removeSeries(s));
  maSeriesList.length = 0;
  props.maLines.forEach((period, i) => {
    const maData = calcMA(ohlc, period);
    if (maData.length) {
      const s = chart!.addSeries(LineSeries, {
        color: maColors[i % maColors.length],
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      }) as ISeriesApi<"Line", Time>;
      s.setData(maData);
      maSeriesList.push(s);
    }
  });

  // Volume
  if (volumeSeries) {
    const volData: HistogramData[] = ohlc.map((d, i) => {
      const raw = props.data[i];
      const isUp = (raw.close ?? 0) >= (raw.open ?? 0);
      const r = isUp ? 232 : 29;
      const g = isUp ? 57 : 189;
      const b = isUp ? 57 : 96;
      return {
        time: d.time,
        value: raw.vol ?? 0,
        color: `rgba(${r},${g},${b},0.4)`,
      };
    });
    volumeSeries.setData(volData);
  }

  chart.timeScale().fitContent();
}

// ---- 信号标记：StaticMarker → SignalMarkerPrimitive ----
function syncSignalMarkers(markers: SignalMarker[]) {
  if (!candleSeries) return;

  // 获取已有的 signal marker 原语 ID
  const existingIds = primitiveManager
    .getAttachedIds()
    .filter((id) => id.startsWith("signal-"));
  const wantedIds = new Set(markers.map((_, i) => `signal-${i}`));

  // 移除不再需要的
  for (const id of existingIds) {
    if (!wantedIds.has(id)) {
      primitiveManager.detach(id);
    }
  }

  // 创建/更新标记原语
  markers.forEach((m, i) => {
    const id = `signal-${i}`;
    const signalData: SignalMarkerData = {
      id,
      type: "signalMarker",
      time: toTime(m.time),
      price: 0, // 将在 updateChartData 后根据 K 线数据计算
      direction: m.shape === "arrowUp" ? "buy" : "sell",
      shape: m.shape,
      color: m.color,
      text: m.text,
      strategyName: m.strategyName,
    };

    // 从原始数据中查找对应 bar 的价格
    const bar = props.data.find(
      (d) => toTime(d.trade_date) === toTime(m.time),
    );
    if (bar) {
      signalData.price =
        m.position === "aboveBar"
          ? (bar.high ?? bar.close ?? 0)
          : (bar.low ?? bar.close ?? 0);
    }

    // 已存在则更新，否则创建
    const existingIds = primitiveManager.getAttachedIds();
    if (existingIds.includes(id)) {
      // 需要获取已附加的原语实例来更新——这里简化为 detach + 重建
      primitiveManager.detach(id);
    }
    const primitive = new SignalMarkerPrimitive(signalData);
    primitiveManager.attach(id, primitive);
  });
}

// ---- 同步绘制原语 ----
function syncDrawings(drawings: ISeriesPrimitive<Time>[]) {
  if (!candleSeries) return;
  // 清除旧的 drawing 原语
  const existingDrawIds = primitiveManager
    .getAttachedIds()
    .filter((id) => id.startsWith("draw-"));
  for (const id of existingDrawIds) {
    primitiveManager.detach(id);
  }
  // 附加新的
  drawings.forEach((primitive, i) => {
    primitiveManager.attach(`draw-${i}`, primitive);
  });
}

// ---- watchers ----
watch(
  () => props.data,
  async () => {
    if (!props.data.length) return;
    await nextTick();
    if (!chartContainer.value) return;
    if (!chart) initKLineChart();
    if (chart) {
      updateChartData();
      // 数据更新后重新同步信号标记（因为价格可能变化）
      if (props.signalMarkers.length > 0) {
        syncSignalMarkers(props.signalMarkers);
      }
    }
  },
  { deep: true },
);

watch(
  () => props.signalMarkers,
  (markers) => {
    if (!candleSeries || !chart) return;
    syncSignalMarkers(markers);
  },
  { deep: true },
);

watch(
  () => props.drawings,
  (drawings) => {
    if (!candleSeries || !chart) return;
    syncDrawings(drawings ?? []);
  },
  { deep: true },
);

// ---- lifecycle ----
onMounted(() => {
  if (props.data.length) {
    const inst = createChartInstance();
    if (inst) {
      updateChartData();
      if (props.signalMarkers.length > 0) {
        syncSignalMarkers(props.signalMarkers);
      }
      if (props.drawings && props.drawings.length > 0) {
        syncDrawings(props.drawings);
      }
    }
  }
  bindGlobalEvents();
});

onBeforeUnmount(() => {
  unbindGlobalEvents();
  primitiveManager.dispose();
  maSeriesList.length = 0;
  candleSeries = null;
  volumeSeries = null;
  if (chart) {
    chart.remove();
    chart = null;
  }
});

defineExpose({
  fitContent() {
    chart?.timeScale().fitContent();
  },
  setVisibleRange(from: number, to: number) {
    chart?.timeScale().setVisibleRange({ from, to } as any);
  },
  resize() {
    lifecycleResize();
  },
  getChart() {
    return chart;
  },
});
</script>

<template>
  <div class="lw-kline-container">
    <n-skeleton v-if="loading" height="420px" width="100%" />
    <n-result v-else-if="error" status="500" title="K线数据加载失败">
      <template #footer>
        <n-button type="primary" @click="emit('retry')">重试</n-button>
      </template>
    </n-result>
    <n-empty
      v-else-if="!hasData"
      description="暂无K线数据"
      style="padding: 80px"
    />
    <div
      ref="chartContainer"
      class="lw-chart"
      :style="{ display: hasData && !loading && !error ? '' : 'none' }"
    />
  </div>
</template>

<style lang="scss" scoped>
.lw-kline-container {
  width: 100%;
  position: relative;
}
.lw-chart {
  width: 100%;
  min-height: v-bind("props.height + 'px'");
}
</style>
