<script setup lang="ts">
import { computed } from 'vue'
import { ElStatistic, ElRow, ElCol } from 'element-plus'

interface PerformanceMetrics {
  responseTime: {
    average: number
    p95: number
    p99: number
    unit: string
  }
  throughput: {
    requests: number
    period: string
    rps: number
  }
  errorRate: {
    rate: number
    totalErrors: number
    totalRequests: number
  }
  database: {
    queries: number
    slowQueries: number
    connectionPool: {
      active: number
      idle: number
      total: number
    }
  }
  cache: {
    hitRate: number
    size: number
    unit: string
  }
}

const props = defineProps<{
  metrics?: PerformanceMetrics
}>()

// 提供默认值
const defaultMetrics: PerformanceMetrics = {
  responseTime: {
    average: 0,
    p95: 0,
    p99: 0,
    unit: 'ms'
  },
  throughput: {
    requests: 0,
    period: '-',
    rps: 0
  },
  errorRate: {
    rate: 0,
    totalErrors: 0,
    totalRequests: 0
  },
  database: {
    queries: 0,
    slowQueries: 0,
    connectionPool: {
      active: 0,
      idle: 0,
      total: 0
    }
  },
  cache: {
    hitRate: 0,
    size: 0,
    unit: 'MB'
  }
}

// 使用计算属性确保始终有值
const safeMetrics = computed(() => props.metrics || defaultMetrics)

const formatNumber = (value: number) => {
  if (value >= 1000000) {
    return (value / 1000000).toFixed(1) + 'M'
  }
  if (value >= 1000) {
    return (value / 1000).toFixed(1) + 'K'
  }
  return value.toString()
}

const formatPercentage = (value: number) => {
  return (value * 100).toFixed(1) + '%'
}

const getErrorRateStatus = (rate: number) => {
  if (rate < 0.01) return 'success'
  if (rate < 0.05) return 'warning'
  return 'danger'
}

const getResponseTimeStatus = (time: number) => {
  if (time < 100) return 'success'
  if (time < 500) return 'warning'
  return 'danger'
}
</script>

<template>
  <div class="performance-metrics">
    <ElRow :gutter="16">
      <!-- Response Time -->
      <ElCol :span="8">
        <div class="metric-card">
          <ElStatistic
            title="平均响应时间"
            :value="safeMetrics.responseTime.average"
            :suffix="safeMetrics.responseTime.unit"
            :value-style="{
              color: getResponseTimeStatus(safeMetrics.responseTime.average) === 'success' ? '#67c23a' :
                     getResponseTimeStatus(safeMetrics.responseTime.average) === 'warning' ? '#e6a23c' : '#f56c6c'
            }"
          />
          <div class="metric-details">
            <div>P95: {{ safeMetrics.responseTime.p95 }}{{ safeMetrics.responseTime.unit }}</div>
            <div>P99: {{ safeMetrics.responseTime.p99 }}{{ safeMetrics.responseTime.unit }}</div>
          </div>
        </div>
      </ElCol>

      <!-- Throughput -->
      <ElCol :span="8">
        <div class="metric-card">
          <ElStatistic
            title="请求速率"
            :value="safeMetrics.throughput.rps"
            suffix="req/s"
          />
          <div class="metric-details">
            <div>总请求: {{ formatNumber(safeMetrics.throughput.requests) }}</div>
            <div>周期: {{ safeMetrics.throughput.period }}</div>
          </div>
        </div>
      </ElCol>

      <!-- Error Rate -->
      <ElCol :span="8">
        <div class="metric-card">
          <ElStatistic
            title="错误率"
            :value="safeMetrics.errorRate.rate * 100"
            prefix=""
            suffix="%"
            :value-style="{
              color: getErrorRateStatus(safeMetrics.errorRate.rate) === 'success' ? '#67c23a' :
                     getErrorRateStatus(safeMetrics.errorRate.rate) === 'warning' ? '#e6a23c' : '#f56c6c'
            }"
          />
          <div class="metric-details">
            <div>错误数: {{ safeMetrics.errorRate.totalErrors }}</div>
            <div>总请求: {{ formatNumber(safeMetrics.errorRate.totalRequests) }}</div>
          </div>
        </div>
      </ElCol>
    </ElRow>

    <ElRow :gutter="16" class="metric-row">
      <!-- Database -->
      <ElCol :span="12">
        <div class="metric-card">
          <h4 class="metric-title">数据库</h4>
          <div class="metric-content">
            <div class="metric-item">
              <span class="metric-label">查询次数:</span>
              <span class="metric-value">{{ formatNumber(safeMetrics.database.queries) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">慢查询:</span>
              <span class="metric-value">{{ safeMetrics.database.slowQueries }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">连接池:</span>
              <span class="metric-value">
                {{ safeMetrics.database.connectionPool.active }}/{{ safeMetrics.database.connectionPool.total }}
              </span>
            </div>
          </div>
        </div>
      </ElCol>

      <!-- Cache -->
      <ElCol :span="12">
        <div class="metric-card">
          <h4 class="metric-title">缓存</h4>
          <div class="metric-content">
            <div class="metric-item">
              <span class="metric-label">命中率:</span>
              <span class="metric-value">{{ formatPercentage(safeMetrics.cache.hitRate) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">缓存大小:</span>
              <span class="metric-value">
                {{ formatNumber(safeMetrics.cache.size) }} {{ safeMetrics.cache.unit }}
              </span>
            </div>
          </div>
        </div>
      </ElCol>
    </ElRow>

    <!-- Additional Metrics -->
    <div class="additional-metrics">
      <h4>实时指标</h4>
      <ElRow :gutter="16">
        <ElCol :span="6">
          <div class="mini-metric">
            <div class="mini-value">12.5K</div>
            <div class="mini-label">活跃连接</div>
          </div>
        </ElCol>
        <ElCol :span="6">
          <div class="mini-metric">
            <div class="mini-value">98.2%</div>
            <div class="mini-label">服务可用性</div>
          </div>
        </ElCol>
        <ElCol :span="6">
          <div class="mini-metric">
            <div class="mini-value">45</div>
            <div class="mini-label">活跃策略</div>
          </div>
        </ElCol>
        <ElCol :span="6">
          <div class="mini-metric">
            <div class="mini-value">1.2M</div>
            <div class="mini-label">数据处理</div>
          </div>
        </ElCol>
      </ElRow>
    </div>
  </div>
</template>

<style scoped>
.performance-metrics {
  padding: 8px 0;
}

.metric-row {
  margin-top: 16px;
}

.metric-card {
  background: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.metric-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.metric-content {
  font-size: 12px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.metric-label {
  color: #666;
}

.metric-value {
  color: #333;
  font-weight: 500;
  font-family: 'Courier New', monospace;
}

.metric-details {
  margin-top: 8px;
  font-size: 11px;
  color: #666;
}

.metric-details div {
  margin-bottom: 2px;
}

.additional-metrics {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e8e8e8;
}

.additional-metrics h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.mini-metric {
  text-align: center;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.mini-value {
  font-size: 18px;
  font-weight: bold;
  color: #409EFF;
  font-family: 'Courier New', monospace;
}

.mini-label {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}

:deep(.el-statistic__content) {
  justify-content: center;
}

:deep(.el-statistic__number) {
  font-size: 24px;
}
</style>