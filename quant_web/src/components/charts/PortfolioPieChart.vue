<!--投资组合饼图-->
<template>
  <div ref="chart" class="portfolio-pie-chart"></div>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: "PortfolioPieChart",
  props: {
    portfolioData: {
      type: Array,
      default: () => []
    },
    title: {
      type: String,
      default: '投资组合分布'
    }
  },
  data() {
    return {
      chart: null
    }
  },
  watch: {
    portfolioData: {
      deep: true,
      handler() {
        this.updateChart();
      }
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
      if (!this.chart || !this.portfolioData.length) return;

      const option = {
        title: {
          text: this.title,
          left: 'center',
          top: 10
        },
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)'
        },
        legend: {
          orient: 'vertical',
          right: 10,
          top: 'center',
          formatter: name => {
            const item = this.portfolioData.find(d => d.name === name);
            return `${name} ${item ? item.value + '%' : ''}`;
          }
        },
        series: [
          {
            name: '持仓分布',
            type: 'pie',
            radius: ['35%', '65%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 10,
              borderColor: '#fff',
              borderWidth: 2
            },
            label: {
              show: true,
              formatter: '{b}: {d}%'
            },
            emphasis: {
              label: {
                show: true,
                fontSize: '16',
                fontWeight: 'bold'
              }
            },
            labelLine: {
              show: true
            },
            data: this.portfolioData
          }
        ]
      };

      this.chart.setOption(option);
    }
  }
}
</script>

<style scoped>
.portfolio-pie-chart {
  width: 100%;
  height: 400px;
}
</style>