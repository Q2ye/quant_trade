<!--
  PerformanceDashboard.vue — 绩效驾驶舱（绩效中心唯一入口 /performance）
  一屏总览：指标条(账户口径) + 净值/回撤 + 策略健康 + 回测 Top5 + 重要报警 + 月度收益
  钻取：回测排行 /performance/rank、账户绩效 /performance/account、策略健康 /performance/health
  数据并行加载（Promise.all），各区块四状态覆盖。
-->
<template>
  <div class="perf-dashboard-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">绩效中心</h1>
          <p class="page-description">账户资金 · 策略健康 · 回测排行 · 报警 一屏总览</p>
        </div>
        <div class="header-actions">
          <!-- 账户选择：绩效中心账户区块按所选账户展示（2026-08：不再固定第一个账户） -->
          <n-select
            v-model:value="accountId"
            :options="accountOptions"
            placeholder="选择账户"
            size="small"
            style="width: 200px"
            :loading="accountsLoading"
            @update:value="onAccountChange"
          />
          <n-button quaternary size="small" @click="goRank">
            <template #icon><SmartIcon name="Trophy" /></template>
            回测排行
          </n-button>
          <n-button quaternary size="small" @click="goAccount">
            <template #icon><SmartIcon name="AnalyticsOutline" /></template>
            账户绩效
          </n-button>
          <n-button quaternary size="small" @click="goHealth">
            <template #icon><SmartIcon name="Pulse" /></template>
            策略健康
          </n-button>
          <n-button quaternary size="small" :loading="loading" @click="loadAll">
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-spin :show="loading">
        <n-result v-if="error" status="500" title="加载失败" description="获取绩效数据失败，请稍后重试">
          <template #footer><n-button type="primary" @click="loadAll">重试</n-button></template>
        </n-result>

        <template v-else>
          <!-- 指标条（账户口径） -->
          <div class="metric-row">
            <StatCard title="账户总资产" :value="fmtMoney(totalAsset)" />
            <StatCard title="当日盈亏" :value="fmtMoneySigned(dailyPnl)" :trend="dailyPnl >= 0 ? 'up' : 'down'" />
            <StatCard title="当日收益率" :value="fmtPct(dailyReturn)" :trend="dailyReturn >= 0 ? 'up' : 'down'" />
            <StatCard title="累计收益" :value="fmtPct(totalReturn)" :trend="totalReturn >= 0 ? 'up' : 'down'" />
            <StatCard title="年化收益" :value="sampleEnough ? fmtPct(annualReturn) : '--'" :trend="annualReturn >= 0 ? 'up' : 'down'" />
            <StatCard title="最大回撤" :value="fmtPct(maxDrawdown)" trend="down" />
            <StatCard title="夏普比率" :value="sampleEnough ? sharpeRatio.toFixed(2) : '--'" />
          </div>
          <div class="metric-footnote">
            数据源：账户日资产快照 <SourceBadge type="account" />
            <template v-if="equityCurve.length > 0">
              · 当前 {{ equityCurve.length }} 个交易日样本（随日终结算逐日积累）
              <template v-if="!sampleEnough"> · 年化/夏普需 ≥20 个交易日，暂时显示 --</template>
            </template>
          </div>

          <!-- 实盘监控三数预警（B4：当日盈亏/总回撤/可用资金 阈值高亮） -->
          <div v-if="liveSummary" class="live-monitor">
            <div class="live-monitor-header">
              <span class="live-monitor-title">实盘监控</span>
              <n-tag :type="liveSummary.overall_level === 'critical' ? 'error' : liveSummary.overall_level === 'warning' ? 'warning' : 'success'" size="small">
                {{ liveSummary.overall_level === 'critical' ? '严重' : liveSummary.overall_level === 'warning' ? '预警' : '正常' }}
              </n-tag>
            </div>
            <div class="live-monitor-grid">
              <div v-for="a in liveSummary.alerts" :key="a.metric" class="live-monitor-item" :class="'lm-' + a.level">
                <span class="lm-label">{{ a.label }}</span>
                <span class="lm-value">{{ a.value }}{{ a.unit }}</span>
                <span class="lm-threshold">预警 {{ a.warning_threshold }}{{ a.unit }} · 严重 {{ a.critical_threshold }}{{ a.unit }}</span>
              </div>
            </div>
          </div>

          <!-- 主区：净值/回撤 + 策略健康 -->
          <div class="dual-row">
            <n-card :class="tokens.surface.card" size="small" style="flex: 1.6">
              <template #header>
                <span class="card-title">账户净值曲线 <SourceBadge type="account" /></span>
              </template>
              <EquityCurveChart
                v-if="equityCurve.length > 0"
                :data="equityCurve"
                :drawdown="drawdownCurve"
                :height="320"
              />
              <n-empty v-else description="暂无账户净值数据" style="padding: 60px 0" />
            </n-card>

            <n-card :class="tokens.surface.card" size="small" style="flex: 1">
              <template #header>
                <span class="card-title">策略健康 <SourceBadge type="strategy" /></span>
                <span v-if="healthItems.length" class="card-sub">{{ healthSummary }}</span>
              </template>
              <div v-if="healthItems.length" class="health-list">
                <div v-for="s in healthItems" :key="s.strategy_id" class="health-item" @click="goHealth">
                  <span class="h-name" :title="s.name">{{ s.name }}</span>
                  <n-tag :type="tagType(s.status)" size="small" round>{{ statusLabel(s.status) }}</n-tag>
                  <span class="h-metric" :class="s.metrics.recent_return >= 0 ? 'text-rise' : 'text-fall'">
                    {{ s.metrics.recent_days > 0 ? fmtPct(s.metrics.recent_return) : '--' }}
                  </span>
                  <span class="h-metric text-fall">{{ s.metrics.recent_days > 0 ? fmtPct(-s.metrics.recent_mdd) : '--' }}</span>
                </div>
                <div class="drill-link" @click="goHealth">查看全部 →</div>
              </div>
              <n-empty v-else description="暂无运行中的策略" style="padding: 40px 0" />
            </n-card>
          </div>

          <!-- 回测 Top5（回测口径） -->
          <n-card :class="tokens.surface.card" size="small" style="margin-top: 12px">
            <template #header>
              <span class="card-title">回测绩效 Top5 <SourceBadge type="backtest" /></span>
              <span class="card-sub">点击进入回测报告</span>
            </template>
            <div v-if="topRankings.length" class="rank-list">
              <div class="rank-head">
                <span class="rc col-rank">#</span>
                <span class="rc col-name">策略</span>
                <span class="rc col-metric">年化</span>
                <span class="rc col-metric">总收益</span>
                <span class="rc col-metric">夏普</span>
                <span class="rc col-metric">最大回撤</span>
                <span class="rc col-date">回测日期</span>
                <span class="rc col-range">回测区间</span>
              </div>
              <div v-for="(s, idx) in topRankings" :key="s.taskId" class="rank-row" @click="goReport(s)">
                <span class="rc col-rank">
                  <span :class="['rank-badge', idx < 3 ? `top-${idx + 1}` : '']">{{ idx + 1 }}</span>
                </span>
                <span class="rc col-name">{{ s.name }}</span>
                <span class="rc col-metric" :class="s.annualReturn >= 0 ? 'text-rise' : 'text-fall'">{{ fmtPct(s.annualReturn) }}</span>
                <span class="rc col-metric" :class="s.totalReturn >= 0 ? 'text-rise' : 'text-fall'">{{ fmtPct(s.totalReturn) }}</span>
                <span class="rc col-metric">{{ (s.sharpeRatio || 0).toFixed(2) }}</span>
                <span class="rc col-metric text-fall">{{ fmtPct(s.maxDrawdown) }}</span>
                <span class="rc col-date">{{ s.taskDate || '--' }}</span>
                <span class="rc col-range">{{ s.startDate && s.endDate ? `${s.startDate} ~ ${s.endDate}` : '--' }}</span>
              </div>
              <div class="drill-link" @click="goRank">查看全部排行 →</div>
            </div>
            <n-empty v-else description="暂无回测数据，请先运行回测" style="padding: 30px 0" />
          </n-card>

          <!-- 底部：月度收益 + 重要报警 -->
          <div class="dual-row" style="margin-top: 12px">
            <n-card :class="tokens.surface.card" size="small" style="flex: 1.4">
              <template #header>
                <span class="card-title">月度收益 <SourceBadge type="account" /></span>
              </template>
              <MonthlyReturnChart v-if="monthlyReturns.length" :data="monthlyReturns" :height="220" :title="''" />
              <n-empty
                v-else
                :description="equityCurve.length > 0 ? `数据积累中（账户快照 ${equityCurve.length} 个交易日，满一个月后展示月度收益）` : '暂无月度数据'"
                style="padding: 40px 0"
              />
            </n-card>

            <n-card :class="tokens.surface.card" size="small" style="flex: 1">
              <template #header>
                <span class="card-title">最新报警</span>
                <span class="card-sub">重要优先 · 点击进入报警中心</span>
              </template>
              <div v-if="recentAlerts.length" class="alert-list">
                <div v-for="a in recentAlerts" :key="a.id" class="alert-item" @click="goHealth">
                  <span class="a-level" :style="{ color: levelColor(a.alert_level) }">{{ levelLabel(a.alert_level) }}</span>
                  <span class="a-title" :title="a.title || a.message">{{ a.title || a.message }}</span>
                  <span class="a-time">{{ shortTime(a.created_at) }}</span>
                </div>
                <div class="drill-link" @click="goHealth">查看全部 →</div>
              </div>
              <n-empty v-else description="暂无报警" style="padding: 40px 0" />
            </n-card>
          </div>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCard, NEmpty, NResult, NSpin, NTag } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import SourceBadge from "@/components/common/SourceBadge.vue";
