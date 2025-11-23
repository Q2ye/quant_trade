<!-- LimitAnalysis.vue - 涨跌停分析页面 -->
<!-- 基于全局主题样式系统重构，统一使用主题变量和混入 -->
<template>
  <div class="limit-analysis-page">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">涨跌停分析</h1>
          <p class="page-description">实时监控股票涨跌停情况与市场热度分析</p>
        </div>
        <div class="header-actions">
          <button class="refresh-btn" @click="refreshData" :disabled="loading">
            <Icon icon="ant-design:reload-outlined" class="refresh-icon" :class="{ refreshing: loading }"/>
            <span class="btn-text">{{ loading ? '刷新中...' : '刷新数据' }}</span>
          </button>
          <button class="back-btn" @click="handleBack">
            <Icon icon="ant-design:arrow-left-outlined"/>
            <span class="btn-text">返回</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content-with-sidebar">
      <!-- 筛选条件区域 -->
      <div class="filter-section">
        <div class="filter-card card">
          <div class="filter-content">
            <!-- 筛选表单 -->
            <div class="filter-group">
              <div class="filter-item">
                <label class="filter-label">交易日期</label>
                <input
                    type="date"
                    v-model="filterDate"
                    class="filter-input"
                    @change="handleDateChange"
                />
              </div>
              <div class="filter-item">
                <label class="filter-label">交易所</label>
                <select v-model="filterExchange" class="filter-select" @change="handleFilterChange">
                  <option value="">全部</option>
                  <option value="SSE">上交所</option>
                  <option value="SZSE">深交所</option>
                  <option value="BSE">北交所</option>
                </select>
              </div>
              <div class="filter-item">
                <label class="filter-label">市场类型</label>
                <select v-model="filterMarket" class="filter-select" @change="handleFilterChange">
                  <option value="">全部</option>
                  <option value="主板">主板</option>
                  <option value="创业板">创业板</option>
                  <option value="科创板">科创板</option>
                </select>
              </div>
            </div>
            <div class="filter-group">
              <div class="filter-item">
                <label class="filter-label">分析类型</label>
                <select v-model="analysisType" class="filter-select" @change="handleAnalysisTypeChange">
                  <option value="daily">当日涨跌停</option>
                  <option value="consecutive">连续涨停</option>
                  <option value="space">涨跌停空间</option>
                  <option value="history">历史统计</option>
                </select>
              </div>
              <div class="filter-item">
                <button class="search-btn" @click="searchData">
                  <Icon icon="mdi:magnify"/>
                  查询
                </button>
                <button class="export-btn" @click="exportData">
                  <Icon icon="ant-design:export-outlined"/>
                  <span class="btn-text">导出数据</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 统计卡片区域 -->
      <div class="stats-section">
        <div class="stats-grid">
          <!-- 涨停数量统计 -->
          <div class="stats-card card">
            <div class="stats-content">
              <div class="stats-icon up">
                <Icon icon="mdi:arrow-up-bold"/>
              </div>
              <div class="stats-info">
                <div class="stats-value">{{ stats.upLimitCount }}</div>
                <div class="stats-label">涨停数量</div>
              </div>
            </div>
          </div>

          <!-- 跌停数量统计 -->
          <div class="stats-card card">
            <div class="stats-content">
              <div class="stats-icon down">
                <Icon icon="mdi:arrow-down-bold"/>
              </div>
              <div class="stats-info">
                <div class="stats-value">{{ stats.downLimitCount }}</div>
                <div class="stats-label">跌停数量</div>
              </div>
            </div>
          </div>

          <!-- 连续涨停统计 -->
          <div class="stats-card card">
            <div class="stats-content">
              <div class="stats-icon consecutive">
                <Icon icon="mdi:chart-line"/>
              </div>
              <div class="stats-info">
                <div class="stats-value">{{ stats.consecutiveCount }}</div>
                <div class="stats-label">连续涨停</div>
              </div>
            </div>
          </div>

          <!-- 涨跌停比例统计 -->
          <div class="stats-card card">
            <div class="stats-content">
              <div class="stats-icon ratio">
                <Icon icon="mdi:percent"/>
              </div>
              <div class="stats-info">
                <div class="stats-value">{{ stats.limitRatio }}%</div>
                <div class="stats-label">涨跌停比例</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 涨跌停列表 -->
      <div class="data-section">
        <div class="data-card card">
          <div class="card-header">
            <h3 class="card-title">
              <Icon icon="mdi:format-list-bulleted"/>
              涨跌停股票列表
            </h3>
            <div class="card-actions">
              <button class="view-toggle-btn" @click="toggleViewMode">
                <Icon :icon="viewMode === 'table' ? 'mdi:view-grid' : 'mdi:table'"/>
                {{ viewMode === 'table' ? '图表视图' : '表格视图' }}
              </button>
            </div>
          </div>
          <div class="card-body">
            <!-- 表格视图 -->
            <div v-if="viewMode === 'table'" class="table-container">
              <table class="data-table">
                <thead>
                <tr>
                  <th>股票代码</th>
                  <th>收盘价</th>
                  <th>涨停价</th>
                  <th>跌停价</th>
                  <th>状态</th>
                  <th>连续天数</th>
                  <th>涨停空间</th>
                  <th>行业</th>
                  <th>操作</th>
                </tr>
                </thead>
                <tbody>
                <tr v-for="stock in limitStocks" :key="stock.ts_code" class="table-row" @click="handleRowClick(stock)">
                  <td class="stock-code">
                    <div class="code">{{ stock.ts_code }}</div>
                    <div class="name">{{ stock.name }}</div>
                  </td>
                  <td class="price">¥{{ stock.close?.toFixed(2) }}</td>
                  <td class="price">¥{{ stock.up_limit?.toFixed(2) }}</td>
                  <td class="price">¥{{ stock.down_limit?.toFixed(2) }}</td>
                  <td>
                      <span :class="['status-tag', getLimitTagClass(stock.limit_type)]">
                        {{ getLimitTypeText(stock.limit_type) }}
                      </span>
                  </td>
                  <td class="consecutive-days">
                      <span v-if="stock.consecutive_days > 1" class="consecutive-badge">
                        {{ stock.consecutive_days }}天
                      </span>
                    <span v-else>-</span>
                  </td>
                  <td>
                      <span :class="getSpaceClass(stock.space_pct)">
                        {{ stock.space_pct?.toFixed(2) }}%
                      </span>
                  </td>
                  <td class="industry">{{ stock.industry }}</td>
                  <td class="actions">
                    <button class="detail-btn" @click.stop="viewStockDetail(stock)">
                      详情
                    </button>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>

            <!-- 图表视图 -->
            <div v-else class="chart-container">
              <div class="chart-placeholder">
                <Icon icon="mdi:chart-line" class="placeholder-icon"/>
                <p>涨跌停分析图表</p>
              </div>
            </div>

            <!-- 分页控件 -->
            <div class="pagination-container">
              <div class="pagination">
                <button
                    class="pagination-btn"
                    :disabled="pagination.currentPage === 1"
                    @click="pagination.currentPage--"
                >
                  上一页
                </button>
                <span class="pagination-info">
                  第 {{ pagination.currentPage }} 页，共 {{ Math.ceil(pagination.total / pagination.pageSize) }} 页
                </span>
                <button
                    class="pagination-btn"
                    :disabled="pagination.currentPage * pagination.pageSize >= pagination.total"
                    @click="pagination.currentPage++"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {onMounted, reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Icon} from '@iconify/vue'

