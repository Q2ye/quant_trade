<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, h, nextTick } from "vue";
import { useRouter } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import VChart from "vue-echarts";
import {
  NCard, NButton, NSelect, NDataTable, NTabs, NTabPane,
  NGrid, NGridItem, NStatistic, NSpace, NSpin, NResult, NEmpty, NSkeleton, useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import performanceAPI from "@/api/performance";
import AppDateRangePicker from "@/components/common/AppDateRangePicker.vue";

interface PerformancePoint {
  date: string;
  equity?: number;
  nav?: number;
  total_asset?: number;
  cash?: number;
  market_value?: number;
  daily_pnl?: number;
  daily_return?: number;
  cumulative_return?: number;
  drawdown?: number;
}

interface Position {
  symbol: string;
  name: string;
  volume: number;
  cost_price: number;
  current_price: number;
  market_value: number;
  pnl: number;
  pnl_ratio: number;
  weight: number;
}

const message = useMessage();
const router = useRouter();
const loading = ref(false);
const error = ref(false);
const empty = ref(false);
const accountId = ref("");
const accounts = ref<any[]>([]);
const accountOptions = computed(() =>
  accounts.value.map((a: any) => ({
    label: `${a.broker ? a.broker + ' ' : ''}${a.account_name || a.account_number || a.id}`,
    value: a.id,
  }))
);
const performanceData = ref<PerformancePoint[]>([]);
const positions = ref<Position[]>([]);
const monthlyReturns = ref<Record<string, number>>({});
const dateRange = ref<[string, string] | null>(null);
const selectedPeriod = ref("1m");
const activeTab = ref("overview");

const periodOptions = [
  { label: "近1周", value: "1w" },
  { label: "近1月", value: "1m" },
  { label: "近3月", value: "3m" },
  { label: "近1年", value: "1y" },
  { label: "全部", value: "all" },
];

const performanceMetrics = reactive({
  totalReturn: 0,
  annualizedReturn: 0,
  sharpeRatio: 0,
  sortinoRatio: 0,
  calmarRatio: 0,
  maxDrawdown: 0,
  volatility: 0,
  var95: 0,
  totalAsset: 0,
  dailyPnl: 0,
  dailyReturn: 0,
  totalTrades: 0,
});

// ---- Metric card display data ----
// 核心 6 卡（一行）：收益 + 风险调整收益
const coreMetricCards = computed(() => [
  { label: "累计收益", value: fmtPct(performanceMetrics.totalReturn), color: performanceMetrics.totalReturn >= 0 ? "text-up" : "text-down" },
  { label: "年化收益", value: fmtPct(performanceMetrics.annualizedReturn), color: performanceMetrics.annualizedReturn >= 0 ? "text-up" : "text-down" },
  { label: "夏普比率", value: performanceMetrics.sharpeRatio.toFixed(2), color: "" },
  { label: "最大回撤", value: fmtPct(performanceMetrics.maxDrawdown), color: "text-down" },
  { label: "Sortino比率", value: performanceMetrics.sortinoRatio.toFixed(2), color: "" },
  { label: "Calmar比率", value: performanceMetrics.calmarRatio.toFixed(2), color: "" },
]);
// 辅助 3 卡（第二行）：波动率 / 成交笔数 / VaR
// 说明：账户绩效不含胜率/利润因子（trades 表无 pnl 列，盈亏由持仓/结算层计算），
// 以可准确统计的「区间成交笔数」「95% VaR」替代，避免展示恒 0 的误导数据。
const extraMetricCards = computed(() => [
  { label: "年化波动率", value: fmtPct(performanceMetrics.volatility), color: "" },
  { label: "区间成交笔数", value: performanceMetrics.totalTrades > 0 ? String(performanceMetrics.totalTrades) : "--", color: "" },
  { label: "95% VaR", value: fmtPct(performanceMetrics.var95), color: performanceMetrics.var95 < 0 ? "text-down" : "" },
]);

const fmtPct = (v: number) => {
  if (v === null || v === undefined || isNaN(v)) return "--";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
};

const fmtMoney = (v: number) => {
  if (v === null || v === undefined) return "--";
  return `¥${v.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

// ---- ECharts options (computed) ----
const equityDrawdownOption = computed(() => {
  const pts = performanceData.value;
  if (pts.length === 0) return null;
  const dates = pts.map((p) => p.date || "");
  const navs = pts.map((p) => p.equity ?? p.nav ?? p.total_asset ?? 1);
  const dds = pts.map((p) => p.drawdown ?? 0);

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(20,20,40,0.92)",
      borderColor: "rgba(255,255,255,0.08)",
      textStyle: { color: "#ccc", fontSize: 12 },
      formatter: (params: any) => {
        if (!params || params.length === 0) return "";
        const date = params[0].axisValue;
        let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`;
        params.forEach((p: any) => {
          const v = p.seriesName === "回撤" ? `${(p.value*100).toFixed(2)}%` : p.value.toFixed(4);
          html += `<div>${p.marker} ${p.seriesName}: ${v}</div>`;
        });
        return html;
      },
    },
    legend: { data: ["净值", "回撤"], bottom: 0, textStyle: { color: "#a0a0a0", fontSize: 11 } },
    grid: { left: "3%", right: "3%", top: 16, bottom: 36, containLabel: true },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: "#a0a0a0", fontSize: 10, rotate: dates.length > 30 ? 45 : 0 },
    },
    yAxis: [
      {
        type: "value",
        name: "净值",
        axisLabel: { color: "#a0a0a0", fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
      },
      {
        type: "value",
        name: "回撤",
        axisLabel: { color: "#a0a0a0", fontSize: 10, formatter: (v: number) => `${(v*100).toFixed(0)}%` },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "净值",
        type: "line",
        yAxisIndex: 0,
        data: navs,
        smooth: true,
        lineStyle: { color: "#7c3aed", width: 2 },
        itemStyle: { color: "#7c3aed" },
        symbol: "none",
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(124,58,237,0.25)" },
            { offset: 1, color: "rgba(124,58,237,0.02)" },
          ]),
        },
      },
      {
        name: "回撤",
        type: "line",
        yAxisIndex: 1,
        data: dds,
        lineStyle: { color: "#d03050", width: 1, type: "dashed" },
        itemStyle: { color: "#d03050" },
        symbol: "none",
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(208,48,80,0.4)" },
            { offset: 1, color: "rgba(208,48,80,0.02)" },
          ]),
        },
      },
    ],
    dataZoom: dates.length > 60 ? [
      { type: "inside", minSpan: 5 },
      { type: "slider", bottom: 20, minSpan: 5 },
    ] : undefined,
  };
});

