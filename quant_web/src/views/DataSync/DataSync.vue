<!-- quant_web/src/views/DataSync/DataSync.vue -->
<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useRoute } from 'vue-router'
import type { BatchSyncRequest, DataTypeInfo, SyncResponse, SyncStatusResponse } from '@/api/data-sync'
import { dataSyncService } from '@/api/data-sync'

// 引入 Iconify 图标
import { Icon } from '@iconify/vue'

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
const statusPollingInterval = ref<NodeJS.Timeout | null>(null)
const dataTypesLoadFailed = ref(false)

// 同步状态和数据类型
const syncStatus = ref<SyncStatusResponse | null>(null)
const supportedDataTypes = ref<DataTypeInfo[]>([])

// 同步配置表单
const syncConfig = reactive({
  data_types: [] as string[],
  days: 30,
  start_date: '',
  end_date: '',
  stock_codes: [] as string[],
  exchange: '',
  batch_size: 100
})

// 计算属性
const estimatedRemainingTime = computed(() => {
  if (!syncStatus.value || !syncStatus.value.is_running) return 0
  const elapsed = syncStatus.value.elapsed_time || 0
  const progress = syncStatus.value.progress || 0
  if (progress <= 0) return 0
  return Math.round((elapsed / progress) * (100 - progress))
})

const statusColor = computed(() => {
  if (!syncStatus.value) return 'default'
  if (syncStatus.value.error) return 'error'
  if (syncStatus.value.is_running) return 'processing'
  if (syncStatus.value.progress === 100) return 'success'
  return 'default'
})

const statusText = computed(() => {
  if (!syncStatus.value) return '未知'
  if (syncStatus.value.error) return '错误'
  if (syncStatus.value.is_running) return '同步中'
  if (syncStatus.value.progress === 100) return '已完成'
  return '就绪'
})

// 方法
const initializePage = async () => {
  await Promise.all([
    checkSyncStatus(),
    fetchSupportedDataTypes()
  ])
}

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

const checkSyncStatus = async () => {
  isCheckingStatus.value = true
  try {
    const status = await dataSyncService.getSyncStatus()
    syncStatus.value = status

    if (status.is_running && !statusPollingInterval.value) {
      startStatusPolling()
    } else if (!status.is_running && statusPollingInterval.value) {
      stopStatusPolling()
    }
  } catch (error) {
    console.error('获取同步状态失败:', error)
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

const startStatusPolling = () => {
  if (statusPollingInterval.value) return
  statusPollingInterval.value = setInterval(async () => {
    try {
      const status = await dataSyncService.getSyncStatus()
      syncStatus.value = status
      if (!status.is_running) {
        stopStatusPolling()
        message.success('数据同步任务已完成')
      }
    } catch (error) {
      console.error('轮询同步状态失败:', error)
    }
  }, 2000)
}

const stopStatusPolling = () => {
  if (statusPollingInterval.value) {
    clearInterval(statusPollingInterval.value)
    statusPollingInterval.value = null
  }
}

const handleBatchSync = async () => {
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
    startStatusPolling()
  } catch (error: any) {
    console.error('同步任务启动失败:', error)
    message.error(error.response?.data?.detail || '同步任务启动失败')
  } finally {
    isLoading.value = false
  }
}

const handleQuickSync = () => {
  syncConfig.days = 30
  syncConfig.start_date = ''
  syncConfig.end_date = ''
  handleBatchSync()
}

const handleFullSync = () => {
  Modal.confirm({
    title: '确认全量同步',
    icon: () => h('div', {}, [
      h(Icon, { icon: 'ant-design:exclamation-circle-outlined' })
    ]),
    content: '全量同步将重新下载所有历史数据，耗时较长，可能会影响系统性能，确定继续吗？',
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      syncConfig.data_types = supportedDataTypes.value.map(type => type.code)
      syncConfig.days = 365
      syncConfig.start_date = ''
      syncConfig.end_date = ''
      await handleBatchSync()
    }
  })
}

const handleCancelSync = async () => {
  try {
    await dataSyncService.cancelSync()
    message.success('同步任务已取消')
    stopStatusPolling()
    await checkSyncStatus()
  } catch (error: any) {
    console.error('取消同步任务失败:', error)
    message.error(error.response?.data?.detail || '取消同步任务失败')
  }
}

