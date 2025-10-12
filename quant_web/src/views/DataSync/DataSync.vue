<!-- quant_web/src/views/DataSync/DataSync.vue -->
<script setup lang="ts">
import {computed, h, onMounted, onUnmounted, reactive, ref, watch} from 'vue'
import {message, Modal} from 'ant-design-vue'
import {
  CheckCircleOutlined,
  CloudDownloadOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  SyncOutlined,
  ClockCircleOutlined,  // 添加缺失的图标
  HourglassOutlined     // 添加缺失的图标
} from '@ant-design/icons-vue'
import {useRoute} from 'vue-router'
import type {BatchSyncRequest, DataTypeInfo, SyncResponse, SyncStatusResponse} from '@/api/data-sync'
import {dataSyncService} from '@/api/data-sync'

// 完整的数据类型选项 - 作为降级数据
const fallbackDataTypes = [
  { code: 'stock_basic', name: '股票列表', description: '股票基础信息', estimated_time: 30 },
  { code: 'trade_calendar', name: '交易日历', description: '交易所交易日历', estimated_time: 5 },
  { code: 'daily', name: '日线行情', description: 'A股日线行情数据', estimated_time: 120 },
  { code: 'minute', name: '分钟行情', description: '分钟级行情数据', estimated_time: 180 },
  { code: 'weekly', name: '周线行情', description: '周线行情数据', estimated_time: 60 },
  { code: 'monthly', name: '月线行情', description: '月线行情数据', estimated_time: 45 },
  { code: 'financial', name: '财务数据', description: '财务报表数据', estimated_time: 90 },
  { code: 'moneyflow', name: '资金流向', description: '资金流向数据', estimated_time: 75 },
  { code: 'etf', name: 'ETF数据', description: 'ETF基础信息和行情', estimated_time: 40 },
  { code: 'adj_factor', name: '复权因子', description: '股票复权因子', estimated_time: 25 },
  { code: 'daily_basic', name: '每日指标', description: '每日基本面指标', estimated_time: 50 },
  { code: 'daily_limit', name: '涨跌停价格', description: '每日涨跌停价格', estimated_time: 20 },
  { code: 'st_list', name: 'ST股票列表', description: 'ST股票历史记录', estimated_time: 15 },
  { code: 'company', name: '公司信息', description: '上市公司基本信息', estimated_time: 35 },
  { code: 'managers', name: '管理层信息', description: '公司管理层信息', estimated_time: 25 }
]

// 路由实例
const route = useRoute()

// 响应式数据
const isLoading = ref(false)
const isCheckingStatus = ref(false)
// 删除未使用的 isTaskLoading 变量
const statusPollingInterval = ref<NodeJS.Timeout | null>(null)
const dataTypesLoadFailed = ref(false)

// 同步状态和数据类型
const syncStatus = ref<SyncStatusResponse | null>(null)
const supportedDataTypes = ref<DataTypeInfo[]>([])

// 同步配置表单 - 与后端BatchSyncRequest完全匹配
const syncConfig = reactive({
  data_types: [] as string[],           // 数据类型列表
  days: 30,                            // 同步天数
  start_date: '',                      // 开始日期
  end_date: '',                        // 结束日期
  stock_codes: [] as string[],         // 股票代码列表
  exchange: '',                        // 交易所代码
  batch_size: 100                      // 批量处理大小
})

/**
 * 初始化页面数据
 */
const initializePage = async () => {
  await Promise.all([
    checkSyncStatus(),
    fetchSupportedDataTypes()
  ])
}

/**
 * 获取支持的数据类型列表
 */
const fetchSupportedDataTypes = async () => {
  try {
    supportedDataTypes.value = await dataSyncService.getSupportedDataTypes()
    dataTypesLoadFailed.value = false
  } catch (error) {
    console.error('获取数据类型列表失败，使用降级数据:', error)
    supportedDataTypes.value = fallbackDataTypes
    dataTypesLoadFailed.value = true
    message.warning('使用本地数据类型列表，部分功能可能受限')
  }
}

