<template>
  <div class="strategy-performance">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">策略绩效</h1>
      <div class="header-actions">
        <el-select v-model="selectedStrategy" placeholder="选择策略" style="width: 200px">
          <el-option
            v-for="strategy in strategyList"
            :key="strategy.id"
            :label="strategy.name"
            :value="strategy.id"
          />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 240px; margin-left: 10px"
        />
        <el-button type="primary" @click="loadPerformanceData">
          <el-icon><Icon icon="ep:search" /></el-icon>
          查询
        </el-button>
        <el-button @click="exportReport">
          <el-icon><Icon icon="ep:download" /></el-icon>
          导出报告
        </el-button>
      </div>
    </div>

    <!-- 绩效概览 -->
    <el-row :gutter="16" class="performance-overview">
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-value" :class="getReturnClass(performance.totalReturn)">
              {{ formatPercent(performance.totalReturn) }}
            </div>
            <div class="metric-label">累计收益</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-value">{{ performance.annualReturn ? formatPercent(performance.annualReturn) : '--' }}</div>
            <div class="metric-label">年化收益</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-value" :class="getDrawdownClass(performance.maxDrawdown)">
              {{ formatPercent(performance.maxDrawdown) }}
            </div>
            <div class="metric-label">最大回撤</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-value">{{ performance.sharpeRatio ? performance.sharpeRatio.toFixed(2) : '--' }}</div>
            <div class="metric-label">夏普比率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 绩效图表 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="chart-header">
              <span>净值曲线</span>
              <el-radio-group v-model="chartType" size="small">
                <el-radio-button label="cumulative">累计收益</el-radio-button>
                <el-radio-button label="daily">每日收益</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="equityChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="chart-header">
              <span>回撤分析</span>
            </div>
          </template>
          <div ref="drawdownChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细指标 -->
    <el-card class="metrics-card">
      <template #header>
        <span>详细绩效指标</span>
      </template>

      <el-table :data="performanceMetrics" v-loading="loading">
        <el-table-column prop="metric" label="指标名称" width="200" />
        <el-table-column prop="value" label="数值" width="150">
          <template #default="{ row }">
            <span :class="getMetricClass(row.metric, row.value)">
              {{ formatMetricValue(row.metric, row.value) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" />
        <el-table-column prop="benchmark" label="基准" width="150">
          <template #default="{ row }">
            {{ formatMetricValue(row.metric, row.benchmark) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 月度收益热力图 -->
    <el-card class="heatmap-card">
      <template #header>
        <span>月度收益热力图</span>
      </template>
      <div ref="heatmapChart" class="chart-container" style="height: 400px;"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'

// 响应式数据
const loading = ref(false)
const selectedStrategy = ref('')
const dateRange = ref([new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), new Date()])
const chartType = ref('cumulative')
const equityChart = ref(null)
const drawdownChart = ref(null)
const heatmapChart = ref(null)

const strategyList = ref([
  { id: '1', name: '双均线策略' },
  { id: '2', name: '动量反转策略' },
  { id: '3', name: '均值回归策略' }
])

const performance = reactive({
  totalReturn: 0.1542,
  annualReturn: 0.2345,
  maxDrawdown: -0.0876,
  sharpeRatio: 1.23,
  winRate: 0.634,
  profitFactor: 1.89
})

const performanceMetrics = ref([
  { metric: '累计收益率', value: 0.1542, description: '策略从开始到现在的总收益率', benchmark: 0.1023 },
  { metric: '年化收益率', value: 0.2345, description: '折算成年度的收益率', benchmark: 0.1567 },
  { metric: '最大回撤', value: -0.0876, description: '策略净值从最高点到最低点的最大跌幅', benchmark: -0.1234 },
  { metric: '夏普比率', value: 1.23, description: '每承受一单位风险产生的超额收益', benchmark: 0.89 },
  { metric: '索提诺比率', value: 1.89, description: '只考虑下行风险的调整后收益', benchmark: 1.23 },
  { metric: '胜率', value: 0.634, description: '盈利交易次数占总交易次数的比例', benchmark: 0.523 },
  { metric: '盈亏比', value: 1.45, description: '平均盈利与平均亏损的比例', benchmark: 1.21 },
  { metric: '利润因子', value: 1.89, description: '总盈利与总亏损的比值', benchmark: 1.34 },
  { metric: '年化波动率', value: 0.1876, description: '策略收益率的年化标准差', benchmark: 0.2345 }
])

// 方法
const getReturnClass = (returnValue) => {
  return returnValue >= 0 ? 'positive' : 'negative'
}

const getDrawdownClass = (drawdown) => {
  return drawdown <= -0.1 ? 'negative' : drawdown <= -0.05 ? 'warning' : 'positive'
}

const getMetricClass = (metric, value) => {
  if (metric.includes('回撤') || metric.includes('波动率')) {
    return value <= -0.1 ? 'negative' : value <= -0.05 ? 'warning' : 'positive'
  }
  return value >= 0 ? 'positive' : 'negative'
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return '--'
  return `${(value * 100).toFixed(2)}%`
}

const formatMetricValue = (metric, value) => {
  if (metric.includes('率') && !metric.includes('波动率')) {
    return formatPercent(value)
  }
  if (typeof value === 'number') {
    return value.toFixed(4)
  }
  return value || '--'
}

const loadPerformanceData = async () => {
  if (!selectedStrategy.value) {
    ElMessage.warning('请选择策略')
    return
  }

  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1500))
    ElMessage.success('数据加载成功')
    initCharts()
  } catch (error) {
    ElMessage.error('数据加载失败')
  } finally {
    loading.value = false
  }
}

