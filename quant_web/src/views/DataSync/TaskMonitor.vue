<script setup lang="ts">
import {onMounted, onUnmounted, ref} from 'vue'
import {Button, Card, List, Progress, Space, Tag} from 'ant-design-vue'
import {ArrowLeftOutlined, CloseCircleOutlined, PauseCircleOutlined, PlayCircleOutlined} from '@ant-design/icons-vue'
import {useRouter} from 'vue-router'

// 引入 Iconify 图标
import {Icon} from '@iconify/vue'

const router = useRouter() // 添加路由实例

interface SyncTask {
  id: string
  taskType: string
  dataCategory: string
  progress: number
  status: 'running' | 'paused' | 'completed' | 'failed'
  startTime: string
  elapsedTime: string
  currentStep: string
  details: string
}

// 添加返回按钮处理函数
const handleBack = () => {
  router.go(-1)
}

const tasks = ref<SyncTask[]>([])
const loading = ref(false)
let refreshInterval: number | undefined

const loadTasks = async () => {
  loading.value = true
  try {
    // 直接赋值，移除冗余的 mockData 变量
    tasks.value = [
      {
        id: '1',
        taskType: '数据同步',
        dataCategory: '市场数据',
        progress: 75,
        status: 'running',
        startTime: '2024-01-15 10:00:00',
        elapsedTime: '15分钟',
        currentStep: '处理K线数据',
        details: '同步沪深300指数数据'
      }
    ]
  } catch (error) {
    console.error('加载任务失败:', error)
  } finally {
    loading.value = false
  }
}

// 添加缺失的函数
const handleControlTask = async (taskId: string, action: 'pause' | 'resume' | 'stop') => {
  try {
    console.log(`执行操作: ${action} 任务: ${taskId}`)
    await loadTasks()
  } catch (error) {
    console.error('操作失败:', error)
  }
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    running: 'var(--accent-color)',
    paused: 'var(--warning-color)',
    completed: 'var(--success-color)',
    failed: 'var(--danger-color)'
  }
  return colors[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    running: '运行中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status] || status
}

onMounted(() => {
  loadTasks()
  refreshInterval = window.setInterval(loadTasks, 5000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="task-monitor-page">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步任务监控</h1>
          <p class="page-description">实时监控数据同步任务执行状态和进度</p>
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

    <Card class="monitor-card">
      <div class="card-content">
        <List
            :data-source="tasks"
            :loading="loading"
            item-layout="vertical"
            class="task-list"
        >
          <template #renderItem="{ item }">
            <List.Item class="task-item">
              <template #actions>
                <span class="task-meta">开始时间: {{ item.startTime }}</span>
                <span class="task-meta">已运行: {{ item.elapsedTime }}</span>
                <span class="task-meta">当前步骤: {{ item.currentStep }}</span>
              </template>

              <template #extra>
                <Space class="task-actions">
                  <Button
                      v-if="item.status === 'running'"
                      @click="handleControlTask(item.id, 'pause')"
                      class="control-btn pause-btn"
                  >
                    <template #icon>
                      <PauseCircleOutlined/>
                    </template>
                    暂停
                  </Button>
                  <Button
                      v-if="item.status === 'paused'"
                      @click="handleControlTask(item.id, 'resume')"
                      class="control-btn resume-btn"
                  >
                    <template #icon>
                      <PlayCircleOutlined/>
                    </template>
                    继续
                  </Button>
                  <Button
                      danger
                      @click="handleControlTask(item.id, 'stop')"
                      class="control-btn stop-btn"
                  >
                    <template #icon>
                      <CloseCircleOutlined/>
                    </template>
                    停止
                  </Button>
                </Space>
              </template>

              <!-- 修复 List.Item.Meta 的使用 -->
              <List.Item.Meta>
                <template #title>
                  <Space class="task-title">
                    <span>{{ item.dataCategory }} - {{ item.taskType }}</span>
                    <Tag :color="getStatusColor(item.status)" class="status-tag">
                      {{ getStatusText(item.status) }}
                    </Tag>
                  </Space>
                </template>
                <template #description>
                  <div class="task-description">{{ item.details }}</div>
                </template>
              </List.Item.Meta>

              <Progress
                  :percent="item.progress"
                  :status="item.status === 'failed' ? 'exception' : 'normal'"
                  class="task-progress"
                  :stroke-color="item.status === 'failed' ? 'var(--danger-color)' : 'var(--accent-color)'"
              />
            </List.Item>
          </template>

          <template #empty>
            <div class="empty-state">
              <div class="empty-icon">📊</div>
              <div class="empty-text">暂无同步任务</div>
              <Button @click="loadTasks" class="empty-btn">刷新</Button>
            </div>
          </template>
        </List>
      </div>
    </Card>
  </div>
</template>

<style scoped lang="scss">
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
    padding: 0 var(--spacer-4);
    position: relative;

    .header-actions-right {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
  }

  .title-section {
    flex: 1;

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
    font-size: 12px;
  }
}

// 优化返回按钮样式
.back-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  border-radius: var(--border-radius, 6px);
  font-weight: 500;
  transition: all var(--transition-fast, 0.3s);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  height: 32px;
  display: flex;
  align-items: center;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:active {
    transform: translateY(0);
  }
}

.task-monitor-page {
  padding: 0;
  max-width: 1400px;
  margin: 0 auto;
  background: var(--primary-bg);
  min-height: 100vh;
}

.monitor-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  margin: 0 20px;

  .card-content {
    padding: var(--spacer-3);
  }
}

