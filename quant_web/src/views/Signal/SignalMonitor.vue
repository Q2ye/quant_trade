<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElTable, ElTag, ElButton } from 'element-plus'
import type { TradingSignal as Signal } from '@/types/entities/trading'
import type { TagProps } from 'element-plus'

// 实时信号数据
const signals = ref<Signal[]>([])
const wsConnection = ref<WebSocket | null>(null)
const isConnecting = ref(false)
const reconnectAttempts = ref(0)
const maxReconnectAttempts = 5
// 明确指定类型为 number
const reconnectTimer = ref<number | null>(null)

// WebSocket状态常量，用于模板中访问
const WS_OPEN = WebSocket.OPEN
const WS_CONNECTING = WebSocket.CONNECTING
const WS_CLOSING = WebSocket.CLOSING
const WS_CLOSED = WebSocket.CLOSED

// 信号类型配置 - 添加默认值处理
const signalTypeMap: Record<string, { color: TagProps['type']; text: string }> = {
  buy: { color: 'success', text: '买入' },
  sell: { color: 'danger', text: '卖出' },
  hold: { color: 'info', text: '持有' },
  // 添加默认值
  default: { color: 'warning', text: '未知' }
}

// 安全的信号类型获取函数
const getSignalTypeInfo = (signalType: string) => {
  return signalTypeMap[signalType] || signalTypeMap.default
}

// 计算今日信号数量
const todaySignalsCount = computed(() => {
  const today = new Date().toDateString()
  return signals.value.filter(s => new Date(s.signal_time).toDateString() === today).length
})

