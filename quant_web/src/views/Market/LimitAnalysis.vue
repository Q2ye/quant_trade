<!-- LimitAnalysis.vue - 涨跌停分析页面 - Naive UI 实现 -->
<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
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
import { SmartIcon } from '@/components/SmartIcon'
// 导入图标
import {
  ArrowBack as ArrowBackIcon,
  ArrowDownward,
  ArrowUpward,
  BarChart as BarChartIcon,
  Download,
  Percent,
  Refresh as RefreshIcon,
  Search,
  TrendingUp,
  TableChart
} from '@vicons/ionicons5'

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
  { label: '全部', value: '' },
  { label: '上交所', value: 'SSE' },
  { label: '深交所', value: 'SZSE' },
  { label: '北交所', value: 'BSE' }
]

const marketOptions = [
  { label: '全部', value: '' },
  { label: '主板', value: '主板' },
  { label: '创业板', value: '创业板' },
  { label: '科创板', value: '科创板' }
]

const analysisTypeOptions = [
  { label: '当日涨跌停', value: 'daily' },
  { label: '连续涨停', value: 'consecutive' },
  { label: '涨跌停空间', value: 'space' },
  { label: '历史统计', value: 'history' }
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
      return h('div', { class: 'stock-code' }, [
        h('div', { class: 'code' }, row.ts_code),
        h('div', { class: 'name' }, row.name)
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
      return h('n-tag', { type: tagClass }, { default: () => tagText })
    }
  },
  {
    title: '连续天数',
    key: 'consecutive_days',
    render: (row) => {
      if (row.consecutive_days > 1) {
        return h('n-tag', { type: 'primary' }, { default: () => `${row.consecutive_days}天` })
      }
      return '-'
    }
  },
  {
    title: '涨停空间',
    key: 'space_pct',
    render: (row) => {
      const spaceClass = getSpaceClass(row.space_pct)
      return h('span', { class: spaceClass }, `${row.space_pct?.toFixed(2)}%`)
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
      }, { default: () => '详情' })
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

<template>
  <NLayout class="limit-analysis-page">
    <!-- 页面标题区域 -->
    <NLayoutHeader class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">涨跌停分析</h1>
          <p class="page-description">实时监控股票涨跌停情况与市场热度分析</p>
        </div>
        <div class="header-actions">
          <NButton
            :loading="loading"
            @click="refreshData"
            class="refresh-btn"
          >
            <template #icon>
              <NIcon>
                <SmartIcon name="Refresh" />
              </NIcon>
            </template>
            {{ loading ? '刷新中...' : '刷新数据' }}
          </NButton>
          <NButton @click="handleBack" class="back-btn">
            <template #icon>
              <NIcon>
                <SmartIcon name="ArrowBack" />
              </NIcon>
            </template>
            返回
          </NButton>
        </div>
      </div>
    </NLayoutHeader>

    <!-- 主要内容区域 -->
    <NLayoutContent class="main-content">
      <!-- 筛选条件区域 -->
      <NCard class="filter-section" title="筛选条件">
        <NForm :model="filterForm" label-placement="left" :label-width="80">
          <NGrid :cols="24" :x-gap="24">
            <NFormItemGi :span="6" label="交易日期">
              <NDatePicker
                v-model:value="filterDate"
                type="date"
                @update:value="handleDateChange"
                clearable
              />
            </NFormItemGi>
            <NFormItemGi :span="6" label="交易所">
              <NSelect
                v-model:value="filterExchange"
                :options="exchangeOptions"
                @update:value="handleFilterChange"
                clearable
              />
            </NFormItemGi>
            <NFormItemGi :span="6" label="市场类型">
              <NSelect
                v-model:value="filterMarket"
                :options="marketOptions"
                @update:value="handleFilterChange"
                clearable
              />
            </NFormItemGi>
            <NFormItemGi :span="6" label="分析类型">
              <NSelect
                v-model:value="analysisType"
                :options="analysisTypeOptions"
                @update:value="handleAnalysisTypeChange"
              />
            </NFormItemGi>
          </NGrid>
          <div class="form-actions">
            <NButton type="primary" @click="searchData" class="search-btn">
              <template #icon>
                <NIcon>
                  <SmartIcon name="Search" />
                </NIcon>
              </template>
              查询
            </NButton>
            <NButton @click="exportData" class="export-btn">
              <template #icon>
                <NIcon>
                  <SmartIcon name="Download" />
                </NIcon>
              </template>
              导出数据
            </NButton>
          </div>
        </NForm>
      </NCard>

      <!-- 统计卡片区域 -->
      <NGrid :cols="4" :x-gap="16" class="stats-section">
        <NGi>
          <NCard class="stats-card">
            <NStatistic label="涨停数量" :value="stats.upLimitCount">
              <template #prefix>
                <NIcon class="stats-icon up" :component="ArrowUpward" />
              </template>
            </NStatistic>
          </NCard>
        </NGi>
        <NGi>
          <NCard class="stats-card">
            <NStatistic label="跌停数量" :value="stats.downLimitCount">
              <template #prefix>
                <NIcon class="stats-icon down" :component="ArrowDownward" />
              </template>
            </NStatistic>
          </NCard>
        </NGi>
        <NGi>
          <NCard class="stats-card">
            <NStatistic label="连续涨停" :value="stats.consecutiveCount">
              <template #prefix>
                <NIcon class="stats-icon consecutive" :component="TrendingUp" />
              </template>
            </NStatistic>
          </NCard>
        </NGi>
        <NGi>
          <NCard class="stats-card">
            <NStatistic label="涨跌停比例" :value="stats.limitRatio" suffix="%">
              <template #prefix>
                <NIcon class="stats-icon ratio" :component="Percent" />
              </template>
            </NStatistic>
          </NCard>
        </NGi>
      </NGrid>

      <!-- 涨跌停列表 -->
      <NCard class="data-section" :title="viewTitle">
        <template #header-extra>
          <NButton @click="toggleViewMode" class="view-toggle-btn">
            <template #icon>
              <NIcon>
                <component :is="viewMode === 'table' ? BarChartIcon : TableChart" />
              </NIcon>
            </template>
            {{ viewMode === 'table' ? '图表视图' : '表格视图' }}
          </NButton>
        </template>

        <!-- 表格视图 -->
        <div v-if="viewMode === 'table'">
          <NDataTable
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
            <NIcon class="placeholder-icon" :component="BarChartIcon" />
            <p>涨跌停分析图表</p>
          </div>
        </div>
      </NCard>
    </NLayoutContent>
  </NLayout>
</template>

<style scoped lang="scss">
@use '@/assets/scss/mixins' as mixin;
@use '@/assets/scss/variables' as *;

.limit-analysis-page {
  @include mixin.content-with-base;
}

.page-header {
  @include mixin.page-header-base;
}

// 筛选区域样式
.filter-section {
  margin-bottom: map.get($spacers, 4);
  margin-top: map.get($spacers, 5);
}

.search-btn {
  @include mixin.button-base(var(--n-primary-color), white);
  padding: map.get($spacers, 2) map.get($spacers, 3);
}

// 统计卡片样式
.stats-section {
  margin-bottom: map.get($spacers, 4);
}

.stats-card {
  @include mixin.card-base;
  padding: map.get($spacers, 3);

  .stats-icon {
    &.up {
      color: var(--n-success-color);
    }

    &.down {
      color: var(--n-error-color);
    }

    &.consecutive {
      color: var(--n-primary-color);
    }

    &.ratio {
      color: var(--n-warning-color);
    }
  }
}

// 数据表格样式
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--n-card-color);
}

.table-row {
  transition: background-color $transition-fast;

  &:hover {
    background: var(--n-color-hover);
  }
}

.stock-code {
  .code {
    font-weight: 600;
    color: var(--n-text-color-base);
  }

  .name {
    font-size: $font-size-base - 2px;
    color: var(--n-text-color-2);
    margin-top: 2px;
  }
}

.space-high {
  color: var(--n-success-color);
  font-weight: 600;
}

.space-medium {
  color: var(--n-warning-color);
  font-weight: 600;
}

.space-low {
  color: var(--n-text-color-2);
}

.space-none {
  color: var(--n-error-color);
  font-weight: 600;
}

// 图表容器
.chart-container {
  height: 400px;
  @include mixin.flex-center(column);
  background: var(--n-color-secondary);
  border-radius: var(--n-border-radius);
}

// 视图切换按钮
.view-toggle-btn {
  @include mixin.button-base(transparent, var(--n-text-color-primary));
  border: 1px solid var(--n-border-color);
  padding: map.get($spacers, 1) map.get($spacers, 2);
  font-size: $font-size-base - 2px;
}
</style>