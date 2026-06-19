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
          <div
            v-if="report.excessMetrics && report.excessMetrics.aligned_days"
            class="benchmark-stats"
          >
            <h4 style="margin: 16px 0 10px; color: var(--n-text-color-2);">
              基准对比（{{
                report.excessMetrics.low_confidence ? "样本偏少 · " : ""
              }}对齐 {{ report.excessMetrics.aligned_days }} 个交易日）
            </h4>
            <div class="summary-stats" style="margin-top: 0;">
              <StatCard
                title="超额收益"
                :value="`${(report.excessMetrics.excess_annual_return * 100).toFixed(2)}%`"
                :trend="report.excessMetrics.excess_annual_return > 0 ? 'up' : 'down'"
              />
              <StatCard title="Alpha" :value="report.excessMetrics.alpha.toFixed(4)" />
              <StatCard title="Beta" :value="report.excessMetrics.beta.toFixed(2)" />
              <StatCard
                title="信息比率"
                :value="report.excessMetrics.information_ratio.toFixed(2)"
              />
              <StatCard
                title="基准收益"
                :value="`${(report.excessMetrics.benchmark_annual_return * 100).toFixed(2)}%`"
                :trend="report.excessMetrics.benchmark_annual_return > 0 ? 'up' : 'down'"
              />
              <StatCard
                title="跟踪误差"
                :value="`${(report.excessMetrics.tracking_error * 100).toFixed(2)}%`"
              />
            </div>
          </div>
        </div>
      </template>

      <template #content>
        <div class="section">
          <div class="section-header-row">
            <h3>净值曲线</h3>
            <n-space :size="8">
              <n-switch v-model:value="showTradeMarkers" size="small" />
              <span class="toggle-label">交易标记</span>
              <n-switch v-model:value="showTrendLines" size="small" />
              <span class="toggle-label">趋势线</span>
            </n-space>
          </div>
          <EquityCurveChart
            ref="equityChartRef"
            :data="report.equityCurve"
            :benchmark="report.benchmark"
            :show-excess="report.benchmark.length > 0"
            :height="400"
            :primitives="equityPrimitives"
          />
        </div>

        <div class="metrics-grid">
          <div class="metric-card">
            <h3>回撤分析</h3>
            <DrawdownAreaChart
              :data="report.drawdown"
              title="回撤分析"
              :height="260"
              :primitives="drawdownPrimitives"
            />
          </div>
          <div class="metric-card">
            <h3>月度收益</h3>
            <MonthlyReturnChart v-if="report.monthlyReturns.length > 0" :data="report.monthlyReturns" />
            <n-empty v-else description="暂无月度收益数据" />
          </div>
        </div>

        <div class="section">
          <h3>每日盈亏</h3>
          <DailyPnLChart :data="report.dailyReturns" :height="260" />
        </div>

        <div class="section">
          <h3>成交记录图</h3>
          <TradeRecordChart
            :trades="report.trades"
            :height="300"
            :symbol="route.params.taskId as string"
          />
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
import { useMessage, NResult, NSpin, NEmpty, NSwitch, NSpace } from "naive-ui";
import { type ISeriesPrimitive, type Time } from "lightweight-charts";
import ReportLayout from "@/layouts/ReportLayout.vue";
import EquityCurveChart from "@/components/charts/EquityCurveChart.vue";
import DrawdownAreaChart from "@/components/charts/DrawdownAreaChart.vue";
import MonthlyReturnChart from "@/components/charts/MonthlyReturnChart.vue";
import ProfitDistributionChart from "@/components/charts/ProfitDistributionChart.vue";
import DailyPnLChart from "@/components/charts/DailyPnLChart.vue";
import TradeRecordChart from "@/components/charts/TradeRecordChart.vue";
import TradeTable from "@/components/data/TradeTable.vue";
import StatCard from "@/components/common/StatCard.vue";
import backtestAPI from "@/api/backtest";
import { SignalMarkerPrimitive } from "@/components/charts/primitives/SignalMarker";
import { TrendLinePrimitive } from "@/components/charts/primitives/TrendLine";
import type { SignalMarkerData, TrendLineData } from "@/components/charts/primitives/types";
const route = useRoute();
const message = useMessage();
const store = useStore<any>();

const loading = ref(false);
const error = ref(false);
const activeTradeTab = ref("trades");

