<!-- components/Research/FactorDetailAnalysis.vue -->
<!--详细的因子分析报告，包含图表和统计数据-->
<template>
  <div class="factor-detail-analysis" v-loading="loading">
    <!-- 因子基本信息 -->
    <el-card class="factor-info">
      <template #header>
        <div class="card-header">
          <span>因子基本信息</span>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="因子名称">
          <el-tag type="primary">{{ factor.name }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="因子代码">
          <el-tag>{{ factor.code }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="因子类别">
          <el-tag :type="getCategoryTag(factor.category)">
            {{ getCategoryText(factor.category) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="factor.status === 'active' ? 'success' : 'danger'">
            {{ factor.status === 'active' ? '启用' : '停用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="数据字段" :span="2">
          <div class="data-fields">
            <el-tag
              v-for="field in factor.dataFields"
              :key="field"
              size="small"
              type="info"
            >
              {{ field }}
            </el-tag>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="因子描述" :span="2">
          {{ factor.description }}
        </el-descriptions-item>
        <el-descriptions-item label="计算公式" :span="2">
          <code class="formula-code">{{ factor.formula }}</code>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 测试结果概览 -->
    <el-row :gutter="20" class="results-overview">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="metric-card">
            <div class="metric-icon annual-return">
              <el-icon><Icon icon="mdi:chart-line" /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value positive">
                {{ formatPercent(testResults.annualReturn) }}
              </div>
              <div class="metric-label">年化收益</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover">
          <div class="metric-card">
            <div class="metric-icon sharpe">
              <el-icon><Icon icon="mdi:finance" /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value">{{ testResults.sharpeRatio.toFixed(2) }}</div>
              <div class="metric-label">夏普比率</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover">
          <div class="metric-card">
            <div class="metric-icon drawdown">
              <el-icon><Icon icon="mdi:arrow-down" /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value negative">
                {{ formatPercent(testResults.maxDrawdown) }}
              </div>
              <div class="metric-label">最大回撤</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover">
          <div class="metric-card">
            <div class="metric-icon win-rate">
              <el-icon><Icon icon="mdi:trophy" /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value">{{ formatPercent(testResults.winRate) }}</div>
              <div class="metric-label">胜率</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细分析图表 -->
    <el-row :gutter="20" class="analysis-charts">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>分组收益分析</span>
          </template>
          <div ref="groupReturnsChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>IC序列分析</span>
          </template>
          <div ref="icSeriesChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细统计表格 -->
    <el-card class="detailed-stats">
      <template #header>
        <span>详细统计指标</span>
      </template>

      <el-table :data="statisticsData" border>
        <el-table-column prop="metric" label="统计指标" width="150" />
        <el-table-column prop="value" label="数值" width="120" />
        <el-table-column prop="description" label="说明" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'

const props = defineProps({
  factor: {
    type: Object,
    required: true
  },
  testConfig: {
    type: Object,
    default: () => ({})
  },
  testResults: {
    type: Object,
    default: () => ({})
  }
})

// 响应式数据
const loading = ref(false)
const groupReturnsChart = ref(null)
const icSeriesChart = ref(null)

let groupReturnsChartInstance = null
let icSeriesChartInstance = null

// 统计指标数据
const statisticsData = computed(() => [
  { metric: '年化收益', value: formatPercent(props.testResults.annualReturn), description: '策略年化收益率' },
  { metric: '年化波动率', value: formatPercent(0.182), description: '策略年化波动率' },
  { metric: '夏普比率', value: props.testResults.sharpeRatio.toFixed(3), description: '每单位风险获得的超额收益' },
  { metric: '最大回撤', value: formatPercent(props.testResults.maxDrawdown), description: '策略最大回撤幅度' },
  { metric: '卡尔玛比率', value: (props.testResults.annualReturn / Math.abs(props.testResults.maxDrawdown)).toFixed(3), description: '年化收益与最大回撤的比率' },
  { metric: '胜率', value: formatPercent(props.testResults.winRate), description: '盈利周期占总周期比例' },
  { metric: '盈亏比', value: '1.85', description: '平均盈利与平均亏损的比率' },
  { metric: 'IC均值', value: '0.045', description: '因子与下期收益的相关性均值' },
  { metric: 'ICIR', value: '0.32', description: 'IC均值与标准差的比率' },
  { metric: '换手率', value: '2.45', description: '策略月均换手率' }
])

// 方法
const getCategoryTag = (category) => {
  const map = {
    value: 'success',
    growth: 'warning',
    quality: 'primary',
    momentum: 'danger',
    technical: 'info'
  }
  return map[category] || 'info'
}

const getCategoryText = (category) => {
  const map = {
    value: '价值因子',
    growth: '成长因子',
    quality: '质量因子',
    momentum: '动量因子',
    technical: '技术因子'
  }
  return map[category] || '其他'
}

const formatPercent = (value) => {
  return `${(value * 100).toFixed(2)}%`
}

// 初始化图表
const initCharts = () => {
  if (!groupReturnsChart.value || !icSeriesChart.value) return

  // 分组收益图表
  groupReturnsChartInstance = echarts.init(groupReturnsChart.value)
  const groupReturnsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}: {c}%'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['第1组', '第2组', '第3组', '第4组', '第5组'],
      axisLabel: {
        color: '#606266'
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value}%',
        color: '#606266'
      }
    },
    series: [
      {
        name: '分组收益',
        type: 'bar',
        data: props.testResults.groupReturns.map(v => (v * 100).toFixed(2)),
        itemStyle: {
          color: function(params) {
            const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de']
            return colors[params.dataIndex] || '#5470c6'
          }
        },
        label: {
          show: true,
          position: 'top',
          formatter: '{c}%'
        }
      }
    ]
  }
  groupReturnsChartInstance.setOption(groupReturnsOption)

  // IC序列图表
  icSeriesChartInstance = echarts.init(icSeriesChart.value)
  const icSeriesOption = {
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
      data: Array.from({ length: props.testResults.icSeries.length }, (_, i) => `周期${i + 1}`),
      axisLabel: {
        color: '#606266'
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#606266'
      }
    },
    series: [
      {
        name: 'IC序列',
        type: 'line',
        data: props.testResults.icSeries,
        smooth: true,
        lineStyle: {
          color: '#67c23a',
          width: 2
        },
        itemStyle: {
          color: '#67c23a'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
            { offset: 1, color: 'rgba(103, 194, 58, 0.1)' }
          ])
        }
      }
    ]
  }
  icSeriesChartInstance.setOption(icSeriesOption)
}