/**
 * 检查同步状态
 */
const checkSyncStatus = async () => {
  isCheckingStatus.value = true
  try {
    const status = await dataSyncService.getSyncStatus()
    syncStatus.value = status

    // 如果任务正在运行，启动轮询
    if (status.is_running && !statusPollingInterval.value) {
      startStatusPolling()
    } else if (!status.is_running && statusPollingInterval.value) {
      stopStatusPolling()
    }
  } catch (error) {
    console.error('获取同步状态失败:', error)
    // 设置默认状态
    syncStatus.value = {
      is_running: false,
      progress: 0,
      total_tasks: 0,
      completed_tasks: 0,
      error: '获取状态失败'
    } as SyncStatusResponse
  } finally {
    isCheckingStatus.value = false
  }
}

/**
 * 启动状态轮询
 */
const startStatusPolling = () => {
  if (statusPollingInterval.value) return

  statusPollingInterval.value = setInterval(async () => {
    try {
      const status = await dataSyncService.getSyncStatus()
      syncStatus.value = status

      // 如果任务完成，停止轮询
      if (!status.is_running) {
        stopStatusPolling()
        message.success('数据同步任务已完成')
      }
    } catch (error) {
      console.error('轮询同步状态失败:', error)
    }
  }, 2000) // 每2秒轮询一次
}

/**
 * 停止状态轮询
 */
const stopStatusPolling = () => {
  if (statusPollingInterval.value) {
    clearInterval(statusPollingInterval.value)
    statusPollingInterval.value = null
  }
}

/**
 * 处理批量数据同步
 */
const handleBatchSync = async () => {
  // 表单验证
  if (!syncConfig.data_types.length) {
    message.warning('请选择至少一种数据类型')
    return
  }

  if (syncConfig.days < 1 || syncConfig.days > 365) {
    message.warning('同步天数必须在1-365之间')
    return
  }

  isLoading.value = true
  try {
    const requestData: BatchSyncRequest = {
      data_types: syncConfig.data_types,
      days: syncConfig.days,
      start_date: syncConfig.start_date || undefined,
      end_date: syncConfig.end_date || undefined,
      stock_codes: syncConfig.stock_codes.length ? syncConfig.stock_codes : undefined,
      exchange: syncConfig.exchange || undefined,
      batch_size: syncConfig.batch_size
    }

    const response: SyncResponse = await dataSyncService.batchSyncData(requestData)

    message.success(response.message)

    // 启动状态轮询
    startStatusPolling()

  } catch (error: any) {
    console.error('同步任务启动失败:', error)
    message.error(error.response?.data?.detail || '同步任务启动失败')
  } finally {
    isLoading.value = false
  }
}

/**
 * 处理快速同步（最近30天）
 */
const handleQuickSync = () => {
  syncConfig.days = 30
  syncConfig.start_date = ''
  syncConfig.end_date = ''
  handleBatchSync()
}

/**
 * 处理全量同步
 */
const handleFullSync = () => {
  Modal.confirm({
    title: '确认全量同步',
    icon: () => h(ExclamationCircleOutlined),
    content: '全量同步将重新下载所有历史数据，耗时较长，可能会影响系统性能，确定继续吗？',
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      syncConfig.data_types = supportedDataTypes.value.map(type => type.code)
      syncConfig.days = 365 // 全量同步一年数据
      syncConfig.start_date = ''
      syncConfig.end_date = ''
      await handleBatchSync()
    }
  })
}

/**
 * 取消同步任务
 */
const handleCancelSync = async () => {
  try {
    await dataSyncService.cancelSync()
    message.success('同步任务已取消')
    stopStatusPolling()
    await checkSyncStatus() // 刷新状态
  } catch (error: any) {
    console.error('取消同步任务失败:', error)
    message.error(error.response?.data?.detail || '取消同步任务失败')
  }
}

/**
 * 处理股票代码输入
 */
const handleStockCodesInput = (value: string) => {
  if (!value.trim()) {
    syncConfig.stock_codes = []
    return
  }

  // 分割并清理股票代码
  syncConfig.stock_codes = value.split(',')
    .map(code => code.trim())
    .filter(code => code.length > 0)
}

