<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NCard,
  NDataTable,
  NSkeleton,
  NEmpty,
  NResult,
  NButton,
  NInput,
  NSpace,
  NGrid,
  NGridItem,
  NCheckboxGroup,
  NCheckbox,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import { tokens } from "@/styles/design-tokens";
import SmartIcon from "@/components/common/SmartIcon.vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { RadarChart } from "echarts/charts";
import {
  RadarComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
use([
  CanvasRenderer,
  RadarChart,
  RadarComponent,
  TooltipComponent,
  LegendComponent,
]);

const route = useRoute();
const router = useRouter();
const message = useMessage();
const loading = ref(false);
const error = ref(false);
const data = ref<any[]>([]);
const codeInput = ref("");

// radar metric selection
const radarKeys = [
  { key: "roe", label: "ROE", max: 40 },
  { key: "roa", label: "ROA", max: 20 },
  { key: "grossprofit_margin", label: "毛利率", max: 80 },
  { key: "netprofit_margin", label: "净利率", max: 50 },
  { key: "debt_to_assets", label: "负债率", max: 100, invert: true },
  { key: "eps", label: "EPS", max: 10 },
  { key: "current_ratio", label: "流动比率", max: 5 },
  { key: "quick_ratio", label: "速动比率", max: 3 },
];
const selectedRadarKeys = ref([
  "roe",
  "roa",
  "grossprofit_margin",
  "netprofit_margin",
  "debt_to_assets",
]);

const radarPalette = ["#448aff", "#ef5350", "#ff9800", "#26a69a", "#7e57c2", "#e91e63"];

const radarOption = computed(() => {
  if (!data.value.length || !selectedRadarKeys.value.length) return null;
  const selectedMetrics = radarKeys.filter((k) =>
    selectedRadarKeys.value.includes(k.key),
  );
  // 每指标自适应上限（观测最大值×1.2，下限 1），保证多边形撑开、对比清晰
  const indicator = selectedMetrics.map((k) => {
    const vals = data.value
      .map((r: any) => (r[k.key] == null ? 0 : Math.abs(r[k.key])))
      .filter((v) => !isNaN(v));
    const obsMax = vals.length ? Math.max(...vals) : 0;
    let max = Math.max(1, obsMax * 1.2);
    max = max >= 10 ? Math.ceil(max / 5) * 5 : Math.round(max * 10) / 10;
    return { name: k.label, max };
  });
  const seriesData = data.value.map((row: any, idx: number) => {
    const color = radarPalette[idx % radarPalette.length];
    const vals = selectedMetrics.map((k) => {
      const cap = indicator[selectedMetrics.indexOf(k)].max;
      const raw = row[k.key] == null ? 0 : Math.abs(row[k.key]);
      if (k.invert) return Math.max(0, Math.min(cap, cap - raw)); // 负债率越低越好
      return Math.min(cap, raw);
    });
    return {
      value: vals,
      name: row.name || row.ts_code,
      lineStyle: { color, width: 2 },
      areaStyle: { color: color + "2e" },
      itemStyle: { color },
      symbol: "circle",
      symbolSize: 5,
      emphasis: { lineStyle: { width: 3 }, areaStyle: { color: color + "44" } },
    };
  });
  // 原始值映射（tooltip 展示真实数值而非归一化值）
  const rawBySeries: Record<string, any> = {};
  data.value.forEach((row: any) => {
    rawBySeries[row.name || row.ts_code] = row;
  });
  return {
    tooltip: {
      trigger: "item",
      formatter: (p: any) => {
        const raw = rawBySeries[p.name] || {};
        const lines = ["<b>" + p.name + "</b>"];
        selectedMetrics.forEach((k) => {
          const v = raw[k.key];
          const label = k.invert ? k.label + "（越低越好）" : k.label;
          lines.push(
            `${label}: ${v == null ? "--" : Number(v).toFixed(2)}`,
          );
        });
        return lines.join("<br/>");
      },
    },
    legend: {
      top: 0,
      right: 8,
      data: seriesData.map((d: any) => d.name),
      textStyle: { fontSize: 11 },
      itemWidth: 14,
      itemHeight: 8,
    },
    radar: {
      indicator,
      center: ["50%", "57%"],
      radius: "62%",
      splitNumber: 4,
      axisName: { color: "#94a3b8", fontSize: 11 },
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } },
      splitArea: {
        areaStyle: { color: ["rgba(255,255,255,0.02)", "rgba(255,255,255,0.05)"] },
      },
    },
    series: [{ type: "radar", data: seriesData }],
  };
});

// conditional formatting: find min/max per column
const numericKeys = [
  "roe",
  "roa",
  "grossprofit_margin",
  "netprofit_margin",
  "debt_to_assets",
  "eps",
  "current_ratio",
  "quick_ratio",
];
const colExtremes = computed(() => {
  const extremes: Record<string, { min: number; max: number }> = {};
  numericKeys.forEach((k) => {
    const vals = data.value
      .map((r: any) => r[k] as number)
      .filter((v) => v != null);
    if (vals.length)
      extremes[k] = { min: Math.min(...vals), max: Math.max(...vals) };
  });
  return extremes;
});

