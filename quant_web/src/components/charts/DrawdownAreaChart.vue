<!-- DrawdownAreaChart.vue — lightweight-charts 回撤曲线（重构版） -->
<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick, computed } from "vue";
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
import { useTimeCoordinate } from "@/composables/useTimeCoordinate";
import { usePrimitiveManager } from "@/composables/usePrimitiveManager";

export interface DrawdownPoint {
  date: string;
  value: number;
}

const props = withDefaults(
  defineProps<{
    data: DrawdownPoint[];
    height?: number;
    loading?: boolean;
    error?: boolean;
    title?: string;
    primitives?: ISeriesPrimitive<Time>[];
  }>(),
  {
    data: () => [],
    height: 280,
    loading: false,
    error: false,
    title: "",
    primitives: () => [],
  },
);

const emit = defineEmits<{ retry: [] }>();
const hasData = computed(() => props.data.length > 0);

const {
  chartContainer,
  createChartInstance,
  destroyChart,
  handleResize,
  bindGlobalEvents,
  unbindGlobalEvents,
  getChart,
} = useChartLifecycle({ height: props.height, timeScale: { timeVisible: false } });

const { markDirty, updateCache } = useTimeCoordinate();
const primitiveManager = usePrimitiveManager();

let chart: IChartApi | null = null;
let ddSeries: ISeriesApi<"Line", Time> | null = null;
// 悬停详情（2026-08 修复：回撤图缺 tooltip）
const ddTooltipData = ref<{ x: number; y: number; date: string; value: number; visible: boolean } | null>(null);
let _ddTooltipTimer: ReturnType<typeof setTimeout> | null = null;

function toTimeEpoch(dateStr: string): Time {
  const s = (dateStr?.slice(0, 10) || dateStr);
  return (Math.floor(new Date(s + "T00:00:00Z").getTime() / 1000)) as Time;
}
function toLineData(data: DrawdownPoint[]): LineData[] {
  return data.map((d) => ({
    time: toTimeEpoch(d.date),
    value: d.value,
  }));
}

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
        minBarSpacing: 10, // 2026-08: 放大上限统一为 10px
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

    ddSeries = chart.addSeries(LineSeries, {
      color: "#ef4444",
      lineWidth: 2 as const,
      priceLineVisible: false,
      lastValueVisible: true,
      priceFormat: {
        type: "custom",
        formatter: (v: number) => `${(v * 100).toFixed(1)}%`,
      },
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 3,
    }) as ISeriesApi<"Line", Time>;

    // 绑定 primitive manager（首次创建时）
    primitiveManager.bind(ddSeries, () => {
      // requestUpdate 回调：强制图表重绘（原语增删/切换开关后生效，不改可视范围）
      if (chart) {
        const r = chart.timeScale().getVisibleLogicalRange();
        if (r) chart.timeScale().setVisibleLogicalRange(r);
      }
    });
    // ⚠️ 关键修复：chart 创建后立即同步外部传入的 primitives
    if (props.primitives && props.primitives.length > 0) {
      const items = props.primitives.map((p) => {
        const dataId = (p as any).getData?.()?.id || (p as any)._data?.id;
        return { id: dataId || `dd-p-${Math.random().toString(36).slice(2, 8)}`, primitive: p };
      });
      primitiveManager.syncPrimitives(items);
    }

    // 悬停详情（2026-08 修复）：订阅十字光标，用 seriesData 精确取点
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || param.point === undefined) {
        ddTooltipData.value = null;
        return;
      }
      const sd = ddSeries ? param.seriesData.get(ddSeries) : undefined;
      if (sd && "value" in sd) {
        const dateStr = new Date((param.time as number) * 1000).toISOString().slice(0, 10);
        ddTooltipData.value = { x: param.point.x, y: param.point.y, date: dateStr, value: sd.value as number, visible: true };
        if (_ddTooltipTimer) clearTimeout(_ddTooltipTimer);
        _ddTooltipTimer = setTimeout(() => { ddTooltipData.value = null; }, 2500);
      }
    });
  }

  const ddData = toLineData(props.data);
  _currentDDData = ddData; // 供 viewport handler 做缩小限制
  ddSeries!.setData(ddData);
  // ⚠️ 用 setVisibleRange 替代 fitContent，保持时间等比模式
  if (ddData.length > 0) {
    chart!.timeScale().setVisibleRange({ from: ddData[0].time, to: ddData[ddData.length - 1].time });
  }
}