const router = useRouter()

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

const stats = reactive<StatsData>({
  upLimitCount: 45,
  downLimitCount: 12,
  consecutiveCount: 8,
  limitRatio: 78.9
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
  }
])

// 方法
const handleBack = () => {
  router.go(-1)
}

const refreshData = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
  } finally {
    loading.value = false
  }
}

const exportData = () => {
  console.log('导出数据')
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
    await new Promise(resolve => setTimeout(resolve, 800))
  } finally {
    loading.value = false
  }
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'table' ? 'chart' : 'table'
}

const handleRowClick = (row: LimitStock) => {
  console.log('点击行:', row)
}

const viewStockDetail = (stock: LimitStock) => {
  console.log('查看股票详情:', stock)
}

const getLimitTagClass = (type: string) => {
  const classMap: { [key: string]: string } = {
    up: 'success',
    down: 'danger',
    near_up: 'warning',
    near_down: 'info'
  }
  return classMap[type] || 'info'
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

// 初始化
onMounted(() => {
  const today = new Date()
  filterDate.value = today.toISOString().split('T')[0]
})
</script>

<style scoped lang="scss">
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color' as scssColor;

.limit-analysis-page {
  min-height: 100vh;
  background: $primary-bg;
  transition: all $transition-normal; // 所有属性使用标准过渡时间
  .main-content-with-sidebar {
    @include mixin.content-with-sidebar; // 应用带侧边栏的内容区域混入
    margin: 0 auto; // 水平居中
  }
}


// ============================================================================
// 页面头部样式 - 使用混入统一管理
// ============================================================================
.page-header {
  @include mixin.page-header-base; // 应用页面头部基础样式混入
  margin-bottom: map.get($spacers, 6); // 底部外边距使用间距映射中的第6个值
}

// 筛选区域样式
.filter-section {
  margin-bottom: map.get($spacers, 4);
}

.filter-card {
  background: $card-bg;
}

.filter-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: map.get($spacers, 3);
}

