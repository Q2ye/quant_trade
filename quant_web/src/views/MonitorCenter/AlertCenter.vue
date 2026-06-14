<!--
  AlertCenter.vue — 报警中心
  路由: /monitor/alerts
  数据源: GET /quantTrade/monitor/alerts + PATCH /quantTrade/monitor/alerts/{id}
-->
<template>
  <div class="alert-page scrollbar-hide">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">报警中心</h1>
          <p class="page-description">查看和管理系统报警，确认处理或忽略</p>
        </div>
        <div class="header-actions">
          <n-button quaternary @click="refreshData" :loading="loading">
            <template #icon><Icon icon="mdi:refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 严重级别统计条 -->
    <div class="severity-bar">
      <div
        v-for="item in severityStats"
        :key="item.level"
        class="severity-chip"
        :class="[`severity-${item.level}`]"
        @click="filterSeverity = filterSeverity === item.level ? null : item.level"
      >
        <span class="severity-dot" :style="{ background: item.color }"></span>
        <span class="severity-label">{{ item.label }}</span>
        <span class="severity-count">{{ item.count }}</span>
      </div>
    </div>

    <!-- 主体 -->
    <div class="main-content">
      <template v-if="loading">
        <n-card :class="tokens.surface.card">
          <n-skeleton text :repeat="6" />
        </n-card>
      </template>

      <n-result
        v-else-if="error"
        status="500"
        title="加载失败"
        description="无法获取报警数据"
      >
        <template #footer>
          <n-button type="primary" @click="refreshData">重试</n-button>
        </template>
      </n-result>

      <n-empty v-else-if="filteredAlerts.length === 0" description="暂无报警" />

      <template v-else>
        <n-card :class="tokens.surface.card" content-class="!p-0">
          <n-data-table
            :columns="columns"
            :data="filteredAlerts"
            :row-key="(row: AlertItem) => row.id"
            :row-props="(row: AlertItem) => ({
              style: 'cursor: pointer',
              onClick: () => toggleExpand(row.id),
            })"
            :bordered="false"
            size="small"
            :max-height="500"
            :expanded-row-keys="expandedKeys"
          />
        </n-card>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted } from "vue";
import { useMessage } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import { Icon } from "@iconify/vue";
import riskAPI from "@/api/risk";

interface AlertItem {
  id: string;
  level: string;
  source: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
  rule_name?: string;
  trigger_value?: string;
  current_value?: string;
  suggestion?: string;
}

const message = useMessage();
const loading = ref(true);
const error = ref(false);
const alerts = ref<AlertItem[]>([]);
const filterSeverity = ref<string | null>(null);
const expandedKeys = ref<string[]>([]);

const severityConfig: Record<string, { label: string; color: string }> = {
  critical: { label: "🔴 严重", color: "#EF4444" },
  warning: { label: "🟡 警告", color: "#F59E0B" },
  info: { label: "🔵 信息", color: "#3B82F6" },
};

const severityStats = computed(() => {
  const counts: Record<string, number> = { critical: 0, warning: 0, info: 0 };
  alerts.value.forEach((a) => {
    const key = a.level?.toLowerCase() || "info";
    if (counts[key] !== undefined) counts[key]++;
  });
  return Object.entries(counts).map(([level, count]) => ({
    level,
    label: severityConfig[level]?.label || level,
    color: severityConfig[level]?.color || "#6B7280",
    count,
  }));
});

const filteredAlerts = computed(() => {
  if (!filterSeverity.value) return alerts.value;
  return alerts.value.filter((a) => a.level?.toLowerCase() === filterSeverity.value);
});

const columns = [
  {
    title: "时间",
    key: "created_at",
    width: 160,
    render: (row: AlertItem) =>
      row.created_at ? new Date(row.created_at).toLocaleString("zh-CN") : "--",
  },
  {
    title: "级别",
    key: "level",
    width: 80,
    render: (row: AlertItem) => {
      const cfg = severityConfig[row.level?.toLowerCase()] || severityConfig.info;
      return h("span", { style: { color: cfg.color, fontWeight: 600 } }, cfg.label);
    },
  },
  {
    title: "来源",
    key: "source",
    width: 100,
    ellipsis: { tooltip: true },
  },
  {
    title: "标题",
    key: "title",
    ellipsis: { tooltip: true },
  },
  {
    title: "状态",
    key: "status",
    width: 80,
    render: (row: AlertItem) =>
      h(
        "span",
        {
          class: `n-tag n-tag--${row.status === "acknowledged" ? "success" : "warning"}-type n-tag--small-type`,
        },
        row.status === "acknowledged" ? "已确认" : "处理中"
      ),
  },
  {
    title: "操作",
    key: "actions",
    width: 100,
    render: (row: AlertItem) =>
      row.status !== "acknowledged"
        ? h(
            "button",
            {
              class: "n-button n-button--primary-type n-button--tiny-type",
              onClick: (e: Event) => {
                e.stopPropagation();
                acknowledge(row.id);
              },
            },
            "确认"
          )
        : h("span", { style: { color: "var(--color-text-tertiary)", fontSize: "12px" } }, "—"),
  },
];

const toggleExpand = (id: string) => {
  if (expandedKeys.value.includes(id)) {
    expandedKeys.value = expandedKeys.value.filter((k) => k !== id);
  } else {
    expandedKeys.value = [id];
  }
};

const acknowledge = async (alertId: string) => {
  try {
    await riskAPI.acknowledgeRiskAlert(alertId).catch(() => {});
    const alert = alerts.value.find((a) => a.id === alertId);
    if (alert) alert.status = "acknowledged";
    message.success("报警已确认");
  } catch {
    message.error("确认失败");
  }
};

const refreshData = async () => {
  loading.value = true;
  error.value = false;
  try {
    const data = await riskAPI.getRiskAlerts().catch(() => []);
    alerts.value = Array.isArray(data) ? data : [];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  refreshData();
});
</script>

<style lang="scss" scoped>
.alert-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
  animation: fadeIn 0.3s ease-out;
}

.page-header {
  padding: 24px 32px 0;
  .header-content {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
  }
  .page-title { font-size: 22px; font-weight: 700; margin: 0 0 4px; color: var(--color-text-primary); }
  .page-description { font-size: 13px; color: var(--color-text-tertiary); margin: 0; }
}

.severity-bar {
  display: flex;
  gap: 12px;
  padding: 16px 32px 0;
  .severity-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 8px;
    background: var(--color-bg-card, rgba(12, 18, 32, 0.72));
    border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
    cursor: pointer;
    transition: all 0.2s;
    &:hover {
      border-color: var(--color-primary, #7C3AED);
    }
    .severity-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    .severity-label {
      font-size: 13px;
      font-weight: 500;
      color: var(--color-text-secondary);
    }
    .severity-count {
      font-size: 18px;
      font-weight: 700;
      color: var(--color-text-primary);
    }
  }
}

.main-content {
  padding: 20px 32px 32px;
}
</style>
