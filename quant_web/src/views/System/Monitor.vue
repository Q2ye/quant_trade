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
          <n-card size="small" :class="['health-card', tokens.surface.card]">
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

      <div class="refresh-bar">
        <span class="refresh-time">最后刷新: {{ lastRefresh }}</span>
        <n-button text size="small" @click="refreshData">刷新</n-button>
      </div>

      <!-- 错误状态 -->
      <n-result
        v-if="error"
        status="500"
        title="加载失败"
        description="获取监控数据失败"
        class="monitor-error"
      >
        <template #footer>
          <n-button @click="refreshData">重试</n-button>
        </template>
      </n-result>

      <!-- 加载状态 -->
      <n-spin v-else-if="loading && !hasData" :show="true">
        <div style="height: 400px" />
      </n-spin>

      <!-- 空状态 -->
      <n-empty
        v-else-if="!loading && !error && !hasData"
        description="暂无监控数据，请稍后刷新"
        style="margin-top: 60px"
      />

      <!-- 内容 -->
      <template v-else>
        <n-grid
          :x-gap="20"
          :y-gap="20"
          :cols="3"
          responsive="screen"
          class="monitor-grid"
        >
          <n-grid-item>
            <n-card title="连接状态" :class="tokens.surface.card">
              <div v-if="connectionStatus" class="status-grid">
                <div class="status-item">
                  <n-tag :type="connectionStatus.database ? 'success' : 'error'" round>
                    数据库
                  </n-tag>
                  <span class="status-label">{{ connectionStatus.database ? '已连接' : '断开' }}</span>
                </div>
                <div class="status-item">
                  <n-tag :type="connectionStatus.redis ? 'success' : 'error'" round>
                    Redis
                  </n-tag>
                  <span class="status-label">{{ connectionStatus.redis ? '已连接' : '断开' }}</span>
                </div>
                <div class="status-item">
                  <n-tag :type="connectionStatus.tushare ? 'success' : 'warning'" round>
                    Tushare
                  </n-tag>
                  <span class="status-label">{{ connectionStatus.tushare ? '已配置' : '未配置' }}</span>
                </div>
                <div class="status-item">
                  <n-tag :type="connectionStatus.broker ? 'success' : 'warning'" round>
                    交易网关
                  </n-tag>
                  <span class="status-label">{{ connectionStatus.broker || '模拟模式' }}</span>
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card title="资源使用" :class="tokens.surface.card">
              <div v-if="resourceUsage" class="resource-grid">
                <div class="resource-item">
                  <span class="resource-label">CPU</span>
                  <n-progress
                    type="circle"
                    :percentage="resourceUsage.cpu_percent || 0"
                    :color="cpuColor"
                    size="80"
                    stroke-width="8"
                  />
                </div>
                <div class="resource-item">
                  <span class="resource-label">内存</span>
                  <n-progress
                    type="circle"
                    :percentage="resourceUsage.memory_percent || 0"
                    :color="memColor"
                    size="80"
                    stroke-width="8"
                  />
                </div>
                <div class="resource-item">
                  <span class="resource-label">磁盘</span>
                  <n-progress
                    type="circle"
                    :percentage="resourceUsage.disk_usage || 0"
                    color="#F59E0B"
                    size="80"
                    stroke-width="8"
                  />
                </div>
              </div>
              <n-empty v-else description="资源数据不可用" size="small" />
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card title="系统信息" :class="tokens.surface.card">
              <div v-if="systemStatus" class="info-list">
                <div class="info-item">
                  <span class="info-label">版本</span>
                  <span class="info-value">{{ systemStatus.version || '--' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">运行时间</span>
                  <span class="info-value">{{ systemStatus.uptime || '--' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">活跃用户</span>
                  <span class="info-value">{{ systemStatus.users?.active || 0 }}</span>
                </div>
                <div v-if="dbStatus" class="info-item">
                  <span class="info-label">数据库表数</span>
                  <span class="info-value">{{ dbStatus.total_tables || 0 }}</span>
                </div>
                <div v-if="dbStatus" class="info-item">
                  <span class="info-label">股票数据</span>
                  <span class="info-value">{{ dbStatus.stock_data_count?.toLocaleString() || 0 }}</span>
                </div>
              </div>
              <n-empty v-else description="暂无系统信息" size="small" />
            </n-card>
          </n-grid-item>
        </n-grid>
      </template>
    </div>
  </div>
</template>

<script>
import { tokens } from "@/styles/design-tokens"
import systemAPI from "@/api/system"

export default {
  setup() {
    return { tokens }
  },

  data() {
    return {
      loading: false,
      error: false,
      lastRefresh: "--:--:--",
      connectionStatus: null,
      resourceUsage: null,
      systemStatus: null,
      dbStatus: null,
    }
  },

  computed: {
    hasData() {
      return this.connectionStatus || this.resourceUsage || this.systemStatus
    },
    healthStats() {
      const res = this.resourceUsage || {}
      return [
        {
          label: "CPU",
          value: res.cpu_percent != null ? `${res.cpu_percent}%` : "--%",
          percent: res.cpu_percent || 0,
          icon: "mdi:cpu-64-bit",
          color: this.cpuColor,
        },
        {
          label: "内存",
          value: res.memory_percent != null ? `${res.memory_percent}%` : "--%",
          percent: res.memory_percent || 0,
          icon: "mdi:memory",
          color: this.memColor,
        },
        {
          label: "磁盘",
          value: res.disk_usage != null ? `${res.disk_usage}%` : "--%",
          percent: res.disk_usage || 0,
          icon: "mdi:harddisk",
          color: "#F59E0B",
        },
        {
          label: "数据库",
          value: this.dbStatus?.active_connections != null
            ? `${this.dbStatus.active_connections} 连接`
            : "--",
          percent: Math.min((this.dbStatus?.active_connections || 0) * 5, 100),
          icon: "mdi:database",
          color: "#7C3AED",
        },
      ]
    },
    cpuColor() {
      const p = this.resourceUsage?.cpu_percent || 0
      return p > 80 ? "#EF4444" : p > 50 ? "#F59E0B" : "#22C55E"
    },
    memColor() {
      const p = this.resourceUsage?.memory_percent || 0
      return p > 80 ? "#EF4444" : p > 50 ? "#F59E0B" : "#3B82F6"
    },
  },

  methods: {
    async refreshData() {
      this.loading = true
      this.error = false
      try {
        // 并行请求所有数据（防御式：单个失败不影响其他）
        const [connRes, resRes, sysRes, dbRes] = await Promise.all([
          systemAPI.getConnections().catch(() => null),
          systemAPI.getResources().catch(() => null),
          systemAPI.getSystemStatus().catch(() => null),
          systemAPI.getDatabaseStatus().catch(() => null),
        ])

        this.connectionStatus = connRes
        this.resourceUsage = resRes
        this.systemStatus = sysRes
        this.dbStatus = dbRes
        this.lastRefresh = new Date().toLocaleTimeString("zh-CN")
      } catch {
        this.error = true
      } finally {
        this.loading = false
      }
    },
  },

  async mounted() {
    await this.refreshData()
    this._timer = setInterval(() => this.refreshData(), 30000)
  },

  beforeUnmount() {
    clearInterval(this._timer)
  },
}
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

.refresh-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 0 4px;
}

.refresh-time {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-label {
  font-size: 13px;
  color: var(--n-text-color-2);
}

.resource-grid {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 8px 0;
}

.resource-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.resource-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 13px;
  color: var(--n-text-color-3);
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--n-text-color-1);
}
</style>
