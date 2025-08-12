<!--系统监控-->
<template>
  <div class="system-monitor">
    <h2>系统监控</h2>

    <el-row :gutter="20" class="monitor-row">
      <el-col :span="8">
        <el-card class="monitor-card">
          <div slot="header" class="clearfix">
            <span>连接状态</span>
          </div>
          <ConnectionStatus :connections="connections" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="monitor-card">
          <div slot="header" class="clearfix">
            <span>资源使用</span>
          </div>
          <ResourceUsage :resources="resources" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="monitor-card">
          <div slot="header" class="clearfix">
            <span>策略状态</span>
          </div>
          <StrategyStatus :strategies="runningStrategies" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="monitor-row">
      <el-col :span="12">
        <el-card class="monitor-card">
          <div slot="header" class="clearfix">
            <span>实时日志</span>
            <el-button
              style="float: right; padding: 3px 0"
              type="text"
              @click="clearLogs"
            >
              清空
            </el-button>
          </div>
          <SystemLogs :logs="logs" />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="monitor-card">
          <div slot="header" class="clearfix">
            <span>性能指标</span>
          </div>
          <PerformanceMetrics :metrics="performanceMetrics" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex'
import ConnectionStatus from '@/components/system/ConnectionStatus.vue'
import ResourceUsage from '@/components/system/ResourceUsage.vue'
import StrategyStatus from '@/components/system/StrategyStatus.vue'
import SystemLogs from '@/components/system/SystemLogs.vue'
import PerformanceMetrics from '@/components/system/PerformanceMetrics.vue'

export default {
  components: {
    ConnectionStatus,
    ResourceUsage,
    StrategyStatus,
    SystemLogs,
    PerformanceMetrics
  },

  computed: {
    ...mapState('system', [
      'connections',
      'resources',
      'logs',
      'performanceMetrics'
    ]),
    ...mapState('strategy', ['runningStrategies'])
  },

  methods: {
    ...mapActions('system', ['clearLogs', 'startMonitoring']),

    refreshData() {
      this.startMonitoring()
    }
  },

  mounted() {
    this.startMonitoring()
    this.$store.dispatch('strategy/fetchRunningStrategies')

    // 每30秒刷新一次
    this.refreshInterval = setInterval(() => {
      this.refreshData()
    }, 30000)
  },

  beforeDestroy() {
    clearInterval(this.refreshInterval)
  }
}
</script>

<style scoped>
.system-monitor {
  padding: 20px;
}

.monitor-row {
  margin-bottom: 20px;
}

.monitor-card {
  height: 100%;
}
</style>