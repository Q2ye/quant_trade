<template>
  <n-spin :show="loading" class="attribution-analysis">
    <n-result
      v-if="error"
      status="500"
      title="分析失败"
      description="归因分析失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="runAttributionAnalysis">重试</n-button></template
      >
    </n-result>

    <template v-else>
      <div class="page-header">
        <h1 class="page-title">归因分析</h1>
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
            :is-date-disabled="() => false"
            style="width: 240px; margin-left: 10px"
          />
          <n-select
            v-model:value="analysisConfig.attributionModel"
            placeholder="归因模型"
            :options="modelOptions"
            style="width: 150px"
          />
          <n-button type="primary" @click="runAttributionAnalysis">
            <Icon icon="ep:search" />
            分析
          </n-button>
        </div>
      </div>

      <n-grid :x-gap="16" :cols="24" class="attribution-overview">
        <n-grid-item :span="8">
          <n-card class="attribution-card">
            <template #header><span>超额收益分解</span></template>
            <div ref="attributionChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>
        <n-grid-item :span="8">
          <n-card class="attribution-card">
            <template #header><span>行业配置贡献</span></template>
            <div ref="industryChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>
        <n-grid-item :span="8">
          <n-card class="attribution-card">
            <template #header><span>风格因子暴露</span></template>
            <div ref="factorExposureChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <n-card class="detailed-attribution">
        <template #header><span>详细归因结果</span></template>
        <n-tabs v-model:value="activeTab">
          <n-tab-pane name="brinson" tab="Brinson归因">
            <n-data-table
              :data="brinsonAttribution"
              :columns="brinsonColumns"
              :loading="loading"
              :bordered="false"
              striped
            />
          </n-tab-pane>
          <n-tab-pane name="multiFactor" tab="多因子归因">
            <n-data-table
              :data="factorAttribution"
              :columns="factorColumns"
              :loading="loading"
              :bordered="false"
              striped
            />
          </n-tab-pane>
          <n-tab-pane name="timeSeries" tab="时间序列归因">
            <div
              ref="timeSeriesChart"
              class="chart-container"
              style="height: 400px"
            ></div>
          </n-tab-pane>
        </n-tabs>
      </n-card>

      <n-grid :x-gap="16" :cols="24" class="summary-row">
        <n-grid-item :span="12">
          <n-card class="summary-card">
            <template #header><span>归因统计摘要</span></template>
            <n-descriptions :column="2" bordered>
              <n-descriptions-item label="分析期间">{{
                dateLabel
              }}</n-descriptions-item>
              <n-descriptions-item label="总超额收益">
                <span
                  :class="getEffectClass(attributionSummary.totalExcessReturn)"
                  >{{
                    formatPercent(attributionSummary.totalExcessReturn)
                  }}</span
                >
              </n-descriptions-item>
              <n-descriptions-item label="配置效应贡献">
                <span
                  :class="
                    getEffectClass(attributionSummary.allocationContribution)
                  "
                  >{{
                    formatPercent(attributionSummary.allocationContribution)
                  }}</span
                >
              </n-descriptions-item>
              <n-descriptions-item label="选股效应贡献">
                <span
                  :class="
                    getEffectClass(attributionSummary.selectionContribution)
                  "
                  >{{
                    formatPercent(attributionSummary.selectionContribution)
                  }}</span
                >
              </n-descriptions-item>
              <n-descriptions-item label="可解释度(R²)"
                >{{
                  (attributionSummary.rSquared * 100).toFixed(1)
                }}%</n-descriptions-item
              >
              <n-descriptions-item label="跟踪误差">{{
                formatPercent(attributionSummary.trackingError)
              }}</n-descriptions-item>
            </n-descriptions>
          </n-card>
        </n-grid-item>
        <n-grid-item :span="12">
          <n-card class="summary-card">
            <template #header><span>风险调整指标</span></template>
            <n-descriptions :column="2" bordered>
              <n-descriptions-item label="信息比率">{{
                attributionSummary.informationRatio.toFixed(2)
              }}</n-descriptions-item>
              <n-descriptions-item label="主动份额">{{
                formatPercent(attributionSummary.activeShare)
              }}</n-descriptions-item>
              <n-descriptions-item label="主动风险">{{
                formatPercent(attributionSummary.activeRisk)
              }}</n-descriptions-item>
              <n-descriptions-item label="Beta系数">{{
                attributionSummary.beta.toFixed(2)
              }}</n-descriptions-item>
              <n-descriptions-item label="Alpha收益">
                <span :class="getEffectClass(attributionSummary.alpha)">{{
                  formatPercent(attributionSummary.alpha)
                }}</span>
              </n-descriptions-item>
              <n-descriptions-item label="Alpha显著性">
                <n-tag
                  :type="
                    attributionSummary.alphaSignificant ? 'success' : 'info'
                  "
                  size="small"
                >
                  {{ attributionSummary.alphaSignificant ? "显著" : "不显著" }}
                </n-tag>
              </n-descriptions-item>
            </n-descriptions>
          </n-card>
        </n-grid-item>
      </n-grid>
    </template>
  </n-spin>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from "vue";
