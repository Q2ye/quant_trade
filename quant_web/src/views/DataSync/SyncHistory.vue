<!-- quant_web/src/views/DataSync/SyncHistory.vue -->
<script setup lang="ts">
import { onMounted, reactive, ref, h } from 'vue'
import { Alert, Button, Card, DatePicker, Descriptions, Divider, Drawer, Select, Space,  Tag } from 'ant-design-vue'
import { ArrowLeftOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { useRouter } from 'vue-router'
import type { Dayjs } from 'dayjs'

const SelectOption = Select.Option
const DescriptionsItem = Descriptions.Item
const RangePicker = DatePicker.RangePicker

const router = useRouter()

const handleBack = () => {
  router.go(-1)
}

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

const loading = ref(false)
const records = ref<SyncRecord[]>([])
const selectedRecord = ref<SyncRecord | null>(null)
const drawerVisible = ref(false)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0
})

const filters = reactive({
  status: '',
  dateRange: [] as [Dayjs, Dayjs] | []
})

const columns = [
  {
    title: '任务ID',
    dataIndex: 'task_id',
    key: 'task_id',
    width: 120
  },
  {
    title: '数据类型',
    dataIndex: 'data_types',
    key: 'data_types',
    render: (types: string[]) => types.join(', ')
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (status: string) => {
      const statusConfig = {
        completed: { color: 'var(--success-color)', text: '完成' },
        running: { color: 'var(--accent-color)', text: '运行中' },
        failed: { color: 'var(--danger-color)', text: '失败' },
        cancelled: { color: 'var(--warning-color)', text: '已取消' }
      }
      const config = statusConfig[status as keyof typeof statusConfig] || { color: 'default', text: status }
      return h(Tag, { color: config.color }, () => config.text)
    }
  },
  {
    title: '开始时间',
    dataIndex: 'start_time',
    key: 'start_time'
  },
  {
    title: '完成进度',
    key: 'progress',
    render: (record: SyncRecord) => `${record.completed_tasks}/${record.total_tasks}`
  },
  {
    title: '操作',
    key: 'actions',
    render: (record: SyncRecord) => h(Button, {
      type: 'link',
      onClick: () => showDetails(record)
    }, () => '详情')
  }
]

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    completed: 'var(--success-color)',
    running: 'var(--accent-color)',
    failed: 'var(--danger-color)',
    cancelled: 'var(--warning-color)'
  }
  return colors[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    completed: '完成',
    running: '运行中',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return time
}

const formatDuration = (startTime: string, endTime?: string) => {
  if (!endTime) return '-'
  return '计算中...'
}

const showDetails = (record: SyncRecord) => {
  selectedRecord.value = record
  drawerVisible.value = true
}

const closeDrawer = () => {
  drawerVisible.value = false
  selectedRecord.value = null
}

const handleSearch = () => {
  pagination.current = 1
  loadHistory()
}

const handleReset = () => {
  filters.status = ''
  filters.dateRange = []
  pagination.current = 1
  loadHistory()
}

const handleTableChange = (pag: any) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadHistory()
}

