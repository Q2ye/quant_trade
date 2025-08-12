<template>
  <div id="app" class="app-container">
    <!-- 主框架布局 -->
    <MainLayout
      v-if="!isReportView"
      :active-menu="activeMenu"
      @menu-change="handleMenuChange"
    >
      <!-- 策略工作室特殊布局 -->
      <StrategyLayout v-if="isStrategyEditor">
        <router-view />
      </StrategyLayout>

      <!-- 交易驾驶舱特殊布局 -->
      <TradeLayout v-else-if="isTradeDashboard">
        <router-view />
      </TradeLayout>

      <!-- 默认布局 -->
      <div v-else class="default-layout">
        <router-view />
      </div>
    </MainLayout>

    <!-- 回测报告专用布局 -->
    <ReportLayout
      v-else
      :report-data="reportData"
      @go-back="exitReportView"
    >
      <router-view />
    </ReportLayout>
  </div>
</template>

<script>
import MainLayout from './layouts/MainLayout.vue';
import ReportLayout from './layouts/ReportLayout.vue';
import StrategyLayout from './layouts/StrategyLayout.vue';
import TradeLayout from './layouts/TradeLayout.vue';

export default {
  name: 'App',
  components: {
    MainLayout,
    ReportLayout,
    StrategyLayout,
    TradeLayout
  },
  data() {
    return {
      activeMenu: 'market',
      isReportView: false,
      reportData: {}
    };
  },
  computed: {
    // 检查当前是否是策略编辑视图
    isStrategyEditor() {
      return this.$route.path.includes('/strategy/editor');
    },
    // 检查当前是否是交易驾驶舱视图
    isTradeDashboard() {
      return this.$route.path === '/trade';
    }
  },
  watch: {
    $route(to) {
      // 根据路由更新激活菜单
      this.activeMenu = to.meta?.menu || 'market';

      // 检查是否是回测报告视图
      this.isReportView = to.path.includes('/backtest/report');

      // 如果是报告视图，加载报告数据
      if (this.isReportView) {
        this.loadReportData(to.params.reportId);
      }
    }
  },
  methods: {
    handleMenuChange(menuId) {
      this.activeMenu = menuId;
      // 根据菜单ID导航到对应路由
      const routes = {
        market: '/market',
        strategy: '/strategy',
        basket: '/basket',
        trade: '/trade',
        system: '/system'
      };
      if (routes[menuId] && this.$route.path !== routes[menuId]) {
        this.$router.push(routes[menuId]);
      }
    },

    loadReportData(reportId) {
      // 模拟加载报告数据
      this.reportData = {
        title: `策略回测报告 #${reportId}`,
        strategy: '双均线策略',
        startDate: '2023-01-01',
        endDate: '2023-08-01',
        capital: 1000000
      };
    },

    exitReportView() {
      this.isReportView = false;
      this.$router.push('/strategy');
    }
  }
};
</script>

<style lang="scss">
@import "./assets/scss/global.scss";

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background-color: $background-dark;
  color: $text-primary;
}

#app {
  height: 100vh;
  overflow: hidden;
}

.app-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.default-layout {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}
</style>