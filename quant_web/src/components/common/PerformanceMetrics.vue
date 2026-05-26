<script setup lang="ts">
import { computed } from "vue";
import { NStatistic, NGrid, NGridItem } from "naive-ui";

interface PerformanceMetrics {
  responseTime: {
    average: number;
    p95: number;
    p99: number;
    unit: string;
  };
  throughput: {
    requests: number;
    period: string;
    rps: number;
  };
  errorRate: {
    rate: number;
    totalErrors: number;
    totalRequests: number;
  };
  database: {
    queries: number;
    slowQueries: number;
    connectionPool: {
      active: number;
      idle: number;
      total: number;
    };
  };
  cache: {
    hitRate: number;
    size: number;
    unit: string;
  };
}

const props = defineProps<{
  metrics?: PerformanceMetrics;
}>();

const defaultMetrics: PerformanceMetrics = {
  responseTime: { average: 0, p95: 0, p99: 0, unit: "ms" },
  throughput: { requests: 0, period: "-", rps: 0 },
  errorRate: { rate: 0, totalErrors: 0, totalRequests: 0 },
  database: {
    queries: 0,
    slowQueries: 0,
    connectionPool: { active: 0, idle: 0, total: 0 },
  },
  cache: { hitRate: 0, size: 0, unit: "MB" },
};

const safeMetrics = computed(() => props.metrics || defaultMetrics);

const formatNumber = (value: number) => {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + "M";
  if (value >= 1000) return (value / 1000).toFixed(1) + "K";
  return value.toString();
};

const formatPercentage = (value: number) => {
  return (value * 100).toFixed(1) + "%";
};

const getErrorRateStatus = (rate: number) => {
  if (rate < 0.01) return "#67c23a";
  if (rate < 0.05) return "#f0a020";
  return "#d03050";
};

const getResponseTimeStatus = (time: number) => {
  if (time < 100) return "#67c23a";
  if (time < 500) return "#f0a020";
  return "#d03050";
};
</script>

<template>
  <div class="performance-metrics">
    <NGrid :cols="24" :x-gap="16">
      <NGridItem :span="8">
        <div class="metric-card">
          <NStatistic
            label="平均响应时间"
            :value="safeMetrics.responseTime.average"
          >
            <template #suffix>{{ safeMetrics.responseTime.unit }}</template>
          </NStatistic>
          <div class="metric-details">
            <div>
              P95: {{ safeMetrics.responseTime.p95
              }}{{ safeMetrics.responseTime.unit }}
            </div>
            <div>
              P99: {{ safeMetrics.responseTime.p99
              }}{{ safeMetrics.responseTime.unit }}
            </div>
          </div>
        </div>
      </NGridItem>

      <NGridItem :span="8">
        <div class="metric-card">
          <NStatistic label="请求速率" :value="safeMetrics.throughput.rps">
            <template #suffix>req/s</template>
          </NStatistic>
          <div class="metric-details">
            <div>
              总请求: {{ formatNumber(safeMetrics.throughput.requests) }}
            </div>
            <div>周期: {{ safeMetrics.throughput.period }}</div>
          </div>
        </div>
      </NGridItem>

      <NGridItem :span="8">
        <div class="metric-card">
          <NStatistic
            label="错误率"
            :value="(safeMetrics.errorRate.rate * 100).toFixed(1)"
          >
            <template #suffix>%</template>
          </NStatistic>
          <div class="metric-details">
            <div>错误数: {{ safeMetrics.errorRate.totalErrors }}</div>
            <div>
              总请求: {{ formatNumber(safeMetrics.errorRate.totalRequests) }}
            </div>
          </div>
        </div>
      </NGridItem>
    </NGrid>

    <NGrid :cols="24" :x-gap="16" class="metric-row">
      <NGridItem :span="12">
        <div class="metric-card">
          <h4 class="metric-title">数据库</h4>
          <div class="metric-content">
            <div class="metric-item">
              <span class="metric-label">查询次数:</span>
              <span class="metric-value">{{
                formatNumber(safeMetrics.database.queries)
              }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">慢查询:</span>
              <span class="metric-value">{{
                safeMetrics.database.slowQueries
              }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">连接池:</span>
              <span class="metric-value">
                {{ safeMetrics.database.connectionPool.active }}/{{
                  safeMetrics.database.connectionPool.total
                }}
              </span>
            </div>
          </div>
        </div>
      </NGridItem>

      <NGridItem :span="12">
        <div class="metric-card">
          <h4 class="metric-title">缓存</h4>
          <div class="metric-content">
            <div class="metric-item">
              <span class="metric-label">命中率:</span>
              <span class="metric-value">{{
                formatPercentage(safeMetrics.cache.hitRate)
              }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">缓存大小:</span>
              <span class="metric-value">
                {{ formatNumber(safeMetrics.cache.size) }}
                {{ safeMetrics.cache.unit }}
              </span>
            </div>
          </div>
        </div>
      </NGridItem>
    </NGrid>

    <div class="additional-metrics">
      <h4>实时指标</h4>
      <NGrid :cols="24" :x-gap="16">
        <NGridItem :span="6">
          <div class="mini-metric">
            <div class="mini-value">12.5K</div>
            <div class="mini-label">活跃连接</div>
          </div>
        </NGridItem>
        <NGridItem :span="6">
          <div class="mini-metric">
            <div class="mini-value">98.2%</div>
            <div class="mini-label">服务可用性</div>
          </div>
        </NGridItem>
        <NGridItem :span="6">
          <div class="mini-metric">
            <div class="mini-value">45</div>
            <div class="mini-label">活跃策略</div>
          </div>
        </NGridItem>
        <NGridItem :span="6">
          <div class="mini-metric">
            <div class="mini-value">1.2M</div>
            <div class="mini-label">数据处理</div>
          </div>
        </NGridItem>
      </NGrid>
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
  background: var(--n-card-color);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--n-border-color);
}

.metric-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--n-text-color-1);
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
  color: var(--n-text-color-3);
}

.metric-value {
  color: var(--n-text-color-1);
  font-weight: 500;
  font-family: "Courier New", monospace;
}

.metric-details {
  margin-top: 8px;
  font-size: 11px;
  color: var(--n-text-color-3);
}

.metric-details div {
  margin-bottom: 2px;
}

.additional-metrics {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--n-border-color);
}

.additional-metrics h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--n-text-color-1);
  font-weight: 500;
}

.mini-metric {
  text-align: center;
  padding: 8px;
  background: var(--n-color-embedded);
  border-radius: 4px;
}

.mini-value {
  font-size: 18px;
  font-weight: bold;
  color: var(--n-color-target);
  font-family: "Courier New", monospace;
}

.mini-label {
  font-size: 11px;
  color: var(--n-text-color-3);
  margin-top: 4px;
}
</style>
