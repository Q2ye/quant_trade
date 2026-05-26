<template>
  <div ref="chartRef" class="monthly-return-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps<{ data: Array<{ month: string; return: number }> }>();

const chartRef = ref<HTMLElement>();
const instance = ref<any>(null);

const resizeChart = () => instance.value?.resize();

const initChart = () => {
  if (!chartRef.value || !props.data?.length) return;
  if (instance.value) instance.value.dispose();
  instance.value = echarts.init(chartRef.value);
  const months = props.data.map((d) => d.month);
  const values = props.data.map((d) => d.return * 100);
  instance.value.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: { type: "category", data: months },
    yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    series: [
      {
        type: "bar",
        data: values,
        itemStyle: {
          color: (params: any) => (params.value >= 0 ? "#67c23a" : "#f56c6c"),
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
.monthly-return-chart {
  width: 100%;
  height: 300px;
}
</style>
