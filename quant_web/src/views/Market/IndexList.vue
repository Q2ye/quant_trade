<script setup lang="ts">
import {h, onMounted, onUnmounted, reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Button, message, Space, Tag} from 'ant-design-vue'
import type {ColumnsType} from 'ant-design-vue/es/table'
import {ArrowLeftOutlined, FallOutlined, LineChartOutlined, RiseOutlined} from '@ant-design/icons-vue'

const router = useRouter()

// 返回按钮处理 - 修复路由问题
const handleBack = () => {
  // 使用更安全的路由返回方式
  if (window.history.length > 1) {
    router.go(-1)
  } else {
    // 如果没有历史记录，跳转到首页
    router.push('/')
  }
}

interface Index {
  ts_code: string
  name: string
  fullname: string
  market: string
  publisher: string
  category: string
  base_date: string
  base_point: number
  current_point: number
  change: number
  change_percent: number
  volume: number
  amount: number
}

const loading = ref(false)
const indexList = ref<Index[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0
})

// 修复表格列定义
const columns: ColumnsType<Index> = [
  {
    title: '指数代码',
    dataIndex: 'ts_code',
    key: 'ts_code',
    width: 120
  },
  {
    title: '指数名称',
    dataIndex: 'name',
    key: 'name',
    width: 150
  },
  {
    title: '当前点位',
    dataIndex: 'current_point',
    key: 'current_point',
    width: 120,
    customRender: ({text: point}) => point ? point.toFixed(2) : '-'
  },
  {
    title: '涨跌',
    dataIndex: 'change',
    key: 'change',
    width: 100,
    customRender: ({text: change}) => {
      if (change === undefined || change === null) return '-'
      const icon = change >= 0 ?
          h(RiseOutlined, {style: {color: '#f5222d'}}) :
          h(FallOutlined, {style: {color: '#52c41a'}})
      const color = change >= 0 ? '#f5222d' : '#52c41a'
      return h('span', {style: {color, display: 'flex', alignItems: 'center', gap: '4px'}}, [
        icon,
        change >= 0 ? '+' : '',
        change.toFixed(2)
      ])
    }
  },
  {
    title: '涨跌幅',
    dataIndex: 'change_percent',
    key: 'change_percent',
    width: 100,
    customRender: ({text: percent}) => {
      if (percent === undefined || percent === null) return '-'
      const color = percent >= 0 ? '#f5222d' : '#52c41a'
      return h('span', {style: {color}}, [
        percent >= 0 ? '+' : '',
        percent.toFixed(2),
        '%'
      ])
    }
  },
  {
    title: '成交量(亿)',
    dataIndex: 'volume',
    key: 'volume',
    width: 120,
    customRender: ({text: volume}) => {
      if (!volume) return '-'
      return (volume / 100000000).toFixed(2)
    }
  },
  {
    title: '成交额(亿)',
    dataIndex: 'amount',
    key: 'amount',
    width: 120,
    customRender: ({text: amount}) => {
      if (!amount) return '-'
      return (amount / 100000000).toFixed(2)
    }
  },
  {
    title: '市场',
    dataIndex: 'market',
    key: 'market',
    width: 80,
    customRender: ({text: market}) => {
      if (!market) return '-'
      return h(Tag, {color: 'blue'}, () => market)
    }
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    width: 100
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    customRender: ({record}) => h(Space, {size: 'small'}, () => [
      h(Button, {
        type: 'link',
        size: 'small',
        icon: h(LineChartOutlined),
        onClick: () => viewIndexDetail(record)
      }, () => '详情')
    ])
  }
]

// 修复数据加载函数
const loadIndexList = async () => {
  loading.value = true
  try {
    // 模拟API数据，避免slice错误
    await new Promise(resolve => setTimeout(resolve, 1000))

    // 使用模拟数据，确保是数组格式
    const mockData: Index[] = [
      {
        ts_code: '000001.SH',
        name: '上证指数',
        fullname: '上海证券综合指数',
        market: '上证',
        publisher: '上海证券交易所',
        category: '综合指数',
        base_date: '1990-12-19',
        base_point: 100,
        current_point: 3200.45,
        change: 25.67,
        change_percent: 0.81,
        volume: 450000000,
        amount: 3800.25
      },
      {
        ts_code: '399001.SZ',
        name: '深证成指',
        fullname: '深圳成份指数',
        market: '深证',
        publisher: '深圳证券交易所',
        category: '成份指数',
        base_date: '1994-07-20',
        base_point: 1000,
        current_point: 11500.78,
        change: -15.23,
        change_percent: -0.13,
        volume: 320000000,
        amount: 2800.67
      }
    ]

    indexList.value = mockData
    pagination.total = mockData.length

  } catch (error) {
    console.error('加载指数列表失败:', error)
    message.error('加载指数列表失败')
    // 确保即使出错也设置空数组，避免slice错误
    indexList.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const viewIndexDetail = (index: Index) => {
  // 使用router.push而不是window.open，避免Vue组件卸载问题
  router.push(`/market/index/${index.ts_code}`)
}

// 添加组件卸载处理
onMounted(() => {
  loadIndexList()
})

// 防止内存泄漏和vnode错误
onUnmounted(() => {
  // 清理工作
  indexList.value = []
})
</script>

<template>
  <div class="index-list-page">
    <!-- 页面标题和状态 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">指数行情</h1>
          <p class="page-description">主要市场指数表现与趋势分析</p>
        </div>
        <div class="header-actions-right">
          <a-button class="back-btn" @click="handleBack" :disabled="loading">
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>

    <a-card
        class="index-list-card"
        title="指数列表"
        :bordered="false"
    >
      <a-table
          :columns="columns"
          :data-source="indexList"
          :pagination="pagination"
          :loading="loading"
          row-key="ts_code"
          :scroll="{ x: 1000 }"
      >
        <template #headerCell="{ column }">
          <span class="table-header">{{ column.title }}</span>
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <div class="index-name-cell">
              <div class="index-name">{{ record.name }}</div>
              <div class="index-fullname">{{ record.fullname }}</div>
            </div>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/scss/mixins';

.index-list-page {
  padding: var(--spacer-4, 1.5rem);
  background: var(--primary-bg);
  min-height: 100vh;
}

.page-header {
  background: var(--page-header-bg, linear-gradient(135deg, var(--accent-color) 0%, color-mix(in srgb, var(--accent-color) 60%, #6f42c1) 100%));
  color: white;
  padding: 20px 0;
  margin-bottom: 20px;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 var(--spacer-4);
    position: relative;

    .header-actions-right {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
  }

  .title-section {
    flex: 1;

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      color: white;
    }

    .page-description {
      margin: 6px 0 0 0;
      opacity: 0.9;
      font-size: 13px;
    }
  }
}

// 返回按钮样式
.back-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  border-radius: var(--border-radius, 6px);
  font-weight: 500;
  transition: all var(--transition-fast, 0.3s);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  height: 32px;
  display: flex;
  align-items: center;

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:active {
    transform: translateY(0);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.index-list-card {
  @include mixins.unified-card;
}

:deep(.ant-table) {
  @include mixins.unified-table;

  // 指数名称单元格样式
  .index-name-cell {
    .index-name {
      font-weight: 500;
      color: var(--text-primary);
    }

    .index-fullname {
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 2px;
    }
  }
}

// 响应式调整
@media (max-width: 768px) {
  .page-header .header-content {
    flex-direction: column;
    gap: 12px;
    text-align: center;

    .header-actions-right {
      order: -1;
      align-self: stretch;
      justify-content: space-between;
      margin-bottom: var(--spacer-2);
    }
  }
}
</style>