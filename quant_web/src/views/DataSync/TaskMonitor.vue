<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Card, List, Progress, Tag, Button, Space } from 'ant-design-vue'
import { PlayCircleOutlined, PauseCircleOutlined, CloseCircleOutlined } from '@ant-design/icons-vue'

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

const tasks = ref<SyncTask[]>([])
const loading = ref(false)
let refreshInterval: number | undefined

const loadTasks = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/data-sync/tasks')
    tasks.value = await response.json()
  } catch (error) {
    console.error('加载任务失败:', error)
  } finally {
    loading.value = false
  }
}

const handleControlTask = async (taskId: string, action: 'pause' | 'resume' | 'stop') => {
  try {
    await fetch(`/api/data-sync/tasks/${taskId}/${action}`, { method: 'POST' })
    await loadTasks()
  } catch (error) {
    console.error('操作失败:', error)
  }
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    running: 'blue',
    paused: 'orange',
    completed: 'green',
    failed: 'red'
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
  refreshInterval = window.setInterval(loadTasks, 5000) // 5秒刷新一次
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="task-monitor-page">
    <a-card title="同步任务监控">
      <template #extra>
        <a-button @click="loadTasks">刷新</a-button>
      </template>

      <a-list
        :data-source="tasks"
        :loading="loading"
        item-layout="vertical"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <template #actions>
              <span>开始时间: {{ item.startTime }}</span>
              <span>已运行: {{ item.elapsedTime }}</span>
              <span>当前步骤: {{ item.currentStep }}</span>
            </template>

            <template #extra>
              <a-space>
                <a-button
                  v-if="item.status === 'running'"
                  @click="handleControlTask(item.id, 'pause')"
                >
                  <template #icon><PauseCircleOutlined /></template>
                  暂停
                </a-button>
                <a-button
                  v-if="item.status === 'paused'"
                  @click="handleControlTask(item.id, 'resume')"
                >
                  <template #icon><PlayCircleOutlined /></template>
                  继续
                </a-button>
                <a-button
                  danger
                  @click="handleControlTask(item.id, 'stop')"
                >
                  <template #icon><CloseCircleOutlined /></template>
                  停止
                </a-button>
              </a-space>
            </template>

            <a-list-item-meta>
              <template #title>
                <a-space>
                  <span>{{ item.dataCategory }} - {{ item.taskType }}</span>
                  <a-tag :color="getStatusColor(item.status)">
                    {{ getStatusText(item.status) }}
                  </a-tag>
                </a-space>
              </template>
              <template #description>
                {{ item.details }}
              </template>
            </a-list-item-meta>

            <a-progress
              :percent="item.progress"
              :status="item.status === 'failed' ? 'exception' : 'normal'"
              style="max-width: 400px"
            />
          </a-list-item>
        </template>
      </a-list>
    </a-card>
  </div>
</template>

<style scoped>
.task-monitor-page {
  padding: 24px;
}
</style>