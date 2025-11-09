<!-- quant_web/src/views/DataSync/DataSync.vue -->
<script setup lang="ts">
import {computed, h, onMounted, onUnmounted, reactive, ref, watch} from 'vue'
import {message, Modal} from 'ant-design-vue'
import {useRoute, useRouter} from 'vue-router'
import type {BatchSyncRequest, DataTypeInfo, SyncResponse, SyncStatusResponse} from '@/api/data-sync'
import {dataSyncService} from '@/api/data-sync'
import {ArrowLeftOutlined} from '@ant-design/icons-vue'

// 引入 Iconify 图标
import {Icon} from '@iconify/vue'

// 完整的数据类型选项 - 作为降级数据
const fallbackDataTypes = [
  {code: 'stock_basic', name: '股票列表', description: '股票基础信息', estimated_time: 30},
  {code: 'trade_calendar', name: '交易日历', description: '交易所交易日历', estimated_time: 5},
  {code: 'daily', name: '日线行情', description: 'A股日线行情数据', estimated_time: 120},
  {code: 'weekly', name: '周线行情', description: '周线行情数据', estimated_time: 60},
  {code: 'monthly', name: '月线行情', description: '月线行情数据', estimated_time: 45},
  {code: 'moneyflow', name: '资金流向', description: '资金流向数据', estimated_time: 75},
  {code: 'etf', name: 'ETF数据', description: 'ETF基础信息和行情', estimated_time: 40},
  {code: 'adj_factor', name: '复权因子', description: '股票复权因子', estimated_time: 25},
  {code: 'daily_basic', name: '每日指标', description: '每日基本面指标', estimated_time: 50},
  {code: 'daily_limit', name: '涨跌停价格', description: '每日涨跌停价格', estimated_time: 20},
  {code: 'st_list', name: 'ST股票列表', description: 'ST股票历史记录', estimated_time: 15},
  {code: 'company', name: '公司信息', description: '上市公司基本信息', estimated_time: 35},
  {code: 'managers', name: '管理层信息', description: '公司管理层信息', estimated_time: 25}
]

// 路由实例
const route = useRoute()
const router = useRouter()

// 添加返回按钮处理函数
const handleBack = () => {
  router.go(-1)
}

// 响应式数据
const isLoading = ref(false)
const isQuickLoading = ref(false)
const isFullLoading = ref(false)
const isCheckingStatus = ref(false)
const statusPollingInterval = ref<NodeJS.Timeout | null>(null)
const dataTypesLoadFailed = ref(false)
const errorShown = ref(false) // 新增：防止重复显示错误

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
    // 这里不显示警告，因为可能是服务器连接问题
  }
}

const checkSyncStatus = async () => {
  isCheckingStatus.value = true
  try {
    const status = await dataSyncService.getSyncStatus()
    syncStatus.value = status
    errorShown.value = false // 重置错误显示状态

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

    // 只在第一次失败时显示错误
    if (!errorShown.value) {
      showConnectionError()
      errorShown.value = true
    }
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
      errorShown.value = false // 重置错误显示状态

      if (!status.is_running) {
        stopStatusPolling()
        message.success('数据同步任务已完成')
      }
    } catch (error) {
      console.error('轮询同步状态失败:', error)
      // 轮询失败时不重复显示错误
      stopStatusPolling()
    }
  }, 2000)
}

const stopStatusPolling = () => {
  if (statusPollingInterval.value) {
    clearInterval(statusPollingInterval.value)
    statusPollingInterval.value = null
  }
}

// 新增：统一的连接错误显示
const showConnectionError = () => {
  message.error({
    content: '无法连接到服务器，请检查：1. 后端服务是否启动 2. 代理配置是否正确',
    duration: 5, // 显示5秒
    key: 'connection-error' // 使用相同的key防止重复
  })
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
    errorShown.value = false // 重置错误显示状态

    // 根据响应状态决定是否启动轮询
    if (response.status === 'started') {
      startStatusPolling()
    }
  } catch (error: any) {
    console.error('同步任务启动失败:', error)

    // 只在第一次失败时显示连接错误
    if (!errorShown.value) {
      showConnectionError()
      errorShown.value = true
    }

    // 更新状态显示错误信息
    updateLocalStatus({
      is_running: false,
      error: '连接服务器失败'
    })
  } finally {
    isLoading.value = false
  }
}

