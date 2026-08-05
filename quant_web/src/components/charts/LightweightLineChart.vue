<!-- LightweightLineChart.vue -->
<script setup lang="ts">
import { watch, onMounted, onBeforeUnmount, nextTick, computed, ref } from "vue";
import { NSkeleton, NEmpty } from "naive-ui";
import {
  createChart, ColorType, LineSeries, HistogramSeries,
  type IChartApi, type ISeriesApi, type LineData, type HistogramData, type Time,
} from "lightweight-charts";

export interface LineSeriesDef {
  name: string; color: string;
  data: { time: string; value: number | null }[];
  lineWidth?: number;
  lineStyle?: 0 | 1 | 2 | 3; // 0=Solid 1=Dotted 2=Dashed 3=LargeDashed
}
export interface BarSeriesDef {
  name: string;
  data: { time: string; value: number | null; color?: string }[];
}

const props = withDefaults(defineProps<{
  lineSeries?: LineSeriesDef[]; barSeries?: BarSeriesDef[];
  height?: number; loading?: boolean; emptyText?: string;
}>(), {
  lineSeries: () => [], barSeries: () => [], height: 280, loading: false, emptyText: "暂无数据",
});

const emit = defineEmits<{
  timeRangeChange: [range: { from: number; to: number }];
}>();

const container = ref<HTMLDivElement>();
let chart: IChartApi | null = null;
const store = new Map<string, ISeriesApi<any, Time>>();

// 悬浮提示
const tooltip = ref<{ x: number; y: number; date: string; items: { name: string; value: number; color: string }[]; visible: boolean } | null>(null);
let _tooltipTimer: ReturnType<typeof setTimeout> | null = null;

const hasData = computed(() =>
  props.lineSeries.some(s => s.data.length > 0) ||
  props.barSeries.some(s => s.data.length > 0)
);

// 图例：过滤零线等参考线
const legendItems = computed(() => {
  const items: { name: string; color: string }[] = [];
  for (const s of props.lineSeries) {
    if (s.name !== "零线") items.push({ name: s.name, color: s.color });
  }
  for (const s of props.barSeries) {
    items.push({ name: s.name, color: "rgba(239,83,80,0.6)" });
  }
  return items;
});

function toTime(d: string): number {
  return Math.floor(new Date((d?.slice(0,10)||d)+"T00:00:00Z").getTime()/1000);
}

