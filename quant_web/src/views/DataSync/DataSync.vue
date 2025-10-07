<script setup lang="ts">
import {computed, onActivated, onMounted, reactive, ref, watch} from 'vue'
import {message, Modal} from 'ant-design-vue'
import {
  CheckCircleOutlined,
  CloudDownloadOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  SyncOutlined
} from '@ant-design/icons-vue'
import {useRoute} from "vue-router";

// 在 setup 中添加
const route = useRoute()

// 添加路由监听
watch(() => route.path, (newPath, oldPath) => {
  if (newPath === '/data-sync') {
    console.log('路由切换到数据同步页面，重新加载数据')
    checkSyncStatus()
    fetchSyncTasks()
  }
})

// 添加组件激活时的处理
onActivated(() => {
  console.log('DataSync组件被激活')
  checkSyncStatus()
  fetchSyncTasks()
})

// 现有的 onMounted 保持不变
onMounted(() => {
  console.log('DataSync组件挂载')
  checkSyncStatus()
  fetchSyncTasks()
})

interface SyncConfig {
  dataType: string[]
  symbolCodes: string
  dateRange: [string, string]
  syncMode: 'incremental' | 'full'
  frequency?: string
}

interface SyncTask {
  id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  start_time: string
  end_time?: string
  total_records: number
  error_message?: string
}

interface SyncStatus {
  status: 'completed' | 'running' | 'pending' | 'error' | 'unknown'
  last_sync_time?: string
  next_sync_time?: string
  running_tasks: number
  completed_today: number
}

const syncConfig = reactive<SyncConfig>({
  dataType: ['daily'],
  symbolCodes: '',
  dateRange: ['', ''],
  syncMode: 'incremental',
  frequency: 'D'
})

// 完整的数据类型选项
const dataTypes = [
  {label: '股票列表', value: 'stock_basic', description: '股票基础信息'},
  {label: '交易日历', value: 'trade_calendar', description: '交易所交易日历'},
  {label: '日线行情', value: 'daily', description: 'A股日线行情数据'},
  {label: '分钟行情', value: 'minute', description: '分钟级行情数据'},
  {label: '周线行情', value: 'weekly', description: '周线行情数据'},
  {label: '月线行情', value: 'monthly', description: '月线行情数据'},
  {label: '财务数据', value: 'financial', description: '财务报表数据'},
  {label: '资金流向', value: 'moneyflow', description: '资金流向数据'},
  {label: 'ETF数据', value: 'etf', description: 'ETF基础信息和行情'},
  {label: '复权因子', value: 'adj_factor', description: '股票复权因子'},
  {label: '每日指标', value: 'daily_basic', description: '每日基本面指标'},
  {label: '涨跌停价格', value: 'daily_limit', description: '每日涨跌停价格'},
  {label: 'ST股票列表', value: 'st_list', description: 'ST股票历史记录'},
  {label: '公司信息', value: 'company', description: '上市公司基本信息'},
  {label: '管理层信息', value: 'managers', description: '公司管理层信息'}
]

// 频率选项
const frequencyOptions = [
  {label: '日线', value: 'D'},
  {label: '1分钟', value: '1min'},
  {label: '5分钟', value: '5min'},
  {label: '15分钟', value: '15min'},
  {label: '30分钟', value: '30min'},
  {label: '60分钟', value: '60min'}
]

const isLoading = ref(false)
const syncStatus = ref<SyncStatus | null>(null)
const isCheckingStatus = ref(false)
const syncTasks = ref<SyncTask[]>([])
const isTaskLoading = ref(false)

// 检查同步状态
const checkSyncStatus = async () => {
  isCheckingStatus.value = true
  try {
    const response = await fetch('/api/system/data/status')
    if (response.ok) {
      const data = await response.json()
      // 确保数据结构完整，添加更严格的验证
      syncStatus.value = {
        status: data?.status || 'unknown',
        last_sync_time: data?.last_sync_time || '',
        next_sync_time: data?.next_sync_time || '',
        running_tasks: typeof data?.running_tasks === 'number' ? data.running_tasks : 0,
        completed_today: typeof data?.completed_today === 'number' ? data.completed_today : 0
      }
    } else {
      console.warn('获取同步状态失败，状态码:', response.status)
      // 设置更合理的默认状态
      syncStatus.value = {
        status: 'unknown',
        last_sync_time: '',
        next_sync_time: '',
        running_tasks: 0,
        completed_today: 0
      }
    }
  } catch (error) {
    console.error('获取同步状态失败:', error)
    message.error('获取同步状态失败')
    // 设置合理的错误状态
    syncStatus.value = {
      status: 'error',
      last_sync_time: '',
      next_sync_time: '',
      running_tasks: 0,
      completed_today: 0
    }
  } finally {
    isCheckingStatus.value = false
  }
}

