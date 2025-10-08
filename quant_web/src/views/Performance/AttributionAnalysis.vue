<template>
  <div class="attribution-analysis">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">归因分析</h1>
      <div class="header-actions">
        <el-select v-model="analysisConfig.strategy" placeholder="选择策略" style="width: 200px">
          <el-option
            v-for="strategy in strategyList"
            :key="strategy.id"
            :label="strategy.name"
            :value="strategy.id"
          />
        </el-select>
        <el-date-picker
          v-model="analysisConfig.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 240px; margin-left: 10px"
        />
        <el-select v-model="analysisConfig.attributionModel" placeholder="归因模型" style="width: 150px">
          <el-option label="Brinson模型" value="brinson" />
          <el-option label="多因子模型" value="multi-factor" />
        </el-select>
        <el-button type="primary" @click="runAttributionAnalysis">
          <el-icon><Icon icon="ep:search" /></el-icon>
          分析
        </el-button>
      </div>
    </div>

    <!-- 归因结果概览 -->
    <el-row :gutter="16" class="attribution-overview">
      <el-col :span="8">
        <el-card class="attribution-card">
          <template #header>
            <span>超额收益分解</span>
          </template>
          <div ref="attributionChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="attribution-card">
          <template #header>
            <span>行业配置贡献</span>
          </template>
          <div ref="industryChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="attribution-card">
          <template #header>
            <span>风格因子暴露</span>
          </template>
          <div ref="factorExposureChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细归因结果 -->
    <el-card class="detailed-attribution">
      <template #header>
        <span>详细归因结果</span>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="Brinson归因" name="brinson">
          <el-table :data="brinsonAttribution" v-loading="loading">
            <el-table-column prop="category" label="类别" width="150" />
            <el-table-column prop="allocationEffect" label="配置效应" width="120">
              <template #default="{ row }">
                <span :class="getEffectClass(row.allocationEffect)">
                  {{ formatPercent(row.allocationEffect) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="selectionEffect" label="选股效应" width="120">
              <template #default="{ row }">
                <span :class="getEffectClass(row.selectionEffect)">
                  {{ formatPercent(row.selectionEffect) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="interactionEffect" label="交互效应" width="120">
              <template #default="{ row }">
                <span :class="getEffectClass(row.interactionEffect)">
                  {{ formatPercent(row.interactionEffect) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="totalEffect" label="总效应" width="120">
              <template #default="{ row }">
                <span :class="getEffectClass(row.totalEffect)">
                  {{ formatPercent(row.totalEffect) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="说明" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="多因子归因" name="multiFactor">
          <el-table :data="factorAttribution" v-loading="loading">
            <el-table-column prop="factor" label="因子" width="150" />
            <el-table-column prop="exposure" label="暴露度" width="120">
              <template #default="{ row }">
                <span :class="getExposureClass(row.exposure)">
                  {{ row.exposure.toFixed(3) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="factorReturn" label="因子收益" width="120">
              <template #default="{ row }">
                <span :class="getEffectClass(row.factorReturn)">
                  {{ formatPercent(row.factorReturn) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="attribution" label="归因贡献" width="120">
              <template #default="{ row }">
                <span :class="getEffectClass(row.attribution)">
                  {{ formatPercent(row.attribution) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="tStat" label="T统计量" width="100">
              <template #default="{ row }">
                <span :class="getTStatClass(row.tStat)">
                  {{ row.tStat.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="significance" label="显著性" width="100">
              <template #default="{ row }">
                <el-tag :type="getSignificanceTag(row.significance)" size="small">
                  {{ row.significance }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="时间序列归因" name="timeSeries">
          <div ref="timeSeriesChart" class="chart-container" style="height: 400px;"></div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 归因统计摘要 -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="12">
        <el-card class="summary-card">
          <template #header>
            <span>归因统计摘要</span>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="分析期间">
              {{ analysisConfig.dateRange?.[0]?.toLocaleDateString() }} -
              {{ analysisConfig.dateRange?.[1]?.toLocaleDateString() }}
            </el-descriptions-item>
            <el-descriptions-item label="总超额收益">
              <span :class="getEffectClass(attributionSummary.totalExcessReturn)">
                {{ formatPercent(attributionSummary.totalExcessReturn) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="配置效应贡献">
              <span :class="getEffectClass(attributionSummary.allocationContribution)">
                {{ formatPercent(attributionSummary.allocationContribution) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="选股效应贡献">
              <span :class="getEffectClass(attributionSummary.selectionContribution)">
                {{ formatPercent(attributionSummary.selectionContribution) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="可解释度(R²)">
              {{ (attributionSummary.rSquared * 100).toFixed(1) }}%
            </el-descriptions-item>
            <el-descriptions-item label="跟踪误差">
              {{ formatPercent(attributionSummary.trackingError) }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="summary-card">
          <template #header>
            <span>风险调整指标</span>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="信息比率">
              {{ attributionSummary.informationRatio.toFixed(2) }}
            </el-descriptions-item>
            <el-descriptions-item label="主动份额">
              {{ formatPercent(attributionSummary.activeShare) }}
            </el-descriptions-item>
            <el-descriptions-item label="主动风险">
              {{ formatPercent(attributionSummary.activeRisk) }}
            </el-descriptions-item>
            <el-descriptions-item label="Beta系数">
              {{ attributionSummary.beta.toFixed(2) }}
            </el-descriptions-item>
            <el-descriptions-item label="Alpha收益">
              <span :class="getEffectClass(attributionSummary.alpha)">
                {{ formatPercent(attributionSummary.alpha) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="Alpha显著性">
              <el-tag :type="attributionSummary.alphaSignificant ? 'success' : 'info'" size="small">
                {{ attributionSummary.alphaSignificant ? '显著' : '不显著' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'

// 响应式数据
const loading = ref(false)
const activeTab = ref('brinson')
const attributionChart = ref(null)
const industryChart = ref(null)
const factorExposureChart = ref(null)
const timeSeriesChart = ref(null)

const analysisConfig = reactive({
  strategy: '',
  dateRange: [new Date(Date.now() - 365 * 24 * 60 * 60 * 1000), new Date()],
  attributionModel: 'brinson'
})

const strategyList = ref([
  { id: '1', name: '双均线策略' },
  { id: '2', name: '动量反转策略' },
  { id: '3', name: '均值回归策略' }
])

const attributionSummary = reactive({
  totalExcessReturn: 0.0456,
  allocationContribution: 0.0123,
  selectionContribution: 0.0289,
  interactionContribution: 0.0044,
  rSquared: 0.856,
  trackingError: 0.0345,
  informationRatio: 1.32,
  activeShare: 0.782,
  activeRisk: 0.0289,
  beta: 0.95,
  alpha: 0.0234,
  alphaSignificant: true
})

const brinsonAttribution = ref([
  {
    category: '金融',
    allocationEffect: 0.0089,
    selectionEffect: 0.0156,
    interactionEffect: 0.0023,
    totalEffect: 0.0268,
    description: '金融行业整体超配，选股能力较强'
  },
  {
    category: '科技',
    allocationEffect: 0.0056,
    selectionEffect: 0.0089,
    interactionEffect: 0.0012,
    totalEffect: 0.0157,
    description: '科技行业配置适中，选股贡献显著'
  },
  {
    category: '消费',
    allocationEffect: -0.0023,
    selectionEffect: 0.0045,
    interactionEffect: 0.0009,
    totalEffect: 0.0031,
    description: '消费行业低配，但选股能力弥补了配置不足'
  },
  {
    category: '医药',
    allocationEffect: 0.0034,
    selectionEffect: -0.0012,
    interactionEffect: 0.0005,
    totalEffect: 0.0027,
    description: '医药行业超配，但选股表现一般'
  },
  {
    category: '其他',
    allocationEffect: -0.0033,
    selectionEffect: 0.0011,
    interactionEffect: -0.0005,
    totalEffect: -0.0027,
    description: '其他行业配置分散，整体贡献为负'
  }
])

const factorAttribution = ref([
  {
    factor: '市值因子',
    exposure: 0.234,
    factorReturn: 0.0156,
    attribution: 0.0036,
    tStat: 2.34,
    significance: '显著'
  },
  {
    factor: '价值因子',
    exposure: 0.189,
    factorReturn: 0.0234,
    attribution: 0.0044,
    tStat: 3.12,
    significance: '显著'
  },
  {
    factor: '动量因子',
    exposure: 0.156,
    factorReturn: -0.0089,
    attribution: -0.0014,
    tStat: -1.45,
    significance: '不显著'
  },
  {
    factor: '质量因子',
    exposure: 0.278,
    factorReturn: 0.0189,
    attribution: 0.0052,
    tStat: 2.89,
    significance: '显著'
  },
  {
    factor: '波动率因子',
    exposure: -0.134,
    factorReturn: -0.0123,
    attribution: 0.0016,
    tStat: 1.78,
    significance: '显著'
  },
  {
    factor: '残差收益',
    exposure: 1.000,
    factorReturn: 0.0098,
    attribution: 0.0098,
    tStat: 1.23,
    significance: '不显著'
  }
])

// 方法
const getEffectClass = (effect) => {
  return effect >= 0 ? 'positive' : 'negative'
}

const getExposureClass = (exposure) => {
  return Math.abs(exposure) > 0.2 ? 'highlight' : exposure >= 0 ? 'positive' : 'negative'
}

const getTStatClass = (tStat) => {
  const absTStat = Math.abs(tStat)
  if (absTStat >= 2.0) return 'significant'
  if (absTStat >= 1.5) return 'moderate'
  return 'insignificant'
}

const getSignificanceTag = (significance) => {
  return significance === '显著' ? 'success' : 'info'
}

const formatPercent = (value) => {
  return `${(value * 100).toFixed(2)}%`
}

const runAttributionAnalysis = async () => {
  if (!analysisConfig.strategy) {
    ElMessage.warning('请选择策略')
    return
  }

  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 2000))
    ElMessage.success('归因分析完成')
    initCharts()
  } catch (error) {
    ElMessage.error('归因分析失败')
  } finally {
    loading.value = false
  }
}

// 图表初始化
let attributionChartInstance = null
let industryChartInstance = null
let factorExposureChartInstance = null
let timeSeriesChartInstance = null

const initCharts = () => {
  // 超额收益分解图表
  if (attributionChart.value) {
    attributionChartInstance = echarts.init(attributionChart.value)
    const attributionOption = {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c} ({d}%)'
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center'
      },
      series: [
        {
          name: '超额收益分解',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 18,
              fontWeight: 'bold'
            }
          },
          labelLine: {
            show: false
          },
          data: [
            { value: 45.6, name: '选股效应', itemStyle: { color: '#5470c6' } },
            { value: 26.9, name: '配置效应', itemStyle: { color: '#91cc75' } },
            { value: 9.6, name: '交互效应', itemStyle: { color: '#fac858' } },
            { value: 17.9, name: '其他', itemStyle: { color: '#ee6666' } }
          ]
        }
      ]
    }
    attributionChartInstance.setOption(attributionOption)
  }

  // 行业配置贡献图表
  if (industryChart.value) {
    industryChartInstance = echarts.init(industryChart.value)
    const industryOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'value',
        axisLabel: {
          formatter: '{value}%'
        }
      },
      yAxis: {
        type: 'category',
        data: ['金融', '科技', '消费', '医药', '工业', '能源', '其他']
      },
      series: [
        {
          name: '配置贡献',
          type: 'bar',
          data: [2.68, 1.57, 0.31, 0.27, -0.45, -0.23, -0.15],
          itemStyle: {
            color: function(params) {
              return params.value >= 0 ? '#5470c6' : '#ee6666'
            }
          },
          label: {
            show: true,
            position: 'right',
            formatter: '{c}%'
          }
        }
      ]
    }
    industryChartInstance.setOption(industryOption)
  }

  // 风格因子暴露图表
  if (factorExposureChart.value) {
    factorExposureChartInstance = echarts.init(factorExposureChart.value)
    const factorOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      radar: {
        indicator: [
          { name: '市值', max: 0.3 },
          { name: '价值', max: 0.3 },
          { name: '动量', max: 0.3 },
          { name: '质量', max: 0.3 },
          { name: '波动率', max: 0.3 },
          { name: '成长', max: 0.3 }
        ]
      },
      series: [
        {
          name: '因子暴露',
          type: 'radar',
          data: [
            {
              value: [0.234, 0.189, 0.156, 0.278, 0.134, 0.167],
              name: '策略暴露',
              areaStyle: {
                color: 'rgba(84, 112, 198, 0.3)'
              },
              lineStyle: {
                color: '#5470c6'
              }
            },
            {
              value: [0.156, 0.234, 0.123, 0.189, 0.167, 0.145],
              name: '基准暴露',
              areaStyle: {
                color: 'rgba(145, 204, 117, 0.3)'
              },
              lineStyle: {
                color: '#91cc75'
              }
            }
          ]
        }
      ]
    }
    factorExposureChartInstance.setOption(factorOption)
  }

  // 时间序列归因图表
  if (timeSeriesChart.value) {
    timeSeriesChartInstance = echarts.init(timeSeriesChart.value)
    const timeSeriesOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        }
      },
      legend: {
        data: ['累计超额收益', '配置效应', '选股效应', '交互效应']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['Q1', 'Q2', 'Q3', 'Q4']
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: '{value}%'
        }
      },
      series: [
        {
          name: '累计超额收益',
          type: 'line',
          data: [1.2, 2.8, 3.5, 4.6],
          itemStyle: { color: '#5470c6' },
          smooth: true
        },
        {
          name: '配置效应',
          type: 'bar',
          data: [0.8, 1.2, 1.0, 1.3],
          itemStyle: { color: '#91cc75' }
        },
        {
          name: '选股效应',
          type: 'bar',
          data: [0.3, 1.4, 2.2, 2.9],
          itemStyle: { color: '#fac858' }
        },
        {
          name: '交互效应',
          type: 'bar',
          data: [0.1, 0.2, 0.3, 0.4],
          itemStyle: { color: '#ee6666' }
        }
      ]
    }
    timeSeriesChartInstance.setOption(timeSeriesOption)
  }
}

// 生命周期
onMounted(() => {
  if (strategyList.value.length > 0) {
    analysisConfig.strategy = strategyList.value[0].id
  }
  runAttributionAnalysis()
})
</script>

<style lang="scss" scoped>
.attribution-analysis {
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

.attribution-overview {
  margin-bottom: 20px;
}

.attribution-card {
  :deep(.el-card__header) {
    padding: 12px 20px;
  }
}

.chart-container {
  height: 300px;
}

.detailed-attribution {
  margin-bottom: 20px;

  :deep(.el-card__header) {
    padding: 12px 20px;
  }
}

.summary-row {
  margin-bottom: 20px;
}

.summary-card {
  :deep(.el-card__header) {
    padding: 12px 20px;
  }
}

.positive {
  color: #67c23a;
  font-weight: bold;
}

.negative {
  color: #f56c6c;
  font-weight: bold;
}

.highlight {
  color: #e6a23c;
  font-weight: bold;
}

.significant {
  color: #67c23a;
  font-weight: bold;
}

.moderate {
  color: #e6a23c;
  font-weight: bold;
}

.insignificant {
  color: #909399;
}
</style>