const heatmapOption = computed(() => {
  const mr = monthlyReturns.value;
  const entries = Object.entries(mr);
  if (entries.length === 0) return null;

  const yearSet = new Set<string>();
  const monthSet = new Set<string>();
  const hData: any[] = [];
  entries.forEach(([key, val]) => {
    const parts = key.split("-");
    if (parts.length >= 2) {
      yearSet.add(parts[0]); monthSet.add(parts[1]);
      hData.push([parts[1], parts[0], +(Number(val) * 100).toFixed(2)]);
    }
  });
  const years = Array.from(yearSet).sort();
  const months = Array.from(monthSet).sort((a, b) => parseInt(a) - parseInt(b));
  const maxAbs = Math.max(...hData.map((d: any) => Math.abs(d[2])), 5);

  return {
    backgroundColor: "transparent",
    tooltip: {
      position: "top",
      backgroundColor: "rgba(20,20,40,0.92)",
      borderColor: "rgba(255,255,255,0.08)",
      textStyle: { color: "#ccc", fontSize: 12 },
      formatter: (p: any) => `${p.data[1]}-${p.data[0]}: ${p.data[2]}%`,
    },
    grid: { height: "70%", top: "10%" },
    xAxis: { type: "category", data: months, splitArea: { show: true }, axisLabel: { color: "#a0a0a0" } },
    yAxis: { type: "category", data: years.reverse(), splitArea: { show: true }, axisLabel: { color: "#a0a0a0" } },
    visualMap: {
      min: -maxAbs, max: maxAbs, calculable: true,
      orient: "horizontal", left: "center", bottom: "0%",
      // A 股红涨绿跌：左端（负收益）绿、右端（正收益）红
      inRange: { color: ["#18a058", "#a3d9b1", "#fafafa", "#f6a6a0", "#d03050"] },
      textStyle: { color: "#a0a0a0" },
    },
    series: [{
      name: "月度收益",
      type: "heatmap",
      data: hData,
      label: { show: true, fontSize: 10, color: "#666" },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" } },
    }],
  };
});

