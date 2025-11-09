<script setup lang="ts">
import {h, onMounted, reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Button, message, Space, Tag} from 'ant-design-vue'
import type {ColumnsType} from 'ant-design-vue/es/table'
import {
  ArrowLeftOutlined,
  ExportOutlined,
  LineChartOutlined,
  SearchOutlined,
  StarFilled,
  StarOutlined
} from '@ant-design/icons-vue'
import marketApi from '@/api/market'
import {StockBasic} from '@/types/entities/data'
import type {PaginatedResponse} from '@/types/api/base'

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
  // 保存到 localStorage
  localStorage.setItem('watchlist', JSON.stringify([...watchlist.value]))
}

/**
 * 查看股票详情
 * @param stock 股票对象
 */
const viewStockDetail = (stock: Stock) => {
  // 跳转到个股详情页面
  window.open(`/market/stock/${stock.ts_code}`, '_blank')
}

/**
 * 搜索股票
 */
const handleSearch = () => {
  pagination.current = 1
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
    list_status: 'L'
  })
  handleSearch()
}

/**
 * 导出数据
 */
const exportData = () => {
  // 导出数据功能
  message.info('导出功能开发中...')
}

/**
 * 表格变化处理
 * @param pag 分页信息
 * @param filters 筛选条件
 * @param sorter 排序条件
 */
const handleTableChange = (pag: any, filters: any, sorter: any) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadStockList()
}

/**
 * 加载股票列表数据
 */
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

/**
 * 表格列配置
 */
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

// 组件挂载时加载数据
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
          <!-- 返回按钮 -->
          <a-button class="back-btn" @click="handleBack">
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content-with-sidebar">
      <!-- 股票列表卡片 -->
      <a-card class="stock-list-card" title="股票列表" :bordered="false">
        <template #extra>
          <a-space>
            <!-- 导出数据按钮 -->
            <a-button type="primary" @click="exportData" class="export-btn">
              <template #icon>
                <ExportOutlined/>
              </template>
              导出数据
            </a-button>
          </a-space>
        </template>

        <!-- 筛选工具栏 -->
        <div class="filter-bar">
          <a-space :size="16" wrap>
            <!-- 搜索框 -->
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

            <!-- 市场筛选 -->
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

            <!-- 行业筛选 -->
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

            <!-- 地区筛选 -->
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

            <!-- 上市状态筛选 -->
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

            <!-- 操作按钮 -->
            <a-button type="primary" @click="handleSearch" class="action-btn">
              搜索
            </a-button>
            <a-button @click="handleReset" class="action-btn secondary">
              重置
            </a-button>
          </a-space>
        </div>

        <!-- 股票数据表格 -->
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
  </div>
</template>
<style scoped lang="scss">
/**
 * 股票列表页面样式
 * 基于全局主题系统实现，统一使用主题变量和混入
 */

// 导入主题混入
@use '@/assets/scss/mixins' as mixin;
@use '@/assets/scss/variables' as *;
@use 'sass:map';

// 页面主容器
.stock-list-page {
  min-height: 100vh;
  background: $primary-bg;
  transition: all $transition-normal;

  .main-content-with-sidebar {
    @include mixin.content-with-sidebar; // 应用带侧边栏的内容布局混入
    margin: 0 auto; // 水平居中
  }
}

.page-header {
  @include mixin.page-header-base;
  margin-bottom: map.get($spacers, 6);
}

// 股票列表卡片样式
.stock-list-card {
  @include mixin.card-base;
  margin-bottom: map.get($spacers, 4);
  padding: map.get($spacers, 3);
  color: white; // 文字颜色
  // 筛选工具栏样式
  .filter-bar {
    margin-bottom: map.get($spacers, 4);
    padding: map.get($spacers, 3);
    background: $secondary-bg;
    border-radius: $border-radius;
    border: $border-width solid $border-color;
  }
}

// 搜索输入框样式
.search-input {
  width: 240px;

  :deep(.ant-input) {
    background: $input-bg;
    border: $border-width solid $border-color;
    color: $text-primary;
    border-radius: $border-radius;
    transition: border-color $transition-fast;

    &:focus {
      border-color: $accent-color;
      box-shadow: 0 0 0 2px rgba($accent-color, 0.2);
    }

    &::placeholder {
      color: $text-secondary;
    }
  }

  :deep(.ant-input-suffix) {
    color: $text-secondary;
  }
}

// 筛选选择器样式
.filter-select {
  width: 140px;

  :deep(.ant-select-selector) {
    background: $input-bg !important;
    border: $border-width solid $border-color !important;
    color: $text-primary !important;
    border-radius: $border-radius !important;
    transition: border-color $transition-fast;

    &:hover {
      border-color: $accent-color !important;
    }
  }

  :deep(.ant-select-arrow) {
    color: $text-secondary;
  }
}

