<script setup lang="ts">
import { ref, reactive, onMounted, h } from 'vue'
import { Tag, Space, Button } from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { LineChartOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons-vue'

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

const columns: ColumnsType<Index> = [
  {
    title: '指数代码',
    dataIndex: 'ts_code',
    key: 'ts_code',
    width: 120,
    sorter: true
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
    sorter: true,
    customRender: ({ text: point }) => point?.toFixed(2) || '-'
  },
  {
    title: '涨跌',
    dataIndex: 'change',
    key: 'change',
    width: 100,
    sorter: true,
    customRender: ({ text: change }) => {
      if (change === undefined) return '-'
      const icon = change >= 0 ?
        h(RiseOutlined, { style: 'color: #f5222d' }) :
        h(FallOutlined, { style: 'color: #52c41a' })
      const color = change >= 0 ? '#f5222d' : '#52c41a'
      return h('span', { style: { color } }, [
        icon,
        ' ',
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
    sorter: true,
    customRender: ({ text: percent }) => {
      if (percent === undefined) return '-'
      const color = percent >= 0 ? '#f5222d' : '#52c41a'
      return h('span', { style: { color } }, [
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
    customRender: ({ text: volume }) => volume ? (volume / 100000000).toFixed(2) : '-'
  },
  {
    title: '成交额(亿)',
    dataIndex: 'amount',
    key: 'amount',
    width: 120,
    customRender: ({ text: amount }) => amount ? (amount / 100000000).toFixed(2) : '-'
  },
  {
    title: '市场',
    dataIndex: 'market',
    key: 'market',
    width: 80,
    customRender: ({ text: market }) => h(Tag, { color: 'blue' }, () => market)
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
    customRender: ({ record }) => h(Space, null, () => [
      h(Button, {
        type: 'link',
        size: 'small',
        icon: h(LineChartOutlined),
        onClick: () => viewIndexDetail(record)
      }, () => '详情')
    ])
  }
]

const loadIndexList = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/market/indexes')
    const data = await response.json()
    indexList.value = data
    pagination.total = data.length
  } catch (error) {
    console.error('加载指数列表失败:', error)
  } finally {
    loading.value = false
  }
}

const viewIndexDetail = (index: Index) => {
  // 跳转到指数详情页面
  window.open(`/market/index/${index.ts_code}`, '_blank')
}

onMounted(() => {
  loadIndexList()
})
</script>

<template>
  <div class="index-list-page">
    <a-card title="指数列表">
      <a-table
        :columns="columns"
        :data-source="indexList"
        :pagination="pagination"
        :loading="loading"
        row-key="ts_code"
        @change="loadIndexList"
      >
        <template #headerCell="{ title }">
          <span style="font-weight: bold;">{{ title }}</span>
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <div>
              <div style="font-weight: 500;">{{ record.name }}</div>
              <div style="font-size: 12px; color: #999;">{{ record.fullname }}</div>
            </div>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<style scoped>
.index-list-page {
  padding: 24px;
}

:deep(.ant-table-thead > tr > th) {
  background-color: #fafafa;
  font-weight: 600;
}
</style>