import * as echarts from "echarts";

// Position pie
const positionPieOption = computed(() => {
  if (positions.value.length === 0) return null;
  const pieData = positions.value
    .filter((p) => (p.weight || 0) > 0.01)
    .map((p) => ({ name: p.symbol || p.name, value: +(p.market_value || 0) }));
  const others = positions.value
    .filter((p) => (p.weight || 0) <= 0.01)
    .reduce((s, p) => s + (p.market_value || 0), 0);
  if (others > 0) pieData.push({ name: "其他", value: others });

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(20,20,40,0.92)",
      borderColor: "rgba(255,255,255,0.08)",
      textStyle: { color: "#ccc", fontSize: 12 },
      formatter: "{b}: ¥{c} ({d}%)",
    },
    legend: {
      orient: "vertical", right: 8, top: "center",
      textStyle: { color: "#a0a0a0", fontSize: 10 },
    },
    series: [{
      type: "pie",
      radius: ["50%", "75%"],
      center: ["38%", "50%"],
      data: pieData,
      label: { show: false },
      emphasis: { label: { show: true, fontWeight: "bold" } },
      itemStyle: { borderRadius: 4, borderColor: "rgba(0,0,0,0.3)", borderWidth: 2 },
    }],
  };
});

// Position columns
const positionColumns: DataTableColumns<Position> = [
  { title: "代码", key: "symbol", width: 90 },
  { title: "名称", key: "name", width: 100 },
  { title: "持仓数量", key: "volume", width: 90, render: (row) => (row.volume || 0).toLocaleString() },
  { title: "成本价", key: "cost_price", width: 90, render: (row) => `¥${(row.cost_price || 0).toFixed(2)}` },
  { title: "当前价", key: "current_price", width: 90, render: (row) => `¥${(row.current_price || 0).toFixed(2)}` },
  { title: "市值", key: "market_value", width: 110, render: (row) => `¥${((row.market_value || 0) / 10000).toFixed(2)}万` },
  {
    title: "盈亏", key: "pnl", width: 110,
    render: (row) => {
      const v = row.pnl || 0;
      const c = v >= 0 ? "text-up" : "text-down";
      return h("span", { class: c }, `${v >= 0 ? "+" : ""}¥${v.toFixed(2)}`);
    },
  },
  {
    title: "盈亏率", key: "pnl_ratio", width: 90,
    render: (row) => {
      const v = row.pnl_ratio || 0;
      const c = v >= 0 ? "text-up" : "text-down";
      return h("span", { class: c }, `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`);
    },
  },
  { title: "权重", key: "weight", width: 80, render: (row) => `${((row.weight || 0) * 100).toFixed(1)}%` },
];

