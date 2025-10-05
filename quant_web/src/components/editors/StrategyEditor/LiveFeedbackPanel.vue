<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'debug'
  message: string
  source: string
}

const logs = ref<LogEntry[]>([])
const autoScroll = ref(true)
const { subscribe, unsubscribe } = useWebSocket()

const logContainer = ref<HTMLDivElement>()

// 添加日志条目
const addLog = (entry: LogEntry) => {
  logs.value.push(entry)

  // 限制日志数量
  if (logs.value.length > 1000) {
    logs.value = logs.value.slice(-500)
  }

  // 自动滚动到底部
  if (autoScroll.value) {
    nextTick(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    })
  }
}

// 清空日志
const clearLogs = () => {
  logs.value = []
}

// 导出日志
const exportLogs = () => {
  const content = logs.value.map(log =>
    `[${log.timestamp}] [${log.level.toUpperCase()}] [${log.source}] ${log.message}`
  ).join('\n')

  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `strategy-logs-${new Date().toISOString().slice(0, 10)}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// 过滤日志级别
const filterLevel = ref<'all' | 'info' | 'warning' | 'error'>('all')
const filteredLogs = computed(() => {
  if (filterLevel.value === 'all') return logs.value
  return logs.value.filter(log => log.level === filterLevel.value)
})

// 获取日志级别样式
const getLevelStyle = (level: string) => {
  switch (level) {
    case 'error': return { color: '#f56c6c', background: '#fef0f0' }
    case 'warning': return { color: '#e6a23c', background: '#fdf6ec' }
    case 'info': return { color: '#409eff', background: '#f0f9ff' }
    case 'debug': return { color: '#909399', background: '#f4f4f5' }
    default: return { color: '#606266', background: '#f4f4f5' }
  }
}

onMounted(() => {
  // 订阅策略日志
  subscribe('strategy_logs', (data: LogEntry) => {
    addLog(data)
  })

  // 订阅回测日志
  subscribe('backtest_logs', (data: LogEntry) => {
    addLog(data)
  })
})

onUnmounted(() => {
  unsubscribe('strategy_logs')
  unsubscribe('backtest_logs')
})
</script>

<template>
  <div class="live-feedback-panel">
    <div class="panel-header">
      <h3>实时日志</h3>
      <div class="header-controls">
        <el-select v-model="filterLevel" size="small" style="width: 100px;">
          <el-option label="全部" value="all" />
          <el-option label="信息" value="info" />
          <el-option label="警告" value="warning" />
          <el-option label="错误" value="error" />
        </el-select>

        <el-switch
          v-model="autoScroll"
          active-text="自动滚动"
          size="small"
        />

        <el-button size="small" @click="clearLogs">清空</el-button>
        <el-button size="small" @click="exportLogs">导出</el-button>
      </div>
    </div>

    <div ref="logContainer" class="log-container">
      <div
        v-for="log in filteredLogs"
        :key="log.id"
        class="log-entry"
        :style="getLevelStyle(log.level)"
      >
        <span class="timestamp">{{ new Date(log.timestamp).toLocaleTimeString() }}</span>
        <span class="level-badge" :class="log.level">{{ log.level.toUpperCase() }}</span>
        <span class="source">[{{ log.source }}]</span>
        <span class="message">{{ log.message }}</span>
      </div>

      <div v-if="filteredLogs.length === 0" class="empty-logs">
        暂无日志信息
      </div>
    </div>

    <div class="panel-footer">
      <span class="log-count">共 {{ logs.length }} 条日志</span>
      <span class="filter-count" v-if="filterLevel !== 'all'">
        (过滤后: {{ filteredLogs.length }} 条)
      </span>
    </div>
  </div>
</template>

<style scoped>
.live-feedback-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color);
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
}

.log-entry {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  margin-bottom: 2px;
  border-radius: 3px;
  border-left: 3px solid;
}

.timestamp {
  color: var(--el-text-color-secondary);
  margin-right: 8px;
  min-width: 80px;
}

.level-badge {
  padding: 1px 4px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: bold;
  margin-right: 8px;
  min-width: 40px;
  text-align: center;
}

.level-badge.error { background: #f56c6c; color: white; }
.level-badge.warning { background: #e6a23c; color: white; }
.level-badge.info { background: #409eff; color: white; }
.level-badge.debug { background: #909399; color: white; }

.source {
  color: var(--el-text-color-secondary);
  margin-right: 8px;
  min-width: 80px;
}

.message {
  flex: 1;
  word-break: break-all;
}

.empty-logs {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 40px;
}

.panel-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--el-border-color);
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.log-count {
  margin-right: 8px;
}
</style>