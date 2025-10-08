<template>
  <div class="risk-monitor">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">实时监控</h1>
      <div class="header-actions">
        <el-button type="primary" @click="refreshData">
          <el-icon><Icon icon="ep:refresh" /></el-icon>
          刷新
        </el-button>
        <el-button @click="exportData">
          <el-icon><Icon icon="ep:download" /></el-icon>
          导出
        </el-button>
      </div>
    </div>

    <!-- 监控概览卡片 -->
    <div class="overview-cards">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value" :class="getStatusClass(riskStats.totalRiskLevel)">
                {{ riskStats.totalAlerts }}
              </div>
              <div class="metric-label">总警报数</div>
            </div>
            <template #footer>
              <div class="metric-footer">
                <span :class="getTrendClass(riskStats.alertTrend)">
                  {{ riskStats.alertTrend > 0 ? '↑' : '↓' }}
                  {{ Math.abs(riskStats.alertTrend) }}
                </span>
                较昨日
              </div>
            </template>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value" :class="getStatusClass(riskStats.positionRiskLevel)">
                {{ riskStats.positionAlerts }}
              </div>
              <div class="metric-label">持仓风险</div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value" :class="getStatusClass(riskStats.accountRiskLevel)">
                ¥{{ formatNumber(riskStats.accountRiskAmount) }}
              </div>
              <div class="metric-label">账户风险金额</div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value" :class="getStatusClass(riskStats.systemRiskLevel)">
                {{ riskStats.systemAlerts }}
              </div>
              <div class="metric-label">系统风险</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 实时风险图表 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="chart-header">
              <span>风险事件趋势</span>
              <el-select v-model="trendPeriod" size="small" style="width: 120px">
                <el-option label="今日" value="today" />
                <el-option label="本周" value="week" />
                <el-option label="本月" value="month" />
              </el-select>
            </div>
          </template>
          <div ref="riskTrendChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="chart-header">
              <span>风险类型分布</span>
            </div>
          </template>
          <div ref="riskTypeChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 实时警报列表 -->
    <el-card class="alerts-card">
      <template #header>
        <div class="alerts-header">
          <span>实时风险警报</span>
          <div class="alert-filters">
            <el-select v-model="alertFilter.level" placeholder="风险等级" size="small" style="width: 100px">
              <el-option label="全部" value="" />
              <el-option label="高风险" value="high" />
              <el-option label="中风险" value="medium" />
              <el-option label="低风险" value="low" />
            </el-select>
            <el-select v-model="alertFilter.type" placeholder="风险类型" size="small" style="width: 120px">
              <el-option label="全部" value="" />
              <el-option label="持仓风险" value="position" />
              <el-option label="账户风险" value="account" />
              <el-option label="系统风险" value="system" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="filteredAlerts" v-loading="loading">
        <el-table-column prop="time" label="时间" width="140">
          <template #default="{ row }">
            {{ formatTime(row.time) }}
          </template>
        </el-table-column>
        <el-table-column prop="strategyName" label="策略" width="120" />
        <el-table-column prop="symbol" label="标的" width="100" />
        <el-table-column prop="type" label="风险类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getRiskTypeTag(row.type)" size="small">
              {{ getRiskTypeText(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="风险等级" width="100">
          <template #default="{ row }">
            <el-tag :type="getRiskLevelTag(row.level)" size="small">
              {{ getRiskLevelText(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="风险描述" min-width="200" />
        <el-table-column prop="action" label="处理动作" width="120">
          <template #default="{ row }">
            <el-tag :type="getActionTag(row.action)" size="small">
              {{ getActionText(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="handleAlertAction(row)">
              处理
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'

// 响应式数据
const loading = ref(false)
const trendPeriod = ref('today')
const riskTrendChart = ref(null)
const riskTypeChart = ref(null)

const riskStats = reactive({
  totalAlerts: 12,
  positionAlerts: 5,
  accountRiskAmount: 125000,
  systemAlerts: 3,
  totalRiskLevel: 'medium',
  positionRiskLevel: 'high',
  accountRiskLevel: 'medium',
  systemRiskLevel: 'low',
  alertTrend: 2
})

const alertFilter = reactive({
  level: '',
  type: ''
})

const pagination = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const alerts = ref([
  {
    id: 1,
    time: new Date('2024-01-15 14:30:25'),
    strategyName: '双均线策略',
    symbol: '000001.SZ',
    type: 'position',
    level: 'high',
    description: '持仓集中度超过阈值：45%',
    action: 'pending'
  },
  {
    id: 2,
    time: new Date('2024-01-15 14:25:10'),
    strategyName: '动量反转',
    symbol: '600519.SH',
    type: 'account',
    level: 'medium',
    description: '单日亏损达到预警线：-3.5%',
    action: 'processed'
  },
  {
    id: 3,
    time: new Date('2024-01-15 14:20:45'),
    strategyName: '系统监控',
    symbol: '',
    type: 'system',
    level: 'low',
    description: '数据同步延迟超过5分钟',
    action: 'ignored'
  }
])

// 计算属性
const filteredAlerts = computed(() => {
  let result = alerts.value

  if (alertFilter.level) {
    result = result.filter(alert => alert.level === alertFilter.level)
  }

  if (alertFilter.type) {
    result = result.filter(alert => alert.type === alertFilter.type)
  }

  pagination.total = result.length
  const start = (pagination.currentPage - 1) * pagination.pageSize
  const end = start + pagination.pageSize
  return result.slice(start, end)
})

// 方法
const getStatusClass = (level) => {
  const map = {
    high: 'status-high',
    medium: 'status-medium',
    low: 'status-low'
  }
  return map[level] || 'status-low'
}

const getTrendClass = (trend) => {
  return trend > 0 ? 'trend-up' : 'trend-down'
}

const getRiskTypeTag = (type) => {
  const map = {
    position: 'danger',
    account: 'warning',
    system: 'info'
  }
  return map[type] || 'info'
}

const getRiskTypeText = (type) => {
  const map = {
    position: '持仓风险',
    account: '账户风险',
    system: '系统风险'
  }
  return map[type] || '未知'
}

const getRiskLevelTag = (level) => {
  const map = {
    high: 'danger',
    medium: 'warning',
    low: 'info'
  }
  return map[level] || 'info'
}

const getRiskLevelText = (level) => {
  const map = {
    high: '高风险',
    medium: '中风险',
    low: '低风险'
  }
  return map[level] || '未知'
}

const getActionTag = (action) => {
  const map = {
    pending: 'warning',
    processed: 'success',
    ignored: 'info'
  }
  return map[action] || 'info'
}

const getActionText = (action) => {
  const map = {
    pending: '待处理',
    processed: '已处理',
    ignored: '已忽略'
  }
  return map[action] || '未知'
}

const formatNumber = (num) => {
  return new Intl.NumberFormat('zh-CN').format(num)
}

const formatTime = (time) => {
  return new Date(time).toLocaleTimeString('zh-CN')
}

const refreshData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    ElMessage.success('数据刷新成功')
    initCharts()
  } catch (error) {
    ElMessage.error('数据刷新失败')
  } finally {
    loading.value = false
  }
}

const exportData = () => {
  ElMessage.info('导出功能开发中')
}

const handleAlertAction = async (alert) => {
  try {
    await ElMessageBox.confirm(
      `确定要处理这条风险警报吗？\n${alert.description}`,
      '处理风险警报',
      {
        confirmButtonText: '确认处理',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    alert.action = 'processed'
    ElMessage.success('风险警报已处理')
  } catch (error) {
    // 用户取消
  }
}

const handlePageChange = (page) => {
  pagination.currentPage = page
}

// 图表初始化
let trendChartInstance = null
let typeChartInstance = null

const initCharts = () => {
  // 风险趋势图表
  if (riskTrendChart.value) {
    trendChartInstance = echarts.init(riskTrendChart.value)
    const trendOption = {
      tooltip: {
        trigger: 'axis'
      },
      legend: {
        data: ['高风险', '中风险', '低风险']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00']
      },
      yAxis: {
        type: 'value'
      },
      series: [
        {
          name: '高风险',
          type: 'line',
          data: [2, 3, 1, 4, 2, 3, 2],
          itemStyle: { color: '#f56c6c' }
        },
        {
          name: '中风险',
          type: 'line',
          data: [5, 4, 6, 3, 5, 4, 3],
          itemStyle: { color: '#e6a23c' }
        },
        {
          name: '低风险',
          type: 'line',
          data: [3, 2, 4, 2, 3, 1, 2],
          itemStyle: { color: '#909399' }
        }
      ]
    }
    trendChartInstance.setOption(trendOption)
  }

  // 风险类型分布图表
  if (riskTypeChart.value) {
    typeChartInstance = echarts.init(riskTypeChart.value)
    const typeOption = {
      tooltip: {
        trigger: 'item'
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center'
      },
      series: [
        {
          name: '风险类型',
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
            { value: 45, name: '持仓风险', itemStyle: { color: '#f56c6c' } },
            { value: 30, name: '账户风险', itemStyle: { color: '#e6a23c' } },
            { value: 25, name: '系统风险', itemStyle: { color: '#67c23a' } }
          ]
        }
      ]
    }
    typeChartInstance.setOption(typeOption)
  }
}

// 生命周期
onMounted(() => {
  initCharts()
  // 监听窗口大小变化，重绘图表
  window.addEventListener('resize', () => {
    trendChartInstance?.resize()
    typeChartInstance?.resize()
  })
})

onUnmounted(() => {
  trendChartInstance?.dispose()
  typeChartInstance?.dispose()
})
</script>

<style lang="scss" scoped>
.risk-monitor {
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

.overview-cards {
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
    font-size: 32px;
    font-weight: bold;
    margin-bottom: 8px;

    &.status-high {
      color: #f56c6c;
    }
    &.status-medium {
      color: #e6a23c;
    }
    &.status-low {
      color: #67c23a;
    }
  }

  .metric-label {
    color: #909399;
    font-size: 14px;
  }
}

.metric-footer {
  text-align: center;
  color: #909399;
  font-size: 12px;

  .trend-up {
    color: #f56c6c;
  }
  .trend-down {
    color: #67c23a;
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

.alerts-card {
  :deep(.el-card__header) {
    padding: 12px 20px;
  }
}

.alerts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alert-filters {
  display: flex;
  gap: 10px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>