// 获取同步任务列表 - 修复API路径
const fetchSyncTasks = async () => {
  isTaskLoading.value = true
  try {
    const response = await fetch('/api/system/data/sync/tasks?limit=10')
    if (response.ok) {
      const data = await response.json()
      // 确保数据是数组，并验证每个任务的字段
      if (Array.isArray(data)) {
        syncTasks.value = data.map(task => ({
          id: task.id || `task_${Date.now()}_${Math.random()}`,
          task_type: task.task_type || 'unknown',
          status: task.status || 'pending',
          start_time: task.start_time || '',
          end_time: task.end_time || '',
          total_records: typeof task.total_records === 'number' ? task.total_records : 0,
          error_message: task.error_message || ''
        }))
      } else {
        console.warn('任务数据不是数组:', data)
        syncTasks.value = []
      }
    } else {
      console.warn('获取任务列表失败，状态码:', response.status)
      syncTasks.value = []
    }
  } catch (error) {
    console.error('获取同步任务失败:', error)
    syncTasks.value = []
  } finally {
    isTaskLoading.value = false
  }
}

// 处理数据同步
const handleSync = async () => {
  if (!syncConfig.dataType.length) {
    message.warning('请选择至少一种数据类型')
    return
  }

  // 增量同步需要时间范围
  if (syncConfig.syncMode === 'incremental' && (!syncConfig.dateRange[0] || !syncConfig.dateRange[1])) {
    message.warning('增量同步需要选择时间范围')
    return
  }

  isLoading.value = true
  try {
    const response = await fetch('/api/system/data/sync', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(syncConfig)
    })

    if (response.ok) {
      const result = await response.json()
      message.success(`数据同步任务已启动 (ID: ${result.sync_id})`)
      // 启动后刷新状态和任务列表
      setTimeout(() => {
        checkSyncStatus()
        fetchSyncTasks()
      }, 1000)
    } else {
      const error = await response.json()
      throw new Error(error.message || '同步任务启动失败')
    }
  } catch (error) {
    message.error('同步任务启动失败')
    console.error('同步错误:', error)
  } finally {
    isLoading.value = false
  }
}

// 处理全量同步
const handleFullSync = () => {
  Modal.confirm({
    title: '确认全量同步',
    content: '全量同步将重新下载所有历史数据，耗时较长，可能会影响系统性能，确定继续吗？',
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      syncConfig.syncMode = 'full'
      syncConfig.dateRange = ['', '']
      await handleSync()
    }
  })
}

// 处理快速同步（最近30天）
const handleQuickSync = () => {
  const endDate = new Date()
  const startDate = new Date()
  startDate.setDate(startDate.getDate() - 30)

  syncConfig.dateRange = [
    startDate.toISOString().split('T')[0],
    endDate.toISOString().split('T')[0]
  ]
  syncConfig.syncMode = 'incremental'

  handleSync()
}

// 重新执行任务
const handleRetryTask = async (taskId: string) => {
  try {
    const response = await fetch(`/api/system/data/sync/tasks/${taskId}/retry`, {
      method: 'POST'
    })

    if (response.ok) {
      message.success('任务已重新执行')
      fetchSyncTasks()
    } else {
      throw new Error('重新执行失败')
    }
  } catch (error) {
    message.error('重新执行任务失败')
    console.error('重新执行错误:', error)
  }
}

// 状态标签颜色
const statusColor = computed(() => {
  if (!syncStatus.value) return 'default'
  switch (syncStatus.value.status) {
    case 'completed':
      return 'success'
    case 'running':
      return 'processing'
    case 'pending':
      return 'warning'
    case 'error':
      return 'error'
    default:
      return 'default'
  }
})

// 状态标签文本
const statusText = computed(() => {
  if (!syncStatus.value) return '未知'
  switch (syncStatus.value.status) {
    case 'completed':
      return '已完成'
    case 'running':
      return '同步中'
    case 'pending':
      return '等待中'
    case 'error':
      return '异常'
    default:
      return '未知'
  }
})

// 获取状态颜色
const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'green'
    case 'running':
      return 'blue'
    case 'failed':
      return 'red'
    default:
      return 'orange'
  }
}

// 获取状态文本
const getStatusText = (status: string) => {
  switch (status) {
    case 'completed':
      return '完成'
    case 'running':
      return '运行中'
    case 'failed':
      return '失败'
    default:
      return '等待'
  }
}

// 时间格式化
const formatTime = (timeString: string) => {
  if (!timeString) return '--'
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN')
  } catch (error) {
    return timeString
  }
}

