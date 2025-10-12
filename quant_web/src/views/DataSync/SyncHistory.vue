<!-- quant_web/src/views/DataSync/SyncHistory.vue -->
<script setup lang="ts">
import { ref, reactive, onMounted, h } from 'vue'
import {
  Tag,
  Space,
  Button
} from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { SearchOutlined, ReloadOutlined, EyeOutlined } from '@ant-design/icons-vue'

// 同步记录接口
interface SyncRecord {
  id: string
  task_id: string
  data_types: string[]
  status: 'completed' | 'running' | 'failed' | 'cancelled'
  start_time: string
  end_time?: string
  duration?: number
  total_tasks: number
  completed_tasks: number
  results: Record<string, any>
  error?: string
}

// 响应式数据
const loading = ref(false)
const records = ref<SyncRecord[]>([])
const selectedRecord = ref<SyncRecord | null>(null)

// 分页和筛选
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0
})

const filters = reactive({
  status: '',
  dateRange: [] as string[]
})

/**
 * 加载同步历史数据
 */
const loadHistory = async () => {
  loading.value = true
  try {
    // 模拟API调用 - 实际项目中需要实现对应的后端接口
    const response = await fetch(`/api/data-sync/history?page=${pagination.current}&size=${pagination.pageSize}`)
    const data = await response.json()
    records.value = data.records
    pagination.total = data.total
  } catch (error) {
    console.error('加载同步历史失败:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 查看记录详情
 */
const viewRecordDetail = (record: SyncRecord) => {
  selectedRecord.value = record
}

/**
 * 重新执行任务
 */
const retryTask = async (record: SyncRecord) => {
  try {
    // 这里可以实现重新执行逻辑
    console.log('重新执行任务:', record)
  } catch (error) {
    console.error('重新执行任务失败:', error)
  }
}

/**
 * 处理搜索
 */
const handleSearch = () => {
  pagination.current = 1
  loadHistory()
}

/**
 * 处理重置
 */
const handleReset = () => {
  Object.assign(filters, {
    status: '',
    dateRange: []
  })
  handleSearch()
}

/**
 * 处理表格分页变化
 */
const handleTableChange = (pag: any) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadHistory()
}

/**
 * 获取状态颜色
 */
const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    completed: 'green',
    running: 'blue',
    failed: 'red',
    cancelled: 'orange'
  }
  return colors[status] || 'default'
}

/**
 * 获取状态文本
 */
const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    completed: '完成',
    running: '运行中',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

/**
 * 格式化时间
 */
const formatTime = (timeString: string) => {
  if (!timeString) return '--'
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN')
  } catch (error) {
    return timeString
  }
}

/**
 * 计算持续时间
 */
const formatDuration = (start: string, end?: string) => {
  if (!end) return '--'
  const startTime = new Date(start).getTime()
  const endTime = new Date(end).getTime()
  const duration = Math.round((endTime - startTime) / 1000)
  return `${duration}秒`
}

