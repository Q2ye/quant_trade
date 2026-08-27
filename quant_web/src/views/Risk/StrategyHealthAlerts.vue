<!--
  StrategyHealthAlerts.vue v2 — 策略健康与报警（合并页）
  路由: /risk/strategy-health-alerts
  数据源: /quantTrade/monitor/strategies/health（策略健康）+ /quantTrade/risk/alerts（报警）
  改进（2026-08）：解包 items 修复报警不显示；统计卡区；历史对比（MDD 80% 线/信号频率）；
               报警字段对齐后端 alert_level/source_module/message；质感升级
-->
<template>
  <div class="health-alerts-page bg-gradient-mesh bg-noise">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略健康与报警</h1>
          <p class="page-description">运行中策略月度体检（healthy / warning / stop）+ 系统报警中心</p>
        </div>
        <div class="header-actions">
          <n-button quaternary @click="goPerformance">
            <template #icon><Icon icon="mdi:trophy" /></template>
            绩效中心
          </n-button>
          <n-button quaternary @click="goAccount">
            <template #icon><Icon icon="mdi:chart-box-outline" /></template>
            账户绩效
          </n-button>
          <n-button quaternary @click="refreshAll" :loading="loading">
            <template #icon><Icon icon="mdi:refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 统计卡区 -->
    <div class="main-content">
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-icon" style="background: rgba(24, 160, 88, 0.12); color: #18a058">
            <Icon icon="mdi:chart-line" />
          </div>
          <div>
            <div class="stat-label">运行策略</div>
            <div class="stat-value">{{ healthItems.length }} <span class="stat-sub">个</span></div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: rgba(240, 160, 32, 0.12); color: #f0a020">
            <Icon icon="mdi:alert" />
          </div>
          <div>
            <div class="stat-label">预警 / 停用</div>
            <div class="stat-value">
              {{ warnStopCount }} <span class="stat-sub">个</span>
              <span v-if="stopCount > 0" class="stat-stop-badge">停用 {{ stopCount }}</span>
            </div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: rgba(59, 130, 246, 0.12); color: #3b82f6">
            <Icon icon="mdi:bell-outline" />
          </div>
          <div>
            <div class="stat-label">未确认报警</div>
            <div class="stat-value">
              {{ alertCount }} <span class="stat-sub">条</span>
              <span class="stat-warn-badge">信号通知 {{ severityCount('info') }}</span>
            </div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: rgba(239, 68, 68, 0.12); color: #ef4444">
            <Icon icon="mdi:alert-octagon" />
          </div>
          <div>
            <div class="stat-label">严重告警</div>
            <div class="stat-value">
              {{ severityCount('critical') }}
              <span class="stat-sub">条</span>
              <span v-if="severityCount('warning') > 0" class="stat-warn-badge">警告 {{ severityCount('warning') }}</span>
            </div>
          </div>
        </div>
      </div>

      <n-tabs v-model:value="activeTab" type="line" animated>
        <!-- ══════════ Tab 1: 策略健康 ══════════ -->
        <n-tab-pane name="health" tab="策略健康">
          <div class="status-bar">
            <div
              v-for="item in statusStats"
              :key="item.status"
              class="chip"
              :class="{ 'chip-active': filterStatus === item.status }"
              @click="filterStatus = filterStatus === item.status ? null : item.status"
            >
              <span class="dot" :style="{ background: item.color }"></span>
              <span>{{ item.label }}</span>
              <span class="chip-count">{{ item.count }}</span>
            </div>
          </div>

          <n-spin :show="loading">
            <n-empty v-if="!loading && healthItems.length === 0" description="暂无运行中的策略" />
            <div v-else class="strategy-list">
              <div
                v-for="s in filteredHealthItems"
                :key="s.strategy_id"
                class="strategy-card"
                :class="`card-${s.status}`"
              >
                <div class="card-header">
                  <span class="strategy-name">{{ s.name }}</span>
                  <n-tag :type="tagType(s.status)" size="small" round>{{ statusLabel(s.status) }}</n-tag>
                </div>

                <div class="alert-list">
                  <div
                    v-for="(a, i) in s.alerts"
                    :key="i"
                    class="alert-line"
                    :class="{ 'line-warning': s.status === 'warning', 'line-stop': s.status === 'stop' }"
                  >
                    <Icon :icon="s.status === 'stop' ? 'mdi:close-octagon' : s.status === 'warning' ? 'mdi:alert' : 'mdi:check-circle'" :size="14" />
                    <span>{{ a }}</span>
                  </div>
                </div>

                <!-- 口径标注：近段收益/回撤/信号频率均来自实盘策略每日绩效 -->
                <div class="metrics-source">数据源：实盘策略每日绩效 <SourceBadge type="strategy" /></div>
                <div class="metrics-grid">
                  <div class="metric">
                    <div class="metric-label">近段交易日</div>
                    <div class="metric-value">{{ s.metrics.recent_days }}</div>
                  </div>
                  <div class="metric">
                    <div class="metric-label">近段收益</div>
                    <div class="metric-value" :class="s.metrics.recent_return >= 0 ? 'text-rise' : 'text-fall'">
                      {{ s.metrics.recent_days > 0 ? fmtPct(s.metrics.recent_return) : '--' }}
                    </div>
                  </div>
                  <div class="metric">
                    <div class="metric-label">近段回撤</div>
                    <div class="metric-value text-fall">{{ s.metrics.recent_days > 0 ? fmtPct(s.metrics.recent_mdd) : '--' }}</div>
                  </div>
                  <div class="metric">
                    <div class="metric-label">近段信号</div>
                    <div class="metric-value">{{ s.metrics.recent_signal_count }}</div>
                  </div>
                </div>

                <!-- 历史对比（有历史数据时） -->
                <template v-if="s.metrics.hist_max_mdd != null">
                  <div class="compare-block">
                    <div class="compare-row">
                      <span class="compare-label">回撤 vs 历史最大</span>
                      <span class="compare-value">
                        近段 {{ fmtPct(s.metrics.recent_mdd) }} / 历史 {{ fmtPct(s.metrics.hist_max_mdd) }}
                        <span
                          class="compare-hint"
                          :class="mddWarn(s.metrics) ? 'hint-danger' : 'hint-ok'"
                        >
                          {{ mddWarn(s.metrics) ? '超 80% 线' : '正常' }}
                        </span>
                      </span>
                    </div>
                    <n-progress
                      type="line"
                      :percentage="mddPct(s.metrics)"
                      :show-indicator="false"
                      :height="6"
                      :color="mddWarn(s.metrics) ? '#f0a020' : '#18a058'"
                      rail-color="rgba(128,128,128,0.15)"
                    />
                    <div class="compare-row" style="margin-top: 8px">
                      <span class="compare-label">信号频率 vs 历史月均</span>
                      <span class="compare-value">
                        近段 {{ s.metrics.recent_signal_count }} / 月均 {{ s.metrics.hist_monthly_signal_avg ?? '--' }}
                      </span>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </n-spin>
        </n-tab-pane>

        <!-- ══════════ Tab 2: 报警中心 ══════════ -->
        <n-tab-pane name="alerts" tab="报警中心">
          <div class="status-bar alerts-filter-bar">
            <span class="important-toggle">
              <n-switch v-model:value="showImportantOnly" size="small" />
              <span class="important-label">仅看重要（warning / critical）</span>
            </span>
            <div
              v-for="item in severityStats"
              :key="item.level"
              class="chip"
              :class="{ 'chip-active': filterSeverity === item.level }"
              @click="filterSeverity = filterSeverity === item.level ? null : item.level"
            >
              <span class="dot" :style="{ background: item.color }"></span>
              <span>{{ item.label }}</span>
              <span class="chip-count">{{ item.count }}</span>
            </div>
          </div>

          <n-spin :show="loading">
            <n-empty v-if="!loading && filteredAlerts.length === 0" description="暂无报警" />
            <n-card v-else :bordered="false" class="alerts-card">
              <n-data-table
                :columns="alertColumns"
                :data="filteredAlerts"
                :row-key="(row: AlertItem) => row.id"
                :bordered="false"
                size="small"
                :max-height="540"
                :expanded-row-keys="expandedKeys"
                :row-props="(row: AlertItem) => ({ onClick: () => toggleExpand(row.id), style: 'cursor: pointer' })"
              />
            </n-card>
          </n-spin>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { useMessage } from "naive-ui";