const safeTableData = computed(() => {
  if (!Array.isArray(syncTasks.value)) {
    return []
  }

  return syncTasks.value
    .filter(task => task != null) // 过滤掉 null 或 undefined
    .map(task => ({
      id: task.id || `task_${Date.now()}_${Math.random()}`,
      task_type: task.task_type || '未知类型',
      status: task.status || 'pending',
      start_time: task.start_time || '',
      end_time: task.end_time || '',
      total_records: typeof task.total_records === 'number' ? task.total_records : 0,
      error_message: task.error_message || ''
    }))
})

// 组件挂载时检查状态和任务列表
onMounted(() => {
  console.log('DataSync组件挂载')
  checkSyncStatus()
  fetchSyncTasks()
})
</script>

<template>
  <div class="data-sync-page">
    <!-- 状态概览卡片 -->
    <a-row :gutter="16" class="status-overview">
      <a-col :span="6">
        <a-card size="small">
          <template #title>
            <span>同步状态</span>
          </template>
          <div class="status-content">
            <a-tag :color="statusColor">{{ statusText }}</a-tag>
            <div class="status-time" v-if="syncStatus?.last_sync_time">
              最后同步: {{ formatTime(syncStatus.last_sync_time) }}
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small">
          <template #title>
            <span>运行任务</span>
          </template>
          <div class="status-number" :class="{ 'status-active': (syncStatus?.running_tasks || 0) > 0 }">
            {{ syncStatus?.running_tasks || 0 }}
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small">
          <template #title>
            <span>今日完成</span>
          </template>
          <div class="status-number">
            {{ syncStatus?.completed_today || 0 }}
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small">
          <template #title>
            <span>下次同步</span>
          </template>
          <div class="status-time">
            {{ syncStatus?.next_sync_time ? formatTime(syncStatus.next_sync_time) : '--' }}
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 同步配置卡片 -->
    <a-card title="数据同步配置" class="sync-card">
      <template #extra>
        <a-space>
          <a-button @click="checkSyncStatus" :loading="isCheckingStatus">
            <template #icon>
              <ReloadOutlined/>
            </template>
            刷新状态
          </a-button>
          <a-button @click="handleQuickSync" :disabled="isLoading">
            <template #icon>
              <CloudDownloadOutlined/>
            </template>
            快速同步(30天)
          </a-button>
          <a-button
              type="primary"
              :loading="isLoading"
              @click="handleSync"
          >
            <template #icon>
              <CloudDownloadOutlined/>
            </template>
            开始同步
          </a-button>
          <a-button
              danger
              @click="handleFullSync"
              :disabled="isLoading"
          >
            <template #icon>
              <SyncOutlined/>
            </template>
            全量同步
          </a-button>
        </a-space>
      </template>

      <a-form layout="vertical">
        <!-- 数据类型选择 -->
        <a-form-item label="数据类型" required>
          <div class="form-item-description">选择需要同步的数据类型，可多选</div>
          <a-checkbox-group v-model:value="syncConfig.dataType" class="data-type-group">
            <a-row :gutter="[16, 16]">
              <a-col :span="8" v-for="type in dataTypes" :key="type.value">
                <a-checkbox :value="type.value">
                  <div class="data-type-item">
                    <div class="type-label">{{ type.label }}</div>
                    <div class="type-description">{{ type.description }}</div>
                  </div>
                </a-checkbox>
              </a-col>
            </a-row>
          </a-checkbox-group>
        </a-form-item>

        <a-row :gutter="16">
          <!-- 标的代码输入 -->
          <a-col :span="12">
            <a-form-item label="标的代码">
              <div class="form-item-description">输入股票/ETF代码，多个用逗号分隔，留空则同步全市场</div>
              <a-textarea
                  v-model:value="syncConfig.symbolCodes"
                  placeholder="例如：000001.SZ,600000.SH,159001.SZ"
                  :rows="3"
                  show-count
                  :maxlength="1000"
              />
            </a-form-item>
          </a-col>

          <!-- 时间范围选择 -->
          <a-col :span="12">
            <a-form-item label="时间范围" v-if="syncConfig.syncMode === 'incremental'">
              <div class="form-item-description">选择增量同步的时间范围</div>
              <a-range-picker
                  v-model:value="syncConfig.dateRange"
                  format="YYYY-MM-DD"
                  style="width: 100%"
                  :placeholder="['开始日期', '结束日期']"
              />
            </a-form-item>

            <!-- 频率选择 -->
            <a-form-item label="数据频率" v-if="syncConfig.dataType.includes('minute')">
              <div class="form-item-description">选择分钟数据的频率</div>
              <a-radio-group v-model:value="syncConfig.frequency" button-style="solid">
                <a-radio-button v-for="freq in frequencyOptions" :key="freq.value" :value="freq.value">
                  {{ freq.label }}
                </a-radio-button>
              </a-radio-group>
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 同步模式选择 -->
        <a-form-item label="同步模式">
          <a-radio-group v-model:value="syncConfig.syncMode">
            <a-radio value="incremental">
              <div class="sync-mode-option">
                <div class="mode-title">增量同步</div>
                <div class="mode-description">同步最近N天的数据，节省时间和资源</div>
              </div>
            </a-radio>
            <a-radio value="full">
              <div class="sync-mode-option">
                <div class="mode-title">全量同步</div>
                <div class="mode-description">重新下载所有历史数据，耗时较长</div>
              </div>
            </a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 同步任务历史 -->
    <!-- 同步任务历史 -->
    <a-card title="同步任务历史" class="tasks-card">
      <template #extra>
        <a-button @click="fetchSyncTasks" :loading="isTaskLoading">
          <template #icon>
            <ReloadOutlined/>
          </template>
          刷新
        </a-button>
      </template>

      <!-- 修复表格列定义 - 使用安全的插槽参数处理 -->
      <a-table
          :dataSource="safeTableData"
          :loading="isTaskLoading"
          :pagination="{ pageSize: 10 }"
          size="small"
          :rowKey="(record: SyncTask) => record.id"
          :locale="{
            emptyText: '暂无同步任务'
          }"
      >
        <a-table-column key="task_type" title="任务类型" data-index="task_type">
          <template #default="{ text, record }">
            <!-- 添加安全检查 -->
            <a-tag>{{ text || (record && record.task_type) || '未知类型' }}</a-tag>
          </template>
        </a-table-column>

        <a-table-column key="status" title="状态" data-index="status">
          <template #default="{ text, record }">
            <!-- 添加安全检查 -->
            <a-tag :color="getStatusColor(text || (record && record.status))">
              <CheckCircleOutlined v-if="(text || (record && record.status)) === 'completed'"/>
              <SyncOutlined v-else-if="(text || (record && record.status)) === 'running'"/>
              <ExclamationCircleOutlined v-else-if="(text || (record && record.status)) === 'failed'"/>
              {{ getStatusText(text || (record && record.status)) }}
            </a-tag>
          </template>
        </a-table-column>

        <a-table-column key="start_time" title="开始时间" data-index="start_time">
          <template #default="{ text, record }">
            <!-- 添加安全检查 -->
            {{ text || (record && record.start_time) || '--' }}
          </template>
        </a-table-column>

        <a-table-column key="end_time" title="结束时间" data-index="end_time">
          <template #default="{ text, record }">
            <!-- 添加安全检查 -->
            {{ text || (record && record.end_time) || '--' }}
          </template>
        </a-table-column>

        <a-table-column key="total_records" title="记录数" data-index="total_records">
          <template #default="{ text, record }">
            <!-- 添加安全检查 -->
            {{ text || (record && record.total_records) || 0 }}
          </template>
        </a-table-column>

        <a-table-column key="actions" title="操作">
          <template #default="{ record }">
            <!-- 添加安全检查 -->
            <a-button
                v-if="record && record.status === 'failed'"
                type="link"
                size="small"
                @click="handleRetryTask(record.id)"
            >
              重试
            </a-button>
            <a-button type="link" size="small">
              详情
            </a-button>
          </template>
        </a-table-column>
      </a-table>
    </a-card>

    <!-- 同步提示 -->
    <div class="sync-tips">
      <a-alert
          message="数据同步说明"
          description="数据同步任务将在后台执行，您可以在'同步任务监控'页面查看详细执行进度和结果。建议在非交易时间段执行全量同步操作。"
          type="info"
          show-icon
      />
    </div>
  </div>
