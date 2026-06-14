<!-- LightweightKLine.vue — lightweight-charts K线封装，替代 ECharts K线 -->
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
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type LineData,
  type Time,
} from "lightweight-charts";

// ---- public types ----
export interface SignalMarker {
  time: string; // 'YYYY-MM-DD'
  position: "aboveBar" | "belowBar";
  color: string; // buy: '#ef5350', sell: '#26a69a'
  shape: "arrowUp" | "arrowDown";
  text: string; // 'MA金叉'
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
  }>(),
  {
    data: () => [],
    maLines: () => [5, 10, 20],
    showVolume: true,
    height: 420,
    loading: false,
    error: false,
    signalMarkers: () => [],
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

const chartContainer = ref<HTMLDivElement>();
const hasData = computed(() => props.data.length > 0);

let chart: IChartApi | null = null;
let candleSeries: ISeriesApi<"Candlestick", Time> | null = null;
let volumeSeries: ISeriesApi<"Histogram", Time> | null = null;
const maSeriesList: ISeriesApi<"Line", Time>[] = [];

// ---- MA colors ----
const maColors = ["#ff9800", "#448AFF", "#E040FB", "#00bcd4", "#ff5722"];

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

function isDarkMode(): boolean {
  const bg = getComputedStyle(document.documentElement).getPropertyValue(
    "--body-color",
  );
  if (bg) {
    const rgb = bg.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      return (Number(rgb[0]) + Number(rgb[1]) + Number(rgb[2])) / 3 < 128;
    }
  }
  return true;
}

function createChartInstance() {
  if (!chartContainer.value || chart) return;
  // 容器必须有有效尺寸，否则 lightweight-charts 无法初始化
  const w = chartContainer.value.clientWidth;
  if (!w || w <= 0) return;
  const isDark = isDarkMode();

  try {
    chart = createChart(chartContainer.value, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "#a0a0a0" : "#666666",
      },
      grid: {
        vertLines: {
          color: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
        },
        horzLines: {
          color: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
        },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
      },
      timeScale: {
        borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
        timeVisible: true,
      },
      handleScroll: { vertTouchDrag: false },
      width: w,
      height: props.height,
    });
    if (!chart || typeof chart.addSeries !== "function") {
      console.warn("[LightweightKLine] createChart 返回无效实例，跳过渲染");
      chart = null;
      return;
    }
  } catch (e) {
    console.warn("[LightweightKLine] createChart 失败:", e);
    chart = null;
    return;
  }

  // Candlestick — v5 API: addSeries(CandlestickSeries, options)
  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: "#e83939",
    downColor: "#1dbd60",
    borderUpColor: "#e83939",
    borderDownColor: "#1dbd60",
    wickUpColor: "#e83939",
    wickDownColor: "#1dbd60",
  }) as ISeriesApi<"Candlestick", Time>;

  // Volume — v5 API: addSeries(HistogramSeries, options)
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

  // Crosshair event → emit
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

  // Time range change → emit
  chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
    if (range) {
      emit("timeRangeChange", {
        from: typeof range.from === "number" ? range.from : 0,
        to: typeof range.to === "number" ? range.to : 0,
      });
    }
  });
}

function updateChartData() {
  if (!candleSeries) createChartInstance();
  if (!candleSeries || !chart) return;

  const ohlc = transformData(props.data);
  if (!ohlc.length) return;

  candleSeries.setData(ohlc);

  // MA lines — v5 API: addSeries(LineSeries, options)
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
      const isUp = raw.close! >= raw.open!;
      let r = 0;
      let g = 0;
      let b = 0;
      if (isUp) {
        r = 232;
        g = 57;
        b = 57;
      } else {
        r = 29;
        g = 189;
        b = 96;
      }
      return {
        time: d.time,
        value: raw.vol ?? 0,
        color: `rgba(${r},${g},${b},0.4)`,
      };
    });
    volumeSeries.setData(volData);
  }

  // Signal markers — v5.2 移除了 setMarkers，内置函数已不存在，跳过
  // 信号标记功能待 lightweight-charts v5 原语 API 稳定后接入

  chart.timeScale().fitContent();
}

// ---- watch data ----
watch(
  () => props.data,
  async () => {
    if (!props.data.length) return;
    // 等待 DOM 更新确保 chartContainer ref 已挂载
    await nextTick();
    if (!chartContainer.value) return;
    if (!chart) createChartInstance();
    if (chart) updateChartData();
  },
  { deep: true },
);

// ---- watch signalMarkers (v5.2 removed setMarkers; skip for now) ----
watch(
  () => props.signalMarkers,
  () => {
    // 信号标记功能待 lightweight-charts v5 原语 API 稳定后接入
  },
);

// ---- resize ----
function handleResize() {
  if (chart && chartContainer.value) {
    chart.applyOptions({
      width: chartContainer.value.clientWidth,
      height: props.height,
    });
  }
}

function handleThemeChange() {
  if (!chart) return;
  const isDark = isDarkMode();
  chart.applyOptions({
    layout: {
      background: { type: ColorType.Solid, color: "transparent" },
      textColor: isDark ? "#a0a0a0" : "#666666",
    },
    grid: {
      vertLines: {
        color: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
      },
      horzLines: {
        color: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
      },
    },
    rightPriceScale: {
      borderColor: isDark
        ? "rgba(255,255,255,0.1)"
        : "rgba(0,0,0,0.1)",
    },
    timeScale: {
      borderColor: isDark
        ? "rgba(255,255,255,0.1)"
        : "rgba(0,0,0,0.1)",
    },
  });
}

onMounted(() => {
  createChartInstance();
  if (props.data.length) updateChartData();
  window.addEventListener("resize", handleResize);
  window.addEventListener("theme-change", handleThemeChange);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  window.removeEventListener("theme-change", handleThemeChange);
  maSeriesList.length = 0;
  candleSeries = null;
  volumeSeries = null;
  if (chart) {
    chart.remove();
    chart = null;
  }
});

// ---- exposed ----
defineExpose({
  fitContent() {
    chart?.timeScale().fitContent();
  },
  setVisibleRange(from: number, to: number) {
    chart?.timeScale().setVisibleRange({ from, to } as any);
  },
  resize() {
    handleResize();
  },
});
</script>

<template>
  <div class="lw-kline-container">
    <!-- 状态覆盖层（绝对定位，不影响 chart div 的存在） -->
    <n-skeleton v-if="loading" height="420px" width="100%" />
    <n-result v-else-if="error" status="500" title="K线数据加载失败">
      <template #footer
        ><n-button type="primary" @click="emit('retry')"
          >重试</n-button
        ></template
      >
    </n-result>
    <n-empty
      v-else-if="!hasData"
      description="暂无K线数据"
      style="padding: 80px"
    />
    <!-- chart 容器始终渲染，使用 v-show 而非 v-if/v-else，确保 ref 可用 -->
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