// ---- Data loading ----
const loadPerformanceData = async () => {
  loading.value = true;
  error.value = false;
  empty.value = false;
  try {
    const params: any = {};
    if (dateRange.value) {
      params.start_date = dateRange.value[0];
      params.end_date = dateRange.value[1];
    }
    const data: any = await performanceAPI.getAccountPerformance(accountId.value, params);
    if (data) {
      // Metrics
      performanceMetrics.totalReturn = data.total_return ?? 0;
      performanceMetrics.annualizedReturn = data.annual_return ?? 0;
      performanceMetrics.sharpeRatio = data.sharpe_ratio ?? 0;
      performanceMetrics.sortinoRatio = data.sortino_ratio ?? 0;
      performanceMetrics.calmarRatio = data.calmar_ratio ?? 0;
      performanceMetrics.maxDrawdown = data.max_drawdown ?? 0;
      performanceMetrics.volatility = data.volatility ?? 0;
      performanceMetrics.var95 = data.var_95 ?? 0;
      performanceMetrics.totalTrades = data.total_trades ?? 0;
      performanceMetrics.dailyPnl = data.daily_pnl ?? 0;
      performanceMetrics.dailyReturn = data.daily_return ?? 0;
      performanceMetrics.totalAsset = data.total_asset ?? 0;

      // Chart data
      if (data.equity_curve && Array.isArray(data.equity_curve) && data.equity_curve.length > 0) {
        performanceData.value = data.equity_curve;
      } else {
        empty.value = true;
      }
      if (data.drawdown_curve && Array.isArray(data.drawdown_curve)) {
        // Merge drawdown into performanceData for dual-axis
        data.drawdown_curve.forEach((dd: any, i: number) => {
          if (performanceData.value[i]) {
            performanceData.value[i].drawdown = dd.drawdown ?? dd.value ?? 0;
          }
        });
      }
      if (data.monthly_returns) {
        monthlyReturns.value = data.monthly_returns;
      }
      if (data.positions && Array.isArray(data.positions)) {
        positions.value = data.positions;
      }
    } else {
      empty.value = true;
    }
  } catch (err) {
    console.error("加载账户绩效失败:", err);
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const onPeriodChange = () => {
  const now = new Date();
  let start: Date;
  switch (selectedPeriod.value) {
    case "1w": start = new Date(now.getTime() - 7 * 86400000); break;
    case "1m": start = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate()); break;
    case "3m": start = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate()); break;
    case "1y": start = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate()); break;
    default: start = new Date(2020, 0, 1); break;
  }
  dateRange.value = [start.toISOString().split("T")[0], now.toISOString().split("T")[0]];
  loadPerformanceData();
};

const loadAccounts = async () => {
  try {
    const { default: request } = await import("@/utils/request");
    const res: any = await request.get("/quantTrade/account/list", { params: { page: 1, page_size: 100 } });
    accounts.value = (res?.data?.data || res?.data || []);
    if (accounts.value.length > 0 && !accountId.value) {
      accountId.value = accounts.value[0].id;
    }
  } catch { accounts.value = []; }
};

onMounted(async () => {
  await loadAccounts();
  if (accountId.value) loadPerformanceData();
});
</script>

