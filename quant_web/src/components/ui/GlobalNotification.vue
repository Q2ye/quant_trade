<!-- 全局通知组件 - 迁移到 Naive UI 和统一图标方案 -->
<template>
  <div class="global-notification">
    <n-popover
      placement="bottom-end"
      trigger="click"
      :show="showNotifications"
      @update:show="handlePopoverUpdate"
    >
      <template #trigger>
        <div class="notification-bell">
          <n-badge :value="unreadCount" :max="99" dot>
            <!-- 使用 SmartIcon 组件 -->
            <smart-icon name="Bell" size="20" />
          </n-badge>
        </div>
      </template>

      <div class="notifications-panel">
        <div class="panel-header">
          <h3>系统通知</h3>
          <n-button text type="primary" size="small" @click="markAllAsRead">
            全部已读
          </n-button>
        </div>

        <div class="notifications-list">
          <div
            v-for="notification in notifications"
            :key="notification.id"
            class="notification-item"
            :class="{ unread: !notification.read }"
          >
            <div class="notification-icon">
              <!-- 使用 SmartIcon 组件 -->
              <smart-icon 
                :name="getNotificationIcon(notification.type)" 
                size="20" 
              />
            </div>
            <div class="notification-content">
              <div class="notification-title">
                {{ notification.title }}
              </div>
              <div class="notification-time">
                {{ formatTime(notification.time) }}
              </div>
              <div class="notification-message">
                {{ notification.message }}
              </div>
            </div>
            <div class="notification-actions">
              <n-button size="small" @click="handleAction(notification)">
                查看
              </n-button>
            </div>
          </div>
        </div>

        <div v-if="notifications.length === 0" class="empty-notifications">
          暂无通知
        </div>
      </div>
    </n-popover>
  </div>
</template>

<script>
import { defineComponent, ref, computed } from 'vue'
import { NPopover, NBadge, NButton } from 'naive-ui'
// 导入 SmartIcon 组件
import SmartIcon from '../common/SmartIcon.vue'

export default defineComponent({
  name: "GlobalNotification",
  components: {
    NPopover,
    NBadge,
    NButton,
    SmartIcon // 注册 SmartIcon 组件
  },
  emits: ["notification-action"],
  setup(_, { emit }) {
    const showNotifications = ref(false)
    const notifications = ref([
      {
        id: 1,
        type: "alert",
        title: "风险预警",
        message: "单日亏损已接近5%阈值",
        time: new Date(Date.now() - 3600000),
        read: false,
      },
      {
        id: 2,
        type: "trade",
        title: "交易信号",
        message: "策略A触发买入信号: 600519.SH",
        time: new Date(Date.now() - 1800000),
        read: false,
      },
      {
        id: 3,
        type: "system",
        title: "系统维护",
        message: "今晚22:00-24:00进行系统维护",
        time: new Date(Date.now() - 86400000),
        read: true,
      },
    ])

    const unreadCount = computed(() => {
      return notifications.value.filter((n) => !n.read).length
    })

    const handlePopoverUpdate = (value) => {
      showNotifications.value = value
      if (value) {
        markAllAsRead()
      }
    }

    const markAllAsRead = () => {
      notifications.value.forEach((n) => (n.read = true))
    }

    const formatTime = (date) => {
      const now = new Date()
      const diffMs = now - date
      const diffMins = Math.round(diffMs / 60000)

      if (diffMins < 1) return "刚刚"
      if (diffMins < 60) return `${diffMins}分钟前`

      const diffHours = Math.round(diffMins / 60)
      if (diffHours < 24) return `${diffHours}小时前`

      return date.toLocaleDateString()
    }

    // 获取通知图标 - 使用统一的图标名称
    const getNotificationIcon = (type) => {
      const iconMap = {
        alert: "Warning", // 警告图标
        trade: "SwapHorizontal", // 交易图标
        system: "InformationCircle" // 信息图标
      }
      return iconMap[type] || "InformationCircle"
    }

    const handleAction = (notification) => {
      emit("notification-action", notification)
      showNotifications.value = false
    }

    return {
      showNotifications,
      notifications,
      unreadCount,
      handlePopoverUpdate,
      markAllAsRead,
      formatTime,
      getNotificationIcon,
      handleAction,
    }
  },
})
</script>

<style lang="scss" scoped>
.global-notification {
  position: relative;
  display: inline-block;
}

.notification-bell {
  position: relative;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background-color 0.2s var(--n-bezier);
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background-color: var(--n-hover-color);
  }
}

.notifications-panel {
  width: 350px;
  background-color: var(--n-popover-color);
  border-radius: var(--n-border-radius);
  box-shadow: var(--n-box-shadow-3);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--n-divider-color);
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--n-text-color-1);
  font-weight: 600;
}

.notifications-list {
  max-height: 400px;
  overflow-y: auto;
}

.notification-item {
  display: flex;
  padding: 12px 16px;
  border-bottom: 1px solid var(--n-divider-color);
  transition: background-color 0.2s var(--n-bezier);
}

.notification-item.unread {
  background-color: var(--n-hover-color);
}

.notification-item:hover {
  background-color: var(--n-hover-color);
}

.notification-icon {
  margin-right: 12px;
  display: flex;
  align-items: flex-start;
}

.notification-content {
  flex: 1;
}

.notification-title {
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--n-text-color-1);
}

.notification-time {
  color: var(--n-text-color-3);
  font-size: 11px;
  margin-bottom: 6px;
}

.notification-message {
  font-size: 13px;
  color: var(--n-text-color-2);
  line-height: 1.4;
}

.notification-actions {
  display: flex;
  align-items: center;
  margin-left: 8px;
}

.empty-notifications {
  padding: 24px;
  text-align: center;
  color: var(--n-text-color-3);
}
</style>