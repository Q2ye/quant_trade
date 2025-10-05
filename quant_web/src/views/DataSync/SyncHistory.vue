<script setup lang="ts">
import { ref, reactive, onMounted, h } from 'vue'
import { Table, Tag, Space, Button, DatePicker, Select } from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons-vue'

interface SyncRecord {
  id: string
  taskType: string
  dataCategory: string
  status: 'success' | 'failed' | 'running'
  startTime: string
  endTime: string
  duration: string
  recordsCount: number
  errorMessage?: string
}

const loading = ref(false)
const records = ref<SyncRecord[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0
})

const filters = reactive({
  taskType: '',
  status: '',
  dateRange: [] as string[]
})

const columns: ColumnsType<SyncRecord> = [
  {
    title: '任务ID',
    dataIndex: 'id',
    key: 'id',
    width: 120
  },
  {
    title: '任务类型',
    dataIndex: 'taskType',
    key: 'taskType',
    width: 100,
    filters: [
      { text: '自动', value: 'auto' },
      { text: '手动', value: 'manual' }
    ]
  },
  {
    title: '数据类型',
    dataIndex: 'dataCategory',
    key: 'dataCategory',
    width: 120
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    customRender: ({ text: status }) => {
      const colorMap: Record<string, string> = {
        success: 'green',
        failed: 'red',
        running: 'blue'
      }
      const textMap: Record<string, string> = {
        success: '成功',
        failed: '失败',
        running: '运行中'
      }
      return h(Tag, { color: colorMap[status] }, () => textMap[status])
    }
  },
  {
    title: '开始时间',
    dataIndex: 'startTime',
    key: 'startTime',
    width: 180
  },
  {
    title: '结束时间',
    dataIndex: 'endTime',
    key: 'endTime',
    width: 180
  },
  {
    title: '耗时',
    dataIndex: 'duration',
    key: 'duration',
    width: 100
  },
  {
    title: '记录数',
    dataIndex: 'recordsCount',
    key: 'recordsCount',
    width: 100,
    customRender: ({ text: count }) => count.toLocaleString()
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    customRender: ({ record }) => {
      return h(Space, null, () => [
        h(Button, { type: 'link', size: 'small' }, () => '查看日志'),
        record.status === 'failed' 
          ? h(Button, { type: 'link', size: 'small', danger: true }, () => '重试')
          : null
      ].filter(Boolean))
    }
  }
]

const loadData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    const response = await fetch(`/api/data-sync/history?page=${pagination.current}&size=${pagination.pageSize}`)
    const data = await response.json()
    records.value = data.records
    pagination.total = data.total
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  loadData()
}

const handleReset = () => {
  Object.assign(filters, {
    taskType: '',
    status: '',
    dateRange: []
  })
  handleSearch()
}

const handleTableChange = (pag: { current: number; pageSize: number }) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="sync-history-page">
    <a-card title="同步历史记录">
      <template #extra>
        <a-button @click="loadData">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </template>

      <div class="filter-bar">
        <a-space :size="16">
          <a-select
            v-model:value="filters.taskType"
            placeholder="任务类型"
            style="width: 120px"
            allowClear
          >
            <a-select-option value="auto">自动</a-select-option>
            <a-select-option value="manual">手动</a-select-option>
          </a-select>

          <a-select
            v-model:value="filters.status"
            placeholder="状态"
            style="width: 120px"
            allowClear
          >
            <a-select-option value="success">成功</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
            <a-select-option value="running">运行中</a-select-option>
          </a-select>

          <a-range-picker
            v-model:value="filters.dateRange"
            style="width: 240px"
          />

          <a-button type="primary" @click="handleSearch">
            <template #icon><SearchOutlined /></template>
            搜索
          </a-button>

          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="records"
        :pagination="pagination"
        :loading="loading"
        row-key="id"
        @change="handleTableChange"
      />
    </a-card>
  </div>
</template>

<style scoped>
.sync-history-page {
  padding: 24px;
}

.filter-bar {
  margin-bottom: 16px;
}
</style>