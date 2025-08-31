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
      default: "#1890ff",
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

<style scoped>
.dashboard-card {
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s;
}

.dashboard-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 16px 0 rgba(0, 0, 0, 0.12);
}

.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-right: 12px;
}

.card-title {
  font-size: 14px;
  color: #606266;
  flex: 1;
}

.status-badge {
  margin-left: 10px;
}

.card-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 10px;
  line-height: 1.2;
}

.unit {
  font-size: 14px;
  color: #909399;
  font-weight: normal;
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
  color: #f56c6c;
}

.trend-down {
  color: #67c23a;
}

.slot-content {
  flex: 1;
  text-align: right;
}
</style>
