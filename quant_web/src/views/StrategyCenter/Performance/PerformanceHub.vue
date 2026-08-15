<!-- PerformanceHub.vue — 绩效总览：密集卡片 + 排行表格 + 聚合统计 -->
<template>
  <div class="perf-page scrollbar-hide">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">绩效总览</h1>
          <p class="page-description">策略回测绩效排名 · {{ stats.strategyCount }} 个策略 · {{ stats.rankedCount }} 有回测</p>
        </div>
        <div class="header-actions">
          <n-button size="small" :loading="loading" @click="loadData">刷新</n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading / Error -->
      <template v-if="loading">
        <div class="metric-cards"><n-card v-for="i in 6" :key="i" :class="tokens.surface.card" size="small"><n-skeleton text :repeat="2" /></n-card></div>
        <n-card :class="tokens.surface.card" style="margin-top:12px"><n-skeleton text :repeat="8" /></n-card>
      </template>
      <n-result v-else-if="error" status="500" title="加载失败">
        <template #footer><n-button type="primary" @click="loadData">重试</n-button></template>
      </n-result>

      <template v-else>
        <!-- 策略回测排名表 → 点击直达回测报告 -->
        <div class="section-head">
          <h3><SmartIcon name="Trophy" class="title-icon" />策略回测绩效排行</h3>
          <n-tag size="tiny" v-if="strategyRankings.length > 0">Top {{ strategyRankings.length }}</n-tag>
        </div>
        <n-card :class="tokens.surface.card" size="small" content-class="!p-0">
          <n-empty v-if="strategyRankings.length === 0" description="暂无绩效数据，请先运行回测" style="padding:20px" />
          <div v-else class="rank-table">
            <div class="rt-header">
              <span class="rt-col col-rank">#</span>
              <span class="rt-col col-name">策略</span>
              <span class="rt-col col-metric">年化收益</span>
              <span class="rt-col col-metric">夏普</span>
              <span class="rt-col col-metric">最大回撤</span>
              <span class="rt-col col-metric">胜率</span>
              <span class="rt-col col-metric">交易</span>
              <span class="rt-col col-date">回测日期</span>
            </div>
            <div
              v-for="(s, idx) in strategyRankings" :key="idx"
              class="rt-row" @click="goReport(s)"
            >
              <span class="rt-col col-rank">
                <span :class="['rank-badge', idx < 3 ? `top-${idx+1}` : '']">{{ idx + 1 }}</span>
              </span>
              <span class="rt-col col-name">{{ s.name }}</span>
              <span class="rt-col col-metric" :class="s.annualReturn >= 0 ? 'text-up' : 'text-down'">{{ (s.annualReturn*100).toFixed(1) }}%</span>
              <span class="rt-col col-metric">{{ (s.sharpeRatio||0).toFixed(2) }}</span>
              <span class="rt-col col-metric text-down">{{ ((s.maxDrawdown||0)*100).toFixed(1) }}%</span>
              <span class="rt-col col-metric">{{ s.winRate ? (s.winRate*100).toFixed(0)+'%' : '--' }}</span>
              <span class="rt-col col-metric">{{ s.tradesCount || '--' }}</span>
              <span class="rt-col col-date">{{ s.taskDate || '--' }}</span>
            </div>
          </div>
        </n-card>
        <!-- 口径标注（2026-08 C4：绩效口径统一） -->
        <div class="metric-footnote">
          口径：夏普 = 日频超额收益 × √252（无风险利率 2%）；年化 = 252 交易日几何复合；最大回撤以负值表示（-15% = 回撤 15%）
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCard, NTag, NSkeleton, NEmpty, NResult } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import request from "@/utils/request";
import strategyAPI from "@/api/strategy";
import backtestAPI from "@/api/backtest";

const router = useRouter();
const loading = ref(true);
const error = ref(false);

interface RankItem { id: string; name: string; taskId?: string; taskDate?: string; annualReturn: number; sharpeRatio: number; maxDrawdown: number; winRate?: number; tradesCount?: number; totalReturn?: number; }

// 点击排名行 → 直达该策略最新回测任务报告
const goReport = (s: RankItem) => {
  if (s.taskId) router.push(`/backtest/report/${s.taskId}`);
};
const stats = ref({ strategyCount: 0, runningCount: 0, rankedCount: 0, avgAnnualReturn: 0, cumulativeReturn: 0, sharpeRatio: 0, maxDrawdown: 0, accountNav: "--" });
const strategyRankings = ref<RankItem[]>([]);

const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

