<!--预警提示组件-->
<template>
  <div
    v-if="alert"
    class="app-alert"
    :style="{ borderLeft: `3px solid ${alertColor}` }"
  >
    <div class="alert-header">
      <div class="alert-icon" :style="{ color: alertColor }">
        <i :class="alertIcon" />
      </div>
      <div class="alert-title">
        {{ alert.title }}
      </div>
      <div class="alert-time">
        {{ formattedTime }}
      </div>
    </div>

    <div class="alert-content">
      {{ alert.content }}
    </div>

    <div class="alert-actions">
      <el-button
        v-if="alert.action"
        type="text"
        size="small"
        @click="$emit('action', alert)"
      >
        {{ alert.action }}
      </el-button>
      <el-button type="text" size="small" @click="$emit('dismiss', alert.id)">
        忽略
      </el-button>
    </div>
  </div>
</template>

<script>
export default {
  name: "AppAlert",
  props: {
    alert: {
      type: Object,
      required: true,
      default: () => ({
        level: "info",
        title: "",
        content: "",
        timestamp: Date.now(),
        id: Date.now().toString(),
      }),
    },
  },
  emits: ["action", "dismiss"],
  computed: {
    alertIcon() {
      const level = this.alert?.level || "info";
      switch (level) {
        case "critical":
          return "el-icon-warning";
        case "warning":
          return "el-icon-warning-outline";
        default:
          return "el-icon-info";
      }
    },

    alertColor() {
      const level = this.alert?.level || "info";
      switch (level) {
        case "critical":
          return "var(--alert-critical-color)";
        case "warning":
          return "var(--alert-warning-color)";
        default:
          return "var(--alert-info-color)";
      }
    },

    formattedTime() {
      const timestamp = this.alert?.timestamp || Date.now();
      return new Date(timestamp).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    },
  },
};
</script>

<style lang="scss" scoped>
.app-alert {
  background-color: var(--card-bg);
  border-radius: var(--border-radius);
  box-shadow: var(--card-shadow);
  padding: var(--spacer-3) var(--spacer-4);
  margin-bottom: var(--spacer-2);
  transition: all var(--transition-normal);
  border: 1px solid var(--border-color);
}

.app-alert:hover {
  box-shadow: var(--hover-shadow);
  transform: var(--hover-transform);
}

.alert-header {
  display: flex;
  align-items: center;
  margin-bottom: var(--spacer-2);
}

.alert-icon {
  font-size: 18px;
  margin-right: var(--spacer-2);
}

.alert-title {
  font-weight: var(--font-weight-semibold);
  flex: 1;
  color: var(--text-primary);
}

.alert-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.alert-content {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: var(--spacer-2);
}

.alert-actions {
  text-align: right;
}

:root {
  --alert-critical-color: #f56c6c;
  --alert-warning-color: #e6a23c;
  --alert-info-color: #909399;
  --spacer-2: 0.5rem;
  --spacer-3: 1rem;
  --spacer-4: 1.5rem;
}
</style>