function conditionalCell(k: string, r: any) {
  const v = r[k];
  if (v == null) return "-";
  const fmt = [
    "roe",
    "roa",
    "grossprofit_margin",
    "netprofit_margin",
    "debt_to_assets",
  ].includes(k)
    ? v.toFixed(1) + "%"
    : v.toFixed(2);
  const extreme = colExtremes.value[k];
  if (!extreme || extreme.max === extreme.min) return fmt;
  const isBest = k === "debt_to_assets" ? v === extreme.min : v === extreme.max;
  const isWorst =
    k === "debt_to_assets" ? v === extreme.max : v === extreme.min;
  return h(
    "span",
    {
      style: {
        color: isBest ? "#26a69a" : isWorst ? "#ef5350" : "",
        fontWeight: isBest || isWorst ? "600" : "400",
        background: isBest
          ? "rgba(38,166,154,0.1)"
          : isWorst
            ? "rgba(239,83,80,0.1)"
            : "",
        padding: "0 4px",
        borderRadius: "2px",
      },
    },
    r[k + "_pct"] != null ? fmt + " (" + r[k + "_pct"] + "分位)" : fmt,
  );
}

const columns: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 100, fixed: "left" },
  { title: "简称", key: "name", width: 90, fixed: "left" },
  { title: "报告期", key: "end_date", width: 100 },
  {
    title: "ROE",
    key: "roe",
    width: 120,
    render: (r) => conditionalCell("roe", r),
  },
  {
    title: "ROA",
    key: "roa",
    width: 110,
    render: (r) => conditionalCell("roa", r),
  },
  {
    title: "毛利率",
    key: "grossprofit_margin",
    width: 120,
    render: (r) => conditionalCell("grossprofit_margin", r),
  },
  {
    title: "净利率",
    key: "netprofit_margin",
    width: 120,
    render: (r) => conditionalCell("netprofit_margin", r),
  },
  {
    title: "负债率",
    key: "debt_to_assets",
    width: 120,
    render: (r) => conditionalCell("debt_to_assets", r),
  },
  {
    title: "EPS",
    key: "eps",
    width: 80,
    render: (r) => conditionalCell("eps", r),
  },
  {
    title: "流动比率",
    key: "current_ratio",
    width: 85,
    render: (r) => conditionalCell("current_ratio", r),
  },
  {
    title: "速动比率",
    key: "quick_ratio",
    width: 85,
    render: (r) => conditionalCell("quick_ratio", r),
  },
];

async function search() {
  const codes = codeInput.value
    .split(/[,; ]+/)
    .filter(Boolean)
    .map((c) => c.trim().toUpperCase());
  if (!codes.length) {
    message.warning("请输入股票代码");
    return;
  }
  loading.value = true;
  error.value = false;
  try {
    data.value = await marketAPI.getFinancialCompare({ codes });
  } catch {
    error.value = true;
    message.error("查询失败");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  const qCodes = route.query.codes as string;
  if (qCodes) {
    codeInput.value = qCodes;
  } else {
    codeInput.value = "000001.SZ, 600036.SH, 600519.SH, 000858.SZ, 601318.SH";
  }
  search();
});
</script>

<template>
  <div class="financial-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">财务对比</h1>
          <p class="page-description">多只股票财务指标横向对比</p>
        </div>
        <div class="header-actions">
          <n-button
            size="tiny"
            type="primary"
            ghost
            @click="router.push('/strategies/create?template=fundamental')"
            >创建基本面因子策略</n-button
          >
          <n-button
            size="tiny"
            quaternary
            @click="router.push('/market/screener')"
            >添加更多 →</n-button
          ><n-button class="action-btn" @click="() => $router.back()" quaternary
            ><template #icon><SmartIcon name="ArrowLeft" /></template
          ></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-space style="margin-bottom: 16px">
        <n-input
          v-model:value="codeInput"
          placeholder="输入代码，逗号/空格分隔"
          style="width: 400px"
          clearable
          @keyup.enter="search"
        />
        <n-button type="primary" @click="search">对比</n-button>
      </n-space>

      <n-skeleton v-if="loading" :text="true" :repeat="6" />
      <n-result v-else-if="error" status="500"
        ><template #footer
          ><n-button @click="search">重试</n-button></template
        ></n-result
      >
      <n-empty v-else-if="!data.length" description="无数据" />

      <template v-else>
        <!-- 雷达图 -->
        <n-card
          :class="tokens.surface.card"
          size="small"
          style="margin-bottom: 16px"
          title="多维度对比雷达图"
        >
          <template #header-extra>
            <n-checkbox-group v-model:value="selectedRadarKeys" size="small">
              <n-checkbox
                v-for="k in radarKeys"
                :key="k.key"
                :value="k.key"
                :label="k.label"
                style="margin-right: 8px"
              />
            </n-checkbox-group>
          </template>
          <VChart
            v-if="radarOption"
            :option="radarOption"
            autoresize
            style="height: 350px"
          />
          <n-skeleton v-else :text="true" height="350px" />
        </n-card>

        <n-card :class="tokens.surface.card">
          <n-dataTable
            :columns="columns"
            :data="data"
            size="small"
            :bordered="true"
            max-height="calc(100vh - 280px)"
            :row-props="
              (row: any) => ({
                style: 'cursor:pointer',
                onClick: () => router.push('/market/stock/' + row.ts_code),
              })
            "
          />
        </n-card>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.financial-page {
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}
</style>
