<script setup lang="ts">
import { ref, reactive, onMounted, computed, h } from 'vue'
import { Table, Input, Select, Tag, Space, Button, Card, Modal, message } from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { SearchOutlined, StarOutlined, StarFilled, LineChartOutlined } from '@ant-design/icons-vue'
import marketApi from '@/api/market'
import { StockBasic } from '@/types/entities/data'
import type { PaginatedResponse } from '@/types/api/base'

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
    customRender: ({ text: price }) => price ? `¥${price.toFixed(2)}` : '-'
  },
  {
    title: '涨跌幅',
    dataIndex: 'change_percent',
    key: 'change_percent',
    width: 100,
    sorter: true,
    customRender: ({ text: percent }) => {
      if (!percent) return '-'
      const color = percent >= 0 ? '#f5222d' : '#52c41a'
      return h('span', { style: { color } }, [
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
    customRender: ({ text: cap }) => cap ? (cap / 100000000).toFixed(2) : '-'
  },
  {
    title: '地区',
    dataIndex: 'area',
    key: 'area',
    width: 80,
    filters: areas.value.map(area => ({ text: area, value: area }))
  },
  {
    title: '行业',
    dataIndex: 'industry',
    key: 'industry',
    width: 120,
    filters: industries.value.map(industry => ({ text: industry, value: industry }))
  },
  {
    title: '市场',
    dataIndex: 'market',
    key: 'market',
    width: 80,
    customRender: ({ text: market }) => {
      const colorMap: Record<string, string> = {
        '主板': 'blue',
        '创业板': 'green',
        '科创板': 'red',
        '北交所': 'orange'
      }
      return h(Tag, { color: colorMap[market] || 'default' }, () => market)
    }
  },
  {
    title: '沪深港通',
    dataIndex: 'is_hs',
    key: 'is_hs',
    width: 100,
    customRender: ({ text: is_hs }) => {
      const map: Record<string, string> = { 'H': '沪股通', 'S': '深股通', 'N': '否' }
      const colorMap: Record<string, string> = { 'H': 'red', 'S': 'blue', 'N': 'default' }
      return h(Tag, { color: colorMap[is_hs] }, () => map[is_hs])
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    fixed: 'right',
    customRender: ({ record }) => h(Space, null, () => [
      h(Button, {
        type: 'link',
        size: 'small',
        icon: watchlist.value.has(record.ts_code) ? h(StarFilled) : h(StarOutlined),
        style: { color: watchlist.value.has(record.ts_code) ? '#faad14' : undefined },
        onClick: () => toggleWatchlist(record.ts_code)
      }, () => watchlist.value.has(record.ts_code) ? '移出自选' : '加入自选'),
      h(Button, {
        type: 'link',
        size: 'small',
        icon: h(LineChartOutlined),
        onClick: () => viewStockDetail(record)
      }, () => '详情')
    ])
  }
]

// 修复后的 loadStockList 函数
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

// 修复表格变化处理
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
    <a-card title="股票列表">
      <template #extra>
        <a-button @click="exportData">导出数据</a-button>
      </template>

      <div class="filter-bar">
        <a-space :size="16" wrap>
          <a-input
            v-model:value="filters.search"
            placeholder="搜索股票代码或名称"
            style="width: 200px"
            @press-enter="handleSearch"
          >
            <template #suffix><SearchOutlined /></template>
          </a-input>

          <a-select
            v-model:value="filters.market"
            placeholder="市场板块"
            style="width: 120px"
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
            style="width: 150px"
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
            style="width: 120px"
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
            style="width: 120px"
            @change="handleSearch"
          >
            <a-select-option value="L">上市</a-select-option>
            <a-select-option value="D">退市</a-select-option>
            <a-select-option value="P">暂停上市</a-select-option>
          </a-select>

          <a-button type="primary" @click="handleSearch">搜索</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="stockList"
        :pagination="pagination"
        :loading="loading"
        :scroll="{ x: 1500, y: 600 }"
        row-key="ts_code"
        @change="handleTableChange"
      >
        <template #headerCell="{ title }">
          <span style="font-weight: bold;">{{ title }}</span>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<style scoped>
.stock-list-page {
  padding: 24px;
}

.filter-bar {
  margin-bottom: 16px;
}

:deep(.ant-table-thead > tr > th) {
  background-color: #fafafa;
  font-weight: 600;
}
</style>