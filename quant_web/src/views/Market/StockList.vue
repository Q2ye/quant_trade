<script setup lang="ts">
import {ref, reactive, onMounted, computed, h} from 'vue'
import {useRouter} from 'vue-router'
import {Table, Input, Select, Tag, Space, Button, Card, Modal, message} from 'ant-design-vue'
import type {ColumnsType} from 'ant-design-vue/es/table'
import {SearchOutlined, StarOutlined, StarFilled, LineChartOutlined, ExportOutlined,ArrowLeftOutlined} from '@ant-design/icons-vue'
import marketApi from '@/api/market'
import {StockBasic} from '@/types/entities/data'
import type {PaginatedResponse} from '@/types/api/base'

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

// 返回按钮处理
const handleBack = () => {
  router.go(-1)
}


// 响应式数据
const loading = ref(false)
const stockList = ref<Stock[]>([])
const watchlist = ref<Set<string>>(new Set())
const pagination = reactive({
  current: 1,
  pageSize: 50,
  total: 0
})

const filters = reactive({
  search: '',
  market: '',
  industry: '',
  area: '',
  list_status: 'L'
})

const industries = ref<string[]>([])
const areas = ref<string[]>([])

// 计算属性 - 使用主题变量
const tableHeaderStyle = computed(() => ({
  backgroundColor: 'var(--secondary-bg)',
  color: 'var(--text-primary)',
  fontWeight: '600'
}))

const rowHoverStyle = computed(() => ({
  backgroundColor: 'var(--hover-bg)',
  transition: 'background-color var(--transition-fast)'
}))

// 表格列定义
const columns: ColumnsType<Stock> = [
  {
    title: '代码',
    dataIndex: 'ts_code',
    key: 'ts_code',
    width: 120,
    sorter: true,
    fixed: 'left'
  },
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
    width: 100,
    fixed: 'left'
  },
  {
    title: '最新价',
    dataIndex: 'current_price',
    key: 'current_price',
    width: 100,
    sorter: true,
    customRender: ({text: price}) => price ? `¥${price.toFixed(2)}` : '-'
  },
  {
    title: '涨跌幅',
    dataIndex: 'change_percent',
    key: 'change_percent',
    width: 100,
    sorter: true,
    customRender: ({text: percent}) => {
      if (!percent) return '-'
      const color = percent >= 0 ? 'var(--success-color)' : 'var(--danger-color)'
      return h('span', {style: {color, fontWeight: '600'}}, [
        percent >= 0 ? '+' : '',
        percent.toFixed(2),
        '%'
      ])
    }
  },
  {
    title: '市值(亿)',
    dataIndex: 'market_cap',
    key: 'market_cap',
    width: 120,
    sorter: true,
    customRender: ({text: cap}) => cap ? (cap / 100000000).toFixed(2) : '-'
  },
  {
    title: '地区',
    dataIndex: 'area',
    key: 'area',
    width: 80,
    filters: areas.value.map(area => ({text: area, value: area}))
  },
  {
    title: '行业',
    dataIndex: 'industry',
    key: 'industry',
    width: 120,
    filters: industries.value.map(industry => ({text: industry, value: industry}))
  },
  {
    title: '市场',
    dataIndex: 'market',
    key: 'market',
    width: 80,
    customRender: ({text: market}) => {
      const colorMap: Record<string, string> = {
        '主板': 'var(--accent-color)',
        '创业板': 'var(--success-color)',
        '科创板': 'var(--warning-color)',
        '北交所': 'var(--danger-color)'
      }
      return h(Tag, {
        color: colorMap[market] || 'default',
        style: {
          border: `1px solid ${colorMap[market] || 'var(--border-color)'}`,
          background: 'transparent'
        }
      }, () => market)
    }
  },
  {
    title: '沪深港通',
    dataIndex: 'is_hs',
    key: 'is_hs',
    width: 100,
    customRender: ({text: is_hs}) => {
      const map: Record<string, string> = {'H': '沪股通', 'S': '深股通', 'N': '否'}
      const colorMap: Record<string, string> = {
        'H': 'var(--danger-color)',
        'S': 'var(--accent-color)',
        'N': 'var(--text-secondary)'
      }
      return h(Tag, {
        color: colorMap[is_hs],
        style: {
          border: `1px solid ${colorMap[is_hs]}`,
          background: 'transparent',
          color: colorMap[is_hs]
        }
      }, () => map[is_hs])
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    fixed: 'right',
    customRender: ({record}) => h(Space, null, () => [
      h(Button, {
        type: 'link',
        size: 'small',
        icon: watchlist.value.has(record.ts_code) ? h(StarFilled) : h(StarOutlined),
        style: {
          color: watchlist.value.has(record.ts_code) ? 'var(--warning-color)' : 'var(--text-secondary)',
          transition: 'color var(--transition-fast)'
        },
        onClick: () => toggleWatchlist(record.ts_code)
      }, () => watchlist.value.has(record.ts_code) ? '移出自选' : '加入自选'),
      h(Button, {
        type: 'link',
        size: 'small',
        icon: h(LineChartOutlined),
        style: {color: 'var(--accent-color)'},
        onClick: () => viewStockDetail(record)
      }, () => '详情')
    ])
  }
]