const aggregateStats = computed(() => {
  const r = strategyRankings.value;
  if (r.length === 0) return { medianSharpe: 0, avgDrawdown: 0, bestStrategy: "--", medianWinRate: "--", positiveCount: 0, totalTrades: 0 };
  const sharpes = r.map(s => s.sharpeRatio || 0).sort((a,b) => a-b);
  const medianSharpe = sharpes[Math.floor(sharpes.length/2)];
  const avgDrawdown = r.reduce((sum, s) => sum + (s.maxDrawdown||0), 0) / r.length;
  const best = r.reduce((a,b) => (a.annualReturn||0) > (b.annualReturn||0) ? a : b);
  const winRates = r.filter(s => s.winRate != null).map(s => s.winRate!);
  const medianWinRate = winRates.length > 0 ? `${((winRates.sort((a,b)=>a-b)[Math.floor(winRates.length/2)]||0)*100).toFixed(0)}%` : "--";
  const positiveCount = r.filter(s => (s.annualReturn||0) > 0).length;
  const totalTrades = r.reduce((sum, s) => sum + (s.tradesCount||0), 0);
  return { medianSharpe, avgDrawdown, bestStrategy: best.name||"--", medianWinRate, positiveCount, totalTrades };
});

const loadData = async () => {
  loading.value = true; error.value = false;
  try {
    // 1. 获取策略列表
    const strategies = await strategyAPI.getStrategies().catch(() => []);
    const strategyList = Array.isArray(strategies) ? strategies : [];
    stats.value.strategyCount = strategyList.length;
    stats.value.runningCount = strategyList.filter((s: any) => s.status === "running").length;

    // 2. 获取所有已完成回测任务，构建 per-strategy 最新完成任务映射
    const tasksRes: any = await backtestAPI.getTasks({ page_size: 200 }).catch(() => ({}));
    const taskItems: any[] = Array.isArray(tasksRes) ? tasksRes : (tasksRes?.data || tasksRes?.items || []);
    const completedTasks = taskItems.filter((t: any) => t.status === 'completed');

    // 3. 批量加载全部已完成任务结果（用于按净值窗口选最长回测；列表 config 为空，无法用配置算窗口）
    const allTaskIds = completedTasks.map((t: any) => t.id || t.task_id);
    const batchResults: Record<string, any> = allTaskIds.length > 0
      ? await backtestAPI.getBatchResults(allTaskIds).catch(() => ({}))
      : {};

    // 窗口跨度：用 result.equity_curve 首末日期（最代表实际回测区间）
    const taskSpan = (r: any) => {
      const ec = r?.equity_curve || [];
      if (ec.length >= 2) {
        const f = new Date(ec[0].trade_date || ec[0].date);
        const l = new Date(ec[ec.length - 1].trade_date || ec[ec.length - 1].date);
        if (!isNaN(f.getTime()) && !isNaN(l.getTime())) return l.getTime() - f.getTime();
      }
      return 0;
    };
    // 每策略选「净值窗口最长」的已完成回测（避免冒烟/参数扫描短窗口抢占）
    const strategyBest = new Map<string, { task: any; result: any; span: number }>();
    for (const t of completedTasks) {
      const sid = t.strategy_id;
      if (!sid) continue;
      const tid = t.id || t.task_id;
      const r = batchResults[tid];
      const span = taskSpan(r);
      const existing = strategyBest.get(sid);
      if (!existing || span > existing.span) {
        strategyBest.set(sid, { task: t, result: r, span });
      }
    }

    const rankings: RankItem[] = [];
    for (const s of strategyList.slice(0, 15)) {
      const best = strategyBest.get(s.id);
      if (!best) continue;
      const { task, result: r } = best;
      if (!r) continue;
      rankings.push({
        id: s.id,
        name: s.name || s.id,
        taskId: task.id || task.task_id,
        taskDate: (task.created_at || "").slice(0, 10),
        annualReturn: r.annual_return ?? 0,
        sharpeRatio: r.sharpe_ratio ?? 0,
        maxDrawdown: r.max_drawdown ?? 0,
        winRate: r.win_rate,
        tradesCount: r.num_trades ?? 0,
        totalReturn: r.total_return ?? 0,
      });
    }
    rankings.sort((a, b) => b.annualReturn - a.annualReturn);
    strategyRankings.value = rankings;

    // 4. 摘要卡片 — 从 rankings 聚合真实数据（回测口径，标注"平均/最差"）
    stats.value.rankedCount = rankings.length;
    if (rankings.length > 0) {
      stats.value.avgAnnualReturn = rankings.reduce((s, r) => s + r.annualReturn, 0) / rankings.length;
      // 修复：累计收益用「平均」而非「求和」（求和会虚高）
      stats.value.cumulativeReturn = rankings.reduce((s, r) => s + (r.totalReturn ?? 0), 0) / rankings.length;
      stats.value.sharpeRatio = rankings.reduce((s, r) => s + r.sharpeRatio, 0) / rankings.length;
      // 最差策略回撤（组合/账户回撤需账户净值计算，此处明确为最差单策略）
      stats.value.maxDrawdown = Math.min(...rankings.map(r => r.maxDrawdown));
    }

    // 5. 账户总净值（真实数据：账户列表 total_balance 求和）
    try {
      const accRes: any = await request.get("/quantTrade/account/list", { params: { page: 1, page_size: 100 } }).catch(() => null);
      const accList = accRes?.data?.data || accRes?.data || [];
      const totalNav = Array.isArray(accList)
        ? accList.reduce((sum: number, a: any) => sum + (Number(a.total_balance ?? a.total_asset ?? 0) || 0), 0)
        : 0;
      stats.value.accountNav = totalNav > 0 ? totalNav.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : "--";
    } catch { /* 账户数据不可用时保持 -- */ }
  } catch { error.value = true; } finally { loading.value = false; }
};

