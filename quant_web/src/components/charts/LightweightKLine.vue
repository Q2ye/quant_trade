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
import { MA_COLORS, MA_FALLBACK_COLORS } from "./chart-palette";

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

// ⚠️ 抵消全局 `html { zoom: 0.8 }`（见 styles/global.scss）。
//    容器按 1.25 渲染后，**图表内部坐标 → 父级 CSS px 需再乘 1.25** ——
//    浮层标签（DOM 兄弟节点，未随容器缩放）必须用 KLINE_ZOOM 换算，否则漂移。
const KLINE_ZOOM = 1.25;
const klineZoom = String(KLINE_ZOOM);

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
const maSeriesIdx: number[] = []; // 与 maSeriesList 平行：每个 series 对应 props.maLines 的下标

// 均线配色 —— 集中定义在 chart-palette.ts（canvas 无法解析 CSS 变量），按周期取色
function maColor(period: number, index: number): string {
  return MA_COLORS[period] ?? MA_FALLBACK_COLORS[index % MA_FALLBACK_COLORS.length];
}

// 十字光标浮层标签
const tooltipData = ref<{ x: number; y: number; date: string; open: number; high: number; low: number; close: number; vol: number; visible: boolean } | null>(null);

// 均线图例（同花顺式：MA5: 值 · MA10: 值 · MA20: 值，按线色）
const maLegend = ref<{ period: number; value: number | null; color: string }[]>([]);
let _maLastValues: (number | null)[] = [];

function setMaLegendFromValues(values: (number | null)[]) {
  maLegend.value = props.maLines.map((period, i) => ({
    period,
    value: values[i] ?? null,
    color: maColor(period, i),
  }));
}

/** 刷新均线图例：传 param（十字光标）取该时点值；传 null 取最新值 */
function refreshMaLegend(param: { seriesData: Map<unknown, unknown> } | null) {
  if (!param) {
    setMaLegendFromValues(_maLastValues);
    return;
  }
  const values: (number | null)[] = props.maLines.map(() => null);
  maSeriesList.forEach((s, k) => {
    const d = param.seriesData.get(s) as LineData | undefined;
    if (d && typeof d.value === "number") values[maSeriesIdx[k]] = d.value;
  });
  setMaLegendFromValues(values);
}

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

  // 移除左下角 logo
  el.querySelector('a')?.remove();

  // 动态价格轴：根据数据范围自适应刻度密度
  chart.applyOptions({
    rightPriceScale: {
      autoScale: true,
      scaleMargins: { top: 0.05, bottom: 0.05 },
    },
  });

  // Candlestick
  // 根据价格量级自适应精度：>50元 → 3位小数（货币ETF），否则2位
  const samplePrice = props.data[0]?.close ?? 10;
  const pricePrecision = samplePrice > 50 ? 3 : 2;

  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: "#e83939",
    downColor: "#1dbd60",
    borderUpColor: "#e83939",
    borderDownColor: "#1dbd60",
    wickUpColor: "#e83939",
    wickDownColor: "#1dbd60",
    priceFormat: {
      type: "price",
      precision: pricePrecision,
      minMove: pricePrecision === 3 ? 0.001 : 0.01,
    },
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
      refreshMaLegend(null); // 光标离开 → 图例回到最新值
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
      // ⚠️ 缩放换算：`param.point` 是**图表内部坐标**，而浮层是 `.lw-chart`（zoom:1.25）
      //    的**兄弟节点**（未缩放）→ 必须乘 KLINE_ZOOM 才与鼠标位置重合。
      if (_tooltipTimer) clearTimeout(_tooltipTimer);
      tooltipData.value = {
        x: param.point.x * KLINE_ZOOM,
        y: param.point.y * KLINE_ZOOM,
        date: candleDateStr,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        vol: raw?.vol ?? 0,
        visible: true,
      };
      _tooltipTimer = setTimeout(() => { tooltipData.value = null; }, 3000);
      refreshMaLegend(param);
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

  // Time range change → 缩小下限守卫 + emit + dirty check
  chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
    if (!range) return;
    const from = typeof range.from === "number" ? range.from : 0;
    const to = typeof range.to === "number" ? range.to : 0;
    // ⚠️ 缩小下限守卫（2026-10-11）：useChartLifecycle 的 `maxBarSpacing` 只限**放大**，
    //    **不限缩小** ⇒ 此前滚轮/触控板可把 K 线无限缩小成一条线。
    //    判据与复位方式复用 EquityCurveChart.setupViewportListener（`:276-301`）。
    const dataSpan = _dataLastTime - _dataFirstTime;
    if (dataSpan > 0 && to - from > dataSpan * 1.05) {
      chart!.timeScale().setVisibleRange({
        from: _dataFirstTime as unknown as Time,
        to: _dataLastTime as unknown as Time,
      });
      return; // 复位后跳过本次 emit/cache 更新（避免竞态）
    }
    markDirty();
    updateCache(range, chart!.timeScale().width());
    emit("timeRangeChange", { from, to });
  });

  return chart;
}

