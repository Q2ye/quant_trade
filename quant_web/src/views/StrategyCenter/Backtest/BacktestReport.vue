<template>
  <n-spin :show="loading" class="backtest-report-page">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取回测报告失败，请稍后重试"
    >
      <template #footer><n-button @click="loadReport">重试</n-button></template>
    </n-result>

    <ReportLayout v-else>
      <template #header>
        <div class="report-header">
          <h2>{{ strategy.name }} - 回测报告</h2>
          <div class="summary-stats">
            <StatCard
              title="年化收益"
              :value="`${(report.summary.annualReturn * 100).toFixed(2)}%`"
              :trend="report.summary.annualReturn > 0 ? 'up' : 'down'"
            />
            <StatCard
              title="累计收益"
              :value="`${(report.summary.totalReturn * 100).toFixed(2)}%`"
              :trend="report.summary.totalReturn > 0 ? 'up' : 'down'"
            />
            <StatCard
              title="最大回撤"
              :value="`${(report.summary.maxDrawdown * 100).toFixed(2)}%`"
              trend="down"
            />
            <StatCard
              title="夏普比率"
              :value="report.summary.sharpeRatio.toFixed(2)"
            />
            <StatCard
              title="胜率"
              :value="`${(report.summary.winRate * 100).toFixed(1)}%`"
            />
          </div>
        </div>
      </template>

      <template #content>
        <div class="section">
          <h3>净值曲线</h3>
          <EquityCurveChart
            :data="report.equityCurve"
            :benchmark="report.benchmark"
            title="净值曲线"
            subtitle="策略净值 vs 基准走势"
            :height="400"
          />
        </div>

        <div class="metrics-grid">
          <div class="metric-card">
            <h3>回撤分析</h3>
            <DrawdownAreaChart :data="report.drawdown" title="回撤分析" :height="260" />
          </div>
          <div class="metric-card">
            <h3>月度收益</h3>
            <MonthlyReturnChart v-if="report.monthlyReturns.length > 0" :data="report.monthlyReturns" />
            <n-empty v-else description="暂无月度收益数据" />
          </div>
        </div>

        <div class="section">
          <h3>交易分析</h3>
          <n-tabs v-model:value="activeTradeTab">
            <n-tab-pane name="trades" tab="交易列表">
              <TradeTable :trades="report.trades" />
            </n-tab-pane>
            <n-tab-pane name="distribution" tab="收益分布">
              <n-empty v-if="report.profitDistribution.bins.length === 0" description="收益分布由交易列表聚合计算" />
              <ProfitDistributionChart v-else :data="report.profitDistribution" />
            </n-tab-pane>
          </n-tabs>
        </div>
      </template>

      <template #footer>
        <div class="report-footer">
          <n-space justify="center" :size="12">
            <n-button type="primary" @click="saveReport">保存报告</n-button>
            <n-button @click="exportPDF">导出PDF</n-button>
            <n-button @click="addToBasket">加入股票篮子</n-button>
          </n-space>
        </div>
      </template>
    </ReportLayout>
  </n-spin>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { useStore } from "vuex";
import { useMessage, NResult, NSpin, NEmpty } from "naive-ui";
import ReportLayout from "@/layouts/ReportLayout.vue";
import EquityCurveChart from "@/components/charts/EquityCurveChart.vue";
import DrawdownAreaChart from "@/components/charts/DrawdownAreaChart.vue";
import MonthlyReturnChart from "@/components/charts/MonthlyReturnChart.vue";
import ProfitDistributionChart from "@/components/charts/ProfitDistributionChart.vue";
import TradeTable from "@/components/data/TradeTable.vue";
import StatCard from "@/components/common/StatCard.vue";
import backtestAPI from "@/api/backtest";

const route = useRoute();
const message = useMessage();
const store = useStore<any>();

const loading = ref(false);
const error = ref(false);
const activeTradeTab = ref("trades");

/** 从 trades 列表聚合收益分布（后端不直接返回此字段） */
const aggregateProfitDistribution = (trades: any[]) => {
  if (!trades || trades.length === 0) return { bins: [], counts: [] };
  const buyMap = new Map<string, { price: number; quantity: number }>();
  const profitRates: number[] = [];

  for (const t of trades) {
    const key = t.ts_code || t.symbol;
    const dir = t.direction === "LONG" || t.direction === "buy" ? "buy" : "sell";
    const price = Number(t.price || 0);
    const qty = Number(t.quantity || 0);
    if (dir === "buy") {
      const prev = buyMap.get(key);
      if (prev) {
        const totalQty = prev.quantity + qty;
        const avgPrice = (prev.price * prev.quantity + price * qty) / totalQty;
        buyMap.set(key, { price: avgPrice, quantity: totalQty });
      } else {
        buyMap.set(key, { price, quantity: qty });
      }
    } else if (dir === "sell") {
      const entry = buyMap.get(key);
      if (entry && entry.quantity > 0) {
        const pnlRate = (price - entry.price) / entry.price;
        profitRates.push(pnlRate);
        buyMap.set(key, { price: entry.price, quantity: entry.quantity - qty });
      }
    }
  }

  if (profitRates.length === 0) return { bins: [], counts: [] };
  const min = Math.floor(Math.min(...profitRates) * 100) / 100;
  const max = Math.ceil(Math.max(...profitRates) * 100) / 100;
  const step = Math.max((max - min) / 6, 0.01);
  const bins: number[] = [];
  for (let v = min; v <= max + step / 2; v += step) bins.push(Math.round(v * 100) / 100);
  const counts = new Array(bins.length - 1).fill(0);
  for (const r of profitRates) {
    let idx = bins.length - 2;
    for (let i = 0; i < bins.length - 1; i++) {
      if (r >= bins[i] && r < bins[i + 1]) { idx = i; break; }
    }
    counts[idx]++;
  }
  return { bins, counts };
};