onMounted(() => loadData());
</script>

<style lang="scss" scoped>
.perf-page { height: 100%; overflow-y: auto; background: transparent; animation: fadeIn 0.3s ease-out; }
.main-content { padding: 0 19px 24px; }

/* 指标卡片 */
.metric-cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 16px; }
@media (max-width: 1400px) { .metric-cards { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 768px) { .metric-cards { grid-template-columns: repeat(2, 1fr); } }
.run-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--n-success-color); margin-right: 4px; vertical-align: middle;
}
.metric-card {
  padding: 12px 14px; border-radius: 8px; background: var(--color-bg-card, rgba(12,18,32,0.72));
  border: 1px solid rgba(255,255,255,0.06); backdrop-filter: blur(8px);
  .mc-label { font-size: 11px; color: var(--color-text-tertiary); display: block; margin-bottom: 4px; }
  .mc-value { font-size: 20px; font-weight: 700; color: var(--color-text-primary); display: block; }
  .mc-sub { font-size: 10px; color: var(--color-text-tertiary); margin-top: 2px; display: block; }
}

/* 主体双栏 */
.body-row { display: flex; gap: 14px; }
.body-left { flex: 1; min-width: 0; }
.body-right { width: 280px; flex-shrink: 0; }

.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;
  h3 { margin: 0; font-size: 14px; color: var(--color-text-primary); display: flex; align-items: center; gap: 6px; }
}
.title-icon { font-size: 15px; color: var(--color-primary, #7C3AED); }

/* 排行表格 */
.rank-table { font-size: 12px; }
.rt-header, .rt-row { display: flex; align-items: center; padding: 7px 12px; }
.rt-header { font-weight: 600; color: var(--color-text-tertiary); border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 11px; }
.rt-row { cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.03); transition: background 0.12s;
  &:hover { background: rgba(124,111,247,0.05); }
  &:last-child { border-bottom: none; }
}
.rt-col { flex-shrink: 0; }
.col-rank { width: 32px; text-align: center; }
.col-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; color: var(--color-text-primary); }
.col-metric { width: 72px; text-align: right; color: var(--color-text-secondary); font-weight: 500; }
.col-date { width: 90px; text-align: right; color: var(--color-text-tertiary); font-size: 11px; }
.rank-badge { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; font-size: 11px; font-weight: 700; color: var(--color-text-tertiary); background: rgba(255,255,255,0.05);
  &.top-1 { background: #FFD700; color: #000; } &.top-2 { background: #C0C0C0; color: #000; } &.top-3 { background: #CD7F32; color: #fff; }
}

/* 聚合统计 */
.agg-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.agg-item {
  text-align: center; padding: 6px 4px;
  .agg-label { font-size: 11px; color: var(--color-text-tertiary); display: block; margin-bottom: 3px; }
  .agg-val { font-size: 15px; font-weight: 700; color: var(--color-text-primary); }
}

/* 快捷入口 */
.quick-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.quick-btn { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; color: var(--color-text-secondary); background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.04); transition: all 0.15s;
  &:hover { border-color: var(--color-primary, #7C3AED); color: var(--color-primary, #7C3AED); background: rgba(124,111,247,0.08); }
}

.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }
.metric-footnote { margin: 6px 0 0; font-size: 12px; color: var(--color-text-tertiary); line-height: 1.6; }
</style>
