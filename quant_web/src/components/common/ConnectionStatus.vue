<script setup lang="ts">
import { computed } from "vue";
import { NTag, NTooltip } from "naive-ui";

interface Connection {
  name: string;
  type: "data" | "trade" | "websocket" | "database";
  status: "connected" | "disconnected" | "error" | "connecting";
  lastCheck: string;
  latency?: number;
}

interface Props {
  connections?: Connection[];
}

const props = withDefaults(defineProps<Props>(), {
  connections: () => [],
});

const statusMap: Record<
  string,
  { type: "success" | "info" | "error" | "warning" | "default"; text: string }
> = {
  connected: { type: "success", text: "已连接" },
  disconnected: { type: "default", text: "未连接" },
  error: { type: "error", text: "错误" },
  connecting: { type: "warning", text: "连接中" },
};

const getStatusInfo = (status: string) => {
  return statusMap[status] || { type: "default" as const, text: "未知状态" };
};

const typeMap: Record<string, string> = {
  data: "数据源",
  trade: "交易接口",
  websocket: "WebSocket",
  database: "数据库",
};

const getTypeName = (type: string) => {
  return typeMap[type] || "未知类型";
};

const formatTime = (time: string) => {
  try {
    return new Date(time).toLocaleTimeString();
  } catch {
    return "无效时间";
  }
};

const safeConnections = computed(() => {
  if (!props.connections || !Array.isArray(props.connections)) {
    return [];
  }
  return props.connections.filter((conn) => conn && typeof conn === "object");
});
</script>

<template>
  <div class="connection-status">
    <div
      v-for="(conn, index) in safeConnections"
      :key="conn.name || `conn-${index}`"
      class="connection-item"
    >
      <div class="connection-info">
        <span class="connection-name"
          >{{ getTypeName(conn.type) }} - {{ conn.name || "未知连接" }}</span
        >
        <div class="connection-details">
          <span class="last-check"
            >最后检查: {{ formatTime(conn.lastCheck) }}</span
          >
          <span
            v-if="conn.latency !== undefined && conn.latency !== null"
            class="latency"
          >
            延迟: {{ conn.latency }}ms
          </span>
        </div>
      </div>
      <NTooltip>
        <template #trigger>
          <NTag :type="getStatusInfo(conn.status).type">
            {{ getStatusInfo(conn.status).text }}
          </NTag>
        </template>
        {{ getStatusInfo(conn.status).text }}
      </NTooltip>
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
  border-bottom: 1px solid var(--n-border-color);
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
  color: var(--n-text-color-3);
}

.last-check,
.latency {
  margin-right: 12px;
}

.empty-state {
  text-align: center;
  color: var(--n-text-color-3);
  padding: 20px;
}
</style>
