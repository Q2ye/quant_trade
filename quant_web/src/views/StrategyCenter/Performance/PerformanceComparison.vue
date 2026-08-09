<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, h, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import VChart from "vue-echarts";
import { tokens } from "@/styles/design-tokens";
import {
  NCard, NButton, NSelect, NDatePicker, NDataTable, NTabs, NTabPane,
  NSpace, NSpin, NResult, NEmpty, NSkeleton,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import * as echarts from "echarts";

import strategyAPI from "@/api/strategy";
import performanceAPI from "@/api/performance";
import backtestAPI from "@/api/backtest";

interface MetricRow {
  metric: string;
  values: Record<string, number | string>;
  highlightIndex?: number; // index of best value
}

const loading = ref(false);
const error = ref(false);
const empty = ref(false);
const router = useRouter();
const route = useRoute();
const comparisonMetrics = ref<MetricRow[]>([]);
const selectedStrategies = ref<string[]>([]);
const dateRange = ref<[string, string] | null>(null);
const strategyOptions = ref<Array<{ label: string; value: string }>>([]);
const strategyNames = ref<Record<string, string>>({});
const equityCurveData = ref<Array<Record<string, any>>>([]);

// Chart options
const lineOption = ref<any>(null);

const metricColumns = computed<DataTableColumns<MetricRow>>(() => {
  const cols: DataTableColumns<MetricRow> = [
    { title: "指标", key: "metric", width: 120, fixed: "left" },
  ];
  selectedStrategies.value.forEach((sid, idx) => {
    cols.push({
      title: strategyNames.value[sid] || sid,
      key: `col_${idx}`,
      width: 120,
      render: (row: MetricRow) => {
        const val = row.values[sid];
        if (val === undefined || val === null) return h("span", "--");
        const isBest = row.highlightIndex === idx;
        const isNum = typeof val === "number";
        const color = isNum && (val as number) >= 0 ? "var(--n-success-color)" : "var(--n-error-color)";
        const text = isNum ? formatMetricVal(row.metric, val as number) : String(val);
        return h("span", {
          style: { color, fontWeight: isBest ? 700 : 400 },
        }, text);
      },
    });
  });
  return cols;
});

const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;
const formatMetricVal = (metric: string, v: number) => {
  if (metric.includes("率") && !metric.includes("波动率")) return fmtPct(v);
  if (metric.includes("回撤") || metric.includes("波动")) return fmtPct(v);
  if (metric.includes("夏普") || metric.includes("Sortino") || metric.includes("Calmar") || metric.includes("Alpha") || metric.includes("Beta") || metric.includes("比率") || metric.includes("因子")) return v.toFixed(2);
  if (metric.includes("交易")) return String(Math.round(v));
  return v.toFixed(4);
};

// Determine "best" value per row — lower is better for drawdown/volatility
const LOWER_IS_BETTER = ["最大回撤", "波动率"];

// 后端 StrategyComparison.to_dict() 返回 performance_comparison（dict keyed by sid）
// + rankings/correlations/statistics，无 strategies 数组、无 equity_curves。
// 前端适配：指标从 performance_comparison 读；净值曲线经回测接口按策略拉取。
const metricDefs = [
  { key: "total_return", label: "累计收益" },
  { key: "annual_return", label: "年化收益" },
  { key: "sharpe_ratio", label: "夏普比率" },
  { key: "sortino_ratio", label: "Sortino比率" },
  { key: "calmar_ratio", label: "Calmar比率" },
  { key: "max_drawdown", label: "最大回撤" },
  { key: "volatility", label: "波动率" },
  { key: "win_rate", label: "胜率" },
  { key: "profit_factor", label: "利润因子" },
  { key: "alpha", label: "Alpha" },
  { key: "beta", label: "Beta" },
  // 注：后端 PerformanceMetrics 无 total_trades 字段，已移除该指标
];

const buildMetrics = (data: any) => {
  if (!data || !data.performance_comparison || Object.keys(data.performance_comparison).length === 0) {
    return false;
  }
  const pc = data.performance_comparison as Record<string, Record<string, any>>;
  const sids = (data.strategy_ids && data.strategy_ids.length > 0)
    ? data.strategy_ids as string[]
    : Object.keys(pc);

  const metrics: MetricRow[] = [];
  metricDefs.forEach((def) => {
    const values: Record<string, number | string> = {};
    sids.forEach((sid) => {
      const m = pc[sid] || {};
      values[sid] = m[def.key] ?? "--";
    });
    // Find best
    let bestIdx = -1;
    const numericVals = sids.map((sid, i) => ({ i, v: Number(values[sid]) })).filter((x) => !isNaN(x.v));
    if (numericVals.length > 0) {
      bestIdx = LOWER_IS_BETTER.includes(def.label)
        ? numericVals.reduce((a, b) => (b.v < a.v ? b : a)).i
        : numericVals.reduce((a, b) => (b.v > a.v ? b : a)).i;
    }
    metrics.push({ metric: def.label, values, highlightIndex: bestIdx });
  });
  comparisonMetrics.value = metrics;
  return true;
};

const fetchEquityCurves = async (sids: string[]) => {
  // 与 StrategyPerformance 一致：取各策略最新完成回测的净值曲线 → 累计收益率%
  const eqData: Array<Record<string, any>> = [];
  for (const sid of sids) {
    try {
      const tasks: any = await backtestAPI.getTasks({ strategy_id: sid, status: "completed", page_size: 1 }).catch(() => []);
      const items = Array.isArray(tasks) ? tasks : (tasks?.data || tasks?.items || []);
      const task = items[0];
      if (!task) continue;
      const taskId = task.task_id || task.id;
      const eq = await backtestAPI.getEquityCurve(taskId).catch(() => []);
      const first = (eq[0] as any)?.equity || (eq[0] as any)?.total_assets || 1;
      (eq as any[]).forEach((p, i) => {
        const date = p.trade_date || p.date || `T${i}`;
        let row = eqData.find((r) => r.date === date);
        if (!row) { row = { date }; eqData.push(row); }
        row[sid] = (((p.equity ?? p.total_assets ?? 0) / first) - 1) * 100;
      });
    } catch { /* 单策略曲线失败跳过 */ }
  }
  equityCurveData.value = eqData;
  return eqData;
};

const buildLineOption = (eqData: Array<Record<string, any>>, sids: string[]) => {
  const dates = eqData.map((r) => r.date);
  const series = sids.map((sid: string, idx: number) => {
    const colors = ["#5470c6", "#18a058", "#f0a020", "#d03050", "#7c3aed", "#ff6d00"];
    return {
      name: strategyNames.value[sid] || sid,
      type: "line",
      data: eqData.map((r) => r[sid] ?? null),
      smooth: true,
      lineStyle: { width: 2 },
      itemStyle: { color: colors[idx % colors.length] },
      symbol: "none" as const,
    };
  });
  lineOption.value = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(20,20,40,0.92)",
      borderColor: "rgba(255,255,255,0.08)",
      textStyle: { color: "#ccc", fontSize: 12 },
    },
    legend: {
      data: sids.map((sid) => strategyNames.value[sid] || sid),
      bottom: 0,
      textStyle: { color: "#a0a0a0", fontSize: 11 },
    },
    grid: { left: "3%", right: "4%", top: 12, bottom: 40, containLabel: true },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: "#a0a0a0", fontSize: 10, rotate: dates.length > 12 ? 45 : 0 },
    },
    yAxis: { type: "value", axisLabel: { color: "#a0a0a0", fontSize: 10 } },
    series,
    dataZoom: dates.length > 60 ? [{ type: "inside" }, { type: "slider", bottom: 24 }] : undefined,
  };
};

