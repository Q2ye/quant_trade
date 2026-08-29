<template>
  <n-spin :show="loading" class="backtest-report-page bg-gradient-mesh bg-noise">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取回测报告失败，请稍后重试"
    >
      <template #footer><n-button @click="loadReport">重试</n-button></template>
    </n-result>

    <template v-else>
      <div class="page-header">
        <div class="header-content">
          <div class="title-section">
            <h1 class="page-title">{{ strategyName ? strategyName + ' · ' : '' }}回测报告</h1>
            <p class="page-description">{{ rangeLabel }}</p>
          </div>
          <div class="header-actions">
            <n-button class="action-btn" @click="router.back()" quaternary>
              <template #icon><SmartIcon name="ArrowLeft" /></template>
            </n-button>
          </div>
        </div>
      </div>
      <div class="main-content">
        <div class="report-body">
          <div class="report-header">
            <h3 class="report-section-title">核心指标</h3>
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
            <StatCard title="波动率" :value="`${(report.summary.volatility * 100).toFixed(1)}%`" />
            <StatCard title="盈亏比" :value="report.summary.profitFactor ? report.summary.profitFactor.toFixed(2) : '--'" />
            <StatCard title="平均单笔" :value="report.summary.avgTradeReturn ? `¥${report.summary.avgTradeReturn.toFixed(0)}` : '--'" />
            <StatCard title="卡玛比率" :value="report.summary.calmarRatio ? report.summary.calmarRatio.toFixed(2) : '--'" />
            <StatCard title="平均持仓" :value="report.summary.avgHoldingDays ? `${report.summary.avgHoldingDays.toFixed(1)} 天` : '--'" />
          </div>
          <!-- 口径标注（2026-08 C4：绩效口径统一） -->
          <div class="metric-footnote">
            口径：夏普 = 日频超额收益 × √252（无风险利率 2%）；年化 = 252 交易日几何复合；最大回撤以负值表示（-15% = 回撤 15%）
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
        <div class="report-sections">
        <n-alert
          v-if="report.riskViolations.length > 0"
          type="warning"
          title="风控违规记录"
          style="margin-bottom: 12px"
        >
          <div v-for="(rv, i) in report.riskViolations" :key="i" style="font-size: 12px">
            {{ rv.rule_name || rv.message || JSON.stringify(rv) }}
          </div>
        </n-alert>
        <div class="section">
          <div class="section-header-row">
            <h3>净值曲线</h3>
          </div>
          <EquityCurveChart
            :data="report.equityCurve"
            :benchmark="report.benchmark"
            :drawdown="report.drawdown"
            :show-excess="report.benchmark.length > 0"
            :height="400"
          />
        </div>

        <div class="metrics-grid">
          <div class="metric-card metric-card-full">
            <div class="metric-card-header">
              <h3>月度收益</h3>
              <div class="monthly-toggle">
                <n-radio-group v-model:value="monthlyUnit" size="small">
                  <n-radio-button value="percent">百分比</n-radio-button>
                  <n-radio-button value="amount">金额</n-radio-button>
                </n-radio-group>
              </div>
            </div>
            <MonthlyReturnChart v-if="report.monthlyReturns.length > 0" :data="monthlyDisplayData" :unit="monthlyUnit" :title="''" :height="300" />
            <n-empty v-if="report.monthlyReturns.length === 0" description="暂无月度收益数据" />
            <div v-if="monthlyAnalysis" class="monthly-analysis">
              正收益月 <b>{{ monthlyAnalysis.pos }}</b>/{{ monthlyAnalysis.total }}（{{ (monthlyAnalysis.winRate * 100).toFixed(0) }}%），
              最佳 <b class="text-up">{{ monthlyAnalysis.best.month }} +{{ (monthlyAnalysis.best.return * 100).toFixed(1) }}%</b>，
              最差 <b class="text-down">{{ monthlyAnalysis.worst.month }} {{ (monthlyAnalysis.worst.return * 100).toFixed(1) }}%</b>，
              最长连续正收益 {{ monthlyAnalysis.maxConsecPos }} 月
            </div>
          </div>
          <div class="metric-card">
            <h3>分年度表现</h3>
            <table v-if="report.yearlyReturns.length > 0" class="yearly-table">
              <thead>
                <tr><th>年份</th><th>收益</th><th>最大回撤</th><th>市场情况</th><th>策略表现</th><th>归因分析</th></tr>
              </thead>
              <tbody>
                <tr v-for="y in report.yearlyReturns" :key="y.year">
                  <td>{{ y.year }}</td>
                  <td :style="{ color: y.return >= 0 ? 'var(--n-error-color)' : 'var(--n-success-color)' }">
                    {{ (y.return * 100).toFixed(1) }}%
                  </td>
                  <!-- 回撤统一负值口径（与主卡/注脚一致） -->
                  <td>{{ (-y.max_drawdown * 100).toFixed(1) }}%</td>
                  <!-- 市场情况（当年 regime 分布，来自 CSI500 vs MA250） -->
                  <td>{{ regimeLabelForYear(y.year) }}</td>
                  <!-- 策略表现：相对 CSI500 的超额收益（跑赢/跑输） -->
                  <td>
                    <span :class="(y.return - (csi500YearlyReturn[String(y.year)] ?? 0)) >= 0 ? 'text-up' : 'text-down'">
                      {{ (y.return - (csi500YearlyReturn[String(y.year)] ?? 0)) >= 0 ? '跑赢' : '跑输' }}
                      {{ ((y.return - (csi500YearlyReturn[String(y.year)] ?? 0)) * 100).toFixed(1) }}%
                    </span>
                  </td>
                  <!-- 归因分析（顺逆风 + α 有无 → 结论） -->
                  <td>{{ yearAttribution(y) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="yearlyConclusion" class="yearly-conclusion">
              正收益年 <b>{{ yearlyConclusion.pos }}</b>/{{ yearlyConclusion.total }}，
              最佳 <b class="text-up">{{ yearlyConclusion.best.year }} +{{ (yearlyConclusion.best.return * 100).toFixed(1) }}%</b>，
              最差 <b class="text-down">{{ yearlyConclusion.worst.year }} {{ (yearlyConclusion.worst.return * 100).toFixed(1) }}%</b>
            </div>
            <n-empty v-else description="样本不足（回测区间不足一年）" :size="'small'" />
          </div>
          <div class="metric-card">
            <h3>回撤区间与连续亏损</h3>
            <template v-if="report.maxDrawdownPeriod.start">
              <p class="drawdown-info-line">
                最大回撤区间：<strong>{{ report.maxDrawdownPeriod.start }} ~ {{ report.maxDrawdownPeriod.end }}</strong>
                （<strong>{{ (-report.maxDrawdownPeriod.depth * 100).toFixed(1) }}%</strong>）
              </p>
              <p class="drawdown-info-line">连续亏损月份：<strong>{{ report.maxConsecutiveLosses }} 个月</strong></p>
              <p class="drawdown-info-line">
                月度分布：正收益月 <strong>{{ monthlyWinMonths }}</strong> 个 / 负收益月 <strong>{{ monthlyLossMonths }}</strong> 个（占比 {{ monthlyWinPct }}%，详见上方月度收益图）
              </p>
              <!-- 行情背景归因（A2-④：市场同期涨跌 + 结论） -->
              <p v-if="drawdownMarketContext" class="drawdown-info-line">
                行情背景：同期 CSI500
                <strong :class="(drawdownMarketContext.csiRet ?? 0) < 0 ? 'text-down' : 'text-up'">{{ ((drawdownMarketContext.csiRet ?? 0) * 100).toFixed(1) }}%</strong>
                / 沪深300
                <strong :class="(drawdownMarketContext.hsRet ?? 0) < 0 ? 'text-down' : 'text-up'">{{ ((drawdownMarketContext.hsRet ?? 0) * 100).toFixed(1) }}%</strong>
                <strong>{{ ((drawdownMarketContext.csiRet ?? 0) < -0.05 || (drawdownMarketContext.hsRet ?? 0) < -0.05) ? '——市场下跌拖累为主' : '——策略自身因素为主' }}</strong>
              </p>
              <!-- 结论与建议 -->
              <p v-if="drawdownConclusion" class="drawdown-info-line drawdown-conclusion">
                结论：回撤<strong>{{ drawdownConclusion.severity }}</strong>（{{ (drawdownConclusion.depth * 100).toFixed(1) }}%，连续亏损 {{ drawdownConclusion.consec }} 月），{{ drawdownConclusion.cause }}。<br />
                建议：{{ drawdownConclusion.advice }}
              </p>
            </template>
            <n-empty v-else description="样本不足" :size="'small'" />
          </div>
        </div>

        <div class="section">
          <h3>每日盈亏</h3>
          <DailyPnLChart :data="report.dailyReturns" :height="260" :title="''" />
          <!-- 诊断区块：尾部风险 / 分布偏度 / 收益集中度 / 连续亏损 / 基准相关性 -->
          <div v-if="dailyPnLDiagnostics" class="pnl-diagnostic">
            <div class="diag-grid">
              <div class="diag-item">
                <span class="diag-label">单日最大盈利</span>
                <span class="diag-value text-up">¥{{ (dailyPnLDiagnostics.maxWin / 1e4).toFixed(2) }}万</span>
              </div>
              <div class="diag-item">
                <span class="diag-label">单日最大亏损</span>
                <span class="diag-value text-down">¥{{ (dailyPnLDiagnostics.maxLoss / 1e4).toFixed(2) }}万</span>
              </div>
              <div class="diag-item">
                <span class="diag-label">亏损超 -3% 天数</span>
                <span class="diag-value">{{ dailyPnLDiagnostics.lossOver3Pct }} 天</span>
              </div>
              <div class="diag-item">
                <span class="diag-label">日胜率</span>
                <span class="diag-value">{{ (dailyPnLDiagnostics.winRate * 100).toFixed(1) }}%</span>
              </div>
              <div class="diag-item">
                <span class="diag-label">收益分布偏度</span>
                <span class="diag-value">{{ dailyPnLDiagnostics.skew > 0.2 ? '右偏' : dailyPnLDiagnostics.skew < -0.2 ? '左偏' : '近对称' }}（{{ dailyPnLDiagnostics.skew.toFixed(2) }}）</span>
              </div>
              <div class="diag-item">
                <span class="diag-label">收益集中度</span>
                <span class="diag-value" :class="dailyPnLDiagnostics.concentration < 0.5 ? 'text-down' : ''">去掉最好/最差 10 天后剩 {{ (dailyPnLDiagnostics.concentration * 100).toFixed(0) }}%</span>
              </div>
              <div class="diag-item">
                <span class="diag-label">最长连续亏损</span>
                <span class="diag-value">{{ dailyPnLDiagnostics.maxConsecLoss }} 天</span>
              </div>
              <div class="diag-item">
                <span class="diag-label">与基准日相关性</span>
                <span class="diag-value">{{ dailyPnLDiagnostics.benchmarkCorr != null ? dailyPnLDiagnostics.benchmarkCorr.toFixed(2) : '--' }}</span>
              </div>
            </div>
            <div class="diag-note">
              集中度：去掉最好/最差 10 天收益即归零，说明「靠运气不靠 alpha」；相关性高 = 单日涨跌跟随大盘（beta 暴露）。
            </div>
          </div>
        </div>

        <div class="section">
          <h3>成交记录</h3>
          <TradePnlScatterChart
            :data="roundTrips"
            :height="300"
            :title="''"
          />
          <div class="sub-chart-title">x=退出时间 · y=单笔盈亏% · 颜色=赚/亏 · 气泡大小=仓位</div>
        </div>

        <div class="section">
          <h3>交易分析</h3>
          <n-tabs v-model:value="activeTradeTab">
            <n-tab-pane name="stats" tab="交易统计">
              <div v-if="tradeStats" class="trade-stats-grid">
                <div class="ts-item"><span class="ts-label">总交易笔数</span><span class="ts-value">{{ tradeStats.total }}</span></div>
                <div class="ts-item"><span class="ts-label">胜率</span><span class="ts-value">{{ (tradeStats.winRate * 100).toFixed(1) }}%</span></div>
                <div class="ts-item"><span class="ts-label">盈亏比</span><span class="ts-value">{{ tradeStats.profitFactor.toFixed(2) }}</span></div>
                <div class="ts-item"><span class="ts-label">平均盈利</span><span class="ts-value text-up">{{ (tradeStats.avgWin * 100).toFixed(2) }}%</span></div>
                <div class="ts-item"><span class="ts-label">平均亏损</span><span class="ts-value text-down">{{ (tradeStats.avgLoss * 100).toFixed(2) }}%</span></div>
                <div class="ts-item"><span class="ts-label">平均持仓</span><span class="ts-value">{{ tradeStats.avgHolding.toFixed(1) }} 天</span></div>
              </div>
              <n-empty v-else description="暂无成交配对数据" />
            </n-tab-pane>
            <n-tab-pane name="trades" tab="交易列表">
              <n-data-table
                :columns="stockColumns"
                :data="stockGroupedTrips"
                :row-key="(row: any) => row.symbol"
                size="small"
                :max-height="360"
                :row-class-name="(row: any) => row.symbol === selectedStockSymbol ? 'stock-row-selected' : ''"
                @row-click="onStockRowClick"
              />
              <div v-if="selectedStockDetail" class="stock-detail">
                <h4 class="stock-detail-title">{{ selectedStockDetail.name }}（{{ selectedStockDetail.symbol }}）成交明细 · 共 {{ selectedStockDetail.count }} 次往返</h4>
                <n-data-table :columns="tripColumns" :data="selectedStockDetail.trips" size="small" :bordered="false" />
              </div>
              <div v-else class="stock-detail-hint">👆 点击上方股票行，追溯该股票的每笔买卖配对</div>
            </n-tab-pane>
            <n-tab-pane name="distribution" tab="收益分布">
              <n-empty v-if="report.profitDistribution.bins.length === 0" description="收益分布由交易列表聚合计算" />
              <template v-else>
                <ProfitDistributionChart :data="report.profitDistribution" />
                <div v-if="distributionConclusion" class="distribution-conclusion">
                  <b>{{ distributionConclusion.type }}</b>：{{ distributionConclusion.text }}
                </div>
              </template>
            </n-tab-pane>
          </n-tabs>
        </div>
        </div>
        <div class="report-footer">
          <n-space justify="center" :size="12">
            <n-button type="primary" @click="saveReport">保存报告</n-button>
            <n-button @click="exportPDF">导出PDF</n-button>
            <n-button @click="addToBasket">加入股票篮子</n-button>
          </n-space>
        </div>
        </div>
      </div>
    </template>
  </n-spin>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import { useMessage, NResult, NSpin, NEmpty, NSpace, NButton } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import EquityCurveChart from "@/components/charts/EquityCurveChart.vue";
import MonthlyReturnChart from "@/components/charts/MonthlyReturnChart.vue";
import ProfitDistributionChart from "@/components/charts/ProfitDistributionChart.vue";
import DailyPnLChart from "@/components/charts/DailyPnLChart.vue";
import TradePnlScatterChart from "@/components/charts/TradePnlScatterChart.vue";
import StatCard from "@/components/common/StatCard.vue";
import backtestAPI from "@/api/backtest";
import strategyAPI from "@/api/strategy";
import marketAPI from "@/api/market";
const route = useRoute();
const router = useRouter();
const message = useMessage();
const store = useStore<any>();

const loading = ref(false);
const error = ref(false);
const activeTradeTab = ref("stats");


/** 从 trades 列表聚合收益分布（后端不直接返回此字段） */
const aggregateProfitDistribution = (trades: any[]) => {
  if (!trades || trades.length === 0) return { bins: [], counts: [] };
  const buyMap = new Map<string, { price: number; quantity: number }>();
  const profitRates: number[] = [];

  for (const t of trades) {
    const key = t.ts_code || t.symbol;
    const rawDir = t.side || t.direction || "";
    const dir = rawDir === "LONG" || rawDir === "buy" ? "buy" : "sell";
    const price = Number(t.price || 0);
    const qty = Number(t.quantity || t.volume || 0); // 2026-08: 原始 trades 用 volume 字段
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

// ---- 成交 round-trip（A4：FIFO 买卖配对 → 单笔盈亏/持仓天数/仓位） ----
const roundTrips = computed(() => {
  const trades = report.value.trades || [];
  if (trades.length === 0) return [];
  const bySymbol = new Map<string, any[]>();
  for (const t of trades) {
    const key = t.symbol;
    if (!bySymbol.has(key)) bySymbol.set(key, []);
    bySymbol.get(key)!.push(t);
  }
  const trips: any[] = [];
  for (const [symbol, list] of bySymbol) {
    const sorted = [...list].sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const open: Array<{ date: string; price: number; quantity: number }> = [];
    for (const t of sorted) {
      if (t.direction === 'buy') {
        open.push({ date: t.date, price: t.price, quantity: t.quantity });
      } else {
        let remaining = t.quantity;
        while (remaining > 0 && open.length > 0) {
          const entry = open[0];
          const matchedQty = Math.min(remaining, entry.quantity);
          const pnlRate = entry.price > 0 ? (t.price - entry.price) / entry.price : 0;
          const holdingMs = new Date(t.date).getTime() - new Date(entry.date).getTime();
          const holdingDays = Math.max(0, Math.round(holdingMs / 86400000));
          trips.push({
            symbol,
            entryDate: String(entry.date).slice(0, 10),
            exitDate: String(t.date).slice(0, 10),
            buyPrice: entry.price,
            sellPrice: t.price,
            pnlRate,
            holdingDays,
            positionSize: entry.price * matchedQty,
            isWin: pnlRate >= 0,
          });
          remaining -= matchedQty;
          entry.quantity -= matchedQty;
          if (entry.quantity <= 0) open.shift();
        }
      }
    }
  }
  return trips.sort((a, b) => String(a.exitDate).localeCompare(String(b.exitDate)));
});

// ---- 交易统计（Fix 6：胜率/盈亏比/平均盈亏/持仓天数，替代逐笔 K 线） ----
const tradeStats = computed(() => {
  const trips = roundTrips.value;
  if (trips.length === 0) return null;
  const wins = trips.filter((t) => t.pnlRate > 0);
  const losses = trips.filter((t) => t.pnlRate < 0);
  const avgWin = wins.length ? wins.reduce((a, t) => a + t.pnlRate, 0) / wins.length : 0;
  const avgLoss = losses.length ? Math.abs(losses.reduce((a, t) => a + t.pnlRate, 0) / losses.length) : 0;
  const totalWin = wins.reduce((a, t) => a + t.pnlRate, 0);
  const totalLoss = Math.abs(losses.reduce((a, t) => a + t.pnlRate, 0));
  return {
    total: trips.length,
    winRate: wins.length / trips.length,
    avgWin,
    avgLoss,
    profitFactor: avgLoss > 0 ? avgWin / avgLoss : 0,
    avgHolding: trips.reduce((a, t) => a + t.holdingDays, 0) / trips.length,
    totalWin,
    totalLoss,
  };
});

// ---- 收益分布结论（偏度判断策略类型 + 尾部风险） ----
const distributionConclusion = computed(() => {
  const trips = roundTrips.value;
  if (trips.length < 3) return null;
  const rates = trips.map((t: any) => t.pnlRate);
  const mean = rates.reduce((a, b) => a + b, 0) / rates.length;
  const std = Math.sqrt(rates.reduce((a, b) => a + (b - mean) ** 2, 0) / rates.length);
  const skew = std > 1e-9 ? rates.reduce((a, b) => a + ((b - mean) / std) ** 3, 0) / rates.length : 0;
  if (skew > 0.3) return { type: "右偏", text: "多数小亏 + 少数大赚（截断亏损、让利润奔跑），典型趋势/动量策略" };
  if (skew < -0.3) return { type: "左偏", text: "多数小赚 + 少数大亏，尾部风险高，某次大亏可能吃掉累计利润" };
  return { type: "近对称", text: "单笔赚亏对等，无明显 alpha 结构" };
});

// ---- 股票名称解析 + 按股票聚合（追溯单只股票交易记录） ----
const stockNames = ref<Record<string, string>>({});

async function resolveStockNames() {
  const codes = [...new Set(roundTrips.value.map((t: any) => t.symbol).filter(Boolean))];
  if (!codes.length) return;
  const results = await Promise.all(codes.map((c) => marketAPI.getStockDetail(c).catch(() => null)));
  const map: Record<string, string> = {};
  codes.forEach((c, i) => {
    const s: any = results[i];
    map[c] = s?.name || s?.stock_name || s?.ts_name || c;
  });
  stockNames.value = map;
}

const stockGroupedTrips = computed(() => {
  const map = new Map<string, any[]>();
  for (const t of roundTrips.value) {
    if (!map.has(t.symbol)) map.set(t.symbol, []);
    map.get(t.symbol)!.push(t);
  }
  return [...map.entries()].map(([symbol, ts]) => {
    const wins = ts.filter((t: any) => t.isWin).length;
    return {
      symbol,
      name: stockNames.value[symbol] || symbol,
      count: ts.length,
      winRate: wins / ts.length,
      totalPnl: ts.reduce((a: number, t: any) => a + t.pnlRate, 0),
      avgHolding: ts.reduce((a: number, t: any) => a + t.holdingDays, 0) / ts.length,
      trips: ts,
    };
  });
});

const stockColumns = [
  { title: "股票代码", key: "symbol", width: 100 },
  { title: "名称", key: "name", width: 160, ellipsis: { tooltip: true } },
  { title: "往返次数", key: "count", width: 90 },
  { title: "胜率", key: "winRate", width: 80, render: (row: any) => `${(row.winRate * 100).toFixed(0)}%` },
  { title: "总盈亏", key: "totalPnl", width: 110, render: (row: any) => h("span", { class: row.totalPnl >= 0 ? "text-up" : "text-down" }, `${row.totalPnl >= 0 ? "+" : ""}${(row.totalPnl * 100).toFixed(1)}%`) },
  { title: "平均持仓", key: "avgHolding", width: 90, render: (row: any) => `${row.avgHolding.toFixed(1)} 天` },
  {
    title: "操作",
    key: "action",
    width: 90,
    render: (row: any) => h(NButton, {
      size: "tiny", type: "primary", quaternary: true,
      onClick: () => onStockRowClick(row),
    }, { default: () => "查看明细" }),
  },
];

const tripColumns = [
  { title: "买入日期", key: "entryDate", width: 105 },
  { title: "卖出日期", key: "exitDate", width: 105 },
  { title: "买入价", key: "buyPrice", width: 80, render: (row: any) => row.buyPrice?.toFixed(2) },
  { title: "卖出价", key: "sellPrice", width: 80, render: (row: any) => row.sellPrice?.toFixed(2) },
  { title: "盈亏", key: "pnlRate", width: 90, render: (row: any) => h("span", { class: row.pnlRate >= 0 ? "text-up" : "text-down" }, `${row.pnlRate >= 0 ? "+" : ""}${(row.pnlRate * 100).toFixed(2)}%`) },
  { title: "持仓天数", key: "holdingDays", width: 85 },
  { title: "仓位", key: "positionSize", width: 100, render: (row: any) => `¥${(row.positionSize / 1e4).toFixed(1)}万` },
];

// ---- 股票追溯（点击行选中 → 下方明细） ----
const selectedStockSymbol = ref("");

function onStockRowClick(row: any) {
  selectedStockSymbol.value = row.symbol === selectedStockSymbol.value ? "" : row.symbol;
}

const selectedStockDetail = computed(() => {
  if (!selectedStockSymbol.value) return null;
  return stockGroupedTrips.value.find((s: any) => s.symbol === selectedStockSymbol.value) || null;
});

// ---- 市场背景（A2-③④：CSI500 regime 分年度 + 回撤区间行情归因） ----
const marketCloses = ref<{ csi500: Array<{ date: string; close: number }>; hs300: Array<{ date: string; close: number }> }>({ csi500: [], hs300: [] });

// regime 判定：CSI500 close vs MA250 ±3% 带（与后端 shared.market_regime.compute_regime 同源）
function regimeOf(closes: Array<{ date: string; close: number }>, i: number): "bull" | "bear" | "range" {
  if (i < 249) return "range";
  let sum = 0;
  for (let j = i - 249; j <= i; j++) sum += closes[j].close;
  const ma = sum / 250;
  if (closes[i].close > ma * 1.03) return "bull";
  if (closes[i].close < ma * 0.97) return "bear";
  return "range";
}

const REGIME_LABEL: Record<string, string> = { bull: "牛", bear: "熊", range: "震荡" };

// 分年度市场情况（当年各 regime 天数占比）
const regimeByYear = computed(() => {
  const closes = marketCloses.value.csi500;
  const map: Record<string, { bull: number; bear: number; range: number; total: number }> = {};
  for (let i = 249; i < closes.length; i++) {
    const year = closes[i].date.slice(0, 4);
    const r = regimeOf(closes, i);
    if (!map[year]) map[year] = { bull: 0, bear: 0, range: 0, total: 0 };
    map[year][r]++;
    map[year].total++;
  }
  return map;
});

function regimeLabelForYear(year: string | number): string {
  const d = regimeByYear.value[String(year)];
  if (!d || d.total === 0) return "--";
  const parts = ["bull", "range", "bear"]
    .filter((k) => d[k as keyof typeof d] > 0)
    .map((k) => `${REGIME_LABEL[k]}${Math.round((d[k as keyof typeof d] / d.total) * 100)}%`);
  return parts.join(" / ");
}

// 回撤区间行情背景（市场同期涨跌 + regime，判定「市场下跌拖累」vs「策略自身失效」）
const drawdownMarketContext = computed(() => {
  const period = report.value.maxDrawdownPeriod;
  const start = String(period.start || "").slice(0, 10);
  const end = String(period.end || "").slice(0, 10);
  const csi = marketCloses.value.csi500;
  const hs300 = marketCloses.value.hs300;
  if (!start || !end || csi.length === 0) return null;

  const range = (arr: Array<{ date: string; close: number }>) => {
    const seg = arr.filter((d) => d.date >= start && d.date <= end);
    if (seg.length < 2) return null;
    const first = seg[0].close;
    const last = seg[seg.length - 1].close;
    return first > 0 ? (last - first) / first : null;
  };
  const csiRet = range(csi);
  const hsRet = range(hs300);
  // 回撤区间内的 regime 分布
  const regimeCount = { bull: 0, bear: 0, range: 0 };
  const idxStart = csi.findIndex((d) => d.date >= start);
  if (idxStart >= 0) {
    for (let i = idxStart; i < csi.length && csi[i].date <= end; i++) {
      regimeCount[regimeOf(csi, i)]++;
    }
  }
  return { csiRet, hsRet, regimeCount, start, end };
});

// ---- 回撤结论与建议（严重度 + 归因 + 对应动作） ----
const drawdownConclusion = computed(() => {
  const period = report.value.maxDrawdownPeriod;
  if (!period || !period.start) return null;
  const depth = Number(period.depth || 0);
  const consec = Number(report.value.maxConsecutiveLosses || 0);
  const ctx = drawdownMarketContext.value;
  const marketDrop = ctx && ((ctx.csiRet ?? 0) < -0.05 || (ctx.hsRet ?? 0) < -0.05);
  const severity = depth >= 0.2 ? "较大" : depth >= 0.1 ? "偏高" : "可控";
  const cause = marketDrop ? "主要受市场系统性下跌拖累" : "以策略自身因素为主";
  const advice = marketDrop
    ? "对冲逻辑可能正常，维持现有风控，关注市场企稳信号后再加仓"
    : "复盘止盈止损纪律与仓位控制，必要时收紧止损、降低单一持仓集中度";
  return { depth, consec, severity, cause, advice };
});

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
    volatility: 0,
    calmarRatio: 0,
    avgHoldingDays: 0,
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
  riskViolations: [] as any[],
  // 增强指标（基建设计 §二，旧数据缺失时兜底为空）
  yearlyReturns: [] as Array<{ year: string; return: number; max_drawdown: number }>,
  maxDrawdownPeriod: { start: "", end: "", depth: 0 } as Record<string, any>,
  maxConsecutiveLosses: 0,
});

// 月度盈亏分布统计（增强指标，基建设计 §2.3）
const monthlyWinMonths = computed(() =>
  report.value.monthlyReturns.filter((m: any) => m.return >= 0).length,
);
const monthlyLossMonths = computed(() =>
  report.value.monthlyReturns.filter((m: any) => m.return < 0).length,
);
const monthlyWinPct = computed(() => {
  const total = monthlyWinMonths.value + monthlyLossMonths.value;
  return total > 0 ? Math.round((monthlyWinMonths.value / total) * 100) : 0;
});

// ---- 月度收益（热力图，百分比/金额切换）+ 分析结论 ----
const monthlyUnit = ref<"percent" | "amount">("percent");

const monthlyInitialCapital = computed(() => {
  const eq = report.value.equityCurve;
  return eq.length ? Number(eq[0]?.value || 0) : 0;
});

const monthlyDisplayData = computed(() => {
  if (monthlyUnit.value === "percent") return report.value.monthlyReturns;
  const base = monthlyInitialCapital.value;
  return report.value.monthlyReturns.map((m: any) => ({ month: m.month, return: (m.return ?? 0) * base }));
});

const monthlyAnalysis = computed(() => {
  const mr = report.value.monthlyReturns;
  if (!mr.length) return null;
  const best = mr.reduce((a, b) => (a.return > b.return ? a : b));
  const worst = mr.reduce((a, b) => (a.return < b.return ? a : b));
  const pos = mr.filter((m) => m.return > 0).length;
  let maxConsecPos = 0;
  let cur = 0;
  for (const m of mr) { cur = m.return > 0 ? cur + 1 : 0; if (cur > maxConsecPos) maxConsecPos = cur; }
  return { pos, total: mr.length, best, worst, maxConsecPos, winRate: pos / mr.length };
});

// ---- 分年度市场基准（CSI500 年度收益，用于「策略表现」相对结论） ----
const csi500YearlyReturn = computed(() => {
  const closes = marketCloses.value.csi500;
  const map: Record<string, { first: number; last: number }> = {};
  for (const c of closes) {
    const y = c.date.slice(0, 4);
    if (!map[y]) map[y] = { first: c.close, last: c.close };
    map[y].last = c.close;
  }
  const ret: Record<string, number> = {};
  for (const [y, v] of Object.entries(map)) {
    ret[y] = v.first > 0 ? (v.last - v.first) / v.first : 0;
  }
  return ret;
});

const yearlyConclusion = computed(() => {
  const yr = report.value.yearlyReturns;
  if (!yr.length) return null;
  const pos = yr.filter((y: any) => y.return > 0).length;
  const best = yr.reduce((a: any, b: any) => (a.return > b.return ? a : b));
  const worst = yr.reduce((a: any, b: any) => (a.return < b.return ? a : b));
  return { pos, total: yr.length, best, worst };
});

// ---- 分年度归因分析（市场顺逆风 + α 有无 → 归因结论） ----
function yearAttribution(y: any): string {
  const excess = y.return - (csi500YearlyReturn.value[String(y.year)] ?? 0);
  if (y.return >= 0 && excess >= 0) return "顺风+超额，α 有效";
  if (y.return >= 0 && excess < 0) return "β 驱动，α 不足";
  if (y.return < 0 && excess >= 0) return "逆风但跑赢，防御有效";
  return "β+α 双弱，需复盘";
}

// ---- 每日盈亏诊断（A3：尾部风险/分布偏度/收益集中度/连续亏损/基准相关性） ----
const dailyPnLDiagnostics = computed(() => {
  const days = report.value.dailyReturns || [];
  if (days.length < 2) return null;
  const returns = days.map((d: any) => Number(d.daily_return ?? 0));
  const pnls = days.map((d: any) => Number(d.daily_pnl ?? 0));

  // 1. 尾部风险
  const maxWin = Math.max(...pnls);
  const maxLoss = Math.min(...pnls);
  const lossOver3Pct = returns.filter((r) => r < -0.03).length;

  // 2. 分布偏度
  const winDays = returns.filter((r) => r > 0).length;
  const lossDays = returns.filter((r) => r < 0).length;
  const winRate = winDays / returns.length;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const std = Math.sqrt(returns.reduce((a, b) => a + (b - mean) ** 2, 0) / returns.length);
  const skew = std > 1e-9
    ? returns.reduce((a, b) => a + ((b - mean) / std) ** 3, 0) / returns.length
    : 0;

  // 3. 收益集中度（去掉最好/最差 10 天后总收益剩余占比）
  const totalReturn = returns.reduce((a, b) => a + b, 0);
  const sorted = [...returns].sort((a, b) => a - b);
  const trim = Math.min(10, Math.floor(returns.length * 0.05));
  const trimmedSum = sorted.slice(trim, returns.length - trim).reduce((a, b) => a + b, 0);
  const concentration = Math.abs(totalReturn) > 1e-9 ? trimmedSum / totalReturn : 1;

  // 4. 连续亏损（最长连续亏损天数）
  let maxConsecLoss = 0;
  let cur = 0;
  for (const r of returns) {
    cur = r < 0 ? cur + 1 : 0;
    if (cur > maxConsecLoss) maxConsecLoss = cur;
  }

  // 5. 与基准日相关性（beta 暴露，日期对齐）
  let benchmarkCorr: number | null = null;
  const bench = report.value.benchmark || [];
  if (bench.length >= 2) {
    const benchByDate = new Map<string, number>();
    for (let i = 1; i < bench.length; i++) {
      const prev = bench[i - 1];
      const curB = bench[i];
      const ret = prev.value ? (curB.value - prev.value) / prev.value : 0;
      benchByDate.set(String(curB.date).slice(0, 10), ret);
    }
    const paired = days
      .map((d: any) => ({ s: Number(d.daily_return ?? 0), b: benchByDate.get(String(d.trade_date).slice(0, 10)) }))
      .filter((p: any) => p.b != null);
    if (paired.length >= 5) {
      const sArr = paired.map((p: any) => p.s);
      const bArr = paired.map((p: any) => p.b);
      const sMean = sArr.reduce((a: number, b: number) => a + b, 0) / sArr.length;
      const bMean = bArr.reduce((a: number, b: number) => a + b, 0) / bArr.length;
      let cov = 0; let sVar = 0; let bVar = 0;
      for (let i = 0; i < sArr.length; i++) {
        cov += (sArr[i] - sMean) * (bArr[i] - bMean);
        sVar += (sArr[i] - sMean) ** 2;
        bVar += (bArr[i] - bMean) ** 2;
      }
      benchmarkCorr = sVar > 1e-9 && bVar > 1e-9 ? cov / Math.sqrt(sVar * bVar) : null;
    }
  }

  return {
    maxWin, maxLoss, lossOver3Pct,
    winDays, lossDays, winRate, skew,
    concentration, maxConsecLoss, benchmarkCorr,
  };
});

const strategy = computed(
  () => store.state.strategy?.currentStrategy || { name: "未知策略" },
);

// 页头标题：优先用 strategy_id 拉真实策略名（不依赖 Vuex store）
const strategyName = ref("");
const rangeLabel = ref("");

async function loadMarketContext() {
  try {
    const [csi500, hs300] = await Promise.all([
      marketAPI.getIndexHistory("000905.SH", 750).catch(() => []),
      marketAPI.getIndexHistory("000300.SH", 750).catch(() => []),
    ]);
    const map = (arr: any) => (Array.isArray(arr) ? arr : [])
      .map((d: any) => ({ date: String(d.trade_date || d.date || "").slice(0, 10), close: Number(d.close || 0) }))
      .filter((d: any) => d.date && d.close > 0)
      .sort((a: any, b: any) => a.date.localeCompare(b.date));
    marketCloses.value = { csi500: map(csi500), hs300: map(hs300) };
  } catch { /* 市场背景加载失败不阻塞报告 */ }
}

const loadReport = async () => {
  const taskId = route.params.taskId as string;
  if (!taskId) { error.value = true; return; }
  loading.value = true;
  error.value = false;
  loadMarketContext(); // 市场背景（非阻塞，供分年度市场列 + 回撤归因）
  try {
    const [result, equity, trades] = await Promise.all([
      backtestAPI.getResult(taskId).catch(() => null),
      backtestAPI.getEquityCurve(taskId).catch(() => []),
      // 全量成交（后端默认 page_size=10000）：成交图/交易列表/收益分布需完整数据
      backtestAPI.getTrades(taskId, { page_size: 10000 }).catch(() => []),
    ]);

    const r: Record<string, any> = result || {};
    // 策略名：从 result.strategy_id 拉取（替代 Vuex store，直接导航也能显示）
    if (r.strategy_id) {
      strategyAPI.getStrategy(r.strategy_id).then((s: any) => {
        if (s?.name) strategyName.value = s.name;
      }).catch(() => {});
    }
    // Fallback: 如果独立 equity API 为空，使用 result.equity_curve（v3.3 to_dict 中包含）
    const rawEq = Array.isArray(equity) && equity.length > 0
      ? equity
      : (Array.isArray(r.equity_curve) ? r.equity_curve : []);
    // 2026-08 修复（净值曲线数据不对）：策略/基准须同一量纲可比。
    // 策略用绝对资产（total_assets，起点=初始资金）；基准若为累计收益则 × 初始资金对齐绝对尺度。
    const _eqArr = rawEq.map((p: any) => ({
      date: p.trade_date || p.date,
      value: p.total_assets || p.equity || 0,
    }));
    const _eqBase = _eqArr[0]?.value || 1;
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
        volatility: r.volatility ?? 0,
        calmarRatio: r.calmar_ratio ?? 0,
        avgHoldingDays: r.avg_holding_days ?? 0,
      },
      equityCurve: _eqArr,
      benchmark: (r.benchmark_curve || []).map((p: any) => ({
        date: p.trade_date || p.date,
        value: p.total_assets ?? (p.cumulative_return != null ? (1 + p.cumulative_return) * _eqBase : (p.value ?? 0)),
      })),
      drawdown: (r.drawdown_curve || []).map((p: any) => ({
        date: p.trade_date || p.date,
        // 引擎 drawdown 为正值深度 → 取负使回撤曲线显示在 0 下方（与负值口径一致）
        value: -(p.drawdown || p.max_drawdown || 0),
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
      riskViolations: Array.isArray(r.risk_violations) ? r.risk_violations : [],
      // 增强指标（旧任务 result 缺失 → 兜底为空，不报错）
      yearlyReturns: Array.isArray(r.yearly_returns) ? r.yearly_returns : [],
      maxDrawdownPeriod: r.max_drawdown_period && typeof r.max_drawdown_period === "object"
        ? r.max_drawdown_period
        : { start: "", end: "", depth: 0 },
      maxConsecutiveLosses: r.max_consecutive_losses ?? 0,
    };

    resolveStockNames(); // 解析股票名称（非阻塞）

    // 回测区间标签（页头副标题）
    const eqD = report.value.equityCurve;
    if (eqD.length >= 2) {
      rangeLabel.value = `${String(eqD[0].date).slice(0, 10)} ~ ${String(eqD[eqD.length - 1].date).slice(0, 10)}`;
    }
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
    basketName: `${strategyName.value || '回测'}_股票池`,
  });
  message.success(`已创建股票篮子: ${strategyName.value || '回测'}_股票池`);
};

const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

onMounted(() => {
  loadReport()
  // 启动轮询：任务未完成时每 5 秒重新加载
  pollTimer.value = setInterval(async () => {
    const taskId = route.params.taskId as string
    if (!taskId) return
    try {
      const status = await backtestAPI.getTask(taskId)
      if (status?.status === 'completed' || status?.status === 'failed') {
        if (pollTimer.value) { clearInterval(pollTimer.value); pollTimer.value = null }
        if (!report.value || !report.value.summary?.totalReturn) {
          await loadReport()
        }
      }
    } catch { /* 轮询失败静默 */ }
  }, 5000)
})

onUnmounted(() => {
  if (pollTimer.value) { clearInterval(pollTimer.value); pollTimer.value = null }
})
</script>

<style scoped>
.report-header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--n-border-color);
}
.report-section-title {
  margin: 0 0 14px;
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.report-header h2 {
  color: var(--n-text-color-1);
}
.report-header-top {
  display: flex;
  align-items: center;
  gap: 10px;
}
.report-body {
  padding: 20px;
}
.report-sections {
  margin-top: 20px;
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
.metric-card-full {
  grid-column: 1 / -1;
}

/* 增强指标（基建设计 §二） */
.yearly-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.yearly-table th,
.yearly-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--n-border-color);
  color: var(--n-text-color-2);
}
.yearly-table th {
  color: var(--n-text-color-3);
  font-weight: 500;
  font-size: 12px;
}
.drawdown-info-line {
  font-size: 14px;
  color: var(--n-text-color-2);
  line-height: 2;
  margin: 0;
}
.drawdown-info-line strong {
  font-size: 15px;
  color: var(--n-text-color-1);
  font-weight: 700;
}

