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

// 十字光标浮层标签
const tooltipData = ref<{ x: number; y: number; date: string; open: number; high: number; low: number; close: number; vol: number; visible: boolean } | null>(null);

// ---- helpers ----
// ⚠️ 返回 epoch 秒（Unix 时间戳），而非字符串 BusinessDay
// lightweight-charts 对 BusinessDay 使用非线性交易日映射，导致十字星与鼠标错位
// UTCTimestamp (number) 使用严格线性时间轴，消除偏差
function toTime(d: string): Time {
  const dateStr = (d?.slice(0, 10) || d);
  return (Math.floor(new Date(dateStr + "T00:00:00Z").getTime() / 1000)) as Time;
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
    () => { /* 原语触发重绘: lightweight-charts 自动处理，不调用 fitContent 避免切换到等距模式 */ },
  );

  // Crosshair (含浮层标签)
  let _tooltipTimer: ReturnType<typeof setTimeout> | null = null;

  chart.subscribeCrosshairMove((param) => {
    if (!param.time || param.point === undefined || !candleSeries) {
      tooltipData.value = null;
      return;
    }
    const cd = param.seriesData.get(candleSeries);
    if (cd) {
      const candle = cd as CandlestickData;
      // 通过时间匹配查找原始数据行（time 现在是 epoch 秒，需转回日期字符串匹配）
      const candleDateStr = new Date((candle.time as number) * 1000).toISOString().slice(0, 10);
      const raw = props.data.find(
        (d) => (d.trade_date?.slice(0, 10) || d.trade_date) === candleDateStr,
      ) ?? props.data[0];
      // 更新浮层标签
      if (_tooltipTimer) clearTimeout(_tooltipTimer);
      tooltipData.value = {
        x: param.point.x,
        y: param.point.y,
        date: candleDateStr,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        vol: raw?.vol ?? 0,
        visible: true,
      };
      _tooltipTimer = setTimeout(() => { tooltipData.value = null; }, 3000);
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

  // ⚠️ 用 setVisibleRange 替代 fitContent，保持时间等比模式（避免切换到等距 barSpacing 导致十字星漂移）
  const lastIdx = ohlc.length - 1;
  if (lastIdx >= 0) {
    chart.timeScale().setVisibleRange({ from: ohlc[0].time, to: ohlc[lastIdx].time });
  }
}

// ---- 信号标记：StaticMarker → SignalMarkerPrimitive ----
function syncSignalMarkers(markers: SignalMarker[]) {
  if (!candleSeries) return;

  // 使用内容哈希作为 ID：time + text，避免位置漂移
  const wantedIds = new Set(
    markers.map((m) => `signal-${toTime(m.time)}-${m.text || m.shape}`),
  );

  // 移除不再需要的
  const existingIds = primitiveManager
    .getAttachedIds()
    .filter((id) => id.startsWith("signal-"));
  for (const id of existingIds) {
    if (!wantedIds.has(id)) {
      primitiveManager.detach(id);
    }
  }

  // 创建/更新标记原语
  markers.forEach((m) => {
    const id = `signal-${toTime(m.time)}-${m.text || m.shape}`;
    const signalData: SignalMarkerData = {
      id,
      type: "signalMarker",
      time: toTime(m.time),
      price: 0,
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
    if (primitiveManager.getAttachedIds().includes(id)) {
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
  // 附加新的，使用原语内部数据 ID 避免位置漂移
  drawings.forEach((primitive) => {
    const dataId =
      (primitive as any).getData?.()?.id || (primitive as any)._data?.id;
    const id = dataId || `draw-${Math.random().toString(36).slice(2, 8)}`;
    primitiveManager.attach(id, primitive);
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
  { deep: true, immediate: true },
);

watch(
  () => props.signalMarkers,
  (markers) => {
    if (!candleSeries || !chart) return;
    syncSignalMarkers(markers);
  },
  { deep: true, immediate: true },
);

watch(
  () => props.drawings,
  (drawings) => {
    if (!candleSeries || !chart) return;
    syncDrawings(drawings ?? []);
  },
  { deep: true, immediate: true },
);

// ---- lifecycle ----
onMounted(() => {
  bindGlobalEvents();
  if (props.data.length) {
    // updateChartData() 内部会通过 initKLineChart() 首次创建 chart
    // 不再额外调用 createChartInstance()，避免 chart 被创建两次
    updateChartData();
    if (props.signalMarkers.length > 0) {
      syncSignalMarkers(props.signalMarkers);
    }
    if (props.drawings && props.drawings.length > 0) {
      syncDrawings(props.drawings);
    }
  }
});

onBeforeUnmount(() => {
  unbindGlobalEvents();
  primitiveManager.dispose();
  maSeriesList.length = 0;
  candleSeries = null;
  volumeSeries = null;
  // 通过 composable 统一销毁（清理其内部引用 + DOM 事件）
  destroyChart();
  chart = null;
});

defineExpose({
  fitContent() {
    // 使用时间等比模式，避免等距间距导致十字星漂移
    const data = chart?.series()[0]?.data();
    if (data && data.length > 0) {
      const last = data[data.length - 1];
      chart?.timeScale().setVisibleRange({ from: data[0].time, to: last.time });
    }
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
    <!-- 十字光标浮层标签 -->
    <div
      v-if="tooltipData?.visible"
      class="crosshair-tooltip"
      :style="{ left: tooltipData.x + 'px', top: (tooltipData.y - 10) + 'px' }"
    >
      <div class="tooltip-date">{{ tooltipData.date }}</div>
      <div class="tooltip-row"><span>开</span><span>{{ tooltipData.open.toFixed(2) }}</span></div>
      <div class="tooltip-row"><span>高</span><span class="text-up">{{ tooltipData.high.toFixed(2) }}</span></div>
      <div class="tooltip-row"><span>低</span><span class="text-down">{{ tooltipData.low.toFixed(2) }}</span></div>
      <div class="tooltip-row"><span>收</span><span :class="tooltipData.close >= tooltipData.open ? 'text-up' : 'text-down'">{{ tooltipData.close.toFixed(2) }}</span></div>
      <div class="tooltip-row"><span>量</span><span>{{ (tooltipData.vol / 1e8).toFixed(2) }}亿</span></div>
    </div>
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
  zoom: 1.25; /* 抵消 html { zoom: 0.8 }，恢复 chart 内部坐标系统与 OS 鼠标一致 */
}

/* 十字光标浮层标签 */
.crosshair-tooltip {
  position: absolute;
  transform: translate(-50%, -100%);
  pointer-events: none;
  z-index: 100;
  background: var(--color-bg-card, rgba(18, 24, 40, 0.95));
  border: 1px solid var(--color-primary, #448aff);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 11px;
  line-height: 1.6;
  white-space: nowrap;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
  min-width: 130px;
}
.tooltip-date {
  font-weight: 600;
  color: var(--color-primary, #448aff);
  margin-bottom: 3px;
  text-align: center;
  font-size: 12px;
}
.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.tooltip-row span:first-child {
  color: var(--color-text-tertiary, #888);
}
.tooltip-row span:last-child {
  font-variant-numeric: tabular-nums;
}
</style>
