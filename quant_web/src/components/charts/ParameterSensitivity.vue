<template>
  <div ref="chartRef" class="parameter-sensitivity-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps<{
  data: { params: string[]; metrics: string[]; data: number[][][] };
}>();

const chartRef = ref<HTMLElement>();
const instance = ref<any>(null);

const resizeChart = () => instance.value?.resize();

const initChart = () => {
  if (!chartRef.value || !props.data?.params?.length) return;
  if (instance.value) instance.value.dispose();
  instance.value = echarts.init(chartRef.value);
  instance.value.setOption({
    title: { text: "参数敏感性分析", left: "center" },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: props.data.params },
    yAxis: { type: "value" },
    series: props.data.metrics.map((m, i) => ({
      name: m,
      type: "line",
      data: (props.data.data?.[i] || []).map((d: any) => d?.[0] ?? 0),
      smooth: true,
    })),
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
.parameter-sensitivity-chart {
  width: 100%;
  height: 300px;
}
</style>