import { useMessage, NTag } from "naive-ui";
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
const activeTab = ref("brinson");
const attributionChart = ref<HTMLElement>();
const industryChart = ref<HTMLElement>();
const factorExposureChart = ref<HTMLElement>();
const timeSeriesChart = ref<HTMLElement>();

const analysisConfig = reactive({
  strategy: "" as string | number,
  dateRange: null as any,
  attributionModel: "brinson",
});

const strategyList = ref([
  { id: "1", name: "双均线策略" },
  { id: "2", name: "动量反转策略" },
  { id: "3", name: "均值回归策略" },
]);
const strategyOptions = computed(() =>
  strategyList.value.map((s) => ({ label: s.name, value: s.id })),
);
const modelOptions = [
  { label: "Brinson模型", value: "brinson" },
  { label: "多因子模型", value: "multi-factor" },
];

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
  alphaSignificant: true,
});

const brinsonAttribution = ref([
  {
    category: "金融",
    allocationEffect: 0.0089,
    selectionEffect: 0.0156,
    interactionEffect: 0.0023,
    totalEffect: 0.0268,
    description: "金融行业整体超配，选股能力较强",
  },
  {
    category: "科技",
    allocationEffect: 0.0056,
    selectionEffect: 0.0089,
    interactionEffect: 0.0012,
    totalEffect: 0.0157,
    description: "科技行业配置适中，选股贡献显著",
  },
  {
    category: "消费",
    allocationEffect: -0.0023,
    selectionEffect: 0.0045,
    interactionEffect: 0.0009,
    totalEffect: 0.0031,
    description: "消费行业低配，但选股能力弥补了配置不足",
  },
  {
    category: "医药",
    allocationEffect: 0.0034,
    selectionEffect: -0.0012,
    interactionEffect: 0.0005,
    totalEffect: 0.0027,
    description: "医药行业超配，但选股表现一般",
  },
  {
    category: "其他",
    allocationEffect: -0.0033,
    selectionEffect: 0.0011,
    interactionEffect: -0.0005,
    totalEffect: -0.0027,
    description: "其他行业配置分散，整体贡献为负",
  },
]);

const factorAttribution = ref([
  {
    factor: "市值因子",
    exposure: 0.234,
    factorReturn: 0.0156,
    attribution: 0.0036,
    tStat: 2.34,
    significance: "显著",
  },
  {
    factor: "价值因子",
    exposure: 0.189,
    factorReturn: 0.0234,
    attribution: 0.0044,
    tStat: 3.12,
    significance: "显著",
  },
  {
    factor: "动量因子",
    exposure: 0.156,
    factorReturn: -0.0089,
    attribution: -0.0014,
    tStat: -1.45,
    significance: "不显著",
  },
  {
    factor: "质量因子",
    exposure: 0.278,
    factorReturn: 0.0189,
    attribution: 0.0052,
    tStat: 2.89,
    significance: "显著",
  },
  {
    factor: "波动率因子",
    exposure: -0.134,
    factorReturn: -0.0123,
    attribution: 0.0016,
    tStat: 1.78,
    significance: "显著",
  },
  {
    factor: "残差收益",
    exposure: 1.0,
    factorReturn: 0.0098,
    attribution: 0.0098,
    tStat: 1.23,
    significance: "不显著",
  },
]);

const getEffectClass = (effect: number) =>
  effect >= 0 ? "positive" : "negative";
