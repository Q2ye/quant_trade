<!--StockList.vue - Naive UI 实现的股票列表页面-->
<script setup lang="ts">
import { ref, reactive, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NDataTable,
  DataTableColumns,
  NInput,
  NSelect,
  NTag,
  NPagination,
  NSpace,
  NGrid,
  NGi,
  NIcon,
  useMessage
} from 'naive-ui'
import SmartIcon from '@/components/common/SmartIcon.vue'

/**
 * 股票列表页面组件
 * 功能：展示A股市场股票列表，支持搜索、筛选、排序和自选股管理
 */
interface Stock {
  ts_code: string
  symbol: string
  name: string
  area: string
  industry: string
  market: string
  list_date: string
  is_hs: string
  curr_type: string
  list_status: string
  current_price?: number
  change_percent?: number
  market_cap?: number
}

const router = useRouter()
const message = useMessage()

// 响应式数据
const loading = ref(false)
const stockList = ref<Stock[]>([])
const watchlist = ref<Set<string>>(new Set())
const pagination = reactive({
  page: 1,
  pageSize: 50,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100, 200]
})

const filters = reactive({
  search: '',
  market: '',
  industry: '',
  area: '',
  list_status: 'L',
  change_percent: ''
})

const industries = ref<string[]>([])
const areas = ref<string[]>([])

// 模拟数据
const mockStocks: Stock[] = Array.from({ length: 100 }, (_, i) => ({
  ts_code: i < 9 ? `00000${i + 1}.SH` : `0000${i + 1}.SH`,
  symbol: `000${i + 1}`,
  name: `股票${i + 1}`,
  area: i % 3 === 0 ? '北京' : i % 3 === 1 ? '上海' : '深圳',
  industry: i % 5 === 0 ? '科技' : i % 5 === 1 ? '金融' : i % 5 === 2 ? '消费' : i % 5 === 3 ? '医药' : '制造',
  market: i % 4 === 0 ? '主板' : i % 4 === 1 ? '创业板' : i % 4 === 2 ? '科创板' : '北交所',
  list_date: '2020-01-01',
  is_hs: i % 3 === 0 ? 'H' : i % 3 === 1 ? 'S' : 'N',
  curr_type: 'RMB',
  list_status: 'L',
  current_price: 10 + Math.random() * 100,
  change_percent: (Math.random() - 0.5) * 10,
  market_cap: 100000000 + Math.random() * 10000000000
}))

/**
 * 返回上一页
 */
const handleBack = () => {
  router.go(-1)
}

/**
 * 切换自选股状态
 * @param tsCode 股票代码
 */
const toggleWatchlist = (tsCode: string) => {
  if (watchlist.value.has(tsCode)) {
    watchlist.value.delete(tsCode)
    message.success('已移出自选股')
  } else {
    watchlist.value.add(tsCode)
    message.success('已加入自选股')
  }
  localStorage.setItem('watchlist', JSON.stringify([...watchlist.value]))
}

/**
 * 查看股票详情
 * @param stock 股票对象
 */
const viewStockDetail = (stock: Stock) => {
  router.push(`/market/stock/${stock.ts_code}`)
}

/**
 * 搜索股票
 */
const handleSearch = () => {
  pagination.page = 1
  loadStockList()
}

/**
 * 重置筛选条件
 */
const handleReset = () => {
  Object.assign(filters, {
    search: '',
    market: '',
    industry: '',
    area: '',
    list_status: 'L',
    change_percent: ''
  })
  handleSearch()
}

/**
 * 导出数据
 */
const exportData = () => {
  message.info('导出功能开发中...')
}

/**
 * 加载股票列表数据
 */
