<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElProgress } from 'element-plus'
import type { ProgressProps } from 'element-plus'

interface ResourceUsage {
  cpu: {
    usage: number
    cores: number
    loadAverage: number[]
  }
  memory: {
    usage: number
    total: number
    used: number
    unit: string
  }
  disk: {
    usage: number
    total: number
    used: number
    unit: string
  }
  network?: {
    upload: number
    download: number
    unit: string
  }
}

// 定义 props 接口，设置默认值
interface Props {
  resources?: ResourceUsage
}

// 使用 withDefaults 提供默认值
const props = withDefaults(defineProps<Props>(), {
  resources: () => ({
    cpu: {
      usage: 0,
      cores: 4,
      loadAverage: [0, 0, 0]
    },
    memory: {
      usage: 0,
      total: 0,
      used: 0,
      unit: 'GB'
    },
    disk: {
      usage: 0,
      total: 0,
      used: 0,
      unit: 'GB'
    },
    network: {
      upload: 0,
      download: 0,
      unit: 'MB'
    }
  })
})

// 计算属性：安全的资源数据访问
const safeResources = computed(() => {
  if (!props.resources) {
    return {
      cpu: {
        usage: 0,
        cores: 4,
        loadAverage: [0, 0, 0]
      },
      memory: {
        usage: 0,
        total: 0,
        used: 0,
        unit: 'GB'
      },
      disk: {
        usage: 0,
        total: 0,
        used: 0,
        unit: 'GB'
      },
      network: {
        upload: 0,
        download: 0,
        unit: 'MB'
      }
    }
  }
  return props.resources
})

// 安全的 CPU 数据访问
const safeCpu = computed(() => {
  const cpu = safeResources.value.cpu
  return {
    usage: cpu?.usage || 0,
    cores: cpu?.cores || 4,
    loadAverage: cpu?.loadAverage || [0, 0, 0]
  }
})

// 安全的内存数据访问
const safeMemory = computed(() => {
  const memory = safeResources.value.memory
  return {
    usage: memory?.usage || 0,
    total: memory?.total || 0,
    used: memory?.used || 0,
    unit: memory?.unit || 'GB'
  }
})

// 安全的磁盘数据访问
const safeDisk = computed(() => {
  const disk = safeResources.value.disk
  return {
    usage: disk?.usage || 0,
    total: disk?.total || 0,
    used: disk?.used || 0,
    unit: disk?.unit || 'GB'
  }
})

// 安全的网络数据访问
const safeNetwork = computed(() => {
  return safeResources.value.network || {
    upload: 0,
    download: 0,
    unit: 'MB'
  }
})

const formatBytes = (bytes: number): string => {
  if (bytes === 0 || bytes === undefined || bytes === null) return '0 B'
  
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unitIndex = 0

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex++
  }

  return `${value.toFixed(1)} ${units[unitIndex]}`
}

// 使用 Element Plus 合法的 Progress 状态类型
type ProgressStatus = ProgressProps['status']

const getStatusType = (usage: number): ProgressStatus => {
  if (usage === undefined || usage === null) return undefined
  if (usage < 70) return undefined
  if (usage < 85) return 'warning'
  return 'exception'
}

// 安全的数值格式化
const safeToFixed = (value: number | undefined | null, digits: number = 1): string => {
  if (value === undefined || value === null) return '0.0'
  return value.toFixed(digits)
}
</script>

<template>
  <div class="resource-usage">
    <!-- CPU Usage -->
    <div class="resource-item">
      <div class="resource-header">
        <span class="resource-title">CPU 使用率</span>
        <span class="resource-value">{{ safeToFixed(safeCpu.usage) }}%</span>
      </div>
      <ElProgress
        :percentage="safeCpu.usage"
        :status="getStatusType(safeCpu.usage)"
        :show-text="false"
      />
      <div class="resource-details">
        <span>核心: {{ safeCpu.cores }}</span>
        <span>负载: {{ safeToFixed(safeCpu.loadAverage[0], 2) }}</span>
      </div>
    </div>

    <!-- Memory Usage -->
    <div class="resource-item">
      <div class="resource-header">
        <span class="resource-title">内存使用</span>
        <span class="resource-value">{{ safeToFixed(safeMemory.usage) }}%</span>
      </div>
      <ElProgress
        :percentage="safeMemory.usage"
        :status="getStatusType(safeMemory.usage)"
        :show-text="false"
      />
      <div class="resource-details">
        <span>{{ formatBytes(safeMemory.used) }} / {{ formatBytes(safeMemory.total) }}</span>
      </div>
    </div>

    <!-- Disk Usage -->
    <div class="resource-item">
      <div class="resource-header">
        <span class="resource-title">磁盘使用</span>
        <span class="resource-value">{{ safeToFixed(safeDisk.usage) }}%</span>
      </div>
      <ElProgress
        :percentage="safeDisk.usage"
        :status="getStatusType(safeDisk.usage)"
        :show-text="false"
      />
      <div class="resource-details">
        <span>{{ formatBytes(safeDisk.used) }} / {{ formatBytes(safeDisk.total) }}</span>
      </div>
    </div>

    <!-- Network Usage -->
    <div v-if="safeNetwork" class="resource-item">
      <div class="resource-header">
        <span class="resource-title">网络流量</span>
      </div>
      <div class="network-stats">
        <div class="network-item">
          <span class="network-label">上传:</span>
          <span class="network-value">{{ safeToFixed(safeNetwork.upload) }} {{ safeNetwork.unit }}/s</span>
        </div>
        <div class="network-item">
          <span class="network-label">下载:</span>
          <span class="network-value">{{ safeToFixed(safeNetwork.download) }} {{ safeNetwork.unit }}/s</span>
        </div>
      </div>
    </div>

    <!-- 空状态显示 -->
    <div v-if="!props.resources" class="empty-state">
      <p>等待资源数据加载...</p>
    </div>
  </div>
</template>

<style scoped>
.resource-usage {
  padding: 8px 0;
  min-height: 200px;
}

.resource-item {
  margin-bottom: 20px;
}

.resource-item:last-child {
  margin-bottom: 0;
}

.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.resource-title {
  font-weight: 500;
  color: #333;
}

.resource-value {
  font-size: 14px;
  color: #666;
}

.resource-details {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.network-stats {
  margin-top: 8px;
}

.network-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 13px;
}

.network-label {
  color: #666;
}

.network-value {
  color: #333;
  font-family: 'Courier New', monospace;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
  font-size: 14px;
}

:deep(.el-progress-bar) {
  padding-right: 0;
}
</style>