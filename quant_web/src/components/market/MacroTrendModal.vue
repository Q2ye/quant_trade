<!-- MacroTrendModal.vue — 宏观趋势弹窗 -->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { NModal, NCard, NSkeleton, NEmpty, NButton } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent]);

const props = defineProps<{ type: "cpi" | "ppi" | "gdp" }>();
const emit = defineEmits(["close"]);

const loading = ref(true);
const data = ref<any[]>([]);
const labelMap: Record<string, string> = {
  cpi: "CPI 同比%",
  ppi: "PPI 同比%",
  gdp: "GDP 同比%",
};
const colorMap: Record<string, string> = {
  cpi: "#ef5350",
  ppi: "#2196f3",
  gdp: "#4caf50",
};
const valKey: Record<string, string> = {
  cpi: "cpi_yoy",
  ppi: "ppi_yoy",
  gdp: "gdp_yoy",
};

const option = computed(() => {
  if (!data.value.length) return {};
  const items = [...data.value].reverse();
  return {
    grid: { top: 20, right: 20, bottom: 30, left: 60 },
    xAxis: {
      type: "category",
      data: items.map((d: any) =>
        (d.month || d.quarter || d.date || "").slice(0, 7),
      ),
      axisLabel: { fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10, formatter: (v: number) => v + "%" },
    },
    tooltip: { trigger: "axis" },
    series: [
      {
        name: labelMap[props.type],
        type: "line",
        data: items.map((d: any) => d[valKey[props.type]] ?? 0),
        smooth: true,
        lineStyle: { color: colorMap[props.type], width: 2 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: colorMap[props.type] + "33" },
              { offset: 1, color: colorMap[props.type] + "00" },
            ],
          },
        },
        symbol: "none",
      },
    ],
  };
});

async function load() {
  loading.value = true;
  try {
    const limit = props.type === "gdp" ? 20 : 24;
    const r = await request
      .get(`/quantTrade/market/macro/${props.type}?limit=${limit}`)
      .then(handleResponse);
    data.value = (r as any).data || [];
  } catch {
    data.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => props.type, load);
</script>

<template>
  <n-modal
    :show="true"
    @mask-click="emit('close')"
    preset="card"
    style="width: 680px; max-width: 90vw"
    :title="labelMap[type] + ' 历史趋势'"
  >
    <template #header-extra>
      <n-button size="tiny" quaternary @click="emit('close')">✕</n-button>
    </template>
    <n-skeleton v-if="loading" :text="true" :repeat="4" />
    <n-empty
      v-else-if="!data.length"
      description="暂无数据"
      style="padding: 40px"
    />
    <v-chart v-else :option="option" autoresize style="height: 320px" />
  </n-modal>
</template>
