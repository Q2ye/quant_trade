<!--顶部状态栏-->
<template>
  <div class="app-header">
    <div class="logo-section">
      <div class="logo">
        <span class="logo-icon">Q</span>
        <span class="logo-text">QuantMaster</span>
      </div>
    </div>

    <div class="status-section">
      <div class="status-item">
        <span class="status-label">数据状态:</span>
        <status-badge :status="systemStatus.data" />
      </div>

      <div class="status-item">
        <span class="status-label">策略状态:</span>
        <status-badge
          :status="systemStatus.strategy"
          type="running"
        />
      </div>

      <div class="status-item">
        <span class="status-label">交易状态:</span>
        <status-badge
          :status="systemStatus.trade"
          type="success"
        />
      </div>
    </div>

    <div class="time-section">
      <div class="current-time">
        {{ formattedTime }}
      </div>
      <div class="current-date">
        {{ formattedDate }}
      </div>
    </div>

    <div class="alert-section">
      <el-badge
        :value="unreadAlerts"
        :max="99"
        class="alert-badge"
      >
        <el-button
          icon="el-icon-bell"
          circle
          @click="$emit('show-alerts')"
        />
      </el-badge>
    </div>

    <div class="user-section">
      <el-dropdown @command="handleCommand">
        <div class="user-info">
          <el-avatar
            icon="el-icon-user-solid"
            size="small"
          />
          <span class="user-name">QuantUser</span>
          <i class="el-icon-arrow-down" />
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              个人中心
            </el-dropdown-item>
            <el-dropdown-item command="settings">
              系统设置
            </el-dropdown-item>
            <el-dropdown-item
              divided
              command="logout"
            >
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script>
import StatusBadge from '../ui/StatusBadge.vue'

export default {
  name: "AppHeader",
  components: { StatusBadge },
  data() {
    return {
      currentTime: new Date(),
      systemStatus: {
        data: '已连接',
        strategy: '运行中',
        trade: '已连接'
      },
      unreadAlerts: 3
    }
  },
  computed: {
    formattedTime() {
      return this.currentTime.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    },

    formattedDate() {
      return this.currentTime.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        weekday: 'short'
      })
    }
  },
  mounted() {
    // 更新时间
    this.timeInterval = setInterval(() => {
      this.currentTime = new Date()
    }, 1000)

    // 模拟数据状态变化
    this.statusInterval = setInterval(() => {
      if (Math.random() > 0.8) {
        this.systemStatus.data = Math.random() > 0.5 ? '同步中...' : '已连接'
      }
    }, 5000)
  },
  beforeUnmount() {
    clearInterval(this.timeInterval)
    clearInterval(this.statusInterval)
  },
  methods: {
    handleCommand(command) {
      if (command === 'logout') {
        this.$router.push('/login')
      } else if (command === 'settings') {
        this.$router.push('/system/settings')
      }
    }
  }
}
</script>

<style scoped>
.app-header {
  height: 60px;
  background-color: #001529;
  color: #fff;
  display: flex;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  z-index: 100;
}

.logo-section {
  width: 220px;
}

.logo {
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

.logo-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #1890ff;
  border-radius: 50%;
  margin-right: 10px;
}

.status-section {
  flex: 1;
  display: flex;
  justify-content: center;
  gap: 30px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.65);
}

.time-section {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin-right: 30px;
}

.current-time {
  font-size: 16px;
  font-weight: 500;
}

.current-date {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
}

.alert-section {
  margin-right: 20px;
}

.alert-badge >>> .el-badge__content {
  top: 10px;
  right: 10px;
}

.user-section {
  margin-left: 10px;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 5px;
  border-radius: 4px;
  transition: all 0.3s;
}

.user-info:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.user-name {
  margin: 0 8px;
  font-size: 14px;
}
</style>