const handleQuickSync = async () => {
  if (syncStatus.value?.is_running) {
    message.warning('已有同步任务正在进行中')
    return
  }

  isQuickLoading.value = true
  try {
    const response: SyncResponse = await dataSyncService.quickSyncData()
    message.success(response.message)
    errorShown.value = false // 重置错误显示状态
    startStatusPolling()
  } catch (error: any) {
    console.error('快速同步启动失败:', error)

    // 只在第一次失败时显示连接错误
    if (!errorShown.value) {
      showConnectionError()
      errorShown.value = true
    }

    // 更新状态显示错误信息
    updateLocalStatus({
      is_running: false,
      error: '连接服务器失败'
    })
  } finally {
    isQuickLoading.value = false
  }
}

const handleFullSync = async () => {
  if (syncStatus.value?.is_running) {
    message.warning('已有同步任务正在进行中')
    return
  }

  Modal.confirm({
    title: '确认全量同步',
    icon: () => h('div', {}, [
      h(Icon, {icon: 'ant-design:exclamation-circle-outlined'})
    ]),
    content: h('div', {}, [
      h('p', '全量同步将重新下载所有历史数据，耗时较长，可能会影响系统性能。'),
      h('p', {style: {marginTop: '8px', fontWeight: 'bold'}}, '确定继续吗？')
    ]),
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      isFullLoading.value = true
      try {
        const requestData = {
          days: 365,
          start_date: syncConfig.start_date || undefined,
          end_date: syncConfig.end_date || undefined,
          stock_codes: syncConfig.stock_codes.length ? syncConfig.stock_codes : undefined,
          exchange: syncConfig.exchange || undefined,
          batch_size: syncConfig.batch_size
        }
        const response: SyncResponse = await dataSyncService.fullSyncData(requestData)
        message.success(response.message)
        errorShown.value = false // 重置错误显示状态
        startStatusPolling()
      } catch (error: any) {
        console.error('全量同步启动失败:', error)

        // 只在第一次失败时显示连接错误
        if (!errorShown.value) {
          showConnectionError()
          errorShown.value = true
        }

        // 更新状态显示错误信息
        updateLocalStatus({
          is_running: false,
          error: '连接服务器失败'
        })
      } finally {
        isFullLoading.value = false
      }
    },
    onCancel: () => {
      // 用户取消操作，不需要处理
    }
  })
}

const handleCancelSync = async () => {
  Modal.confirm({
    title: '确认取消同步',
    icon: () => h('div', {}, [
      h(Icon, {icon: 'ant-design:exclamation-circle-outlined'})
    ]),
    content: '取消同步将中断当前正在执行的任务，已同步的数据将保留。确定要取消吗？',
    okText: '确认取消',
    cancelText: '继续同步',
    okType: 'danger',
    onOk: async () => {
      try {
        await dataSyncService.cancelSync()
        message.success('同步任务已取消')
        stopStatusPolling()
        await checkSyncStatus()
      } catch (error: any) {
        console.error('取消同步任务失败:', error)
        // 取消操作失败时也检查是否已显示过错误
        if (!errorShown.value) {
          message.error(error.response?.data?.detail || '取消同步任务失败')
          errorShown.value = true
        }
      }
    }
  })
}

