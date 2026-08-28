<!-- EquityCurveChart.vue — lightweight-charts 净值曲线（重构版）
     使用 useChartLifecycle / usePrimitiveManager / useTimeCoordinate 组合 -->
<script setup lang="ts">
import { watch, onMounted, onBeforeUnmount, nextTick, computed, ref } from "vue";
import { NSkeleton, NEmpty, NResult, NButton, NButtonGroup } from "naive-ui";
import {
  ColorType,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesPrimitive,
  type LineData,
  type Time,
} from "lightweight-charts";
import { useChartLifecycle, isDarkMode } from "@/composables/useChartLifecycle";
import { useTimeCoordinate } from "@/composables/useTimeCoordinate";
import { usePrimitiveManager } from "@/composables/usePrimitiveManager";

export interface EquityPoint {
  date: string;
  value: number;
}
export interface BenchmarkPoint {
  date: string;
  value: number;
}
export interface DrawdownPoint {
  date: string;
  value: number;
}

const props = withDefaults(
  defineProps<{
    data: EquityPoint[];
    benchmark?: BenchmarkPoint[];
    drawdown?: DrawdownPoint[];
    height?: number;
    loading?: boolean;
    error?: boolean;
    title?: string;
    subtitle?: string;
    primitives?: ISeriesPrimitive<Time>[];
    logScale?: boolean;
    showExcess?: boolean;
  }>(),
  {
    data: () => [],
    benchmark: () => [],
    drawdown: () => [],
    height: 420,
    loading: false,
    error: false,
    title: "",
    subtitle: "",
    primitives: () => [],
    logScale: false,
    showExcess: false,
  },
);

const emit = defineEmits<{ retry: [] }>();
const logScale = ref(props.logScale);
const hasData = computed(() => props.data.length > 0);

// ---- composables ----
const {
  chartContainer,
  createChartInstance,
  destroyChart,
  handleResize,
  handleThemeChange,
  bindGlobalEvents,
  unbindGlobalEvents,
  getChart,
} = useChartLifecycle({ height: props.height });

const { markDirty, updateCache } = useTimeCoordinate();
const primitiveManager = usePrimitiveManager();

let chart: IChartApi | null = null;
let equitySeries: ISeriesApi<"Line", Time> | null = null;
let benchSeries: ISeriesApi<"Line", Time> | null = null;
let excessSeries: ISeriesApi<"Line", Time> | null = null;
let ddSeries: ISeriesApi<"Line", Time> | null = null;
// ⚠️ 存储当前渲染的 equityData，供 crosshair handler 动态读取（避免闭包捕获过期数组）
let _currentEquityData: LineData[] = [];
let _currentBenchData: LineData[] = [];
let _currentDDData: LineData[] = [];
// 十字光标浮层标签（含净值/基准/超额/回撤）
const eqTooltipData = ref<{ x: number; y: number; date: string; value: number; benchValue?: number; ddValue?: number; excessValue?: number; visible: boolean } | null>(null);

// ---- 数据转换 ----
// ⚠️ 返回 epoch 秒，强制 lightweight-charts 使用线性时间轴
// 避免 BusinessDay 的非线性交易日映射导致十字星漂移
function toTimeEpoch(dateStr: string): Time {
  const s = (dateStr?.slice(0, 10) || dateStr);
  return (Math.floor(new Date(s + "T00:00:00Z").getTime() / 1000)) as Time;
}
function toLineData(data: Array<{ date: string; value: number }>): LineData[] {
  return data.map((d) => ({
    time: toTimeEpoch(d.date),
    value: d.value,
  }));
}