// 生命周期
onMounted(() => {
  setTimeout(() => {
    initCharts()
  }, 100)
})

onUnmounted(() => {
  if (groupReturnsChartInstance) {
    groupReturnsChartInstance.dispose()
  }
  if (icSeriesChartInstance) {
    icSeriesChartInstance.dispose()
  }
})
</script>

<style lang="scss" scoped>
.factor-detail-analysis {
  .factor-info {
    margin-bottom: 20px;

    .data-fields {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .formula-code {
      background: #f5f7fa;
      padding: 8px 12px;
      border-radius: 4px;
      font-family: 'Monaco', 'Consolas', monospace;
      font-size: 12px;
      color: #e6a23c;
    }
  }

  .results-overview {
    margin-bottom: 20px;

    .metric-card {
      display: flex;
      align-items: center;
      gap: 16px;

      .metric-icon {
        width: 48px;
        height: 48px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;

        &.annual-return {
          background: #f0f9ff;
          color: #409eff;
        }

        &.sharpe {
          background: #f0f9e8;
          color: #67c23a;
        }

        &.drawdown {
          background: #fef0f0;
          color: #f56c6c;
        }

        &.win-rate {
          background: #fdf6ec;
          color: #e6a23c;
        }
      }

      .metric-content {
        .metric-value {
          font-size: 20px;
          font-weight: bold;
          margin-bottom: 4px;

          &.positive {
            color: #67c23a;
          }

          &.negative {
            color: #f56c6c;
          }
        }

        .metric-label {
          font-size: 12px;
          color: #909399;
        }
      }
    }
  }

  .analysis-charts {
    margin-bottom: 20px;

    .chart-container {
      height: 300px;
      width: 100%;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>