// 加载股票列表
const loadStockList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      size: pagination.pageSize,
      search: filters.search,
      market: filters.market,
      industry: filters.industry,
      area: filters.area,
      list_status: filters.list_status
    }

    const response: PaginatedResponse<StockBasic> = await marketApi.getStocks(params)

    if (!response.data.items) {
      throw new Error('返回数据格式不正确')
    }

    stockList.value = response.data.items.map(item => ({
      ts_code: item.ts_code,
      symbol: item.symbol,
      name: item.name,
      area: item.area || '',
      industry: item.industry || '',
      market: item.market,
      list_date: item.list_date,
      is_hs: item.is_hs || 'N',
      curr_type: item.curr_type || '',
      list_status: item.list_status || '',
    }))

    pagination.total = response.data.total || 0

    // 提取行业和地区选项
    const uniqueIndustries = [...new Set(response.data.items.map((stock: StockBasic) => stock.industry))].filter(Boolean) as string[]
    const uniqueAreas = [...new Set(response.data.items.map((stock: StockBasic) => stock.area))].filter(Boolean) as string[]
    industries.value = uniqueIndustries
    areas.value = uniqueAreas

  } catch (error: any) {
    console.error('加载股票列表失败:', error)
    message.error('加载股票列表失败: ' + (error.message || '未知错误'))

    // 设置默认数据以避免页面空白
    stockList.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const toggleWatchlist = (tsCode: string) => {
  if (watchlist.value.has(tsCode)) {
    watchlist.value.delete(tsCode)
    message.success('已移出自选股')
  } else {
    watchlist.value.add(tsCode)
    message.success('已加入自选股')
  }
  // 保存到 localStorage
  localStorage.setItem('watchlist', JSON.stringify([...watchlist.value]))
}

const viewStockDetail = (stock: Stock) => {
  // 跳转到个股详情页面
  window.open(`/market/stock/${stock.ts_code}`, '_blank')
}

const handleSearch = () => {
  pagination.current = 1
  loadStockList()
}

const handleReset = () => {
  Object.assign(filters, {
    search: '',
    market: '',
    industry: '',
    area: '',
    list_status: 'L'
  })
  handleSearch()
}

const exportData = () => {
  // 导出数据功能
  message.info('导出功能开发中...')
}

// 表格变化处理
const handleTableChange = (pag: any, filters: any, sorter: any) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadStockList()
}

