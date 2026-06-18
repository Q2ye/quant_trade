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
        </div>
      </div>
    </div>

    <div class="main-content">
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, h, onMounted } from "vue";
import VChart from "vue-echarts";
import { NCard, NButton, NSelect, NDatePicker, NDataTable, NTabs, NTabPane, NTag, useMessage } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import strategyAPI from "@/api/strategy";

const message = useMessage();

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
  attributionModel: "brinson",
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
const attributionSummary = reactive({
  totalExcessReturn: 0.0456,
  allocationContribution: 0.0123,
  selectionContribution: 0.0289,
  interactionContribution: 0.0044,
  rSquared: 0.856,
  trackingError: 0.0345,
  informationRatio: 1.32,
  activeShare: 0.782,
  activeRisk: 0.0289,
  beta: 0.95,
  alpha: 0.0234,
});

const brinsonAttribution = ref([
  { category: "金融", allocationEffect: 0.0089, selectionEffect: 0.0156, interactionEffect: 0.0023, totalEffect: 0.0268 },
  { category: "科技", allocationEffect: 0.0056, selectionEffect: 0.0089, interactionEffect: 0.0012, totalEffect: 0.0157 },
  { category: "消费", allocationEffect: -0.0023, selectionEffect: 0.0045, interactionEffect: 0.0009, totalEffect: 0.0031 },
  { category: "医药", allocationEffect: 0.0034, selectionEffect: -0.0012, interactionEffect: 0.0005, totalEffect: 0.0027 },
  { category: "工业", allocationEffect: -0.0045, selectionEffect: 0.0023, interactionEffect: -0.0008, totalEffect: -0.0030 },
  { category: "能源", allocationEffect: -0.0023, selectionEffect: 0.0011, interactionEffect: -0.0003, totalEffect: -0.0015 },
  { category: "其他", allocationEffect: -0.0033, selectionEffect: 0.0011, interactionEffect: -0.0005, totalEffect: -0.0027 },
]);

const factorAttribution = ref([
  { factor: "市值因子", exposure: 0.234, factorReturn: 0.0156, attribution: 0.0036, tStat: 2.34, significance: "显著" },
  { factor: "价值因子", exposure: 0.189, factorReturn: 0.0234, attribution: 0.0044, tStat: 3.12, significance: "显著" },
  { factor: "动量因子", exposure: 0.156, factorReturn: -0.0089, attribution: -0.0014, tStat: -1.45, significance: "不显著" },
  { factor: "质量因子", exposure: 0.278, factorReturn: 0.0189, attribution: 0.0052, tStat: 2.89, significance: "显著" },
  { factor: "波动率因子", exposure: -0.134, factorReturn: -0.0123, attribution: 0.0016, tStat: 1.78, significance: "显著" },
  { factor: "成长因子", exposure: 0.167, factorReturn: 0.0112, attribution: 0.0019, tStat: 1.56, significance: "不显著" },
]);

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
    data: [
      { value: 45.6, name: "选股效应", itemStyle: { color: C.purple } },
      { value: 26.9, name: "配置效应", itemStyle: { color: C.green } },
      { value: 9.6, name: "交互效应", itemStyle: { color: C.yellow } },
      { value: 17.9, name: "不可解释", itemStyle: { color: C.red } },
    ],
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