const handleStockCodesInput = (value: string) => {
  if (!value.trim()) {
    syncConfig.stock_codes = []
    return
  }
  syncConfig.stock_codes = value.split(',')
    .map(code => code.trim())
    .filter(code => code.length > 0)
}

// 监听路由变化
watch(() => route.path, (newPath) => {
  if (newPath === '/data-sync') {
    initializePage()
  }
})

// 生命周期
onMounted(() => {
  initializePage()
})

onUnmounted(() => {
  stopStatusPolling()
})
</script>

<template>
  <div class="data-sync-page">
    <!-- 页面标题和状态 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据同步中心</h1>
          <p class="page-description">统一管理金融数据的同步任务和状态监控</p>
        </div>
        <div class="status-section">
          <a-tag :color="statusColor" class="status-tag">
            <Icon v-if="syncStatus?.is_running" icon="ant-design:sync-outlined" :spin="true" />
            <Icon v-else-if="syncStatus?.progress === 100" icon="ant-design:check-circle-outlined" />
            <Icon v-else-if="syncStatus?.error" icon="ant-design:exclamation-circle-outlined" />
            <Icon v-else icon="ant-design:info-circle-outlined" />
            {{ statusText }}
          </a-tag>
        </div>
      </div>
    </div>

    <!-- 状态概览 -->
    <a-row :gutter="[16, 16]" class="status-overview">
      <a-col :xs="12" :sm="6">
        <a-card class="status-card" size="small" :bordered="false">
          <div class="status-content">
            <div class="status-icon running">
              <Icon icon="ant-design:sync-outlined" />
            </div>
            <div class="status-info">
              <div class="status-value">{{ statusText }}</div>
              <div class="status-label">同步状态</div>
            </div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="12" :sm="6">
        <a-card class="status-card" size="small" :bordered="false">
          <div class="status-content">
            <div class="status-icon progress">
              <Icon icon="ant-design:cloud-download-outlined" />
            </div>
            <div class="status-info">
              <div class="status-value">{{ syncStatus?.progress || 0 }}%</div>
              <div class="status-label">任务进度</div>
            </div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="12" :sm="6">
        <a-card class="status-card" size="small" :bordered="false">
          <div class="status-content">
            <div class="status-icon time">
              <Icon icon="ant-design:clock-circle-outlined" />
            </div>
            <div class="status-info">
              <div class="status-value">{{ syncStatus?.elapsed_time || 0 }}s</div>
              <div class="status-label">运行时间</div>
            </div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="12" :sm="6">
        <a-card class="status-card" size="small" :bordered="false">
          <div class="status-content">
            <div class="status-icon remaining">
              <Icon icon="ant-design:hourglass-outlined" />
            </div>
            <div class="status-info">
              <div class="status-value">{{ estimatedRemainingTime }}s</div>
              <div class="status-label">预计剩余</div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <a-row :gutter="[24, 16]">
        <!-- 配置区域 -->
        <a-col :xs="24" :lg="16">
          <a-card title="数据同步配置" class="config-card">
            <template #extra>
              <a-button
                @click="checkSyncStatus"
                :loading="isCheckingStatus"
                size="small"
                class="refresh-btn"
              >
                <template #icon><Icon icon="ant-design:reload-outlined" /></template>
                刷新状态
              </a-button>
            </template>

            <!-- 数据类型选择 -->
            <div class="config-section">
              <h3 class="section-title">数据类型选择</h3>
              <div class="form-item-description">选择需要同步的数据类型（可多选）</div>

              <a-checkbox-group
                v-model:value="syncConfig.data_types"
                class="data-type-group"
              >
                <div class="data-type-grid">
                  <div
                    v-for="type in supportedDataTypes"
                    :key="type.code"
                    class="data-type-grid-item"
                  >
                    <div class="data-type-item-wrapper">
                      <a-checkbox
                        :value="type.code"
                        class="data-type-checkbox"
                      >
                        <div class="data-type-item">
                          <div class="type-name">{{ type.name }}</div>
                          <div class="type-meta">
                            <span class="type-time">{{ type.estimated_time }}s</span>
                          </div>
                        </div>
                      </a-checkbox>
                    </div>
                  </div>
                </div>
              </a-checkbox-group>
            </div>

            <!-- 同步参数 -->
            <div class="config-section">
              <h3 class="section-title">同步参数</h3>
              <a-row :gutter="16">
                <a-col :xs="24" :md="12">
                  <a-form-item label="同步天数" class="compact-form-item">
                    <a-input-number
                      v-model:value="syncConfig.days"
                      :min="1"
                      :max="365"
                      style="width: 100%"
                      placeholder="1-365天"
                    />
                  </a-form-item>

                  <a-form-item label="批量大小" class="compact-form-item">
                    <a-input-number
                      v-model:value="syncConfig.batch_size"
                      :min="1"
                      :max="500"
                      style="width: 100%"
                    />
                  </a-form-item>
                </a-col>

                <a-col :xs="24" :md="12">
                  <a-form-item label="交易所" class="compact-form-item">
                    <a-select v-model:value="syncConfig.exchange" placeholder="选择交易所">
                      <a-select-option value="SSE">上交所</a-select-option>
                      <a-select-option value="SZSE">深交所</a-select-option>
                      <a-select-option value="BSE">北交所</a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
              </a-row>
            </div>

            <!-- 高级选项 -->
            <a-collapse :bordered="false" class="advanced-section">
              <a-collapse-panel key="1" header="高级选项">
                <a-row :gutter="16">
                  <a-col :xs="24" :md="12">
                    <a-form-item label="时间范围" class="compact-form-item">
                      <div class="date-range">
                        <a-date-picker
                          v-model:value="syncConfig.start_date"
                          placeholder="开始日期"
                          style="width: 100%; margin-bottom: 8px;"
                          format="YYYY-MM-DD"
                        />
                        <a-date-picker
                          v-model:value="syncConfig.end_date"
                          placeholder="结束日期"
                          style="width: 100%"
                          format="YYYY-MM-DD"
                        />
                      </div>
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="股票代码" class="compact-form-item">
                      <a-textarea
                        :value="syncConfig.stock_codes.join(',')"
                        @input="(e: any) => handleStockCodesInput(e.target?.value || '')"
                        placeholder="例如：000001.SZ,600000.SH"
                        :rows="2"
                        show-count
                        :maxlength="500"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-collapse-panel>
            </a-collapse>
          </a-card>
        </a-col>

        <!-- 操作区域 -->
        <a-col :xs="24" :lg="8">
          <div class="action-area">
            <a-card title="同步操作" class="action-card">
              <div class="action-buttons">
                <a-button
                  type="primary"
                  @click="handleBatchSync"
                  :loading="isLoading"
                  :disabled="syncStatus?.is_running"
                  block
                  class="action-button primary"
                >
                  <template #icon><Icon icon="ant-design:cloud-download-outlined" /></template>
                  开始同步
                </a-button>

                <a-button
                  @click="handleQuickSync"
                  :loading="isLoading"
                  :disabled="syncStatus?.is_running"
                  block
                  class="action-button"
                >
                  <template #icon><Icon icon="ant-design:sync-outlined" /></template>
                  快速同步(30天)
                </a-button>

                <a-button
                  danger
                  @click="handleFullSync"
                  :loading="isLoading"
                  :disabled="syncStatus?.is_running"
                  block
                  class="action-button"
                >
                  <template #icon><Icon icon="ant-design:sync-outlined" /></template>
                  全量同步
                </a-button>

                <a-button
                  v-if="syncStatus?.is_running"
                  danger
                  @click="handleCancelSync"
                  :loading="isLoading"
                  block
                  class="action-button cancel"
                >
                  <template #icon><Icon icon="ant-design:pause-circle-outlined" /></template>
                  取消同步
                </a-button>
              </div>
            </a-card>

            <!-- 任务状态 -->
            <a-card
              v-if="syncStatus?.is_running || syncStatus?.results"
              title="任务状态"
              class="task-card"
              size="small"
            >
              <div class="task-content">
                <div v-if="syncStatus?.is_running" class="current-task">
                  <div class="task-info">
                    <div class="task-name">{{ syncStatus.current_task || '处理中...' }}</div>
                    <div class="task-progress">
                      <a-progress
                        :percent="syncStatus.progress"
                        size="small"
                        :show-info="false"
                      />
                    </div>
                    <div class="task-stats">
                      {{ syncStatus.completed_tasks }}/{{ syncStatus.total_tasks }} 任务完成
                    </div>
                  </div>
                </div>

                <div v-if="syncStatus?.results" class="task-results">
                  <div class="results-summary">
                    <span class="success-count">
                      {{ Object.values(syncStatus.results).filter(r => !r.error).length }} 成功
                    </span>
                    <span class="error-count">
                      {{ Object.values(syncStatus.results).filter(r => r.error).length }} 失败
                    </span>
                  </div>
                </div>
              </div>
            </a-card>

            <!-- 同步说明 -->
            <a-card title="同步说明" class="tips-card" size="small">
              <div class="tips-content">
                <p>• 数据同步任务将在后台执行</p>
                <p>• 系统会自动轮询状态更新</p>
                <p>• 单个数据类型失败不会影响其他类型</p>
                <p>• 建议在非交易时间段执行全量同步</p>
              </div>
            </a-card>
          </div>
        </a-col>
      </a-row>
    </div>

    <!-- 错误信息 -->
    <a-alert
      v-if="syncStatus?.error"
      :message="syncStatus.error"
      type="error"
      show-icon
      class="error-alert"
    />
  </div>
