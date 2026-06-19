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

const props = withDefaults(
  defineProps<{
    data: EquityPoint[];
    benchmark?: BenchmarkPoint[];
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
// ⚠️ 存储当前渲染的 equityData，供 crosshair handler 动态读取（避免闭包捕获过期数组）
let _currentEquityData: LineData[] = [];
// 十字光标浮层标签
const eqTooltipData = ref<{ x: number; y: number; date: string; value: number; visible: boolean } | null>(null);

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
    chart = createChartInstance();
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
  if (props.showExcess && benchData.length > 0) {
    const excessData = equityData.map((eq, i) => ({
      time: eq.time,
      value: (eq.value - (benchData[i]?.value ?? eq.value)),
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

  // 绑定 primitive manager + 十字光标浮层标签（首次创建时）
  if (isNew && equitySeries) {
    primitiveManager.bind(equitySeries, () => {
      // requestUpdate 回调：驱使图表重绘而不改变可视范围
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
        eqTooltipData.value = { x: param.point.x, y: param.point.y, date: dateStr, value: point.value, visible: true };
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
    <!-- 十字光标浮层 -->
    <div
      v-if="eqTooltipData?.visible"
      class="crosshair-tooltip"
      :style="{ left: eqTooltipData.x + 'px', top: (eqTooltipData.y - 10) + 'px' }"
    >
      <div class="tooltip-date">{{ eqTooltipData.date }}</div>
      <div class="tooltip-row"><span>净值</span><span>{{ eqTooltipData.value.toFixed(2) }}</span></div>
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
