<!--K线图组件-->
<template>
  <div ref="chart" class="kline-chart"></div>
</template>

<script>
import * as echarts from 'echarts';
import 'echarts/extension/bmap/bmap';

export default {
  props: {
    data: {
      type: Array,
      required: true
    },
    period: {
      type: String,
      default: 'day'
    },
    indicators: {
      type: Array,
      default: () => ['MA5', 'MA10', 'VOL']
    }
  },
  data() {
    return {
      chart: null
    }
  },
  watch: {
    data: {
      deep: true,
      handler() {
        this.updateChart();
      }
    },
    period() {
      this.updateChart();
    },
    indicators() {
      this.updateChart();
    }
  },
  mounted() {
    this.initChart();
    window.addEventListener('resize', this.resizeHandler);
  },
  beforeUnmount() {
    if (this.chart) {
      this.chart.dispose();
    }
    window.removeEventListener('resize', this.resizeHandler);
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
      if (!this.chart || !this.data.length) return;

      const option = this.generateOption();
      this.chart.setOption(option);
    },
    generateOption() {
      return {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          },
          backgroundColor: 'rgba(32, 33, 36, 0.8)',
          borderWidth: 0,
          textStyle: {
            color: '#fff'
          },
          formatter: params => {
            const data = params[0].data;
            return `
              <div>日期: ${data[0]}</div>
              <div>开盘: ${data[1]}</div>
              <div>收盘: ${data[2]}</div>
              <div>最低: ${data[3]}</div>
              <div>最高: ${data[4]}</div>
              <div>成交量: ${data[5]}</div>
            `;
          }
        },
        grid: [
          { left: '10%', right: '10%', height: '60%' },
          { left: '10%', right: '10%', top: '75%', height: '15%' }
        ],
        xAxis: [
          {
            type: 'category',
            data: this.data.map(d => d.date),
            scale: true,
            axisLine: { onZero: false },
            axisLabel: {
              formatter: value => {
                return this.$options.filters.dateFormat(value, this.period === 'day' ? 'MM-dd' : 'HH:mm');
              }
            }
          },
          {
            type: 'category',
            gridIndex: 1,
            data: this.data.map(d => d.date),
            scale: true,
            axisLabel: { show: false }
          }
        ],
        yAxis: [
          {
            scale: true,
            splitArea: { show: true }
          },
          {
            scale: true,
            gridIndex: 1,
            splitNumber: 2,
            axisLabel: { show: false }
          }
        ],
        dataZoom: [
          {
            type: 'inside',
            xAxisIndex: [0, 1],
            start: 70,
            end: 100
          },
          {
            show: true,
            xAxisIndex: [0, 1],
            type: 'slider',
            bottom: 10,
            start: 70,
            end: 100
          }
        ],
        series: [
          {
            name: 'K线',
            type: 'candlestick',
            data: this.data.map(d => [d.open, d.close, d.low, d.high]),
            itemStyle: {
              color: '#ef232a',
              color0: '#14b143',
              borderColor: '#ef232a',
              borderColor0: '#14b143'
            }
          },
          ...this.generateIndicatorSeries()
        ]
      };
    },
    generateIndicatorSeries() {
      const series = [];

      if (this.indicators.includes('MA5')) {
        series.push({
          name: 'MA5',
          type: 'line',
          data: this.calculateMA(5),
          smooth: true,
          lineStyle: { width: 1 },
          symbol: 'none'
        });
      }

      if (this.indicators.includes('MA10')) {
        series.push({
          name: 'MA10',
          type: 'line',
          data: this.calculateMA(10),
          smooth: true,
          lineStyle: { width: 1 },
          symbol: 'none'
        });
      }

      if (this.indicators.includes('VOL')) {
        series.push({
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: this.data.map(d => d.volume),
          itemStyle: {
            color: function(params) {
              const data = params.data;
              return data[1] > data[0] ? '#ef232a' : '#14b143';
            }
          }
        });
      }

      return series;
    },
    calculateMA(dayCount) {
      const result = [];
      for (let i = 0; i < this.data.length; i++) {
        if (i < dayCount) {
          result.push('-');
          continue;
        }
        let sum = 0;
        for (let j = 0; j < dayCount; j++) {
          sum += this.data[i - j].close;
        }
        result.push(+(sum / dayCount).toFixed(2));
      }
      return result;
    }
  }
}
</script>

<style scoped>
.kline-chart {
  width: 100%;
  height: 600px;
}
</style>