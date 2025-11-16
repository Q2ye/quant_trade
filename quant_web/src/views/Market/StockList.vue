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
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`,
  pageSizeOptions: ['20', '50', '100', '200']
})

const filters = reactive({
  search: '',
  market: '',
  industry: '',
  area: '',
  list_status: 'L',
  change_percent: '' // 新增：涨跌幅筛选
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
    list_status: 'L',
    change_percent: ''
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
      list_status: filters.list_status,
      change_percent: filters.change_percent // 新增：涨跌幅筛选参数
    }
    console.log('请求参数:', params)
    const response: PaginatedResponse<StockBasic> = await marketApi.getStocks(params)
    console.log('API响应:', response)
    console.log('响应数据:', response.data)
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
      // current_price: item.current_price,
      // change_percent: item.change_percent,
      // market_cap: item.market_cap
    }))

    pagination.total = response.data.total || 0

    // 提取行业和地区选项
    const uniqueIndustries = [...new Set(response.data.items.map((stock: StockBasic) => stock.industry))].filter(Boolean) as string[]
    const uniqueAreas = [...new Set(response.data.items.map((stock: StockBasic) => stock.area))].filter(Boolean) as string[]
    industries.value = uniqueIndustries
    areas.value = uniqueAreas

  } catch (error: any) {
    console.error('加载股票列表失败:', error)
    console.error('错误详情:', error.response)
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
    align: 'center',
    fixed: 'left'
  },
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
    width: 100,
    align: 'center',
    fixed: 'left'
  },
  {
    title: '最新价',
    dataIndex: 'current_price',
    key: 'current_price',
    width: 100,
    align: 'center',
    customRender: ({text: price}) => price ? `¥${price.toFixed(2)}` : '-'
  },
  {
    title: '涨跌幅',
    dataIndex: 'change_percent',
    key: 'change_percent',
    width: 100,
    align: 'center',
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
    align: 'center',
    customRender: ({text: cap}) => cap ? (cap / 100000000).toFixed(2) : '-'
  },
  {
    title: '地区',
    dataIndex: 'area',
    key: 'area',
    width: 80,
    align: 'center',
    filters: areas.value.map(area => ({text: area, value: area}))
  },
  {
    title: '行业',
    dataIndex: 'industry',
    key: 'industry',
    width: 120,
    align: 'center',
    filters: industries.value.map(industry => ({text: industry, value: industry}))
  },
  {
    title: '市场',
    dataIndex: 'market',
    key: 'market',
    width: 80,
    align: 'center',
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
    align: 'center',
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
    align: 'center',
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
      <a-card class="stock-list-card" :bordered="false">
        <template #title>
          <span class="card-title-text">股票列表</span>
        </template>
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

            <!-- 涨跌幅筛选 -->
            <a-select
                v-model:value="filters.change_percent"
                placeholder="涨跌幅"
                class="filter-select"
                allowClear
                @change="handleSearch"
            >
              <a-select-option value="up">涨幅榜</a-select-option>
              <a-select-option value="down">跌幅榜</a-select-option>
              <a-select-option value="high_up">大涨(>5%)</a-select-option>
              <a-select-option value="high_down">大跌(<-5%)</a-select-option>
            </a-select>

            <!-- 上市状态筛选 -->
            <a-select
                v-model:value="filters.list_status"
                placeholder="上市状态"
                class="filter-select"
                allowClear
                @change="handleSearch"
            >
              <a-select-option value="L">上市</a-select-option>
              <a-select-option value="D">退市</a-select-option>
              <a-select-option value="P">暂停上市</a-select-option>
            </a-select>

            <!-- 操作按钮 -->
            <div class="filter-actions">
              <a-space :size="12">
                <a-button type="primary" @click="handleSearch" class="action-btn">
                  搜索
                </a-button>
                <a-button @click="handleReset" class="action-btn secondary">
                  重置
                </a-button>
              </a-space>
            </div>
          </a-space>
        </div>

        <!-- 表格容器，添加自定义滚动条 -->
        <a-table
            class="stock-table"
            :columns="columns"
            :data-source="stockList"
            :pagination="pagination"
            :loading="loading"
            :scroll="{ x: 1500 }"
            row-key="ts_code"
            @change="handleTableChange"
        >
          <template #headerCell="{ column }">
            <span class="table-header">{{ column.title }}</span>
          </template>
        </a-table>
      </a-card>

    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/scss/mixins' as mixin;
@use '@/assets/scss/variables' as *;
@use 'sass:map';

// ============================================================================
// 股票列表页面主容器
// ============================================================================
.stock-list-page {
  min-height: 100vh; // 设置最小高度为整个视口高度
  background: $primary-bg; // 使用主背景色
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

// ============================================================================
// 股票列表卡片 - 使用统一的卡片样式混入
// ============================================================================
.stock-list-card {
  @include mixin.card-base; // 应用卡片基础样式混入
  margin-bottom: map.get($spacers, 4); // 底部外边距
  padding: map.get($spacers, 3); // 内边距

  :deep(.ant-card-head) {
    font-weight: $font-weight-semibold; // 半粗体字重
    font-size: $font-size-base * 1.2; // 字体大小为基准的1.2倍
  }

  .card-title-text {
    color: $text-primary; // 卡片标题文字颜色
    font-weight: $font-weight-semibold; // 半粗体字重
  }
}

// ============================================================================
// 筛选工具栏 - 使用统一的渐变背景和边框
// ============================================================================
.filter-bar {
  margin-bottom: map.get($spacers, 4); // 底部外边距
  padding: map.get($spacers, 3); // 内边距
  background: linear-gradient(135deg, rgba($accent-color, 0.08) 0%, rgba($accent-color, 0.03) 100%); // 135度渐变背景
  border-radius: $border-radius; // 边框圆角
  border: $border-width solid $border-color; // 边框样式

  :deep(.ant-space) {
    width: 100%; // 宽度100%
    align-items: flex-start; // 子元素顶部对齐

    .filter-actions {
      margin-left: auto;
      display: flex;
      align-items: center;

      .ant-space {
        width: auto;
        align-items: center;
      }
    }
  }

  // 将按钮放在右侧
  :deep(.ant-space-item:last-child) {
    margin-left: auto;
    display: flex;
    align-items: center;
  }


}

// ============================================================================
// 按钮样式系统 - 使用统一的按钮混入
// ============================================================================

// 通用操作按钮
.action-btn {
  @include mixin.button-base; // 应用按钮基础样式混入
}

// 导出按钮 - 强调色变体
.export-btn {
  @include mixin.button-base($accent-color, white); // 应用按钮基础样式，传入强调色背景和白色文字
  height: 28px; // 固定高度
}

// 返回按钮 - 透明背景变体
.back-btn {
  @include mixin.button-base(rgba(255, 255, 255, 0.15), white); // 半透明白色背景，白色文字
}

// ============================================================================
// 表单元素样式系统 - 统一使用混入管理
// ============================================================================

// 搜索框样式
.search-input {
  width: 240px; // 固定宽度

  :deep(.ant-input-affix-wrapper) {
    @include mixin.form-element-base;
    background: $card-bg !important;
    border: $border-width solid $border-color !important;

    .ant-input {
      background: $card-bg !important;
      color: $text-primary !important;
      border: none !important;
      box-shadow: none !important;

      &::placeholder {
        color: $text-secondary !important;
        opacity: 0.7;
      }

      &:focus {
        background: $card-bg !important;
        box-shadow: none !important;
      }
    }

    &:hover, &:focus, &.ant-input-affix-wrapper-focused {
      background: $card-bg !important;
      border-color: $accent-color !important;
      box-shadow: 0 0 0 2px rgba($accent-color, 0.2) !important;
    }
  }
}

// 筛选下拉框样式
.filter-select {
  @include mixin.filter-select(false, 140px); // 应用筛选选择器混入，不包含图标，宽度140px

  :deep(.ant-select-selector) {
    @include mixin.form-element-base; // 应用表单元素基础样式混入
  }

  :deep(.ant-select-arrow) {
    color: $text-secondary; // 下拉箭头颜色
  }

  :deep(.ant-select-clear) {
    background: $card-bg; // 清除按钮背景色
    color: $text-secondary; // 清除按钮颜色
  }

  :deep(.ant-select-dropdown) {
    background: $card-bg; // 下拉菜单背景色
    border: $border-width solid $border-color; // 下拉菜单边框
    border-radius: $border-radius; // 下拉菜单圆角
    box-shadow: $card-hover-shadow; // 下拉菜单阴影

    .ant-select-item {
      color: $text-primary; // 选项文字颜色
      background: $card-bg; // 选项背景色
      transition: background-color $transition-fast; // 背景色快速过渡

      &:hover {
        background: $hover-bg; // 选项悬停背景色
      }

      &.ant-select-item-option-selected {
        background: rgba($accent-color, 0.1); // 选中选项背景色（半透明强调色）
        color: $accent-color; // 选中选项文字颜色
      }
    }

    .ant-empty-description {
      color: $text-primary; // 空状态描述文字颜色
    }
  }
}

// ============================================================================
// 表格样式系统 - 使用统一的表格基础样式
// ============================================================================
.stock-table {
  @include mixin.table-base-styles;
}
</style>