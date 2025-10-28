<template>
  <header class="app-header">
    <div class="logo-section">
      <div class="logo">
        <Icon icon="mdi:robot" class="logo-icon"/>
        <span class="logo-text">量化交易平台</span>
      </div>
    </div>

    <div class="status-section">
      <!-- 市场状态 -->
      <div class="status-item market-status">
        <div class="status-indicator status-open"></div>
        <div class="market-data">
          <span class="market-name">上证</span>
          <span class="market-value">3,245.68</span>
          <span class="market-change positive">+1.25%</span>
        </div>
        <div class="market-data">
          <span class="market-name">深证</span>
          <span class="market-value">10,845.32</span>
          <span class="market-change positive">+0.87%</span>
        </div>
        <div class="market-data">
          <span class="market-name">创业</span>
          <span class="market-value">2,245.67</span>
          <span class="market-change negative">-0.23%</span>
        </div>
      </div>

      <!-- 交易时段状态 -->
      <div class="status-item trading-session">
        <Icon icon="mdi:clock-outline" class="session-icon"/>
        <span>交易时段: 09:30-11:30</span>
      </div>
    </div>

    <!-- 头部小部件 -->
    <div class="header-widgets">
      <!-- 策略状态 -->
      <div class="header-widget strategy-status"
           :title="`运行中策略: ${strategyStatus.running}/${strategyStatus.total}\n健康状态: ${getHealthText(strategyStatus.health)}`">
        <div class="widget-content">
          <Icon icon="mdi:cog" class="widget-icon"/>
          <span class="widget-count">{{ strategyStatus.running }}/{{ strategyStatus.total }}</span>
          <div class="status-dot" :class="strategyStatus.health"></div>
        </div>
      </div>

      <!-- 信号状态 -->
      <div class="header-widget signal-status"
           :title="`今日信号: ${signalStats.today}个\n已触发: ${signalStats.triggered}个`">
        <div class="widget-content">
          <Icon icon="mdi:bell-outline" class="widget-icon"/>
          <span class="widget-count">{{ signalStats.triggered }}/{{ signalStats.today }}</span>
        </div>
      </div>

      <!-- 订单状态 -->
      <div class="header-widget order-status"
           :title="`待处理订单: ${orderStats.pending}个\n已执行: ${orderStats.executed}个`">
        <div class="widget-content">
          <Icon icon="mdi:swap-horizontal" class="widget-icon"/>
          <span class="widget-count">{{ orderStats.executed }}/{{ orderStats.pending }}</span>
        </div>
      </div>

      <!-- 风险等级 -->
      <div class="header-widget risk-level" :class="riskLevel.class"
           :title="`当前风险等级: ${riskLevel.text}\n${getRiskDescription(riskLevel.text)}`">
        <div class="widget-content">
          <Icon icon="mdi:shield-check-outline" class="widget-icon"/>
          <span class="widget-count">{{ riskLevel.text }}</span>
        </div>
      </div>
    </div>

    <div class="time-section">
      <div class="current-date">{{ formattedDate }}</div>
      <div class="current-time">{{ formattedTime }}</div>
    </div>

    <div class="user-section">
      <div class="user-dropdown" @click="toggleUserMenu">
        <div class="user-info">
          <div class="user-avatar">
            <Icon icon="mdi:account-circle" class="avatar-icon"/>
          </div>
          <span class="user-name">{{ userName }}</span>
          <Icon icon="mdi:chevron-down" class="dropdown-icon" :class="{ rotated: userMenuOpen }"/>
        </div>

        <div class="user-menu" v-show="userMenuOpen">
          <div class="menu-item" @click="handleCommand('profile')">
            <Icon icon="mdi:account-outline" class="menu-icon"/>
            <span>个人中心</span>
          </div>
          <div class="menu-item" @click="handleCommand('settings')">
            <Icon icon="mdi:cog-outline" class="menu-icon"/>
            <span>系统设置</span>
          </div>
          <div class="menu-divider"></div>
          <div class="menu-item" @click="handleCommand('logout')">
            <Icon icon="mdi:logout" class="menu-icon"/>
            <span>退出登录</span>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Icon } from '@iconify/vue'

