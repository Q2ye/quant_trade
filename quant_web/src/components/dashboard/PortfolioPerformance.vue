<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePerformanceStore } from '@/store/modules/performance'
import { useChart } from '@/composables/useChart'

const performanceStore = usePerformanceStore()
const chartRef = ref<HTMLDivElement>()

interface PerformanceData {
  date: string
  portfolio: number
  benchmark: number
}

const performanceData = ref<PerformanceData[]>([])
const currentReturn = ref(0)
const maxDrawdown = ref(0)
const sharpeRatio = ref(0)

onMounted(async () => {
  await loadPerformanceData()
  initChart()
})

const loadPerformanceData = async () => {
  const data = await performanceStore.fetchPortfolioPerformance()
  performanceData.value = data.curve
  currentReturn.value = data.currentReturn
  maxDrawdown.value = data.maxDrawdown
  sharpeRatio.value = data.sharpeRatio
}

const initChart = () => {
  if (!chartRef.value) return

  const chart = useChart(chartRef.value, {
    title: { text: '组合净值曲线' },
    tooltip: { trigger: 'axis' },
    legend: { data: ['组合净值', '基准指数'] },
    xAxis: {
      type: 'category',
      data: performanceData.value.map(d => d.date)
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: '组合净值',
        type: 'line',
        data: performanceData.value.map(d => d.portfolio),
        smooth: true,
        lineStyle: { color: '#5470c6' }
      },
      {
        name: '基准指数',
        type: 'line',
        data: performanceData.value.map(d => d.benchmark),
        smooth: true,
        lineStyle: { color: '#91cc75' }
      }
    ]
  })
}
</script>

<template>
  <div class="portfolio-performance">
    <div class="header">
      <h3>组合绩效分析</h3>
    </div>

    <div class="performance-metrics">
      <div class="metric-item">
        <div class="metric-label">当前收益</div>
        <div class="metric-value" :class="{ positive: currentReturn > 0, negative: currentReturn < 0 }">
          {{ (currentReturn * 100).toFixed(2) }}%
        </div>
      </div>

      <div class="metric-item">
        <div class="metric-label">最大回撤</div>
        <div class="metric-value negative">
          {{ (maxDrawdown * 100).toFixed(2) }}%
        </div>
      </div>

      <div class="metric-item">
        <div class="metric-label">夏普比率</div>
        <div class="metric-value">
          {{ sharpeRatio.toFixed(2) }}
        </div>
      </div>
    </div>

    <div ref="chartRef" class="performance-chart"></div>
  </div>
</template>

<style scoped>
.portfolio-performance {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
  height: 100%;
}

.header {
  margin-bottom: 20px;
}

.performance-metrics {
  display: flex;
  justify-content: space-around;
  margin-bottom: 20px;
}

.metric-item {
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: bold;
}

.metric-value.positive {
  color: #f56c6c;
}

.metric-value.negative {
  color: #67c23a;
}

.performance-chart {
  height: 300px;
}
</style>