</template>

<style scoped lang="less">
// 使用全局 CSS 变量，完全由主题系统控制
.data-sync-page {
  padding: 0;
  max-width: 1400px;
  margin: 0 auto;
  background: var(--page-bg, var(--primary-bg));
  min-height: 100vh;
}

// 页面标题区域
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
    padding: 0 20px;
  }

  .title-section {
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

  .status-tag {
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: white;

    // 状态标签颜色映射 - 使用主题变量
    &.status-processing {
      background: rgba(var(--accent-color), 0.3);
    }

    &.status-success {
      background: rgba(var(--success-color), 0.3);
    }

    &.status-error {
      background: rgba(var(--danger-color), 0.3);
    }

    &.status-default {
      background: rgba(var(--text-secondary), 0.3);
    }
  }
}

// 状态概览
.status-overview {
  margin-bottom: 20px;
  padding: 0 20px;
}

.status-card {
  background: var(--card-bg);
  transition: all var(--transition-normal);

  &:hover {
    background: var(--status-card-hover, color-mix(in srgb, var(--accent-color) 10%, transparent));
    transform: var(--hover-transform);
  }

  .status-content {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .status-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;

    &.running {
      background: var(--status-running-bg, color-mix(in srgb, var(--accent-color) 10%, transparent));
      color: var(--status-running-color, var(--accent-color));
    }
    &.progress {
      background: var(--status-progress-bg, color-mix(in srgb, var(--success-color) 10%, transparent));
      color: var(--status-progress-color, var(--success-color));
    }
    &.time {
      background: var(--status-time-bg, color-mix(in srgb, var(--warning-color) 10%, transparent));
      color: var(--status-time-color, var(--warning-color));
    }
    &.remaining {
      background: var(--status-remaining-bg, color-mix(in srgb, var(--danger-color) 10%, transparent));
      color: var(--status-remaining-color, var(--danger-color));
    }
  }

  .status-info {
    .status-value {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      line-height: 1.2;
    }

    .status-label {
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 2px;
    }
  }
}

