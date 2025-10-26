<script setup lang="ts">
import {h, onMounted, reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Button, message, Space, Tag} from 'ant-design-vue'
import type {ColumnsType} from 'ant-design-vue/es/table'
import {ArrowLeftOutlined, SearchOutlined} from '@ant-design/icons-vue'

// 引入 Iconify 图标

const router = useRouter()

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
  current: 1,
  pageSize: 50,
  total: 0
})

const filters = reactive({
  search: '',
  market: '',
  mgr_name: ''
})

const columns: ColumnsType<ETF> = [
  {
    title: '代码',
    dataIndex: 'ts_code',
    key: 'ts_code',
    width: 100,
    sorter: true
  },
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
    width: 120
  },
  {
    title: '全称',
    dataIndex: 'full_name',
    key: 'full_name',
    ellipsis: true
  },
  {
    title: '市场',
    dataIndex: 'market',
    key: 'market',
    width: 80,
    customRender: ({text: market}) => {
      return h(Tag, {color: market === 'SH' ? 'red' : 'blue'}, () => market)
    }
  },
  {
    title: '管理人',
    dataIndex: 'mgr_name',
    key: 'mgr_name',
    width: 120
  },
  {
    title: '跟踪指数',
    dataIndex: 'index_name',
    key: 'index_name',
    width: 150
  },
  {
    title: '规模(亿)',
    dataIndex: 'fund_size',
    key: 'fund_size',
    width: 100,
    sorter: true,
    customRender: ({text: size}) => (size / 100000000).toFixed(2)
  },
  {
    title: '费率(%)',
    dataIndex: 'expense_ratio',
    key: 'expense_ratio',
    width: 100,
    customRender: ({text: ratio}) => ratio.toFixed(2)
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    customRender: () => {
      return h(Space, null, () => [
        h(Button, {type: 'link', size: 'small'}, () => '详情'),
        h(Button, {type: 'link', size: 'small'}, () => '加入自选')
      ])
    }
  }
]

const loadETFList = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: pagination.current.toString(),
      size: pagination.pageSize.toString(),
      ...filters
    })

    const response = await fetch(`/api/market/etfs?${params}`)
    const data = await response.json()
    etfList.value = data.records
    pagination.total = data.total
  } catch (error) {
    console.error('加载ETF列表失败:', error)
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag: { current: number; pageSize: number }) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadETFList()
}

onMounted(() => {
  loadETFList()
})
</script>

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
          <a-button class="back-btn" @click="handleBack">
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>
    <a-card title="ETF列表" :bordered="false">
      <div class="filter-bar">
        <a-space :size="16">
          <a-input
              v-model:value="filters.search"
              placeholder="搜索ETF代码或名称"
              style="width: 200px"
              @press-enter="loadETFList"
          >
            <template #suffix>
              <SearchOutlined/>
            </template>
          </a-input>

          <a-select
              v-model:value="filters.market"
              placeholder="选择市场"
              style="width: 120px"
              allowClear
              @change="loadETFList"
          >
            <a-select-option value="SH">上交所</a-select-option>
            <a-select-option value="SZ">深交所</a-select-option>
          </a-select>

          <a-button type="primary" @click="loadETFList">搜索</a-button>
        </a-space>
      </div>

      <a-table
          :columns="columns"
          :data-source="etfList"
          :pagination="pagination"
          :loading="loading"
          row-key="ts_code"
          @change="handleTableChange"
      />
    </a-card>
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/scss/mixins';

.etf-list-page {
  padding: 24px;
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

// 刷新按钮样式
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

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:active {
    transform: translateY(0);
  }
}

:deep(.ant-card) {
  @include mixins.unified-card;

  .filter-bar {
    margin-bottom: 16px;
    padding: var(--spacer-3);
    background: var(--secondary-bg);
    border-radius: var(--border-radius);
    border: 1px solid var(--border-color);
  }
}

:deep(.ant-table) {
  @include mixins.unified-table;
}

</style>