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
            <a-button type="primary" @click="handleSearch" class="action-btn">
              搜索
            </a-button>
            <a-button @click="handleReset" class="action-btn secondary">
              重置
            </a-button>
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
@use 'sass:color' as lcolor ;

// 股票列表页面主容器样式
.stock-list-page {
  min-height: 100vh; // 最小高度为视口高度
  background: $primary-bg; // 主背景色
  transition: all $transition-normal; // 过渡动画

  .main-content-with-sidebar {
    @include mixin.content-with-sidebar; // 应用带侧边栏的内容区域样式
    margin: 0 auto; // 水平居中
  }
}

// 页面头部样式
.page-header {
  @include mixin.page-header-base; // 应用页面头部基础样式
  margin-bottom: map.get($spacers, 6); // 底部外边距

  .page-title {
    color: white !important; // 标题文字颜色（白色）
  }

  .page-description {
    color: rgba(255, 255, 255, 0.9) !important; // 描述文字颜色（半透明白色）
  }
}

// 股票列表卡片样式
.stock-list-card {
  @include mixin.card-base; // 应用卡片基础样式
  margin-bottom: map.get($spacers, 4); // 底部外边距
  padding: map.get($spacers, 3); // 内边距

  // 卡片标题颜色优化
  :deep(.ant-card-head) {
    color: $text-primary !important; // 主要文字颜色
    font-weight: $font-weight-semibold; // 半粗体
    font-size: $font-size-base * 1.2; // 增大字体大小
  }

  .card-title-text {
    color: $text-primary; // 主要文字颜色
    font-weight: $font-weight-semibold; // 半粗体
  }

  // 筛选工具栏样式
  .filter-bar {
    margin-bottom: map.get($spacers, 4); // 底部外边距
    padding: map.get($spacers, 3); // 内边距
    background: $secondary-bg; // 次要背景色
    border-radius: $border-radius; // 圆角
    border: $border-width solid $border-color; // 边框
  }

  // 卡片悬停效果
  &:hover {
    transform: $hover-transform; // 悬停变换效果
    box-shadow: $card-hover-shadow; // 悬停阴影效果
  }
}

// 表格容器滚动条优化
.stock-table-container {
  max-height: 60vh; // 最大高度为视口高度的60%
  overflow-y: auto; // 垂直方向溢出时显示滚动条
  position: relative; // 相对定位
  @include mixin.custom-scrollbar() // 应用自定义滚动条样式
}

// 操作按钮样式
.action-btn {
  border-radius: $border-radius; // 圆角
  font-weight: $font-weight-medium; // 中等字重
  transition: all $transition-fast; // 快速过渡动画

  // 次要按钮样式
  &.secondary {
    background: $secondary-bg; // 次要背景色
    border: $border-width solid $border-color; // 边框样式
    color: $text-primary; // 主要文字颜色

    // 次要按钮悬停状态
    &:hover {
      background: $hover-bg; // 悬停背景色
      border-color: $accent-color; // 强调色边框
      color: $accent-color; // 强调色文字
    }
  }
}

// 导出按钮样式
.export-btn {
  background: $accent-color; // 强调色背景
  border: none; // 无边框
  border-radius: $border-radius; // 圆角
  font-weight: $font-weight-medium; // 中等字重
  transition: all $transition-fast; // 快速过渡动画
  height: 28px; // 固定高度

  // 导出按钮悬停效果
  &:hover {
    transform: $hover-transform; // 悬停变换
    box-shadow: $card-hover-shadow; // 悬停阴影
  }
}

// 返回按钮样式
.back-btn {
  background: rgba(255, 255, 255, 0.15); // 半透明白色背景
  border: 1px solid rgba(255, 255, 255, 0.3); // 半透明白色边框
  color: white; // 白色文字
  border-radius: $border-radius; // 圆角
  font-weight: $font-weight-medium; // 中等字重
  transition: all $transition-fast; // 快速过渡动画
  backdrop-filter: blur(10px); // 背景模糊效果
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); // 阴影效果
  height: 32px; // 固定高度
  display: flex; // 弹性布局
  align-items: center; // 垂直居中

  // 返回按钮悬停状态
  &:hover {
    background: rgba(255, 255, 255, 0.25); // 增加背景透明度
    border-color: rgba(255, 255, 255, 0.5); // 增加边框透明度
    color: white; // 保持白色文字
    transform: $hover-transform; // 悬停变换
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); // 增强阴影
  }

  // 返回按钮激活状态
  &:active {
    transform: translateY(0); // 恢复原始位置
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); // 减小阴影
  }
}

