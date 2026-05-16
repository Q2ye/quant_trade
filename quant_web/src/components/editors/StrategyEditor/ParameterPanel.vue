<script setup lang="ts">
import { ref, watch } from 'vue'
import { NButton, NInput, NInputNumber, NSelect, NSwitch, NTooltip } from 'naive-ui'

interface StrategyParameter {
  name: string
  type: 'number' | 'string' | 'boolean' | 'select'
  value: any
  default: any
  min?: number
  max?: number
  step?: number
  options?: Array<{ label: string; value: any }>
  description: string
}

const parameters = ref<StrategyParameter[]>([
  {
    name: 'window', type: 'number', value: 20, default: 20,
    min: 5, max: 100, step: 1, description: '移动平均窗口大小'
  },
  {
    name: 'threshold', type: 'number', value: 0.02, default: 0.02,
    min: 0.01, max: 0.1, step: 0.01, description: '交易阈值'
  },
  {
    name: 'enable_stop_loss', type: 'boolean', value: true, default: true,
    description: '启用止损'
  },
  {
    name: 'stop_loss_rate', type: 'number', value: 0.05, default: 0.05,
    min: 0.01, max: 0.2, step: 0.01, description: '止损比例'
  },
  {
    name: 'strategy_type', type: 'select', value: 'trend', default: 'trend',
    options: [
      { label: '趋势跟踪', value: 'trend' },
      { label: '均值回归', value: 'mean_reversion' },
      { label: '动量策略', value: 'momentum' }
    ],
    description: '策略类型'
  }
])

const emit = defineEmits<{
  'parameters-change': [value: Record<string, any>]
}>()

watch(parameters, (newParams) => {
  const paramValues: Record<string, any> = {}
  newParams.forEach(param => { paramValues[param.name] = param.value })
  emit('parameters-change', paramValues)
}, { deep: true })

const resetParameters = () => {
  parameters.value.forEach(param => { param.value = param.default })
}

const validateParameters = () => {
  const errors: string[] = []
  parameters.value.forEach(param => {
    if (param.type === 'number') {
      if (param.value < param.min!) errors.push(`参数 ${param.name} 不能小于 ${param.min}`)
      if (param.value > param.max!) errors.push(`参数 ${param.name} 不能大于 ${param.max}`)
    }
  })
  return errors
}
</script>

<template>
  <div class="parameter-panel">
    <div class="panel-header">
      <h3>策略参数</h3>
      <div class="header-actions">
        <NButton size="small" @click="resetParameters">重置</NButton>
      </div>
    </div>

    <div class="parameters-list">
      <div v-for="param in parameters" :key="param.name" class="parameter-item">
        <div class="parameter-header">
          <span class="parameter-name">{{ param.name }}</span>
          <NTooltip placement="top">
            <template #trigger>
              <span class="info-icon">?</span>
            </template>
            {{ param.description }}
          </NTooltip>
        </div>

        <div class="parameter-control">
          <!-- number -->
          <NInputNumber
            v-if="param.type === 'number'"
            v-model:value="param.value"
            :min="param.min"
            :max="param.max"
            :step="param.step"
            style="width: 100%"
          />
          <!-- boolean -->
          <NSwitch v-else-if="param.type === 'boolean'" v-model:value="param.value" />
          <!-- select -->
          <NSelect
            v-else-if="param.type === 'select'"
            v-model:value="param.value"
            :options="param.options!"
            style="width: 100%"
          />
          <!-- string -->
          <NInput v-else-if="param.type === 'string'" v-model:value="param.value" />
          <span v-else>不支持的类型</span>
        </div>

        <div class="parameter-meta">
          <span class="parameter-type">{{ param.type }}</span>
          <span v-if="param.type === 'number'" class="parameter-range">
            {{ param.min }} - {{ param.max }}
          </span>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <div class="current-values">
        <h4>当前参数值</h4>
        <pre class="values-json">{{ JSON.stringify(parameters.reduce((acc: Record<string, any>, param) => {
          acc[param.name] = param.value
          return acc
        }, {}), null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.parameter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--n-body-color);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--n-border-color);
}

.parameters-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.parameter-item {
  background: var(--n-color-embedded);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}

.parameter-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.parameter-name {
  font-weight: bold;
  color: var(--n-text-color-1);
}

.info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--n-color-target);
  color: white;
  font-size: 11px;
  font-weight: bold;
  cursor: help;
}

.parameter-control {
  margin-bottom: 8px;
}

.parameter-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.panel-footer {
  border-top: 1px solid var(--n-border-color);
  padding: 16px;
}

.current-values h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}

.values-json {
  background: var(--n-color-embedded);
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  max-height: 120px;
  overflow-y: auto;
  margin: 0;
  color: var(--n-text-color-2);
}
</style>