const getExposureClass = (exposure: number) =>
  Math.abs(exposure) > 0.2
    ? "highlight"
    : exposure >= 0
      ? "positive"
      : "negative";
const getTStatClass = (tStat: number) => {
  const at = Math.abs(tStat);
  if (at >= 2.0) return "significant";
  if (at >= 1.5) return "moderate";
  return "insignificant";
};
const getSignificanceTag = (sig: string) =>
  sig === "显著" ? "success" : ("info" as const);
const formatPercent = (value: number) => `${(value * 100).toFixed(2)}%`;

const dateLabel = computed(() => {
  const dr = analysisConfig.dateRange;
  if (!dr) return "-";
  if (Array.isArray(dr) && dr.length === 2) {
    return `${new Date(dr[0]).toLocaleDateString()} - ${new Date(dr[1]).toLocaleDateString()}`;
  }
  return "-";
});

const brinsonColumns = computed(() => [
  { title: "类别", key: "category", width: 150 },
  {
    title: "配置效应",
    key: "allocationEffect",
    width: 120,
    render(row: any) {
      return h(
        "span",
        { class: getEffectClass(row.allocationEffect) },
        formatPercent(row.allocationEffect),
      );
    },
  },
  {
    title: "选股效应",
    key: "selectionEffect",
    width: 120,
    render(row: any) {
      return h(
        "span",
        { class: getEffectClass(row.selectionEffect) },
        formatPercent(row.selectionEffect),
      );
    },
  },
  {
    title: "交互效应",
    key: "interactionEffect",
    width: 120,
    render(row: any) {
      return h(
        "span",
        { class: getEffectClass(row.interactionEffect) },
        formatPercent(row.interactionEffect),
      );
    },
  },
  {
    title: "总效应",
    key: "totalEffect",
    width: 120,
    render(row: any) {
      return h(
        "span",
        { class: getEffectClass(row.totalEffect) },
        formatPercent(row.totalEffect),
      );
    },
  },
  { title: "说明", key: "description" },
]);

const factorColumns = computed(() => [
  { title: "因子", key: "factor", width: 150 },
  {
    title: "暴露度",
    key: "exposure",
    width: 120,
    render(row: any) {
      return h(
        "span",
        { class: getExposureClass(row.exposure) },
        row.exposure.toFixed(3),
      );
    },
  },
  {
    title: "因子收益",
    key: "factorReturn",
    width: 120,
    render(row: any) {
      return h(
        "span",
        { class: getEffectClass(row.factorReturn) },
        formatPercent(row.factorReturn),
      );
    },
  },
  {
    title: "归因贡献",
    key: "attribution",
    width: 120,
    render(row: any) {
      return h(
        "span",
        { class: getEffectClass(row.attribution) },
        formatPercent(row.attribution),
      );
    },
  },
  {
    title: "T统计量",
    key: "tStat",
    width: 100,
    render(row: any) {
      return h(
        "span",
        { class: getTStatClass(row.tStat) },
        row.tStat.toFixed(2),
      );
    },
  },
  {
    title: "显著性",
    key: "significance",
    width: 100,
    render(row: any) {
      return h(
        NTag,
        { type: getSignificanceTag(row.significance), size: "small" },
        { default: () => row.significance },
      );
    },
  },
]);