.task-list {
  :deep(.ant-list-item) {
    background: var(--secondary-bg);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    margin-bottom: var(--spacer-2);
    padding: var(--spacer-3);
    transition: all var(--transition-normal);

    &:hover {
      background: var(--hover-bg);
      transform: translateY(-1px);
      box-shadow: var(--hover-shadow);
    }

    .ant-list-item-meta {
      align-items: flex-start;
    }

    .ant-list-item-action {
      margin-top: var(--spacer-2);
      margin-left: 0;
    }
  }
}

.task-item {
  :deep(.ant-list-item-meta-title) {
    color: var(--text-primary);
    font-weight: 600;
    margin-bottom: var(--spacer-1);
  }

  :deep(.ant-list-item-meta-description) {
    color: var(--text-secondary);
  }
}

.task-meta {
  color: var(--text-secondary);
  font-size: 0.875rem;

  &:not(:last-child) {
    margin-right: var(--spacer-3);
  }
}

.task-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacer-2);
}

.status-tag {
  border: none;
  color: white;
  font-weight: 500;
  font-size: 0.75rem;
}

.task-description {
  color: var(--text-secondary);
  line-height: 1.5;
}

.task-progress {
  margin-top: var(--spacer-2);

  :deep(.ant-progress-text) {
    color: var(--text-primary);
    font-weight: 500;
  }
}

.task-actions {
  @media (max-width: 576px) {
    flex-direction: column;
    width: 100%;

    .control-btn {
      width: 100%;
      justify-content: center;
    }
  }
}

.control-btn {
  padding: 8px 16px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all var(--transition-fast);

  &.pause-btn {
    background-color: var(--warning-color);
    border-color: var(--warning-color);
    color: white;

    &:hover {
      background-color: var(--warning-color-dark, rgba(250, 173, 20, 0.8));
      border-color: var(--warning-color-dark, rgba(250, 173, 20, 0.8));
    }
  }

  &.resume-btn {
    background-color: var(--success-color);
    border-color: var(--success-color);
    color: white;

    &:hover {
      background-color: var(--success-color-dark, rgba(82, 196, 26, 0.8));
      border-color: var(--success-color-dark, rgba(82, 196, 26, 0.8));
    }
  }

  &.stop-btn {
    background-color: var(--danger-color);
    border-color: var(--danger-color);
    color: white;

    &:hover {
      background-color: var(--danger-color-dark, rgba(255, 77, 79, 0.8));
      border-color: var(--danger-color-dark, rgba(255, 77, 79, 0.8));
    }
  }
}

.empty-state {
  text-align: center;
  padding: var(--spacer-5) var(--spacer-3);
  color: var(--text-secondary);

  .empty-icon {
    font-size: 3rem;
    margin-bottom: var(--spacer-3);
  }

  .empty-text {
    font-size: 1rem;
    margin-bottom: var(--spacer-3);
    color: var(--text-secondary);
  }

  .empty-btn {
    padding: 8px 16px;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all var(--transition-fast);
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;

    &:hover {
      background-color: var(--accent-color-dark, rgba(24, 144, 255, 0.8));
      border-color: var(--accent-color-dark, rgba(24, 144, 255, 0.8));
    }
  }
}

// 响应式调整
@media (max-width: 768px) {
  .page-header .header-content {
    flex-direction: column;
    gap: 12px;
    text-align: center;

    .header-actions-left {
      position: static;
      align-self: flex-start;
    }
  }

  .monitor-card {
    margin: 0 16px;
  }

  .task-item {
    padding: var(--spacer-2);

    :deep(.ant-list-item-extra) {
      margin-left: 0;
      margin-top: var(--spacer-2);
    }
  }

  .task-actions {
    flex-direction: column;
    gap: var(--spacer-1);

    .control-btn {
      width: 100%;
      justify-content: center;
    }
  }
}

@media (max-width: 576px) {
  .monitor-card {
    margin: 0 var(--spacer-2);
  }

  .task-item {
    :deep(.ant-list-item-action) {
      display: flex;
      flex-direction: column;
      gap: var(--spacer-1);

      li {
        margin-bottom: 0;

        .task-meta {
          display: block;
          margin-right: 0;
          margin-bottom: var(--spacer-1);
        }
      }
    }
  }
}

// 动画效果
@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
  100% {
    opacity: 1;
  }
}

.task-item:has(.status-tag[color='var(--accent-color)']) {
  .status-tag {
    animation: pulse 2s infinite;
  }
}
</style>