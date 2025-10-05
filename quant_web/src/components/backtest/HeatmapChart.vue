<template>
  <div class="heatmap-chart">
    <div ref="chart" class="chart-container"></div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

export default {
  name: 'HeatmapChart',
  props: {
    data: {
      type: Object,
      default: () => ({})
    }
  },
  setup(props) {
    const chart = ref(null)
    let chartInstance = null

    const initChart = () => {
      if (!chart.value || !props.data.heatmapData) return

      chartInstance = echarts.init(chart.value)

      const { heatmapData, xAxis, yAxis } = props.data

      const option = {
        tooltip: {
          position: 'top',
          formatter: function (params) {
            return `${params.data[0]}: ${params.data[1]}<br/>值: ${params.data[2]}`
          }
        },
        grid: {
          height: '50%',
          top: '10%'
        },
        xAxis: {
          type: 'category',
          data: xAxis,
          splitArea: {
            show: true
          }
        },
        yAxis: {
          type: 'category',
          data: yAxis,
          splitArea: {
            show: true
          }
        },
        visualMap: {
          min: 0,
          max: 1,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: '0%'
        },
        series: [{
          name: '参数优化',
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: true
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }]
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
.heatmap-chart {
  width: 100%;
  height: 400px;
}

.chart-container {
  width: 100%;
  height: 100%;
}
</style>