<template>
  <div class="account-performance-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">账户绩效</h1>
          <p class="page-description">净值、收益、风险指标与持仓分布一览</p>
        </div>
        <div class="header-actions">
          <n-select v-model:value="accountId" :options="accountOptions" placeholder="选择账户" size="small" style="width:200px" @update:value="loadPerformanceData" />
          <n-button class="action-btn" @click="loadPerformanceData" quaternary><template #icon><SmartIcon name="Refresh" /></template></n-button>
          <n-button class="action-btn" @click="router.push('/performance')" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <template v-if="loading">
        <div class="metric-cards">
          <n-card v-for="i in 6" :key="i" :class="tokens.surface.card" size="small">
            <n-skeleton text :repeat="2" />
          </n-card>
        </div>
        <div class="metric-cards metric-cards-secondary">
          <n-card v-for="i in 3" :key="i" :class="tokens.surface.card" size="small">
            <n-skeleton text :repeat="2" />
          </n-card>
        </div>
        <n-card :class="tokens.surface.card" size="small" style="margin-top:12px">
          <n-skeleton text :repeat="4" />
        </n-card>
      </template>

      <!-- Error -->
      <n-result v-else-if="error" status="500" title="加载失败" description="获取账户绩效数据失败，请稍后重试">
        <template #footer>
          <n-button type="primary" @click="loadPerformanceData">重试</n-button>
        </template>
      </n-result>

      <!-- Empty -->
      <n-empty v-else-if="empty" description="暂无账户绩效数据" style="padding:60px 0">
        <template #extra>
          <n-button type="primary" @click="router.push('/trade')">前往交易</n-button>
        </template>
      </n-empty>

      <!-- Data -->
      <template v-else>
        <!-- Period & date selector -->
        <div class="toolbar-row">
          <n-space>
            <span class="filter-label">周期</span>
            <n-select v-model:value="selectedPeriod" style="width:100px" :options="periodOptions" @update:value="onPeriodChange" size="small" />
            <AppDateRangePicker v-model:formatted="dateRange" @update:formatted="loadPerformanceData" />
          </n-space>
        </div>

        <!-- Account summary bar -->
        <div class="summary-bar">
          <div class="summary-item card-surface">
            <span class="summary-label">总资产</span>
            <span class="summary-value">{{ fmtMoney(performanceMetrics.totalAsset) }}</span>
          </div>
          <div class="summary-item card-surface">
            <span class="summary-label">可用资金</span>
            <span class="summary-value">{{ fmtMoney(accounts.find((a:any) => a.id === accountId)?.available_balance || 0) }}</span>
          </div>
          <div class="summary-item card-surface">
            <span class="summary-label">当日盈亏</span>
            <span class="summary-value" :class="performanceMetrics.dailyPnl >= 0 ? 'text-up' : 'text-down'">
              {{ performanceMetrics.dailyPnl >= 0 ? '+' : '' }}{{ fmtMoney(performanceMetrics.dailyPnl) }}
            </span>
          </div>
          <div class="summary-item card-surface">
            <span class="summary-label">当日收益率</span>
            <span class="summary-value" :class="performanceMetrics.dailyReturn >= 0 ? 'text-up' : 'text-down'">
              {{ fmtPct(performanceMetrics.dailyReturn) }}
            </span>
          </div>
        </div>

        <!-- Metric cards: 核心 6 卡一行 + 辅助 3 卡一行 -->
        <div class="metric-cards">
          <div v-for="(card, idx) in coreMetricCards" :key="idx" class="metric-card card-surface">
            <span class="mc-label">{{ card.label }}</span>
            <span class="mc-value" :class="card.color">{{ card.value }}</span>
          </div>
        </div>
        <div class="metric-cards metric-cards-secondary">
          <div v-for="(card, idx) in extraMetricCards" :key="idx" class="metric-card card-surface">
            <span class="mc-label">{{ card.label }}</span>
            <span class="mc-value" :class="card.color">{{ card.value }}</span>
          </div>
        </div>
        <!-- 口径标注（2026-08 C4：绩效口径统一） -->
        <div class="metric-footnote">
          口径：夏普 = 日频超额收益 × √252（无风险利率 2%）；年化 = 252 交易日几何复合；最大回撤以负值表示（-15% = 回撤 15%）；95% VaR 为日频收益 5% 分位（负值表示单日潜在亏损比例）。账户层不含胜率/利润因子（成交记录无逐笔盈亏，盈亏由持仓/结算层计算），以区间成交笔数与 VaR 替代。
        </div>

        <!-- Equity + Drawdown dual-axis chart -->
        <n-card :class="tokens.surface.card" size="small" style="margin-top:12px">
          <template #header><span class="card-title">净值曲线 & 回撤</span></template>
          <div v-if="equityDrawdownOption" style="height:360px">
            <v-chart :option="equityDrawdownOption" autoresize style="height:100%" />
          </div>
          <n-empty v-else description="暂无数据" style="padding:40px" />
        </n-card>

        <!-- Two-column: Heatmap + Positions -->
        <div class="dual-row">
          <n-card :class="tokens.surface.card" size="small" style="flex:1">
            <template #header><span class="card-title">月度收益热力图</span></template>
            <div v-if="heatmapOption" style="height:340px">
              <v-chart :option="heatmapOption" autoresize style="height:100%" />
            </div>
            <n-empty v-else description="暂无月度数据" style="padding:40px" />
          </n-card>

          <n-card :class="tokens.surface.card" size="small" style="flex:1">
            <template #header><span class="card-title">持仓分布</span></template>
            <div v-if="positionPieOption" style="height:340px">
              <v-chart :option="positionPieOption" autoresize style="height:100%" />
            </div>
            <n-empty v-else description="暂无持仓数据" style="padding:40px" />
          </n-card>
        </div>

        <!-- Tabs: Position table + Rolling metrics -->
        <n-card :class="tokens.surface.card" size="small" style="margin-top:12px">
          <n-tabs v-model:value="activeTab" size="small">
            <n-tab-pane name="positions" tab="持仓明细">
              <n-data-table
                v-if="positions.length > 0"
                :columns="positionColumns"
                :data="positions"
                :pagination="false"
                :row-key="(row: Position) => row.symbol"
                size="small"
              />
              <n-empty v-else description="暂无持仓数据" style="padding:40px" />
            </n-tab-pane>
            <n-tab-pane name="summary" tab="绩效摘要">
              <div class="stat-list" v-if="performanceData.length > 0">
                <div class="stat-row">
                  <span class="stat-label">最新净值</span>
                  <span class="stat-value">{{ (performanceData[performanceData.length-1]?.equity || performanceData[performanceData.length-1]?.nav || performanceData[performanceData.length-1]?.total_asset || 0).toFixed(4) }}</span>
                </div>
                <div class="stat-divider" />
                <div class="stat-row">
                  <span class="stat-label">数据起始</span>
                  <span class="stat-value">{{ performanceData[0]?.date || "--" }}</span>
                </div>
                <div class="stat-divider" />
                <div class="stat-row">
                  <span class="stat-label">数据截止</span>
                  <span class="stat-value">{{ performanceData[performanceData.length-1]?.date || "--" }}</span>
                </div>
                <div class="stat-divider" />
                <div class="stat-row">
                  <span class="stat-label">数据点数量</span>
                  <span class="stat-value">{{ performanceData.length }}</span>
                </div>
                <div class="stat-divider" />
                <div class="stat-row">
                  <span class="stat-label">总交易次数</span>
                  <span class="stat-value">{{ performanceMetrics.totalTrades || "--" }}</span>
                </div>
              </div>
              <n-empty v-else description="暂无数据" style="padding:40px" />
            </n-tab-pane>
          </n-tabs>
        </n-card>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.account-performance-page {
  height: 100%;
  overflow-y: auto;
}
.main-content {
  padding: 0 19px 24px;
}

