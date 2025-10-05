<template>
  <div class="drawdown-comparison">
    <div ref="chart" class="chart-container"></div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

export default {
  name: 'DrawdownComparison',
  props: {
    data: {
      type: Array,
      default: () => []
    }
  },
  setup(props) {
    const chart = ref(null)
    let chartInstance = null

    const initChart = () => {
      if (!chart.value) return

      chartInstance = echarts.init(chart.value)

      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        legend: {
          data: props.data.map(item => item.strategyName)
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: props.data.map(item => item.strategyName)
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            formatter: '{value}%'
          }
        },
        series: [
          {
            name: '最大回撤',
            type: 'bar',
            data: props.data.map(item => (item.maxDrawdown || 0) * 100),
            itemStyle: {
              color: '#ff4d4f'
            }
          }
        ]
      }

      chartInstance.setOption(option)
    }

    const resizeChart = () => {
      if (chartInstance) {
        chartInstance.resize()
      }
    }

    onMounted(() => {
      initChart()
      window.addEventListener('resize', resizeChart)
    })

    watch(() => props.data, () => {
      if (chartInstance) {
        initChart()
      }
    })

    return {
      chart
    }
  }
}
</script>

<style scoped>
.drawdown-comparison {
  width: 100%;
  height: 300px;
}

.chart-container {
  width: 100%;
  height: 100%;
}
</style>