// ---- 渲染 ----
function renderChart() {
  const el = chartContainer.value;
  if (!el) return;
  const w = el.clientWidth;
  if (!w || w <= 0 || !props.data.length) return;

  const isNew = !chart;
  if (isNew) {
    // 时间轴更密集刻度 + 格式化日期（提升信息密度）
    chart = createChartInstance({
      timeScale: {
        timeVisible: false,
        minBarSpacing: 10, // 2026-08: 放大上限统一为 10px（与 useChartLifecycle 默认一致）
        rightOffset: 4,
        tickMarkFormatter: (time: Time) => {
          const d = new Date((time as number) * 1000);
          const m = d.getUTCMonth() + 1;
          const y = d.getUTCFullYear();
          return `${m}月` + (m === 1 ? `\n${y}` : "");
        },
      },
    });
    if (!chart) return;
  }

  const dark = isDarkMode();

  // 增量更新：首次创建系列，后续 setData
  if (isNew) {
    equitySeries = chart!.addSeries(LineSeries, {
      color: "#7C3AED",
      lineWidth: 2 as const,
      priceLineVisible: false,
      lastValueVisible: true,
      priceFormat: { type: "price", precision: 0, minMove: 1 },
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
    }) as ISeriesApi<"Line", Time>;
  }

  const equityData = toLineData(props.data);
  _currentEquityData = equityData;  // ⚠️ 更新模块级引用，供 crosshair handler 读取最新数据
  equitySeries!.setData(equityData);


  // 基准曲线（与策略共用同一 Y 轴，JoinQuant 风格）
  const benchData = toLineData(props.benchmark || []);
  _currentBenchData = benchData;
  if (benchData.length > 0) {
    if (!benchSeries && chart) {
      benchSeries = chart.addSeries(LineSeries, {
        color: "rgba(24,160,88,0.7)",
        lineWidth: 2 as const,
        lineStyle: 2, // dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        // 共用策略 Y 轴，不再用独立 priceScaleId
      }) as ISeriesApi<"Line", Time>;
    }
    benchSeries?.setData(benchData);
  } else if (benchSeries) {
    chart?.removeSeries(benchSeries);
    benchSeries = null;
  }

  // 超额收益（策略-基准，半透明面积图）
  // v1.4: 日期对齐 — 用 Map 查找替代 index 对齐，处理交易日历不一致
  if (props.showExcess && benchData.length > 0) {
    const benchByTime = new Map<number, number>(
      benchData.map((b) => [b.time as number, b.value]),
    );
    const excessData = equityData.map((eq) => ({
      time: eq.time,
      value: (eq.value - (benchByTime.get(eq.time as number) ?? eq.value)),
    }));
    if (!excessSeries && chart) {
      excessSeries = chart.addSeries(LineSeries, {
        color: "rgba(255,152,0,0.3)",
        lineWidth: 1 as const,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      }) as ISeriesApi<"Line", Time>;
    }
    excessSeries?.setData(excessData);
  } else if (excessSeries) {
    chart?.removeSeries(excessSeries);
    excessSeries = null;
  }

  // 回撤曲线（独立 priceScale 置于底部，与净值共用时间轴）
  const ddData = toLineData(props.drawdown || []);
  _currentDDData = ddData;
  if (ddData.length > 0) {
    if (!ddSeries && chart) {
      ddSeries = chart.addSeries(LineSeries, {
        priceScaleId: 'drawdown',
        color: "rgba(239,68,68,0.85)",
        lineWidth: 1 as const,
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: { type: "custom", formatter: (v: number) => `${(v * 100).toFixed(1)}%` },
        crosshairMarkerVisible: false,
      }) as ISeriesApi<"Line", Time>;
      chart.priceScale('drawdown').applyOptions({
        scaleMargins: { top: 0.85, bottom: 0 },
      });
    }
    ddSeries?.setData(ddData);
  } else if (ddSeries) {
    chart?.removeSeries(ddSeries);
    ddSeries = null;
  }

  // 绑定 primitive manager + 十字光标浮层标签（首次创建时）
  if (isNew && equitySeries) {
    primitiveManager.bind(equitySeries, () => {
      // requestUpdate 回调：强制图表重绘（原语增删/切换开关后生效，不改可视范围）
      if (chart) {
        const r = chart.timeScale().getVisibleLogicalRange();
        if (r) chart.timeScale().setVisibleLogicalRange(r);
      }
    });
    if (props.primitives && props.primitives.length > 0) {
      const items = props.primitives.map((p) => {
        const dataId = (p as any).getData?.()?.id || (p as any)._data?.id;
        return { id: dataId || `eq-p-${Math.random().toString(36).slice(2, 8)}`, primitive: p };
      });
      primitiveManager.syncPrimitives(items);
    }
    // 十字光标浮层标签
    let _eqTooltipTimer: ReturnType<typeof setTimeout> | null = null;
    chart!.subscribeCrosshairMove((param) => {
      if (!param.time || param.point === undefined) {
        eqTooltipData.value = null;
        return;
      }
      // 用时间戳在 _currentEquityData 中匹配数据点
      const crosshairTimeVal = typeof param.time === 'number' ? param.time : 0;
      const point = crosshairTimeVal ? _currentEquityData.find(d => (d.time as number) === crosshairTimeVal) : undefined;
      if (point) {
        if (_eqTooltipTimer) clearTimeout(_eqTooltipTimer);
        const dateStr = new Date(crosshairTimeVal * 1000).toISOString().slice(0, 10);
        const benchPoint = _currentBenchData.find(d => (d.time as number) === crosshairTimeVal);
        const ddPoint = _currentDDData.find(d => (d.time as number) === crosshairTimeVal);
        eqTooltipData.value = {
          x: param.point.x, y: param.point.y, date: dateStr, value: point.value, visible: true,
          benchValue: benchPoint?.value,
          ddValue: ddPoint?.value,
          excessValue: benchPoint ? (point.value - benchPoint.value) : undefined,
        };
        _eqTooltipTimer = setTimeout(() => { eqTooltipData.value = null; }, 3000);
      }
    });
  }

  // ⚠️ 用 setVisibleRange 替代 fitContent，保持时间等比模式
  const lastIdx = equityData.length - 1;
  if (lastIdx >= 0) {
    chart!.timeScale().setVisibleRange({ from: equityData[0].time, to: equityData[lastIdx].time });
  }
}

