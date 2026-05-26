<template>
  <div ref="chartRef" class="profit-distribution-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps<{ data: { bins: number[]; counts: number[] } }>();

const chartRef = ref<HTMLElement>();
const instance = ref<any>(null);

const resizeChart = () => instance.value?.resize();

const initChart = () => {
  if (!chartRef.value || !props.data) return;
  if (instance.value) instance.value.dispose();
  instance.value = echarts.init(chartRef.value);
  instance.value.setOption({
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: props.data.bins.map((b) => `${(b * 100).toFixed(0)}%`),
    },
    yAxis: { type: "value" },
    series: [
      { type: "bar", data: props.data.counts, itemStyle: { color: "#5470c6" } },
    ],
  });
};

onMounted(() => {
  initChart();
  window.addEventListener("resize", resizeChart);
});
onUnmounted(() => {
  window.removeEventListener("resize", resizeChart);
  instance.value?.dispose();
});
watch(() => props.data, initChart);
</script>

<style scoped>
.profit-distribution-chart {
  width: 100%;
  height: 300px;
}
</style>
