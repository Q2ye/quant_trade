<template>
  <div class="backtest-period">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">回溯周期</h1>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreatePeriod">
          <el-icon><Icon icon="mdi:plus" /></el-icon>
          新建周期
        </el-button>
        <el-button @click="exportPeriods">
          <el-icon><Icon icon="mdi:download" /></el-icon>
          导出配置
        </el-button>
      </div>
    </div>

    <!-- 周期配置管理 -->
    <el-card class="period-config">
      <template #header>
        <div class="card-header">
          <span>回溯周期配置</span>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索周期名称"
              style="width: 200px"
              clearable
            >
              <template #prefix>
                <el-icon><Icon icon="mdi:magnify" /></el-icon>
              </template>
            </el-input>
            <el-select v-model="filterStatus" placeholder="状态" style="width: 100px">
              <el-option label="全部" value="" />
              <el-option label="启用" value="active" />
              <el-option label="停用" value="inactive" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="filteredPeriods" v-loading="loading">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="周期名称" width="150" />
        <el-table-column prop="description" label="周期描述" min-width="200" />
        <el-table-column prop="startDate" label="开始日期" width="120">
          <template #default="{ row }">
            {{ formatDate(row.startDate) }}
          </template>
        </el-table-column>
        <el-table-column prop="endDate" label="结束日期" width="120">
          <template #default="{ row }">
            {{ formatDate(row.endDate) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="周期长度" width="100">
          <template #default="{ row }">
            {{ row.duration }}天
          </template>
        </el-table-column>
        <el-table-column prop="testCount" label="测试次数" width="100">
          <template #default="{ row }">
            {{ row.testCount }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastTest" label="最后测试" width="120">
          <template #default="{ row }">
            {{ row.lastTest ? formatDate(row.lastTest) : '--' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEditPeriod(row)">
              <el-icon><Icon icon="mdi:pencil" /></el-icon>
              编辑
            </el-button>
            <el-button size="small" @click="handleRunBacktest(row)">
              <el-icon><Icon icon="mdi:play" /></el-icon>
              回测
            </el-button>
            <el-button size="small" type="danger" @click="handleDeletePeriod(row)">
              <el-icon><Icon icon="mdi:delete" /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 周期性能分析 -->
    <el-card class="period-analysis">
      <template #header>
        <span>周期性能分析</span>
      </template>

      <el-row :gutter="16">
        <el-col :span="12">
          <div class="analysis-chart">
            <div ref="performanceChart" class="chart-container" style="height: 300px;"></div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="analysis-stats">
            <el-descriptions title="统计摘要" :column="1" border>
              <el-descriptions-item label="总周期数">
                {{ analysisStats.totalPeriods }}
              </el-descriptions-item>
              <el-descriptions-item label="平均收益率">
                <span :class="getReturnClass(analysisStats.avgReturn)">
                  {{ formatPercent(analysisStats.avgReturn) }}
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="最优周期">
                {{ analysisStats.bestPeriod }}
              </el-descriptions-item>
              <el-descriptions-item label="最差周期">
                {{ analysisStats.worstPeriod }}
              </el-descriptions-item>
              <el-descriptions-item label="胜率">
                {{ formatPercent(analysisStats.winRate) }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 周期对比分析 -->
    <el-card class="period-comparison">
      <template #header>
        <span>周期对比分析</span>
      </template>

      <el-form :model="comparisonConfig" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="对比周期">
              <el-select
                v-model="comparisonConfig.selectedPeriods"
                multiple
                placeholder="请选择对比周期"
                style="width: 100%"
              >
                <el-option
                  v-for="period in periods"
                  :key="period.id"
                  :label="period.name"
                  :value="period.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="对比指标">
              <el-select v-model="comparisonConfig.metric" placeholder="请选择对比指标" style="width: 100%">
                <el-option label="年化收益率" value="annualReturn" />
                <el-option label="夏普比率" value="sharpeRatio" />
                <el-option label="最大回撤" value="maxDrawdown" />
                <el-option label="胜率" value="winRate" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <el-button type="primary" @click="runComparison" :loading="comparing">
                <el-icon><Icon icon="mdi:chart-bar" /></el-icon>
                运行对比
              </el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div v-if="comparisonResults" class="comparison-results">
        <div class="chart-header">
          <span>周期对比结果 - {{ getMetricLabel(comparisonConfig.metric) }}</span>
        </div>
        <div ref="comparisonChart" class="chart-container" style="height: 400px;"></div>
      </div>
    </el-card>

    <!-- 周期编辑对话框 -->
    <el-dialog
      v-model="periodDialogVisible"
      :title="isEditMode ? '编辑回溯周期' : '新建回溯周期'"
      width="600px"
    >
      <el-form :model="periodForm" :rules="periodRules" ref="periodFormRef" label-width="100px">
        <el-form-item label="周期名称" prop="name">
          <el-input v-model="periodForm.name" placeholder="请输入周期名称" />
        </el-form-item>

        <el-form-item label="周期描述" prop="description">
          <el-input
            v-model="periodForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入周期描述"
          />
        </el-form-item>

        <el-form-item label="时间范围" prop="dateRange">
          <el-date-picker
            v-model="periodForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="状态" prop="status">
          <el-switch
            v-model="periodForm.status"
            :active-value="'active'"
            :inactive-value="'inactive'"
          />
          <span style="margin-left: 10px; color: #909399">
            {{ periodForm.status === 'active' ? '启用' : '停用' }}
          </span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="periodDialogVisible = false">
          <el-icon><Icon icon="mdi:close" /></el-icon>
          取消
        </el-button>
        <el-button type="primary" @click="handleSavePeriod">
          <el-icon><Icon icon="mdi:check" /></el-icon>
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'

// 响应式数据
const loading = ref(false)
const comparing = ref(false)
const periodDialogVisible = ref(false)
const isEditMode = ref(false)
const searchKeyword = ref('')
const filterStatus = ref('')
const performanceChart = ref(null)
const comparisonChart = ref(null)
const periodFormRef = ref(null)

const pagination = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const comparisonConfig = reactive({
  selectedPeriods: [],
  metric: 'annualReturn'
})

const periodForm = reactive({
  id: '',
  name: '',
  description: '',
  dateRange: [],
  status: 'active'
})

const periodRules = {
  name: [{ required: true, message: '请输入周期名称', trigger: 'blur' }],
  description: [{ required: true, message: '请输入周期描述', trigger: 'blur' }],
  dateRange: [{ required: true, message: '请选择时间范围', trigger: 'change' }]
}

const periods = ref([
  {
    id: '1',
    name: '2023年全年',
    description: '2023年完整年度回测周期',
    startDate: new Date('2023-01-01'),
    endDate: new Date('2023-12-31'),
    duration: 365,
    testCount: 15,
    status: 'active',
    lastTest: new Date('2024-01-10'),
    performance: {
      annualReturn: 0.2345,
      sharpeRatio: 1.23,
      maxDrawdown: -0.0876
    }
  },
  {
    id: '2',
    name: '2023下半年',
    description: '2023年下半年回测周期',
    startDate: new Date('2023-07-01'),
    endDate: new Date('2023-12-31'),
    duration: 184,
    testCount: 8,
    status: 'active',
    lastTest: new Date('2024-01-08'),
    performance: {
      annualReturn: 0.1567,
      sharpeRatio: 0.89,
      maxDrawdown: -0.0654
    }
  },
  {
    id: '3',
    name: '2022熊市',
    description: '2022年熊市环境测试',
    startDate: new Date('2022-01-01'),
    endDate: new Date('2022-12-31'),
    duration: 365,
    testCount: 12,
    status: 'inactive',
    lastTest: new Date('2023-12-20'),
    performance: {
      annualReturn: -0.1234,
      sharpeRatio: -0.45,
      maxDrawdown: -0.2345
    }
  }
])

const analysisStats = reactive({
  totalPeriods: 3,
  avgReturn: 0.0893,
  bestPeriod: '2023年全年',
  worstPeriod: '2022熊市',
  winRate: 0.6667
})

const comparisonResults = ref(null)

// 计算属性
const filteredPeriods = computed(() => {
  let result = periods.value

  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(period =>
      period.name.toLowerCase().includes(keyword) ||
      period.description.toLowerCase().includes(keyword)
    )
  }

  if (filterStatus.value) {
    result = result.filter(period => period.status === filterStatus.value)
  }

  pagination.total = result.length
  const start = (pagination.currentPage - 1) * pagination.pageSize
  const end = start + pagination.pageSize
  return result.slice(start, end)
})

// 方法
const getReturnClass = (returnValue) => {
  return returnValue >= 0 ? 'positive' : 'negative'
}

const formatDate = (date) => {
  if (!date) return '--'
  return new Date(date).toLocaleDateString('zh-CN')
}

const formatPercent = (value) => {
  if (value === undefined || value === null) return '--'
  return `${(value * 100).toFixed(2)}%`
}

const getMetricLabel = (metric) => {
  const map = {
    annualReturn: '年化收益率',
    sharpeRatio: '夏普比率',
    maxDrawdown: '最大回撤',
    winRate: '胜率'
  }
  return map[metric] || metric
}

const handleCreatePeriod = () => {
  isEditMode.value = false
  Object.assign(periodForm, {
    id: '',
    name: '',
    description: '',
    dateRange: [],
    status: 'active'
  })
  periodDialogVisible.value = true
}

const handleEditPeriod = (period) => {
  isEditMode.value = true
  Object.assign(periodForm, {
    ...period,
    dateRange: [period.startDate, period.endDate]
  })
  periodDialogVisible.value = true
}

const handleRunBacktest = (period) => {
  ElMessage.info(`开始对周期 "${period.name}" 进行回测...`)
  // 这里可以跳转到回测页面或触发回测任务
}

const handleDeletePeriod = async (period) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除回溯周期 "${period.name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const index = periods.value.findIndex(p => p.id === period.id)
    if (index > -1) {
      periods.value.splice(index, 1)
      ElMessage.success('回溯周期删除成功')
      initPerformanceChart()
    }
  } catch (error) {
    // 用户取消
  }
}

const handleSavePeriod = async () => {
  if (!periodFormRef.value) return

  try {
    await periodFormRef.value.validate()

    const [startDate, endDate] = periodForm.dateRange
    const duration = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24))

    if (isEditMode.value) {
      // 更新现有周期
      const index = periods.value.findIndex(p => p.id === periodForm.id)
      if (index > -1) {
        periods.value[index] = {
          ...periodForm,
          startDate,
          endDate,
          duration,
          lastTest: new Date()
        }
      }
      ElMessage.success('回溯周期更新成功')
    } else {
      // 添加新周期
      const newPeriod = {
        ...periodForm,
        id: Date.now().toString(),
        startDate,
        endDate,
        duration,
        testCount: 0,
        lastTest: null,
        performance: {
          annualReturn: 0,
          sharpeRatio: 0,
          maxDrawdown: 0
        }
      }
      periods.value.push(newPeriod)
      ElMessage.success('回溯周期创建成功')
    }

    periodDialogVisible.value = false
    initPerformanceChart()
  } catch (error) {
    console.error('表单验证失败:', error)
    ElMessage.error('表单验证失败')
  }
}

const exportPeriods = () => {
  ElMessage.info('导出功能开发中')
}

const runComparison = async () => {
  if (comparisonConfig.selectedPeriods.length === 0) {
    ElMessage.warning('请选择要对比的周期')
    return
  }

  comparing.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 2000))

    // 模拟对比结果
    comparisonResults.value = {
      periods: comparisonConfig.selectedPeriods.map(id => {
        const period = periods.value.find(p => p.id === id)
        return {
          name: period.name,
          value: period.performance[comparisonConfig.metric]
        }
      })
    }

    ElMessage.success('对比分析完成')
    nextTick(() => {
      initComparisonChart()
    })
  } catch (error) {
    console.error('对比分析失败:', error)
    ElMessage.error('对比分析失败')
  } finally {
    comparing.value = false
  }
}

