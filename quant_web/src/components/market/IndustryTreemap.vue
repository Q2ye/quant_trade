<!-- IndustryTreemap.vue — 申万行业矩形树图 -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NCard,
  NButtonGroup,
  NButton,
  NSwitch,
  NSkeleton,
  NEmpty,
  NResult,
} from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { TreemapChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
use([CanvasRenderer, TreemapChart, TooltipComponent]);

import { tokens } from "@/styles/design-tokens";
import type { SwHeatmapItem } from "@/types/entities/market";

const props = withDefaults(
  defineProps<{
    data: SwHeatmapItem[];
    loading?: boolean;
    error?: boolean;
  }>(),
  {
    data: () => [],
    loading: false,
    error: false,
  },
);

const emit = defineEmits<{
  select: [code: string, name: string];
  retry: [];
}>();

// ---- state ----
const activeWindow = ref("pct_1d");
const areaByAmount = ref(false);

const windows: { key: string; label: string }[] = [
  { key: "pct_1d", label: "1日" },
  { key: "pct_5d", label: "5日" },
  { key: "pct_10d", label: "10日" },
  { key: "pct_20d", label: "20日" },
  { key: "pct_30d", label: "30日" },
  { key: "pct_60d", label: "60日" },
];

// ---- color ----
function heatmapColor(pct: number | null): string {
  if (pct == null) return "transparent";
  const a = 0.08 + (Math.min(Math.abs(pct), 10) / 10) * 0.72;
  return pct >= 0
    ? `rgba(239,83,80,${a.toFixed(2)})`
    : `rgba(38,166,154,${a.toFixed(2)})`;
}

// ---- echarts option ----
const isDataEmpty = computed(
  () => !props.loading && !props.error && props.data.length === 0,
);

const treemapOption = computed(() => {
  if (!props.data.length) return null;

  // Find the min and max pct for better color range
  const items = props.data.map((d) => ({
    name: d.name,
    code: d.code,
    pct:
      (d[activeWindow.value as keyof SwHeatmapItem] as
        | number
        | null
        | undefined) ?? null,
    amount: d.amount ?? null,
  }));

  // Build treemap data
  const seriesData = items.map((item) => {
    const pct = item.pct;
    const value =
      areaByAmount.value && item.amount ? Math.max(item.amount, 1) : 1;
    return {
      name: item.name,
      value: value,
      pct: pct,
      code: item.code,
      itemStyle: {
        color: heatmapColor(pct),
      },
      label: {
        show: true,
        formatter: () => {
          const pctText =
            pct != null ? (pct > 0 ? "+" : "") + pct.toFixed(1) + "%" : "-";
          return `${item.name}\n${pctText}`;
        },
      },
    };
  });

  return {
    tooltip: {
      formatter: (params: any) => {
        if (!params.data) return "";
        const d = params.data;
        const pctText =
          d.pct != null ? (d.pct > 0 ? "+" : "") + d.pct.toFixed(2) + "%" : "-";
        const amtText =
          d.value && d.value > 1
            ? `成交额: ${(d.value / 1e8).toFixed(1)}亿`
            : "";
        return `<strong>${d.name}</strong><br/>${activeWindow.value}: ${pctText}${amtText ? "<br/>" + amtText : ""}`;
      },
    },
    series: [
      {
        type: "treemap",
        roam: true,
        squareRatio: 1,
        width: "100%",
        height: "100%",
        breadcrumb: { show: false },
        label: {
          show: true,
          position: "inside",
          fontSize: 12,
          color: "#fff",
          textShadowColor: "rgba(0,0,0,0.4)",
          textShadowBlur: 2,
          formatter: (params: any) => {
            if (!params.data) return "";
            const pctText =
              params.data.pct != null
                ? (params.data.pct > 0 ? "+" : "") +
                  params.data.pct.toFixed(1) +
                  "%"
                : "-";
            return `${params.data.name}\n${pctText}`;
          },
        },
        upperLabel: { show: false },
        itemStyle: {
          borderColor: "rgba(255,255,255,0.12)",
          borderWidth: 2,
          borderRadius: 6,
        },
        emphasis: {
          itemStyle: {
            borderColor: "#fff",
            borderWidth: 3,
            shadowBlur: 10,
            shadowColor: "rgba(0,0,0,0.3)",
          },
          label: { fontSize: 14, fontWeight: "bold" },
        },
        levels: [
          {
            colorMappingBy: "value",
            colorSaturation: [0.3, 0.7],
            colorAlpha: [0.6, 1],
          },
        ],
        data: seriesData,
      },
    ],
  };
});

// ---- events ----
function handleChartClick(params: any) {
  if (params.data && params.data.code) {
    emit("select", params.data.code, params.data.name);
  }
}

function setWindow(key: string) {
  activeWindow.value = key;
}

function toggleAreaMode(val: boolean) {
  areaByAmount.value = val;
}
</script>

<template>
  <div class="treemap-container">
    <!-- controls -->
    <div class="treemap-controls">
      <n-button-group size="small">
        <n-button
          v-for="w in windows"
          :key="w.key"
          :type="activeWindow === w.key ? 'primary' : 'default'"
          @click="setWindow(w.key)"
        >
          {{ w.label }}
        </n-button>
      </n-button-group>

      <div class="area-toggle">
        <span
          style="
            font-size: 12px;
            color: var(--n-text-color-3);
            margin-right: 6px;
          "
          >按成交额缩放</span
        >
        <n-switch
          size="small"
          :value="areaByAmount"
          @update:value="toggleAreaMode"
        />
      </div>
    </div>

    <!-- Loading -->
    <n-skeleton
      v-if="loading"
      height="400px"
      width="100%"
      :sharp="false"
      style="border-radius: 8px"
    />

    <!-- Error -->
    <n-result
      v-else-if="error"
      status="500"
      title="数据加载失败"
      description="请检查网络连接后重试"
      style="padding: 40px"
    >
      <template #footer>
        <n-button type="primary" @click="emit('retry')">重试</n-button>
      </template>
    </n-result>

    <!-- Empty -->
    <n-empty
      v-else-if="isDataEmpty"
      description="暂无行业数据"
      style="padding: 60px"
    />

    <!-- Treemap -->
    <v-chart
      v-else-if="treemapOption"
      :option="treemapOption"
      autoresize
      style="height: 500px; width: 100%"
      @click="handleChartClick"
    />
  </div>
</template>

<style lang="scss" scoped>
.treemap-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.treemap-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.area-toggle {
  display: flex;
  align-items: center;
}
</style>