const runAttributionAnalysis = async () => {
  if (!analysisConfig.strategy) {
    message.warning("请选择策略");
    return;
  }
  loading.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    error.value = false;
    message.success("归因分析完成");
    initCharts();
  } catch (err) {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

let attributionChartInstance: any = null;
let industryChartInstance: any = null;
let factorExposureChartInstance: any = null;
let timeSeriesChartInstance: any = null;

const initCharts = () => {
  if (attributionChart.value) {
    attributionChartInstance = echarts.init(attributionChart.value);
    attributionChartInstance.setOption({
      tooltip: { trigger: "item", formatter: "{a} <br/>{b}: {c} ({d}%)" },
      legend: { orient: "vertical", right: 10, top: "center" },
      series: [
        {
          name: "超额收益分解",
          type: "pie",
          radius: ["40%", "70%"],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 10, borderColor: "#fff", borderWidth: 2 },
          label: { show: false, position: "center" },
          emphasis: { label: { show: true, fontSize: 18, fontWeight: "bold" } },
          labelLine: { show: false },
          data: [
            { value: 45.6, name: "选股效应", itemStyle: { color: "#5470c6" } },
            { value: 26.9, name: "配置效应", itemStyle: { color: "#91cc75" } },
            { value: 9.6, name: "交互效应", itemStyle: { color: "#fac858" } },
            { value: 17.9, name: "其他", itemStyle: { color: "#ee6666" } },
          ],
        },
      ],
    });
  }
  if (industryChart.value) {
    industryChartInstance = echarts.init(industryChart.value);
    industryChartInstance.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
      yAxis: {
        type: "category",
        data: ["金融", "科技", "消费", "医药", "工业", "能源", "其他"],
      },
      series: [
        {
          name: "配置贡献",
          type: "bar",
          data: [2.68, 1.57, 0.31, 0.27, -0.45, -0.23, -0.15],
          itemStyle: {
            color: (params: any) => (params.value >= 0 ? "#5470c6" : "#ee6666"),
          },
          label: { show: true, position: "right", formatter: "{c}%" },
        },
      ],
    });
  }
  if (factorExposureChart.value) {
    factorExposureChartInstance = echarts.init(factorExposureChart.value);
    factorExposureChartInstance.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      radar: {
        indicator: [
          { name: "市值", max: 0.3 },
          { name: "价值", max: 0.3 },
          { name: "动量", max: 0.3 },
          { name: "质量", max: 0.3 },
          { name: "波动率", max: 0.3 },
          { name: "成长", max: 0.3 },
        ],
      },
      series: [
        {
          name: "因子暴露",
          type: "radar",
          data: [
            {
              value: [0.234, 0.189, 0.156, 0.278, 0.134, 0.167],
              name: "策略暴露",
              areaStyle: { color: "rgba(84,112,198,0.3)" },
              lineStyle: { color: "#5470c6" },
            },
            {
              value: [0.156, 0.234, 0.123, 0.189, 0.167, 0.145],
              name: "基准暴露",
              areaStyle: { color: "rgba(145,204,117,0.3)" },
              lineStyle: { color: "#91cc75" },
            },
          ],
        },
      ],
    });
  }
  if (timeSeriesChart.value) {
    timeSeriesChartInstance = echarts.init(timeSeriesChart.value);
    timeSeriesChartInstance.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
      legend: { data: ["累计超额收益", "配置效应", "选股效应", "交互效应"] },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: { type: "category", data: ["Q1", "Q2", "Q3", "Q4"] },
      yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
      series: [
        {
          name: "累计超额收益",
          type: "line",
          data: [1.2, 2.8, 3.5, 4.6],
          itemStyle: { color: "#5470c6" },
          smooth: true,
        },
        {
          name: "配置效应",
          type: "bar",
          data: [0.8, 1.2, 1.0, 1.3],
          itemStyle: { color: "#91cc75" },
        },
        {
          name: "选股效应",
          type: "bar",
          data: [0.3, 1.4, 2.2, 2.9],
          itemStyle: { color: "#fac858" },
        },
        {
          name: "交互效应",
          type: "bar",
          data: [0.1, 0.2, 0.3, 0.4],
          itemStyle: { color: "#ee6666" },
        },
      ],
    });
  }
};

onMounted(() => {
  if (strategyList.value.length > 0)
    analysisConfig.strategy = strategyList.value[0].id;
  runAttributionAnalysis();
});
</script>

<style lang="scss" scoped>
.attribution-analysis {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header .page-title {
  margin: 0;
  color: var(--n-text-color-1);
}
.page-header .header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.attribution-overview {
  margin-bottom: 20px;
}
.attribution-card {
  height: 100%;
}
.chart-container {
  height: 300px;
}
.detailed-attribution {
  margin-bottom: 20px;
}
.summary-row {
  margin-bottom: 20px;
}
.positive {
  color: #67c23a;
  font-weight: bold;
}
.negative {
  color: #f56c6c;
  font-weight: bold;
}
.highlight {
  color: #e6a23c;
  font-weight: bold;
}
.significant {
  color: #67c23a;
  font-weight: bold;
}
.moderate {
  color: #e6a23c;
  font-weight: bold;
}
.insignificant {
  color: var(--n-text-color-3);
}
</style>
