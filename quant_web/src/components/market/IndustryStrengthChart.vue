<template>
  <div class="industry-strength-chart">
    <div class="chart-controls">
      <el-radio-group v-model="timeRange" size="small" @change="updateChart">
        <el-radio-button label="5d">5日</el-radio-button>
        <el-radio-button label="20d">20日</el-radio-button>
        <el-radio-button label="60d">60日</el-radio-button>
      </el-radio-group>
    </div>
    <div ref="chartRef" style="height: 400px;"></div>
  </div>
</template>

<script setup>
import {ref, onMounted, watch, nextTick, onUnmounted} from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  }
})

const chartRef = ref(null)
const timeRange = ref('20d')
let chart = null

const updateChart = () => {
  if (!chart || !props.data.length) return

  const fieldMap = {
    '5d': 'change5d',
    '20d': 'change20d',
    '60d': 'change60d'
  }

  const currentField = fieldMap[timeRange.value]
  const sortedData = [...props.data].sort((a, b) => b[currentField] - a[currentField])

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: function(params) {
        const data = params[0]
        return `
          <div style="font-weight: bold; margin-bottom: 5px;">${data.name}</div>
          <div>5日涨跌幅: ${props.data.find(d => d.industry === data.name)?.change5d.toFixed(2)}%</div>
          <div>20日涨跌幅: ${props.data.find(d => d.industry === data.name)?.change20d.toFixed(2)}%</div>
          <div>60日涨跌幅: ${props.data.find(d => d.industry === data.name)?.change60d.toFixed(2)}%</div>
        `
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value}%'
      },
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    yAxis: {
      type: 'category',
      data: sortedData.map(item => item.industry),
      axisLabel: {
        fontSize: 12
      }
    },
    series: [
      {
        name: '涨跌幅',
        type: 'bar',
        data: sortedData.map(item => ({
          value: item[currentField],
          itemStyle: {
            color: item[currentField] >= 0 ? '#e74c3c' : '#2ecc71'
          }
        })),
        label: {
          show: true,
          position: 'right',
          formatter: '{c}%',
          color: '#333'
        },
        emphasis: {
          focus: 'series',
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }

  chart.setOption(option, true)
}

const initChart = () => {
  if (!chartRef.value) return

  chart = echarts.init(chartRef.value)
  updateChart()
}

// 监听数据变化
watch(() => props.data, () => {
  nextTick(() => {
    if (chart) {
      updateChart()
    }
  })
}, { deep: true })

onMounted(() => {
  initChart()

  // 响应式调整
  const resizeHandler = () => {
    chart?.resize()
  }

  window.addEventListener('resize', resizeHandler)
})

// 清理
onUnmounted(() => {
  if (chart) {
    chart.dispose()
  }
})
</script>

<style scoped>
.industry-strength-chart {
  width: 100%;
  position: relative;
}

.chart-controls {
  position: absolute;
  top: 10px;
  right: 20px;
  z-index: 10;
}
</style>