<!--风险矩阵-->
<!-- src/components/events/RiskMatrix.vue -->
<template>
  <div class="risk-matrix">
    <div class="header">
      <h2><i class="fas fa-shield-alt"></i> 风险控制矩阵</h2>
      <div class="last-update">更新于: {{ lastUpdate }}</div>
    </div>

    <div class="metrics-grid">
      <div
        v-for="metric in metrics"
        :key="metric.name"
        class="metric"
        :class="metric.status"
      >
        <div class="metric-header">
          <i :class="metric.icon"></i>
          <div class="name">{{ metric.name }}</div>
          <div class="threshold">阈值: {{ metric.threshold }}</div>
        </div>

        <div class="value-container">
          <div class="value">{{ metric.value }}</div>
          <div class="trend" :class="metric.trend">
            <i v-if="metric.trend === 'up'" class="fas fa-arrow-up"></i>
            <i
              v-else-if="metric.trend === 'down'"
              class="fas fa-arrow-down"
            ></i>
            <span v-if="metric.trendChange">{{ metric.trendChange }}</span>
          </div>
        </div>

        <div class="progress-container">
          <div class="progress-label">
            <span>0%</span>
            <span>{{ metric.threshold }}</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress"
              :style="{ width: metric.percentage + '%' }"
              :class="metric.status"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <div class="risk-summary">
      <div class="summary-item">
        <div class="label">风险等级</div>
        <div class="value level-2">中等风险</div>
      </div>
      <div class="summary-item">
        <div class="label">建议操作</div>
        <div class="value">监控仓位，调整高波动资产</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "RiskMatrix",
  data() {
    return {
      lastUpdate: this.getCurrentTime(),
      metrics: [
        {
          name: "总回撤",
          value: "-5.2%",
          threshold: "-10%",
          percentage: 52,
          status: "warning",
          icon: "fas fa-chart-line",
          trend: "down",
          trendChange: "0.3%",
        },
        {
          name: "当日亏损",
          value: "-2.1%",
          threshold: "-5%",
          percentage: 42,
          status: "normal",
          icon: "fas fa-calendar-day",
          trend: "down",
          trendChange: "0.1%",
        },
        {
          name: "单股仓位",
          value: "18.3%",
          threshold: "20%",
          percentage: 91.5,
          status: "normal",
          icon: "fas fa-chart-pie",
          trend: "up",
          trendChange: "0.5%",
        },
        {
          name: "ST股比例",
          value: "0%",
          threshold: "0%",
          percentage: 0,
          status: "normal",
          icon: "fas fa-exclamation-triangle",
          trend: null,
          trendChange: null,
        },
        {
          name: "策略相关性",
          value: "0.42",
          threshold: "<0.6",
          percentage: 70,
          status: "normal",
          icon: "fas fa-link",
          trend: "down",
          trendChange: "0.02",
        },
        {
          name: "组合波动率",
          value: "12.8%",
          threshold: "15%",
          percentage: 85.3,
          status: "warning",
          icon: "fas fa-bullseye",
          trend: "up",
          trendChange: "0.7%",
        },
      ],
    };
  },
  methods: {
    getCurrentTime() {
      const now = new Date();
      return now.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    },
    updateMetrics() {
      // 模拟数据更新
      this.metrics.forEach((metric) => {
        if (metric.trend) {
          const change = Math.random() * 0.5;
          metric.trendChange =
            change.toFixed(metric.name === "策略相关性" ? 2 : 1) +
            (metric.name === "策略相关性" ? "" : "%");
        }
      });

      this.lastUpdate = this.getCurrentTime();
    },
  },
  mounted() {
    // 每10秒更新一次风险指标
    this.interval = setInterval(this.updateMetrics, 10000);
  },
  beforeDestroy() {
    clearInterval(this.interval);
  },
};
</script>

<style scoped>
.risk-matrix {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  font-size: 1.5rem;
  color: #64b5f6;
  display: flex;
  align-items: center;
  gap: 10px;
}

.last-update {
  color: #a8c7ff;
  font-size: 0.9rem;
  background: rgba(24, 50, 90, 0.5);
  padding: 5px 10px;
  border-radius: 4px;
}

.metrics-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}

.metric {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  display: flex;
  flex-direction: column;
  transition: all 0.3s;
}

.metric:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.metric.normal {
  border-left: 4px solid #5cdd8b;
}

.metric.warning {
  border-left: 4px solid #ffb86c;
  animation: pulse 2s infinite;
}

.metric.critical {
  border-left: 4px solid #ff6b6b;
  animation: pulse 0.5s infinite;
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}

.metric-header i {
  font-size: 1.2rem;
  color: #409eff;
}

.metric-header .name {
  flex: 1;
  font-weight: 600;
  color: #e0e7ff;
}

.metric-header .threshold {
  font-size: 0.85rem;
  color: #a8c7ff;
}

.value-container {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  margin-bottom: 10px;
}

.value {
  font-size: 1.8rem;
  font-weight: 700;
}

.metric.normal .value {
  color: #5cdd8b;
}

.metric.warning .value {
  color: #ffb86c;
}

.metric.critical .value {
  color: #ff6b6b;
}

.trend {
  display: flex;
  align-items: center;
  font-size: 0.9rem;
  padding-bottom: 5px;
}

.trend.up {
  color: #5cdd8b;
}

.trend.down {
  color: #ff6b6b;
}

.progress-container {
  margin-top: 10px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #a8c7ff;
  margin-bottom: 3px;
}

.progress-bar {
  height: 8px;
  background: rgba(16, 33, 59, 0.7);
  border-radius: 4px;
  overflow: hidden;
}

.progress {
  height: 100%;
  border-radius: 4px;
}

.metric.normal .progress {
  background: #5cdd8b;
}

.metric.warning .progress {
  background: #ffb86c;
}

.metric.critical .progress {
  background: #ff6b6b;
}

.risk-summary {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 15px;
  margin-top: 20px;
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.summary-item {
  display: flex;
  flex-direction: column;
}

.summary-item .label {
  color: #a8c7ff;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.summary-item .value {
  font-weight: 600;
  font-size: 1.1rem;
}

.level-1 {
  color: #5cdd8b;
}

.level-2 {
  color: #ffb86c;
}

.level-3 {
  color: #ff6b6b;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
  100% {
    opacity: 1;
  }
}

@media (max-width: 1200px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .risk-summary {
    grid-template-columns: 1fr;
  }
}
</style>