import StatCard from "@/components/common/StatCard.vue";
import EquityCurveChart from "@/components/charts/EquityCurveChart.vue";
import MonthlyReturnChart from "@/components/charts/MonthlyReturnChart.vue";
import { tokens } from "@/styles/design-tokens";
import performanceAPI from "@/api/performance";
import { monitorAPI, type StrategyHealthItem, type LiveSummary } from "@/api/monitor";
import riskAPI from "@/api/risk";
import backtestAPI from "@/api/backtest";
import request from "@/utils/request";

const router = useRouter();

const loading = ref(false);
const error = ref(false);

// ---- 账户指标（账户口径） ----
const totalAsset = ref(0);
const dailyPnl = ref(0);
const dailyReturn = ref(0);
const totalReturn = ref(0);
const annualReturn = ref(0);
const maxDrawdown = ref(0);
const sharpeRatio = ref(0);
const equityCurve = ref<Array<{ date: string; value: number }>>([]);
const drawdownCurve = ref<Array<{ date: string; value: number }>>([]);
const monthlyReturns = ref<Array<{ month: string; return: number }>>([]);

// ---- 策略健康（实盘策略口径） ----
const healthItems = ref<StrategyHealthItem[]>([]);
const liveSummary = ref<LiveSummary | null>(null);
const healthSummary = computed(() => {
  const w = healthItems.value.filter((s) => s.status === "warning" || s.status === "stop").length;
  return w > 0 ? `${w} 个预警/停用` : "全部健康";
});