/**
 * 格式化时间显示
 */
const formatTime = (timeString?: string) => {
  if (!timeString) return '--'
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN')
  } catch (error) {
    return timeString
  }
}

/**
 * 计算预计剩余时间
 */
const estimatedRemainingTime = computed(() => {
  if (!syncStatus.value || !syncStatus.value.is_running) return 0

  const elapsed = syncStatus.value.elapsed_time || 0
  const progress = syncStatus.value.progress || 0

  if (progress <= 0) return 0
  return Math.round((elapsed / progress) * (100 - progress))
})

/**
 * 状态标签颜色
 */
const statusColor = computed(() => {
  if (!syncStatus.value) return 'default'

  if (syncStatus.value.error) return 'error'
  if (syncStatus.value.is_running) return 'processing'
  if (syncStatus.value.progress === 100) return 'success'
  return 'default'
})

/**
 * 状态标签文本
 */
const statusText = computed(() => {
  if (!syncStatus.value) return '未知'

  if (syncStatus.value.error) return '错误'
  if (syncStatus.value.is_running) return '同步中'
  if (syncStatus.value.progress === 100) return '已完成'
  return '就绪'
})

// 监听路由变化，当进入数据同步页面时初始化数据
watch(() => route.path, (newPath) => {
  if (newPath === '/data-sync') {
    initializePage()
  }
})

// 组件挂载时初始化
onMounted(() => {
  initializePage()
})

// 组件卸载时清理轮询
onUnmounted(() => {
  stopStatusPolling()
})
</script>