// 操作按钮基础样式
.action-btn {
  border-radius: $border-radius;
  font-weight: $font-weight-medium;
  transition: all $transition-fast;

  // 次要按钮样式
  &.secondary {
    background: $secondary-bg;
    border: $border-width solid $border-color;
    color: $text-primary;

    &:hover {
      background: $hover-bg;
      border-color: $accent-color;
      color: $accent-color;
    }
  }
}

// 导出按钮样式
.export-btn {
  background: $accent-color;
  border: none;
  border-radius: $border-radius;
  font-weight: $font-weight-medium;
  transition: all $transition-fast;

  &:hover {
    transform: $hover-transform;
    box-shadow: $card-hover-shadow;
  }
}

// 返回按钮样式
.back-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  border-radius: $border-radius;
  font-weight: $font-weight-medium;
  transition: all $transition-fast;
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  height: 32px;
  display: flex;
  align-items: center;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
    transform: $hover-transform;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:active {
    transform: translateY(0);
  }
}

// 表格样式
.stock-table {
  :deep(.ant-table) {
    background: $card-bg;
    border-radius: $border-radius;

    // 表头样式
    .ant-table-thead > tr > th {
      background: $secondary-bg;
      color: $text-primary;
      font-weight: $font-weight-semibold;
      border-bottom: 2px solid $border-color;
      padding: map.get($spacers, 2);
    }

    // 表格行样式
    .ant-table-tbody > tr {
      background: $card-bg;
      transition: background-color $transition-fast;

      // 行悬停效果
      &:hover > td {
        background: $hover-bg !important;
      }

      > td {
        border-bottom: 1px solid $border-color;
        color: $text-primary;
        padding: map.get($spacers, 2);
      }
    }

    // 分页器样式
    .ant-table-pagination {
      margin: map.get($spacers, 4) 0 0 0;
      padding: map.get($spacers, 3) 0 0 0;
      border-top: 1px solid $border-color;

      .ant-pagination-item {
        background: $secondary-bg;
        border: 1px solid $border-color;
        border-radius: $border-radius-sm;

        a {
          color: $text-primary;
        }

        // 激活状态
        &.ant-pagination-item-active {
          background: $accent-color;
          border-color: $accent-color;

          a {
            color: white;
          }
        }

        &:hover {
          border-color: $accent-color;
        }
      }

      // 上一页/下一页按钮
      .ant-pagination-prev,
      .ant-pagination-next {
        .ant-pagination-item-link {
          background: $secondary-bg;
          border: 1px solid $border-color;
          color: $text-primary;
          border-radius: $border-radius-sm;
        }
      }

      // 禁用状态
      .ant-pagination-disabled {
        .ant-pagination-item-link {
          color: $text-secondary;
          background: $primary-bg;
        }
      }

      // 跳页按钮
      .ant-pagination-jump-prev,
      .ant-pagination-jump-next {
        .ant-pagination-item-container {
          .ant-pagination-item-ellipsis {
            color: $text-secondary;
          }
        }
      }
    }

    // 自选股星星按钮样式
    .ant-btn-link {
      color: $text-secondary;
      transition: color $transition-fast;

      &:hover {
        color: $warning-color;
      }
    }
  }
}

// 表格表头文字样式
.table-header {
  color: $text-primary;
  font-weight: $font-weight-semibold;
}

/**
 * 响应式设计
 */

// 中等屏幕调整
@include mixin.media-breakpoint-down(md) {
  .stock-list-page {
    padding: map.get($spacers, 3);
  }

  .stock-list-card {
    margin: 0 map.get($spacers, 2) map.get($spacers, 2);
  }

  .search-input {
    width: 200px;
  }

  .filter-select {
    width: 120px;
  }
}

// 小屏幕调整
@include mixin.media-breakpoint-down(sm) {
  .stock-list-page {
    padding: map.get($spacers, 2);
  }

  .page-header {
    .header-content {
      flex-direction: column;
      gap: map.get($spacers, 3);
      text-align: center;

      .header-actions {
        order: -1;
        align-self: stretch;
        justify-content: space-between;
        margin-bottom: map.get($spacers, 2);
      }
    }
  }

  .filter-bar {
    padding: map.get($spacers, 2) !important;
  }

  .search-input {
    width: 100%;
  }

  .filter-select {
    width: 100px;
  }

  // 移动端隐藏部分操作列
  .stock-table {
    :deep(.ant-table) {
      .ant-table-thead > tr > th:nth-child(5),
      .ant-table-tbody > tr > td:nth-child(5) {
        display: none;
      }
    }
  }
}

// 加载状态样式
:deep(.ant-spin-container) {
  transition: opacity $transition-normal;
}

:deep(.ant-spin-nested-loading) {
  min-height: 400px;
}

// 主题过渡效果
.stock-list-page {
  transition: background-color $transition-normal,
  color $transition-normal;
}

// 卡片悬停效果增强
.stock-list-card {
  &:hover {
    transform: $hover-transform;
    box-shadow: $card-hover-shadow;
  }
}
</style>