// ---- 报警（重要优先，info 兜底展示，避免"重要报警"区块恒空） ----
interface AlertItem { id: string; alert_level: string; title: string; message: string; created_at: string; }
const alerts = ref<AlertItem[]>([]);
const LEVEL_ORDER: Record<string, number> = { critical: 2, warning: 1, info: 0 };
const recentAlerts = computed(() =>
  [...alerts.value]
    .sort((a, b) => (LEVEL_ORDER[(b.alert_level || "info").toLowerCase()] ?? 0) - (LEVEL_ORDER[(a.alert_level || "info").toLowerCase()] ?? 0))
    .slice(0, 6),
);

// ---- 回测 Top5（回测口径） ----
interface RankItem { id: string; name: string; taskId?: string; taskDate?: string; startDate?: string; endDate?: string; annualReturn: number; totalReturn: number; sharpeRatio: number; maxDrawdown: number; }
const topRankings = ref<RankItem[]>([]);

const fmtPct = (v: number) => (v == null || isNaN(v) ? "--" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`);
const fmtMoney = (v: number) => (v == null ? "--" : `¥${Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const fmtMoneySigned = (v: number) => `${v >= 0 ? "+" : ""}${fmtMoney(v)}`;

// 账户样本充分性门控：<20 个交易日时年化/夏普等指标失真（实测 9 天会年化出 ~100%），
// 显示 "--" 避免误导；累计收益/回撤/当日数据保留真实值
const sampleEnough = computed(() => equityCurve.value.length >= 20);

const goRank = () => router.push("/performance/rank");
const goAccount = () => router.push("/performance/account");
const goHealth = () => router.push("/performance/health");
const goReport = (s: RankItem) => s.taskId && router.push(`/backtest/report/${s.taskId}`);

function tagType(st: string): "success" | "warning" | "error" | "default" {
  if (st === "healthy") return "success";
  if (st === "warning") return "warning";
  if (st === "stop") return "error";
  return "default";
}
const STATUS_LABEL: Record<string, string> = {
  healthy: "健康", warning: "预警", stop: "停用", insufficient: "样本积累", not_found: "未知",
};
function statusLabel(st: string): string { return STATUS_LABEL[st] || st; }
function levelLabel(level: string): string {
  const m: Record<string, string> = { critical: "严重", warning: "警告", info: "信息" };
  return m[(level || "info").toLowerCase()] || level;
}
function levelColor(level: string): string {
  const m: Record<string, string> = { critical: "#ef4444", warning: "#f0a020", info: "#3b82f6" };
  return m[(level || "info").toLowerCase()] || "#909399";
}
function shortTime(t: string): string {
  if (!t) return "--";
  return String(t).slice(5, 16).replace("T", " ");
}

// ---- 回测 Top5 加载（后端下沉排行接口：每策略取净值窗口最长任务，按年化降序） ----
async function loadTopRankings() {
  try {
    const rankings: any[] = await backtestAPI.getRankings(5).catch(() => []);
    topRankings.value = (Array.isArray(rankings) ? rankings : []).map((r: any) => ({
      id: r.strategy_id,
      name: r.strategy_name || r.strategy_id,
      taskId: r.task_id,
      taskDate: r.task_date || "",
      startDate: r.start_date || "",
      endDate: r.end_date || "",
      annualReturn: r.annual_return ?? 0,
      totalReturn: r.total_return ?? 0,
      sharpeRatio: r.sharpe_ratio ?? 0,
      maxDrawdown: r.max_drawdown ?? 0,
    }));
  } catch { /* Top5 失败不影响整页 */ }
}

// ---- 账户选择（2026-08：账户区块按所选账户展示，默认选首个有资产的 active 账户） ----
const accounts = ref<any[]>([]);
const accountId = ref("");
const accountsLoading = ref(false);
const accountOptions = computed(() =>
  accounts.value.map((a: any) => ({
    label: `${a.broker ? a.broker + " " : ""}${a.account_name || a.account_number || a.id}${a.status === "closed" ? "（已关闭）" : ""}`,
    value: a.id,
  })),
);

async function loadAccounts() {
  accountsLoading.value = true;
  try {
    const res: any = await request.get("/quantTrade/account/list", { params: { page: 1, page_size: 100 } });
    const list = res?.data?.data || res?.data || [];
    accounts.value = Array.isArray(list) ? list : [];
    // 默认账户：优先 active 且有资产，其次第一个 active，最后第一个
    const active = accounts.value.filter((a: any) => a.status !== "closed");
    const funded = active.find((a: any) => Number(a.total_balance ?? a.total_asset ?? 0) > 0);
    const target = funded || active[0] || accounts.value[0];
    if (target?.id && !accountId.value) {
      accountId.value = target.id;
      await loadAccountData(target.id);
    }
  } catch { /* 无账户时账户区块保持空 */ } finally {
    accountsLoading.value = false;
  }
}

function onAccountChange() {
  if (accountId.value) loadAccountData(accountId.value);
}

// ---- 账户区块数据（按账户加载） ----
async function loadAccountData(id: string) {
  try {
    const accRes: any = await performanceAPI.getAccountPerformance(id).catch(() => null);
    const acc = accRes?.data ?? accRes ?? {};
    totalAsset.value = Number(acc.total_asset ?? 0);
    dailyPnl.value = Number(acc.daily_pnl ?? 0);
    dailyReturn.value = Number(acc.daily_return ?? 0);
    totalReturn.value = Number(acc.total_return ?? 0);
    annualReturn.value = Number(acc.annual_return ?? 0);
    // 账户 API 返回正深度，统一负值口径（-15% = 回撤 15%），与回测排行/报告一致
    maxDrawdown.value = -Math.abs(Number(acc.max_drawdown ?? 0));
    sharpeRatio.value = Number(acc.sharpe_ratio ?? 0);
    if (Array.isArray(acc.equity_curve)) {
      equityCurve.value = acc.equity_curve.map((p: any) => ({
        date: p.date || p.trade_date,
        value: p.equity ?? p.total_asset ?? 0,
      }));
    }
    if (Array.isArray(acc.drawdown_curve)) {
      // 账户 drawdown 为正值深度 → 取负保持回撤图 0 下方（与回测报告口径一致）
      drawdownCurve.value = acc.drawdown_curve.map((p: any) => ({
        date: p.date || p.trade_date,
        value: -(p.drawdown ?? p.value ?? 0),
      }));
    }
    if (acc.monthly_returns && typeof acc.monthly_returns === "object") {
      monthlyReturns.value = Object.entries(acc.monthly_returns).map(([month, r]) => ({
        month, return: Number(r) || 0,
      }));
    }
  } catch { /* 账户数据失败保持现状 */ }
}

// ---- 并行加载全部区块（2026-08 修复：此前注释写并行实则串行 await，改 Promise.all 并行）----
async function loadAll() {
  loading.value = true;
  error.value = false;
  try {
    await Promise.all([
      // 1. 账户列表 + 默认账户绩效
      loadAccounts(),
      // 2. 策略健康（独立兜底）
      monitorAPI.getStrategyHealth()
        .then((items) => { healthItems.value = items; })
        .catch(() => {}),
      // 3. 重要报警（独立兜底）
      riskAPI.getRiskAlerts()
        .then((res: any) => {
          const data = res?.data ?? res ?? {};
          alerts.value = Array.isArray(data) ? data : (data.items ?? []);
        })
        .catch(() => null),
      // 4. 回测 Top5（独立 try，失败不影响整页）
      loadTopRankings(),
      // 5. 实盘监控三数（独立兜底）
      monitorAPI.getLiveSummary()
        .then((s) => { liveSummary.value = s; })
        .catch(() => null),
    ]);
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);
</script>

<style lang="scss" scoped>
.perf-dashboard-page {
  height: 100%;
  overflow-y: auto;
}
.main-content {
  padding: 0 19px 24px;
}
.metric-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 10px;
}
.metric-footnote {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-tertiary);
  line-height: 1.6;
}
.dual-row {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}
.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.card-sub {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-left: 8px;
}

/* 策略健康列表 */
.health-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.health-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: background 0.15s;
  &:hover { background: rgba(124, 111, 247, 0.08); }
}
.h-name {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.h-metric {
  font-size: 12px;
  font-weight: 600;
  min-width: 58px;
  text-align: right;
}

/* 回测排行 */
.rank-list {
  font-size: 12px;
}
.rank-head,
.rank-row {
  display: flex;
  align-items: center;
  padding: 7px 12px;
}
.rank-head {
  font-weight: 600;
  color: var(--color-text-tertiary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 11px;
}
.rank-row {
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  transition: background 0.12s;
  &:hover { background: rgba(124, 111, 247, 0.05); }
  &:last-of-type { border-bottom: none; }
}
.rc { flex-shrink: 0; }
.col-rank { width: 32px; text-align: center; }
.col-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text-primary); font-weight: 500; }
.col-metric { width: 84px; text-align: right; color: var(--color-text-secondary); font-weight: 500; }
.col-date { width: 90px; text-align: right; color: var(--color-text-tertiary); font-size: 11px; }
.col-range { width: 155px; text-align: right; color: var(--color-text-tertiary); font-size: 11px; }
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-tertiary);
  background: rgba(255, 255, 255, 0.05);
  &.top-1 { background: #ffd700; color: #000; }
  &.top-2 { background: #c0c0c0; color: #000; }
  &.top-3 { background: #cd7f32; color: #fff; }
}

/* 报警列表 */
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.alert-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: background 0.15s;
  &:hover { background: rgba(124, 111, 247, 0.08); }
}
.a-level {
  font-size: 11px;
  font-weight: 700;
  min-width: 34px;
}
.a-title {
  flex: 1;
  font-size: 12px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.a-time {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

/* 钻取链接 */
.drill-link {
  margin-top: 10px;
  text-align: right;
  font-size: 12px;
  color: var(--color-primary, #7c3aed);
  cursor: pointer;
  &:hover { text-decoration: underline; }
}

.text-rise { color: var(--color-stock-up) !important; }
.text-fall { color: var(--color-stock-down) !important; }

@media (max-width: 1200px) {
  .metric-row { grid-template-columns: repeat(4, 1fr); }
  .dual-row { flex-direction: column; }
}
@media (max-width: 768px) {
  .metric-row { grid-template-columns: repeat(2, 1fr); }
}

/* 实盘监控三数预警（B4） */
.live-monitor {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--color-bg-card, rgba(12, 18, 32, 0.72));
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
}
.live-monitor-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.live-monitor-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #e6edf3);
}
.live-monitor-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.live-monitor-item {
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--color-bg-card, rgba(12, 18, 32, 0.72));
  border-left: 3px solid var(--color-stock-down, #26a69a);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.live-monitor-item.lm-warning { border-left-color: #f0a020; }
.live-monitor-item.lm-critical { border-left-color: var(--color-stock-up, #ef5350); }
.lm-label { font-size: 11px; color: var(--color-text-tertiary, #8898b8); }
.lm-value { font-size: 18px; font-weight: 700; color: var(--color-text-primary, #e6edf3); }
.live-monitor-item.lm-warning .lm-value { color: #f0a020; }
.live-monitor-item.lm-critical .lm-value { color: var(--color-stock-up, #ef5350); }
.lm-threshold { font-size: 10px; color: var(--color-text-tertiary, #8898b8); }
@media (max-width: 768px) {
  .live-monitor-grid { grid-template-columns: 1fr; }
}
</style>