const report = ref({
  summary: {
    annualReturn: 0,
    totalReturn: 0,
    maxDrawdown: 0,
    sharpeRatio: 0,
    winRate: 0,
    profitFactor: 0,
    tradesCount: 0,
    avgTradeReturn: 0,
  },
  equityCurve: [] as any[],
  benchmark: [] as any[],
  drawdown: [] as any[],
  monthlyReturns: [] as any[],
  profitDistribution: { bins: [] as number[], counts: [] as number[] },
  trades: [] as any[],
});

const strategy = computed(
  () => store.state.strategy?.currentStrategy || { name: "未知策略" },
);

const loadReport = async () => {
  const taskId = route.params.taskId as string;
  if (!taskId) { error.value = true; return; }
  loading.value = true;
  error.value = false;
  try {
    const [result, equity, trades] = await Promise.all([
      backtestAPI.getResult(taskId).catch(() => null),
      backtestAPI.getEquityCurve(taskId).catch(() => []),
      backtestAPI.getTrades(taskId).catch(() => []),
    ]);

    const r: Record<string, any> = result || {};
    const eq = Array.isArray(equity) ? equity : [];
    const tr = Array.isArray(trades) ? trades : [];

    report.value = {
      summary: {
        annualReturn: r.annual_return ?? 0,
        totalReturn: r.total_return ?? 0,
        maxDrawdown: r.max_drawdown ?? 0,
        sharpeRatio: r.sharpe_ratio ?? 0,
        winRate: r.win_rate ?? 0,
        profitFactor: r.profit_factor ?? 0,
        tradesCount: r.num_trades ?? tr.length,
        avgTradeReturn: r.avg_trade_return ?? 0,
      },
      equityCurve: eq.map((p: any) => ({
        date: p.trade_date || p.date,
        value: p.total_assets || p.equity || 0,
      })),
      benchmark: (r.benchmark_curve || []).map((p: any) => ({
        date: p.trade_date || p.date,
        value: p.cumulative_return ? (1 + p.cumulative_return) * 100000 : p.value || 0,
      })),
      drawdown: (r.drawdown_curve || []).map((p: any) => ({
        date: p.trade_date || p.date,
        value: p.drawdown || p.max_drawdown || 0,
      })),
      monthlyReturns: (r.monthly_returns || []).map((p: any) => ({
        month: p.month || p.trade_date || "",
        return: p.return || p.monthly_return || 0,
      })),
      profitDistribution: aggregateProfitDistribution(tr),
      trades: tr.map((t: any) => {
        const side = t.side || t.direction || '';
        const qty = Number(t.volume || t.quantity || 0);
        const px = Number(t.price || 0);
        return {
          id: t.id || t.trade_id,
          symbol: t.symbol || t.ts_code || '',
          name: t.symbol || t.ts_code || '',
          direction: (side === 'LONG' || side === 'buy') ? 'buy' : 'sell',
          date: t.datetime || t.trade_date || t.date || '',
          price: px,
          quantity: qty,
          amount: px * qty,
          fee: 0,
        };
      }),
    };
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const saveReport = () => {
  const taskId = route.params.taskId as string;
  store.dispatch("strategy/saveBacktestReport", {
    id: taskId,
    report: report.value,
  });
  message.success("回测报告已保存");
};
const exportPDF = () => message.info("PDF导出功能正在开发中");
const addToBasket = () => {
  const taskId = route.params.taskId as string;
  store.dispatch("basket/createBasketFromReport", {
    reportId: taskId,
    basketName: `${strategy.value.name}_股票池`,
  });
  message.success(`已创建股票篮子: ${strategy.value.name}_股票池`);
};

onMounted(() => { loadReport(); });
</script>

<style scoped>
.report-header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--n-border-color);
}
.report-header h2 {
  color: var(--n-text-color-1);
}
.summary-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
  margin-top: 20px;
}

.section {
  margin-bottom: 30px;
  padding: 20px;
  background: var(--n-card-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.section h3 {
  color: var(--n-text-color-1);
  margin-bottom: 16px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
}
.metric-card {
  padding: 20px;
  background: var(--n-card-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.metric-card h3 {
  color: var(--n-text-color-1);
  margin-bottom: 16px;
}

.report-footer {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--n-border-color);
}
</style>