.filter-label { font-size: 12px; color: var(--color-text-tertiary); }

.toolbar-row {
  margin-bottom: 14px;
}

/* Account summary bar */
.summary-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}
.summary-item {
  padding: 12px 16px;
  border-radius: 8px;
  .summary-label { font-size: 11px; color: var(--color-text-tertiary); display: block; margin-bottom: 4px; }
  .summary-value { font-size: 18px; font-weight: 700; color: var(--color-text-primary); }
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

/* Metric cards: 核心 6 卡一行 + 辅助 3 卡一行 */
.metric-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}
.metric-cards-secondary {
  grid-template-columns: repeat(3, 1fr);
  margin-top: 10px;
}
.metric-card {
  padding: 14px 18px;
  border-radius: 8px;
  .mc-label { font-size: 11px; color: var(--color-text-tertiary); display: block; margin-bottom: 6px; }
  .mc-value { font-size: 20px; font-weight: 700; color: var(--color-text-primary); display: block; }
}
.metric-footnote { margin: 2px 0 0; font-size: 12px; color: var(--color-text-tertiary); line-height: 1.6; }
.text-up { color: var(--color-stock-up) !important; }
.text-down { color: var(--color-stock-down) !important; }

/* Two-column layout */
.dual-row {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

/* Stat list */
.stat-list { display: flex; flex-direction: column; padding: 8px 0; }
.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; }
.stat-label { font-size: 13px; color: var(--color-text-tertiary); }
.stat-value { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.stat-divider { height: 1px; background: rgba(255,255,255,0.04); margin: 0 16px; }

@media (max-width: 768px) {
  .metric-cards { grid-template-columns: repeat(2, 1fr); }
  .metric-cards-secondary { grid-template-columns: repeat(2, 1fr); }
  .dual-row { flex-direction: column; }
}
</style>