// 更新本地状态（避免重复请求）
const updateLocalStatus = (updates: Partial<SyncStatusResponse>) => {
  if (!syncStatus.value) return

  syncStatus.value = {
    ...syncStatus.value,
    ...updates
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

// 新增：切换数据类型选中状态
const toggleDataType = (code: string) => {
  const index = syncConfig.data_types.indexOf(code)
  if (index > -1) {
    syncConfig.data_types.splice(index, 1)
  } else {
    syncConfig.data_types.push(code)
  }
}

// 新增：判断数据类型是否选中
const isDataTypeSelected = (code: string) => {
  return syncConfig.data_types.includes(code)
}

// 新增：选择所有数据类型
const selectAllDataTypes = () => {
  syncConfig.data_types = supportedDataTypes.value.map(type => type.code)
}

// 新增：清空数据类型选择
const clearAllDataTypes = () => {
  syncConfig.data_types = []
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
          <h1 class="page-title">同步中心</h1>
          <p class="page-description">统一管理金融数据的同步任务和状态监控</p>
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

    <!-- 状态概览 -->
    <a-row :gutter="[16, 16]" class="status-overview">
      <a-col :xs="12" :sm="6">
        <a-card class="status-card" size="small" :bordered="false">
          <div class="status-content">
            <div class="status-icon running">
              <Icon icon="ant-design:sync-outlined"/>
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
              <Icon icon="ant-design:cloud-download-outlined"/>
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
              <Icon icon="ant-design:clock-circle-outlined"/>
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
              <Icon icon="ant-design:hourglass-outlined"/>
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
              <div class="header-actions">
                <a-button
                    type="link"
                    size="small"
                    @click="selectAllDataTypes"
                    class="action-link"
                >
                  全选
                </a-button>
                <a-button
                    type="link"
                    size="small"
                    @click="clearAllDataTypes"
                    class="action-link"
                >
                  清空
                </a-button>
                <a-button
                    @click="checkSyncStatus"
                    :loading="isCheckingStatus"
                    size="small"
                    class="refresh-btn"
                >
                  <template #icon>
                    <Icon icon="ant-design:reload-outlined"/>
                  </template>
                  刷新状态
                </a-button>
              </div>
            </template>

            <!-- 数据类型选择 -->
            <div class="config-section">
              <h3 class="section-title">数据类型选择</h3>
              <div class="form-item-description">
                点击选择需要同步的数据类型（已选择 {{ syncConfig.data_types.length }} 种类型）
              </div>

              <div class="data-type-group">
                <div class="data-type-grid">
                  <div
                      v-for="type in supportedDataTypes"
                      :key="type.code"
                      class="data-type-grid-item"
                      @click="toggleDataType(type.code)"
                  >
                    <div
                        class="data-type-item"
                        :class="{ 'selected': isDataTypeSelected(type.code) }"
                    >
                      <div class="type-name">{{ type.name }}</div>
                      <div class="type-meta">
                        <span class="type-time">{{ type.estimated_time }}s</span>
                      </div>
                      <div class="type-indicator">
                        <Icon
                            v-if="isDataTypeSelected(type.code)"
                            icon="ant-design:check-circle-filled"
                            class="check-icon"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
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
                    :disabled="syncStatus?.is_running || !syncConfig.data_types.length"
                    block
                    class="action-button primary"
                >
                  <template #icon>
                    <Icon icon="ant-design:cloud-download-outlined"/>
                  </template>
                  开始同步
                </a-button>

                <a-button
                    @click="handleQuickSync"
                    :loading="isQuickLoading"
                    :disabled="syncStatus?.is_running"
                    block
                    class="action-button"
                >
                  <template #icon>
                    <Icon icon="ant-design:rocket-outlined"/>
                  </template>
                  快速同步
                </a-button>

                <a-button
                    danger
                    @click="handleFullSync"
                    :loading="isFullLoading"
                    :disabled="syncStatus?.is_running"
                    block
                    class="action-button"
                >
                  <template #icon>
                    <Icon icon="ant-design:database-outlined"/>
                  </template>
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
                  <template #icon>
                    <Icon icon="ant-design:pause-circle-outlined"/>
                  </template>
                  取消同步
                </a-button>
              </div>
            </a-card>

            <!-- 同步说明 -->
            <a-card title="同步说明" class="tips-card" size="small">
              <div class="tips-content">
                <p><strong>批量同步：</strong>自定义选择数据类型和参数，智能选择同步/异步模式</p>
                <p><strong>快速同步：</strong>同步核心数据类型（股票列表、交易日历、日线行情、每日指标），30天数据</p>
                <p><strong>全量同步：</strong>同步所有数据类型，365天历史数据</p>
                <p>• 数据同步任务将在后台执行</p>
                <p>• 系统会自动轮询状态更新</p>
                <p>• 单个数据类型失败不会影响其他类型</p>
                <p>• 建议在非交易时间段执行全量同步</p>
                <p class="cancel-tip">
                  <Icon icon="ant-design:info-circle-outlined" style="color: #faad14; margin-right: 4px;"/>
                  <strong>取消说明：</strong>点击"取消同步"可中断当前任务，已同步的数据将保留
                </p>
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

<style scoped lang="scss">
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color' as sassColor;

.data-sync-page {
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

.status-overview {
  margin-bottom: map.get($spacers, 4);
  padding: 0 map.get($spacers, 4);
}

.status-card {
  @include mixin.status-card-base;
}

.main-content {
  padding: 0 map.get($spacers, 4);
}

.config-card {
  @include mixin.card-base;
  border-radius: $border-radius-lg;

  :deep(.ant-card-head) {
    border-bottom: 1px solid $border-color;
    padding: map.get($spacers, 3) map.get($spacers, 4);

    .ant-card-head-title {
      font-size: $font-size-base * 1.1;
      font-weight: $font-weight-semibold;
      color: $text-primary;
    }
  }
}

.config-section {
  margin-bottom: map.get($spacers, 4);

  .section-title {
    font-size: $font-size-base;
    font-weight: $font-weight-semibold;
    margin-bottom: map.get($spacers, 1);
    color: $text-primary;
  }

  .form-item-description {
    @include mixin.text-secondary;
    margin-bottom: map.get($spacers, 2);
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: map.get($spacers, 2);

  .action-link {
    font-size: $font-size-base * 0.85;
    height: auto;
    padding: 0;
    color: $accent-color;
  }
}

.refresh-btn {
  @include mixin.button-base;
  font-size: $font-size-base * 0.85;
  height: $button-height * 0.8;
  padding: 0 map.get($spacers, 2);
}

.data-type-group {
  width: 100%;
}

.data-type-grid {
  @include mixin.flexible-grid(5, (
    'xl': 4,
    'lg': 3,
    'md': 2,
    'sm': 1
  ), map.get($spacers, 3));
}

.data-type-grid-item {
  width: 100%;
}

.data-type-item {
  @include mixin.card-base(false);
  padding: map.get($spacers, 3) map.get($spacers, 2);
  cursor: pointer;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;

  &:hover {
    border-color: $accent-color;
    transform: $hover-transform;
    box-shadow: $card-hover-shadow;
  }

  &.selected {
    border-color: $accent-color;
    background: sassColor.adjust($accent-color, $lightness: 96%);
    box-shadow: 0 0 0 2px sassColor.adjust($accent-color, $lightness: 80%);

    animation: dataTypeSelected 0.3s ease;

    .type-name {
      color: $accent-color;
      font-weight: $font-weight-semibold;
    }

    .type-time {
      background: $accent-color;
      color: white;
    }

    .check-icon {
      opacity: 1;
      transform: scale(1);
    }
  }

  .type-name {
    color: $text-primary;
    font-size: $font-size-base * 0.9;
    font-weight: $font-weight-medium;
    margin-bottom: map.get($spacers, 2);
    transition: color $transition-fast;
    text-align: center;
  }

  .type-meta {
    display: flex;
    justify-content: center;
  }

  .type-time {
    background: $secondary-bg;
    color: $text-secondary;
    font-size: $font-size-base * 0.8;
    padding: map.get($spacers, 1) map.get($spacers, 2);
    border-radius: 10px;
    transition: all $transition-fast;
  }

  .type-indicator {
    position: absolute;
    top: map.get($spacers, 2);
    right: map.get($spacers, 2);
  }

  .check-icon {
    color: $accent-color;
    font-size: $font-size-base;
    opacity: 0;
    transform: scale(0.8);
    transition: all $transition-fast;
  }
}

.compact-form-item {
  margin-bottom: map.get($spacers, 3);

  :deep(.ant-form-item-label) {
    padding-bottom: map.get($spacers, 1);

    label {
      font-size: $font-size-base * 0.85;
      color: $text-secondary;
      font-weight: $font-weight-medium;
    }
  }

  :deep(.ant-input-number),
  :deep(.ant-select) {
    height: $button-height;

    .ant-input-number-input,
    .ant-select-selector {
      height: $button-height;
      font-size: $font-size-base * 0.9;
    }
  }
}

.advanced-section {
  background: none;

  :deep(.ant-collapse-header) {
    padding: map.get($spacers, 1) 0 !important;
    font-size: $font-size-base * 0.9;
    color: $accent-color;
  }

  :deep(.ant-collapse-content-box) {
    padding: map.get($spacers, 3) 0 0 0 !important;
  }
}

.action-area {
  position: sticky;
  top: map.get($spacers, 4);
}

.action-card {
  @include mixin.card-base;
  border-radius: $border-radius-lg;
  margin-bottom: map.get($spacers, 3);

  :deep(.ant-card-head) {
    border-bottom: 1px solid $border-color;
    padding: map.get($spacers, 3) map.get($spacers, 3);

    .ant-card-head-title {
      font-size: $font-size-base;
      font-weight: $font-weight-semibold;
      color: $text-primary;
    }
  }
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: map.get($spacers, 2);

  .action-button {
    @include mixin.button-base;
    height: $button-height * 1.2;
    transition: all $transition-normal;

    &.primary {
      background: linear-gradient(135deg, $accent-color, sassColor.adjust($accent-color, $lightness: -20%));
      border: none;
      color: white;

      &:hover:not(:disabled) {
        transform: $hover-transform;
        box-shadow: 0 6px 20px sassColor.adjust($accent-color, $alpha: -0.6);
      }
    }

    &.cancel {
      background: sassColor.adjust($danger-color, $lightness: 40%);
      border-color: $danger-color;
      color: $danger-color;

      &:hover:not(:disabled) {
        background: $danger-color;
        color: white;
        transform: $hover-transform;
      }
    }

    &:not(.primary):not(.cancel) {
      background: $secondary-bg;
      border-color: $border-color;
      color: $text-primary;

      &:hover:not(:disabled) {
        background: $hover-bg;
        border-color: $accent-color;
        transform: $hover-transform;
      }
    }
  }
}

.tips-card {
  @include mixin.card-base;
  border-radius: $border-radius-lg;

  :deep(.ant-card-head) {
    border-bottom: 1px solid $border-color;
    padding: map.get($spacers, 2) map.get($spacers, 3);

    .ant-card-head-title {
      font-size: $font-size-base * 0.9;
      font-weight: $font-weight-semibold;
      color: $text-primary;
    }
  }

  .tips-content {
    p {
      margin: map.get($spacers, 1) 0;
      font-size: $font-size-base * 0.85;
      @include mixin.text-secondary;
      line-height: 1.4;
    }

    .cancel-tip {
      margin-top: map.get($spacers, 2);
      padding: map.get($spacers, 2);
      background: sassColor.adjust($warning-color, $lightness: 45%);
      border: 1px solid $warning-color;
      border-radius: $border-radius;
      color: $warning-color;
      font-size: $font-size-base * 0.8;
    }
  }
}

.error-alert {
  margin: map.get($spacers, 4);
  border-radius: $border-radius;
  border: none;
  box-shadow: $card-shadow;
}

@keyframes dataTypeSelected {
  0% { transform: scale(1); }
  50% { transform: scale(1.02); }
  100% { transform: scale(1); }
}

// 响应式设计
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
}
</style>