// ---- 视口变化订阅（幂等：重复调用不堆积 handler） ----
let _viewportHandler: ((range: any) => void) | null = null;

function setupViewportListener() {
  const c = getChart();
  if (!c) return;
  // 先取消旧订阅，防止 handler 堆积
  if (_viewportHandler) {
    c.timeScale().unsubscribeVisibleTimeRangeChange(_viewportHandler);
  }
  _viewportHandler = (range: any) => {
    if (range) {
      // 限制缩小：可视范围超过完整数据跨度时，复位到完整数据（不能无限缩小）
      const data = _currentEquityData;
      if (data.length >= 2) {
        const firstT = data[0].time as number;
        const lastT = data[data.length - 1].time as number;
        const fromT = typeof range.from === "number" ? range.from : 0;
        const toT = typeof range.to === "number" ? range.to : 0;
        const dataSpan = lastT - firstT;
        const visSpan = toT - fromT;
        if (dataSpan > 0 && visSpan > dataSpan * 1.05) {
          c.timeScale().setVisibleRange({ from: firstT as any, to: lastT as any });
          return; // 复位后跳过本次 cache 更新（避免竞态）
        }
      }
      markDirty();
      updateCache(range, c.timeScale().width());
    }
  };
  c.timeScale().subscribeVisibleTimeRangeChange(_viewportHandler);
}

// ---- 原语同步 ----
watch(
  () => props.primitives,
  (prims) => {
    if (!prims || prims.length === 0) {
      primitiveManager.detachAll();
      return;
    }
    // 使用原语内部数据的 id 作为管理器 key，避免数组位置漂移
    const items = prims.map((p) => {
      const dataId = (p as any).getData?.()?.id || (p as any)._data?.id;
      return { id: dataId || `eq-p-${Math.random().toString(36).slice(2, 8)}`, primitive: p };
    });
    primitiveManager.syncPrimitives(items);
  },
  { deep: true, immediate: true },
);

// ---- 数据变更 ----
watch(
  () => props.data,
  async (val) => {
    if (!val?.length) {
      // ⚠️ 必须在 destroyChart 前分离所有原语，避免 _attached 残留旧引用导致坐标漂移
      primitiveManager.detachAll();
      destroyChart();
      chart = null;
      equitySeries = null;
      benchSeries = null;
      excessSeries = null;
      ddSeries = null;
      return;
    }
    await nextTick();
    renderChart();
    setupViewportListener();
  },
  { deep: true, immediate: true },
);

// ---- 生命周期 ----
// 注: renderChart() 由 watch(data) 在首次有数据时自动触发，onMounted 不再重复调用
onMounted(() => {
  bindGlobalEvents();
});