const loadStockList = async () => {
  loading.value = true
  try {
    // 模拟API调用延迟
    await new Promise(resolve => setTimeout(resolve, 800))

    let filtered = [...mockStocks]

    // 应用筛选条件
    if (filters.search) {
      const keyword = filters.search.toLowerCase()
      filtered = filtered.filter(item =>
        item.ts_code.toLowerCase().includes(keyword) ||
        item.name.toLowerCase().includes(keyword) ||
        item.symbol.toLowerCase().includes(keyword)
      )
    }

    if (filters.market) {
      filtered = filtered.filter(item => item.market === filters.market)
    }

    if (filters.industry) {
      filtered = filtered.filter(item => item.industry === filters.industry)
    }

    if (filters.area) {
      filtered = filtered.filter(item => item.area === filters.area)
    }

    if (filters.change_percent) {
      switch (filters.change_percent) {
        case 'up':
          filtered = filtered.filter(item => item.change_percent! > 0)
          break
        case 'down':
          filtered = filtered.filter(item => item.change_percent! < 0)
          break
        case 'high_up':
          filtered = filtered.filter(item => item.change_percent! > 5)
          break
        case 'high_down':
          filtered = filtered.filter(item => item.change_percent! < -5)
          break
      }
    }

    // 更新数据
    stockList.value = filtered
    pagination.itemCount = filtered.length

    // 提取行业和地区选项
    const uniqueIndustries = [...new Set(mockStocks.map(stock => stock.industry))].filter(Boolean) as string[]
    const uniqueAreas = [...new Set(mockStocks.map(stock => stock.area))].filter(Boolean) as string[]
    industries.value = uniqueIndustries
    areas.value = uniqueAreas

  } catch (error) {
    console.error('加载股票列表失败:', error)
    message.error('加载股票列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 表格列配置
 */
const columns: DataTableColumns<Stock> = [
  {
    title: '代码',
    key: 'ts_code',
    width: 120,
    fixed: 'left',
    render(row) {
      return h('div', { class: 'stock-code' }, [
        h('div', { style: 'font-weight: 600;' }, row.ts_code),
        h(NTag, {
          size: 'small',
          type: row.market === '主板' ? 'info' :
                row.market === '创业板' ? 'success' :
                row.market === '科创板' ? 'warning' : 'error',
          style: { marginTop: '2px' }
        }, { default: () => row.market })
      ])
    }
  },
  {
    title: '名称',
    key: 'name',
    width: 100,
    fixed: 'left',
    render(row) {
      return h('span', { style: 'font-weight: 500;' }, row.name)
    }
  },
  {
    title: '最新价',
    key: 'current_price',
    width: 100,
    render(row) {
      return row.current_price ? `¥${row.current_price.toFixed(2)}` : '-'
    }
  },
  {
    title: '涨跌幅',
    key: 'change_percent',
    width: 100,
    render(row) {
      if (!row.change_percent) return '-'
      const isPositive = row.change_percent >= 0
      return h('span', {
        style: {
          color: isPositive ? 'var(--n-success-color)' : 'var(--n-error-color)',
          fontWeight: '600'
        }
      }, [
        isPositive ? '+' : '',
        row.change_percent.toFixed(2),
        '%'
      ])
    }
  },
  {
    title: '市值(亿)',
    key: 'market_cap',
    width: 120,
    render(row) {
      return row.market_cap ? (row.market_cap / 100000000).toFixed(2) : '-'
    }
  },
  {
    title: '地区',
    key: 'area',
    width: 80,
    filterOptions: areas.value.map(area => ({
      label: area,
      value: area
    })),
    filter(value, row) {
      if (!value) return true
      return row.area === value
    }
  },
  {
    title: '行业',
    key: 'industry',
    width: 120,
    filterOptions: industries.value.map(industry => ({
      label: industry,
      value: industry
    })),
    filter(value, row) {
      if (!value) return true
      return row.industry === value
    }
  },
  {
    title: '沪深港通',
    key: 'is_hs',
    width: 100,
    render(row) {
      const map: Record<string, string> = { 'H': '沪股通', 'S': '深股通', 'N': '否' }
      const colorMap: Record<string, string> = {
        'H': 'error',
        'S': 'info',
        'N': 'default'
      }
      return h(NTag, {
        type: colorMap[row.is_hs] as any,
        size: 'small',
        bordered: false
      }, { default: () => map[row.is_hs] })
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 'small' }, [
        h(NButton, {
          size: 'small',
          type: watchlist.value.has(row.ts_code) ? 'warning' : 'default',
          onClick: () => toggleWatchlist(row.ts_code)
        }, {
          icon: () => h(NIcon, null, {
            default: () => h(SmartIcon, {
              name: watchlist.value.has(row.ts_code) ? 'StarFilled' : 'StarOutlined'
            })
          }),
          default: () => watchlist.value.has(row.ts_code) ? '移出自选' : '加入自选'
        }),
        h(NButton, {
          size: 'small',
          type: 'primary',
          onClick: () => viewStockDetail(row)
        }, {
          icon: () => h(NIcon, null, { default: () => h(SmartIcon, { name: 'LineChart' }) }),
          default: () => '详情'
        })
      ])
    }
  }
]

// 市场选项
const marketOptions = [
  { label: '主板', value: '主板' },
  { label: '创业板', value: '创业板' },
  { label: '科创板', value: '科创板' },
  { label: '北交所', value: '北交所' }
]

// 涨跌幅选项
const changePercentOptions = [
  { label: '涨幅榜', value: 'up' },
  { label: '跌幅榜', value: 'down' },
  { label: '大涨(>5%)', value: 'high_up' },
  { label: '大跌(<-5%)', value: 'high_down' }
]

// 上市状态选项
const listStatusOptions = [
  { label: '上市', value: 'L' },
  { label: '退市', value: 'D' },
  { label: '暂停上市', value: 'P' }
]

// 组件挂载时加载数据
onMounted(() => {
  loadStockList()
  const savedWatchlist = localStorage.getItem('watchlist')
  if (savedWatchlist) {
    try {
      watchlist.value = new Set(JSON.parse(savedWatchlist))
    } catch (e) {
      console.error('加载自选股列表失败:', e)
      watchlist.value = new Set()
    }
  }
})
</script>

<template>
  <!-- 股票列表页面主容器 -->
  <div class="stock-list-page">
    <!-- 页面头部区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">股票列表</h1>
          <p class="page-description">A股全市场股票行情数据与统计分析</p>
        </div>
        <div class="header-actions">
          <n-button class="back-btn" @click="handleBack">
            <template #icon>
              <SmartIcon name="ArrowBack" />
            </template>
            返回
          </n-button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content-with-sidebar">
      <!-- 股票列表卡片 -->
      <n-card class="stock-list-card">
        <template #header>
          <div class="card-header">
            <span class="card-title-text">股票列表</span>
            <n-space>
              <n-button type="primary" @click="exportData" class="export-btn">
                <template #icon>
                  <SmartIcon name="Export" />
                </template>
                导出数据
              </n-button>
            </n-space>
          </div>
        </template>

        <!-- 筛选工具栏 -->
        <div class="filter-bar">
          <n-grid :cols="24" :x-gap="12" :y-gap="12">
            <!-- 搜索框 -->
            <n-gi :span="6">
              <n-input
                v-model:value="filters.search"
                placeholder="搜索股票代码或名称"
                clearable
                @input="handleSearch"
              >
                <template #prefix>
                  <SmartIcon name="Search" />
                </template>
              </n-input>
            </n-gi>

            <!-- 市场筛选 -->
            <n-gi :span="4">
              <n-select
                v-model:value="filters.market"
                placeholder="市场板块"
                clearable
                :options="marketOptions"
                @update:value="handleSearch"
              />
            </n-gi>

            <!-- 行业筛选 -->
            <n-gi :span="4">
              <n-select
                v-model:value="filters.industry"
                placeholder="行业分类"
                clearable
                :options="industries.map(i => ({ label: i, value: i }))"
                @update:value="handleSearch"
              />
            </n-gi>

            <!-- 地区筛选 -->
            <n-gi :span="3">
              <n-select
                v-model:value="filters.area"
                placeholder="地区"
                clearable
                :options="areas.map(a => ({ label: a, value: a }))"
                @update:value="handleSearch"
              />
            </n-gi>

            <!-- 涨跌幅筛选 -->
            <n-gi :span="4">
              <n-select
                v-model:value="filters.change_percent"
                placeholder="涨跌幅"
                clearable
                :options="changePercentOptions"
                @update:value="handleSearch"
              />
            </n-gi>

            <!-- 上市状态筛选 -->
            <n-gi :span="3">
              <n-select
                v-model:value="filters.list_status"
                placeholder="上市状态"
                clearable
                :options="listStatusOptions"
                @update:value="handleSearch"
              />
            </n-gi>

            <!-- 操作按钮 -->
            <n-gi :span="5">
              <n-space justify="end">
                <n-button type="primary" @click="handleSearch">
                  搜索
                </n-button>
                <n-button @click="handleReset">
                  重置
                </n-button>
              </n-space>
            </n-gi>
          </n-grid>
        </div>

        <!-- 数据表格 -->
        <div class="table-container">
          <n-data-table
            :columns="columns"
            :data="stockList"
            :loading="loading"
            :pagination="pagination"
            :scroll-x="1200"
            :row-key="(row: Stock) => row.ts_code"
            striped
            @update:page="(page: number) => pagination.page = page"
            @update:page-size="(size: number) => pagination.pageSize = size"
          />
        </div>
      </n-card>
    </div>
  </div>
</template>

<style scoped lang="scss">
.stock-list-page {
  min-height: 100vh;
  background-color: var(--n-body-color);
  transition: all 0.3s;

  .main-content-with-sidebar {
    padding: var(--content-padding);
  }
}

/* 页面头部样式 */
.page-header {
  margin-bottom: 1.5rem;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;

    .title-section {
      .page-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--n-text-color-1);
        margin-bottom: 0.25rem;
      }

      .page-description {
        font-size: 0.875rem;
        color: var(--n-text-color-2);
      }
    }

    .header-actions {
      .back-btn {
        background-color: var(--n-color-secondary);
        color: var(--n-text-color-1);
      }
    }
  }
}