const radarOption = computed(() => ({
  backgroundColor: C.bgTransparent,
  tooltip: { backgroundColor: "rgba(20,20,40,0.92)", borderColor: "rgba(255,255,255,0.08)", textStyle: { color: C.textLight, fontSize: 12 } },
  legend: {
    data: ["策略暴露", "基准暴露"],
    bottom: 0,
    textStyle: { color: C.text, fontSize: 11 },
  },
  radar: {
    center: ["50%", "48%"],
    radius: "65%",
    indicator: [
      { name: "市值", max: 0.3 },
      { name: "价值", max: 0.3 },
      { name: "动量", max: 0.3 },
      { name: "质量", max: 0.3 },
      { name: "波动率", max: 0.3 },
      { name: "成长", max: 0.3 },
    ],
    axisName: { color: C.textLight, fontSize: 10 },
    splitArea: { areaStyle: { color: ["rgba(124,58,237,0.02)", "rgba(124,58,237,0.04)"] } },
    splitLine: { lineStyle: { color: C.gridLine } },
    axisLine: { lineStyle: { color: C.gridLine } },
  },
  series: [
    {
      name: "策略暴露",
      type: "radar",
      data: [{ value: [0.234, 0.189, 0.156, 0.278, 0.134, 0.167], name: "策略暴露" }],
      areaStyle: { color: "rgba(124,58,237,0.25)" },
      lineStyle: { color: C.purple, width: 2 },
      itemStyle: { color: C.purple },
      symbol: "circle",
      symbolSize: 4,
    },
    {
      name: "基准暴露",
      type: "radar",
      data: [{ value: [0.156, 0.234, 0.123, 0.189, 0.167, 0.145], name: "基准暴露" }],
      areaStyle: { color: "rgba(24,160,88,0.25)" },
      lineStyle: { color: C.green, width: 2, type: "dashed" },
      itemStyle: { color: C.green },
      symbol: "diamond",
      symbolSize: 4,
    },
  ],
}));

const tsOption = computed(() => ({
  backgroundColor: C.bgTransparent,
  tooltip: {
    trigger: "axis" as const,
    backgroundColor: "rgba(20,20,40,0.92)",
    borderColor: "rgba(255,255,255,0.08)",
    textStyle: { color: C.textLight, fontSize: 12 },
  },
  legend: {
    data: ["累计超额收益", "配置效应", "选股效应", "交互效应"],
    bottom: 0,
    textStyle: { color: C.text, fontSize: 11 },
  },
  grid: { left: "3%", right: "4%", bottom: "12%", top: "8%", containLabel: true },
  xAxis: {
    type: "category",
    data: ["Q1", "Q2", "Q3", "Q4"],
    axisLabel: { color: C.text, fontSize: 11 },
    axisLine: { lineStyle: { color: C.gridLine } },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: C.text, formatter: "{value}%", fontSize: 10 },
    splitLine: { lineStyle: { color: C.gridLine } },
  },
  series: [
    {
      name: "累计超额收益",
      type: "line",
      data: [1.2, 2.8, 3.5, 4.6],
      smooth: true,
      lineStyle: { color: C.purple, width: 3 },
      itemStyle: { color: C.purple },
      symbol: "circle",
      symbolSize: 6,
      areaStyle: { color: "rgba(124,58,237,0.12)" },
    },
    {
      name: "配置效应", type: "bar", data: [0.8, 1.2, 1.0, 1.3],
      itemStyle: { color: C.green, borderRadius: [3, 3, 0, 0] }, barWidth: "25%", barGap: "10%",
    },
    {
      name: "选股效应", type: "bar", data: [0.3, 1.4, 2.2, 2.9],
      itemStyle: { color: C.yellow, borderRadius: [3, 3, 0, 0] }, barWidth: "25%", barGap: "10%",
    },
    {
      name: "交互效应", type: "bar", data: [0.1, 0.2, 0.3, 0.4],
      itemStyle: { color: C.orange, borderRadius: [3, 3, 0, 0] }, barWidth: "25%", barGap: "10%",
    },
  ],
}));

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
const runAttributionAnalysis = () => {
  if (!analysisConfig.strategy) {
    message.warning("请选择策略");
    return;
  }
  // 当前使用静态演示数据，后续接入真实 API
};

onMounted(async () => {
  try {
    const strategies = await strategyAPI.getStrategies();
    strategyList.value = Array.isArray(strategies) ? strategies : [];
  } catch { strategyList.value = []; }
  if (strategyList.value.length > 0) analysisConfig.strategy = String(strategyList.value[0].id);
});
</script>

<style lang="scss" scoped>
.attribution-page { height: 100%; overflow-y: auto; }
.main-content { padding: 16px 32px 24px; }

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