// ---- 跟踪数据范围，用于判断是否为追加数据 ----
let _prevDataEnd: number | null = null; // 上一次数据的最新时间戳
let _prevDataStart: number | null = null; // 上一次数据的最早时间戳

// ---- 全量数据跨度（epoch 秒）：缩小下限守卫用 ----
let _dataFirstTime = 0;
let _dataLastTime = 0;

// ---- 更新图表数据 ----
function updateChartData() {
  if (!candleSeries) {
    initKLineChart();
  }
  if (!candleSeries || !chart) return;

  const ohlc = transformData(props.data);
  if (!ohlc.length) return;
  _dataFirstTime = ohlc[0].time as number;
  _dataLastTime = ohlc[ohlc.length - 1].time as number;

  // 根据当前数据范围动态调整价格精度（切换ETF时生效）
  const samplePrice = ohlc[0]?.close ?? 10;
  const pricePrecision = samplePrice > 50 ? 3 : 2;
  candleSeries.applyOptions({
    priceFormat: {
      type: "price",
      precision: pricePrecision,
      minMove: pricePrecision === 3 ? 0.001 : 0.01,
    },
  });

  // 保存当前可视范围（用于追加数据时恢复视图位置）
  const savedRange = chart.timeScale().getVisibleLogicalRange();

  candleSeries.setData(ohlc);

  // MA lines — 增量更新
  maSeriesList.forEach((s) => chart!.removeSeries(s));
  maSeriesList.length = 0;
  maSeriesIdx.length = 0;
  const maLast: (number | null)[] = [];
  props.maLines.forEach((period, i) => {
    const maData = calcMA(ohlc, period);
    maLast.push(
      maData.length ? Number(maData[maData.length - 1].value) : null,
    );
    if (maData.length) {
      const s = chart!.addSeries(LineSeries, {
        color: maColor(period, i),
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      }) as ISeriesApi<"Line", Time>;
      s.setData(maData);
      maSeriesList.push(s);
      maSeriesIdx.push(i); // series → props.maLines 下标（MA 无数据时二者会错位，故显式记录）
    }
  });
  _maLastValues = maLast;
  refreshMaLegend(null);

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

  // 可视范围策略：
  // - 无保存范围（首次加载/切换周期）→ 适配全部数据
  // - 数据向前扩展（追加更早历史）→ 恢复到之前保存的可视位置
  // - 数据增加但起始不变（实时追加）→ 保持当前可视位置
  const newStart = ohlc[0].time as number;
  const newEnd = ohlc[ohlc.length - 1].time as number;
  const isAppendBackward = _prevDataStart != null && newStart < _prevDataStart;

  if (savedRange && isAppendBackward) {
    // 追加更早数据：恢复之前保存的可视范围
    chart.timeScale().setVisibleLogicalRange(savedRange);
  } else if (!savedRange || _prevDataStart == null) {
    // 首次加载或切换周期：适配全部数据
    chart.timeScale().setVisibleRange({ from: ohlc[0].time, to: ohlc[ohlc.length - 1].time });
  }
  // 否则保持当前可视范围不变（实时数据追加等场景）

  _prevDataStart = newStart;
  _prevDataEnd = newEnd;
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
    const data = (chart as any)?.series()[0]?.data();
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
  /**
   * 绘图目标（包 B 图上作业层）：供 useChartDrawings 武装绘图状态机。
   * 返回 { chart, series, container }；三者任一缺失（未初始化/已销毁）→ null。
   * ⚠️ 调用方在周期切换（本组件带 :key 会重建）后必须重新获取。
   */
  getDrawTarget() {
    const container = chartContainer.value;
    if (!chart || !candleSeries || !container) return null;
    return { chart, series: candleSeries, container };
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
    <!-- 均线图例（同花顺式；随十字光标联动，光标离开回到最新值） -->
    <div v-if="hasData && maLegend.length" class="ma-legend">
      <span
        v-for="m in maLegend"
        :key="m.period"
        class="ma-legend-item"
        :style="{ color: m.color }"
      >
        MA{{ m.period }}: {{ m.value != null ? m.value.toFixed(2) : "--" }}
      </span>
    </div>
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
  zoom: v-bind("klineZoom"); /* 抵消 html { zoom: 0.8 }，恢复 chart 内部坐标系统与 OS 鼠标一致 */
}

/* 均线图例 —— 与同花顺一致：左上角、按线色标注周期与当前值 */
.ma-legend {
  position: absolute;
  left: 8px;
  top: 6px;
  z-index: 50;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  pointer-events: none;
  font-size: 11px;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}
.ma-legend-item {
  white-space: nowrap;
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