function build() {
  const el = container.value;
  if (!el) return;
  const w = el.clientWidth;
  if (!w || w <= 0) return;

  if (!chart) {
    chart = createChart(el, {
      width: w, height: props.height,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
      crosshair: { mode: 1 },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)", scaleMargins: { top: 0.05, bottom: 0.05 } },
    });
    el.querySelector('a')?.remove();
    // 订阅可视范围变化（用于动态加载）
    chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      if (range) {
        emit("timeRangeChange", {
          from: typeof range.from === "number" ? range.from : 0,
          to: typeof range.to === "number" ? range.to : 0,
        });
      }
    });

    // 悬浮提示
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || param.point === undefined) {
        tooltip.value = null;
        return;
      }
      const dateStr = new Date((param.time as number) * 1000).toISOString().slice(0, 10);
      const items: { name: string; value: number; color: string }[] = [];

      // 收集各 series 在該時間的值
      for (const [id, s] of store) {
        const sd = param.seriesData.get(s);
        if (sd) {
          const prefix = id.startsWith("L:") ? id.slice(2) : id.slice(2);
          let v: number | null = null;
          if (id.startsWith("L:")) {
            v = (sd as any).value ?? null;
          } else {
            v = (sd as any).value ?? null;
          }
          if (v != null) {
            const opts = (s as any).options?.() || (s as any)._options || {};
            items.push({ name: prefix, value: v, color: opts.color || "#9ca3af" });
          }
        }
      }
      if (items.length > 0) {
        if (_tooltipTimer) clearTimeout(_tooltipTimer);
        tooltip.value = { x: param.point.x, y: param.point.y, date: dateStr, items, visible: true };
        _tooltipTimer = setTimeout(() => { tooltip.value = null; }, 3000);
      } else {
        tooltip.value = null;
      }
    });
  } else {
    chart.applyOptions({ width: w });
  }

  const wanted = new Set<string>();
    for (let i = 0; i < props.lineSeries.length; i++) {
      const def = props.lineSeries[i];
      const id = "L:"+def.name; wanted.add(id);
      let s = store.get(id);
      if (!s) {
        s = chart.addSeries(LineSeries, {
          color: def.color,
          lineWidth: (def.lineWidth ?? 1.5) as any,
          lineStyle: def.lineStyle ?? 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        store.set(id, s);
      }
      const seen = new Set<number>();
      const pts = def.data
        .filter(p=>p.value!=null&&!isNaN(p.value))
        .map(p=>({t:toTime(p.time),v:p.value as number}))
        .filter(p=>{ if(seen.has(p.t))return false; seen.add(p.t);return true; })
        .sort((a,b)=>a.t-b.t);
      (s as ISeriesApi<"Line",Time>).setData(pts.map(p=>({time:p.t as Time,value:p.v})));
    }
    for (const def of props.barSeries) {
      const id = "B:"+def.name; wanted.add(id);
      let s = store.get(id);
      if (!s) { s = chart.addSeries(HistogramSeries, { priceFormat:{type:"volume"}, priceScaleId:def.name }); store.set(id,s); }
      const seen = new Set<number>();
      const pts = def.data
        .filter(p=>p.value!=null&&!isNaN(p.value))
        .map(p=>({t:toTime(p.time),v:p.value as number,c:p.color}))
        .filter(p=>{ if(seen.has(p.t))return false; seen.add(p.t);return true; })
        .sort((a,b)=>a.t-b.t);
      (s as ISeriesApi<"Histogram",Time>).setData(pts.map(p=>({time:p.t as Time,value:p.v,color:p.c})));
    }
    for (const [id,s] of store) { if(!wanted.has(id)){try{chart!.removeSeries(s)}catch{/* */}store.delete(id);} }
    if (wanted.size>0) chart.timeScale().fitContent();
}

let _ob: ResizeObserver|null = null;
onMounted(() => {
  const el = container.value;
  if (el) {
    _ob = new ResizeObserver(() => { build(); });
    _ob.observe(el);
  }
  nextTick(build);
  setTimeout(build, 200);
  setTimeout(build, 600);
});

onBeforeUnmount(() => {
  _ob?.disconnect();
  if (chart) { chart.remove(); chart = null; }
  store.clear();
});

watch(() => [props.lineSeries, props.barSeries], () => nextTick(build), { deep: true });
</script>

<template>
  <div :style="{ minHeight: height+'px', zoom:'1.25' }">
    <n-skeleton v-if="loading" :text="true" :repeat="5" />
    <n-empty v-else-if="!hasData" :description="emptyText" style="padding:40px" />
    <div ref="container" :style="{ width:'100%', height:height+'px' }" />
    <!-- 图例 -->
    <div v-if="legendItems.length" class="lw-legend">
      <span v-for="it in legendItems" :key="it.name" class="lw-legend-item">
        <i :style="{ background: it.color }" /> {{ it.name }}
      </span>
    </div>
    <!-- 悬浮提示 -->
    <div
      v-if="tooltip?.visible"
      class="lw-tooltip"
      :style="{ left: tooltip.x + 'px', top: (tooltip.y - 10) + 'px' }"
    >
      <div class="lw-tooltip-date">{{ tooltip.date }}</div>
      <div v-for="it in tooltip.items" :key="it.name" class="lw-tooltip-row">
        <span :style="{ color: it.color }">● {{ it.name }}</span>
        <span>{{ Number.isInteger(it.value) ? it.value.toLocaleString() : it.value.toFixed(4) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lw-legend {
  display: flex; flex-wrap: wrap; gap: 4px 12px;
  padding: 4px 0 0 8px; font-size: 11px;
}
.lw-legend-item { display: inline-flex; align-items: center; gap: 3px; color: var(--n-text-color-3, #999); }
.lw-legend-item i { display: inline-block; width: 10px; height: 2px; border-radius: 1px; flex-shrink: 0; }
.lw-tooltip {
  position: absolute;
  transform: translate(-50%, -100%);
  pointer-events: none;
  z-index: 100;
  background: var(--color-bg-card, rgba(18, 24, 40, 0.95));
  border: 1px solid var(--color-primary, #448aff);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  line-height: 1.6;
  white-space: nowrap;
}
.lw-tooltip-date { color: var(--n-text-color-3, #999); margin-bottom: 2px; font-size: 11px; }
.lw-tooltip-row { display: flex; justify-content: space-between; gap: 16px; }
</style>
