<!--
  StrategyHealth.vue — 策略健康度监控
  路由: /monitor/strategies-health
  数据源: GET /quantTrade/monitor/strategies/health（基建设计 §三）
-->
<template>
  <div class="strategy-health-page bg-gradient-mesh bg-noise">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略健康</h1>
          <p class="page-description">运行中策略的月度体检：healthy / warning / stop 分级预警</p>
        </div>
        <div class="header-actions">
          <n-button quaternary @click="loadHealth" :loading="loading">
            <template #icon><Icon icon="mdi:refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 分级统计条 -->
    <div class="status-bar">
      <div
        v-for="item in statusStats"
        :key="item.status"
        class="status-chip"
        :class="`status-${item.status}`"
        @click="filterStatus = filterStatus === item.status ? null : item.status"
      >
        <span class="status-dot" :style="{ background: item.color }"></span>
        <span class="status-label">{{ item.label }}</span>
        <span class="status-count">{{ item.count }}</span>
      </div>
    </div>

    <div class="main-content">
      <n-spin :show="loading">
        <n-empty v-if="!loading && items.length === 0" description="暂无运行中的策略" />

        <div v-else class="strategy-list">
          <div
            v-for="s in filteredItems"
            :key="s.strategy_id"
            class="strategy-card"
          >
            <div class="card-header">
              <span class="strategy-name">{{ s.name }}</span>
              <n-tag
                :type="tagType(s.status)"
                size="small"
                round
              >
                {{ statusLabel(s.status) }}
              </n-tag>
            </div>
            <div class="alerts">
              <div
                v-for="(a, i) in s.alerts"
                :key="i"
                class="alert-line"
                :class="{ 'alert-warning': s.status === 'warning', 'alert-stop': s.status === 'stop' }"
              >
                {{ a }}
              </div>
            </div>
            <div class="metrics-row">
              <span>近段交易日：{{ s.metrics.recent_days }}</span>
              <span>近段收益：{{ fmtPct(s.metrics.recent_return) }}</span>
              <span>近段回撤：{{ fmtPct(s.metrics.recent_mdd) }}</span>
              <span>近段信号：{{ s.metrics.recent_signal_count }}</span>
            </div>
          </div>
        </div>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { useMessage } from "naive-ui";
import { monitorAPI, type StrategyHealthItem } from "@/api/monitor";

const message = useMessage();
const loading = ref(false);
const items = ref<StrategyHealthItem[]>([]);
const filterStatus = ref<string | null>(null);

const STATUS_META: Record<string, { label: string; color: string }> = {
  healthy: { label: "健康", color: "#18a058" },
  warning: { label: "预警", color: "#f0a020" },
  stop: { label: "停用", color: "#d03050" },
  insufficient: { label: "样本积累", color: "#909399" },
  not_found: { label: "未知", color: "#909399" },
};

const statusStats = computed(() => {
  const counts: Record<string, number> = {};
  for (const s of items.value) counts[s.status] = (counts[s.status] || 0) + 1;
  return Object.keys(STATUS_META).map((st) => ({
    status: st,
    ...STATUS_META[st],
    count: counts[st] || 0,
  }));
});

const filteredItems = computed(() =>
  filterStatus.value ? items.value.filter((s) => s.status === filterStatus.value) : items.value,
);

function statusLabel(st: string): string {
  return STATUS_META[st]?.label || st;
}
function tagType(st: string): "success" | "warning" | "error" | "default" | "info" {
  if (st === "healthy") return "success";
  if (st === "warning") return "warning";
  if (st === "stop") return "error";
  return "default";
}
function fmtPct(v: number | null | undefined): string {
  return v == null ? "--" : `${(v * 100).toFixed(1)}%`;
}

const loadHealth = async () => {
  loading.value = true;
  try {
    items.value = await monitorAPI.getStrategyHealth();
  } catch (e: any) {
    message.error("获取策略健康状态失败：" + (e?.message || "网络错误"));
  } finally {
    loading.value = false;
  }
};

onMounted(loadHealth);
</script>

<style scoped>
.strategy-health-page {
  min-height: 100vh;
}
.page-header {
  padding: 24px 28px 0;
}
.header-content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.title-section .page-title {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 6px;
}
.page-description {
  color: var(--n-text-color-3);
  font-size: 13px;
  margin: 0;
}
.status-bar {
  display: flex;
  gap: 12px;
  padding: 16px 28px;
}
.status-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.status-chip:hover {
  border-color: var(--n-primary-color);
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-count {
  font-weight: 600;
}
.main-content {
  padding: 0 28px 28px;
}
.strategy-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.strategy-card {
  padding: 18px;
  background: var(--n-card-color);
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.strategy-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.alerts {
  margin-bottom: 12px;
}
.alert-line {
  font-size: 13px;
  line-height: 1.8;
  color: var(--n-text-color-2);
}
.alert-warning {
  color: #f0a020;
}
.alert-stop {
  color: #d03050;
}
.metrics-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--n-text-color-3);
  border-top: 1px solid var(--n-border-color);
  padding-top: 10px;
}
</style>
