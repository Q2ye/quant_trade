<!-- IndexList.vue - 使用 Naive UI 重构 -->
<script setup lang="ts">
import { ref, onMounted, onUnmounted, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  NCard,
  NDataTable,
  NButton,
  NTag,
  NSpace,
  NIcon,
  useMessage,
  useLoadingBar,
  type DataTableColumns
} from 'naive-ui'
import { SmartIcon } from '@/components/SmartIcon'
// 导入图标
import { TrendingUp, TrendingDown, BarChart as LineChartIcon } from '@vicons/ionicons5'

const router = useRouter()
const message = useMessage()
const loadingBar = useLoadingBar()

// 返回按钮处理
const handleBack = () => {
  if (window.history.length > 1) {
    router.go(-1)
  } else {
    router.push('/')
  }
}

// 指数数据接口
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
const pagination = ref({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  prefix: (info: any) => `共 ${info.itemCount} 条`
})

// 图标函数
const getIconComponent = (iconName: string) => {
  const iconMap: Record<string, any> = {
    trendingUp: TrendingUp,
    trendingDown: TrendingDown,
    lineChart: LineChartIcon
  }
  return iconMap[iconName]
}

// 表格列定义
const columns: DataTableColumns<Index> = [
  {
    title: '指数代码',
    key: 'ts_code',
    width: 120,
    align: 'center'
  },
  {
    title: '指数名称',
    key: 'name',
    width: 150,
    render: (row) => {
      return h('div', { class: 'index-name-cell' }, [
        h('div', { class: 'index-name' }, row.name),
        h('div', { class: 'index-fullname' }, row.fullname)
      ])
    }
  },
  {
    title: '当前点位',
    key: 'current_point',
    width: 120,
    align: 'right',
    render: (row) => row.current_point?.toFixed(2) || '-'
  },
  {
    title: '涨跌',
    key: 'change',
    width: 100,
    align: 'right',
    render: (row) => {
      if (row.change === undefined || row.change === null) return '-'
      const icon = row.change >= 0 ? TrendingUp : TrendingDown
      const color = row.change >= 0 ? 'var(--n-success-color)' : 'var(--n-error-color)'
      return h('span', { style: { color, display: 'flex', alignItems: 'center', gap: '4px' } }, [
        h(NIcon, { component: icon }),
        `${row.change >= 0 ? '+' : ''}${row.change.toFixed(2)}`
      ])
    }
  },
  {
    title: '涨跌幅',
    key: 'change_percent',
    width: 100,
    align: 'right',
    render: (row) => {
      if (row.change_percent === undefined || row.change_percent === null) return '-'
      const color = row.change_percent >= 0 ? 'var(--n-success-color)' : 'var(--n-error-color)'
      return h('span', { style: { color } }, [
        `${row.change_percent >= 0 ? '+' : ''}${row.change_percent.toFixed(2)}%`
      ])
    }
  },
  {
    title: '成交量(亿)',
    key: 'volume',
    width: 120,
    align: 'right',
    render: (row) => row.volume ? (row.volume / 100000000).toFixed(2) : '-'
  },
  {
    title: '成交额(亿)',
    key: 'amount',
    width: 120,
    align: 'right',
    render: (row) => row.amount ? (row.amount / 100000000).toFixed(2) : '-'
  },
  {
    title: '市场',
    key: 'market',
    width: 80,
    align: 'center',
    render: (row) => h(NTag, { type: 'info', size: 'small' }, () => row.market || '-')
  },
  {
    title: '分类',
    key: 'category',
    width: 100,
    align: 'center'
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    align: 'center',
    render: (row) => h(NSpace, { size: 'small' }, () => [
      h(NButton, {
        type: 'primary',
        size: 'small',
        onClick: () => viewIndexDetail(row)
      }, {
        default: () => '详情',
        icon: () => h(NIcon, { component: LineChartIcon })
      })
    ])
  }
]

// 加载指数列表数据
const loadIndexList = async () => {
  loading.value = true
  loadingBar.start()
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))

    // 模拟数据
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
    pagination.value.itemCount = mockData.length
    message.success('数据加载成功')
  } catch (error) {
    console.error('加载指数列表失败:', error)
    message.error('加载指数列表失败')
    indexList.value = []
    pagination.value.itemCount = 0
  } finally {
    loading.value = false
    loadingBar.finish()
  }
}

// 查看指数详情
const viewIndexDetail = (index: Index) => {
  router.push(`/market/index/${index.ts_code}`)
}

onMounted(() => {
  loadIndexList()
})

onUnmounted(() => {
  indexList.value = []
})
</script>

<template>
  <div class="index-list-page">
    <!-- 页面标题区域 -->
    <NCard class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">指数行情</h1>
          <p class="page-description">主要市场指数表现与趋势分析</p>
        </div>
        <div class="header-actions-right">
          <NButton @click="handleBack" :disabled="loading" class="back-btn">
            <template #icon>
              <SmartIcon name="ArrowBack" />
            </template>
            返回
          </NButton>
        </div>
      </div>
    </NCard>

    <!-- 指数列表卡片 -->
    <NCard class="index-list-card" title="指数列表">
      <NDataTable
        class="index-table"
        :columns="columns"
        :data="indexList"
        :loading="loading"
        :pagination="pagination"
        :row-key="(row: Index) => row.ts_code"
        :scroll-x="1000"
        striped
        @update:page="(page) => pagination.page = page"
        @update:page-size="(size) => pagination.pageSize = size"
      />
    </NCard>
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;

.index-list-page {
  @include mixin.content-with-base;
}

.page-header {
  @include page-header-base;
  margin-bottom: map.get($spacers, 6);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  .page-title {
    margin: 0;
    font-size: $font-size-base * 1.5;
    font-weight: 600;
    color: var(--n-text-color-base);
  }

  .page-description {
    margin: map.get($spacers, 1) 0 0;
    color: var(--n-text-color-2);
    font-size: $font-size-base * 0.9;
  }
}

.header-actions-right {
  display: flex;
  gap: map.get($spacers, 2);
}

.back-btn {
  @include mixin.button-base(var(--n-button-color-2), var(--n-text-color-1));
  border: 1px solid var(--n-border-color);

  &:hover:not(:disabled) {
    background: var(--n-button-color-2-hover);
  }
}

.index-list-card {
  @include mixin.card-base;
  padding: map.get($spacers, 4);
}

// 表格样式
.index-table {
  @include mixin.table-base-styles;

  .index-name-cell {
    .index-name {
      font-weight: 600;
      color: var(--n-text-color-base);
    }

    .index-fullname {
      font-size: $font-size-base * 0.85;
      color: var(--n-text-color-2);
      margin-top: 2px;
    }
  }
}

// 响应式调整
@include mixin.media-breakpoint-down(lg) {
  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: map.get($spacers, 3);
  }

  .header-actions-right {
    width: 100%;
    justify-content: flex-end;
  }
}

@include mixin.media-breakpoint-down(sm) {
  .index-table {
    font-size: $font-size-base * 0.9;
  }
}
</style>