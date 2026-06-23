<template>
  <n-spin :show="loading" class="strategy-performance">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取绩效数据失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="loadPerformanceData">重试</n-button></template
      >
    </n-result>

    <n-empty
      v-else-if="empty"
      description="该策略暂无绩效数据，请先运行回测"
      style="padding: 60px 0"
    >
      <template #extra>
        <n-button type="primary" @click="router.push('/backtest')">前往回测</n-button>
      </template>
    </n-empty>

    <template v-else>
      <div class="page-header">
        <div class="header-content">
          <div class="title-section">
            <h1 class="page-title">策略绩效</h1>
          </div>
          <div class="header-actions">
            <n-select
              v-model:value="selectedStrategy"
              placeholder="选择策略"
              :options="strategyOptions"
              style="width: 200px"
            />
            <n-date-picker
              v-model:value="dateRange"
              type="daterange"
              :is-date-disabled="() => false"
              style="width: 240px; margin-left: 10px"
            />
            <n-button type="primary" @click="loadPerformanceData">
              <Icon icon="ep:search" /> 查询
            </n-button>
            <n-button @click="exportReport">
              <Icon icon="ep:download" /> 导出报告
            </n-button>
            <n-button size="small" @click="router.push('/performance/comparison')" quaternary>
              加入对比
            </n-button>
            <n-button size="small" @click="router.push('/performance/attribution')" quaternary>
              归因分析
            </n-button>
            <n-button class="action-btn" @click="router.push('/performance')" quaternary>
              <template #icon><SmartIcon name="ArrowLeft" /></template>
            </n-button>
          </div>
        </div>
      </div>

      <div class="main-content">
        <!-- 核心指标 6 列 -->
        <div class="stat-grid">
          <StatCard title="累计收益" :value="fmtPct(performance.totalReturn)" :trend="performance.totalReturn >= 0 ? 'up' : 'down'" />
          <StatCard title="年化收益" :value="fmtPct(performance.annualReturn)" :trend="performance.annualReturn >= 0 ? 'up' : 'down'" />
          <StatCard title="最大回撤" :value="fmtPct(performance.maxDrawdown)" trend="down" />
          <StatCard title="夏普比率" :value="performance.sharpeRatio ? performance.sharpeRatio.toFixed(2) : '--'" />
          <StatCard title="胜率" :value="performance.winRate ? fmtPct(performance.winRate) : '--'" />
        </div>

        <!-- 基准对比行 -->
        <div v-if="btBenchmarkLen > 0" class="stat-grid" style="margin-top:8px">
          <StatCard title="超额收益" :value="fmtPct(benchmarkStats.excessReturn)" :trend="benchmarkStats.excessReturn >= 0 ? 'up' : 'down'" />
          <StatCard title="Alpha" :value="benchmarkStats.alpha.toFixed(4)" />
          <StatCard title="Beta" :value="benchmarkStats.beta.toFixed(2)" />
          <StatCard title="信息比率" :value="benchmarkStats.ir.toFixed(2)" />
        </div>

        <!-- 四层子图 — 深色背景凸显分割线 -->
        <div class="subplots-card">
          <BacktestSubplots
            :equity="btEquityPct"
            :benchmark="btBenchmarkPct"
            :daily-returns="btDailyPnL"
            :daily-turnover="btDailyTurnover"
            :drawdown="btDrawdown"
            :height="750"
            :loading="loading"
          />
        </div>

        <n-card class="metrics-card" style="margin-top:12px">
          <template #header><span>详细绩效指标</span></template>
          <n-data-table
            :data="performanceMetrics"
            :columns="metricsColumns"
            :loading="loading"
            :bordered="false"
            striped
          />
        </n-card>

        <n-card class="heatmap-card">
          <template #header><span>月度收益热力图</span></template>
          <div
            ref="heatmapChart"
            class="chart-container"
            style="height: 400px"
          ></div>
        </n-card>
      </div>
    </template>
  </n-spin>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted, h, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useMessage } from "naive-ui";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import strategyAPI from "@/api/strategy";
import performanceAPI from "@/api/performance";
import backtestAPI from "@/api/backtest";
import * as echarts from "echarts";
import BacktestSubplots from "@/components/charts/BacktestSubplots.vue";
import StatCard from "@/components/common/StatCard.vue";
import { tokens } from "@/styles/design-tokens";

const props = defineProps<{ id?: string }>();

const message = useMessage();
const router = useRouter();
const route = useRoute();
const loading = ref(false);
const error = ref(false);
const empty = ref(false);
const selectedStrategy = ref("");
const dateRange = ref<any>(null);
const heatmapChart = ref<HTMLElement>();