// 表格列定义
const columns: ColumnsType<SyncRecord> = [
  {
    title: '任务ID',
    dataIndex: 'task_id',
    key: 'task_id',
    width: 120,
    ellipsis: true
  },
  {
    title: '数据类型',
    dataIndex: 'data_types',
    key: 'data_types',
    width: 150,
    customRender: ({ text: dataTypes }: { text: string[] }) => {
      return dataTypes?.join(', ') || '--'
    }
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    customRender: ({ text: status }: { text: string }) => {
      return h(
        Tag,
        { color: getStatusColor(status) },
        () => getStatusText(status)
      )
    }
  },
  {
    title: '开始时间',
    dataIndex: 'start_time',
    key: 'start_time',
    width: 180,
    customRender: ({ text: startTime }: { text: string }) => formatTime(startTime)
  },
  {
    title: '结束时间',
    dataIndex: 'end_time',
    key: 'end_time',
    width: 180,
    customRender: ({ text: endTime }: { text: string }) => formatTime(endTime || '')
  },
  {
    title: '持续时间',
    key: 'duration',
    width: 100,
    customRender: ({ record }: { record: SyncRecord }) =>
      formatDuration(record.start_time, record.end_time)
  },
  {
    title: '完成进度',
    key: 'progress',
    width: 120,
    customRender: ({ record }: { record: SyncRecord }) => {
      const progress = record.total_tasks > 0
        ? Math.round((record.completed_tasks / record.total_tasks) * 100)
        : 0
      return `${progress}% (${record.completed_tasks}/${record.total_tasks})`
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    customRender: ({ record }: { record: SyncRecord }) => {
      return h(Space, {}, () => [
        h(
          Button,
          {
            type: 'link',
            size: 'small',
            icon: h(EyeOutlined),
            onClick: () => viewRecordDetail(record)
          },
          () => '详情'
        ),
        record.status === 'failed' && h(
          Button,
          {
            type: 'link',
            size: 'small',
            onClick: () => retryTask(record)
          },
          () => '重试'
        )
      ].filter(Boolean))
    }
  }
]

// 组件挂载时加载数据
onMounted(() => {
  loadHistory()
})
</script>

<template>
  <div class="sync-history-page">
    <a-card title="同步历史记录">
      <template #extra>
        <a-button @click="loadHistory" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </template>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <a-space :size="16" wrap>
          <a-select
            v-model:value="filters.status"
            placeholder="状态筛选"
            style="width: 120px"
            allow-clear
          >
            <a-select-option value="completed">完成</a-select-option>
            <a-select-option value="running">运行中</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
            <a-select-option value="cancelled">已取消</a-select-option>
          </a-select>

          <a-range-picker
            v-model:value="filters.dateRange"
            style="width: 240px"
            :placeholder="['开始日期', '结束日期']"
          />

          <a-button type="primary" @click="handleSearch">
            <template #icon><SearchOutlined /></template>
            搜索
          </a-button>

          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>

      <!-- 数据表格 -->
      <a-table
        :columns="columns"
        :data-source="records"
        :pagination="pagination"
        :loading="loading"
        row-key="id"
        @change="handleTableChange"
        :scroll="{ x: 1000 }"
      />

      <!-- 详情抽屉 -->
      <a-drawer
        :visible="!!selectedRecord"
        title="同步任务详情"
        placement="right"
        width="600"
        :closable="true"
        @close="selectedRecord = null"
      >
        <template v-if="selectedRecord">
          <a-descriptions title="任务信息" bordered size="small" :column="1">
            <a-descriptions-item label="任务ID">
              {{ selectedRecord.task_id }}
            </a-descriptions-item>
            <a-descriptions-item label="数据类型">
              {{ selectedRecord.data_types.join(', ') }}
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="getStatusColor(selectedRecord.status)">
                {{ getStatusText(selectedRecord.status) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="开始时间">
              {{ formatTime(selectedRecord.start_time) }}
            </a-descriptions-item>
            <a-descriptions-item label="结束时间">
              {{ formatTime(selectedRecord.end_time || '') }}
            </a-descriptions-item>
            <a-descriptions-item label="持续时间">
              {{ formatDuration(selectedRecord.start_time, selectedRecord.end_time) }}
            </a-descriptions-item>
            <a-descriptions-item label="完成进度">
              {{ selectedRecord.completed_tasks }}/{{ selectedRecord.total_tasks }}
            </a-descriptions-item>
          </a-descriptions>

          <a-divider />

          <a-descriptions title="同步结果" bordered size="small" :column="1">
            <template v-for="(result, dataType) in selectedRecord.results" :key="dataType">
              <a-descriptions-item :label="dataType">
                <a-tag :color="result.error ? 'red' : 'green'">
                  {{ result.error ? '失败' : '成功' }}
                </a-tag>
                <span v-if="result.error" style="color: #ff4d4f; margin-left: 8px;">
                  {{ result.error }}
                </span>
              </a-descriptions-item>
            </template>
          </a-descriptions>

          <a-alert
            v-if="selectedRecord.error"
            :message="selectedRecord.error"
            type="error"
            show-icon
            style="margin-top: 16px;"
          />
        </template>
      </a-drawer>
    </a-card>
  </div>
</template>

<style scoped lang="less">
.sync-history-page {
  padding: 24px;
  background-color: #f5f5f5;
  min-height: 100vh;
}

.filter-bar {
  margin-bottom: 16px;
  padding: 16px;
  background: #fff;
  border-radius: 6px;
}

:deep(.ant-table-thead > tr > th) {
  background-color: #fafafa;
  font-weight: 600;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background-color: #f5f5f5;
}
</style>