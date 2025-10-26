<!--数据卡片-->
<template>
  <div v-loading="loading" class="dashboard-card">
    <div class="card-header">
      <div
        class="card-icon"
        :style="{ backgroundColor: color + '20', color: color }"
      >
        <i :class="icon"></i>
      </div>
      <div class="card-title">{{ title }}</div>
      <status-badge v-if="status" :status="status" class="status-badge" />
    </div>

    <div class="card-value">
      {{ value }} <span class="unit">{{ unit }}</span>
    </div>

    <div class="card-footer">
      <div v-if="trend !== 0" class="trend" :class="trendClass">
        <i :class="trendIcon"></i>
        <span>{{ Math.abs(trend) }}%</span>
      </div>
      <div class="slot-content">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script>
import StatusBadge from "../ui/StatusBadge.vue";

export default {
  name: "DashboardCard",
  components: { StatusBadge },
  props: {
    title: {
      type: String,
      required: true,
    },
    value: {
      type: [String, Number],
      default: "",
    },
    unit: {
      type: String,
      default: "",
    },
    icon: {
      type: String,
      default: "el-icon-data-line",
    },
    color: {
      type: String,
      default: "var(--accent-color)",
    },
    trend: {
      type: Number,
      default: 0,
    },
    status: {
      type: String,
      default: "",
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    trendIcon() {
      return this.trend > 0 ? "el-icon-top" : "el-icon-bottom";
    },

    trendClass() {
      return this.trend > 0 ? "trend-up" : "trend-down";
    },
  },
};
</script>

<style lang="scss" scoped>
.dashboard-card {
  background-color: var(--card-bg);
  border-radius: var(--border-radius);
  box-shadow: var(--card-shadow);
  padding: var(--spacer-4);
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all var(--transition-normal);
  border: 1px solid var(--border-color);
}

.dashboard-card:hover {
  transform: var(--hover-transform);
  box-shadow: var(--hover-shadow);
}

.card-header {
  display: flex;
  align-items: center;
  margin-bottom: var(--spacer-3);
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-right: var(--spacer-2);
}

.card-title {
  font-size: 14px;
  color: var(--text-secondary);
  flex: 1;
}

.status-badge {
  margin-left: var(--spacer-2);
}

.card-value {
  font-size: 28px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacer-2);
  line-height: 1.2;
}

.unit {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: var(--font-weight-normal);
}

.card-footer {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trend {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.trend i {
  margin-right: 4px;
}

.trend-up {
  color: var(--success-color);
}

.trend-down {
  color: var(--danger-color);
}

.slot-content {
  flex: 1;
  text-align: right;
}

:root {
  --accent-color: #2196F3;
  --success-color: #67c23a;
  --danger-color: #f56c6c;
  --card-bg: #ffffff;
  --text-primary: #303133;
  --text-secondary: #606266;
  --border-color: #e1e4e8;
  --border-radius: 4px;
  --spacer-2: 0.5rem;
  --spacer-3: 1rem;
  --spacer-4: 1.5rem;
  --transition-normal: 0.3s;
  --hover-transform: translateY(-5px);
  --card-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  --hover-shadow: 0 6px 16px 0 rgba(0, 0, 0, 0.12);
  --font-weight-normal: 400;
  --font-weight-bold: 700;
}
</style>