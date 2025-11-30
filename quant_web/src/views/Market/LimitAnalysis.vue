<!-- LimitAnalysis.vue - 涨跌停分析页面 - Naive UI 实现 -->
<template>
  <n-layout class="limit-analysis-page">
    <!-- 页面标题区域 -->
    <n-layout-header class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">涨跌停分析</h1>
          <p class="page-description">实时监控股票涨跌停情况与市场热度分析</p>
        </div>
        <div class="header-actions">
          <n-button
              :loading="loading"
              @click="refreshData"
              class="refresh-btn"
          >
            <template #icon>
              <n-icon>
                <RefreshIcon/>
              </n-icon>
            </template>
            {{ loading ? '刷新中...' : '刷新数据' }}
          </n-button>
          <n-button @click="handleBack" class="back-btn">
            <template #icon>
              <n-icon>
                <ArrowBackIcon/>
              </n-icon>
            </template>
            返回
          </n-button>
        </div>
      </div>
    </n-layout-header>

    <!-- 主要内容区域 -->
    <n-layout-content class="main-content">
      <!-- 筛选条件区域 -->
      <n-card class="filter-section" title="筛选条件">
        <n-form :model="filterForm" label-placement="left" :label-width="80">
          <n-grid :cols="24" :x-gap="24">
            <n-form-item-gi :span="6" label="交易日期">
              <n-date-picker
                  v-model:value="filterDate"
                  type="date"
                  @update:value="handleDateChange"
                  clearable
              />
            </n-form-item-gi>
            <n-form-item-gi :span="6" label="交易所">
              <n-select
                  v-model:value="filterExchange"
                  :options="exchangeOptions"
                  @update:value="handleFilterChange"
                  clearable
              />
            </n-form-item-gi>
            <n-form-item-gi :span="6" label="市场类型">
              <n-select
                  v-model:value="filterMarket"
                  :options="marketOptions"
                  @update:value="handleFilterChange"
                  clearable
              />
            </n-form-item-gi>
            <n-form-item-gi :span="6" label="分析类型">
              <n-select
                  v-model:value="analysisType"
                  :options="analysisTypeOptions"
                  @update:value="handleAnalysisTypeChange"
              />
            </n-form-item-gi>
          </n-grid>
          <div class="form-actions">
            <n-button type="primary" @click="searchData" class="search-btn">
              <template #icon>
                <n-icon>
                  <SearchIcon/>
                </n-icon>
              </template>
              查询
            </n-button>
            <n-button @click="exportData" class="export-btn">
              <template #icon>
                <n-icon>
                  <ExportIcon/>
                </n-icon>
              </template>
              导出数据
            </n-button>
          </div>
        </n-form>
      </n-card>

      <!-- 统计卡片区域 -->
      <n-grid :cols="4" :x-gap="16" class="stats-section">
        <n-gi>
          <n-card class="stats-card">
            <n-statistic label="涨停数量" :value="stats.upLimitCount">
              <template #prefix>
                <n-icon class="stats-icon up" :component="ArrowUpwardIcon"/>
              </template>
            </n-statistic>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card class="stats-card">
            <n-statistic label="跌停数量" :value="stats.downLimitCount">
              <template #prefix>
                <n-icon class="stats-icon down" :component="ArrowDownwardIcon"/>
              </template>
            </n-statistic>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card class="stats-card">
            <n-statistic label="连续涨停" :value="stats.consecutiveCount">
              <template #prefix>
                <n-icon class="stats-icon consecutive" :component="TrendingUpIcon"/>
              </template>
            </n-statistic>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card class="stats-card">
            <n-statistic label="涨跌停比例" :value="stats.limitRatio" suffix="%">
              <template #prefix>
                <n-icon class="stats-icon ratio" :component="PercentIcon"/>
              </template>
            </n-statistic>
          </n-card>
        </n-gi>
      </n-grid>

      <!-- 涨跌停列表 -->
      <n-card class="data-section" :title="viewTitle">
        <template #header-extra>
          <n-button @click="toggleViewMode" class="view-toggle-btn">
            <template #icon>
              <n-icon>
                <component :is="viewMode === 'table' ? BarChartIcon : TableChartIcon"/>
              </n-icon>
            </template>
            {{ viewMode === 'table' ? '图表视图' : '表格视图' }}
          </n-button>
        </template>

        <!-- 表格视图 -->
        <div v-if="viewMode === 'table'">
          <n-data-table
              :columns="columns"
              :data="limitStocks"
              :pagination="paginationConfig"
              :bordered="false"
              @update:page="handlePageChange"
          />
        </div>

        <!-- 图表视图 -->
        <div v-else class="chart-container">
          <div class="chart-placeholder">
            <n-icon class="placeholder-icon" :component="BarChartIcon"/>
            <p>涨跌停分析图表</p>
          </div>
        </div>
      </n-card>
    </n-layout-content>
  </n-layout>
</template>