/* 股票列表卡片 */
.stock-list-card {
  background-color: var(--n-card-color);
  border-radius: 8px;
  box-shadow: var(--n-box-shadow-1);

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 0;

    .card-title-text {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--n-text-color-1);
    }

    .export-btn {
      background-color: var(--n-primary-color);
      color: white;
    }
  }
}

/* 筛选工具栏 */
.filter-bar {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background-color: var(--n-color-secondary);
  border-radius: 6px;

  :deep(.n-grid) {
    align-items: center;
  }
}

/* 表格容器 */
.table-container {
  overflow-x: auto;

  :deep(.n-data-table) {
    .n-data-table-th {
      background-color: var(--n-color-secondary);
      font-weight: 600;
      color: var(--n-text-color-1);
    }

    .n-data-table-tr {
      &:nth-child(even) {
        background-color: var(--n-color-secondary);
      }

      &:hover {
        background-color: var(--n-color-hover);
      }
    }

    .stock-code {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .n-button {
      transition: all 0.2s;

      &:hover {
        transform: translateY(-1px);
      }
    }
  }
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .filter-bar {
    :deep(.n-grid) {
      grid-template-columns: repeat(2, 1fr) !important;

      .n-gi {
        grid-column: span 12 !important;
      }

      .n-gi:last-child {
        grid-column: span 24 !important;
        display: flex;
        justify-content: flex-end;
        margin-top: 0.5rem;
      }
    }
  }
}

@media (max-width: 768px) {
  .page-header {
    .header-content {
      flex-direction: column;
      gap: 1rem;
    }
  }

  .stock-list-card {
    .card-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }
  }

  .filter-bar {
    :deep(.n-grid) {
      grid-template-columns: 1fr !important;

      .n-gi {
        grid-column: span 24 !important;
      }

      .n-gi:last-child {
        justify-content: flex-start;
      }
    }
  }
}
</style>