// 主要内容区域
.main-content {
  padding: 0 20px;
}

// 配置卡片
.config-card {
  border-radius: var(--border-radius-lg);
  box-shadow: var(--card-shadow, 0 2px 6px rgba(0, 0, 0, 0.06));
  border: 1px solid var(--border-color);
  background: var(--card-bg);

  :deep(.ant-card-head) {
    border-bottom: 1px solid var(--border-color);
    padding: 14px 20px;

    .ant-card-head-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }
}

.config-section {
  margin-bottom: 20px;

  .section-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 6px;
    color: var(--text-primary);
  }

  .form-item-description {
    font-size: 11px;
    color: var(--text-secondary);
    margin-bottom: 10px;
  }
}

// 刷新按钮
.refresh-btn {
  font-size: 12px;
  height: 28px;
  padding: 0 10px;
}

// 数据类型选择 - 网格布局
.data-type-group {
  width: 100%;
}

.data-type-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  width: 100%;

  @media (max-width: 1200px) {
    grid-template-columns: repeat(4, 1fr);
  }

  @media (max-width: 992px) {
    grid-template-columns: repeat(3, 1fr);
  }

  @media (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }

  @media (max-width: 576px) {
    grid-template-columns: 1fr;
  }
}

.data-type-grid-item {
  width: 100%;
}