// 搜索框样式优化
.search-input {
  width: 240px;

  :deep(.ant-input-affix-wrapper) {
    background: $secondary-bg; // 改为次要背景色，更符合主题
    border: $border-width solid $border-color;
    color: $text-primary;
    border-radius: $border-radius;
    transition: border-color $transition-fast;

    &:focus {
      border-color: $accent-color;
      box-shadow: 0 0 0 2px rgba($accent-color, 0.2);
    }

    &::placeholder {
      color: $text-secondary; // 确保placeholder文字可见
    }
  }

  :deep(.ant-input-suffix) {
    color: $text-secondary;
  }
}

// 下拉框样式优化
.filter-select {
  @include mixin.filter-select(false, 140px);

}

// 股票表格样式
.stock-table {
  :deep(.ant-table) {
    background: $card-bg; // 卡片背景色
    border-radius: $border-radius; // 圆角

    // 表头样式
    .ant-table-thead > tr > th {
      background: $secondary-bg; // 次要背景色
      color: $text-primary; // 主要文字颜色
      font-weight: $font-weight-semibold; // 半粗体
      border-bottom: 2px solid $border-color; // 底部边框
      padding: map.get($spacers, 2); // 内边距
      text-align: center; // 文字居中
    }

    // 表格行样式
    .ant-table-tbody > tr {
      background: $card-bg; // 卡片背景色
      transition: background-color $transition-fast; // 背景色过渡

      // 行悬停状态
      &:hover > td {
        background: $hover-bg !important; // 悬停背景色
      }

      // 表格单元格样式
      > td {
        border-bottom: 1px solid $border-color; // 底部边框
        color: $text-primary; // 主要文字颜色
        padding: map.get($spacers, 2); // 内边距
        text-align: center; // 文字居中
      }
    }

    // 分页器样式
    .ant-table-pagination {
      margin: map.get($spacers, 4) 0 0 0; // 外边距
      padding: map.get($spacers, 3) 0 0 0; // 内边距
      border-top: 1px solid $border-color; // 顶部边框

      // 分页项样式
      .ant-pagination-item {
        background: $secondary-bg; // 次要背景色
        border: 1px solid $border-color; // 边框
        border-radius: $border-radius-sm; // 小圆角

        a {
          color: $text-primary; // 主要文字颜色
        }

        // 激活状态分页项
        &.ant-pagination-item-active {
          background: $accent-color; // 强调色背景
          border-color: $accent-color; // 强调色边框

          a {
            color: white; // 白色文字
          }
        }

        // 分页项悬停状态
        &:hover {
          border-color: $accent-color; // 强调色边框
        }
      }

      // 上一页/下一页按钮样式
      .ant-pagination-prev,
      .ant-pagination-next {
        .ant-pagination-item-link {
          background: $secondary-bg; // 次要背景色
          border: 1px solid $border-color; // 边框
          color: $text-primary; // 主要文字颜色
          border-radius: $border-radius-sm; // 小圆角
        }
      }

      // 禁用状态分页按钮
      .ant-pagination-disabled {
        .ant-pagination-item-link {
          color: $text-secondary; // 次要文字颜色
          background: $primary-bg; // 主背景色
        }
      }

      // 跳转分页按钮样式
      .ant-pagination-jump-prev,
      .ant-pagination-jump-next {
        .ant-pagination-item-container {
          .ant-pagination-item-ellipsis {
            color: $text-secondary; // 次要文字颜色
          }
        }
      }
    }

    // 链接按钮样式
    .ant-btn-link {
      color: $text-secondary; // 次要文字颜色
      transition: color $transition-fast; // 颜色过渡

      // 链接按钮悬停状态
      &:hover {
        color: $warning-color; // 警告色
      }
    }
  }
}

</style>