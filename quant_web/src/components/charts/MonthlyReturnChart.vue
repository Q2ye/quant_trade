<!-- MonthlyReturnChart.vue — lightweight-charts 月度收益柱状图（从 vue-echarts 迁移）
     使用 HistogramSeries，基于时间轴，正收益绿色 / 负收益红色 -->
<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { NEmpty } from "naive-ui";
import {
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type HistogramData,
  type Time,
} from "lightweight-charts";
import { useChartLifecycle } from "@/composables/useChartLifecycle";

export interface MonthlyReturnPoint {
  month: string; // 'YYYY-MM'
  return: number; // ratio (e.g. 0.05 = +5%)
}

const props = withDefaults(
  defineProps<{
    data: MonthlyReturnPoint[];
    title?: string;
    height?: number;
  }>(),
  {
    data: () => [],
    title: "月度收益",
    height: 300,
  },
);

const hasData = computed(() => props.data.length > 0);

const {
  chartContainer,
  createChartInstance,
  destroyChart,
  handleResize,
  bindGlobalEvents,
  unbindGlobalEvents,
  getChart,
} = useChartLifecycle({
  height: props.height,
  timeScale: { timeVisible: false },
  rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
});

let chart: IChartApi | null = null;
let series: ISeriesApi<"Histogram", Time> | null = null;
let _currentData: HistogramData[] = [];
let _viewportHandler: ((range: any) => void) | null = null;

// 悬停详情（2026-08：lightweight-charts 无内置 tooltip，自建浮层）
const tooltipData = ref<{ x: number; y: number; month: string; value: number } | null>(null);
let _tooltipTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Convert 'YYYY-MM' to epoch 秒（2026-08 修复：lightweight-charts v5 的 business day 时间
 * 会让 crosshair param.time 返回对象，String() 得 "[object Object]" 导致 tooltip 月份乱码；
 * 统一用 epoch 秒线性时间轴，与其他图表一致）
 */
function monthToTime(month: string): Time {
  const m = month.slice(0, 7); // 'YYYY-MM'
  return (Math.floor(new Date(m + "-01T00:00:00Z").getTime() / 1000)) as Time;
}

function toHistogramData(data: MonthlyReturnPoint[]): HistogramData[] {
  return data.map((d) => {
    const pct = d.return * 100; // ratio → percentage
    return {
      time: monthToTime(d.month),
      value: Math.round(pct * 100) / 100, // round to 2 decimal places
      // A 股惯例：红涨绿跌（2026-08 修复：原为绿涨红跌）
      color: pct >= 0 ? "rgba(208,48,80,0.65)" : "rgba(24,160,88,0.65)",
    };
  });
}

function renderChart() {
  const el = chartContainer.value;
  if (!el) return;
  const w = el.clientWidth;
  if (!w || w <= 0 || !props.data.length) return;

  const isNew = !chart;
  if (isNew) {
    chart = createChartInstance();
    if (!chart) return;

    series = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "custom",
        formatter: (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`,
      },
    }) as ISeriesApi<"Histogram", Time>;

    // 悬停详情：订阅十字光标（2026-08 修复：用 seriesData 精确取点，替代 time 字符串匹配）
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || param.point === undefined) {
        tooltipData.value = null;
        return;
      }
      const sd = series ? param.seriesData.get(series) : undefined;
      if (sd && "value" in sd) {
        // epoch 秒 → 月份；兼容 business day 字符串
        const month = typeof param.time === "number"
          ? new Date(param.time * 1000).toISOString().slice(0, 7)
          : String(param.time).slice(0, 7);
        tooltipData.value = {
          x: param.point.x,
          y: param.point.y,
          month,
          value: Number(sd.value ?? 0),
        };
        if (_tooltipTimer) clearTimeout(_tooltipTimer);
        _tooltipTimer = setTimeout(() => { tooltipData.value = null; }, 2500);
      }
    });

    // 缩小复位：可视范围超过完整数据跨度时回到全量（缩放最小限制）
    _viewportHandler = (range: any) => {
      if (!range || _currentData.length < 2) return;
      const times = _currentData.map((d) => d.time as number);
      const firstT = times[0];
      const lastT = times[times.length - 1];
      const fromT = typeof range.from === "number" ? range.from : 0;
      const toT = typeof range.to === "number" ? range.to : 0;
      const dataSpan = lastT - firstT;
      const visSpan = toT - fromT;
      if (dataSpan > 0 && visSpan > dataSpan * 1.05) {
        chart?.timeScale().setVisibleRange({ from: firstT as any, to: lastT as any });
      }
    };
    chart.timeScale().subscribeVisibleTimeRangeChange(_viewportHandler);
  }

  _currentData = toHistogramData(props.data);
  series!.setData(_currentData);
  chart!.timeScale().fitContent();
}

watch(
  () => props.data,
  async (val) => {
    if (!val?.length) {
      destroyChart();
      chart = null;
      series = null;
      return;
    }
    await nextTick();
    renderChart();
  },
  { deep: true, immediate: true },
);

onMounted(() => {
  bindGlobalEvents();
});

onBeforeUnmount(() => {
  if (chart && _viewportHandler) {
    chart.timeScale().unsubscribeVisibleTimeRangeChange(_viewportHandler);
  }
  _viewportHandler = null;
  destroyChart();
  chart = null;
  series = null;
  tooltipData.value = null;
  unbindGlobalEvents();
});

defineExpose({
  fitContent() { chart?.timeScale().fitContent(); },
  resize() { handleResize(); },
  getChart,
});
</script>

<template>
  <div class="monthly-return-wrapper">
    <div v-if="title" class="chart-header">
      <h5 class="chart-title">{{ title }}</h5>
    </div>
    <n-empty
      v-if="!hasData"
      description="暂无月度收益数据"
      size="small"
      style="padding: 20px 0"
    />
    <div
      v-show="hasData"
      ref="chartContainer"
      class="monthly-chart"
      :style="{ height: height + 'px' }"
    />
    <!-- 悬停详情浮层（2026-08） -->
    <div
      v-if="tooltipData"
      class="monthly-tooltip"
      :style="{ left: tooltipData.x + 10 + 'px', top: tooltipData.y + 8 + 'px' }"
    >
      <div class="tt-month">{{ tooltipData.month }}</div>
      <div class="tt-value" :style="{ color: tooltipData.value >= 0 ? '#f0483e' : '#18a058' }">
        {{ tooltipData.value > 0 ? "+" : "" }}{{ tooltipData.value.toFixed(2) }}%
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.monthly-return-wrapper {
  width: 100%;
  zoom: 1.25; /* 抵消 html { zoom: 0.8 }，恢复 chart 内部坐标系统与 OS 鼠标一致 */
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
.monthly-chart {
  width: 100%;
}
.monthly-tooltip {
  position: absolute;
  z-index: 10;
  pointer-events: none;
  background: var(--color-bg-card, rgba(18, 24, 40, 0.95));
  border: 1px solid var(--color-primary, #448aff);
  border-radius: 6px;
  padding: 5px 9px;
  font-size: 12px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}
.tt-month {
  color: var(--color-text-secondary, #8898b8);
}
.tt-value {
  font-weight: 700;
  font-size: 13px;
}
</style>
