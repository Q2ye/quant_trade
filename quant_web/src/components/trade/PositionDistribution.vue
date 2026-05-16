<template>
  <div class="position-distribution">
    <div v-if="positions.length === 0" class="empty">暂无持仓数据</div>
    <NGrid v-else :cols="24" :x-gap="16">
      <NGridItem :span="12">
        <div ref="chartRef" style="height: 250px"></div>
      </NGridItem>
      <NGridItem :span="12">
        <NDataTable
          :data="positions"
          :columns="columns"
          :max-height="250"
          size="small"
        />
      </NGridItem>
    </NGrid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, h } from "vue";
import { NGrid, NGridItem, NDataTable, NProgress } from "naive-ui";
import * as echarts from "echarts";

interface Position {
  symbol: string;
  name: string;
  ratio: number;
  industry: string;
}

const props = defineProps<{
  positions: Position[];
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const getProgressColor = (percentage: number) => {
  if (percentage > 15) return "#f56c6c";
  if (percentage > 10) return "#e6a23c";
  if (percentage > 5) return "#5cb87a";
  return "#909399";
};

const columns = [
  { key: "symbol", title: "代码", width: 80 },
  { key: "name", title: "名称", width: 100 },
  {
    key: "ratio",
    title: "占比",
    render: (row: Position) => {
      return h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h(NProgress, {
            percentage: row.ratio,
            color: getProgressColor(row.ratio),
            showIndicator: false,
            style: { flex: 1 },
          }),
          h("span", `${row.ratio}%`),
        ],
      );
    },
  },
  { key: "industry", title: "行业" },
];

const initChart = () => {
  if (!chartRef.value || !props.positions.length) return;
  if (chartInstance) chartInstance.dispose();
  chartInstance = echarts.init(chartRef.value);

  const industryMap: Record<string, number> = {};
  props.positions.forEach((pos) => {
    if (!industryMap[pos.industry]) industryMap[pos.industry] = 0;
    industryMap[pos.industry] += pos.ratio;
  });

  const data = Object.keys(industryMap).map((industry) => ({
    name: industry,
    value: industryMap[industry],
  }));

  chartInstance.setOption({
    tooltip: { trigger: "item", formatter: "{a} <br/>{b}: {c}%" },
    legend: {
      orient: "vertical",
      right: 10,
      top: "center",
      formatter: (name: string) => {
        const val = data.find((d) => d.name === name)?.value || 0;
        return `${name}: ${val.toFixed(1)}%`;
      },
    },
    series: [
      {
        name: "持仓分布",
        type: "pie",
        radius: ["40%", "70%"],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: "#fff", borderWidth: 2 },
        label: { show: false, position: "center" },
        emphasis: { label: { show: true, fontSize: "14", fontWeight: "bold" } },
        labelLine: { show: false },
        data,
      },
    ],
  });

  window.addEventListener("resize", handleResize);
};

const handleResize = () => chartInstance?.resize();

onMounted(() => {
  if (props.positions.length > 0) initChart();
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chartInstance?.dispose();
});

watch(
  () => props.positions,
  () => {
    setTimeout(initChart, 100);
  },
);
</script>

<style scoped>
.position-distribution {
  height: 100%;
}
.empty {
  height: 250px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--n-text-color-3);
}
</style>