import { monitorAPI, type StrategyHealthItem } from "@/api/monitor";
import riskAPI from "@/api/risk";
import SourceBadge from "@/components/common/SourceBadge.vue";

const router = useRouter();
const message = useMessage();
const activeTab = ref("health");
const loading = ref(false);
const healthItems = ref<StrategyHealthItem[]>([]);
const filterStatus = ref<string | null>(null);
const expandedKeys = ref<string[]>([]);

// ── 统计 ──
const warnStopCount = computed(
  () => healthItems.value.filter((s) => s.status === "warning" || s.status === "stop").length,
);
const stopCount = computed(() => healthItems.value.filter((s) => s.status === "stop").length);
const alertCount = computed(() => severityCount("critical") + severityCount("warning"));

// ── 策略健康 ──
const STATUS_META: Record<string, { label: string; color: string }> = {
  healthy: { label: "健康", color: "#18a058" },
  warning: { label: "预警", color: "#f0a020" },
  stop: { label: "停用", color: "#d03050" },
  insufficient: { label: "样本积累", color: "#909399" },
  not_found: { label: "未知", color: "#909399" },
};

const statusStats = computed(() => {
  const counts: Record<string, number> = {};
  for (const s of healthItems.value) counts[s.status] = (counts[s.status] || 0) + 1;
  return Object.keys(STATUS_META).map((st) => ({
    status: st,
    ...STATUS_META[st],
    count: counts[st] || 0,
  }));
});

