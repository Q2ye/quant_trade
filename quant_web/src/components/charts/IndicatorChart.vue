<!--技术指标图表-->
<template>
  <div ref="chart" class="indicator-chart"></div>
</template>

<script>
import * as echarts from "echarts";

export default {
  name: "IndicatorChart",
  props: {
    indicatorData: {
      type: Array,
      required: true,
    },
    indicators: {
      type: Array,
      default: () => ["MACD", "RSI", "KDJ"],
    },
  },
  data() {
    return {
      chart: null,
    };
  },
  watch: {
    indicatorData: {
      deep: true,
      handler() {
        this.updateChart();
      },
    },
    indicators() {
      this.updateChart();
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
      if (!this.chart || !this.indicatorData.length) return;

      const dates = this.indicatorData.map((d) => d.date);
      const series = [];

      // MACD指标
      if (this.indicators.includes("MACD")) {
        series.push(
          {
            name: "DIF",
            type: "line",
            data: this.indicatorData.map((d) => d.DIF),
            symbol: "none",
            lineStyle: { width: 1.5 },
          },
          {
            name: "DEA",
            type: "line",
            data: this.indicatorData.map((d) => d.DEA),
            symbol: "none",
            lineStyle: { width: 1.5 },
          },
          {
            name: "MACD",
            type: "bar",
            data: this.indicatorData.map((d) => d.MACD),
            itemStyle: {
              color: function (params) {
                return params.value >= 0 ? "#ef232a" : "#14b143";
              },
            },
          },
        );
      }

      // RSI指标
      if (this.indicators.includes("RSI")) {
        series.push(
          {
            name: "RSI6",
            type: "line",
            data: this.indicatorData.map((d) => d.RSI6),
            symbol: "none",
            lineStyle: { width: 1.5 },
          },
          {
            name: "RSI12",
            type: "line",
            data: this.indicatorData.map((d) => d.RSI12),
            symbol: "none",
            lineStyle: { width: 1.5, type: "dashed" },
          },
          {
            name: "RSI24",
            type: "line",
            data: this.indicatorData.map((d) => d.RSI24),
            symbol: "none",
            lineStyle: { width: 1.5, type: "dotted" },
          },
        );
      }

      // KDJ指标
      if (this.indicators.includes("KDJ")) {
        series.push(
          {
            name: "K",
            type: "line",
            data: this.indicatorData.map((d) => d.K),
            symbol: "none",
          },
          {
            name: "D",
            type: "line",
            data: this.indicatorData.map((d) => d.D),
            symbol: "none",
          },
          {
            name: "J",
            type: "line",
            data: this.indicatorData.map((d) => d.J),
            symbol: "none",
          },
        );
      }

      const option = {
        tooltip: {
          trigger: "axis",
          axisPointer: {
            type: "cross",
          },
        },
        legend: {
          data: series.map((s) => s.name),
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
          data: dates,
        },
        yAxis: {
          type: "value",
          scale: true,
        },
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
        series: series,
      };

      this.chart.setOption(option);
    },
  },
};
</script>

<style scoped>
.indicator-chart {
  width: 100%;
  height: 400px;
}
</style>