const monthlyReturnsData = ref<Record<string, number>>({});

const strategyList = ref<any[]>([]);
const strategyOptions = computed(() =>
  strategyList.value.map((s: any) => ({
    label: s.name ?? s.strategy_name ?? String(s.id),
    value: String(s.id),
  })),
);

const performance = reactive({
  totalReturn: 0,
  annualReturn: 0,
  maxDrawdown: 0,
  sharpeRatio: 0,
  winRate: 0,
  profitFactor: 0,
});

const performanceMetrics = ref<any[]>([]);

// 图表数据 — BacktestSubplots 格式
const btEquityPct = ref<Array<{ date: string; value: number }>>([]);
const btBenchmarkPct = ref<Array<{ date: string; value: number }>>([]);
const btDailyPnL = ref<Array<{ trade_date: string; daily_return: number; daily_pnl: number }>>([]);
const btDailyTurnover = ref<Array<{ trade_date: string; turnover: number }>>([]);
const btDrawdown = ref<Array<{ date: string; value: number }>>([]);
const btBenchmarkLen = ref(0);

const fmtPct = (v: number) => (v || v === 0) ? `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%` : '--';

const benchmarkStats = computed(() => {
  const raw = analysisData.value;
  return {
    excessReturn: raw?.excess_metrics?.excess_annual_return ?? raw?.alpha ?? 0,
    alpha: raw?.alpha ?? 0,
    beta: raw?.beta ?? 0,
    ir: raw?.information_ratio ?? 0,
  };
});

// 缓存分析 API 原始数据供 benchmarkStats 使用
const analysisData = ref<any>({});

const getReturnClass = (v: number) => (v >= 0 ? "positive" : "negative");
const getDrawdownClass = (d: number) =>
  d <= -0.1 ? "negative" : d <= -0.05 ? "warning" : "positive";

const getMetricClass = (metric: string, value: number) => {
  if (metric.includes("回撤") || metric.includes("波动率"))
    return value <= -0.1 ? "negative" : value <= -0.05 ? "warning" : "positive";
  return value >= 0 ? "positive" : "negative";
};

const formatPercent = (value: number | null | undefined) => {
  if (value === null || value === undefined) return "--";
  return `${(value * 100).toFixed(2)}%`;
};

const formatMetricValue = (metric: string, value: number) => {
  if (metric.includes("率") && !metric.includes("波动率"))
    return formatPercent(value);
  if (typeof value === "number") return value.toFixed(4);
  return value || "--";
};

const metricsColumns = computed(() => [
  { title: "指标名称", key: "metric", width: 200 },
  {
    title: "数值",
    key: "value",
    width: 150,
    render(row: any) {
      return h(
        "span",
        { class: getMetricClass(row.metric, row.value) },
        formatMetricValue(row.metric, row.value),
      );
    },
  },
  { title: "说明", key: "description" },
  {
    title: "基准",
    key: "benchmark",
    width: 150,
    render(row: any) {
      return formatMetricValue(row.metric, row.benchmark);
    },
  },
]);

