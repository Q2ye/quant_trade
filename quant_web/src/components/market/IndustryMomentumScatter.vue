<!-- IndustryMomentumScatter.vue — 动量和量能四象限散点气泡图 -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { NButtonGroup, NButton, NSkeleton, NEmpty, NResult } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from "echarts/components";
use([
  CanvasRenderer,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkAreaComponent,
]);

import type { SwHeatmapItem } from "@/types/entities/market";

const props = withDefaults(
  defineProps<{
    data: SwHeatmapItem[];
    loading?: boolean;
    error?: boolean;
    selectedCode?: string;
  }>(),
  { data: () => [], loading: false, error: false, selectedCode: "" },
);

const emit = defineEmits<{ select: [code: string, name: string]; retry: [] }>();

const xWindow = ref<"pct_20d" | "pct_60d">("pct_20d");
const windowLabels: Record<string, string> = {
  pct_20d: "20日",
  pct_60d: "60日",
};

const scatterOption = computed(() => {
  if (!props.data.length) return null;

  const items = props.data.map((d) => {
    const x = (d[xWindow.value] as number) ?? 0;
    const y5 = (d.pct_5d as number) ?? 0;
    const xv = (d[xWindow.value] as number) ?? 0;
    const y = y5 - xv;
    const sz = d.amount
      ? Math.max(6, Math.min(40, Math.sqrt((d.amount / 1e8) * 20)))
      : 10;
    return {
      name: d.name,
      code: d.code,
      value: [x, y],
      symbolSize: sz,
      itemStyle: { color: x >= 0 ? "#ef5350" : "#26a69a", opacity: 0.8 },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: "rgba(0,0,0,0.4)",
          borderColor: "#fff",
          borderWidth: 1.5,
        },
      },
    };
  });

  // Compute median Y for quadrant line
  const yVals = items.map((d) => d.value[1]).sort((a, b) => a - b);
  const yMid = yVals[Math.floor(yVals.length / 2)];

  return {
    grid: { top: 10, right: 30, bottom: 40, left: 60 },
    xAxis: {
      type: "value",
      name: `涨跌幅(%) - ${windowLabels[xWindow.value]}`,
      nameLocation: "center",
      nameGap: 25,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 10, formatter: (v: number) => v + "%" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
    },
    yAxis: {
      type: "value",
      name: "加速度(5日 - " + windowLabels[xWindow.value] + ")",
      nameLocation: "center",
      nameGap: 40,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 10, formatter: (v: number) => v + "%" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
    },
    tooltip: {
      trigger: "item",
      formatter: (p: any) => {
        const d = p.data;
        return `<strong>${d.name}</strong><br/>${windowLabels[xWindow.value]}涨跌: ${d.value[0].toFixed(2)}%<br/>加速度: ${d.value[1] > 0 ? "+" : ""}${d.value[1].toFixed(2)}%`;
      },
    },
    animationDurationUpdate: 500,
    animationEasingUpdate: "cubicInOut",
    series: [
      {
        type: "scatter",
        data: items,
        markLine: {
          silent: true,
          symbol: "none",
          data: [
            {
              xAxis: 0,
              lineStyle: {
                color: "rgba(255,255,255,0.2)",
                type: "dashed",
                width: 1,
              },
            },
            {
              yAxis: yMid,
              lineStyle: {
                color: "rgba(255,255,255,0.2)",
                type: "dashed",
                width: 1,
              },
            },
          ],
        },
      },
    ],
  };
});

function handleClick(params: any) {
  if (params.data) emit("select", params.data.code, params.data.name);
}

// ---- quadrant labels ----
const quadrantData = computed(() => {
  // Compute from data
  const items = props.data.map((d) => ({
    name: d.name,
    x: (d[xWindow.value] as number) ?? 0,
    y: ((d.pct_5d as number) ?? 0) - ((d[xWindow.value] as number) ?? 0),
  }));
  const yVals = items.map((d) => d.y).sort((a, b) => a - b);
  const yMid = yVals[Math.floor(yVals.length / 2)];
  return { yMid };
});
</script>

<template>
  <div class="scatter-chart">
    <!-- Controls -->
    <div class="scatter-controls">
      <n-button-group size="tiny">
        <n-button
          v-for="k in ['pct_20d', 'pct_60d'] as const"
          :key="k"
          :type="xWindow === k ? 'primary' : 'default'"
          @click="xWindow = k"
          >{{ windowLabels[k] }}</n-button
        >
      </n-button-group>

      <!-- Quadrant legend -->
      <div class="quadrant-legend">
        <span class="q-item"
          ><i class="q-dot" style="background: #ef5350" /> 强势领涨</span
        >
        <span class="q-item"
          ><i class="q-dot" style="background: #ff9800" /> 高位滞涨</span
        >
        <span class="q-item"
          ><i class="q-dot" style="background: #26a69a" /> 弱势下跌</span
        >
        <span class="q-item"
          ><i class="q-dot" style="background: #448aff" /> 温和抗跌</span
        >
      </div>
    </div>

    <!-- States -->
    <n-skeleton v-if="loading" height="400px" width="100%" />
    <n-result v-else-if="error" status="500" title="数据加载失败">
      <template #footer
        ><n-button type="primary" @click="emit('retry')"
          >重试</n-button
        ></template
      >
    </n-result>
    <n-empty
      v-else-if="!scatterOption"
      description="暂无动量和量能数据"
      style="padding: 80px"
    />

    <!-- Chart -->
    <VChart
      v-else
      :option="scatterOption"
      autoresize
      style="height: 420px"
      @click="handleClick"
    />
  </div>
</template>

<style lang="scss" scoped>
.scatter-chart {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scatter-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.quadrant-legend {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.q-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--n-text-color-3);
}

.q-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
</style>