onMounted(() => {
  loadStockList()
  // 加载自选股列表
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
  <div class="stock-list-page">
    <a-card
        class="stock-list-card"
        title="股票列表"
        :bordered="false"
    >
      <template #extra>
        <a-space>
          <a-button
              class="back-btn"
              @click="handleBack"
          >
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
          <a-button
              type="primary"
              @click="exportData"
              class="export-btn"
          >
            <template #icon>
              <ExportOutlined/>
            </template>
            导出数据
          </a-button>
        </a-space>
      </template>

      <div class="filter-bar">
        <a-space :size="16" wrap>
          <a-input
              v-model:value="filters.search"
              placeholder="搜索股票代码或名称"
              class="search-input"
              @press-enter="handleSearch"
          >
            <template #suffix>
              <SearchOutlined/>
            </template>
          </a-input>

          <a-select
              v-model:value="filters.market"
              placeholder="市场板块"
              class="filter-select"
              allowClear
              @change="handleSearch"
          >
            <a-select-option value="主板">主板</a-select-option>
            <a-select-option value="创业板">创业板</a-select-option>
            <a-select-option value="科创板">科创板</a-select-option>
            <a-select-option value="北交所">北交所</a-select-option>
          </a-select>

          <a-select
              v-model:value="filters.industry"
              placeholder="行业分类"
              class="filter-select"
              allowClear
              @change="handleSearch"
          >
            <a-select-option v-for="industry in industries" :key="industry" :value="industry">
              {{ industry }}
            </a-select-option>
          </a-select>

          <a-select
              v-model:value="filters.area"
              placeholder="地区"
              class="filter-select"
              allowClear
              @change="handleSearch"
          >
            <a-select-option v-for="area in areas" :key="area" :value="area">
              {{ area }}
            </a-select-option>
          </a-select>

          <a-select
              v-model:value="filters.list_status"
              placeholder="上市状态"
              class="filter-select"
              @change="handleSearch"
          >
            <a-select-option value="L">上市</a-select-option>
            <a-select-option value="D">退市</a-select-option>
            <a-select-option value="P">暂停上市</a-select-option>
          </a-select>

          <a-button
              type="primary"
              @click="handleSearch"
              class="action-btn"
          >
            搜索
          </a-button>
          <a-button
              @click="handleReset"
              class="action-btn secondary"
          >
            重置
          </a-button>
        </a-space>
      </div>

      <a-table
          class="stock-table"
          :columns="columns"
          :data-source="stockList"
          :pagination="pagination"
          :loading="loading"
          :scroll="{ x: 1500, y: 'calc(100vh - 300px)' }"
          row-key="ts_code"
          @change="handleTableChange"
      >
        <template #headerCell="{ title }">
          <span class="table-header">{{ title }}</span>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<style scoped lang="scss">
.stock-list-page {
  padding: var(--spacer-4, 1.5rem);
  background: var(--primary-bg);
  min-height: 100vh;
}

.stock-list-card {
  background: var(--card-bg);
  border-radius: var(--border-radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--card-shadow);

  :deep(.ant-card-head) {
    border-bottom: 1px solid var(--border-color);
    background: var(--secondary-bg);
    border-radius: var(--border-radius-lg) var(--border-radius-lg) 0 0;

    .ant-card-head-title {
      color: var(--text-primary);
      font-weight: 600;
      font-size: 1.25rem;
    }
  }

  :deep(.ant-card-body) {
    padding: var(--spacer-4, 1.5rem);
  }
}

.back-btn {
  background: var(--secondary-btn-bg);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  border-radius: var(--border-radius);
  font-weight: 500;
  transition: all var(--transition-fast);

  &:hover {
    background: var(--hover-bg);
    border-color: var(--accent-color);
    color: var(--accent-color);
  }
}

.filter-bar {
  margin-bottom: var(--spacer-4, 1.5rem);
  padding: var(--spacer-3, 1rem);
  background: var(--secondary-bg);
  border-radius: var(--border-radius);
  border: 1px solid var(--border-color);
}

.search-input {
  width: 240px;

  :deep(.ant-input) {
    background: var(--input-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    border-radius: var(--border-radius);
    transition: border-color var(--transition-fast);

    &:focus {
      border-color: var(--accent-color);
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent-color) 20%, transparent);
    }

    &::placeholder {
      color: var(--text-secondary);
    }
  }

  :deep(.ant-input-suffix) {
    color: var(--text-secondary);
  }
}

.filter-select {
  width: 140px;

  :deep(.ant-select-selector) {
    background: var(--input-bg) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    border-radius: var(--border-radius) !important;
    transition: border-color var(--transition-fast);

    &:hover {
      border-color: var(--accent-color) !important;
    }
  }

  :deep(.ant-select-arrow) {
    color: var(--text-secondary);
  }
}

.action-btn {
  border-radius: var(--border-radius);
  font-weight: 500;
  transition: all var(--transition-fast);

  &.secondary {
    background: var(--secondary-btn-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);

    &:hover {
      background: var(--hover-bg);
      border-color: var(--accent-color);
      color: var(--accent-color);
    }
  }
}

.export-btn {
  background: var(--action-primary-bg);
  border: none;
  border-radius: var(--border-radius);
  font-weight: 500;
  transition: all var(--transition-fast);

  &:hover {
    transform: translateY(-1px);
    box-shadow: var(--primary-btn-hover-shadow);
  }
}

.stock-table {
  :deep(.ant-table) {
    background: var(--card-bg);
    border-radius: var(--border-radius);

    .ant-table-thead > tr > th {
      background: var(--secondary-bg);
      color: var(--text-primary);
      font-weight: 600;
      border-bottom: 2px solid var(--border-color);
      padding: var(--spacer-2, 0.5rem) var(--spacer-2, 0.5rem);
    }

    .ant-table-tbody > tr {
      background: var(--card-bg);
      transition: background-color var(--transition-fast);

      &:hover > td {
        background: var(--hover-bg) !important;
      }

      > td {
        border-bottom: 1px solid var(--border-color);
        color: var(--text-primary);
        padding: var(--spacer-2, 0.5rem) var(--spacer-2, 0.5rem);
      }
    }

    .ant-table-pagination {
      margin: var(--spacer-4, 1.5rem) 0 0 0;
      padding: var(--spacer-3, 1rem) 0 0 0;
      border-top: 1px solid var(--border-color);

      .ant-pagination-item {
        background: var(--secondary-bg);
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius-sm);

        a {
          color: var(--text-primary);
        }

        &.ant-pagination-item-active {
          background: var(--accent-color);
          border-color: var(--accent-color);

          a {
            color: white;
          }
        }

        &:hover {
          border-color: var(--accent-color);
        }
      }

      .ant-pagination-prev,
      .ant-pagination-next {
        .ant-pagination-item-link {
          background: var(--secondary-bg);
          border: 1px solid var(--border-color);
          color: var(--text-primary);
          border-radius: var(--border-radius-sm);
        }
      }

      .ant-pagination-disabled {
        .ant-pagination-item-link {
          color: var(--text-secondary);
          background: var(--primary-bg);
        }
      }

      .ant-pagination-jump-prev,
      .ant-pagination-jump-next {
        .ant-pagination-item-container {
          .ant-pagination-item-ellipsis {
            color: var(--text-secondary);
          }
        }
      }
    }
  }
}

.table-header {
  color: var(--text-primary);
  font-weight: 600;
}

// 响应式调整
@media (max-width: 768px) {
  .stock-list-page {
    padding: var(--spacer-2, 0.5rem);
  }

  .filter-bar {
    padding: var(--spacer-2, 0.5rem);
  }

  .search-input {
    width: 100%;
  }

  .filter-select {
    width: 100%;
  }
}

// 主题过渡
.stock-list-page {
  transition: background-color var(--transition-normal),
  color var(--transition-normal);
}

// 加载状态样式
:deep(.ant-spin-container) {
  transition: opacity var(--transition-normal);
}

:deep(.ant-spin-nested-loading) {
  min-height: 400px;
}
</style>