// ---- 视口变化订阅（幂等） ----
let _currentDDData: LineData[] = [];
let _viewportHandler: ((range: any) => void) | null = null;

function setupViewportListener() {
  const c = getChart();
  if (!c) return;
  if (_viewportHandler) {
    c.timeScale().unsubscribeVisibleTimeRangeChange(_viewportHandler);
  }
  _viewportHandler = (range: any) => {
    if (range) {
      // 限制缩小：可视范围超过完整数据跨度时，复位到完整数据
      const data = _currentDDData;
      if (data.length >= 2) {
        const firstT = data[0].time as number;
        const lastT = data[data.length - 1].time as number;
        const fromT = typeof range.from === "number" ? range.from : 0;
        const toT = typeof range.to === "number" ? range.to : 0;
        const dataSpan = lastT - firstT;
        const visSpan = toT - fromT;
        if (dataSpan > 0 && visSpan > dataSpan * 1.05) {
          c.timeScale().setVisibleRange({ from: firstT as any, to: lastT as any });
          return;
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
    const items = prims.map((p) => {
      const dataId = (p as any).getData?.()?.id || (p as any)._data?.id;
      return { id: dataId || `dd-p-${Math.random().toString(36).slice(2, 8)}`, primitive: p };
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
      ddSeries = null;
      return;
    }
    await nextTick();
    renderChart();
    setupViewportListener();
  },
  { deep: true, immediate: true },
);

onMounted(() => {
  bindGlobalEvents();
});

onBeforeUnmount(() => {
  primitiveManager.dispose();
  if (_viewportHandler && chart) {
    chart.timeScale().unsubscribeVisibleTimeRangeChange(_viewportHandler);
  }
  _viewportHandler = null;
  if (_ddTooltipTimer) clearTimeout(_ddTooltipTimer);
  destroyChart();
  chart = null;
  ddSeries = null;
  unbindGlobalEvents();
});

defineExpose({
  fitContent() {
    const data = ddSeries?.data();
    if (data && data.length > 0) {
      const last = data[data.length - 1];
      chart?.timeScale().setVisibleRange({ from: data[0].time, to: last.time });
    }
  },
  resize() {
    handleResize();
  },
  getChart,
});
</script>

<template>
  <div class="drawdown-chart-container">
    <div v-if="title" class="chart-header">
      <h5 class="chart-title">{{ title }}</h5>
    </div>
    <n-skeleton v-if="loading" :height="height + 'px'" width="100%" />
    <n-result v-else-if="error" status="500" title="回撤数据加载失败">
      <template #footer>
        <n-button type="primary" size="small" @click="emit('retry')">
          重试
        </n-button>
      </template>
    </n-result>
    <n-empty
      v-else-if="!hasData"
      description="暂无回撤数据"
      style="padding: 30px"
    />
    <div
      ref="chartContainer"
      class="drawdown-chart"
      :style="{
        height: hasData && !loading && !error ? height + 'px' : '',
      }"
    />
    <!-- 悬停详情浮层（2026-08 修复） -->
    <div
      v-if="ddTooltipData?.visible"
      class="crosshair-tooltip"
      :style="{ left: ddTooltipData.x + 'px', top: (ddTooltipData.y - 10) + 'px' }"
    >
      <div class="tooltip-date">{{ ddTooltipData.date }}</div>
      <div class="tooltip-row"><span>回撤</span><span>{{ (ddTooltipData.value * 100).toFixed(1) }}%</span></div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.drawdown-chart-container {
  width: 100%;
  position: relative;
}
.chart-header {
  margin-bottom: 8px;
}
.chart-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.drawdown-chart {
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