const exportReport = () => {
  ElMessage.info('导出报告功能开发中')
}

// 图表初始化
let equityChartInstance = null
let drawdownChartInstance = null
let heatmapChartInstance = null

const initCharts = () => {
  // 净值曲线图表
  if (equityChart.value) {
    equityChartInstance = echarts.init(equityChart.value)
    const equityOption = {
      tooltip: {
        trigger: 'axis',
        formatter: function (params) {
          const date = params[0].axisValue
          const strategyValue = params[0].data
          const benchmarkValue = params[1]?.data || 0
          return `
            ${date}<br/>
            策略: ${(strategyValue * 100).toFixed(2)}%<br/>
            基准: ${(benchmarkValue * 100).toFixed(2)}%
          `
        }
      },
      legend: {
        data: ['策略净值', '基准净值']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['2023-01', '2023-02', '2023-03', '2023-04', '2023-05', '2023-06',
               '2023-07', '2023-08', '2023-09', '2023-10', '2023-11', '2023-12']
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: '{value}%'
        }
      },
      series: [
        {
          name: '策略净值',
          type: 'line',
          data: [2.1, 5.3, 8.7, 6.2, 12.4, 15.2, 13.8, 16.5, 14.2, 17.8, 15.4, 18.2],
          itemStyle: { color: '#5470c6' },
          smooth: true
        },
        {
          name: '基准净值',
          type: 'line',
          data: [1.2, 3.4, 5.6, 4.3, 8.9, 10.2, 9.8, 11.5, 10.1, 12.3, 11.2, 12.8],
          itemStyle: { color: '#91cc75' },
          smooth: true
        }
      ]
    }
    equityChartInstance.setOption(equityOption)
  }

  // 回撤分析图表
  if (drawdownChart.value) {
    drawdownChartInstance = echarts.init(drawdownChart.value)
    const drawdownOption = {
      tooltip: {
        trigger: 'axis'
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['2023-01', '2023-02', '2023-03', '2023-04', '2023-05', '2023-06',
               '2023-07', '2023-08', '2023-09', '2023-10', '2023-11', '2023-12']
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: '{value}%'
        }
      },
      series: [
        {
          name: '回撤幅度',
          type: 'line',
          data: [-1.2, -2.1, -4.3, -3.2, -5.6, -3.8, -6.2, -4.5, -3.9, -2.8, -4.1, -2.5],
          itemStyle: { color: '#ee6666' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(238, 102, 102, 0.5)' },
              { offset: 1, color: 'rgba(238, 102, 102, 0.1)' }
            ])
          }
        }
      ]
    }
    drawdownChartInstance.setOption(drawdownOption)
  }

  // 月度收益热力图
  if (heatmapChart.value) {
    heatmapChartInstance = echarts.init(heatmapChart.value)

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const years = ['2020', '2021', '2022', '2023']

    const data = []
    years.forEach((year, yIndex) => {
      months.forEach((month, mIndex) => {
        // 生成模拟数据
        const value = (Math.random() - 0.5) * 20
        data.push([mIndex, yIndex, value.toFixed(1)])
      })
    })

    const heatmapOption = {
      tooltip: {
        position: 'top',
        formatter: function (params) {
          return `${years[params.data[1]]} ${months[params.data[0]]}<br/>收益: ${params.data[2]}%`
        }
      },
      grid: {
        height: '80%',
        top: '10%'
      },
      xAxis: {
        type: 'category',
        data: months,
        splitArea: {
          show: true
        }
      },
      yAxis: {
        type: 'category',
        data: years,
        splitArea: {
          show: true
        }
      },
      visualMap: {
        min: -10,
        max: 10,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        inRange: {
          color: ['#c23531', '#d48265', '#91c7ae', '#749f83', '#ca8622', '#bda29a']
        }
      },
      series: [
        {
          name: '月度收益',
          type: 'heatmap',
          data: data,
          label: {
            show: true,
            formatter: function (params) {
              return params.data[2] + '%'
            }
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    }
    heatmapChartInstance.setOption(heatmapOption)
  }
}

// 生命周期
onMounted(() => {
  if (strategyList.value.length > 0) {
    selectedStrategy.value = strategyList.value[0].id
  }
  loadPerformanceData()
})
</script>

<style lang="scss" scoped>
.strategy-performance {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .page-title {
    margin: 0;
    color: #303133;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
}

.performance-overview {
  margin-bottom: 20px;
}

.metric-card {
  :deep(.el-card__body) {
    padding: 20px;
  }
}

.metric-content {
  text-align: center;

  .metric-value {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 8px;

    &.positive {
      color: #67c23a;
    }
    &.negative {
      color: #f56c6c;
    }
    &.warning {
      color: #e6a23c;
    }
  }

  .metric-label {
    color: #909399;
    font-size: 14px;
  }
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card {
  :deep(.el-card__header) {
    padding: 12px 20px;
  }
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  height: 300px;
}

.metrics-card,
.heatmap-card {
  margin-bottom: 20px;

  :deep(.el-card__header) {
    padding: 12px 20px;
  }
}
</style>