<template>
  <div class="limit-analysis-page">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <el-button
              class="back-btn"
              @click="handleBack"
              :icon="ArrowLeft"
              text
          >
            返回
          </el-button>
          <h1 class="page-title">
            <i class="iconify" data-icon="mdi:trending-up"></i>
            涨跌停分析
          </h1>
        </div>
        <div class="header-actions">
          <el-button type="primary" @click="refreshData" :loading="loading">
            <i class="iconify" data-icon="mdi:refresh"></i>
            刷新数据
          </el-button>
          <el-button @click="exportData">
            <i class="iconify" data-icon="mdi:export"></i>
            导出数据
          </el-button>
        </div>
      </div>
    </div>

    <!-- 筛选条件区域 -->
    <div class="filter-section">
      <el-card class="filter-card">
        <div class="filter-content">
          <div class="filter-group">
            <div class="filter-item">
              <span class="filter-label">交易日期</span>
              <el-date-picker
                  v-model="filterDate"
                  type="date"
                  placeholder="选择日期"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                  @change="handleDateChange"
              />
            </div>
            <div class="filter-item">
              <span class="filter-label">交易所</span>
              <el-select v-model="filterExchange" placeholder="选择交易所" @change="handleFilterChange">
                <el-option label="全部" value=""></el-option>
                <el-option label="上交所" value="SSE"></el-option>
                <el-option label="深交所" value="SZSE"></el-option>
                <el-option label="北交所" value="BSE"></el-option>
              </el-select>
            </div>
            <div class="filter-item">
              <span class="filter-label">市场类型</span>
              <el-select v-model="filterMarket" placeholder="选择市场" @change="handleFilterChange">
                <el-option label="全部" value=""></el-option>
                <el-option label="主板" value="主板"></el-option>
                <el-option label="创业板" value="创业板"></el-option>
                <el-option label="科创板" value="科创板"></el-option>
              </el-select>
            </div>
          </div>
          <div class="filter-group">
            <div class="filter-item">
              <span class="filter-label">分析类型</span>
              <el-select v-model="analysisType" @change="handleAnalysisTypeChange">
                <el-option label="当日涨跌停" value="daily"></el-option>
                <el-option label="连续涨停" value="consecutive"></el-option>
                <el-option label="涨跌停空间" value="space"></el-option>
                <el-option label="历史统计" value="history"></el-option>
              </el-select>
            </div>
            <div class="filter-item">
              <el-button type="primary" @click="searchData">
                <i class="iconify" data-icon="mdi:magnify"></i>
                查询
              </el-button>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 统计卡片区域 -->
    <div class="stats-section">
      <div class="stats-grid">
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon up">
              <i class="iconify" data-icon="mdi:arrow-up-bold"></i>
            </div>
            <div class="stats-info">
              <div class="stats-value">{{ stats.upLimitCount }}</div>
              <div class="stats-label">涨停数量</div>
            </div>
          </div>
        </el-card>
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon down">
              <i class="iconify" data-icon="mdi:arrow-down-bold"></i>
            </div>
            <div class="stats-info">
              <div class="stats-value">{{ stats.downLimitCount }}</div>
              <div class="stats-label">跌停数量</div>
            </div>
          </div>
        </el-card>
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon consecutive">
              <i class="iconify" data-icon="mdi:chart-line"></i>
            </div>
            <div class="stats-info">
              <div class="stats-value">{{ stats.consecutiveCount }}</div>
              <div class="stats-label">连续涨停</div>
            </div>
          </div>
        </el-card>
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon ratio">
              <i class="iconify" data-icon="mdi:percent"></i>
            </div>
            <div class="stats-info">
              <div class="stats-value">{{ stats.limitRatio }}%</div>
              <div class="stats-label">涨跌停比例</div>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="content-section">
      <!-- 涨跌停列表 -->
      <el-card class="data-card">
        <template #header>
          <div class="card-header">
            <h3 class="card-title">
              <i class="iconify" data-icon="mdi:format-list-bulleted"></i>
              涨跌停股票列表
            </h3>
            <div class="card-actions">
              <el-button text @click="toggleViewMode">
                <i class="iconify" :data-icon="viewMode === 'table' ? 'mdi:view-grid' : 'mdi:table'"></i>
                {{ viewMode === 'table' ? '图表视图' : '表格视图' }}
              </el-button>
            </div>
          </div>
        </template>

        <!-- 表格视图 -->
        <div v-if="viewMode === 'table'" class="table-container">
          <el-table
              :data="limitStocks"
              v-loading="loading"
              stripe
              style="width: 100%"
              @row-click="handleRowClick"
          >
            <el-table-column prop="ts_code" label="股票代码" width="120">
              <template #default="{ row }">
                <div class="stock-code">
                  <span class="code">{{ row.ts_code }}</span>
                  <span class="name">{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="close" label="收盘价" width="100" align="right">
              <template #default="{ row }">
                ¥{{ row.close?.toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="up_limit" label="涨停价" width="100" align="right">
              <template #default="{ row }">
                ¥{{ row.up_limit?.toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="down_limit" label="跌停价" width="100" align="right">
              <template #default="{ row }">
                ¥{{ row.down_limit?.toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="limit_type" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getLimitTagType(row.limit_type)" effect="plain">
                  {{ getLimitTypeText(row.limit_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="consecutive_days" label="连续天数" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.consecutive_days > 1" class="consecutive-badge">
                  {{ row.consecutive_days }}天
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="space_pct" label="涨停空间" width="120" align="right">
              <template #default="{ row }">
                <span :class="getSpaceClass(row.space_pct)">
                  {{ row.space_pct?.toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="industry" label="行业" min-width="120" show-overflow-tooltip>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click.stop="viewStockDetail(row)">
                  详情
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 图表视图 -->
        <div v-else class="chart-container">
          <div class="chart-view">
            <div id="limitAnalysisChart" style="height: 400px;"></div>
          </div>
        </div>

        <!-- 分页 -->
        <div class="pagination-container">
          <el-pagination
              v-model:current-page="pagination.currentPage"
              v-model:page-size="pagination.pageSize"
              :total="pagination.total"
              :page-sizes="[20, 50, 100, 200]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
          />
        </div>
      </el-card>

      <!-- 分析图表区域 -->
      <div class="analysis-section">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card class="analysis-card">
              <template #header>
                <h4 class="card-title">涨跌停分布</h4>
              </template>
              <div id="limitDistributionChart" style="height: 300px;"></div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card class="analysis-card">
              <template #header>
                <h4 class="card-title">行业分布</h4>
              </template>
              <div id="industryDistributionChart" style="height: 300px;"></div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </div>

    <!-- 股票详情对话框 -->
    <el-dialog
        v-model="detailDialogVisible"
        title="股票详情"
        width="800px"
        destroy-on-close
    >
      <StockDetailPanel
          v-if="detailDialogVisible"
          :stock-code="selectedStock?.ts_code"
          :stock-name="selectedStock?.name"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {nextTick, onMounted, reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import * as echarts from 'echarts'
import StockDetailPanel from "@/components/market/StockDetailPanel.vue";


const router = useRouter()
const handleBack = () => {
  router.go(-1)
}

// 类型定义
interface LimitStock {
  ts_code: string
  name: string
  close: number
  up_limit: number
  down_limit: number
  limit_type: 'up' | 'down' | 'near_up' | 'near_down'
  consecutive_days: number
  space_pct: number
  industry: string
  exchange: string
  market: string
}

interface StatsData {
  upLimitCount: number
  downLimitCount: number
  consecutiveCount: number
  limitRatio: number
}

interface Pagination {
  currentPage: number
  pageSize: number
  total: number
}

// 响应式数据
const loading = ref(false)
const filterDate = ref('')
const filterExchange = ref('')
const filterMarket = ref('')
const analysisType = ref('daily')
const viewMode = ref('table')
const detailDialogVisible = ref(false)
const selectedStock = ref<LimitStock | null>(null)

const stats = reactive<StatsData>({
  upLimitCount: 0,
  downLimitCount: 0,
  consecutiveCount: 0,
  limitRatio: 0
})

const pagination = reactive<Pagination>({
  currentPage: 1,
  pageSize: 20,
  total: 0
})

const limitStocks = ref<LimitStock[]>([
  {
    ts_code: '000001.SZ',
    name: '平安银行',
    close: 12.45,
    up_limit: 13.70,
    down_limit: 11.21,
    limit_type: 'near_up',
    consecutive_days: 0,
    space_pct: 2.5,
    industry: '银行',
    exchange: 'SZSE',
    market: '主板'
  },
  {
    ts_code: '600000.SH',
    name: '浦发银行',
    close: 7.23,
    up_limit: 7.95,
    down_limit: 6.51,
    limit_type: 'up',
    consecutive_days: 3,
    space_pct: 0,
    industry: '银行',
    exchange: 'SSE',
    market: '主板'
  }
])

// 图表实例
let limitAnalysisChart: echarts.ECharts | null = null
let limitDistributionChart: echarts.ECharts | null = null
let industryDistributionChart: echarts.ECharts | null = null

// 方法
const refreshData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    ElMessage.success('数据刷新成功')
    updateCharts()
  } catch (error) {
    ElMessage.error('数据刷新失败')
  } finally {
    loading.value = false
  }
}

const exportData = () => {
  ElMessage.info('导出功能开发中')
}

const handleDateChange = () => {
  searchData()
}

const handleFilterChange = () => {
  searchData()
}

const handleAnalysisTypeChange = () => {
  searchData()
}

const searchData = async () => {
  loading.value = true
  try {
    // 模拟搜索
    await new Promise(resolve => setTimeout(resolve, 800))
    updateStats()
    updateCharts()
  } catch (error) {
    ElMessage.error('查询失败')
  } finally {
    loading.value = false
  }
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'table' ? 'chart' : 'table'
  if (viewMode.value === 'chart') {
    nextTick(() => {
      initLimitAnalysisChart()
    })
  }
}

const handleRowClick = (row: LimitStock) => {
  console.log('点击行:', row)
}

const viewStockDetail = (stock: LimitStock) => {
  selectedStock.value = stock
  detailDialogVisible.value = true
}

const getLimitTagType = (type: string) => {
  const typeMap: { [key: string]: string } = {
    up: 'success',
    down: 'danger',
    near_up: 'warning',
    near_down: 'info'
  }
  return typeMap[type] || 'info'
}

const getLimitTypeText = (type: string) => {
  const textMap: { [key: string]: string } = {
    up: '涨停',
    down: '跌停',
    near_up: '接近涨停',
    near_down: '接近跌停'
  }
  return textMap[type] || type
}

const getSpaceClass = (spacePct: number) => {
  if (spacePct > 5) return 'space-high'
  if (spacePct > 2) return 'space-medium'
  if (spacePct > 0) return 'space-low'
  return 'space-none'
}

const handleSizeChange = (size: number) => {
  pagination.pageSize = size
  searchData()
}

const handleCurrentChange = (page: number) => {
  pagination.currentPage = page
  searchData()
}

const updateStats = () => {
  // 模拟统计数据更新
  stats.upLimitCount = 45
  stats.downLimitCount = 12
  stats.consecutiveCount = 8
  stats.limitRatio = 78.9
}

const initCharts = () => {
  initLimitAnalysisChart()
  initLimitDistributionChart()
  initIndustryDistributionChart()
}

const initLimitAnalysisChart = () => {
  const chartDom = document.getElementById('limitAnalysisChart')
  if (!chartDom) return

  limitAnalysisChart = echarts.init(chartDom)
  const option = {
    title: {
      text: '涨跌停分析',
      left: 'center'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['涨停', '跌停', '接近涨停'],
      top: '10%'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '20%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['09:30', '10:30', '11:30', '13:00', '14:00', '15:00']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '涨停',
        type: 'line',
        data: [5, 12, 25, 35, 42, 45],
        lineStyle: {
          color: '#4caf50'
        },
        itemStyle: {
          color: '#4caf50'
        }
      },
      {
        name: '跌停',
        type: 'line',
        data: [2, 5, 8, 10, 11, 12],
        lineStyle: {
          color: '#f44336'
        },
        itemStyle: {
          color: '#f44336'
        }
      },
      {
        name: '接近涨停',
        type: 'line',
        data: [15, 25, 35, 28, 22, 18],
        lineStyle: {
          color: '#ff9800'
        },
        itemStyle: {
          color: '#ff9800'
        }
      }
    ]
  }
  limitAnalysisChart.setOption(option)
}

const initLimitDistributionChart = () => {
  const chartDom = document.getElementById('limitDistributionChart')
  if (!chartDom) return

  limitDistributionChart = echarts.init(chartDom)
  const option = {
    tooltip: {
      trigger: 'item'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '涨跌停分布',
        type: 'pie',
        radius: '70%',
        data: [
          {value: 45, name: '涨停', itemStyle: {color: '#4caf50'}},
          {value: 12, name: '跌停', itemStyle: {color: '#f44336'}},
          {value: 23, name: '接近涨停', itemStyle: {color: '#ff9800'}},
          {value: 15, name: '接近跌停', itemStyle: {color: '#2196f3'}}
        ],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  limitDistributionChart.setOption(option)
}

const initIndustryDistributionChart = () => {
  const chartDom = document.getElementById('industryDistributionChart')
  if (!chartDom) return

  industryDistributionChart = echarts.init(chartDom)
  const option = {
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
      type: 'value'
    },
    yAxis: {
      type: 'category',
      data: ['计算机', '医药生物', '电子', '机械设备', '化工', '传媒', '通信']
    },
    series: [
      {
        name: '涨停数量',
        type: 'bar',
        data: [12, 8, 15, 6, 9, 4, 7],
        itemStyle: {
          color: '#4caf50'
        }
      }
    ]
  }
  industryDistributionChart.setOption(option)
}

const updateCharts = () => {
  if (limitAnalysisChart) {
    limitAnalysisChart.resize()
  }
  if (limitDistributionChart) {
    limitDistributionChart.resize()
  }
  if (industryDistributionChart) {
    industryDistributionChart.resize()
  }
}

// 初始化
onMounted(() => {
  // 设置默认日期为今天
  const today = new Date()
  filterDate.value = today.toISOString().split('T')[0]

  updateStats()
  initCharts()

  // 监听窗口大小变化
  window.addEventListener('resize', updateCharts)
})
</script>

<style scoped lang="scss">
@use '@/assets/scss/mixins';

.limit-analysis-page {
  padding: var(--spacer-4);
  background: var(--primary-bg);
  min-height: 100vh;
}


.page-header {
  margin-bottom: var(--spacer-4);

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-left {
      display: flex;
      align-items: center;
      gap: var(--spacer-3);
    }

    .back-btn {
      color: var(--text-secondary);
      border: 1px solid var(--border-color);
      background: var(--secondary-bg);
      transition: all var(--transition-fast);

      &:hover {
        color: var(--accent-color);
        border-color: var(--accent-color);
        background: var(--hover-bg);
      }
    }

    .page-title {
      display: flex;
      align-items: center;
      gap: var(--spacer-2);
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;

      .iconify {
        color: var(--accent-color);
        font-size: 1.75rem;
      }
    }

    .header-actions {
      display: flex;
      gap: var(--spacer-2);
    }
  }
}

.filter-section {
  margin-bottom: var(--spacer-4);

  .filter-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);

    .filter-content {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      flex-wrap: wrap;
      gap: var(--spacer-3);

      .filter-group {
        display: flex;
        gap: var(--spacer-4);
        align-items: flex-end;

        .filter-item {
          display: flex;
          flex-direction: column;
          gap: var(--spacer-1);

          .filter-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 500;
          }
        }
      }
    }
  }
}

.stats-section {
  margin-bottom: var(--spacer-4);

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--spacer-3);

    .stats-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      transition: transform var(--transition-normal), box-shadow var(--transition-normal);

      &:hover {
        transform: var(--hover-transform);
        box-shadow: var(--hover-shadow);
      }

      .stats-content {
        display: flex;
        align-items: center;
        gap: var(--spacer-3);

        .stats-icon {
          width: 48px;
          height: 48px;
          border-radius: var(--border-radius);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;

          &.up {
            background: rgba(76, 175, 80, 0.1);
            color: var(--success-color);
          }

          &.down {
            background: rgba(244, 67, 54, 0.1);
            color: var(--danger-color);
          }

          &.consecutive {
            background: rgba(33, 150, 243, 0.1);
            color: var(--accent-color);
          }

          &.ratio {
            background: rgba(255, 152, 0, 0.1);
            color: var(--warning-color);
          }
        }

        .stats-info {
          .stats-value {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.2;
          }

          .stats-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: var(--spacer-1);
          }
        }
      }
    }
  }
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacer-4);
}

.data-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .card-title {
      display: flex;
      align-items: center;
      gap: var(--spacer-2);
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;

      .iconify {
        color: var(--accent-color);
      }
    }
  }

  .table-container {
    .stock-code {
      display: flex;
      flex-direction: column;

      .code {
        font-weight: 600;
        color: var(--text-primary);
      }

      .name {
        font-size: 0.75rem;
        color: var(--text-secondary);
        margin-top: 2px;
      }
    }

    .consecutive-badge {
      background: var(--accent-color);
      color: white;
      padding: 2px 6px;
      border-radius: 10px;
      font-size: 0.75rem;
      font-weight: 600;
    }

    .space-high {
      color: var(--success-color);
      font-weight: 600;
    }

    .space-medium {
      color: var(--warning-color);
      font-weight: 600;
    }

    .space-low {
      color: var(--text-secondary);
    }

    .space-none {
      color: var(--danger-color);
      font-weight: 600;
    }
  }

  .chart-container {
    .chart-view {
      height: 400px;
    }
  }

  .pagination-container {
    display: flex;
    justify-content: flex-end;
    margin-top: var(--spacer-3);
    padding-top: var(--spacer-3);
    border-top: 1px solid var(--border-color);
  }
}

.analysis-section {
  .analysis-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);

    .card-title {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;
    }
  }
}

// 响应式设计
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}

@media (max-width: 768px) {
  .limit-analysis-page {
    padding: var(--spacer-2);
  }

  .page-header .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacer-2);
  }

  .filter-content {
    flex-direction: column;
    align-items: stretch !important;
  }

  .filter-group {
    flex-direction: column;
    align-items: stretch !important;
  }

  .stats-grid {
    grid-template-columns: 1fr !important;
  }

  .analysis-section .el-col {
    width: 100%;
  }
}

// 滚动条样式
:deep(.el-table__body-wrapper) {
  @include mixins.scrollbar;
}

// 加载状态
:deep(.el-loading-mask) {
  background-color: rgba(var(--primary-bg), 0.8);
}

:deep(.el-loading-spinner .path) {
  stroke: var(--accent-color);
}
</style>