</template>

<style scoped>
.data-sync-page {
  padding: 24px;
}

.status-overview {
  margin-bottom: 24px;
}

.status-overview :deep(.ant-card) {
  height: 100%;
}

.status-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-number {
  font-size: 24px;
  font-weight: bold;
  color: #1890ff;
}

.status-active {
  color: #52c41a;
}

.status-time {
  font-size: 12px;
  color: #666;
}

.sync-card {
  margin-bottom: 24px;
}

.tasks-card {
  margin-bottom: 24px;
}

.data-type-group {
  width: 100%;
}

.data-type-item {
  padding: 4px 0;
}

.type-label {
  font-weight: 500;
  margin-bottom: 2px;
}

.type-description {
  font-size: 12px;
  color: #666;
  line-height: 1.2;
}

.form-item-description {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
  line-height: 1.2;
}

.sync-mode-option {
  padding: 4px 0;
}

.mode-title {
  font-weight: 500;
  margin-bottom: 2px;
}

.mode-description {
  font-size: 12px;
  color: #666;
  line-height: 1.2;
}

.sync-tips {
  max-width: 100%;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .data-sync-page {
    padding: 16px;
  }

  .status-overview .ant-col {
    margin-bottom: 16px;
  }

  .data-type-group .ant-col {
    width: 100%;
  }
}
</style>