// ---- 图表标记开关 ----
const showTradeMarkers = ref(true);
const showTrendLines = ref(true);
const equityChartRef = ref<InstanceType<typeof EquityCurveChart>>();
let _markerGeneration = 0; // 每次 loadReport 递增，防止 ID 碰撞导致旧原语残留

/**
 * 从交易记录生成信号标记原语
 * 将标记叠加到净值曲线上：X=交易日期，Y=当日净值（而非股票成交价）
 * ⚠️ timeToCoordinate + priceToCoordinate 动态定位，处理节假日断点
 */
function buildTradeMarkers(
  trades: Array<{ date: string; price: number; direction: string; symbol?: string }>,
  equityCurve: Array<{ date: string; value: number }>,
): ISeriesPrimitive<Time>[] {
  // 构建日期→净值查找表
  const equityMap = new Map<string, number>();
  for (const p of equityCurve) {
    const d = (p.date?.slice(0, 10) || p.date);
    equityMap.set(d, p.value);
  }

  return trades.map((t, i) => {
    const isBuy = t.direction === "buy";
    const tradeDate = (t.date?.slice(0, 10) || t.date);
    // 查找交易当日净值，若找不到则取最近净值
    const equityValue = equityMap.get(tradeDate);
    const finalEquityValue = equityValue ?? equityCurve[equityCurve.length - 1]?.value ?? 0;

    const data: SignalMarkerData = {
      id: `trade-marker-g${_markerGeneration}-${i}`,
      type: "signalMarker",
      time: tradeDate as Time,
      price: finalEquityValue,           // ← 净值，非股票成交价
      direction: isBuy ? "buy" : "sell",
      shape: isBuy ? "arrowUp" : "arrowDown",
      color: isBuy ? "#ef5350" : "#26a69a",
      text: isBuy ? "买入" : "卖出",
      strategyName: t.symbol?.slice(0, 6),
    };
    return new SignalMarkerPrimitive(data);
  });
}

/**
 * 从净值曲线关键点生成趋势线
 * 提取起点→最高点→最低点→终点的连线，用于可视化验证
 * ⚠️ 使用 TrendLinePrimitive，坐标在每次 draw() 中通过 timeToCoordinate 动态计算
 *    时间断点期间的空白被自然处理，线条跨越断点时斜率视觉上连续
 */
function buildEquityTrendLines(
  equity: Array<{ date: string; value: number }>,
): TrendLinePrimitive[] {
  if (equity.length < 2) return [];
  const lines: TrendLinePrimitive[] = [];

  // 找到最高点和最低点
  let maxIdx = 0;
  let minIdx = 0;
  for (let i = 1; i < equity.length; i++) {
    if (equity[i].value > equity[maxIdx].value) maxIdx = i;
    if (equity[i].value < equity[minIdx].value) minIdx = i;
  }

  const first = equity[0];
  const last = equity[equity.length - 1];

  // 起点→最高点（如果是上升段）
  if (maxIdx > 0) {
    const peak = equity[maxIdx];
    lines.push(
      new TrendLinePrimitive({
        id: `tl-start-to-peak-g${_markerGeneration}`,
        type: "trendLine",
        startTime: (first.date.slice(0, 10)) as Time,
        endTime: (peak.date.slice(0, 10)) as Time,
        startPrice: first.value,
        endPrice: peak.value,
        lineColor: "rgba(255,152,0,0.5)",
        lineWidth: 1,
        lineStyle: 1, // dashed
        extendLeft: false,
        extendRight: false,
      }),
    );
  }

  // 最高点→终点
  if (maxIdx < equity.length - 1) {
    const peak = equity[maxIdx];
    lines.push(
      new TrendLinePrimitive({
        id: `tl-peak-to-end-g${_markerGeneration}`,
        type: "trendLine",
        startTime: (peak.date.slice(0, 10)) as Time,
        endTime: (last.date.slice(0, 10)) as Time,
        startPrice: peak.value,
        endPrice: last.value,
        lineColor: "rgba(239,68,68,0.4)",
        lineWidth: 1,
        lineStyle: 1,
        extendLeft: false,
        extendRight: true, // 延长射线
      }),
    );
  }

  // 起点→终点（总趋势）
  lines.push(
    new TrendLinePrimitive({
      id: `tl-start-to-end-g${_markerGeneration}`,
      type: "trendLine",
      startTime: (first.date.slice(0, 10)) as Time,
      endTime: (last.date.slice(0, 10)) as Time,
      startPrice: first.value,
      endPrice: last.value,
      lineColor: "rgba(124,58,237,0.6)",
      lineWidth: 2,
      lineStyle: 0, // solid
      extendLeft: false,
      extendRight: true,
    }),
  );

  return lines;
}