const loadComparisonData = async () => {
  loading.value = true;
  error.value = false;
  empty.value = false;
  try {
    // Load strategy list for selector + 策略名称映射
    const strategies = await strategyAPI.getStrategies().catch(() => []);
    const stratList = Array.isArray(strategies) ? strategies : [];
    strategyOptions.value = stratList.map((s: any) => ({
      label: s.name || s.strategy_name || s.id,
      value: s.id || s.name,
    }));
    strategyNames.value = {};
    stratList.forEach((s: any) => {
      strategyNames.value[s.id || s.name] = s.name || s.strategy_name || s.id;
    });

    // Load comparison data
    if (selectedStrategies.value.length > 0) {
      const params: any = { benchmark: "000300.SH" };
      if (dateRange.value) {
        params.start_date = dateRange.value[0];
        params.end_date = dateRange.value[1];
      }
      const res: any = await performanceAPI.comparePerformance(
        selectedStrategies.value,
        params,
      );
      if (!res || !buildMetrics(res)) {
        empty.value = true;
        return;
      }
      const sids = (res.strategy_ids && res.strategy_ids.length > 0)
        ? res.strategy_ids
        : Object.keys(res.performance_comparison || {});
      const eq = await fetchEquityCurves(sids);
      buildLineOption(eq, sids);
    }
  } catch (err) {
    console.error("加载对比数据失败:", err);
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const onSelectionChange = () => {
  if (selectedStrategies.value.length > 0) {
    loadComparisonData();
  } else {
    comparisonMetrics.value = [];
    lineOption.value = null;
    empty.value = false;
  }
};

onMounted(() => {
  // 从策略绩效页「加入对比」跳转时自动预选该策略
  const qid = route.query.strategy_id as string | undefined;
  if (qid && !selectedStrategies.value.includes(qid)) {
    selectedStrategies.value = [qid];
  }
  loadComparisonData();
});
</script>

<template>
  <div class="performance-comparison-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">绩效对比</h1>
          <p class="page-description">多策略净值曲线对比与关键指标横向分析</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="router.push('/performance')" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>
    <div class="main-content">
      <n-spin :show="loading">
        <!-- Error -->
        <n-result
          v-if="error"
          status="500"
          title="加载失败"
          description="获取对比数据失败，请稍后重试"
        >
          <template #footer>
            <n-button type="primary" @click="loadComparisonData">重试</n-button>
          </template>
        </n-result>

        <!-- Selection card (always visible) -->
        <n-card :class="tokens.surface.card" size="small">
          <template #header-extra>
            <n-space>
              <n-select
                v-model:value="selectedStrategies"
                multiple
                placeholder="选择对比策略（可多选，至少选 2 个）"
                style="width: 360px"
                :options="strategyOptions"
                @update:value="onSelectionChange"
              />
                <n-date-picker
                  v-model:formatted-value="dateRange"
                  type="daterange"
                  clearable
                  @update:formatted-value="loadComparisonData"
                />
              </n-space>
            </template>

            <n-tabs>
              <n-tab-pane name="chart" tab="净值曲线">
                <n-empty v-if="selectedStrategies.length < 2" description="请在上方选择至少两个策略" style="padding:40px" />
                <div v-else-if="lineOption" style="height: 420px">
                  <v-chart :option="lineOption" autoresize style="height: 100%" />
                </div>
                <n-empty v-else description="暂无净值曲线数据" style="padding:40px" />
              </n-tab-pane>

              <n-tab-pane name="metrics" tab="绩效指标">
                <n-empty v-if="selectedStrategies.length < 2" description="请在上方选择至少两个策略" style="padding:40px" />
                <n-data-table
                  v-else-if="comparisonMetrics.length > 0"
                  :data="comparisonMetrics"
                  :columns="metricColumns"
                  :pagination="false"
                  :row-key="(row: MetricRow) => row.metric"
                  size="small"
                  :single-line="false"
                />
                <n-empty v-else description="暂无指标数据" style="padding:40px" />
              </n-tab-pane>

              <n-tab-pane name="risk" tab="风险收益散点图">
                <n-empty v-if="selectedStrategies.length < 2" description="请在上方选择至少两个策略" style="padding:40px" />
                <div v-else-if="lineOption && selectedStrategies.length >= 2" style="height: 400px">
                  <v-chart :option="{
                    backgroundColor: 'transparent',
                    tooltip: {
                      trigger: 'item' as const,
                      backgroundColor: 'rgba(20,20,40,0.92)',
                      borderColor: 'rgba(255,255,255,0.08)',
                      textStyle: { color: '#ccc', fontSize: 12 },
                      formatter: (p: any) => `${p.name}<br/>收益: ${(p.value[1]*100).toFixed(1)}%<br/>风险: ${(p.value[0]*100).toFixed(1)}%`,
                    },
                    grid: { left: '8%', right: '8%', top: 24, bottom: 24, containLabel: true },
                    xAxis: {
                      type: 'value' as const,
                      name: '年化波动率',
                      axisLabel: { color: '#a0a0a0', formatter: '{value}%' },
                    },
                    yAxis: {
                      type: 'value' as const,
                      name: '年化收益率',
                      axisLabel: { color: '#a0a0a0', formatter: '{value}%' },
                    },
                    series: [{
                      type: 'scatter' as const,
                      data: selectedStrategies.map((sid) => {
                        const metrics: any[] = comparisonMetrics;
                        const volRow = metrics.find((m: any) => m.metric === '波动率');
                        const retRow = metrics.find((m: any) => m.metric === '年化收益');
                        const vol = Number(volRow?.values?.[sid]) || 0;
                        const ret = Number(retRow?.values?.[sid]) || 0;
                        return { value: [vol, ret], name: strategyNames[sid] || sid };
                      }),
                      symbolSize: 14,
                      itemStyle: { color: '#7c3aed' },
                      label: { show: true, formatter: (p: any) => p.name || '' },
                    }],
                  }" autoresize style="height: 100%" />
                </div>
                <n-empty v-else description="需要至少两个策略" style="padding:40px" />
              </n-tab-pane>
            </n-tabs>
          </n-card>
      </n-spin>
    </div>
  </div>
</template>

<style scoped>
.performance-comparison-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}
.main-content {
  padding: 0 19px 24px;
}
</style>
