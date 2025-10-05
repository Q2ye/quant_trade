<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'

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

// 策略参数
const parameters = ref<StrategyParameter[]>([
  {
    name: 'window',
    type: 'number',
    value: 20,
    default: 20,
    min: 5,
    max: 100,
    step: 1,
    description: '移动平均窗口大小'
  },
  {
    name: 'threshold',
    type: 'number',
    value: 0.02,
    default: 0.02,
    min: 0.01,
    max: 0.1,
    step: 0.01,
    description: '交易阈值'
  },
  {
    name: 'enable_stop_loss',
    type: 'boolean',
    value: true,
    default: true,
    description: '启用止损'
  },
  {
    name: 'stop_loss_rate',
    type: 'number',
    value: 0.05,
    default: 0.05,
    min: 0.01,
    max: 0.2,
    step: 0.01,
    description: '止损比例'
  },
  {
    name: 'strategy_type',
    type: 'select',
    value: 'trend',
    default: 'trend',
    options: [
      { label: '趋势跟踪', value: 'trend' },
      { label: '均值回归', value: 'mean_reversion' },
      { label: '动量策略', value: 'momentum' }
    ],
    description: '策略类型'
  }
])

// 参数值变化
const emit = defineEmits(['parameters-change'])

// 监听参数变化
watch(parameters.value, (newParams) => {
  const paramValues: Record<string, any> = {}
  newParams.forEach(param => {
    paramValues[param.name] = param.value
  })
  emit('parameters-change', paramValues)
}, { deep: true })

// 重置参数
const resetParameters = () => {
  parameters.value.forEach(param => {
    param.value = param.default
  })
}

// 导入参数配置
const importParameters = (config: StrategyParameter[]) => {
  parameters.value = config
}

// 导出参数配置
const exportParameters = () => {
  return parameters.value.map(param => ({
    name: param.name,
    value: param.value,
    type: param.type
  }))
}

// 参数验证
const validateParameters = () => {
  const errors: string[] = []

  parameters.value.forEach(param => {
    if (param.type === 'number') {
      if (param.value < param.min!) {
        errors.push(`参数 ${param.name} 不能小于 ${param.min}`)
      }
      if (param.value > param.max!) {
        errors.push(`参数 ${param.name} 不能大于 ${param.max}`)
      }
    }
  })

  return errors
}

// 根据参数类型渲染不同的输入组件
const renderParameterInput = (param: StrategyParameter) => {
  switch (param.type) {
    case 'number':
      return (
        <el-input-number
          v-model={param.value}
          min={param.min}
          max={param.max}
          step={param.step}
          controls-position="right"
          style="width: 100%"
        />
      )

    case 'boolean':
      return (
        <el-switch v-model={param.value} />
      )

    case 'select':
      return (
        <el-select v-model={param.value} style="width: 100%">
          {param.options?.map(option => (
            <el-option
              key={option.value}
              label={option.label}
              value={option.value}
            />
          ))}
        </el-select>
      )

    case 'string':
      return (
        <el-input v-model={param.value} />
      )

    default:
      return <span>不支持的类型</span>
  }
}
</script>

<template>
  <div class="parameter-panel">
    <div class="panel-header">
      <h3>策略参数</h3>
      <div class="header-actions">
        <el-button size="small" @click="resetParameters">重置</el-button>
      </div>
    </div>

    <div class="parameters-list">
      <div
        v-for="param in parameters"
        :key="param.name"
        class="parameter-item"
      >
        <div class="parameter-header">
          <span class="parameter-name">{{ param.name }}</span>
          <el-tooltip :content="param.description" placement="top">
            <el-icon><InfoFilled /></el-icon>
          </el-tooltip>
        </div>

        <div class="parameter-control">
          <component :is="renderParameterInput(param)" />
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
        <pre class="values-json">{{ JSON.stringify(parameters.reduce((acc, param) => {
          acc[param.name] = param.value
          return acc
        }, {} as Record<string, any>), null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.parameter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color);
}

.parameters-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.parameter-item {
  background: var(--el-fill-color-light);
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
  color: var(--el-text-color-primary);
}

.parameter-control {
  margin-bottom: 8px;
}

.parameter-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.panel-footer {
  border-top: 1px solid var(--el-border-color);
  padding: 16px;
}

.current-values h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}

.values-json {
  background: var(--el-fill-color-dark);
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  max-height: 120px;
  overflow-y: auto;
  margin: 0;
}
</style>