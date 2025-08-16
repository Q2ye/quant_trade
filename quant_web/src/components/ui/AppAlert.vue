<!--预警提示组件-->
<script>
export default {
  name: "AppAlert",
  props: {
    alert: {
      type: Object,
      required: true,
      // 添加默认值防止 undefined
      default: () => ({
        level: 'info',
        title: '',
        content: '',
        timestamp: Date.now(),
        id: Date.now().toString()
      })
    }
  },
  computed: {
    alertIcon() {
      // 安全访问 alert.level
      const level = this.alert?.level || 'info';
      switch (level) {
        case 'critical': return 'el-icon-warning'
        case 'warning': return 'el-icon-warning-outline'
        default: return 'el-icon-info'
      }
    },

    alertColor() {
      // 安全访问 alert.level
      const level = this.alert?.level || 'info';
      switch (level) {
        case 'critical': return '#f56c6c'
        case 'warning': return '#e6a23c'
        default: return '#909399'
      }
    },

    formattedTime() {
      // 安全访问 alert.timestamp
      const timestamp = this.alert?.timestamp || Date.now();
      return new Date(timestamp).toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      })
    }
  }
}
</script>

<template>
  <!-- 添加 v-if 确保 alert 存在 -->
  <div v-if="alert" class="app-alert" :style="{ borderLeft: `3px solid ${alertColor}` }">
    <div class="alert-header">
      <div class="alert-icon" :style="{ color: alertColor }">
        <i :class="alertIcon"></i>
      </div>
      <div class="alert-title">{{ alert.title }}</div>
      <div class="alert-time">{{ formattedTime }}</div>
    </div>

    <div class="alert-content">
      {{ alert.content }}
    </div>

    <div class="alert-actions">
      <el-button
        v-if="alert.action"
        type="text"
        size="small"
        @click="$emit('action', alert)">
        {{ alert.action }}
      </el-button>
      <el-button
        type="text"
        size="small"
        @click="$emit('dismiss', alert.id)">
        忽略
      </el-button>
    </div>
  </div>
</template>

<style scoped>
/* 样式保持不变 */
.app-alert {
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 12px 15px;
  margin-bottom: 10px;
  transition: all 0.3s;
}

.app-alert:hover {
  box-shadow: 0 4px 16px 0 rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.alert-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.alert-icon {
  font-size: 18px;
  margin-right: 10px;
}

.alert-title {
  font-weight: bold;
  flex: 1;
}

.alert-time {
  font-size: 12px;
  color: #909399;
}

.alert-content {
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 10px;
}

.alert-actions {
  text-align: right;
}
</style>