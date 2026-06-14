<!--系统监控-->
<template>
  <div class="system-monitor bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">系统监控</h1>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- 健康指标卡片 -->
      <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen" class="health-grid">
        <n-grid-item v-for="stat in healthStats" :key="stat.label">
          <n-card size="small" class="health-card">
            <n-statistic :label="stat.label" :value="stat.value">
              <template #prefix>
                <Icon :icon="stat.icon" :style="{ color: stat.color }" />
              </template>
            </n-statistic>
            <n-progress
              :percentage="stat.percent"
              :color="stat.color"
              :height="4"
              :border-radius="2"
              :show-indicator="false"
              style="margin-top: 8px"
            />
          </n-card>
        </n-grid-item>
      </n-grid>

      <!-- 最后刷新时间 -->
      <div class="refresh-bar">
        <span class="refresh-time">最后刷新: {{ lastRefresh }}</span>
      </div>

      <n-result
        v-if="error"
        status="500"
        title="加载失败"
        description="获取监控数据失败"
        class="monitor-error"
      >
        <template #footer
          ><n-button @click="refreshData">重试</n-button></template
        >
      </n-result>

      <n-spin v-else :show="loading">
        <n-grid
          :x-gap="20"
          :y-gap="20"
          :cols="3"
          responsive="screen"
          class="monitor-grid"
        >
          <n-grid-item>
            <n-card title="连接状态" class="monitor-card">
              <ConnectionStatus :connections="connections" />
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card title="资源使用" class="monitor-card">
              <ResourceUsage :resources="resources" />
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card title="策略状态" class="monitor-card">
              <StrategyStatus :strategies="runningStrategies" />
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-grid
          :x-gap="20"
          :y-gap="20"
          :cols="2"
          responsive="screen"
          class="monitor-grid"
        >
          <n-grid-item>
            <n-card title="实时日志" class="monitor-card">
              <template #header-extra>
                <n-button text size="small" @click="clearLogs">清空</n-button>
              </template>
              <SystemLogs :logs="logs" />
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card title="性能指标" class="monitor-card">
              <PerformanceMetrics :metrics="performanceMetrics" />
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-spin>
    </div>
    <!-- .main-content -->
  </div>
</template>

<script>
import { mapState, mapActions } from "vuex";
import ConnectionStatus from "@/components/common/ConnectionStatus.vue";
import ResourceUsage from "@/components/common/ResourceUsage.vue";
import StrategyStatus from "@/components/common/StrategyStatus.vue";
import SystemLogs from "@/components/common/SystemLogs.vue";
import PerformanceMetrics from "@/components/common/PerformanceMetrics.vue";

export default {
  components: {
    ConnectionStatus,
    ResourceUsage,
    StrategyStatus,
    SystemLogs,
    PerformanceMetrics,
  },

  data() {
    return {
      loading: false,
      error: false,
      lastRefresh: "--:--:--",
      healthStats: [
        { label: "CPU", value: "--%", percent: 0, icon: "mdi:cpu-64-bit", color: "#22C55E" },
        { label: "内存", value: "--%", percent: 0, icon: "mdi:memory", color: "#3B82F6" },
        { label: "磁盘", value: "--%", percent: 0, icon: "mdi:harddisk", color: "#F59E0B" },
        { label: "数据库", value: "--ms", percent: 0, icon: "mdi:database", color: "#7C3AED" },
      ],
    };
  },

  computed: {
    ...mapState("system", [
      "connections",
      "resources",
      "logs",
      "performanceMetrics",
    ]),
    ...mapState("strategy", ["runningStrategies"]),
  },

  methods: {
    ...mapActions("system", ["clearLogs", "startMonitoring"]),

    async refreshData() {
      this.loading = true;
      this.error = false;
      try {
        await this.startMonitoring();
        await this.$store.dispatch("strategy/fetchRunningStrategies");

        // 更新健康指标（从 resources/performanceMetrics state 中读取）
        const res = this.resources || {};
        const perf = this.performanceMetrics || {};
        this.healthStats = [
          { label: "CPU", value: res.cpu || "--%", percent: parseInt(res.cpu) || 0, icon: "mdi:cpu-64-bit", color: "#22C55E" },
          { label: "内存", value: res.memory || "--%", percent: parseInt(res.memory) || 0, icon: "mdi:memory", color: "#3B82F6" },
          { label: "磁盘", value: res.disk || "--%", percent: parseInt(res.disk) || 0, icon: "mdi:harddisk", color: "#F59E0B" },
          { label: "数据库", value: perf.db_response || "--ms", percent: Math.min((parseInt(perf.db_response) || 0) / 10, 100), icon: "mdi:database", color: "#7C3AED" },
        ];
        this.lastRefresh = new Date().toLocaleTimeString("zh-CN");
      } catch {
        this.error = true;
      } finally {
        this.loading = false;
      }
    },
  },

  async mounted() {
    await this.refreshData();

    this.refreshInterval = setInterval(() => {
      this.refreshData();
    }, 30000);
  },

  beforeDestroy() {
    clearInterval(this.refreshInterval);
  },
};
</script>

<style scoped>
.system-monitor {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.monitor-grid {
  margin-bottom: 20px;
}

.monitor-card {
  height: 100%;
}
</style>