.data-type-item-wrapper {
  margin-bottom: 0;
}

.data-type-checkbox {
  width: 100%;
  margin: 0;

  :deep(.ant-checkbox) {
    display: none;
  }

  :deep(.ant-checkbox-wrapper) {
    width: 100%;
    padding: 0;
    margin: 0;
    display: block;
  }

  :deep(.ant-checkbox-wrapper-checked) {
    .data-type-item {
      border-color: var(--data-type-selected-border, var(--accent-color)) !important;
      background: var(--data-type-selected-bg, color-mix(in srgb, var(--accent-color) 8%, transparent)) !important;
      box-shadow: var(--data-type-selected-shadow, 0 0 0 2px color-mix(in srgb, var(--accent-color) 20%, transparent)) !important;

      animation: dataTypeSelected 0.3s ease;

      .type-name {
        color: var(--accent-color);
        font-weight: 600;
      }

      .type-time {
        background: var(--accent-color);
        color: white;
      }
    }
  }
}

.data-type-item {
  border: 1.5px solid var(--border-color);
  background: var(--card-bg);
  padding: 16px 12px;
  border-radius: var(--border-radius);
  transition: all var(--transition-fast);
  cursor: pointer;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;

  &:hover {
    border-color: var(--accent-color);
    transform: translateY(-2px);
    box-shadow: var(--hover-shadow, 0 4px 12px rgba(0, 0, 0, 0.15));
  }

  .type-name {
    color: var(--text-primary);
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 8px;
    transition: color var(--transition-fast);
    text-align: center;
  }

  .type-meta {
    display: flex;
    justify-content: center;
  }

  .type-time {
    background: var(--secondary-bg);
    color: var(--text-secondary);
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 10px;
    transition: all var(--transition-fast);
  }
}

// 紧凑表单项
.compact-form-item {
  margin-bottom: 14px;

  :deep(.ant-form-item-label) {
    padding-bottom: 3px;

    label {
      font-size: 12px;
      color: var(--text-secondary);
      font-weight: 500;
    }
  }

  :deep(.ant-input-number),
  :deep(.ant-select) {
    height: 34px;

    .ant-input-number-input,
    .ant-select-selector {
      height: 34px;
      font-size: 13px;
    }
  }
}

// 高级选项
.advanced-section {
  background: none;

  :deep(.ant-collapse-header) {
    padding: 6px 0 !important;
    font-size: 13px;
    color: var(--accent-color);
  }

  :deep(.ant-collapse-content-box) {
    padding: 14px 0 0 0 !important;
  }
}

// 操作区域
.action-area {
  position: sticky;
  top: 20px;
}

