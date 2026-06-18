<!-- PerformanceHub.vue — 绩效总览：密集卡片 + 排行表格 + 聚合统计 -->
<template>
  <div class="perf-page scrollbar-hide">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">绩效总览</h1>
          <p class="page-description">策略与账户绩效全景 · {{ stats.strategyCount }} 个策略</p>
        </div>
        <div class="header-actions">
          <n-button size="small" type="primary" @click="router.push('/performance/comparison')">📊 新建对比</n-button>
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
        <!-- ====== 指标卡片 6列 ====== -->
        <div class="metric-cards">
          <div class="metric-card" :class="tokens.surface.card">
            <span class="mc-label">累计收益</span>
            <span class="mc-value" :class="stats.cumulativeReturn >= 0 ? 'text-up' : 'text-down'">{{ fmtPct(stats.cumulativeReturn) }}</span>
            <span class="mc-sub">账户总盈亏</span>
          </div>
          <div class="metric-card" :class="tokens.surface.card">
            <span class="mc-label">年化收益</span>
            <span class="mc-value" :class="stats.avgAnnualReturn >= 0 ? 'text-up' : 'text-down'">{{ fmtPct(stats.avgAnnualReturn) }}</span>
            <span class="mc-sub">年化复合增长率</span>
          </div>
          <div class="metric-card" :class="tokens.surface.card">
            <span class="mc-label">夏普比率</span>
            <span class="mc-value">{{ stats.sharpeRatio.toFixed(2) }}</span>
            <span class="mc-sub">风险调整收益</span>
          </div>
          <div class="metric-card" :class="tokens.surface.card">
            <span class="mc-label">最大回撤</span>
            <span class="mc-value text-down">{{ (stats.maxDrawdown * 100).toFixed(1) }}%</span>
            <span class="mc-sub">历史最大亏损</span>
          </div>
          <div class="metric-card" :class="tokens.surface.card">
            <span class="mc-label">账户净值</span>
            <span class="mc-value">{{ stats.accountNav }}</span>
            <span class="mc-sub">当前总资产</span>
          </div>
          <div class="metric-card" :class="tokens.surface.card">
            <span class="mc-label">策略总数</span>
            <span class="mc-value">{{ stats.strategyCount }}</span>
            <span class="mc-sub">🟢{{ stats.runningCount }} 运行中</span>
          </div>
        </div>

        <!-- ====== 主体区域：排行 + 聚合 ====== -->
        <div class="body-row">
          <!-- 策略排行表（左 65%） -->
          <div class="body-left">
            <div class="section-head">
              <h3><SmartIcon name="Trophy" class="title-icon" />策略绩效排行</h3>
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
                </div>
                <div
                  v-for="(s, idx) in strategyRankings" :key="idx"
                  class="rt-row" @click="router.push(`/strategies/workspace/${s.id}`)"
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
                </div>
              </div>
            </n-card>
          </div>

          <!-- 聚合统计 + 快捷入口（右 35%） -->
          <div class="body-right">
            <!-- 聚合统计 -->
            <h4 style="margin:0 0 8px;font-size:13px;color:var(--color-text-secondary)"><SmartIcon name="Chart" class="title-icon" />策略聚合统计</h4>
            <n-card :class="tokens.surface.card" size="small">
              <div class="agg-grid">
                <div class="agg-item">
                  <span class="agg-label">夏普中位数</span>
                  <span class="agg-val">{{ aggregateStats.medianSharpe.toFixed(2) }}</span>
                </div>
                <div class="agg-item">
                  <span class="agg-label">平均回撤</span>
                  <span class="agg-val text-down">{{ (aggregateStats.avgDrawdown*100).toFixed(1) }}%</span>
                </div>
                <div class="agg-item">
                  <span class="agg-label">最佳策略</span>
                  <span class="agg-val text-up">{{ aggregateStats.bestStrategy }}</span>
                </div>
                <div class="agg-item">
                  <span class="agg-label">胜率中位数</span>
                  <span class="agg-val">{{ aggregateStats.medianWinRate }}</span>
                </div>
                <div class="agg-item">
                  <span class="agg-label">正收益策略</span>
                  <span class="agg-val text-up">{{ aggregateStats.positiveCount }} / {{ strategyRankings.length }}</span>
                </div>
                <div class="agg-item">
                  <span class="agg-label">总交易笔数</span>
                  <span class="agg-val">{{ aggregateStats.totalTrades }}</span>
                </div>
              </div>
            </n-card>

            <!-- 快捷入口 -->
            <h4 style="margin:12px 0 8px;font-size:13px;color:var(--color-text-secondary)"><SmartIcon name="Compass" class="title-icon" />分析工具</h4>
            <n-card :class="tokens.surface.card" size="small">
              <div class="quick-grid">
                <div class="quick-btn" @click="router.push('/performance/comparison')">
                  <SmartIcon name="Scale" /><span>绩效对比</span>
                </div>
                <div class="quick-btn" @click="router.push('/performance/attribution')">
                  <SmartIcon name="Puzzle" /><span>归因分析</span>
                </div>
                <div class="quick-btn" @click="router.push('/performance/strategy')">
                  <SmartIcon name="TrendingUpOutline" /><span>策略详情</span>
                </div>
                <div class="quick-btn" @click="router.push('/performance/account')">
                  <SmartIcon name="Wallet" /><span>账户绩效</span>
                </div>
              </div>
            </n-card>
          </div>
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
import strategyAPI from "@/api/strategy";
import backtestAPI from "@/api/backtest";