.filter-group {
  display: flex;
  gap: map.get($spacers, 4);
  align-items: flex-end;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: map.get($spacers, 1);
}

.filter-label {
  font-size: $font-size-base - 2px;
  color: $text-secondary;
  font-weight: $font-weight-medium;
}

.filter-input,
.filter-select {
  padding: map.get($spacers, 2);
  border: 1px solid $border-color;
  border-radius: $border-radius;
  background: $input-bg;
  color: $text-primary;
  font-size: $font-size-base;

  &:focus {
    outline: none;
    border-color: $accent-color;
    box-shadow: 0 0 0 2px scssColor.adjust($accent-color, $alpha: -0.8);
  }
}

.search-btn {
  @include mixin.button-base($accent-color, white);
  padding: map.get($spacers, 2) map.get($spacers, 3);
}

// 统计卡片样式
.stats-section {
  margin-bottom: map.get($spacers, 4);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: map.get($spacers, 3);
}

.stats-card {
  @include mixin.card-base;
  padding: map.get($spacers, 3);

  .stats-content {
    display: flex;
    align-items: center;
    gap: map.get($spacers, 3);
  }

  .stats-icon {
    width: 48px;
    height: 48px;
    border-radius: $border-radius;
    @include mixin.flex-center;
    font-size: 1.5rem;

    &.up {
      background: scssColor.adjust($success-color, $alpha: -0.9);
      color: $success-color;
    }

    &.down {
      background: scssColor.adjust($danger-color, $alpha: -0.9);
      color: $danger-color;
    }

    &.consecutive {
      background: scssColor.adjust($accent-color, $alpha: -0.9);
      color: $accent-color;
    }

    &.ratio {
      background: scssColor.adjust($warning-color, $alpha: -0.9);
      color: $warning-color;
    }
  }

  .stats-info {
    .stats-value {
      font-size: 1.5rem;
      font-weight: $font-weight-bold;
      color: $text-primary;
      line-height: 1.2;
    }

    .stats-label {
      font-size: $font-size-base - 2px;
      color: $text-secondary;
      margin-top: map.get($spacers, 1);
    }
  }
}

// 数据表格样式
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: $card-bg;

  th, td {
    padding: map.get($spacers, 3);
    text-align: left;
    border-bottom: 1px solid $border-color;
  }

  th {
    background: $card-header-bg;
    font-weight: $font-weight-semibold;
    color: $text-primary;
  }

  td {
    color: $text-primary;
  }
}