.action-card {
  border-radius: var(--border-radius-lg);
  box-shadow: var(--card-shadow, 0 2px 6px rgba(0, 0, 0, 0.06));
  border: 1px solid var(--border-color);
  margin-bottom: 12px;
  background: var(--card-bg);

  :deep(.ant-card-head) {
    border-bottom: 1px solid var(--border-color);
    padding: 14px 16px;

    .ant-card-head-title {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;

  .action-button {
    transition: all var(--transition-normal);
    height: 40px;

    &.primary {
      background: var(--action-primary-bg, linear-gradient(135deg, var(--accent-color), color-mix(in srgb, var(--accent-color) 80%, black)));
      border: none;
      color: white;

      &:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: var(--primary-btn-hover-shadow, 0 6px 20px color-mix(in srgb, var(--accent-color) 40%, transparent));
      }
    }

    &.cancel {
      background: var(--cancel-btn-bg, color-mix(in srgb, var(--danger-color) 10%, transparent));
      border-color: var(--danger-color);
      color: var(--danger-color);

      &:hover:not(:disabled) {
        background: var(--danger-color);
        color: white;
        transform: translateY(-2px);
      }
    }

    &:not(.primary):not(.cancel) {
      background: var(--secondary-btn-bg, var(--secondary-bg));
      border-color: var(--border-color);
      color: var(--text-primary);

      &:hover:not(:disabled) {
        background: var(--hover-bg);
        border-color: var(--accent-color);
        transform: translateY(-2px);
      }
    }
  }
}

// 任务卡片
.task-card {
  border-radius: var(--border-radius-lg);
  box-shadow: var(--card-shadow, 0 2px 6px rgba(0, 0, 0, 0.06));
  border: 1px solid var(--border-color);
  margin-bottom: 12px;
  background: var(--card-bg);

  .task-content {
    .current-task {
      .task-info {
        .task-name {
          font-size: 13px;
          color: var(--text-primary);
          margin-bottom: 6px;
          font-weight: 500;
        }

        .task-progress {
          margin-bottom: 6px;

          :deep(.ant-progress-bg) {
            background: var(--accent-color);
          }

          :deep(.ant-progress-inner) {
            background: var(--secondary-bg);
          }
        }

        .task-stats {
          font-size: 11px;
          color: var(--text-secondary);
        }
      }
    }

    .task-results {
      .results-summary {
        display: flex;
        gap: 10px;
        font-size: 11px;

        .success-count {
          color: var(--success-color);
          font-weight: 500;
        }

        .error-count {
          color: var(--danger-color);
          font-weight: 500;
        }
      }
    }
  }
}

// 提示卡片
.tips-card {
  border-radius: var(--border-radius-lg);
  box-shadow: var(--card-shadow, 0 2px 6px rgba(0, 0, 0, 0.06));
  border: 1px solid var(--border-color);
  background: var(--card-bg);

  :deep(.ant-card-head) {
    border-bottom: 1px solid var(--border-color);
    padding: 12px 16px;

    .ant-card-head-title {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }

  .tips-content {
    p {
      margin: 4px 0;
      font-size: 12px;
      color: var(--text-secondary);
      line-height: 1.4;
    }
  }
}

// 错误提示
.error-alert {
  margin: 20px;
  border-radius: var(--border-radius);
  border: none;
  box-shadow: var(--card-shadow, 0 2px 6px rgba(0, 0, 0, 0.06));
}

// 选中状态动画
@keyframes dataTypeSelected {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.02);
  }
  100% {
    transform: scale(1);
  }
}

// 响应式设计
@media (max-width: 768px) {
  .page-header .header-content {
    flex-direction: column;
    gap: 12px;
    text-align: center;
  }

  .status-overview,
  .main-content {
    padding: 0 16px;
  }

  .data-type-grid {
    gap: 8px;
  }

  .data-type-item {
    padding: 12px 8px;
  }

  .action-button {
    height: 42px !important;
    font-size: 14px !important;
  }
}

// 主题特定调整
[data-theme="light"] {
  .data-sync-page {
    .status-card:hover {
      background: var(--status-card-hover-light, color-mix(in srgb, var(--accent-color) 5%, transparent));
    }

    .data-type-group .data-type-checkbox :deep(.ant-checkbox-wrapper-checked) .data-type-item {
      background: var(--data-type-selected-bg-light, color-mix(in srgb, var(--accent-color) 5%, transparent)) !important;
    }
  }
}

[data-theme="dark"] {
  .data-sync-page {
    .status-card:hover {
      background: var(--status-card-hover-dark, color-mix(in srgb, var(--accent-color) 8%, transparent));
    }

    .data-type-group .data-type-checkbox :deep(.ant-checkbox-wrapper-checked) .data-type-item {
      background: var(--data-type-selected-bg-dark, color-mix(in srgb, var(--accent-color) 15%, transparent)) !important;
    }
  }
}
</style>