<script setup lang="ts">
import {computed, h, onMounted, reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {
  DataTableColumns,
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItemGi,
  NGi,
  NGrid,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NSelect,
  NStatistic,
  useMessage
} from 'naive-ui'
import {
  ArrowBackIosFilled as ArrowBackIcon,
  ArrowDownwardFilled as ArrowDownwardIcon,
  ArrowUpwardFilled as ArrowUpwardIcon,
  BarChartFilled as BarChartIcon,
  ExploreRound as ExportIcon,
  PercentFilled as PercentIcon,
  RefreshRound as RefreshIcon,
  SearchFilled as SearchIcon,
  TableChartFilled as TableChartIcon,
  TrendingUpFilled as TrendingUpIcon
} from '@vicons/material'

const router = useRouter()
const message = useMessage()

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

// 响应式数据
const loading = ref(false)
const filterDate = ref<number | null>(null)
const filterExchange = ref<string | null>(null)
const filterMarket = ref<string | null>(null)
const analysisType = ref('daily')
const viewMode = ref('table')

const stats = reactive<StatsData>({
  upLimitCount: 45,
  downLimitCount: 12,
  consecutiveCount: 8,
  limitRatio: 78.9
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

// 选项配置
const exchangeOptions = [
  {label: '全部', value: ''},
  {label: '上交所', value: 'SSE'},
  {label: '深交所', value: 'SZSE'},
  {label: '北交所', value: 'BSE'}
]

const marketOptions = [
  {label: '全部', value: ''},
  {label: '主板', value: '主板'},
  {label: '创业板', value: '创业板'},
  {label: '科创板', value: '科创板'}
]

const analysisTypeOptions = [
  {label: '当日涨跌停', value: 'daily'},
  {label: '连续涨停', value: 'consecutive'},
  {label: '涨跌停空间', value: 'space'},
  {label: '历史统计', value: 'history'}
]

// 分页配置
const paginationConfig = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => {
    paginationConfig.page = page
  },
  onUpdatePageSize: (pageSize: number) => {
    paginationConfig.pageSize = pageSize
    paginationConfig.page = 1
  }
})

// 计算属性
const viewTitle = computed(() => {
  return viewMode.value === 'table' ? '涨跌停股票列表' : '涨跌停分析图表'
})

const filterForm = computed(() => ({
  date: filterDate.value,
  exchange: filterExchange.value,
  market: filterMarket.value,
  analysisType: analysisType.value
}))

// 表格列定义
const columns: DataTableColumns<LimitStock> = [
  {
    title: '股票代码',
    key: 'ts_code',
    render: (row) => {
      return h('div', {class: 'stock-code'}, [
        h('div', {class: 'code'}, row.ts_code),
        h('div', {class: 'name'}, row.name)
      ])
    }
  },
  {
    title: '收盘价',
    key: 'close',
    render: (row) => `¥${row.close?.toFixed(2)}`
  },
  {
    title: '涨停价',
    key: 'up_limit',
    render: (row) => `¥${row.up_limit?.toFixed(2)}`
  },
  {
    title: '跌停价',
    key: 'down_limit',
    render: (row) => `¥${row.down_limit?.toFixed(2)}`
  },
  {
    title: '状态',
    key: 'limit_type',
    render: (row) => {
      const tagClass = getLimitTagClass(row.limit_type)
      const tagText = getLimitTypeText(row.limit_type)
      return h('n-tag', {type: tagClass}, {default: () => tagText})
    }
  },
  {
    title: '连续天数',
    key: 'consecutive_days',
    render: (row) => {
      if (row.consecutive_days > 1) {
        return h('n-tag', {type: 'primary'}, {default: () => `${row.consecutive_days}天`})
      }
      return '-'
    }
  },
  {
    title: '涨停空间',
    key: 'space_pct',
    render: (row) => {
      const spaceClass = getSpaceClass(row.space_pct)
      return h('span', {class: spaceClass}, `${row.space_pct?.toFixed(2)}%`)
    }
  },
  {
    title: '行业',
    key: 'industry',
    render: (row) => row.industry
  },
  {
    title: '操作',
    key: 'actions',
    render: (row) => {
      return h(NButton, {
        size: 'small',
        type: 'primary',
        onClick: (e: Event) => {
          e.stopPropagation()
          viewStockDetail(row)
        }
      }, {default: () => '详情'})
    }
  }
]

// 方法
const handleBack = () => {
  router.go(-1)
}

const refreshData = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('数据刷新成功')
  } finally {
    loading.value = false
  }
}

const exportData = () => {
  message.info('导出数据功能')
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
    message.success('查询成功')
  } finally {
    loading.value = false
  }
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'table' ? 'chart' : 'table'
}

const handlePageChange = (page: number) => {
  paginationConfig.page = page
}

const viewStockDetail = (stock: LimitStock) => {
  message.info(`查看股票详情: ${stock.name}`)
}

const getLimitTagClass = (type: string) => {
  const classMap: { [key: string]: any } = {
    up: 'success',
    down: 'error',
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
  filterDate.value = today.getTime()
})
</script>

<style scoped lang="scss">
@use '@/assets/scss/mixins' as mixin;
@use '@/assets/scss/variables' as *;
@use 'sass:map';
@use 'sass:color' as scssColor;

.limit-analysis-page {
  @include mixin.content-with-base;

  .main-content {
    @include mixin.content-with-sidebar; // 应用带侧边栏的内容区域混入
    margin: 0 auto; // 水平居中
  }

}

// ============================================================================
// 页面头部样式 - 使用混入统一管理
// ============================================================================
// 使用专门为 Naive UI 优化的混入
.page-header {
  @include mixin.page-header-base;
}

// 筛选区域样式
.filter-section {
  margin-bottom: map.get($spacers, 4);
  margin-top: map.get($spacers, 5); // 顶部外边距：使用spacers映射中的第6个值
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