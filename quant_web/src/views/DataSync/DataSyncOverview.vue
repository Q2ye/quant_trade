<!-- DataSyncOverview.vue -->
<template>
  <div class="data-sync-overview">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据同步概览</h1>
          <p class="page-description">统一管理数据同步任务，监控数据质量和同步状态</p>
        </div>
      </div>
    </div>

    <!-- 状态概览卡片 -->
    <div class="status-overview">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card class="status-card" shadow="hover">
            <div class="status-content">
              <div class="status-icon running">
                <Icon icon="ant-design:sync-outlined"/>
              </div>
              <div class="status-info">
                <div class="status-value">{{ statusText }}</div>
                <div class="status-label">同步状态</div>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="status-card" shadow="hover">
            <div class="status-content">
              <div class="status-icon progress">
                <Icon icon="ant-design:cloud-download-outlined"/>
              </div>
              <div class="status-info">
                <div class="status-value">{{ syncStatus?.progress || 0 }}%</div>
                <div class="status-label">任务进度</div>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="status-card" shadow="hover">
            <div class="status-content">
              <div class="status-icon time">
                <Icon icon="ant-design:clock-circle-outlined"/>
              </div>
              <div class="status-info">
                <div class="status-value">{{ syncStatus?.elapsed_time || 0 }}s</div>
                <div class="status-label">运行时间</div>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="status-card" shadow="hover">
            <div class="status-content">
              <div class="status-icon remaining">
                <Icon icon="ant-design:hourglass-outlined"/>
              </div>
              <div class="status-info">
                <div class="status-value">{{ estimatedRemainingTime }}s</div>
                <div class="status-label">预计剩余</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 核心功能导航卡片 - 四个主要卡片在同一行 -->
    <div class="core-function-nav">
      <el-row :gutter="16">
        <!-- 数据同步配置卡片 -->
        <el-col :span="6">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/data-sync')">
            <div class="function-content">
              <div class="function-icon accent">
                <Icon icon="ant-design:setting-outlined"/>
              </div>
              <div class="function-info">
                <h3>数据同步</h3>
                <p>自定义数据类型同步数据</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">支持类型:</span>
                    <span class="stat-value">{{ supportedTypesCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">已选类型:</span>
                    <span class="stat-value">{{ selectedTypesCount }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">批量大小: {{ syncConfig.batch_size }}</span>
                  <el-button type="primary" text size="small">配置同步</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 数据质量卡片 -->
        <el-col :span="6">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/data-quality')">
            <div class="function-content">
              <div class="function-icon danger">
                <Icon icon="ant-design:check-circle-outlined"/>
              </div>
              <div class="function-info">
                <h3>数据质量</h3>
                <p>数据完整性和质量检查</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">完整性:</span>
                    <span class="stat-value">{{ qualityStats.completeness }}%</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">及时性:</span>
                    <span class="stat-value">{{ qualityStats.timeliness }}%</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">准确性:</span>
                    <span class="stat-value">{{ qualityStats.accuracy }}%</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">检查时间: {{ qualityStats.checkTime }}</span>
                  <el-button type="primary" text size="small">质量报告</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 任务监控卡片 -->
        <el-col :span="6">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/data-sync/tasks')">
            <div class="function-content">
              <div class="function-icon purple">
                <Icon icon="ant-design:monitor-outlined"/>
              </div>
              <div class="function-info">
                <h3>任务监控</h3>
                <p>实时监控同步任务状态</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">运行中:</span>
                    <span class="stat-value">{{ monitorStats.running }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">已完成:</span>
                    <span class="stat-value">{{ monitorStats.completed }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">等待中:</span>
                    <span class="stat-value">{{ monitorStats.pending }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">更新: {{ monitorStats.updateTime }}</span>
                  <el-button type="primary" text size="small">实时监控</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 同步历史卡片 -->
        <el-col :span="6">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/data-sync/history')">
            <div class="function-content">
              <div class="function-icon info">
                <Icon icon="ant-design:history-outlined"/>
              </div>
              <div class="function-info">
                <h3>同步历史</h3>
                <p>查看历史同步任务记录</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">总任务数:</span>
                    <span class="stat-value">{{ historyStats.total }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">成功:</span>
                    <span class="stat-value success">{{ historyStats.completed }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">失败:</span>
                    <span class="stat-value danger">{{ historyStats.failed }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">最近同步: {{ historyStats.lastSync }}</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 实时任务状态 -->
    <div class="realtime-status">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-card class="status-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span class="card-title">当前任务进度</span>
                <el-button type="text" @click="checkSyncStatus">
                  刷新状态
                </el-button>
              </div>
            </template>
            <div class="progress-list">
              <div v-if="syncStatus?.is_running" class="progress-item">
                <div class="progress-info">
                  <div class="progress-name">批量数据同步</div>
                  <div class="progress-details">
                    {{ syncStatus.completed_tasks }}/{{ syncStatus.total_tasks }} 任务完成
                  </div>
                </div>
                <el-progress
                    :percentage="syncStatus.progress"
                    :status="syncStatus.error ? 'exception' : 'success'"
                />
                <div class="progress-time">
                  已运行: {{ syncStatus.elapsed_time }}s | 预计剩余: {{ estimatedRemainingTime }}s
                </div>
              </div>
              <div v-else class="no-task">
                <div class="no-task-icon">
                  <Icon icon="ant-design:check-circle-outlined"/>
                </div>
                <div class="no-task-text">暂无运行中的任务</div>
                <el-button type="primary" @click="navigateTo('/data-sync/config')">
                  开始新任务
                </el-button>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="status-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span class="card-title">最近同步记录</span>
                <el-button type="text" @click="navigateTo('/data-sync/history')">
                  查看全部
                </el-button>
              </div>
            </template>
            <div class="history-list">
              <div
                  v-for="record in recentHistory"
                  :key="record.id"
                  class="history-item"
              >
                <div class="history-info">
                  <div class="history-type">{{ record.data_types.join(', ') }}</div>
                  <div class="history-time">{{ formatTime(record.start_time) }}</div>
                </div>
                <div class="history-status">
                  <el-tag :type="getStatusTagType(record.status)" size="small">
                    {{ getStatusText(record.status) }}
                  </el-tag>
                </div>
              </div>
              <div v-if="recentHistory.length === 0" class="no-history">
                暂无同步记录
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import {computed, onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Icon} from '@iconify/vue'

const router = useRouter()

// 响应式数据
const syncStatus = ref({
  is_running: false,
  progress: 0,
  total_tasks: 0,
  completed_tasks: 0,
  elapsed_time: 0,
  error: null
})

const syncConfig = ref({
  data_types: [],
  days: 30,
  batch_size: 100
})

const supportedDataTypes = ref([
  {code: 'stock_basic', name: '股票列表'},
  {code: 'trade_calendar', name: '交易日历'},
  {code: 'daily', name: '日线行情'},
  {code: 'moneyflow', name: '资金流向'},
  {code: 'etf', name: 'ETF数据'}
])

const historyStats = ref({
  total: 156,
  completed: 142,
  failed: 8,
  lastSync: '2024-01-15 15:30'
})

const monitorStats = ref({
  running: 1,
  completed: 142,
  pending: 0,
  updateTime: '刚刚'
})

const qualityStats = ref({
  completeness: 98.5,
  timeliness: 99.2,
  accuracy: 99.8,
  checkTime: '2024-01-15 16:00'
})

const recentHistory = ref([
  {
    id: '1',
    data_types: ['日线行情', '资金流向'],
    status: 'completed',
    start_time: '2024-01-15T15:30:00Z'
  },
  {
    id: '2',
    data_types: ['股票列表', 'ETF数据'],
    status: 'completed',
    start_time: '2024-01-15T14:20:00Z'
  },
  {
    id: '3',
    data_types: ['全量同步'],
    status: 'failed',
    start_time: '2024-01-14T22:10:00Z'
  }
])

// 计算属性
const statusText = computed(() => {
  if (!syncStatus.value) return '未知'
  if (syncStatus.value.error) return '错误'
  if (syncStatus.value.is_running) return '同步中'
  if (syncStatus.value.progress === 100) return '已完成'
  return '就绪'
})

const estimatedRemainingTime = computed(() => {
  if (!syncStatus.value || !syncStatus.value.is_running) return 0
  const elapsed = syncStatus.value.elapsed_time || 0
  const progress = syncStatus.value.progress || 0
  if (progress <= 0) return 0
  return Math.round((elapsed / progress) * (100 - progress))
})

const supportedTypesCount = computed(() => supportedDataTypes.value.length)
const selectedTypesCount = computed(() => syncConfig.value.data_types.length)

// 方法
const navigateTo = (path) => {
  router.push(path)
}

const checkSyncStatus = async () => {
  try {
    // 模拟API调用
    const status = await new Promise(resolve => {
      setTimeout(() => {
        resolve({
          is_running: false,
          progress: 0,
          total_tasks: 0,
          completed_tasks: 0,
          elapsed_time: 0
        })
      }, 500)
    })
    syncStatus.value = status
  } catch (error) {
    console.error('获取同步状态失败:', error)
  }
}

const formatTime = (timeString) => {
  if (!timeString) return '--'
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN')
  } catch (error) {
    return timeString
  }
}

const getStatusText = (status) => {
  const texts = {
    completed: '完成',
    running: '运行中',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

const getStatusTagType = (status) => {
  const types = {
    completed: 'success',
    running: 'primary',
    failed: 'danger',
    cancelled: 'warning'
  }
  return types[status] || 'info'
}

// 生命周期
onMounted(() => {
  checkSyncStatus()
})
</script>

<style lang="scss" scoped>
.data-sync-overview {
  padding: var(--spacer-4);
  background: var(--primary-bg);
  min-height: 100%;

  .page-header {
    background: var(--page-header-bg, linear-gradient(135deg, var(--accent-color) 0%, color-mix(in srgb, var(--accent-color) 60%, #6f42c1) 100%));
    color: white;
    padding: 20px 0;
    margin-bottom: var(--spacer-4);

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
        color: rgba(255, 255, 255, 0.9);
      }
    }
  }

  .status-overview {
    margin-bottom: var(--spacer-4);

    .status-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);
      transition: all var(--transition-normal);

      &:hover {
        transform: var(--hover-transform);
        box-shadow: var(--hover-shadow);
      }

      .status-content {
        display: flex;
        align-items: center;
        padding: var(--spacer-3);

        .status-icon {
          width: 48px;
          height: 48px;
          border-radius: var(--border-radius);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
          margin-right: var(--spacer-3);

          &.running {
            background: color-mix(in srgb, var(--accent-color) 10%, transparent);
            color: var(--accent-color);
          }

          &.progress {
            background: color-mix(in srgb, var(--success-color) 10%, transparent);
            color: var(--success-color);
          }

          &.time {
            background: color-mix(in srgb, var(--warning-color) 10%, transparent);
            color: var(--warning-color);
          }

          &.remaining {
            background: color-mix(in srgb, var(--danger-color) 10%, transparent);
            color: var(--danger-color);
          }
        }

        .status-info {
          .status-value {
            font-size: 1.5rem;
            font-weight: var(--font-weight-bold);
            color: var(--text-primary);
            line-height: 1.2;
          }

          .status-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: var(--spacer-1);
          }
        }
      }
    }
  }

  .core-function-nav {
    margin-bottom: var(--spacer-4);

    .function-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);
      cursor: pointer;
      transition: all var(--transition-normal);
      height: 100%;

      &:hover {
        transform: translateY(-4px);
        box-shadow: var(--hover-shadow);
        border-color: var(--accent-color);
      }

      .function-content {
        display: flex;
        align-items: flex-start;
        padding: var(--spacer-3);

        .function-icon {
          font-size: 2.5rem;
          margin-right: var(--spacer-3);
          opacity: 0.8;
          flex-shrink: 0;

          &.accent {
            color: var(--accent-color);
          }
          &.danger {
            color: var(--danger-color);
          }
          &.purple {
            color: var(--purple-color);
          }
          &.info {
            color: var(--info-color);
          }
        }

        .function-info {
          flex: 1;

          h3 {
            margin: 0 0 var(--spacer-2) 0;
            color: var(--text-primary);
            font-size: 1.125rem;
            font-weight: var(--font-weight-semibold);
          }

          p {
            margin: 0 0 var(--spacer-3) 0;
            color: var(--text-secondary);
            font-size: calc(var(--font-size-base) - 2px);
            line-height: var(--line-height-base);
          }

          .function-stats {
            display: flex;
            flex-direction: column;
            gap: var(--spacer-2);
            margin-bottom: var(--spacer-3);

            .stat-item {
              display: flex;
              justify-content: space-between;
              align-items: center;

              .stat-label {
                font-size: calc(var(--font-size-base) - 2px);
                color: var(--text-secondary);
              }

              .stat-value {
                font-size: calc(var(--font-size-base) - 1px);
                font-weight: var(--font-weight-semibold);
                color: var(--text-primary);

                &.success {
                  color: var(--success-color);
                }

                &.danger {
                  color: var(--danger-color);
                }
              }
            }
          }

          .function-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: var(--spacer-2);
            border-top: 1px solid var(--border-color);

            .update-time {
              font-size: calc(var(--font-size-base) - 4px);
              color: var(--text-secondary);
            }
          }
        }
      }
    }
  }

  .realtime-status {
    margin-bottom: var(--spacer-4);

    .status-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);

      :deep(.el-card__header) {
        background: var(--secondary-bg);
        border-bottom: 1px solid var(--border-color);
        padding: var(--spacer-3);
      }

      :deep(.el-card__body) {
        padding: var(--spacer-3);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        .card-title {
          font-weight: var(--font-weight-semibold);
          color: var(--text-primary);
        }
      }

      .progress-list {
        .progress-item {
          .progress-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--spacer-2);

            .progress-name {
              font-weight: var(--font-weight-medium);
              color: var(--text-primary);
            }

            .progress-details {
              font-size: 0.875rem;
              color: var(--text-secondary);
            }
          }

          .progress-time {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: var(--spacer-2);
            text-align: center;
          }
        }

        .no-task {
          text-align: center;
          padding: var(--spacer-4) 0;

          .no-task-icon {
            font-size: 3rem;
            color: var(--success-color);
            margin-bottom: var(--spacer-2);
          }

          .no-task-text {
            color: var(--text-secondary);
            margin-bottom: var(--spacer-3);
          }
        }
      }

      .history-list {
        .history-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--spacer-2) 0;
          border-bottom: 1px solid var(--border-color);

          &:last-child {
            border-bottom: none;
          }

          .history-info {
            .history-type {
              font-weight: var(--font-weight-medium);
              color: var(--text-primary);
              margin-bottom: 2px;
            }

            .history-time {
              font-size: 0.75rem;
              color: var(--text-secondary);
            }
          }
        }

        .no-history {
          text-align: center;
          color: var(--text-secondary);
          padding: var(--spacer-4) 0;
        }
      }
    }
  }
}

// 响应式设计
@media (max-width: 1200px) {
  .core-function-nav .el-col {
    width: 50%;
  }
}

@media (max-width: 768px) {
  .data-sync-overview {
    padding: var(--spacer-2);
  }

  .core-function-nav .el-col {
    width: 100%;
  }

  .function-card .function-content {
    flex-direction: column;
    text-align: center;

    .function-icon {
      margin-right: 0;
      margin-bottom: var(--spacer-2);
    }
  }

  .realtime-status .el-col {
    width: 100%;
    margin-bottom: var(--spacer-3);
  }
}
</style>