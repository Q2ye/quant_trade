<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElTag, ElButton, ElTooltip } from 'element-plus'
import type { TagProps } from 'element-plus'

interface Strategy {
  id: string
  name: string
  status: 'running' | 'stopped' | 'error' | 'paused'
  type: string
  symbols: string[]
  startedAt: string
  performance?: {
    dailyReturn: number
    totalReturn: number
    sharpeRatio: number
  }
}

// 定义 props 接口，设置默认值
interface Props {
  strategies?: Strategy[]
}

// 使用 withDefaults 提供默认值
const props = withDefaults(defineProps<Props>(), {
  strategies: () => []
})

const emit = defineEmits<{
  stopStrategy: [id: string]
  startStrategy: [id: string]
  viewDetails: [id: string]
}>()

// 使用计算属性确保 strategies 总是有效的数组
const safeStrategies = computed(() => {
  if (!props.strategies || !Array.isArray(props.strategies)) {
    return []
  }
  return props.strategies.filter(strategy =>
    strategy && typeof strategy === 'object' && strategy.id
  )
})

// 使用 Element Plus 合法的 Tag 类型
type TagType = TagProps['type']

const statusMap: Record<string, { type: TagType; text: string }> = {
  running: { type: 'success', text: '运行中' },
  stopped: { type: 'info', text: '已停止' },
  error: { type: 'danger', text: '错误' },
  paused: { type: 'warning', text: '暂停' }
}

// 安全的格式化时间函数
const formatTime = (time: string) => {
  try {
    return new Date(time).toLocaleString()
  } catch (error) {
    console.warn('时间格式化错误:', error)
    return '无效时间'
  }
}

// 安全的格式化收益率函数
const formatReturn = (value: number | undefined) => {
  if (value === undefined || value === null) return '0.00%'
  return `${(value * 100).toFixed(2)}%`
}

// 安全的处理函数
const handleStop = (strategy: Strategy) => {
  if (strategy && strategy.status === 'running') {
    emit('stopStrategy', strategy.id)
  }
}

const handleStart = (strategy: Strategy) => {
  if (strategy && strategy.status === 'stopped') {
    emit('startStrategy', strategy.id)
  }
}

const handleViewDetails = (strategy: Strategy) => {
  if (strategy) {
    emit('viewDetails', strategy.id)
  }
}

// 安全的获取策略类型
const getStrategyType = (type: string | undefined) => {
  return type || '未知类型'
}

// 安全的获取标的符号
const getStrategySymbols = (symbols: string[] | undefined) => {
  if (!symbols || !Array.isArray(symbols)) {
    return '无标的'
  }
  return symbols.length > 0 ? symbols.join(', ') : '无标的'
}
</script>

<template>
  <div class="strategy-status">
    <div
      v-for="strategy in safeStrategies"
      :key="strategy.id"
      class="strategy-item"
    >
      <div class="strategy-header">
        <div class="strategy-info">
          <span class="strategy-name">{{ strategy.name || '未知策略' }}</span>
          <ElTag
            :type="statusMap[strategy.status]?.type || 'info'"
            size="small"
          >
            {{ statusMap[strategy.status]?.text || '未知状态' }}
          </ElTag>
        </div>
        <div class="strategy-actions">
          <ElTooltip content="查看详情">
            <ElButton
              size="mini"
              type="text"
              @click="handleViewDetails(strategy)"
            >
              详情
            </ElButton>
          </ElTooltip>
          <ElButton
            v-if="strategy.status === 'running'"
            size="mini"
            type="danger"
            text
            @click="handleStop(strategy)"
          >
            停止
          </ElButton>
          <ElButton
            v-else-if="strategy.status === 'stopped'"
            size="mini"
            type="primary"
            text
            @click="handleStart(strategy)"
          >
            启动
          </ElButton>
        </div>
      </div>

      <div class="strategy-details">
        <div class="detail-item">
          <span class="detail-label">类型:</span>
          <span class="detail-value">{{ getStrategyType(strategy.type) }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">标的:</span>
          <span class="detail-value">{{ getStrategySymbols(strategy.symbols) }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">启动时间:</span>
          <span class="detail-value">{{ formatTime(strategy.startedAt) }}</span>
        </div>

        <div v-if="strategy.performance" class="performance-metrics">
          <div class="metric-item">
            <span class="metric-label">日收益:</span>
            <span
              class="metric-value"
              :class="{
                positive: strategy.performance.dailyReturn > 0,
                negative: strategy.performance.dailyReturn < 0
              }"
            >
              {{ formatReturn(strategy.performance.dailyReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">总收益:</span>
            <span
              class="metric-value"
              :class="{
                positive: strategy.performance.totalReturn > 0,
                negative: strategy.performance.totalReturn < 0
              }"
            >
              {{ formatReturn(strategy.performance.totalReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">夏普比率:</span>
            <span class="metric-value">
              {{ strategy.performance.sharpeRatio?.toFixed(2) || '0.00' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="safeStrategies.length === 0" class="empty-state">
      暂无运行中的策略
    </div>
  </div>
</template>

<style scoped>
.strategy-status {
  max-height: 300px;
  overflow-y: auto;
}

.strategy-item {
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  margin-bottom: 8px;
  background: #fafafa;
}

.strategy-item:last-child {
  margin-bottom: 0;
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.strategy-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-name {
  font-weight: 500;
  color: #333;
}

.strategy-actions {
  display: flex;
  gap: 4px;
}

.strategy-details {
  font-size: 12px;
}

.detail-item {
  display: flex;
  margin-bottom: 4px;
}

.detail-label {
  color: #666;
  min-width: 60px;
}

.detail-value {
  color: #333;
  flex: 1;
}

.performance-metrics {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e8e8e8;
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.metric-label {
  font-size: 11px;
  color: #666;
  margin-bottom: 2px;
}

.metric-value {
  font-size: 12px;
  font-weight: 500;
  font-family: 'Courier New', monospace;
}

.positive {
  color: #f56c6c;
}

.negative {
  color: #67c23a;
}

.empty-state {
  text-align: center;
  color: #999;
  padding: 20px;
}
</style>