// 获取正确的 WebSocket URL - 使用8000端口
const getWebSocketUrl = (): string => {
  // 开发环境使用8080端口
  if (import.meta.env.VITE_APP_ENV === 'development') {
    return `ws://localhost:8000/api/ws/signals`
  }

  // 生产环境使用当前主机和协议
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/signals`
}

// 清理 WebSocket 连接
const cleanupWebSocket = () => {
  if (wsConnection.value) {
    wsConnection.value.onopen = null
    wsConnection.value.onmessage = null
    wsConnection.value.onerror = null
    wsConnection.value.onclose = null
    if (wsConnection.value.readyState === WebSocket.OPEN) {
      wsConnection.value.close(1000, '正常关闭')
    }
    wsConnection.value = null
  }

  if (reconnectTimer.value) {
    clearTimeout(reconnectTimer.value)
    reconnectTimer.value = null
  }

  isConnecting.value = false
}

// 连接WebSocket接收实时信号
const connectWebSocket = () => {
  if (isConnecting.value) {
    return // 防止重复连接
  }

  try {
    cleanupWebSocket() // 清理之前的连接

    const wsUrl = getWebSocketUrl()
    console.log('Connecting to WebSocket:', wsUrl)

    isConnecting.value = true
    wsConnection.value = new WebSocket(wsUrl)

    wsConnection.value.onopen = () => {
      console.log('WebSocket连接成功')
      isConnecting.value = false
      reconnectAttempts.value = 0 // 重置重连计数
      ElMessage.success('实时信号连接已建立')
    }

    wsConnection.value.onmessage = (event) => {
      try {
        const signalData = JSON.parse(event.data)

        // 验证数据格式
        if (!signalData.signal_type || !signalData.ts_code) {
          console.warn('Invalid signal data:', signalData)
          return
        }

        const newSignal = {
          ...signalData,
          id: Date.now() + Math.random(),
          timestamp: new Date(),
          // 确保必要字段有默认值
          signal_time: signalData.signal_time || new Date().toISOString(),
          strength: signalData.strength || 0,
          current_price: signalData.current_price || 0
        }

        signals.value.unshift(newSignal)

        // 保持最近100条信号
        if (signals.value.length > 100) {
          signals.value = signals.value.slice(0, 100)
        }

        // 桌面通知
        if (Notification.permission === 'granted' && signalData.symbol) {
          new Notification('交易信号', {
            body: `${signalData.symbol} ${getSignalTypeInfo(signalData.signal_type).text}信号`
          })
        }
      } catch (parseError) {
        console.error('解析信号数据失败:', parseError, event.data)
      }
    }

    wsConnection.value.onerror = (error) => {
      console.error('WebSocket错误:', error)
      isConnecting.value = false

      // 只在首次错误时显示消息，避免重复提示
      if (reconnectAttempts.value === 0) {
        ElMessage.error('信号连接失败，正在重连...')
      }
    }

    wsConnection.value.onclose = (event) => {
      console.log('WebSocket连接关闭:', event.code, event.reason)
      isConnecting.value = false

      // 只在非正常关闭且未超过最大重连次数时重连
      if (event.code !== 1000 && reconnectAttempts.value < maxReconnectAttempts) {
        reconnectAttempts.value++
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.value), 30000) // 指数退避，最大30秒
        console.log(`将在 ${delay}ms 后尝试第 ${reconnectAttempts.value} 次重连`)

        // 使用 Number() 显式转换为 number 类型
        reconnectTimer.value = Number(setTimeout(() => {
          connectWebSocket()
        }, delay))
      } else if (reconnectAttempts.value >= maxReconnectAttempts) {
        ElMessage.warning('信号连接失败，请检查服务器状态')
      }
    }

  } catch (error) {
    console.error('WebSocket连接失败:', error)
    isConnecting.value = false
    ElMessage.error('WebSocket连接失败')
  }
}

// 手动重连函数
const manualReconnect = () => {
  reconnectAttempts.value = 0
  connectWebSocket()
}

// 快速交易操作
const handleQuickTrade = (signal: Signal) => {
  // 跳转到交易页面并预填信息
  const symbol = signal.ts_code || signal.symbol || 'unknown'
  window.open(`/trading?symbol=${encodeURIComponent(symbol)}&action=${signal.signal_type}`, '_blank')
}

// 请求通知权限
const requestNotificationPermission = async () => {
  if ('Notification' in window && Notification.permission === 'default') {
    try {
      await Notification.requestPermission()
    } catch (error) {
      console.warn('通知权限请求失败:', error)
    }
  }
}

onMounted(() => {
  requestNotificationPermission()
  connectWebSocket()
})

onUnmounted(() => {
  cleanupWebSocket()
})
</script>

<template>
  <div class="signal-monitor">
    <div class="monitor-header">
      <h3>实时信号监控</h3>
      <div class="header-controls">
        <div class="stats">
          <span>今日信号: {{ todaySignalsCount }}</span>
          <span>活跃策略: 12</span>
          <span>连接状态:
            <el-tag
              :type="wsConnection?.readyState === WS_OPEN ? 'success' : 'danger'"
              size="small"
            >
              {{ wsConnection?.readyState === WS_OPEN ? '已连接' : '未连接' }}
            </el-tag>
          </span>
        </div>
        <el-button
          v-if="wsConnection?.readyState !== WS_OPEN"
          @click="manualReconnect"
          size="small"
          :loading="isConnecting"
        >
          重新连接
        </el-button>
      </div>
    </div>

    <el-table
      :data="signals"
      height="600"
      style="width: 100%"
      :row-class-name="(rowInfo) => `signal-row-${rowInfo.row.signal_type}`"
      v-if="signals.length > 0"
    >
      <!-- 表格列保持不变 -->
      <el-table-column prop="signal_time" label="信号时间" width="180">
        <template #default="{ row }">
          {{ new Date(row.signal_time).toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="strategy_id" label="策略" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.strategy_id || '--' }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="ts_code" label="标的" width="100">
        <template #default="{ row }">
          <strong>{{ row.ts_code || row.symbol || '--' }}</strong>
        </template>
      </el-table-column>

      <el-table-column prop="signal_type" label="信号类型" width="100">
        <template #default="{ row }">
          <el-tag
            :type="getSignalTypeInfo(row.signal_type).color"
            effect="dark"
          >
            {{ getSignalTypeInfo(row.signal_type).text }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="current_price" label="触发价格" width="100">
        <template #default="{ row }">
          ¥{{ row.current_price?.toFixed(2) || '--' }}
        </template>
      </el-table-column>

      <el-table-column prop="strength" label="信号强度" width="120">
        <template #default="{ row }">
          <el-progress
            :percentage="Math.round((row.strength || 0) * 100)"
            :show-text="false"
            :color="row.strength > 0.7 ? '#67c23a' : row.strength > 0.4 ? '#e6a23c' : '#f56c6c'"
          />
          <span style="margin-left: 8px">{{ Math.round((row.strength || 0) * 100) }}%</span>
        </template>
      </el-table-column>

      <el-table-column prop="reason" label="信号原因" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.reason || '--' }}
        </template>
      </el-table-column>

      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            :type="row.signal_type === 'buy' ? 'success' : 'danger'"
            @click="handleQuickTrade(row)"
          >
            {{ row.signal_type === 'buy' ? '快速买入' : row.signal_type === 'sell' ? '快速卖出' : '执行操作' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-else class="empty-state">
      <p v-if="wsConnection?.readyState === WS_OPEN">等待接收实时信号...</p>
      <p v-else>连接已断开，无法接收实时信号</p>
      <p class="hint">WebSocket URL: {{ getWebSocketUrl() }}</p>
      <el-button @click="manualReconnect" :loading="isConnecting">
        重新连接
      </el-button>
    </div>
  </div>
</template>

<!-- 样式保持不变 -->
<style scoped>
.signal-monitor {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stats {
  display: flex;
  gap: 20px;
  color: #606266;
  font-size: 14px;
  align-items: center;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
}

.hint {
  font-size: 12px;
  margin-top: 8px;
  color: #c0c4cc;
  margin-bottom: 16px;
}

:deep(.signal-row-buy) {
  background-color: #f0f9ff;
}

:deep(.signal-row-sell) {
  background-color: #fef0f0;
}

:deep(.signal-row-hold) {
  background-color: #f4f4f5;
}

:deep(.signal-row-default) {
  background-color: #fdf6ec;
}
</style>