<template>
  <div class="data-sync-page">
    <!-- 页面标题和状态概览 -->
    <a-card class="page-header-card" :bordered="false">
      <div class="page-header">
        <div class="page-title">
          <h1>数据同步中心</h1>
          <p class="page-description">统一管理金融数据的同步任务和状态监控</p>
        </div>
        <div class="status-indicator">
          <a-tag :color="statusColor" class="status-tag">
            <SyncOutlined v-if="syncStatus?.is_running" spin />
            <CheckCircleOutlined v-else-if="syncStatus?.progress === 100" />
            <ExclamationCircleOutlined v-else-if="syncStatus?.error" />
            <InfoCircleOutlined v-else />
            {{ statusText }}
          </a-tag>
        </div>
      </div>
    </a-card>

    <!-- 状态概览卡片 -->
    <a-row :gutter="[16, 16]" class="status-overview">
      <a-col :xs="24" :sm="12" :md="6">
        <a-card size="small" class="status-card">
          <template #title>
            <div class="card-title">
              <SyncOutlined />
              <span>同步状态</span>
            </div>
          </template>
          <div class="status-content">
            <div class="status-value">{{ statusText }}</div>
            <div class="status-time" v-if="syncStatus?.last_run">
              最后同步: {{ formatTime(syncStatus.last_run) }}
            </div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :sm="12" :md="6">
        <a-card size="small" class="status-card">
          <template #title>
            <div class="card-title">
              <CloudDownloadOutlined />
              <span>任务进度</span>
            </div>
          </template>
          <div class="progress-content">
            <a-progress
              type="circle"
              :percent="syncStatus?.progress || 0"
              :width="60"
              :stroke-color="{
                '0%': '#108ee9',
                '100%': '#87d068',
              }"
              :status="syncStatus?.error ? 'exception' : 'normal'"
            />
            <div class="progress-text">
              {{ syncStatus?.completed_tasks || 0 }}/{{ syncStatus?.total_tasks || 0 }}
            </div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :sm="12" :md="6">
        <a-card size="small" class="status-card">
          <template #title>
            <div class="card-title">
              <ClockCircleOutlined />
              <span>运行时间</span>
            </div>
          </template>
          <div class="time-content">
            <div class="time-value">{{ syncStatus?.elapsed_time || 0 }}秒</div>
            <div class="time-label">已运行</div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :sm="12" :md="6">
        <a-card size="small" class="status-card">
          <template #title>
            <div class="card-title">
              <HourglassOutlined />
              <span>预计剩余</span>
            </div>
          </template>
          <div class="time-content">
            <div class="time-value">{{ estimatedRemainingTime }}秒</div>
            <div class="time-label">剩余时间</div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 主要配置区域 -->
    <a-row :gutter="[16, 16]">
      <!-- 同步配置卡片 -->
      <a-col :xs="24" :lg="16">
        <a-card title="数据同步配置" class="sync-config-card">
          <template #extra>
            <a-alert
              v-if="dataTypesLoadFailed"
              message="使用本地数据类型"
              description="后端服务不可用，使用本地数据类型列表"
              type="warning"
              show-icon
              size="small"
            />
          </template>

          <a-form layout="vertical" :model="syncConfig">
            <!-- 数据类型选择 -->
            <a-form-item label="数据类型" required>
              <div class="form-item-description">选择需要同步的数据类型，可多选</div>
              <a-checkbox-group v-model:value="syncConfig.data_types" class="data-type-group">
                <a-row :gutter="[12, 12]">
                  <a-col :xs="12" :sm="8" :md="6" v-for="type in supportedDataTypes" :key="type.code">
                    <a-checkbox :value="type.code" class="data-type-checkbox">
                      <div class="data-type-item">
                        <div class="type-label">{{ type.name }}</div>
                        <div class="type-description">{{ type.description }}</div>
                        <div class="type-estimate">预计: {{ type.estimated_time }}秒</div>
                      </div>
                    </a-checkbox>
                  </a-col>
                </a-row>
              </a-checkbox-group>
            </a-form-item>

            <a-row :gutter="16">
              <!-- 时间参数 -->
              <a-col :xs="24" :md="12">
                <a-form-item label="同步天数">
                  <div class="form-item-description">同步最近N天的数据 (1-365天)</div>
                  <a-input-number
                    v-model:value="syncConfig.days"
                    :min="1"
                    :max="365"
                    style="width: 100%"
                    placeholder="请输入同步天数"
                  />
                </a-form-item>

                <a-form-item label="时间范围 (可选)">
                  <div class="form-item-description">指定具体的开始和结束日期，优先级高于同步天数</div>
                  <a-space direction="vertical" style="width: 100%">
                    <a-date-picker
                      v-model:value="syncConfig.start_date"
                      placeholder="开始日期"
                      style="width: 100%"
                      format="YYYYMMDD"
                    />
                    <a-date-picker
                      v-model:value="syncConfig.end_date"
                      placeholder="结束日期"
                      style="width: 100%"
                      format="YYYYMMDD"
                    />
                  </a-space>
                </a-form-item>
              </a-col>

              <!-- 股票和批量参数 -->
              <a-col :xs="24" :md="12">
                <a-form-item label="股票代码">
                  <div class="form-item-description">输入股票代码，多个用逗号分隔，留空则同步全市场</div>
                  <a-textarea
                    :value="syncConfig.stock_codes.join(',')"
                    @input="(e: any) => handleStockCodesInput(e.target?.value || '')"
                    placeholder="例如：000001.SZ,600000.SH"
                    :rows="3"
                    show-count
                    :maxlength="1000"
                  />
                </a-form-item>

                <a-row :gutter="12">
                  <a-col :xs="12">
                    <a-form-item label="交易所">
                      <a-select v-model:value="syncConfig.exchange" placeholder="选择交易所" style="width: 100%">
                        <a-select-option value="SSE">上交所</a-select-option>
                        <a-select-option value="SZSE">深交所</a-select-option>
                        <a-select-option value="BSE">北交所</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :xs="12">
                    <a-form-item label="批量大小">
                      <a-input-number
                        v-model:value="syncConfig.batch_size"
                        :min="1"
                        :max="500"
                        style="width: 100%"
                        placeholder="批量处理大小"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-col>
            </a-row>
          </a-form>
        </a-card>
      </a-col>

      <!-- 操作按钮卡片 -->
      <a-col :xs="24" :lg="8">
        <a-card title="同步操作" class="action-card">
          <div class="action-buttons">
            <a-button
              type="primary"
              @click="handleBatchSync"
              :loading="isLoading"
              :disabled="syncStatus?.is_running"
              block
              size="large"
              class="action-button"
            >
              <template #icon><CloudDownloadOutlined /></template>
              开始同步
            </a-button>

            <a-button
              @click="handleQuickSync"
              :loading="isLoading"
              :disabled="syncStatus?.is_running"
              block
              size="large"
              class="action-button"
            >
              <template #icon><SyncOutlined /></template>
              快速同步(30天)
            </a-button>

            <a-button
              danger
              @click="handleFullSync"
              :loading="isLoading"
              :disabled="syncStatus?.is_running"
              block
              size="large"
              class="action-button"
            >
              <template #icon><SyncOutlined /></template>
              全量同步
            </a-button>

            <a-space direction="vertical" style="width: 100%" class="utility-buttons">
              <a-button @click="checkSyncStatus" :loading="isCheckingStatus" block>
                <template #icon><ReloadOutlined /></template>
                刷新状态
              </a-button>

              <a-button
                v-if="syncStatus?.is_running"
                danger
                @click="handleCancelSync"
                :loading="isLoading"
                block
              >
                <template #icon><PauseCircleOutlined /></template>
                取消同步
              </a-button>
            </a-space>
          </div>
        </a-card>

        <!-- 同步提示卡片 -->
        <a-card title="同步说明" class="tips-card" size="small">
          <a-alert
            message="数据同步说明"
            description="数据同步任务将在后台执行，系统会自动轮询状态更新。单个数据类型失败不会影响其他类型的同步。建议在非交易时间段执行全量同步操作。"
            type="info"
            show-icon
          />
        </a-card>
      </a-col>
    </a-row>

    <!-- 任务状态信息 -->
    <a-row :gutter="[16, 16]" v-if="syncStatus?.is_running || syncStatus?.results">
      <!-- 当前任务状态 -->
      <a-col :xs="24" :lg="12" v-if="syncStatus?.is_running">
        <a-card title="当前任务状态" class="task-status-card" size="small">
          <a-descriptions bordered size="small" :column="1">
            <a-descriptions-item label="当前任务">
              {{ syncStatus.current_task || '--' }}
            </a-descriptions-item>
            <a-descriptions-item label="任务ID">
              {{ syncStatus.task_id || '--' }}
            </a-descriptions-item>
            <a-descriptions-item label="进度">
              {{ syncStatus.progress }}%
            </a-descriptions-item>
            <a-descriptions-item label="已完成">
              {{ syncStatus.completed_tasks }}/{{ syncStatus.total_tasks }}
            </a-descriptions-item>
            <a-descriptions-item label="开始时间">
              {{ formatTime(syncStatus.start_time) }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>

      <!-- 同步结果 -->
      <a-col :xs="24" :lg="12" v-if="syncStatus?.results && Object.keys(syncStatus.results).length > 0">
        <a-card title="同步结果" class="results-card" size="small">
          <a-list
            item-layout="horizontal"
            :data-source="Object.entries(syncStatus.results)"
            size="small"
          >
            <template #default="{ item }">
              <a-list-item class="result-item">
                <template #actions>
                  <a-tag :color="item[1].error ? 'red' : 'green'" size="small">
                    {{ item[1].error ? '失败' : '成功' }}
                  </a-tag>
                </template>
                <a-list-item-meta :description="item[1].error || '同步成功'">
                  <template #title>
                    <span class="result-title">{{ item[0] }}</span>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>

    <!-- 错误信息 -->
    <a-card v-if="syncStatus?.error" title="错误信息" class="error-card" size="small">
      <a-alert
        :message="syncStatus.error"
        type="error"
        show-icon
      />
    </a-card>
  </div>
</template>

<!-- 样式部分保持不变 -->
<style scoped lang="less">
/* 原有的样式代码保持不变 */
</style>