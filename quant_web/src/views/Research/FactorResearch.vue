<!-- views/Research/FactorResearch.vue -->
<template>
  <div class="factor-research">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Icon icon="mdi:flask" /></el-icon>
        因子研究
      </h1>
      <div class="header-actions">
        <el-button type="primary" @click="runQuickTest" :loading="testing">
          <el-icon><Icon icon="mdi:play" /></el-icon>
          快速测试
        </el-button>
        <el-button @click="compareFactors" :disabled="selectedFactors.length < 2">
          <el-icon><Icon icon="mdi:compare" /></el-icon>
          因子对比
        </el-button>
        <el-button @click="gotoFactorLibrary">
          <el-icon><Icon icon="mdi:cog" /></el-icon>
          管理因子库
        </el-button>
      </div>
    </div>

    <!-- 快速测试面板 -->
    <el-card class="quick-test-panel">
      <template #header>
        <div class="card-header">
          <span>快速因子测试</span>
          <el-button type="text" @click="showAdvanced = !showAdvanced">
            {{ showAdvanced ? '简化配置' : '高级配置' }}
          </el-button>
        </div>
      </template>

      <el-row :gutter="20">
        <!-- 因子选择区域 -->
        <el-col :span="8">
          <div class="factor-selection">
            <div class="section-title">
              <el-icon><Icon icon="mdi:check-circle" /></el-icon>
              选择测试因子
            </div>

            <!-- 因子分类选择 -->
            <el-tabs v-model="activeCategory" class="factor-tabs">
              <el-tab-pane label="价值因子" name="value">
                <factor-selector
                  :factors="valueFactors"
                  v-model:selected="selectedFactors"
                  category="value"
                />
              </el-tab-pane>
              <el-tab-pane label="成长因子" name="growth">
                <factor-selector
                  :factors="growthFactors"
                  v-model:selected="selectedFactors"
                  category="growth"
                />
              </el-tab-pane>
              <el-tab-pane label="质量因子" name="quality">
                <factor-selector
                  :factors="qualityFactors"
                  v-model:selected="selectedFactors"
                  category="quality"
                />
              </el-tab-pane>
            </el-tabs>

            <div class="selected-count">
              已选择 {{ selectedFactors.length }} 个因子
            </div>
          </div>
        </el-col>

        <!-- 测试配置区域 -->
        <el-col :span="8">
          <div class="test-config">
            <div class="section-title">
              <el-icon><Icon icon="mdi:settings" /></el-icon>
              测试配置
            </div>

            <el-form :model="quickConfig" label-width="80px" size="small">
              <el-form-item label="测试周期">
                <el-date-picker
                  v-model="quickConfig.dateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  style="width: 100%"
                />
              </el-form-item>

              <el-form-item label="股票池">
                <el-select v-model="quickConfig.universe" style="width: 100%">
                  <el-option label="全A股" value="all" />
                  <el-option label="沪深300" value="hs300" />
                  <el-option label="中证500" value="zz500" />
                </el-select>
              </el-form-item>

              <el-form-item label="初始资金">
                <el-input-number
                  v-model="quickConfig.initialCapital"
                  :min="100000"
                  :step="100000"
                  style="width: 100%"
                  controls-position="right"
                >
                  <template #append>元</template>
                </el-input-number>
              </el-form-item>

              <!-- 高级配置 -->
              <div v-if="showAdvanced" class="advanced-config">
                <el-form-item label="调仓频率">
                  <el-select v-model="quickConfig.rebalanceFreq" style="width: 100%">
                    <el-option label="每日" value="daily" />
                    <el-option label="每周" value="weekly" />
                    <el-option label="每月" value="monthly" />
                  </el-select>
                </el-form-item>

                <el-form-item label="分组数量">
                  <el-slider
                    v-model="quickConfig.groupCount"
                    :min="3"
                    :max="10"
                    :step="1"
                    show-stops
                  />
                </el-form-item>
              </div>
            </el-form>
          </div>
        </el-col>

        <!-- 快速结果预览 -->
        <el-col :span="8">
          <div class="quick-results">
            <div class="section-title">
              <el-icon><Icon icon="mdi:chart-line" /></el-icon>
              快速结果
            </div>

            <div v-if="quickResults" class="results-preview">
              <div class="result-metrics">
                <div class="metric-item">
                  <div class="metric-value positive">{{ formatPercent(quickResults.annualReturn) }}</div>
                  <div class="metric-label">年化收益</div>
                </div>
                <div class="metric-item">
                  <div class="metric-value">{{ quickResults.sharpeRatio.toFixed(2) }}</div>
                  <div class="metric-label">夏普比率</div>
                </div>
                <div class="metric-item">
                  <div class="metric-value negative">{{ formatPercent(quickResults.maxDrawdown) }}</div>
                  <div class="metric-label">最大回撤</div>
                </div>
              </div>

              <el-button type="primary" text @click="showDetailAnalysis" style="width: 100%; margin-top: 10px;">
                查看详细分析
              </el-button>
            </div>

            <div v-else class="no-results">
              <el-empty description="暂无测试结果" :image-size="80">
                <template #description>
                  <p>选择因子并点击"快速测试"查看结果</p>
                </template>
              </el-empty>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 因子对比面板 -->
    <el-card v-if="comparisonResults" class="comparison-panel">
      <template #header>
        <span>因子对比分析</span>
      </template>

      <el-tabs v-model="comparisonTab">
        <el-tab-pane label="收益对比" name="returns">
          <div ref="returnsComparisonChart" class="chart-container" style="height: 300px;"></div>
        </el-tab-pane>
        <el-tab-pane label="风险指标" name="risk">
          <el-table :data="comparisonResults.riskMetrics" border>
            <el-table-column prop="factorName" label="因子名称" />
            <el-table-column prop="annualReturn" label="年化收益">
              <template #default="{ row }">
                <span :class="row.annualReturn >= 0 ? 'positive' : 'negative'">
                  {{ formatPercent(row.annualReturn) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="sharpeRatio" label="夏普比率" />
            <el-table-column prop="maxDrawdown" label="最大回撤">
              <template #default="{ row }">
                <span class="negative">{{ formatPercent(row.maxDrawdown) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="winRate" label="胜率">
              <template #default="{ row }">
                {{ formatPercent(row.winRate) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 详细分析对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="因子详细分析"
      width="90%"
      fullscreen
    >
      <factor-detail-analysis
        :factor="selectedFactor"
        :test-config="quickConfig"
        :test-results="quickResults"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'

// 共享组件
import FactorSelector from '@/components/Research/FactorSelector.vue'
import FactorDetailAnalysis from '@/components/Research/FactorDetailAnalysis.vue'

const router = useRouter()

// 响应式数据
const testing = ref(false)
const showAdvanced = ref(false)
const activeCategory = ref('value')
const selectedFactors = ref([])
const selectedFactor = ref(null)
const quickResults = ref(null)
const comparisonResults = ref(null)
const comparisonTab = ref('returns')
const detailDialogVisible = ref(false)
const returnsComparisonChart = ref(null)

// 测试配置
const quickConfig = reactive({
  dateRange: [new Date(Date.now() - 365 * 24 * 60 * 60 * 1000), new Date()],
  universe: 'all',
  initialCapital: 1000000,
  rebalanceFreq: 'monthly',
  groupCount: 5
})

// 因子数据
const valueFactors = ref([
  { id: 'pe_ratio', name: '市盈率(PE)', description: '市值与净利润比率', category: 'value' },
  { id: 'pb_ratio', name: '市净率(PB)', description: '市值与净资产比率', category: 'value' },
  { id: 'dividend_yield', name: '股息率', description: '年度股息与股价比率', category: 'value' },
  { id: 'ev_ebitda', name: 'EV/EBITDA', description: '企业价值与税息折旧摊销前利润比率', category: 'value' }
])

const growthFactors = ref([
  { id: 'revenue_growth', name: '营收增长率', description: '营业收入同比增长率', category: 'growth' },
  { id: 'profit_growth', name: '利润增长率', description: '净利润同比增长率', category: 'growth' },
  { id: 'roe_growth', name: 'ROE增长率', description: '净资产收益率变化率', category: 'growth' }
])

const qualityFactors = ref([
  { id: 'roe', name: '净资产收益率(ROE)', description: '净利润与净资产比率', category: 'quality' },
  { id: 'roa', name: '总资产收益率(ROA)', description: '净利润与总资产比率', category: 'quality' },
  { id: 'profit_margin', name: '净利润率', description: '净利润与营业收入比率', category: 'quality' }
])

// 方法
const runQuickTest = async () => {
  if (selectedFactors.value.length === 0) {
    ElMessage.warning('请选择至少一个因子进行测试')
    return
  }

  testing.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1500))

    // 模拟测试结果
    quickResults.value = {
      annualReturn: 0.156,
      sharpeRatio: 1.24,
      maxDrawdown: -0.153,
      winRate: 0.625,
      groupReturns: [0.156, 0.123, 0.089, 0.045, -0.012],
      icSeries: [0.045, 0.056, 0.032, -0.012, 0.067, 0.023, 0.078, 0.034]
    }

    ElMessage.success('因子测试完成')
  } catch (error) {
    ElMessage.error('测试失败: ' + error.message)
  } finally {
    testing.value = false
  }
}

const compareFactors = async () => {
  if (selectedFactors.value.length < 2) {
    ElMessage.warning('请选择至少两个因子进行对比')
    return
  }

  testing.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 2000))

    // 模拟对比结果
    comparisonResults.value = {
      riskMetrics: selectedFactors.value.map(factor => ({
        factorName: factor.name,
        annualReturn: Math.random() * 0.3 - 0.05,
        sharpeRatio: Math.random() * 2,
        maxDrawdown: Math.random() * -0.2 - 0.1,
        winRate: Math.random() * 0.3 + 0.5
      }))
    }

    // 初始化对比图表
    initComparisonChart()
  } catch (error) {
    ElMessage.error('对比分析失败: ' + error.message)
  } finally {
    testing.value = false
  }
}

