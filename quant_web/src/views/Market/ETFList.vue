<script setup lang="ts">
import {h, onMounted, reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Button, Space, Tag} from 'ant-design-vue'
import type {ColumnsType} from 'ant-design-vue/es/table'
import {ArrowLeftOutlined, SearchOutlined} from '@ant-design/icons-vue'

const router = useRouter()

// 返回按钮处理
const handleBack = () => {
  router.go(-1)
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
    <a-card title="ETF列表" :bordered="false">
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
        </a-space>
      </template>

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
.etf-list-page {
  padding: 24px;
  background: var(--primary-bg);
  min-height: 100vh;
}

:deep(.ant-card) {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);

  .ant-card-head {
    border-bottom: 1px solid var(--border-color);
    background: var(--secondary-bg);

    .ant-card-head-title {
      color: var(--text-primary);
      font-weight: 600;
    }
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
  margin-bottom: 16px;
  padding: var(--spacer-3);
  background: var(--secondary-bg);
  border-radius: var(--border-radius);
  border: 1px solid var(--border-color);
}
</style>