const loadPerformanceData = async () => {
  if (!selectedStrategy.value) {
    message.warning("请选择策略");
    return;
  }
  loading.value = true;
  error.value = false;
  empty.value = false;
  try {
    const params: any = { benchmark: "000300.SH" };
    if (dateRange.value) {
      const [start, end] = Array.isArray(dateRange.value)
        ? dateRange.value
        : [null, null];
      if (start) params.start_date = new Date(start).toISOString().split("T")[0];
      if (end) params.end_date = new Date(end).toISOString().split("T")[0];
    }
    // 1. 分析 API → 绩效指标
    const data: any = await performanceAPI.getStrategyPerformance(
      selectedStrategy.value,
      params,
    );
    if (data === null) {
      error.value = true; return;
    }

    // 2. 回测 API → 图表数据（与 BacktestReport 完全一致的加载方式）
    try {
      const tasksRes: any = await backtestAPI.getTasks({
        strategy_id: selectedStrategy.value, status: "completed", page_size: 1,
      }).catch(() => null);
      const items = Array.isArray(tasksRes) ? tasksRes : (tasksRes?.data || tasksRes?.items || []);
      const task = items[0];
      if (task) {
        const taskId = task.task_id || task.id;
        const [btResult, btEquity] = await Promise.all([
          backtestAPI.getResult(taskId).catch(() => null),
          backtestAPI.getEquityCurve(taskId).catch(() => []),
        ]);
        const r: Record<string, any> = btResult || {};
        const eq = Array.isArray(btEquity) ? btEquity : [];

        // BacktestSubplots 格式：净值→累计收益率%（eq 字段为 {date, equity, drawdown}）
        const firstEq = (eq[0] as any)?.equity || (eq[0] as any)?.total_assets || 1000000;
        btEquityPct.value = (eq as any[]).map((p: any) => ({
          date: p.trade_date || p.date,
          value: ((p.equity ?? p.total_assets ?? 0) / firstEq - 1) * 100,
        }));
        // 基准→累计收益率%
        const bm = r.benchmark_curve || [];
        const firstBm = bm[0]?.total_assets || firstEq;
        btBenchmarkPct.value = bm.map((p: any) => ({
          date: p.trade_date || p.date,
          value: ((p.total_assets || 0) / firstBm - 1) * 100,
        }));
        btBenchmarkLen.value = bm.length;
        // 每日盈亏
        btDailyPnL.value = (r.daily_returns || []).map((p: any) => ({
          trade_date: p.trade_date || p.date || "",
          daily_return: p.daily_return ?? p.return ?? 0,
          daily_pnl: p.daily_pnl ?? p.pnl ?? 0,
        }));
        // 每日成交额
        btDailyTurnover.value = (r.daily_turnover || []).map((p: any) => ({
          trade_date: p.trade_date || p.date || "",
          turnover: p.turnover ?? 0,
        }));
        // 回撤
        btDrawdown.value = (r.drawdown_curve || []).map((p: any) => ({
          date: p.trade_date || p.date,
          value: p.drawdown ?? 0,
        }));
        monthlyReturnsData.value = Array.isArray(r.monthly_returns)
          ? Object.fromEntries(r.monthly_returns.map((m: any) => [m.month || m.trade_date?.slice(0, 7) || "", m.return ?? 0]))
          : (r.monthly_returns || {});
        analysisData.value = r;
      }
    } catch { /* chart data fallback silent */ }

    if (data && Object.keys(data).length > 0) {
      performance.totalReturn = data.total_return ?? data.totalReturn ?? 0;
      performance.annualReturn = data.annual_return ?? data.annualReturn ?? 0;
      performance.maxDrawdown = data.max_drawdown ?? data.maxDrawdown ?? 0;
      performance.sharpeRatio = data.sharpe_ratio ?? data.sharpeRatio ?? 0;
      performance.winRate = data.win_rate ?? data.winRate ?? 0;
      performance.profitFactor = data.profit_factor ?? data.profitFactor ?? 0;

      // Build metrics table from rich response
      const metricsList: any[] = [
        {
          metric: "累计收益率",
          value: performance.totalReturn,
          description: "策略从开始到现在的总收益率",
          benchmark: data.benchmark_return ?? "--",
        },
        {
          metric: "年化收益率",
          value: performance.annualReturn,
          description: "折算成年度的收益率",
          benchmark: data.benchmark_annual_return ?? "--",
        },
        {
          metric: "最大回撤",
          value: performance.maxDrawdown,
          description: "策略净值从最高点到最低点的最大跌幅",
          benchmark: "--",
        },
        {
          metric: "夏普比率",
          value: performance.sharpeRatio,
          description: "每承受一单位风险产生的超额收益",
          benchmark: data.benchmark_sharpe ?? "--",
        },
        {
          metric: "Sortino 比率",
          value: data.sortino_ratio ?? 0,
          description: "下行风险调整后的收益",
          benchmark: "--",
        },
        {
          metric: "Calmar 比率",
          value: data.calmar_ratio ?? 0,
          description: "年化收益与最大回撤的比值",
          benchmark: "--",
        },
        {
          metric: "波动率",
          value: data.volatility ?? 0,
          description: "收益率的标准差",
          benchmark: "--",
        },
        {
          metric: "胜率",
          value: performance.winRate,
          description: "盈利交易次数占总交易次数的比例",
          benchmark: "--",
        },
        {
          metric: "利润因子",
          value: performance.profitFactor,
          description: "总盈利与总亏损的比值",
          benchmark: "--",
        },
        {
          metric: "总交易次数",
          value: data.total_trades ?? data.totalTrades ?? 0,
          description: "策略执行的总交易次数",
          benchmark: "--",
        },
      ];
      if (data.alpha !== undefined || data.beta !== undefined) {
        metricsList.push(
          { metric: "Alpha", value: data.alpha ?? 0, description: "超额收益（相对基准）", benchmark: "--" },
          { metric: "Beta", value: data.beta ?? 0, description: "系统性风险暴露", benchmark: "--" },
          { metric: "信息比率", value: data.information_ratio ?? 0, description: "主动管理效率", benchmark: "--" },
        );
      }
      performanceMetrics.value = metricsList;

      if (!data.equity_curve || data.equity_curve.length === 0) {
        empty.value = true;
      }
    } else {
      empty.value = true;
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const exportReport = () => message.info("导出报告功能开发中");

let heatmapChartInstance: any = null;

const initHeatmap = () => {
  if (!heatmapChart.value) return;
  heatmapChartInstance?.dispose();
  heatmapChartInstance = echarts.init(heatmapChart.value);
  const mr = monthlyReturnsData.value;
  const mrEntries = Object.entries(mr);

  if (mrEntries.length > 0) {
    const yearSet = new Set<string>();
    const monthSet = new Set<string>();
    const heatData: any[] = [];
    mrEntries.forEach(([key, val]) => {
      const parts = key.split("-");
      if (parts.length >= 2) {
        const y = parts[0];
        const m = parts[1];
        yearSet.add(y); monthSet.add(m);
        heatData.push([m, y, +(Number(val) * 100).toFixed(2)]);
      }
    });
    const years = Array.from(yearSet).sort();
    const months = Array.from(monthSet).sort((a,b) => parseInt(a)-parseInt(b));
    const maxAbs = Math.max(...heatData.map((d: any) => Math.abs(d[2])), 5);

    heatmapChartInstance.setOption({
      tooltip: { position: "top", formatter: (p: any) => `${p.data[1]}-${p.data[0]}: ${p.data[2]}%` },
      grid: { height: "75%", top: "8%" },
      xAxis: { type: "category", data: months, splitArea: { show: true } },
      yAxis: { type: "category", data: years, splitArea: { show: true } },
      visualMap: {
        min: -maxAbs, max: maxAbs, calculable: true,
        orient: "horizontal", left: "center", bottom: "0%",
        inRange: { color: ["#d03050", "#f6a6a0", "#fafafa", "#a3d9b1", "#18a058"] },
      },
      series: [{
        name: "月度收益",
        type: "heatmap",
        data: heatData,
        label: { show: true, fontSize: 10 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" } },
      }],
    });
  } else {
    heatmapChartInstance.setOption({
      title: { text: "暂无月度收益数据", left: "center", top: "center", textStyle: { color: "#999", fontSize: 14 } },
    });
  }
};

onMounted(async () => {
  const routeId = props.id || (route.params.id as string);

  if (routeId) {
    // 路由直连：先取当前策略名，再加载绩效
    try {
      const single = await strategyAPI.getStrategy(routeId);
      const name = single?.name || (single as any)?.strategy_name || routeId.slice(0, 8) + "...";
      strategyList.value = [{ id: routeId, name }];
    } catch {
      strategyList.value = [{ id: routeId, name: routeId.slice(0, 8) + "..." }];
    }
    selectedStrategy.value = routeId;
    await loadPerformanceData();

    // 后台补全全量列表
    strategyAPI.getStrategies().then(list => {
      if (Array.isArray(list) && list.length > 0) {
        const cur = selectedStrategy.value;
        if (!list.some((s: any) => String(s.id) === cur)) {
          const item = strategyList.value.find((s: any) => String(s.id) === cur);
          if (item) list.unshift(item);
        }
        strategyList.value = list;
      }
    }).catch(() => {});
    return;
  }

  // 选择器模式：加载全量列表
  try {
    const strategies = await strategyAPI.getStrategies();
    strategyList.value = Array.isArray(strategies) ? strategies : [];
  } catch { strategyList.value = []; }
  if (strategyList.value.length > 0) {
    selectedStrategy.value = String(strategyList.value[0].id);
  }
});

onUnmounted(() => {
  heatmapChartInstance?.dispose();
});

// heatmap 数据变更时重新渲染
watch(monthlyReturnsData, async () => {
  await nextTick();
  await nextTick();
  initHeatmap();
}, { deep: true });

watch(heatmapChart, (el) => {
  if (el) nextTick(() => initHeatmap());
});

</script>

<style lang="scss" scoped>
.strategy-performance {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.subplots-card {
  margin-top: 12px;
  background: var(--color-bg-card, rgba(12, 18, 32, 0.85));
  border-radius: 8px;
  padding: 8px 4px 4px;
}
/* .page-header 已迁移至全局样式（global.scss） */

.performance-overview {
  margin-bottom: 20px;
}
.metric-content {
  text-align: center;
}
.metric-content .metric-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}
.metric-content .metric-label {
  color: var(--n-text-color-3);
  font-size: 14px;
}
.positive {
  color: #67c23a;
}
.negative {
  color: #f56c6c;
}
.warning {
  color: #e6a23c;
}
.chart-row {
  margin-bottom: 20px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chart-container {
  height: 300px;
}
.metrics-card,
.heatmap-card {
  margin-bottom: 20px;
}
</style>