const showDetailAnalysis = () => {
  if (selectedFactors.value.length > 0) {
    selectedFactor.value = selectedFactors.value[0]
    detailDialogVisible.value = true
  }
}

const gotoFactorLibrary = () => {
  router.push('/strategies/factor-library')
}

const formatPercent = (value) => {
  return `${(value * 100).toFixed(2)}%`
}

// 图表初始化
let comparisonChartInstance = null

const initComparisonChart = () => {
  if (!comparisonResults.value || !returnsComparisonChart.value) return

  comparisonChartInstance = echarts.init(returnsComparisonChart.value)
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: selectedFactors.value.map(f => f.name)
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月']
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: selectedFactors.value.map((factor, index) => ({
      name: factor.name,
      type: 'line',
      data: Array(7).fill(0).map(() => Math.random() * 20 + 5),
      itemStyle: {
        color: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452'][index]
      }
    }))
  }

  comparisonChartInstance.setOption(option)
}

// 清理
import { onUnmounted } from 'vue'
onUnmounted(() => {
  if (comparisonChartInstance) {
    comparisonChartInstance.dispose()
  }
})
</script>

<style lang="scss" scoped>
.factor-research {
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
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.quick-test-panel {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: #303133;
}

.factor-selection {
  .factor-tabs {
    height: 300px;

    :deep(.el-tab-pane) {
      height: 250px;
      overflow-y: auto;
    }
  }

  .selected-count {
    margin-top: 10px;
    padding: 8px;
    background: #f5f7fa;
    border-radius: 4px;
    text-align: center;
    color: #606266;
  }
}

.test-config {
  .advanced-config {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #e4e7ed;
  }
}

.quick-results {
  .results-preview {
    .result-metrics {
      display: flex;
      justify-content: space-around;
      text-align: center;

      .metric-item {
        .metric-value {
          font-size: 18px;
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

  .no-results {
    text-align: center;
    color: #909399;
  }
}

.comparison-panel {
  margin-top: 20px;
}

.chart-container {
  width: 100%;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>