const handlePageChange = (page) => {
  pagination.currentPage = page
}

// 图表初始化
let performanceChartInstance = null
let comparisonChartInstance = null

const initPerformanceChart = () => {
  // 周期性能图表
  if (performanceChart.value) {
    performanceChartInstance = echarts.init(performanceChart.value)
    const performanceOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      legend: {
        data: ['年化收益', '夏普比率', '最大回撤']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: periods.value.map(p => p.name)
      },
      yAxis: [
        {
          type: 'value',
          name: '收益率',
          axisLabel: {
            formatter: '{value}%'
          }
        },
        {
          type: 'value',
          name: '比率/回撤',
          axisLabel: {
            formatter: '{value}'
          }
        }
      ],
      series: [
        {
          name: '年化收益',
          type: 'bar',
          data: periods.value.map(p => (p.performance.annualReturn * 100).toFixed(1)),
          itemStyle: {
            color: function(params) {
              return params.data >= 0 ? '#5470c6' : '#ee6666'
            }
          }
        },
        {
          name: '夏普比率',
          type: 'line',
          yAxisIndex: 1,
          data: periods.value.map(p => p.performance.sharpeRatio.toFixed(2)),
          itemStyle: { color: '#91cc75' }
        },
        {
          name: '最大回撤',
          type: 'line',
          yAxisIndex: 1,
          data: periods.value.map(p => (p.performance.maxDrawdown * 100).toFixed(1)),
          itemStyle: { color: '#ee6666' }
        }
      ]
    }
    performanceChartInstance.setOption(performanceOption)
  }
}

