<!--技术指标图表-->
<template>
  <div ref="chart" class="net-value-chart"></div>
</template>

<script>
import * as echarts from "echarts";

export default {
  name: "NetValueChart",
  props: {
    netValueData: {
      type: Array,
      default: () => [],
    },
    benchmarkData: {
      type: Array,
      default: () => [],
    },
    period: {
      type: String,
      default: "1y",
    },
  },
  data() {
    return {
      chart: null,
    };
  },
  watch: {
    netValueData: {
      deep: true,
      handler() {
        this.updateChart();
      },
    },
    benchmarkData: {
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
      if (!this.chart || !this.netValueData.length) return;

      const option = {
        tooltip: {
          trigger: "axis",
          formatter: (params) => {
            const strategy = params[0];
            const benchmark = params[1] || { value: 0 };
            return `
              <div>日期: ${strategy.name}</div>
              <div>策略净值: ${strategy.value.toFixed(4)}</div>
              <div>基准收益: ${benchmark.value ? (benchmark.value * 100).toFixed(2) + "%" : "N/A"}</div>
              <div>超额收益: ${benchmark.value ? (strategy.value - benchmark.value * 100).toFixed(2) + "%" : "N/A"}</div>
            `;
          },
        },
        legend: {
          data: ["策略净值", "基准收益"],
          bottom: 10,
        },
        grid: {
          left: "3%",
          right: "4%",
          bottom: "15%",
          top: "10%",
          containLabel: true,
        },
        xAxis: {
          type: "category",
          boundaryGap: false,
          data: this.netValueData.map((d) => d.date),
        },
        yAxis: [
          {
            type: "value",
            name: "净值",
            min: (value) => Math.min(value.min, 0.9),
            axisLabel: {
              formatter: "{value}",
            },
          },
          {
            type: "value",
            name: "收益率",
            min: -0.3,
            max: 0.3,
            axisLabel: {
              formatter: (value) => (value * 100).toFixed(0) + "%",
            },
          },
        ],
        dataZoom: [
          {
            type: "inside",
            start: 70,
            end: 100,
          },
          {
            show: true,
            type: "slider",
            bottom: 25,
            start: 70,
            end: 100,
          },
        ],
        series: [
          {
            name: "策略净值",
            type: "line",
            smooth: true,
            symbol: "none",
            data: this.netValueData.map((d) => d.value),
            lineStyle: {
              width: 3,
              color: "#5470C6",
            },
          },
          {
            name: "基准收益",
            type: "line",
            yAxisIndex: 1,
            smooth: true,
            symbol: "none",
            data: this.benchmarkData,
            lineStyle: {
              width: 2,
              type: "dashed",
              color: "#91CC75",
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
.net-value-chart {
  width: 100%;
  height: 500px;
}
</style>