/** 动态计算净值曲线原语（响应开关状态） */
const equityPrimitives = computed<ISeriesPrimitive<Time>[]>(() => {
  const prims: ISeriesPrimitive<Time>[] = [];

  if (showTradeMarkers.value && report.value.trades.length > 0) {
    prims.push(...buildTradeMarkers(report.value.trades, report.value.equityCurve));
  }

  if (showTrendLines.value && report.value.equityCurve.length >= 2) {
    prims.push(...buildEquityTrendLines(report.value.equityCurve));
  }

  return prims;
});

/** 回撤曲线原语：标注最大回撤点 */
const drawdownPrimitives = computed<ISeriesPrimitive<Time>[]>(() => {
  if (!showTrendLines.value) return [];
  const dd = report.value.drawdown;
  if (dd.length === 0) return [];

  // 找到最大回撤点
  let worstIdx = 0;
  for (let i = 1; i < dd.length; i++) {
    if (dd[i].value < dd[worstIdx].value) worstIdx = i;
  }
  const worst = dd[worstIdx];

  return [
    new SignalMarkerPrimitive({
      id: `max-drawdown-marker-g${_markerGeneration}`,
      type: "signalMarker",
      time: (worst.date.slice(0, 10)) as Time,
      price: worst.value,
      direction: "sell",
      shape: "circle",
      color: "#ef4444",
      text: `最大回撤 ${(worst.value * 100).toFixed(1)}%`,
    }),
  ];
});

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
  dailyReturns: [] as any[],
  dailyTurnover: [] as any[],
  profitDistribution: { bins: [] as number[], counts: [] as number[] },
  trades: [] as any[],
  excessMetrics: null as Record<string, any> | null,
});

const strategy = computed(
  () => store.state.strategy?.currentStrategy || { name: "未知策略" },
);

const loadReport = async () => {
  const taskId = route.params.taskId as string;
  if (!taskId) { error.value = true; return; }
  loading.value = true;
  error.value = false;
  _markerGeneration++; // 递增代次，确保重新加载时原语 ID 不碰撞
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
        value: p.total_assets || (p.cumulative_return ? (1 + p.cumulative_return) * 100000 : p.value || 0),
      })),
      drawdown: (r.drawdown_curve || []).map((p: any) => ({
        date: p.trade_date || p.date,
        value: p.drawdown || p.max_drawdown || 0,
      })),
      monthlyReturns: (r.monthly_returns || []).map((p: any) => ({
        month: p.month || p.trade_date || "",
        return: p.return || p.monthly_return || 0,
      })),
      dailyReturns: (r.daily_returns || []).map((p: any) => ({
        trade_date: p.trade_date || p.date || "",
        daily_return: p.daily_return ?? 0,
        daily_pnl: p.daily_pnl ?? 0,
      })),
      dailyTurnover: (r.daily_turnover || []).map((p: any) => ({
        trade_date: p.trade_date || p.date || "",
        turnover: p.turnover ?? 0,
      })),
      profitDistribution: aggregateProfitDistribution(tr),
      excessMetrics: r.excess_metrics && Object.keys(r.excess_metrics).length > 0
        ? r.excess_metrics
        : null,
      trades: tr.map((t: any) => {
        const side = t.side || t.direction || '';
        const qty = Number(t.volume || t.quantity || 0);
        const px = Number(t.price || 0);
        // v1.4: 读取实际手续费（Broker 在 match_orders 中计算）
        const commission = Number(t.commission || 0);
        const stampTax = Number(t.stamp_tax || 0);
        const transferFee = Number(t.transfer_fee || 0);
        return {
          id: t.id || t.trade_id,
          symbol: t.symbol || t.ts_code || '',
          name: t.symbol || t.ts_code || '',
          direction: (side === 'LONG' || side === 'buy') ? 'buy' : 'sell',
          date: t.datetime || t.trade_date || t.date || '',
          price: px,
          quantity: qty,
          amount: px * qty,
          fee: commission + stampTax + transferFee,
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
.section-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-header-row h3 {
  margin-bottom: 0;
}
.toggle-label {
  font-size: 12px;
  color: var(--n-text-color-3);
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