export default {
  name: "AppHeader",
  components: {
    Icon
  },
  props: {
    userName: {
      type: String,
      default: "用户"
    }
  },
  setup(props) {
    const router = useRouter();
    const currentTime = ref(new Date());
    const userMenuOpen = ref(false);

    // 策略状态
    const strategyStatus = ref({
      running: 3,
      total: 5,
      health: 'healthy'
    });

    // 信号统计
    const signalStats = ref({
      today: 12,
      triggered: 8
    });

    // 订单统计
    const orderStats = ref({
      pending: 2,
      executed: 15
    });

    // 风险等级
    const riskLevel = computed(() => {
      const levels = {
        low: { class: 'risk-low', text: '低' },
        medium: { class: 'risk-medium', text: '中' },
        high: { class: 'risk-high', text: '高' }
      };
      return levels.medium;
    });

    // 获取健康状态文本
    const getHealthText = (health) => {
      const healthMap = {
        healthy: '正常',
        warning: '警告',
        danger: '危险'
      };
      return healthMap[health] || '未知';
    };

    // 获取风险等级描述
    const getRiskDescription = (riskLevel) => {
      const descriptions = {
        '低': '保守策略，风险可控',
        '中': '平衡策略，适度风险',
        '高': '激进策略，高风险'
      };
      return descriptions[riskLevel] || '风险等级未知';
    };

    // 时间格式化 - 增强版本
    const formattedTime = ref("");
    const formattedDate = ref("");

    // 增强的 toLocaleTimeString 方法
    const formatTime = (date) => {
      try {
        // 优先使用标准的 toLocaleTimeString
        if (date && typeof date.toLocaleTimeString === 'function') {
          return date.toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false
          });
        }
      } catch (error) {
        console.warn('toLocaleTimeString failed, using fallback:', error);
      }

      // 备用方案：手动格式化
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${hours}:${minutes}:${seconds}`;
    };

    // 增强的 toLocaleDateString 方法
    const formatDate = (date) => {
      try {
        // 优先使用标准的 toLocaleDateString
        if (date && typeof date.toLocaleDateString === 'function') {
          return date.toLocaleDateString("zh-CN", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            weekday: "short"
          });
        }
      } catch (error) {
        console.warn('toLocaleDateString failed, using fallback:', error);
      }

      // 备用方案：手动格式化
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
      const weekday = weekdays[date.getDay()];
      return `${year}/${month}/${day} 周${weekday}`;
    };

    // 更新时间显示
    const updateTime = () => {
      currentTime.value = new Date();
      formattedTime.value = formatTime(currentTime.value);
      formattedDate.value = formatDate(currentTime.value);
    };

    // 模拟交易状态更新
    const updateTradingStatus = () => {
      const healthStates = ['healthy', 'warning', 'danger'];
      strategyStatus.value.health = healthStates[Math.floor(Math.random() * 3)];
      signalStats.value.today = Math.max(5, Math.min(20, signalStats.value.today + (Math.random() > 0.5 ? 1 : -1)));
      orderStats.value.pending = Math.max(0, Math.min(5, orderStats.value.pending + (Math.random() > 0.7 ? 1 : -1)));
    };

    // 切换用户菜单
    const toggleUserMenu = () => {
      userMenuOpen.value = !userMenuOpen.value;
    };

    // 点击外部关闭菜单
    const closeUserMenu = (event) => {
      if (!event.target.closest('.user-dropdown')) {
        userMenuOpen.value = false;
      }
    };

    let timeInterval;
    let tradingInterval;

    onMounted(() => {
      updateTime();
      timeInterval = setInterval(updateTime, 1000);
      tradingInterval = setInterval(updateTradingStatus, 10000);
      document.addEventListener('click', closeUserMenu);
    });

    onUnmounted(() => {
      if (timeInterval) clearInterval(timeInterval);
      if (tradingInterval) clearInterval(tradingInterval);
      document.removeEventListener('click', closeUserMenu);
    });

    const handleCommand = (command) => {
      userMenuOpen.value = false;
      if (command === "logout") {
        router.push("/login");
      } else if (command === "settings") {
        router.push("/system/settings");
      } else if (command === "profile") {
        router.push("/user/profile");
      }
    };

    return {
      formattedTime,
      formattedDate,
      strategyStatus,
      signalStats,
      orderStats,
      riskLevel,
      userMenuOpen,
      toggleUserMenu,
      handleCommand,
      getHealthText,
      getRiskDescription,
      userName: props.userName
    };
  },
};
</script>

<style lang="scss" scoped>
// 引入头部专用样式
@use '@/assets/scss/header';
</style>