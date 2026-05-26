<template>
  <div ref="chartRef" class="holding-analysis-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps<{
  data: Array<{ symbol: string; name: string; weight: number; return: number }>;
}>();

const chartRef = ref<HTMLElement>();
const instance = ref<any>(null);

const resizeChart = () => instance.value?.resize();

const initChart = () => {
  if (!chartRef.value || !props.data?.length) return;
  if (instance.value) instance.value.dispose();
  instance.value = echarts.init(chartRef.value);
  instance.value.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c}%" },
    series: [
      {
        type: "pie",
        radius: ["40%", "70%"],
        data: props.data.map((d) => ({ name: d.name, value: d.weight * 100 })),
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" },
        },
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
.holding-analysis-chart {
  width: 100%;
  height: 300px;
}
</style>
