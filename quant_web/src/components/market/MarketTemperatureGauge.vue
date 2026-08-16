<script setup lang="ts">
// 市场温度计（v5 N1）—— 温度计仪表盘 + 四维分位小字；Tab2 嵌入四维状态雷达（D4 落地）
import { computed } from "vue";
import { NSkeleton, NEmpty, NTabs, NTabPane, NTag, NTooltip } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { GaugeChart } from "echarts/charts";
import type { MarketTemperature, TemperatureDimension } from "@/types/entities/market";
import MarketStateRadar from "@/components/market/MarketStateRadar.vue";
import PctlBar from "@/components/market/PctlBar.vue";

use([CanvasRenderer, GaugeChart]);

const props = defineProps<{
  data: MarketTemperature | null;
  loading: boolean;
}>();

const zoneColor = computed(() => {
  const t = props.data?.temperature;
  if (t == null) return "#cbd5e1";
  if (t < 30) return "#26a69a";
  if (t <= 70) return "#ff9800";
  return "#ef5350";
});

// 环渐变：绿(#26a69a) → 橙(#ff9800) → 红(#ef5350) 多段插值，近似平滑渐变环
function ringGradientStops(): [number, string][] {
  const segs = 24;
  const stops: [number, string][] = [];
  for (let i = 0; i <= segs; i++) {
    const t = i / segs;
    let r = 0, g = 0, b = 0;
    if (t < 0.5) {
      const k = t / 0.5;
      r = Math.round(0x26 + (0xff - 0x26) * k);
      g = Math.round(0xa6 + (0x98 - 0xa6) * k);
      b = Math.round(0x9a + (0x00 - 0x9a) * k);
    } else {
      const k = (t - 0.5) / 0.5;
      r = Math.round(0xff + (0xef - 0xff) * k);
      g = Math.round(0x98 + (0x53 - 0x98) * k);
      b = Math.round(0x00 + (0x50 - 0x00) * k);
    }
    stops.push([i / segs, `rgb(${r},${g},${b})`]);
  }
  return stops;
}

const gaugeOption = computed(() => ({
  series: [
    {
      type: "gauge",
      min: 0,
      max: 100,
      startAngle: 210,
      endAngle: -30,
      radius: "95%",
      // 指针与数值按当前温度区着色；色环为 绿→橙→红 渐变
      pointer: { show: true, length: "58%", width: 5, itemStyle: { color: zoneColor.value } },
      axisLine: {
        lineStyle: {
          width: 12,
          color: ringGradientStops(),
        },
      },
      axisTick: { show: false },
      splitLine: { length: 7, lineStyle: { color: "rgba(255,255,255,0.28)", width: 1 } },
      axisLabel: {
        fontSize: 10,
        distance: 17,
        color: "#94a3b8",
        formatter: (v: number) => (v === 30 || v === 70 ? String(v) : ""),
      },
      anchor: { show: false },
      title: {
        show: true,
        offsetCenter: [0, "76%"],
        fontSize: 12,
        color: "#94a3b8",
      },
      detail: {
        valueAnimation: true,
        offsetCenter: [0, "32%"],
        fontSize: 30,
        fontWeight: 700,
        color: zoneColor.value,
        formatter: (v: number) =>
          props.data?.temperature != null ? v.toFixed(1) : "--",
      },
      data: [
        {
          value: props.data?.temperature ?? 0,
          name: props.data?.zone ? props.data.zone + "区" : "-",
        },
      ],
    },
  ],
}));

const dimItems = computed(() => {
  const d = props.data?.dimensions;
  if (!d) return [];
  return [
    { label: "估值", unit: "PE", dim: d.valuation, color: "#26a69a" },
    { label: "情绪", unit: "涨停家数", dim: d.emotion, color: "#ff9800" },
    { label: "资金", unit: "北向20日", dim: d.capital, color: "#448aff" },
    { label: "技术", unit: "MA20占比", dim: d.technical, color: "#7e57c2" },
  ];
});

// 样本不足时提示具体缺失维度（后端 120s 短 TTL 自动重算自愈）
const dimNameMap: Record<string, string> = {
  valuation: "估值",
  emotion: "情绪",
  capital: "资金",
  technical: "技术",
};
const missingDims = computed(() => {
  const d = props.data?.dimensions;
  if (!d) return [];
  return (Object.keys(d) as (keyof typeof d)[])
    .filter((k) => d[k]?.percentile == null)
    .map((k) => dimNameMap[k]);
});

const dimValueText = (it: { unit: string; dim: TemperatureDimension }) => {
  const v = it.dim.value;
  if (v == null) return "-";
  if (it.unit === "北向20日") return (v / 1e4).toFixed(1) + "亿"; // north_money 单位万元 → /1e4 = 亿
  if (it.unit === "MA20占比") return v.toFixed(1) + "%";
  return v.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
};
</script>

<template>
  <n-card size="small" class="full-height-card" title="市场温度计">
    <template #header-extra>
      <n-tooltip v-if="data?.sample_warning" trigger="hover">
        <template #trigger>
          <n-tag size="tiny" type="warning" :bordered="false">样本不足</n-tag>
        </template>
        缺失维度：{{ missingDims.join("、") }}（后台 120s 内自动重算）
      </n-tooltip>
    </template>
    <n-skeleton v-if="loading && !data" :text="true" :repeat="3" />
    <n-empty v-else-if="!data" description="暂无温度数据" size="small" style="padding: 24px" />
    <n-tabs v-else type="segment" size="small" default-value="gauge">
      <n-tab-pane name="gauge" tab="温度计">
        <div class="gauge-wrap">
          <VChart :option="gaugeOption" autoresize style="height: 190px" />
        </div>
        <div class="dim-grid">
          <div v-for="it in dimItems" :key="it.label" class="dim-item">
            <div class="dim-val-line">
              <span class="dim-label">{{ it.label }}</span>
              <span class="dim-val">{{ dimValueText(it) }}</span>
              <n-tag v-if="it.dim.approx" size="tiny" :bordered="false">近似</n-tag>
            </div>
            <div class="dim-pctl">
              <PctlBar :value="it.dim.percentile" :color="it.color" />
            </div>
          </div>
        </div>
        <div class="temp-note">
          分位基准 = 各指标自身历史（中线 50% 为历史中位）· 估值 1000 日 / 情绪·技术 250 日 / 资金 750 日
        </div>
      </n-tab-pane>
      <n-tab-pane name="radar" tab="四维雷达">
        <MarketStateRadar />
      </n-tab-pane>
    </n-tabs>
  </n-card>
</template>

<style lang="scss" scoped>
.full-height-card {
  height: 100%;
}
.gauge-wrap {
  display: flex;
  justify-content: center;
}
.dim-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-top: 8px;
}
.dim-item {
  padding: 6px 4px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  text-align: center;
}
.dim-val-line {
  display: flex;
  justify-content: center;
  align-items: baseline;
  gap: 5px;
}
.dim-label {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.dim-val {
  font-size: 13px;
  font-weight: 600;
  font-family: monospace;
}
.dim-pctl {
  margin-top: 4px;
  padding: 0 2px;
}
.temp-note {
  margin-top: 8px;
  font-size: 10px;
  line-height: 1.4;
  color: var(--n-text-color-3);
  text-align: center;
}
@media (max-width: 640px) {
  .dim-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