const filteredHealthItems = computed(() =>
  filterStatus.value ? healthItems.value.filter((s) => s.status === filterStatus.value) : healthItems.value,
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
function mddPct(m: StrategyHealthItem["metrics"]): number {
  if (m.hist_max_mdd == null || m.hist_max_mdd <= 0) return 0;
  return Math.min(Math.round((m.recent_mdd / m.hist_max_mdd) * 100), 100);
}
function mddWarn(m: StrategyHealthItem["metrics"]): boolean {
  return m.hist_max_mdd != null && m.hist_max_mdd > 0 && m.recent_mdd > m.hist_max_mdd * 0.8;
}

// ── 报警中心（字段对齐后端 alert_level/source_module/message） ──
interface AlertItem {
  id: string;
  alert_type: string;
  alert_level: string;
  source_module: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
}

const alerts = ref<AlertItem[]>([]);
const filterSeverity = ref<string | null>(null);
// 2026-08：报警默认仅看重要级别（info 信号通知量大且非异常，计数仍保留）
const showImportantOnly = ref(true);

const severityConfig: Record<string, { label: string; color: string }> = {
  critical: { label: "严重", color: "#EF4444" },
  warning: { label: "警告", color: "#F59E0B" },
  info: { label: "信息", color: "#3B82F6" },
};

const severityStats = computed(() => {
  const counts: Record<string, number> = { critical: 0, warning: 0, info: 0 };
  alerts.value.forEach((a) => {
    const key = (a.alert_level || "info").toLowerCase();
    if (counts[key] !== undefined) counts[key]++;
  });
  return Object.entries(counts).map(([level, count]) => ({
    level,
    label: severityConfig[level]?.label || level,
    color: severityConfig[level]?.color || "#6B7280",
    count,
  }));
});

function severityCount(level: string): number {
  return alerts.value.filter((a) => (a.alert_level || "info").toLowerCase() === level).length;
}

const filteredAlerts = computed(() => {
  let list = alerts.value;
  if (showImportantOnly.value) {
    list = list.filter((a) => (a.alert_level || "info").toLowerCase() !== "info");
  }
  if (filterSeverity.value) {
    list = list.filter((a) => (a.alert_level || "info").toLowerCase() === filterSeverity.value);
  }
  return list;
});

const toggleExpand = (id: string) => {
  expandedKeys.value = expandedKeys.value.includes(id) ? [] : [id];
};

const alertColumns = [
  {
    type: "expand",
    render: (row: AlertItem) =>
      h(
        "div",
        { style: "padding: 10px 16px; font-size: 12px; color: var(--n-text-color-2); white-space: pre-wrap; line-height: 1.7;" },
        row.message || "无详情",
      ),
  },
  {
    title: "时间",
    key: "created_at",
    width: 165,
    render: (row: AlertItem) =>
      row.created_at ? new Date(row.created_at).toLocaleString("zh-CN") : "--",
  },
  {
    title: "级别",
    key: "alert_level",
    width: 80,
    render: (row: AlertItem) => {
      const cfg = severityConfig[(row.alert_level || "info").toLowerCase()] || severityConfig.info;
      return h("span", { style: { color: cfg.color, fontWeight: 600 } }, cfg.label);
    },
  },
  { title: "来源", key: "source_module", width: 150, ellipsis: { tooltip: true } },
  { title: "标题", key: "title", ellipsis: { tooltip: true } },
  {
    title: "状态",
    key: "status",
    width: 80,
    render: (row: AlertItem) =>
      h(
        "span",
        { style: { color: row.status === "acknowledged" ? "#18a058" : "#f0a020", fontSize: "12px" } },
        row.status === "acknowledged" ? "已确认" : "处理中",
      ),
  },
  {
    title: "操作",
    key: "actions",
    width: 80,
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
            "确认",
          )
        : h("span", { style: { color: "var(--color-text-tertiary)", fontSize: "12px" } }, "—"),
  },
];

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