const router = useRouter();
const loading = ref(true);
const error = ref(false);

interface RankItem { id: string; name: string; annualReturn: number; sharpeRatio: number; maxDrawdown: number; winRate?: number; tradesCount?: number; totalReturn?: number; }
const stats = ref({ strategyCount: 0, runningCount: 0, avgAnnualReturn: 0, cumulativeReturn: 0, sharpeRatio: 0, maxDrawdown: 0, accountNav: "--" });
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

    const strategyLatestTask = new Map<string, any>();
    for (const t of completedTasks) {
      const sid = t.strategy_id;
      if (!sid) continue;
      const existing = strategyLatestTask.get(sid);
      if (!existing || (t.created_at || '') > (existing.created_at || '')) {
        strategyLatestTask.set(sid, t);
      }
    }

    // 3. 并行加载每个策略最新回测结果
    const rankings: RankItem[] = [];
    const results = await Promise.all(
      strategyList.slice(0, 15).map(async (s: any) => {
        const task = strategyLatestTask.get(s.id);
        if (!task) return null;
        const taskId = task.id || task.task_id;
        const r: any = await backtestAPI.getResult(taskId).catch(() => null);
        if (!r) return null;
        return {
          id: s.id,
          name: s.name || s.id,
          annualReturn: r.annual_return ?? 0,
          sharpeRatio: r.sharpe_ratio ?? 0,
          maxDrawdown: r.max_drawdown ?? 0,
          winRate: r.win_rate,
          tradesCount: r.num_trades ?? 0,
          totalReturn: r.total_return ?? 0,
        };
      })
    );

    for (const item of results) {
      if (item) rankings.push(item);
    }
    rankings.sort((a, b) => b.annualReturn - a.annualReturn);
    strategyRankings.value = rankings;

    // 4. 摘要卡片 — 从 rankings 聚合真实数据
    if (rankings.length > 0) {
      stats.value.avgAnnualReturn = rankings.reduce((s, r) => s + r.annualReturn, 0) / rankings.length;
      stats.value.cumulativeReturn = rankings.reduce((s, r) => s + (r.totalReturn ?? 0), 0);
      stats.value.sharpeRatio = rankings.reduce((s, r) => s + r.sharpeRatio, 0) / rankings.length;
      stats.value.maxDrawdown = Math.min(...rankings.map(r => r.maxDrawdown));
      stats.value.accountNav = '--';
    }
  } catch { error.value = true; } finally { loading.value = false; }
};

onMounted(() => loadData());
</script>

<style lang="scss" scoped>
.perf-page { height: 100%; overflow-y: auto; background: transparent; animation: fadeIn 0.3s ease-out; }
.main-content { padding: 20px 32px 32px; }

/* 指标卡片 */
.metric-cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 16px; }
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
</style>
