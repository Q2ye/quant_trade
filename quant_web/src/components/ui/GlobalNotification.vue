<template>
  <div class="global-notification">
    <div class="notification-bell" @click="toggleNotifications">
      <span class="bell-icon">🔔</span>
      <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
    </div>

    <div v-if="showNotifications" class="notifications-panel">
      <div class="panel-header">
        <h3>系统通知</h3>
        <button @click="markAllAsRead" class="mark-read-btn">全部已读</button>
      </div>

      <div class="notifications-list">
        <div
          v-for="notification in notifications"
          :key="notification.id"
          class="notification-item"
          :class="{'unread': !notification.read}">
          <div class="notification-icon">
            <span v-if="notification.type === 'alert'">⚠️</span>
            <span v-else-if="notification.type === 'trade'">💹</span>
            <span v-else>ℹ️</span>
          </div>
          <div class="notification-content">
            <div class="notification-title">{{ notification.title }}</div>
            <div class="notification-time">{{ formatTime(notification.time) }}</div>
            <div class="notification-message">{{ notification.message }}</div>
          </div>
          <div class="notification-actions">
            <button @click="handleAction(notification)">查看</button>
          </div>
        </div>
      </div>

      <div v-if="notifications.length === 0" class="empty-notifications">
        暂无通知
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "GlobalNotification",
  data() {
    return {
      showNotifications: false,
      notifications: [
        {
          id: 1,
          type: 'alert',
          title: '风险预警',
          message: '单日亏损已接近5%阈值',
          time: new Date(Date.now() - 3600000),
          read: false
        },
        {
          id: 2,
          type: 'trade',
          title: '交易信号',
          message: '策略A触发买入信号: 600519.SH',
          time: new Date(Date.now() - 1800000),
          read: false
        },
        {
          id: 3,
          type: 'system',
          title: '系统维护',
          message: '今晚22:00-24:00进行系统维护',
          time: new Date(Date.now() - 86400000),
          read: true
        }
      ]
    }
  },
  computed: {
    unreadCount() {
      return this.notifications.filter(n => !n.read).length;
    }
  },
  methods: {
    toggleNotifications() {
      this.showNotifications = !this.showNotifications;
      // 打开时标记为已读
      if (this.showNotifications) {
        this.markAllAsRead();
      }
    },
    markAllAsRead() {
      this.notifications.forEach(n => n.read = true);
    },
    formatTime(date) {
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.round(diffMs / 60000);

      if (diffMins < 1) return '刚刚';
      if (diffMins < 60) return `${diffMins}分钟前`;

      const diffHours = Math.round(diffMins / 60);
      if (diffHours < 24) return `${diffHours}小时前`;

      return date.toLocaleDateString();
    },
    handleAction(notification) {
      this.$emit('notification-action', notification);
      this.showNotifications = false;
    }
  }
}
</script>

<style scoped>
.global-notification {
  position: relative;
  display: inline-block;
}

.notification-bell {
  position: relative;
  cursor: pointer;
  font-size: 18px;
  padding: 5px 10px;
}

.badge {
  position: absolute;
  top: -5px;
  right: 0;
  background-color: #f56c6c;
  color: white;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.notifications-panel {
  position: absolute;
  top: 100%;
  right: 0;
  width: 350px;
  background-color: white;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  z-index: 1000;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  border-bottom: 1px solid #dcdfe6;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
}

.mark-read-btn {
  background: none;
  border: none;
  color: #409eff;
  cursor: pointer;
  font-size: 12px;
}

.notifications-list {
  max-height: 400px;
  overflow-y: auto;
}

.notification-item {
  display: flex;
  padding: 12px 15px;
  border-bottom: 1px solid #eee;
}

.notification-item.unread {
  background-color: #f0f7ff;
}

.notification-icon {
  font-size: 20px;
  margin-right: 12px;
}

.notification-content {
  flex: 1;
}

.notification-title {
  font-weight: bold;
  margin-bottom: 3px;
}

.notification-time {
  color: #909399;
  font-size: 11px;
  margin-bottom: 5px;
}

.notification-message {
  font-size: 13px;
  color: #606266;
}

.notification-actions {
  display: flex;
  align-items: center;
}

.notification-actions button {
  background: none;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  padding: 3px 8px;
  font-size: 12px;
  cursor: pointer;
}

.empty-notifications {
  padding: 30px;
  text-align: center;
  color: #909399;
}
</style>