// ── 加载（修复：getRiskAlerts 返回 {items, pagination}，需解包 items） ──
const refreshAll = async () => {
  loading.value = true;
  try {
    healthItems.value = await monitorAPI.getStrategyHealth();
    const res: any = await riskAPI.getRiskAlerts().catch(() => null);
    const data = res?.data ?? res ?? {};
    alerts.value = Array.isArray(data) ? data : (data.items ?? []);
  } catch {
    message.error("加载失败，请重试");
  } finally {
    loading.value = false;
  }
};

// ── 绩效中心互跳快捷入口 ──
const goPerformance = () => router.push("/performance");
const goAccount = () => router.push("/performance/account");

onMounted(refreshAll);
</script>

<style scoped>
.health-alerts-page {
  min-height: 100vh;
}
/* 页头样式由全局 global.scss .page-header 统一提供（渐变块/发光边/排版），本页不覆盖 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: var(--n-card-color);
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  border: 1px solid var(--n-border-color);
}
.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}
.stat-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--n-text-color-1);
  line-height: 1.3;
}
.stat-sub {
  font-size: 12px;
  font-weight: 400;
  color: var(--n-text-color-3);
}
.stat-stop-badge {
  margin-left: 8px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: #d03050;
  border-radius: 10px;
  padding: 1px 8px;
}
.stat-warn-badge {
  margin-left: 8px;
  font-size: 11px;
  font-weight: 600;
  color: #f0a020;
  border: 1px solid rgba(240, 160, 32, 0.4);
  border-radius: 10px;
  padding: 1px 8px;
}

.main-content {
  margin-top: 6px;
}
.status-bar {
  display: flex;
  gap: 10px;
  padding: 8px 0 16px;
  flex-wrap: wrap;
}
.chip {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 14px;
  border-radius: 20px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.chip:hover {
  border-color: var(--n-primary-color);
}
.chip-active {
  border-color: var(--n-primary-color);
  box-shadow: 0 0 0 2px rgba(24, 160, 88, 0.12);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.chip-count {
  font-weight: 600;
}

/* 报警过滤条：仅看重要开关 */
.alerts-filter-bar {
  align-items: center;
}
.important-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
}
.important-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* 口径标注 */
.metrics-source {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-bottom: 8px;
}

/* 策略卡片 */
.strategy-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}
.strategy-card {
  padding: 18px;
  background: var(--n-card-color);
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  border-left: 4px solid #909399;
  transition: all 0.2s;
}
.strategy-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
}
.card-healthy {
  border-left-color: #18a058;
}
.card-warning {
  border-left-color: #f0a020;
}
.card-stop {
  border-left-color: #d03050;
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
.alert-list {
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.alert-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--n-text-color-2);
}
.line-warning {
  color: #f0a020;
}
.line-stop {
  color: #d03050;
  font-weight: 500;
}

/* 指标网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  border-top: 1px solid var(--n-border-color);
  padding-top: 12px;
}
.metric-label {
  font-size: 11px;
  color: var(--n-text-color-3);
  margin-bottom: 2px;
}
.metric-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.text-rise {
  color: #f0483e;
}
.text-fall {
  color: #18a058;
}

/* 历史对比 */
.compare-block {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--n-border-color);
}
.compare-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-bottom: 6px;
}
.compare-value {
  color: var(--n-text-color-2);
  font-weight: 500;
}
.compare-hint {
  margin-left: 6px;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 8px;
}
.hint-danger {
  color: #f0a020;
  background: rgba(240, 160, 32, 0.1);
}
.hint-ok {
  color: #18a058;
  background: rgba(24, 160, 88, 0.1);
}

/* 报警表格 */
.alerts-card {
  background: var(--n-card-color);
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
}
</style>