.table-row {
  transition: background-color $transition-fast;

  &:hover {
    background: $hover-bg;
  }
}

.stock-code {
  .code {
    font-weight: $font-weight-semibold;
    color: $text-primary;
  }

  .name {
    font-size: $font-size-base - 2px;
    color: $text-secondary;
    margin-top: 2px;
  }
}

.price {
  font-family: $font-family;
  text-align: right;
}

.status-tag {
  display: inline-block;
  padding: map.get($spacers, 1) map.get($spacers, 2);
  border-radius: $border-radius-sm;
  font-size: $font-size-base - 2px;
  font-weight: $font-weight-medium;

  &.success {
    background: scssColor.adjust($success-color, $alpha: -0.9);
    color: $success-color;
    border: 1px solid scssColor.adjust($success-color, $alpha: -0.7);
  }

  &.danger {
    background: scssColor.adjust($danger-color, $alpha: -0.9);
    color: $danger-color;
    border: 1px solid scssColor.adjust($danger-color, $alpha: -0.7);
  }

  &.warning {
    background: scssColor.adjust($warning-color, $alpha: -0.9);
    color: $warning-color;
    border: 1px solid scssColor.adjust($warning-color, $alpha: -0.7);
  }

  &.info {
    background: scssColor.adjust($info-color, $alpha: -0.9);
    color: $info-color;
    border: 1px solid scssColor.adjust($info-color, $alpha: -0.7);
  }
}

.consecutive-badge {
  background: $accent-color;
  color: white;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: $font-size-base - 4px;
  font-weight: $font-weight-semibold;
}

.space-high {
  color: $success-color;
  font-weight: $font-weight-semibold;
}

.space-medium {
  color: $warning-color;
  font-weight: $font-weight-semibold;
}

.space-low {
  color: $text-secondary;
}

.space-none {
  color: $danger-color;
  font-weight: $font-weight-semibold;
}

.industry {
  color: $text-secondary;
}

.actions .detail-btn {
  @include mixin.button-base($accent-color, white);
  padding: map.get($spacers, 1) map.get($spacers, 2);
  font-size: $font-size-base - 2px;
}

// 图表容器
.chart-container {
  height: 400px;
  @include mixin.flex-center(column);
  background: $secondary-bg;
  border-radius: $border-radius;
}

.chart-placeholder {
  text-align: center;
  color: $text-secondary;

  .placeholder-icon {
    font-size: 3rem;
    margin-bottom: map.get($spacers, 2);
    opacity: 0.5;
  }
}

// 分页样式
.pagination-container {
  margin-top: map.get($spacers, 3);
  padding-top: map.get($spacers, 3);
  border-top: 1px solid $border-color;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: map.get($spacers, 3);
}

.pagination-btn {
  @include mixin.button-base(transparent, $text-primary);
  border: 1px solid $border-color;
  padding: map.get($spacers, 2) map.get($spacers, 3);

  &:hover:not(:disabled) {
    background: $accent-color;
    color: white;
    border-color: $accent-color;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.pagination-info {
  color: $text-secondary;
  font-size: $font-size-base - 2px;
}

// 视图切换按钮
.view-toggle-btn {
  @include mixin.button-base(transparent, $text-primary);
  border: 1px solid $border-color;
  padding: map.get($spacers, 1) map.get($spacers, 2);
  font-size: $font-size-base - 2px;

  &:hover {
    background: $accent-color;
    color: white;
    border-color: $accent-color;
  }
}

// 响应式设计
@include mixin.media-breakpoint-down(lg) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@include mixin.media-breakpoint-down(md) {
  .filter-content {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-group {
    flex-direction: column;
    align-items: stretch;
  }

  .data-table {
    font-size: $font-size-base - 2px;

    th, td {
      padding: map.get($spacers, 2);
    }
  }
}

@include mixin.media-breakpoint-down(sm) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .table-container {
    overflow-x: auto;

    .data-table {
      min-width: 800px;
    }
  }

  .pagination {
    flex-direction: column;
    gap: map.get($spacers, 2);
  }
}
</style>