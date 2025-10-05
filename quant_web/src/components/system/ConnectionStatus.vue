<script setup lang="ts">
import { ElTag, ElTooltip } from 'element-plus'
import type { ComponentSize } from 'element-plus'

interface Connection {
  name: string
  type: 'data' | 'trade' | 'websocket' | 'database'
  status: 'connected' | 'disconnected' | 'error' | 'connecting'
  lastCheck: string
  latency?: number
}

// 定义 props 接口
interface Props {
  connections?: Connection[]
}

// 使用 defineProps 并指定类型，设置默认值
const props = withDefaults(defineProps<Props>(), {
  connections: () => []
})

// 使用 Element Plus 合法的 Tag 类型
import type { TagProps } from 'element-plus'
type TagType = TagProps['type']

// 修复状态映射，添加默认值处理
const statusMap: Record<string, { type: TagType; text: string }> = {
  connected: { type: 'success', text: '已连接' },
  disconnected: { type: 'info', text: '未连接' },
  error: { type: 'danger', text: '错误' },
  connecting: { type: 'warning', text: '连接中' },
  // 添加默认状态处理
  default: { type: 'info', text: '未知状态' }
}

// 安全的获取状态信息函数
const getStatusInfo = (status: string) => {
  return statusMap[status] || statusMap.default
}

const typeMap: Record<string, string> = {
  data: '数据源',
  trade: '交易接口',
  websocket: 'WebSocket',
  database: '数据库',
  // 添加默认类型处理
  default: '未知类型'
}

// 安全的获取类型名称函数
const getTypeName = (type: string) => {
  return typeMap[type] || typeMap.default
}

// 安全的格式化时间函数
const formatTime = (time: string) => {
  try {
    return new Date(time).toLocaleTimeString()
  } catch (error) {
    console.warn('时间格式化错误:', error)
    return '无效时间'
  }
}

// 计算属性：确保 connections 是响应式数组
import { computed } from 'vue'
const safeConnections = computed(() => {
  if (!props.connections || !Array.isArray(props.connections)) {
    return []
  }
  return props.connections.filter(conn => conn && typeof conn === 'object')
})
</script>

<template>
  <div class="connection-status">
    <div
      v-for="(conn, index) in safeConnections"
      :key="conn.name || `conn-${index}`"
      class="connection-item"
    >
      <div class="connection-info">
        <span class="connection-name">{{ getTypeName(conn.type) }} - {{ conn.name || '未知连接' }}</span>
        <div class="connection-details">
          <span class="last-check">最后检查: {{ formatTime(conn.lastCheck) }}</span>
          <span v-if="conn.latency !== undefined && conn.latency !== null" class="latency">
            延迟: {{ conn.latency }}ms
          </span>
        </div>
      </div>
      <ElTooltip :content="getStatusInfo(conn.status).text">
        <ElTag :type="getStatusInfo(conn.status).type">
          {{ getStatusInfo(conn.status).text }}
        </ElTag>
      </ElTooltip>
    </div>

    <div v-if="safeConnections.length === 0" class="empty-state">
      暂无连接信息
    </div>
  </div>
</template>

<style scoped>
.connection-status {
  max-height: 300px;
  overflow-y: auto;
}

.connection-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.connection-item:last-child {
  border-bottom: none;
}

.connection-info {
  flex: 1;
}

.connection-name {
  font-weight: 500;
  display: block;
  margin-bottom: 4px;
}

.connection-details {
  font-size: 12px;
  color: #666;
}

.last-check, .latency {
  margin-right: 12px;
}

.empty-state {
  text-align: center;
  color: #999;
  padding: 20px;
}

/* 修复选择器使用问题 */
:deep(.el-tag) {
  min-width: 60px;
  text-align: center;
}
</style>