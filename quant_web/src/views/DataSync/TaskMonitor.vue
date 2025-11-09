<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Button, Card, List, Progress, Space, Tag } from 'ant-design-vue'
import { ArrowLeftOutlined, CloseCircleOutlined, PauseCircleOutlined, PlayCircleOutlined } from '@ant-design/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()

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

const handleBack = () => {
  router.go(-1)
}

const tasks = ref<SyncTask[]>([])
const loading = ref(false)
let refreshInterval: number | undefined

const loadTasks = async () => {
  loading.value = true
  try {
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
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步任务监控</h1>
          <p class="page-description">实时监控数据同步任务执行状态和进度</p>
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
                      <PauseCircleOutlined />
                    </template>
                    暂停
                  </Button>
                  <Button
                    v-if="item.status === 'paused'"
                    @click="handleControlTask(item.id, 'resume')"
                    class="control-btn resume-btn"
                  >
                    <template #icon>
                      <PlayCircleOutlined />
                    </template>
                    继续
                  </Button>
                  <Button
                    danger
                    @click="handleControlTask(item.id, 'stop')"
                    class="control-btn stop-btn"
                  >
                    <template #icon>
                      <CloseCircleOutlined />
                    </template>
                    停止
                  </Button>
                </Space>
              </template>
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
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';

.task-monitor-page {
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

.monitor-card {
  @include mixin.card-base;
  margin: 0 map.get($spacers, 4);

  .card-content {
    padding: map.get($spacers, 3);
  }
}

.task-list {
  :deep(.ant-list-item) {
    @include mixin.card-base;
    margin-bottom: map.get($spacers, 2);
    padding: map.get($spacers, 3);
    transition: all $transition-normal;

    &:hover {
      background: $hover-bg;
      transform: $hover-transform;
      box-shadow: $card-hover-shadow;
    }

    .ant-list-item-meta {
      align-items: flex-start;
    }

    .ant-list-item-action {
      margin-top: map.get($spacers, 2);
      margin-left: 0;
    }
  }
}

.task-item {
  :deep(.ant-list-item-meta-title) {
    color: $text-primary;
    font-weight: $font-weight-semibold;
    margin-bottom: map.get($spacers, 1);
  }

  :deep(.ant-list-item-meta-description) {
    color: $text-secondary;
  }
}

.task-meta {
  @include mixin.text-secondary;

  &:not(:last-child) {
    margin-right: map.get($spacers, 3);
  }
}

.task-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: map.get($spacers, 2);
}

.status-tag {
  border: none;
  color: white;
  font-weight: $font-weight-medium;
  font-size: 0.75rem;
}

.task-description {
  @include mixin.text-secondary;
  line-height: 1.5;
}

.task-progress {
  margin-top: map.get($spacers, 2);

  :deep(.ant-progress-text) {
    color: $text-primary;
    font-weight: $font-weight-medium;
  }
}

.task-actions {
  @include mixin.media-breakpoint-down(sm) {
    flex-direction: column;
    width: 100%;

    .control-btn {
      width: 100%;
      justify-content: center;
    }
  }
}

.control-btn {
  @include mixin.button-base;
  padding: map.get($spacers, 2) map.get($spacers, 3);
  border-radius: $border-radius;
  display: flex;
  align-items: center;
  gap: map.get($spacers, 1);

  &.pause-btn {
    background-color: $warning-color;
    border-color: $warning-color;
    color: white;
  }

  &.resume-btn {
    background-color: $success-color;
    border-color: $success-color;
    color: white;
  }

  &.stop-btn {
    background-color: $danger-color;
    border-color: $danger-color;
    color: white;
  }
}

.empty-state {
  @include mixin.flex-center(column);
  padding: map.get($spacers, 5) map.get($spacers, 3);
  color: $text-secondary;

  .empty-icon {
    font-size: 3rem;
    margin-bottom: map.get($spacers, 3);
  }

  .empty-text {
    font-size: 1rem;
    margin-bottom: map.get($spacers, 3);
    color: $text-secondary;
  }

  .empty-btn {
    @include mixin.button-base;
  }
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

  .monitor-card {
    margin: 0 map.get($spacers, 3);
  }

  .task-item {
    padding: map.get($spacers, 2);

    :deep(.ant-list-item-extra) {
      margin-left: 0;
      margin-top: map.get($spacers, 2);
    }
  }

  .task-actions {
    flex-direction: column;
    gap: map.get($spacers, 1);

    .control-btn {
      width: 100%;
      justify-content: center;
    }
  }
}

@include mixin.media-breakpoint-down(sm) {
  .monitor-card {
    margin: 0 map.get($spacers, 2);
  }

  .task-item {
    :deep(.ant-list-item-action) {
      display: flex;
      flex-direction: column;
      gap: map.get($spacers, 1);

      li {
        margin-bottom: 0;

        .task-meta {
          display: block;
          margin-right: 0;
          margin-bottom: map.get($spacers, 1);
        }
      }
    }
  }
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.7; }
  100% { opacity: 1; }
}

.task-item:has(.status-tag[color='$accent-color']) {
  .status-tag {
    animation: pulse 2s infinite;
  }
}
</style>