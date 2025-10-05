<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useChart } from '@/composables/useChart'
import { useStrategyStore } from '@/store/modules/strategy'

const strategyStore = useStrategyStore()

// 策略对比数据
interface StrategyResult {
  id: string
  name: string
  annualReturn: number
  sharpeRatio: number
  maxDrawdown: number
  volatility: number
  winRate: number
  profitFactor: number
  totalTrades: number
  equityCurve: Array<{ date: string; value: number }>
}

const strategies = ref<StrategyResult[]>([])
const selectedStrategies = ref<string[]>([])
const compareMetrics = ref(['annualReturn', 'sharpeRatio', 'maxDrawdown'])
const chartRef = ref<HTMLDivElement>()

// 可对比的指标
const availableMetrics = [
  { value: 'annualReturn', label: '年化收益率', format: 'percent' },
  { value: 'sharpeRatio', label: '夏普比率', format: 'number' },
  { value: 'maxDrawdown', label: '最大回撤', format: 'percent' },
  { value: 'volatility', label: '波动率', format: 'percent' },
  { value: 'winRate', label: '胜率', format: 'percent' },
  { value: 'profitFactor', label: '盈利因子', format: 'number' },
  { value: 'totalTrades', label: '交易次数', format: 'number' }
]

// 加载策略回测结果
const loadStrategyResults = async () => {
  const results = await strategyStore.getStrategyBacktestResults()
  strategies.value = results
  // 默认选择前3个策略进行对比
  selectedStrategies.value = results.slice(0, 3).map(s => s.id)
}

// 过滤选中的策略
const selectedStrategyData = computed(() => {
  return strategies.value.filter(s => selectedStrategies.value.includes(s.id))
})

// 初始化对比图表
const initComparisonChart = () => {
  if (!chartRef.value || selectedStrategyData.value.length === 0) return

  const chart = useChart(chartRef.value, {
    title: { text: '策略净值曲线对比' },
    tooltip: { trigger: 'axis' },
    legend: {
      data: selectedStrategyData.value.map(s => s.name),
      bottom: 0
    },
    grid: { top: 50, right: 50, bottom: 50, left: 50 },
    xAxis: {
      type: 'time',
      axisLabel: { formatter: '{yyyy}-{MM}-{dd}' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}' },
      scale: true
    },
    series: selectedStrategyData.value.map(strategy => ({
      name: strategy.name,
      type: 'line',
      data: strategy.equityCurve.map(point => [point.date, point.value]),
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 }
    }))
  })
}

// 生成雷达图数据
const radarChartData = computed(() => {
  const indicators = compareMetrics.value.map(metric => {
    const metricInfo = availableMetrics.find(m => m.value === metric)
    return { name: metricInfo?.label || metric, max: getMaxValue(metric) }
  })

  const seriesData = selectedStrategyData.value.map(strategy => ({
    name: strategy.name,
    value: compareMetrics.value.map(metric => {
      const value = strategy[metric as keyof StrategyResult] as number
      return metric.includes('Drawdown') ? value * -1 : value
    })
  }))

  return { indicators, seriesData }
})

// 获取指标最大值
const getMaxValue = (metric: string) => {
  const values = selectedStrategyData.value.map(s =>
    s[metric as keyof StrategyResult] as number
  )
  const max = Math.max(...values)

  switch (metric) {
    case 'annualReturn': return Math.max(max * 1.2, 0.5)
    case 'sharpeRatio': return Math.max(max * 1.2, 3)
    case 'maxDrawdown': return Math.max(max * 1.2, 0.3)
    case 'volatility': return Math.max(max * 1.2, 0.4)
    case 'winRate': return 1
    case 'profitFactor': return Math.max(max * 1.2, 5)
    case 'totalTrades': return Math.max(max * 1.2, 1000)
    default: return max * 1.2
  }
}

// 格式化数值显示
const formatValue = (value: number, format: string) => {
  switch (format) {
    case 'percent': return (value * 100).toFixed(2) + '%'
    case 'number': return value.toFixed(2)
    default: return value.toString()
  }
}

// 导出对比报告
const exportComparison = () => {
  const report = {
    comparedStrategies: selectedStrategyData.value.map(s => s.name),
    metrics: compareMetrics.value,
    data: selectedStrategyData.value
  }

  // 实现导出逻辑
  console.log('导出对比报告:', report)
}

onMounted(async () => {
  await loadStrategyResults()
  initComparisonChart()
})
</script>

<template>
  <div class="multi-strategy-compare">
    <div class="compare-header">
      <h3>多策略对比分析</h3>
      <div class="header-actions">
        <el-button size="small" @click="exportComparison">导出报告</el-button>
      </div>
    </div>

    <div class="compare-controls">
      <!-- 策略选择 -->
      <div class="control-section">
        <span class="control-label">选择策略:</span>
        <el-checkbox-group v-model="selectedStrategies">
          <el-checkbox
            v-for="strategy in strategies"
            :key="strategy.id"
            :label="strategy.id"
          >
            {{ strategy.name }}
          </el-checkbox>
        </el-checkbox-group>
      </div>

      <!-- 指标选择 -->
      <div class="control-section">
        <span class="control-label">对比指标:</span>
        <el-checkbox-group v-model="compareMetrics">
          <el-checkbox
            v-for="metric in availableMetrics"
            :key="metric.value"
            :label="metric.value"
          >
            {{ metric.label }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
    </div>

    <!-- 净值曲线对比 -->
    <div class="chart-section">
      <h4>净值曲线对比</h4>
      <div ref="chartRef" class="comparison-chart"></div>
    </div>

    <!-- 指标对比表格 -->
    <div class="metrics-table">
      <h4>策略指标对比</h4>
      <el-table :data="selectedStrategyData" stripe>
        <el-table-column prop="name" label="策略名称" fixed />
        <el-table-column
          v-for="metric in compareMetrics"
          :key="metric"
          :label="availableMetrics.find(m => m.value === metric)?.label"
        >
          <template #default="{ row }">
            {{ formatValue(row[metric], availableMetrics.find(m => m.value === metric)?.format || 'number') }}
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 雷达图对比 -->
    <div class="radar-section" v-if="compareMetrics.length >= 3">
      <h4>综合能力雷达图</h4>
      <div class="radar-chart">
        <!-- 这里可以集成雷达图组件 -->
        <div class="radar-placeholder">
          雷达图展示区域 - 需要集成ECharts雷达图
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.multi-strategy-compare {
  padding: 20px;
  background: var(--el-bg-color);
  min-height: 100%;
}

.compare-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color);
}

.compare-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 30px;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.control-section {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.control-label {
  font-weight: bold;
  min-width: 80px;
  padding-top: 4px;
}

.chart-section {
  margin-bottom: 30px;
}

.chart-section h4 {
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.comparison-chart {
  height: 400px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
}

.metrics-table {
  margin-bottom: 30px;
}

.metrics-table h4 {
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.radar-section h4 {
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.radar-chart {
  height: 300px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.radar-placeholder {
  color: var(--el-text-color-secondary);
  font-size: 16px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .compare-controls {
    flex-direction: column;
    gap: 16px;
  }

  .control-section {
    flex-direction: column;
    align-items: flex-start;
  }

  .control-label {
    margin-bottom: 8px;
  }
}
</style>