.report-footer {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--n-border-color);
}
.metric-footnote {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--n-text-color-3);
  line-height: 1.6;
}
.trade-kline-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

/* 每日盈亏诊断（A3） */
.text-up { color: var(--n-error-color); }
.text-down { color: var(--n-success-color); }
.pnl-diagnostic {
  margin-top: 16px;
}
.diag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}
.diag-item {
  padding: 10px 12px;
  background: var(--n-hover-color);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.diag-label {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.diag-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.diag-note {
  margin-top: 10px;
  font-size: 12px;
  color: var(--n-text-color-3);
  line-height: 1.6;
}
.sub-chart-title {
  margin: 18px 0 4px;
  font-size: 12px;
  color: var(--n-text-color-3);
}
.trade-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}
.ts-item {
  padding: 10px 12px;
  background: var(--n-hover-color);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ts-label {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.ts-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.metric-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.metric-card-header h3 {
  margin: 0;
}
.monthly-toggle {
  transform: scale(0.5);
  transform-origin: right center;
}
.monthly-analysis {
  margin-top: 12px;
  font-size: 12px;
  color: var(--n-text-color-2);
  line-height: 1.7;
}
.monthly-analysis b {
  color: var(--n-text-color-1);
}
.yearly-conclusion {
  margin-top: 12px;
  font-size: 12px;
  color: var(--n-text-color-2);
  line-height: 1.7;
}
.yearly-conclusion b {
  color: var(--n-text-color-1);
}
.drawdown-conclusion {
  margin-top: 8px;
  padding: 8px 10px;
  background: var(--n-hover-color);
  border-radius: 6px;
}
.stock-trips-detail {
  padding: 8px 16px;
  background: var(--n-hover-color);
}
.stock-row-selected td {
  background: var(--n-pressed-color) !important;
}
.stock-detail {
  margin-top: 10px;
  padding: 10px 14px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
}
.stock-detail-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.stock-detail-hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--n-text-color-3);
}
.distribution-conclusion {
  margin-top: 10px;
  padding: 8px 12px;
  background: var(--n-hover-color);
  border-radius: 6px;
  font-size: 12px;
  color: var(--n-text-color-2);
  line-height: 1.6;
}
</style>
