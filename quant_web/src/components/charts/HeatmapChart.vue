<!--热力图组件-->
<template>
  <div ref="chart" class="heatmap-chart"></div>
</template>

<script>
import * as echarts from "echarts";

export default {
  name: "HeatmapChart",
  props: {
    matrixData: {
      type: Array,
      default: () => [],
    },
    rowLabels: {
      type: Array,
      default: () => [],
    },
    colLabels: {
      type: Array,
      default: () => [],
    },
    title: {
      type: String,
      default: "风险矩阵",
    },
  },
  data() {
    return {
      chart: null,
    };
  },
  watch: {
    matrixData: {
      deep: true,
      handler() {
        this.updateChart();
      },
    },
  },
  mounted() {
    this.initChart();
    window.addEventListener("resize", this.resizeHandler);
  },
  beforeUnmount() {
    if (this.chart) {
      this.chart.dispose();
    }
    window.removeEventListener("resize", this.resizeHandler);
  },
  methods: {
    initChart() {
      this.chart = echarts.init(this.$refs.chart);
      this.updateChart();
    },
    resizeHandler() {
      this.chart.resize();
    },
    updateChart() {
      if (!this.chart || !this.matrixData.length) return;

      const data = [];
      for (let i = 0; i < this.rowLabels.length; i++) {
        for (let j = 0; j < this.colLabels.length; j++) {
          data.push([j, i, this.matrixData[i][j] || 0]);
        }
      }

      const option = {
        title: {
          text: this.title,
          left: "center",
        },
        tooltip: {
          position: "top",
          formatter: (params) => {
            return `${this.rowLabels[params.value[1]]} vs ${this.colLabels[params.value[0]]}<br/>
                    值: ${params.value[2].toFixed(4)}`;
          },
        },
        grid: {
          left: "10%",
          right: "10%",
          bottom: "15%",
          top: "18%",
        },
        xAxis: {
          type: "category",
          data: this.colLabels,
          splitArea: {
            show: true,
          },
        },
        yAxis: {
          type: "category",
          data: this.rowLabels,
          splitArea: {
            show: true,
          },
        },
        visualMap: {
          min: -1,
          max: 1,
          calculable: true,
          orient: "horizontal",
          left: "center",
          bottom: "0%",
          textStyle: {
            color: "#333",
          },
          inRange: {
            color: [
              "#313695",
              "#4575b4",
              "#74add1",
              "#abd9e9",
              "#e0f3f8",
              "#ffffbf",
              "#fee090",
              "#fdae61",
              "#f46d43",
              "#d73027",
              "#a50026",
            ],
          },
        },
        series: [
          {
            name: "相关性",
            type: "heatmap",
            data: data,
            label: {
              show: true,
              formatter: (params) => params.value[2].toFixed(2),
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(0, 0, 0, 0.5)",
              },
            },
          },
        ],
      };

      this.chart.setOption(option);
    },
  },
};
</script>

<style scoped>
.heatmap-chart {
  width: 100%;
  height: 500px;
}
</style>
