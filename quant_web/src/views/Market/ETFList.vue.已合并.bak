<!-- ETF列表页 - 基于 Naive UI 重构 -->
<template>
  <div class="etf-list-page">
    <!-- 页面标题和状态-->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">ETF基金</h1>
          <p class="page-description">交易所交易基金数据与市场分析</p>
        </div>
        <div class="header-actions-right">
          <n-button class="back-btn" @click="handleBack">
            <template #icon>
              <n-icon><ArrowBackIcon /></n-icon>
            </template>
            返回
          </n-button>
        </div>
      </div>
    </div>
    <div class="main-content-with-sidebar">
      <n-card class="etf-list-card" title="ETF列表" :bordered="false">
        <div class="filter-bar">
          <n-space :size="16">
            <n-input
              v-model:value="filters.search"
              placeholder="搜索ETF代码或名称"
              style="width: 200px"
              @keydown.enter="loadETFList"
            >
              <template #prefix>
                <n-icon><SearchIcon /></n-icon>
              </template>
            </n-input>

            <n-select
              v-model:value="filters.market"
              placeholder="选择市场"
              style="width: 120px"
              clearable
              :options="marketOptions"
              @update:value="loadETFList"
            />
            <div class="filter-actions">
              <n-button type="primary" @click="loadETFList" class="action-btn">搜索</n-button>
            </div>
          </n-space>
        </div>

        <n-data-table
          class="etf-table"
          :columns="columns"
          :data="etfList"
          :pagination="pagination"
          :loading="loading"
          :row-key="(row) => row.ts_code"
          @update:page="handlePageChange"
          @update:page-size="handlePageSizeChange"
        />
      </n-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NDataTable,
  NCard,
  NInput,
  NSelect,
  NSpace,
  NTag,
  NIcon,
  useMessage
} from 'naive-ui'
import { ArrowBack as ArrowBackIcon, Search as SearchIcon } from '@vicons/ionicons5'

const router = useRouter()
const message = useMessage()

// 返回按钮处理
const handleBack = () => {
  router.go(-1)
}

// 刷新数据方法
const refreshData = () => {
  message.success('ETF数据已刷新')
  loadETFList()
}

interface ETF {
  ts_code: string
  name: string
  full_name: string
  market: string
  list_date: string
  mgr_name: string
  index_code: string
  index_name: string
  fund_size: number
  expense_ratio: number
}

const loading = ref(false)
const etfList = ref<ETF[]>([])
const pagination = reactive({
  page: 1,
  pageSize: 50,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => {
    pagination.page = page
    loadETFList()
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    loadETFList()
  }
})

const filters = reactive({
  search: '',
  market: '',
  mgr_name: ''
})

const marketOptions = [
  { label: '上交所', value: 'SH' },
  { label: '深交所', value: 'SZ' }
]

const columns = [
  {
    title: '代码',
    key: 'ts_code',
    width: 100,
    sorter: 'default'
  },
  {
    title: '名称',
    key: 'name',
    width: 120
  },
  {
    title: '全称',
    key: 'full_name',
    ellipsis: {
      tooltip: true
    }
  },
  {
    title: '市场',
    key: 'market',
    width: 80,
    render: (row: ETF) => {
      return h(NTag, {
        color: row.market === 'SH' ? 'red' : 'blue',
        bordered: false
      }, { default: () => row.market })
    }
  },
  {
    title: '管理人',
    key: 'mgr_name',
    width: 120
  },
  {
    title: '跟踪指数',
    key: 'index_name',
    width: 150
  },
  {
    title: '规模(亿)',
    key: 'fund_size',
    width: 100,
    sorter: 'default',
    render: (row: ETF) => (row.fund_size / 100000000).toFixed(2)
  },
  {
    title: '费率(%)',
    key: 'expense_ratio',
    width: 100,
    render: (row: ETF) => row.expense_ratio.toFixed(2)
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row: ETF) => {
      return h(NSpace, null, {
        default: () => [
          h(NButton, { type: 'primary', size: 'small', text: true }, { default: () => '详情' }),
          h(NButton, { type: 'primary', size: 'small', text: true }, { default: () => '加入自选' })
        ]
      })
    }
  }
]

const loadETFList = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: pagination.page.toString(),
      size: pagination.pageSize.toString(),
      ...filters
    })

    const response = await fetch(`/api/market/etfs?${params}`)
    const data = await response.json()
    etfList.value = data.records
    pagination.itemCount = data.total
  } catch (error) {
    console.error('加载ETF列表失败:', error)
    message.error('加载ETF列表失败')
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  pagination.page = page
  loadETFList()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.page = 1
  loadETFList()
}

onMounted(() => {
  loadETFList()
})
</script>
<style scoped lang="scss">
@use '@/assets/scss/naive-variables' as *;

.etf-list-page {
  min-height: 100vh;
  background: var(--n-body-color);
  transition: all $transition-normal;

  .main-content-with-sidebar {
    @include content-with-sidebar;
  }
}

.page-header {
  @include page-header-base;
  margin-bottom: spacer(6);
}

.etf-list-card {
  @include card-base;
  margin-bottom: spacer(4);
  padding: spacer(3);

  :deep(.n-card-header) {
    @include card-header-base;
    border-bottom: 1px solid var(--n-border-color);
  }
}

.filter-bar {
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  border: 1px solid var(--n-border-color);
  padding: spacer(3);
  margin-bottom: spacer(3);

  :deep(.n-space) {
    width: 100%;
    align-items: flex-start;

    .filter-actions {
      margin-left: auto;
      display: flex;
      align-items: center;

      .n-space {
        width: auto;
        align-items: center;
      }
    }
  }

  :deep(.n-space-item:last-child) {
    margin-left: auto;
    display: flex;
    align-items: center;
  }
}

.action-btn {
  @include button-base;
}

.export-btn {
  @include button-base(var(--n-primary-color), white);
  height: 28px;
}

.back-btn {
  @include button-base(rgba(255, 255, 255, 0.15), white);
}

.etf-table {
  @include table-base-styles;
}
</style>