const initComparisonChart = () => {
  // 周期对比图表
  if (comparisonChart.value && comparisonResults.value) {
    comparisonChartInstance = echarts.init(comparisonChart.value)

    const formatComparisonValue = (value, metric) => {
      if (metric === 'annualReturn' || metric === 'maxDrawdown' || metric === 'winRate') {
        return (value * 100).toFixed(2) + '%'
      }
      return value.toFixed(2)
    }

    const comparisonOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        },
        formatter: function (params) {
          return `${params[0].name}<br/>${getMetricLabel(comparisonConfig.metric)}: ${formatComparisonValue(params[0].value, comparisonConfig.metric)}`
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: comparisonResults.value.periods.map(p => p.name)
      },
      yAxis: {
        type: 'value',
        name: getMetricLabel(comparisonConfig.metric)
      },
      series: [
        {
          name: getMetricLabel(comparisonConfig.metric),
          type: 'bar',
          data: comparisonResults.value.periods.map(p => p.value),
          itemStyle: {
            color: function(params) {
              if (comparisonConfig.metric === 'maxDrawdown') {
                return params.data >= 0 ? '#ee6666' : '#5470c6'
              }
              return params.data >= 0 ? '#5470c6' : '#ee6666'
            }
          },
          label: {
            show: true,
            position: 'top',
            formatter: function(params) {
              return formatComparisonValue(params.data, comparisonConfig.metric)
            }
          }
        }
      ]
    }
    comparisonChartInstance.setOption(comparisonOption)
  }
}

// 响应窗口大小变化
const handleResize = () => {
  if (performanceChartInstance) {
    performanceChartInstance.resize()
  }
  if (comparisonChartInstance) {
    comparisonChartInstance.resize()
  }
}

// 生命周期
onMounted(() => {
  window.addEventListener('resize', handleResize)
  initPerformanceChart()
  pagination.total = periods.value.length
})

// 清理
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (performanceChartInstance) {
    performanceChartInstance.dispose()
  }
  if (comparisonChartInstance) {
    comparisonChartInstance.dispose()
  }
})
</script>

<style lang="scss" scoped>
.backtest-period {
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
}

.period-config,
.period-analysis,
.period-comparison {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.chart-container {
  width: 100%;
}

.analysis-stats {
  padding: 20px;
}

.comparison-results {
  margin-top: 20px;
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: #303133;
}

.positive {
  color: #67c23a;
  font-weight: bold;
}

.negative {
  color: #f56c6c;
  font-weight: bold;
}

// 确保图标正确显示
.el-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

// 修复表格操作按钮间距
.el-table .el-button {
  margin: 2px;
}
</style>