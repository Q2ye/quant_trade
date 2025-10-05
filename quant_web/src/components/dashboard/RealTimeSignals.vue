<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

interface Signal {
  id: string
  strategy: string
  symbol: string
  name: string
  signal: 'BUY' | 'SELL' | 'HOLD'
  price: number
  time: string
  strength: number
}

const signals = ref<Signal[]>([])
const { subscribe, unsubscribe } = useWebSocket()

onMounted(() => {
  subscribe('strategy_signals', (data: Signal) => {
    signals.value.unshift(data)
    if (signals.value.length > 50) {
      signals.value = signals.value.slice(0, 50)
    }
  })
})

onUnmounted(() => {
  unsubscribe('strategy_signals')
})

const getSignalColor = (signal: string) => {
  switch (signal) {
    case 'BUY': return '#f56c6c'
    case 'SELL': return '#67c23a'
    default: return '#909399'
  }
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleTimeString()
}
</script>

<template>
  <div class="real-time-signals">
    <div class="header">
      <h3>实时信号流</h3>
      <span class="count">{{ signals.length }}</span>
    </div>

    <div class="signals-list">
      <div
        v-for="signal in signals"
        :key="signal.id"
        class="signal-item"
      >
        <div class="signal-header">
          <span class="strategy">{{ signal.strategy }}</span>
          <span class="time">{{ formatTime(signal.time) }}</span>
        </div>

        <div class="signal-content">
          <div class="symbol-info">
            <span class="symbol">{{ signal.symbol }}</span>
            <span class="name">{{ signal.name }}</span>
          </div>

          <div class="signal-action" :style="{ color: getSignalColor(signal.signal) }">
            {{ signal.signal }}
          </div>

          <div class="signal-details">
            <span class="price">¥{{ signal.price.toFixed(2) }}</span>
            <div class="strength">
              <div
                class="strength-bar"
                :style="{ width: signal.strength * 100 + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.real-time-signals {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.count {
  background: var(--el-color-primary);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.signals-list {
  flex: 1;
  overflow-y: auto;
}

.signal-item {
  background: var(--el-fill-color-light);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
  border-left: 3px solid var(--el-color-primary);
}

.signal-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.strategy {
  font-weight: bold;
  font-size: 12px;
}

.time {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.symbol-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.symbol {
  font-weight: bold;
}

.name {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.signal-action {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 8px;
}

.signal-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.strength {
  width: 60px;
  height: 4px;
  background: var(--el-border-color-light);
  border-radius: 2px;
  overflow: hidden;
}

.strength-bar {
  height: 100%;
  background: var(--el-color-primary);
  transition: width 0.3s ease;
}
</style>