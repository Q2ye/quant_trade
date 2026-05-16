<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useWebSocket } from "@/composables/useWebSocket";

const { subscribe, unsubscribe } = useWebSocket();

interface RiskData {
  totalRisk: number;
  positionRisks: Array<{
    symbol: string;
    name: string;
    risk: number;
    exposure: number;
  }>;
  warnings: Array<{
    type: string;
    message: string;
    level: "low" | "medium" | "high";
  }>;
}

const riskData = ref<RiskData>({
  totalRisk: 0,
  positionRisks: [],
  warnings: [],
});

onMounted(() => {
  subscribe(["risk_updates"], (data: any) => {
    riskData.value = data;
  });
});

onUnmounted(() => {
  unsubscribe(["risk_updates"]);
});

const getRiskLevel = (risk: number) => {
  if (risk < 0.3) return "low";
  if (risk < 0.7) return "medium";
  return "high";
};

const getWarningColor = (level: string) => {
  switch (level) {
    case "low":
      return "#67c23a";
    case "medium":
      return "#e6a23c";
    case "high":
      return "#f56c6c";
    default:
      return "#909399";
  }
};
</script>

<template>
  <div class="risk-overview">
    <div class="header">
      <h3>风险概览</h3>
      <div class="total-risk" :class="getRiskLevel(riskData.totalRisk)">
        总体风险: {{ (riskData.totalRisk * 100).toFixed(1) }}%
      </div>
    </div>

    <div class="risk-content">
      <!-- 风险警告 -->
      <div class="warnings-section">
        <h4>风险警告</h4>
        <div class="warnings-list">
          <div
            v-for="(warning, index) in riskData.warnings"
            :key="index"
            class="warning-item"
            :style="{ borderLeftColor: getWarningColor(warning.level) }"
          >
            <span
              class="level"
              :style="{ color: getWarningColor(warning.level) }"
            >
              {{ warning.level.toUpperCase() }}
            </span>
            <span class="message">{{ warning.message }}</span>
          </div>
        </div>
      </div>

      <!-- 持仓风险 -->
      <div class="positions-section">
        <h4>持仓风险</h4>
        <div class="positions-list">
          <div
            v-for="position in riskData.positionRisks"
            :key="position.symbol"
            class="position-item"
          >
            <div class="stock-info">
              <span class="symbol">{{ position.symbol }}</span>
              <span class="name">{{ position.name }}</span>
            </div>
            <div class="risk-info">
              <span class="exposure"
                >暴露: {{ (position.exposure * 100).toFixed(1) }}%</span
              >
              <div class="risk-bar">
                <div
                  class="risk-fill"
                  :style="{ width: position.risk * 100 + '%' }"
                  :class="getRiskLevel(position.risk)"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-overview {
  background: var(--n-body-color);
  border-radius: 8px;
  padding: 16px;
  height: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.total-risk {
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
}

.total-risk.low {
  background: #f0f9ff;
  color: #409eff;
}
.total-risk.medium {
  background: #fdf6ec;
  color: #e6a23c;
}
.total-risk.high {
  background: #fef0f0;
  color: #f56c6c;
}

.risk-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.warnings-section h4,
.positions-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--n-text-color-1);
}

.warning-item {
  background: var(--n-color-embedded);
  border-left: 3px solid;
  padding: 8px 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.level {
  font-size: 11px;
  font-weight: bold;
  text-transform: uppercase;
}

.message {
  font-size: 12px;
  flex: 1;
}

.position-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--n-border-color);
}

.stock-info {
  display: flex;
  flex-direction: column;
}

.symbol {
  font-weight: bold;
  font-size: 12px;
}

.name {
  font-size: 11px;
  color: var(--n-text-color-3);
}

.risk-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.exposure {
  font-size: 11px;
  color: var(--n-text-color-3);
}

.risk-bar {
  width: 60px;
  height: 4px;
  background: var(--n-border-color);
  border-radius: 2px;
  overflow: hidden;
}

.risk-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.risk-fill.low {
  background: #67c23a;
}
.risk-fill.medium {
  background: #e6a23c;
}
.risk-fill.high {
  background: #f56c6c;
}
</style>
