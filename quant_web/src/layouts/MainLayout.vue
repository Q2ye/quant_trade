<!--主布局（包含顶部+侧边栏）-->
<template>
  <div class="main-layout">
    <!-- 顶部状态栏 -->
    <AppHeader
      :current-time="currentTime"
      :data-status="dataStatus"
      :strategy-status="strategyStatus"
      @refresh-data="handleRefreshData"
    />

    <div class="main-content">
      <!-- 左侧导航栏 -->
      <AppSidebar
        :active-menu="activeMenu"
        @menu-change="handleMenuChange"
      />

      <!-- 中间工作区 -->
      <div class="workspace">
        <slot />
      </div>

      <!-- 右侧辅助面板 -->
      <AppAlertPanel
        :alerts="alerts"
        @clear-alert="handleClearAlert"
      />
    </div>

    <!-- 全局通知 -->
    <GlobalNotification
      v-if="showNotification"
      :message="notificationMessage"
      :type="notificationType"
      @close="showNotification = false"
    />
  </div>
</template>

<script>
import AppHeader from '../components/ui/AppHeader.vue';
import AppSidebar from '../components/ui/AppSidebar.vue';
import AppAlertPanel from '../components/ui/AppAlert.vue';
import GlobalNotification from '../components/ui/GlobalNotification.vue';

export default {
  name: "MainLayout",
  components: {
    AppHeader,
    AppSidebar,
    AppAlertPanel,
    GlobalNotification
  },
  props: {
    activeMenu: {
      type: String,
      default: 'market'
    }
  },
  data() {
    return {
      currentTime: new Date(),
      dataStatus: '已同步', // 数据同步状态
      strategyStatus: '运行中', // 策略运行状态
      alerts: [
        { id: 1, type: 'warning', message: '数据同步延迟超过5分钟', timestamp: new Date() },
        { id: 2, type: 'error', message: '策略回测失败: 参数越界', timestamp: new Date() },
        { id: 3, type: 'info', message: '交易信号触发: 600519.SH', timestamp: new Date() }
      ],
      showNotification: false,
      notificationMessage: '',
      notificationType: 'info'
    };
  },
  mounted() {
    // 更新时间
    this.timeInterval = setInterval(() => {
      this.currentTime = new Date();
    }, 1000);

    // 模拟数据状态变化
    this.dataStatusInterval = setInterval(() => {
      this.dataStatus = Math.random() > 0.8 ? '同步中...' : '已同步';
    }, 5000);
  },
  beforeUnmount() {
    clearInterval(this.timeInterval);
    clearInterval(this.dataStatusInterval);
  },
  methods: {
    // 处理菜单切换
    handleMenuChange(menuId) {
      this.$emit('menu-change', menuId);
    },

    // 处理数据刷新
    handleRefreshData() {
      this.showNotification = true;
      this.notificationMessage = '正在刷新市场数据...';
      this.notificationType = 'info';

      // 模拟数据刷新
      setTimeout(() => {
        this.notificationMessage = '数据刷新完成';
        this.notificationType = 'success';
      }, 2000);
    },

    // 清除警报
    handleClearAlert(alertId) {
      this.alerts = this.alerts.filter(alert => alert.id !== alertId);
    },

    // 添加新警报
    addAlert(type, message) {
      this.alerts.push({
        id: Date.now(),
        type,
        message,
        timestamp: new Date()
      });
    }
  }
}
</script>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--background-dark);
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.workspace {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: var(--background-content);
  box-shadow: inset 0 0 15px rgba(0, 0, 0, 0.2);
}

@media (max-width: 1200px) {
  .workspace {
    padding: 15px;
  }
}

@media (max-width: 768px) {
  .main-content {
    flex-direction: column;
  }

  .workspace {
    order: 2;
  }

  .alert-panel {
    order: 3;
    height: 200px;
  }
}
</style>