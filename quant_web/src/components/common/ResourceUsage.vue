<script setup lang="ts">
import { computed } from "vue";
import { NProgress } from "naive-ui";

interface ResourceUsage {
  cpu: {
    usage: number;
    cores: number;
    loadAverage: number[];
  };
  memory: {
    usage: number;
    total: number;
    used: number;
    unit: string;
  };
  disk: {
    usage: number;
    total: number;
    used: number;
    unit: string;
  };
  network?: {
    upload: number;
    download: number;
    unit: string;
  };
}

interface Props {
  resources?: ResourceUsage;
}

const props = withDefaults(defineProps<Props>(), {
  resources: () => ({
    cpu: { usage: 0, cores: 4, loadAverage: [0, 0, 0] },
    memory: { usage: 0, total: 0, used: 0, unit: "GB" },
    disk: { usage: 0, total: 0, used: 0, unit: "GB" },
    network: { upload: 0, download: 0, unit: "MB" },
  }),
});

const safeResources = computed(
  () =>
    props.resources || {
      cpu: { usage: 0, cores: 4, loadAverage: [0, 0, 0] },
      memory: { usage: 0, total: 0, used: 0, unit: "GB" },
      disk: { usage: 0, total: 0, used: 0, unit: "GB" },
      network: { upload: 0, download: 0, unit: "MB" },
    },
);

const safeCpu = computed(() => {
  const cpu = safeResources.value.cpu;
  return {
    usage: cpu?.usage || 0,
    cores: cpu?.cores || 4,
    loadAverage: cpu?.loadAverage || [0, 0, 0],
  };
});

const safeMemory = computed(() => {
  const memory = safeResources.value.memory;
  return {
    usage: memory?.usage || 0,
    total: memory?.total || 0,
    used: memory?.used || 0,
    unit: memory?.unit || "GB",
  };
});

const safeDisk = computed(() => {
  const disk = safeResources.value.disk;
  return {
    usage: disk?.usage || 0,
    total: disk?.total || 0,
    used: disk?.used || 0,
    unit: disk?.unit || "GB",
  };
});

const safeNetwork = computed(() => {
  return safeResources.value.network || { upload: 0, download: 0, unit: "MB" };
});

const formatBytes = (bytes: number): string => {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex++;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
};

const getStatusType = (
  usage: number,
): "success" | "warning" | "error" | undefined => {
  if (usage == null) return undefined;
  if (usage < 70) return "success";
  if (usage < 85) return "warning";
  return "error";
};

const safeToFixed = (
  value: number | undefined | null,
  digits: number = 1,
): string => {
  if (value === undefined || value === null) return "0.0";
  return value.toFixed(digits);
};
</script>

<template>
  <div class="resource-usage">
    <div class="resource-item">
      <div class="resource-header">
        <span class="resource-title">CPU 使用率</span>
        <span class="resource-value">{{ safeToFixed(safeCpu.usage) }}%</span>
      </div>
      <NProgress
        :percentage="safeCpu.usage"
        :status="getStatusType(safeCpu.usage)"
        :show-indicator="false"
      />
      <div class="resource-details">
        <span>核心: {{ safeCpu.cores }}</span>
        <span>负载: {{ safeToFixed(safeCpu.loadAverage[0], 2) }}</span>
      </div>
    </div>

    <div class="resource-item">
      <div class="resource-header">
        <span class="resource-title">内存使用</span>
        <span class="resource-value">{{ safeToFixed(safeMemory.usage) }}%</span>
      </div>
      <NProgress
        :percentage="safeMemory.usage"
        :status="getStatusType(safeMemory.usage)"
        :show-indicator="false"
      />
      <div class="resource-details">
        <span
          >{{ formatBytes(safeMemory.used) }} /
          {{ formatBytes(safeMemory.total) }}</span
        >
      </div>
    </div>

    <div class="resource-item">
      <div class="resource-header">
        <span class="resource-title">磁盘使用</span>
        <span class="resource-value">{{ safeToFixed(safeDisk.usage) }}%</span>
      </div>
      <NProgress
        :percentage="safeDisk.usage"
        :status="getStatusType(safeDisk.usage)"
        :show-indicator="false"
      />
      <div class="resource-details">
        <span
          >{{ formatBytes(safeDisk.used) }} /
          {{ formatBytes(safeDisk.total) }}</span
        >
      </div>
    </div>

    <div v-if="safeNetwork" class="resource-item">
      <div class="resource-header">
        <span class="resource-title">网络流量</span>
      </div>
      <div class="network-stats">
        <div class="network-item">
          <span class="network-label">上传:</span>
          <span class="network-value"
            >{{ safeToFixed(safeNetwork.upload) }}
            {{ safeNetwork.unit }}/s</span
          >
        </div>
        <div class="network-item">
          <span class="network-label">下载:</span>
          <span class="network-value"
            >{{ safeToFixed(safeNetwork.download) }}
            {{ safeNetwork.unit }}/s</span
          >
        </div>
      </div>
    </div>

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
  color: var(--n-text-color-1);
}

.resource-value {
  font-size: 14px;
  color: var(--n-text-color-3);
}

.resource-details {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--n-text-color-3);
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
  color: var(--n-text-color-3);
}

.network-value {
  color: var(--n-text-color-1);
  font-family: "Courier New", monospace;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--n-text-color-3);
  font-size: 14px;
}
</style>
