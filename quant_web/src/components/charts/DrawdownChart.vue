<template>
  <div ref="chartRef" class="drawdown-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps<{ data: Array<{ date: string; value: number }> }>();

const chartRef = ref<HTMLElement>();
const instance = ref<any>(null);

const resizeChart = () => instance.value?.resize();

const initChart = () => {
  if (!chartRef.value || !props.data?.length) return;
  if (instance.value) instance.value.dispose();
  instance.value = echarts.init(chartRef.value);
  instance.value.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: { type: "category", data: props.data.map((d) => d.date) },
    yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    series: [
      {
        type: "line",
        data: props.data.map((d) => d.value),
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(238,102,102,0.5)" },
            { offset: 1, color: "rgba(238,102,102,0.1)" },
          ]),
        },
        lineStyle: { color: "#ee6666" },
      },
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
.drawdown-chart {
  width: 100%;
  height: 300px;
}
</style>
