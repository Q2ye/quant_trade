<template>
  <div class="multi-strategy-chart">
    <div ref="chart" class="chart-container"></div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";

export default {
  name: "MultiStrategyChart",
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  setup(props) {
    const chart = ref(null);
    let chartInstance = null;

    const initChart = () => {
      if (!chart.value) return;
      if (chartInstance) {
        chartInstance.dispose();
        chartInstance = null;
      }
      chartInstance = echarts.init(chart.value);

      const option = {
        tooltip: {
          trigger: "axis",
          axisPointer: {
            type: "cross",
          },
        },
        legend: {
          data: props.data.map((item) => item.strategyName),
        },
        grid: {
          left: "3%",
          right: "4%",
          bottom: "3%",
          containLabel: true,
        },
        xAxis: {
          type: "category",
          boundaryGap: false,
          data: props.data.length > 0 ? props.data[0].dates : [],
        },
        yAxis: {
          type: "value",
          axisLabel: {
            formatter: "{value}",
          },
        },
        series: props.data.map((item) => ({
          name: item.strategyName,
          type: "line",
          data: item.equityCurve,
          smooth: true,
          lineStyle: {
            width: 2,
          },
        })),
      };

      chartInstance.setOption(option);
    };

    const resizeChart = () => {
      if (chartInstance) {
        chartInstance.resize();
      }
    };

    onMounted(() => {
      initChart();
      window.addEventListener("resize", resizeChart);
    });

    onUnmounted(() => {
      window.removeEventListener("resize", resizeChart);
      if (chartInstance) {
        chartInstance.dispose();
        chartInstance = null;
      }
    });

    watch(
      () => props.data,
      () => {
        if (chartInstance) {
          initChart();
        }
      },
    );

    return {
      chart,
    };
  },
};
</script>

<style scoped>
.multi-strategy-chart {
  width: 100%;
  height: 400px;
}

.chart-container {
  width: 100%;
  height: 100%;
}
</style>
