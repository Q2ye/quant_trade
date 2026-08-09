<!-- AttributionAnalysis.vue — 归因分析：Brinson归因 + 多因子归因，vue-echarts 声明式图表 -->
<template>
  <div class="attribution-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">归因分析</h1>
          <p class="page-description">分解策略超额收益来源：配置效应 · 选股效应 · 因子暴露</p>
        </div>
        <div class="header-actions">
          <n-select
            v-model:value="analysisConfig.strategy"
            placeholder="选择策略"
            :options="strategyOptions"
            style="width: 200px"
          />
          <n-date-picker
            v-model:value="analysisConfig.dateRange"
            type="daterange"
            style="width: 240px; margin-left: 10px"
          />
          <n-select
            v-model:value="analysisConfig.attributionModel"
            placeholder="归因模型"
            :options="modelOptions"
            style="width: 150px"
          />
          <n-button type="primary" @click="runAttributionAnalysis">
            <SmartIcon name="Search" /> 分析
          </n-button>
          <n-button class="action-btn" @click="router.push('/performance')" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <template v-if="loading">
        <div class="chart-row">
          <n-card v-for="i in 3" :key="i" :class="tokens.surface.card" size="small" style="flex:1">
            <n-skeleton text :repeat="3" />
          </n-card>
        </div>
        <n-card :class="tokens.surface.card" size="small" style="margin-top:12px">
          <n-skeleton text :repeat="5" />
        </n-card>
      </template>

      <!-- Error -->
      <n-result v-else-if="error" status="500" title="加载失败" description="获取归因数据失败">
        <template #footer><n-button type="primary" @click="runAttributionAnalysis">重试</n-button></template>
      </n-result>

      <!-- Not analyzed yet -->
      <n-empty v-else-if="!analysisRun" description="请选择策略和归因模型，点击「分析」按钮开始分析" style="padding:60px 0" />

      <!-- Empty -->
      <n-empty v-else-if="empty" description="暂无归因数据，请选择策略后进行分析" style="padding:60px 0" />

      <!-- Data -->
      <template v-else>
        <!-- ====== Row 1：三大图表卡片 ====== -->
        <div class="chart-row">
        <n-card :class="tokens.surface.card" size="small" style="flex:1">
          <template #header><span class="card-title">超额收益分解</span></template>
          <v-chart v-if="pieOption" :option="pieOption" autoresize style="height: 280px" />
        </n-card>
        <n-card :class="tokens.surface.card" size="small" style="flex:1">
          <template #header><span class="card-title">行业配置贡献</span></template>
          <v-chart v-if="barOption" :option="barOption" autoresize style="height: 280px" />
        </n-card>
        <n-card :class="tokens.surface.card" size="small" style="flex:1">
          <template #header><span class="card-title">风格因子暴露</span></template>
          <v-chart v-if="radarOption" :option="radarOption" autoresize style="height: 280px" />
          <n-empty v-else description="该模型不输出因子暴露" size="small" style="padding:40px 0" />
        </n-card>
      </div>

      <!-- ====== Row 2：归因表格 ====== -->
      <n-card :class="tokens.surface.card" size="small" style="margin-top:12px">
        <n-tabs v-model:value="activeTab" size="small">
          <n-tab-pane name="brinson" tab="Brinson 归因">
            <n-data-table
              :data="brinsonAttribution"
              :columns="brinsonColumns"
              :bordered="false"
              striped
              size="small"
            />
          </n-tab-pane>
          <n-tab-pane name="factor" tab="多因子归因">
            <n-data-table
              :data="factorAttribution"
              :columns="factorColumns"
              :bordered="false"
              striped
              size="small"
            />
          </n-tab-pane>
          <n-tab-pane name="timeseries" tab="时序归因">
            <v-chart v-if="tsOption" :option="tsOption" autoresize style="height: 320px" />
            <n-empty v-else description="暂无时序归因数据（后端暂未计算）" size="small" style="padding:40px" />
          </n-tab-pane>
        </n-tabs>
      </n-card>

      <!-- ====== Row 3：摘要 + 风控指标 ====== -->
      <div class="summary-row">
        <n-card :class="tokens.surface.card" size="small" style="flex:1">
          <template #header><span class="card-title">归因统计摘要</span></template>
          <div class="stat-list">
            <div class="stat-row"><span class="stat-label">分析期间</span><span class="stat-value">{{ dateLabel }}</span></div>
            <div class="stat-divider" />
            <div class="stat-row">
              <span class="stat-label">总超额收益</span>
              <span :class="['stat-value', vclass(attributionSummary.totalExcessReturn)]">
                {{ fmtPct(attributionSummary.totalExcessReturn) }}
              </span>
            </div>
            <div class="stat-divider" />
            <div class="stat-row">
              <span class="stat-label">配置效应</span>
              <span :class="['stat-value', vclass(attributionSummary.allocationContribution)]">
                {{ fmtPct(attributionSummary.allocationContribution) }}
              </span>
            </div>
            <div class="stat-divider" />
            <div class="stat-row">
              <span class="stat-label">选股效应</span>
              <span :class="['stat-value', vclass(attributionSummary.selectionContribution)]">
                {{ fmtPct(attributionSummary.selectionContribution) }}
              </span>
            </div>
            <div class="stat-divider" />
            <div class="stat-row">
              <span class="stat-label">可解释度 (R²)</span>
              <span class="stat-value">{{ (attributionSummary.rSquared * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </n-card>

        <n-card :class="tokens.surface.card" size="small" style="flex:1">
          <template #header><span class="card-title">风险调整指标</span></template>
          <div class="stat-list">
            <div class="stat-row"><span class="stat-label">信息比率</span><span class="stat-value">{{ attributionSummary.informationRatio.toFixed(2) }}</span></div>
            <div class="stat-divider" />
            <div class="stat-row"><span class="stat-label">主动份额</span><span class="stat-value">{{ fmtPct(attributionSummary.activeShare) }}</span></div>
            <div class="stat-divider" />
            <div class="stat-row"><span class="stat-label">主动风险</span><span class="stat-value">{{ fmtPct(attributionSummary.activeRisk) }}</span></div>
            <div class="stat-divider" />
            <div class="stat-row"><span class="stat-label">Beta 系数</span><span class="stat-value">{{ attributionSummary.beta.toFixed(2) }}</span></div>
            <div class="stat-divider" />
            <div class="stat-row">
              <span class="stat-label">Alpha 收益</span>
              <span :class="['stat-value', vclass(attributionSummary.alpha)]">{{ fmtPct(attributionSummary.alpha) }}</span>
            </div>
          </div>
        </n-card>
      </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, h, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import VChart from "vue-echarts";
import { NCard, NButton, NSelect, NDatePicker, NDataTable, NTabs, NTabPane, NTag, NSkeleton, NResult, NEmpty, useMessage } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import strategyAPI from "@/api/strategy";
import performanceAPI from "@/api/performance";

const message = useMessage();
const router = useRouter();
const route = useRoute();

// State
const loading = ref(false);
const error = ref(false);
const empty = ref(false);

// ---- Dark theme chart colors ----
const C = {
  purple: "#7C3AED",
  green: "#18A058",
  yellow: "#F0A020",
  red: "#D03050",
  blue: "#448AFF",
  cyan: "#00BCD4",
  orange: "#FF6D00",
  text: "#a0a0a0",
  textLight: "#cccccc",
  gridLine: "rgba(255,255,255,0.06)",
  bgTransparent: "transparent",
};

// ---- Config ----
const analysisConfig = reactive({
  strategy: "" as string | number,
  dateRange: null as any,
  attributionModel: "multi-factor",
});

const strategyList = ref<any[]>([]);
const strategyOptions = computed(() =>
  strategyList.value.map((s: any) => ({ label: s.name ?? s.id, value: String(s.id) }))
);
const modelOptions = [
  { label: "Brinson 模型", value: "brinson" },
  { label: "多因子模型", value: "multi-factor" },
];

const activeTab = ref("brinson");

// ---- Helpers ----
const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;
const vclass = (v: number) => (v >= 0 ? "text-up" : "text-down");

const dateLabel = computed(() => {
  const dr = analysisConfig.dateRange;
  if (!dr) return "2023-01-01 — 2023-12-31";
  if (Array.isArray(dr) && dr.length === 2) {
    return `${new Date(dr[0]).toLocaleDateString()} — ${new Date(dr[1]).toLocaleDateString()}`;
  }
  return "—";
});

// ---- Static attribution data ----
// Track whether real analysis has been run (not initial fake data)
const analysisRun = ref(false);

const attributionSummary = reactive({
  totalExcessReturn: 0,
  allocationContribution: 0,
  selectionContribution: 0,
  interactionContribution: 0,
  rSquared: 0,
  trackingError: 0,
  informationRatio: 0,
  activeShare: 0,
  activeRisk: 0,
  beta: 0,
  alpha: 0,
});

const brinsonAttribution = ref<any[]>([]);
const factorAttribution = ref<any[]>([]);

// ---- ECharts Options (computed) ----
const pieOption = computed(() => ({
  backgroundColor: C.bgTransparent,
  tooltip: {
    trigger: "item" as const,
    backgroundColor: "rgba(20,20,40,0.92)",
    borderColor: "rgba(255,255,255,0.08)",
    textStyle: { color: C.textLight, fontSize: 12 },
    formatter: "{b}: {c}% ({d}%)",
  },
  legend: {
    orient: "vertical" as const,
    right: 8,
    top: "center",
    textStyle: { color: C.text, fontSize: 11 },
  },
  series: [{
    name: "超额收益分解",
    type: "pie",
    radius: ["48%", "76%"],
    center: ["40%", "50%"],
    avoidLabelOverlap: false,
    itemStyle: { borderRadius: 6, borderColor: "rgba(0,0,0,0.3)", borderWidth: 2 },
    label: { show: false },
    emphasis: { label: { show: true, fontSize: 16, fontWeight: "bold" } },
    data: (() => {
      const s = attributionSummary;
      const selec = s.selectionContribution * 100;
      const alloc = s.allocationContribution * 100;
      const inter = s.interactionContribution * 100;
      const total = s.totalExcessReturn * 100;
      const unexplained = total - (selec + alloc + inter);
      const items: any[] = [
        { value: +selec.toFixed(2), name: "选股效应", itemStyle: { color: C.purple } },
        { value: +alloc.toFixed(2), name: "配置效应", itemStyle: { color: C.green } },
        { value: +inter.toFixed(2), name: "交互效应", itemStyle: { color: C.yellow } },
      ];
      if (Math.abs(unexplained) > 0.01) {
        items.push({ value: +unexplained.toFixed(2), name: "不可解释", itemStyle: { color: C.red } });
      }
      return items;
    })(),
  }],
}));

const barOption = computed(() => {
  const categories = brinsonAttribution.value.map((d) => d.category);
  const values = brinsonAttribution.value.map((d) => +(d.totalEffect * 100).toFixed(2));
  return {
    backgroundColor: C.bgTransparent,
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(20,20,40,0.92)",
      borderColor: "rgba(255,255,255,0.08)",
      textStyle: { color: C.textLight, fontSize: 12 },
      formatter: (p: any) => `${p[0].name}<br/>总效应: ${p[0].value > 0 ? "+" : ""}${p[0].value}%`,
    },
    grid: { left: "3%", right: "8%", bottom: "3%", top: "8%", containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: { color: C.text, formatter: "{value}%", fontSize: 10 },
      splitLine: { lineStyle: { color: C.gridLine } },
    },
    yAxis: {
      type: "category",
      data: categories,
      axisLabel: { color: C.textLight, fontSize: 11 },
      axisLine: { lineStyle: { color: C.gridLine } },
    },
    series: [{
      type: "bar",
      data: values.map((v, i) => ({
        value: v,
        itemStyle: {
          color: v >= 0 ? C.green : C.red,
          borderRadius: v >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
        },
      })),
      barWidth: 16,
      label: { show: true, position: "right", color: C.text, fontSize: 10, formatter: "{c}%" },
    }],
  };
});

// 风格因子暴露雷达图：仅多因子模型有 factor_attribution.exposures 数据；
// Brinson 模型无该维度 → 返回 null，模板显示空态提示
const radarOption = computed(() => {
  const fac = factorAttribution.value;
  if (!fac || fac.length === 0) return null;
  const strategyVals = fac.map((f) => f.exposure || 0);
  const maxAbs = Math.max(...strategyVals.map((v) => Math.abs(v)), 0.1);
  const max = +(maxAbs * 1.2).toFixed(2);
  return {
    backgroundColor: C.bgTransparent,
    tooltip: { backgroundColor: "rgba(20,20,40,0.92)", borderColor: "rgba(255,255,255,0.08)", textStyle: { color: C.textLight, fontSize: 12 } },
    legend: {
      data: ["策略暴露"],
      bottom: 0,
      textStyle: { color: C.text, fontSize: 11 },
    },
    radar: {
      center: ["50%", "50%"],
      radius: "65%",
      indicator: fac.map((f) => ({ name: f.factor, max })),
      axisName: { color: C.textLight, fontSize: 10 },
      splitArea: { areaStyle: { color: ["rgba(124,58,237,0.02)", "rgba(124,58,237,0.04)"] } },
      splitLine: { lineStyle: { color: C.gridLine } },
      axisLine: { lineStyle: { color: C.gridLine } },
    },
    series: [
      {
        name: "策略暴露",
        type: "radar",
        data: [{ value: strategyVals, name: "策略暴露" }],
        areaStyle: { color: "rgba(124,58,237,0.25)" },
        lineStyle: { color: C.purple, width: 2 },
        itemStyle: { color: C.purple },
        symbol: "circle",
        symbolSize: 4,
      },
    ],
  };
});

// 时序归因：后端当前不计算 time_series_attribution（为空），始终显示空态提示
const tsOption = computed(() => null);

// ---- Table columns ----
const brinsonColumns = computed(() => [
  { title: "行业", key: "category", width: 80 },
  {
    title: "配置效应", key: "allocationEffect", width: 100,
    render: (row: any) => h("span", { class: vclass(row.allocationEffect) }, `${(row.allocationEffect * 100).toFixed(2)}%`),
  },
  {
    title: "选股效应", key: "selectionEffect", width: 100,
    render: (row: any) => h("span", { class: vclass(row.selectionEffect) }, `${(row.selectionEffect * 100).toFixed(2)}%`),
  },
  {
    title: "交互效应", key: "interactionEffect", width: 100,
    render: (row: any) => h("span", { class: vclass(row.interactionEffect) }, `${(row.interactionEffect * 100).toFixed(2)}%`),
  },
  {
    title: "总效应", key: "totalEffect", width: 100,
    render: (row: any) => h("span", { class: vclass(row.totalEffect), style: "font-weight:600" }, `${(row.totalEffect * 100).toFixed(2)}%`),
  },
]);

const factorColumns = computed(() => [
  { title: "因子", key: "factor", width: 110 },
  {
    title: "暴露度", key: "exposure", width: 90,
    render: (row: any) => h("span", { class: Math.abs(row.exposure) > 0.2 ? "text-up" : "" }, row.exposure.toFixed(3)),
  },
  {
    title: "因子收益", key: "factorReturn", width: 100,
    render: (row: any) => h("span", { class: vclass(row.factorReturn) }, `${(row.factorReturn * 100).toFixed(2)}%`),
  },
  {
    title: "归因贡献", key: "attribution", width: 100,
    render: (row: any) => h("span", { class: vclass(row.attribution) }, `${(row.attribution * 100).toFixed(2)}%`),
  },
  {
    title: "T 统计量", key: "tStat", width: 80,
    render: (row: any) => h("span", { class: Math.abs(row.tStat) >= 2 ? "text-up" : "" }, row.tStat.toFixed(2)),
  },
  {
    title: "显著性", key: "significance", width: 80,
    render: (row: any) => h(NTag, { type: row.significance === "显著" ? "success" : "default", size: "small" }, { default: () => row.significance }),
  },
]);

// ---- Actions ----
const runAttributionAnalysis = async () => {
  if (!analysisConfig.strategy) {
    message.warning("请选择策略");
    return;
  }
  loading.value = true; error.value = false; empty.value = false;
  try {
    const params: any = {};
    const dr = analysisConfig.dateRange;
    if (dr && Array.isArray(dr) && dr.length === 2) {
      const [start, end] = dr;
      if (start) params.start_date = new Date(start).toISOString().split("T")[0];
      if (end) params.end_date = new Date(end).toISOString().split("T")[0];
    }
    const res = await performanceAPI.getAttribution(String(analysisConfig.strategy), params);
    if (res) {
      // 适配后端 AttributionAnalysis.to_dict() 结构：
      // { return_decomposition, brinson_attribution, factor_attribution,
      //   sector_attribution, stock_attribution, quality_metrics }
      const rd = res.return_decomposition || {};
      const ba = res.brinson_attribution || {};
      const qm = res.quality_metrics || {};
      const active = rd.active_return ?? rd.total_return ?? 0;
      const alloc = ba.allocation_effect ?? 0;
      const selec = ba.selection_effect ?? 0;
      const inter = ba.interaction_effect ?? 0;

      Object.assign(attributionSummary, {
        totalExcessReturn: active,
        allocationContribution: alloc,
        selectionContribution: selec,
        interactionContribution: inter,
        rSquared: qm.attribution_r_squared ?? 0,
        trackingError: qm.tracking_error_explained ?? 0,
      });

      // Brinson 表/柱图 ← sector/stock attributions（dict {sector: effect}）
      const secAttrib = res.sector_attribution?.attributions
        || res.stock_attribution?.attributions || {};
      brinsonAttribution.value = Object.entries(secAttrib).map(([category, v]) => ({
        category,
        allocationEffect: alloc,
        selectionEffect: selec,
        interactionEffect: inter,
        totalEffect: Number(v) || 0,
      }));

      // 因子归因表 ← factor_attribution.attributions（dict {factor: value}）
      const facAttrib = res.factor_attribution?.attributions || {};
      const facExpo = res.factor_attribution?.exposures || {};
      factorAttribution.value = Object.entries(facAttrib).map(([factor, v]) => ({
        factor,
        exposure: Number(facExpo[factor] ?? 0),
        factorReturn: 0,
        attribution: Number(v) || 0,
        tStat: 0,
        significance: "—",
      }));

      analysisRun.value = true;
      const hasData = Object.keys(rd).length > 0
        || Object.keys(secAttrib).length > 0
        || Object.keys(facAttrib).length > 0;
      if (!hasData) empty.value = true;
    } else {
      empty.value = true;
    }
  } catch (err) {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  try {
    const strategies = await strategyAPI.getStrategies();
    strategyList.value = Array.isArray(strategies) ? strategies : [];
  } catch { strategyList.value = []; }
  const qid = route.query.strategy_id as string | undefined;
  if (strategyList.value.length > 0) {
    if (qid && strategyList.value.some((s: any) => String(s.id) === qid)) {
      analysisConfig.strategy = qid;
    } else {
      analysisConfig.strategy = String(strategyList.value[0].id);
    }
  }
  // 带 strategy_id 进入时自动执行分析，避免再手动点「分析」
  if (qid && analysisConfig.strategy) {
    await runAttributionAnalysis();
  }
});
</script>

<style lang="scss" scoped>
.attribution-page { height: 100%; overflow-y: auto; }
.main-content { padding: 0 19px 24px; }

.card-title { font-size: 13px; font-weight: 600; color: var(--color-text-primary); }

/* 图表行 — 三列等宽 */
.chart-row { display: flex; gap: 12px; }

/* 摘要行 */
.summary-row { display: flex; gap: 12px; margin-top: 12px; }

/* 统计列表 */
.stat-list { display: flex; flex-direction: column; }
.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; }
.stat-label { font-size: 13px; color: var(--color-text-tertiary); }
.stat-value { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.stat-divider { height: 1px; background: rgba(255,255,255,0.04); }

.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }
</style>
