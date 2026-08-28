<!-- ProfitDistributionChart.vue — 单笔盈亏分布直方图（vue-echarts，红涨绿跌，暗色统一） -->
<script setup lang="ts">
import { computed } from "vue";
import { NEmpty } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart } from "echarts/charts";
import { TooltipComponent, GridComponent } from "echarts/components";
use([CanvasRenderer, BarChart, TooltipComponent, GridComponent]);

const props = defineProps<{ data: { bins: number[]; counts: number[] } }>();

const hasData = computed(() => props.data && props.data.counts?.length > 0);

const chartOption = computed(() => {
  if (!hasData.value) return undefined;
  const counts = props.data.counts;
  // bins 是区间边界（长度 = counts + 1），取左边界作 x 轴标签，与 counts 对齐
  const labels = props.data.bins.slice(0, counts.length).map((b) => `${(b * 100).toFixed(0)}%`);
  return {
    grid: { top: 20, right: 10, bottom: 30, left: 45 },
    xAxis: {
      type: "category" as const,
      data: labels,
      axisLabel: { fontSize: 10, color: "#8898b8" },
      axisLine: { lineStyle: { color: "#30363d" } },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#8898b8" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    },
    tooltip: {
      trigger: "axis" as const,
      formatter: (p: any) => `${p[0].name} 盈亏：${p[0].value} 笔`,
    },
    series: [
      {
        type: "bar" as const,
        barWidth: "70%",
        data: counts.map((c, i) => ({
          value: c,
          itemStyle: {
            // A股红涨绿跌：正收益区间红、负收益区间绿
            color: props.data.bins[i] >= 0 ? "rgba(239,83,80,0.7)" : "rgba(38,166,154,0.7)",
          },
        })),
      },
    ],
  };
});
</script>

<template>
  <div class="profit-dist-container">
    <n-empty v-if="!hasData" description="暂无收益分布数据" style="padding: 30px" />
    <v-chart v-else :option="chartOption" autoresize style="height: 300px; width: 100%" />
  </div>
</template>

<style lang="scss" scoped>
.profit-dist-container { width: 100%; position: relative; zoom: 1.25; }
</style>