const loadHistory = async () => {
  loading.value = true
  try {
    records.value = [
      {
        id: '1',
        task_id: 'TASK_001',
        data_types: ['市场数据', 'K线数据'],
        status: 'completed',
        start_time: '2024-01-15 10:00:00',
        end_time: '2024-01-15 10:15:00',
        duration: 900,
        total_tasks: 100,
        completed_tasks: 100,
        results: {
          '市场数据': { error: null },
          'K线数据': { error: null }
        }
      }
    ]
    pagination.total = records.value.length
  } catch (error) {
    console.error('加载同步历史失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<template>
  <div class="sync-history-page">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步历史记录</h1>
          <p class="page-description">查看和管理历史数据同步任务记录</p>
        </div>
        <div class="header-actions-right">
          <a-button class="back-btn" @click="handleBack">
            <template #icon>
              <ArrowLeftOutlined />
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>

    <Card class="history-card">
      <div class="filter-bar">
        <Space :size="16" wrap>
          <Select
            v-model:value="filters.status"
            placeholder="状态筛选"
            style="width: 120px"
            allow-clear
            class="status-select"
          >
            <SelectOption value="completed">完成</SelectOption>
            <SelectOption value="running">运行中</SelectOption>
            <SelectOption value="failed">失败</SelectOption>
            <SelectOption value="cancelled">已取消</SelectOption>
          </Select>

          <RangePicker
            v-model:value="filters.dateRange"
            style="width: 240px"
            :placeholder="['开始日期', '结束日期']"
            class="date-picker"
          />

          <Button type="primary" @click="handleSearch" class="search-btn">
            <SearchOutlined />
            搜索
          </Button>

          <Button @click="handleReset" class="reset-btn">重置</Button>

          <Button @click="loadHistory" :loading="loading" class="refresh-btn">
            <ReloadOutlined />
            刷新
          </Button>
        </Space>
      </div>

      <a-table
        :columns="columns"
        :data-source="records"
        :pagination="pagination"
        :loading="loading"
        :row-key="(record: SyncRecord) => record.id"
        @change="handleTableChange"
        :scroll="{ x: 1000 }"
        class="history-table"
      />

      <Drawer
        :open="drawerVisible"
        title="同步任务详情"
        placement="right"
        width="600"
        :closable="true"
        @close="closeDrawer"
        class="detail-drawer"
      >
        <template v-if="selectedRecord">
          <Descriptions title="任务信息" bordered size="small" :column="1">
            <DescriptionsItem label="任务ID">
              {{ selectedRecord.task_id }}
            </DescriptionsItem>
            <DescriptionsItem label="数据类型">
              {{ selectedRecord.data_types.join(', ') }}
            </DescriptionsItem>
            <DescriptionsItem label="状态">
              <Tag :color="getStatusColor(selectedRecord.status)">
                {{ getStatusText(selectedRecord.status) }}
              </Tag>
            </DescriptionsItem>
            <DescriptionsItem label="开始时间">
              {{ formatTime(selectedRecord.start_time) }}
            </DescriptionsItem>
            <DescriptionsItem label="结束时间">
              {{ formatTime(selectedRecord.end_time || '') }}
            </DescriptionsItem>
            <DescriptionsItem label="持续时间">
              {{ formatDuration(selectedRecord.start_time, selectedRecord.end_time) }}
            </DescriptionsItem>
            <DescriptionsItem label="完成进度">
              {{ selectedRecord.completed_tasks }}/{{ selectedRecord.total_tasks }}
            </DescriptionsItem>
          </Descriptions>

          <Divider />

          <Descriptions title="同步结果" bordered size="small" :column="1">
            <template v-for="(result, dataType) in selectedRecord.results" :key="dataType">
              <DescriptionsItem :label="dataType">
                <Tag :color="result.error ? 'var(--danger-color)' : 'var(--success-color)'">
                  {{ result.error ? '失败' : '成功' }}
                </Tag>
                <span v-if="result.error" class="error-text">
                  {{ result.error }}
                </span>
              </DescriptionsItem>
            </template>
          </Descriptions>

          <Alert
            v-if="selectedRecord.error"
            :message="selectedRecord.error"
            type="error"
            show-icon
            class="error-alert"
          />
        </template>
      </Drawer>
    </Card>
  </div>
</template>

<style scoped lang="scss">

@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';

.sync-history-page {
  padding: 0;
  max-width: 1400px;
  margin: 0 auto;
  background: $primary-bg;
  min-height: 100vh;
}

.page-header {
  background: $page-header-bg;
  color: white;
  padding: map.get($spacers, 4) 0;
  margin-bottom: map.get($spacers, 4);

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 map.get($spacers, 4);

    .header-actions-right {
      display: flex;
      align-items: center;
      gap: map.get($spacers, 2);
      flex-shrink: 0;
    }
  }

  .title-section {
    flex: 1;

    .page-title {
      margin: 0;
      font-size: $page-title-font-size;
      font-weight: $font-weight-bold;
      color: white;
    }

    .page-description {
      margin: map.get($spacers, 1) 0 0 0;
      opacity: 0.9;
      font-size: $page-description-font-size;
      color: rgba(255, 255, 255, 0.9);
    }
  }
}

.back-btn {
  @include mixin.button-base(rgba(255, 255, 255, 0.15), white);
  border: 1px solid rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(10px);
  box-shadow: $card-shadow;
  height: $button-height;
  display: flex;
  align-items: center;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
  }
}

.history-card {
  @include mixin.card-base;
  margin: 0 map.get($spacers, 4);

  :deep(.ant-card-body) {
    padding: map.get($spacers, 3);
  }
}

.filter-bar {
  margin-bottom: map.get($spacers, 3);
  padding: map.get($spacers, 3);
  background: $secondary-bg;
  border-radius: $border-radius;
  border: 1px solid $border-color;
}

.history-table {
  :deep(.ant-table-thead > tr > th) {
    background-color: $toolbar-bg;
    font-weight: $font-weight-semibold;
    color: $text-primary;
    border-bottom: 1px solid $border-color;
  }

  :deep(.ant-table-tbody > tr > td) {
    border-bottom: 1px solid $border-color;
    color: $text-primary;
  }

  :deep(.ant-table-tbody > tr:hover > td) {
    background-color: $hover-bg;
  }

  :deep(.ant-table-pagination) {
    margin: map.get($spacers, 3) 0 0 0;
    padding: map.get($spacers, 2) 0;
    border-top: 1px solid $border-color;
  }
}

.detail-drawer {
  :deep(.ant-drawer-header) {
    background: $toolbar-bg;
    border-bottom: 1px solid $border-color;

    .ant-drawer-title {
      color: $text-primary;
      font-weight: $font-weight-semibold;
    }
  }

  :deep(.ant-drawer-body) {
    background: $primary-bg;
    padding: map.get($spacers, 3);
  }
}

.refresh-btn,
.search-btn,
.reset-btn {
  @include mixin.button-base;
}

.error-text {
  color: $danger-color;
  margin-left: map.get($spacers, 2);
}

.error-alert {
  margin-top: map.get($spacers, 3);
}

// 响应式调整
@include mixin.media-breakpoint-down(md) {
  .page-header .header-content {
    flex-direction: column;
    gap: map.get($spacers, 3);
    text-align: center;

    .header-actions-right {
      order: -1;
      align-self: stretch;
      justify-content: space-between;
      margin-bottom: map.get($spacers, 2);
    }
  }

  .history-card {
    margin: 0 map.get($spacers, 3);
  }

  .filter-bar {
    padding: map.get($spacers, 2);
  }
}

@include mixin.media-breakpoint-down(sm) {
  .history-card {
    margin: 0 map.get($spacers, 2);
  }

  .filter-bar {
    .ant-space {
      width: 100%;

      .ant-space-item {
        width: 100%;

        .ant-select, .ant-picker, .ant-btn {
          width: 100%;
        }
      }
    }
  }
}
</style>