<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'debug'
  module: string
  message: string
  details?: any
}

const props = defineProps<{
  logs: LogEntry[]
}>()

const logContainer = ref<HTMLElement>()
const autoScroll = ref(true)

const levelMap = {
  info: { color: '#409EFF', icon: '🔵' },
  warning: { color: '#E6A23C', icon: '🟡' },
  error: { color: '#F56C6C', icon: '🔴' },
  debug: { color: '#909399', icon: '⚫' }
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleTimeString()
}

const scrollToBottom = () => {
  if (logContainer.value && autoScroll.value) {
    nextTick(() => {
      logContainer.value!.scrollTop = logContainer.value!.scrollHeight
    })
  }
}

onMounted(() => {
  scrollToBottom()
})

defineExpose({
  scrollToBottom
})
</script>

<template>
  <div class="system-logs">
    <div class="logs-controls">
      <div class="auto-scroll">
        <input
          id="auto-scroll"
          type="checkbox"
          v-model="autoScroll"
        >
        <label for="auto-scroll">自动滚动</label>
      </div>
      <div class="log-count">
        共 {{ logs.length }} 条日志
      </div>
    </div>

    <div class="logs-container" ref="logContainer">
      <div
        v-for="(log, index) in logs"
        :key="index"
        class="log-entry"
        :class="`level-${log.level}`"
      >
        <div class="log-time">{{ formatTime(log.timestamp) }}</div>
        <div class="log-level" :style="{ color: levelMap[log.level].color }">
          {{ levelMap[log.level].icon }} {{ log.level.toUpperCase() }}
        </div>
        <div class="log-module">[{{ log.module }}]</div>
        <div class="log-message">{{ log.message }}</div>
        <div v-if="log.details" class="log-details">
          {{ JSON.stringify(log.details) }}
        </div>
      </div>

      <div v-if="logs.length === 0" class="empty-logs">
        暂无日志记录
      </div>
    </div>
  </div>
</template>

<style scoped>
.system-logs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.logs-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #e8e8e8;
  margin-bottom: 8px;
}

.auto-scroll {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.auto-scroll input {
  margin: 0;
}

.log-count {
  font-size: 12px;
  color: #666;
}

.logs-container {
  flex: 1;
  overflow-y: auto;
  max-height: 300px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
}

.log-entry {
  display: flex;
  padding: 4px 0;
  border-bottom: 1px solid #f5f5f5;
  gap: 8px;
  align-items: flex-start;
}

.log-entry:last-child {
  border-bottom: none;
}

.log-entry.level-error {
  background-color: #fef0f0;
}

.log-entry.level-warning {
  background-color: #fdf6ec;
}

.log-time {
  color: #999;
  min-width: 80px;
  flex-shrink: 0;
}

.log-level {
  font-weight: 500;
  min-width: 50px;
  flex-shrink: 0;
}

.log-module {
  color: #409EFF;
  min-width: 80px;
  flex-shrink: 0;
}

.log-message {
  flex: 1;
  color: #333;
  word-break: break-all;
}

.log-details {
  color: #666;
  font-size: 11px;
  margin-top: 2px;
  flex-basis: 100%;
}

.empty-logs {
  text-align: center;
  color: #999;
  padding: 20px;
}
</style>