// ---- 对数轴切换 ----
watch(logScale, (enabled) => {
  if (chart) {
    chart.priceScale("right").applyOptions({
      mode: enabled ? 1 : 0, // 0=线性 1=对数
    });
  }
});

onBeforeUnmount(() => {
  primitiveManager.dispose();
  if (_viewportHandler && chart) {
    chart.timeScale().unsubscribeVisibleTimeRangeChange(_viewportHandler);
  }
  _viewportHandler = null;
  destroyChart();
  chart = null;
  equitySeries = null;
  benchSeries = null;
  excessSeries = null;
  ddSeries = null;
  unbindGlobalEvents();
});

defineExpose({
  fitContent() {
    const data = equitySeries?.data();
    if (data && data.length > 0) {
      const last = data[data.length - 1];
      chart?.timeScale().setVisibleRange({ from: data[0].time, to: last.time });
    }
  },
  resize() {
    handleResize();
  },
  getChart,
  getContainer: () => chartContainer.value,
  getSeries: () => equitySeries,
});
</script>

<template>
  <div class="equity-chart-container">
    <div v-if="title" class="chart-header">
      <h5 class="chart-title">{{ title }}</h5>
      <span v-if="subtitle" class="chart-subtitle">{{ subtitle }}</span>
      <n-button-group size="tiny" style="margin-left: auto;">
        <n-button :type="!logScale ? 'primary' : 'default'" @click="logScale = false">线性</n-button>
        <n-button :type="logScale ? 'primary' : 'default'" @click="logScale = true">对数</n-button>
      </n-button-group>
    </div>
    <n-skeleton v-if="loading" :height="height + 'px'" width="100%" />
    <n-result v-else-if="error" status="500" title="净值曲线加载失败">
      <template #footer>
        <n-button type="primary" size="small" @click="emit('retry')">
          重试
        </n-button>
      </template>
    </n-result>
    <n-empty
      v-else-if="!hasData"
      description="暂无净值数据"
      style="padding: 40px"
    />
    <div
      ref="chartContainer"
      class="equity-chart"
      :style="{
        height: hasData && !loading && !error ? height + 'px' : '',
      }"
    />
    <!-- 图例（多线说明：净值/基准/超额/回撤） -->
    <div class="chart-legend">
      <span class="legend-item"><i class="legend-dot" style="background:#7C3AED"></i>净值</span>
      <span v-if="benchmark && benchmark.length" class="legend-item"><i class="legend-dot" style="background:rgba(24,160,88,0.7)"></i>基准</span>
      <span v-if="showExcess && benchmark && benchmark.length" class="legend-item"><i class="legend-dot" style="background:rgba(255,152,0,0.5)"></i>超额</span>
      <span v-if="drawdown && drawdown.length" class="legend-item"><i class="legend-dot" style="background:rgba(239,68,68,0.85)"></i>回撤（右轴）</span>
    </div>
    <!-- 十字光标浮层 -->
    <div
      v-if="eqTooltipData?.visible"
      class="crosshair-tooltip"
      :style="{ left: eqTooltipData.x + 'px', top: (eqTooltipData.y - 10) + 'px' }"
    >
      <div class="tooltip-date">{{ eqTooltipData.date }}</div>
      <div class="tooltip-row"><span>净值</span><span>{{ eqTooltipData.value.toFixed(2) }}</span></div>
      <div v-if="eqTooltipData.benchValue != null" class="tooltip-row"><span>基准</span><span>{{ eqTooltipData.benchValue.toFixed(2) }}</span></div>
      <div v-if="eqTooltipData.excessValue != null" class="tooltip-row"><span>超额</span><span>{{ eqTooltipData.excessValue.toFixed(2) }}</span></div>
      <div v-if="eqTooltipData.ddValue != null" class="tooltip-row"><span>回撤</span><span>{{ (eqTooltipData.ddValue * 100).toFixed(1) }}%</span></div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.equity-chart-container {
  width: 100%;
  position: relative;
}
.chart-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.chart-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.chart-subtitle {
  font-size: 11px;
  color: var(--color-text-tertiary);
}
.equity-chart {
  width: 100%;
  zoom: 1.25; /* 抵消 html { zoom: 0.8 } */
}
.chart-legend {
  display: flex;
  gap: 14px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--color-text-tertiary, #8898b8);
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
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
