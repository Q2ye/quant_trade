<!--
  IndexDetail.vue — 重设计版本
  方案1：页头 + 快速统计 + K线图 + 选项卡（基本信息 / 成分股）
  背景由 MainLayout 全局提供：bg-gradient-mesh + bg-noise
-->
<template>
  <div class="index-detail-page">
    <!-- ========== A. 页头栏 ========== -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            {{ indexInfo?.name || "--" }}
            <span class="index-code-tag">{{ code }}</span>
          </h1>
          <p v-if="indexInfo" class="page-description">
            <span class="index-price">{{
              formatPrice(indexInfo.close)
            }}</span>
            <span class="index-change" :class="changeClass">{{
              formatChange(indexInfo.change)
            }}</span>
            <span class="index-change-pct" :class="changeClass"
              >({{ formatPercent(indexInfo.pct_chg) }})</span
            >
            <span class="index-update">{{ updateTime }}</span>
            <n-tag
              :type="marketStatus === 'open' ? 'success' : 'default'"
              size="small"
              :bordered="false"
              class="index-status-tag"
            >
              {{ marketStatus === "open" ? "交易中" : "已收盘" }}
            </n-tag>
          </p>
        </div>
        <div class="header-actions">
          <n-button-group size="small">
            <n-button
              v-for="idx in coreIndices"
              :key="idx.value"
              :type="code === idx.value ? 'primary' : 'default'"
              @click="router.replace('/market/index/' + idx.value)"
              >{{ idx.label.slice(0, 4) }}</n-button
            >
          </n-button-group>
          <n-button
            class="action-btn"
            @click="refreshData"
            :loading="loading"
            quaternary
          >
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content scrollbar-hide">
      <!-- ========== Loading ========== -->
      <template v-if="loading">
        <div class="section">
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item v-for="i in 4" :key="i">
              <n-card><n-skeleton :text="true" :repeat="2" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
        <div class="section">
          <n-card>
            <template #header
              ><n-skeleton :text="true" width="120px"
            /></template>
            <n-skeleton style="height: 420px" width="100%" />
          </n-card>
        </div>
        <div class="section">
          <n-card><n-skeleton :text="true" :repeat="8" /></n-card>
        </div>
      </template>

      <!-- ========== Error ========== -->
      <n-result
        v-else-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <!-- ========== Data ========== -->
      <template v-else>
        <!-- B. 快速统计行 -->
        <div class="section">
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item
              v-for="(stat, idx) in quickStats"
              :key="stat.label"
              :class="tokens.motion.stagger"
              :style="{ animationDelay: `${idx * 0.06}s` }"
            >
              <n-card :class="tokens.motion.hover">
                <div class="stat-card-inner">
                  <div class="stat-icon-row">
                    <SmartIcon :name="stat.icon" class="stat-icon" />
                    <span class="stat-label">{{ stat.label }}</span>
                  </div>
                  <span class="stat-value" :class="stat.colorClass">{{
                    stat.value
                  }}</span>
                  <span v-if="stat.sub" class="stat-sub">{{ stat.sub }}</span>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>

        <!-- C. K线图 -->
        <div class="section">
          <n-card>
            <template #header>
              <div class="chart-header">
                <h3 class="chart-title">
                  <SmartIcon name="BarChart" class="title-icon" />K线图
                </h3>
                <n-button-group size="small">
                  <n-button
                    v-for="p in periods"
                    :key="p.value"
                    :type="selectedPeriod === p.value ? 'primary' : 'default'"
                    @click="selectedPeriod = p.value"
                  >
                    {{ p.label }}
                  </n-button>
                </n-button-group>
              </div>
            </template>
            <div class="chart-body">
              <LightweightKLine
                :key="`${code}-${selectedPeriod}`"
                :data="klineData"
                :ma-lines="[5, 10, 20]"
                :show-volume="true"
                :height="420"
                :loading="loading"
                :error="error"
                @retry="loadData"
              />
            </div>
          </n-card>
        </div>

        <!-- D. 选项卡 -->
        <div class="section">
          <n-card>
            <n-tabs v-model:value="activeTab" type="line" animated>
              <!-- D1. 基本信息 -->
              <n-tab-pane name="basic" tab="基本信息">
                <n-empty v-if="!indexInfo" description="暂无指数信息" />
                <n-descriptions
                  v-else
                  label-placement="left"
                  :column="2"
                  bordered
                  class="info-descriptions"
                >
                  <n-descriptions-item label="指数全称">
                    <span :title="indexInfo.fullname">{{
                      indexInfo.fullname || "--"
                    }}</span>
                  </n-descriptions-item>
                  <n-descriptions-item label="市场">
                    <n-tag :bordered="false" type="info" size="small">{{
                      indexInfo.market
                    }}</n-tag>
                  </n-descriptions-item>
                  <n-descriptions-item label="发布机构">{{
                    indexInfo.publisher || "--"
                  }}</n-descriptions-item>
                  <n-descriptions-item label="分类">{{
                    indexInfo.category || "--"
                  }}</n-descriptions-item>
                  <n-descriptions-item label="基日">{{
                    indexInfo.base_date || "--"
                  }}</n-descriptions-item>
                  <n-descriptions-item label="基点">{{
                    formatNumber(indexInfo.base_point)
                  }}</n-descriptions-item>
                  <n-descriptions-item label="成分股数量"
                    >{{
                      indexInfo.components_count ?? "--"
                    }}
                    只</n-descriptions-item
                  >
                  <n-descriptions-item label="上市日期">{{
                    indexInfo.list_date || "--"
                  }}</n-descriptions-item>
                  <n-descriptions-item label="市盈率 (PE)">
                    <span :class="getValueClass(indexInfo.pe)">{{
                      formatNumber(indexInfo.pe)
                    }}</span>
                  </n-descriptions-item>
                  <n-descriptions-item label="市净率 (PB)">
                    <span :class="getValueClass(indexInfo.pb)">{{
                      formatNumber(indexInfo.pb)
                    }}</span>
                  </n-descriptions-item>
                  <n-descriptions-item label="成交额">
                    {{
                      indexInfo.amount != null
                        ? formatAmount(indexInfo.amount)
                        : "--"
                    }}
                  </n-descriptions-item>
                  <n-descriptions-item label="成交量">
                    {{
                      indexInfo.vol != null
                        ? formatVolume(indexInfo.vol)
                        : "--"
                    }}
                  </n-descriptions-item>
                </n-descriptions>
              </n-tab-pane>

              <!-- D2. 成分股 -->
              <n-tab-pane name="components" :tab="componentsTabLabel">
                <div class="components-toolbar">
                  <n-input
                    v-model:value="componentSearch"
                    placeholder="搜索代码或名称..."
                    clearable
                    class="search-input"
                  >
                    <template #prefix><SmartIcon name="Search" /></template>
                  </n-input>
                </div>
                <n-empty
                  v-if="filteredComponents.length === 0"
                  description="暂无成分股数据"
                />
                <n-data-table
                  v-else
                  :columns="componentColumns"
                  :data="filteredComponents"
                  :virtual-scroll="true"
                  :max-height="420"
                  :row-props="componentRowProps"
                  :row-class-name="componentRowClass"
                  striped
                  size="small"
                />
              </n-tab-pane>

              <n-tab-pane name="valuation" tab="估值">
                <n-empty
                  v-if="!indexValuation.length"
                  description="暂无估值数据"
                  style="padding: 40px"
                />
                <v-chart
                  v-else
                  :option="valOption"
                  autoresize
                  style="height: 300px"
                />
              </n-tab-pane>

              <n-tab-pane name="weights" :tab="`权重股 (${weightsTotal})`">
                <n-empty
                  v-if="!indexWeights.length"
                  description="暂无权重数据"
                  style="padding: 40px"
                />
                <n-dataTable
                  v-else
                  :columns="weightColumns"
                  :data="indexWeights"
                  size="small"
                  :bordered="false"
                  max-height="400"
                  :remote="true"
                  :pagination="{
                    page: weightsPage,
                    pageSize: weightsPageSize,
                    itemCount: weightsTotal,
                    onChange: loadWeightsPage,
                  }"
                />
              </n-tab-pane>

              <n-tab-pane name="exposure" tab="行业暴露">
                <n-empty
                  v-if="!sectorExposure.length"
                  description="暂无行业暴露数据"
                  style="padding: 40px"
                />
                <v-chart
                  v-else
                  :option="sectorExposureOption"
                  autoresize
                  style="height: 380px"
                />
              </n-tab-pane>
            </n-tabs>
          </n-card>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NGrid,
  NGridItem,
  NSkeleton,
  NEmpty,
  NResult,
  NTabs,
  NTabPane,
  NDescriptions,
  NDescriptionsItem,
  NTag,
  NButtonGroup,
  NInput,
  NDataTable,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, DataTableRowKey } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import LightweightKLine from "@/components/charts/LightweightKLine.vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { PieChart } from "echarts/charts";
import { TooltipComponent, LegendComponent } from "echarts/components";
use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent]);
import { tokens } from "@/styles/design-tokens";
import marketApi from "@/api/market";

// 6 core indices for quick switching
const coreIndices = [
  { label: "上证指数", value: "000001.SH" },
  { label: "深证成指", value: "399001.SZ" },
  { label: "沪深300", value: "000300.SH" },
  { label: "中证500", value: "000905.SH" },
  { label: "创业板指", value: "399006.SZ" },
  { label: "科创50", value: "000688.SH" },
];

const route = useRoute();
const router = useRouter();
const message = useMessage();

const code = computed(
  () => (route.query.focus as string) || (route.params.code as string) || "",
);

// ---- 状态 ----
const loading = ref(true);
const error = ref(false);
const activeTab = ref("basic");
const selectedPeriod = ref("daily");
const componentSearch = ref("");

const periods = [
  { label: "日K", value: "daily" },
  { label: "周K", value: "weekly" },
  { label: "月K", value: "monthly" },
];

// ---- 指数详情数据（扩展接口，包含行情字段） ----
interface IndexDetailData {
  ts_code: string;
  name: string;
  fullname: string;
  market: string;
  publisher: string;
  category: string;
  base_date: string;
  base_point: number;
  list_date: string;
  close: number;
  open: number;
  high: number;
  low: number;
  pre_close: number;
  change: number;
  pct_chg: number;
  vol: number;
  amount: number;
  trade_date: string;
  pe: number;
  pb: number;
  total_mv: number;
  components_count: number;
}

interface ComponentStock {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  weight: number;
  market_cap: number;
}

const indexInfo = ref<IndexDetailData | null>(null);
const components = ref<ComponentStock[]>([]);
const indexWeights = ref<any[]>([]);
const weightsTotal = ref(0);
const weightsPage = ref(1);
const weightsPageSize = ref(50);
const indexValuation = ref<any[]>([]);
const history = ref<any[]>([]);
const sectorExposure = ref<any[]>([]);

const klineData = computed(() => {
  if (!history.value.length) return [];
  // 将后端返回的任意格式映射到 LightweightKLine 期望的 KLineDataItem
  const mapped = history.value.map((d: any) => ({
    trade_date: d.trade_date || d.date || "",
    open: d.open ?? null,
    high: d.high ?? null,
    low: d.low ?? null,
    close: d.close ?? null,
    vol: d.vol ?? d.volume ?? null,
  }));
  if (selectedPeriod.value === "daily") return mapped;
  const step = selectedPeriod.value === "weekly" ? 5 : 20;
  return mapped.filter((_: any, i: number) => i % step === 0);
});
const weightColumns = [
  { title: "代码", key: "ts_code", width: 100 },
  { title: "简称", key: "name", width: 100 },
  {
    title: "权重(%)",
    key: "weight",
    width: 80,
    render: (r: any) => r.weight?.toFixed(2) ?? "-",
  },
  {
    title: "最新价",
    key: "close",
    width: 80,
    render: (r: any) => r.close?.toFixed(2) ?? "-",
  },
  {
    title: "涨跌幅",
    key: "pct_chg",
    width: 80,
    render: (r: any) =>
      r.pct_chg != null
        ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%"
        : "-",
  },
];
const valOption = computed(() => {
  if (!indexValuation.value.length) return undefined;
  const items = [...indexValuation.value].reverse();
  const dates = items.map((d: any) => d.trade_date?.slice(5) ?? "");
  const peVals = items.map((d: any) => d.pe ?? 0);
  const pbVals = items.map((d: any) => d.pb ?? 0);
  const peSorted = [...peVals].sort((a, b) => a - b);
  const pbSorted = [...pbVals].sort((a, b) => a - b);
  const p25 = (arr: number[]) => arr[Math.floor(arr.length * 0.25)];
  const p50 = (arr: number[]) => arr[Math.floor(arr.length * 0.5)];
  const p75 = (arr: number[]) => arr[Math.floor(arr.length * 0.75)];
  return {
    grid: { top: 10, right: 50, bottom: 30, left: 60 },
    xAxis: { type: "category", data: dates, axisLabel: { fontSize: 9 } },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10 },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    },
    dataZoom: [{ type: "inside", start: 50, end: 100 }],
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, textStyle: { fontSize: 10 } },
    series: [
      {
        name: "PE",
        type: "line",
        data: peVals,
        smooth: true,
        lineStyle: { width: 2, color: "#ef5350" },
        symbol: "none",
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed", color: "#ef5350", width: 1 },
          data: [
            { yAxis: p25(peSorted), label: { formatter: "P25", fontSize: 9 } },
            { yAxis: p50(peSorted), label: { formatter: "P50", fontSize: 9 } },
            { yAxis: p75(peSorted), label: { formatter: "P75", fontSize: 9 } },
          ],
        },
      },
      {
        name: "PB",
        type: "line",
        data: pbVals,
        smooth: true,
        lineStyle: { width: 2, color: "#2196f3" },
        symbol: "none",
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed", color: "#2196f3", width: 1 },
          data: [
            { yAxis: p25(pbSorted), label: { formatter: "P25", fontSize: 9 } },
            { yAxis: p50(pbSorted), label: { formatter: "P50", fontSize: 9 } },
            { yAxis: p75(pbSorted), label: { formatter: "P75", fontSize: 9 } },
          ],
        },
      },
    ],
  };
});

const sectorExposureOption = computed(() => {
  if (!sectorExposure.value.length) return undefined;
  const data = sectorExposure.value.map((d: any) => ({
    name: d.name || d.sector_name || d.industry || "",
    value: Math.abs(d.weight_pct ?? d.weight ?? d.exposure ?? 0),
  }));
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c}% ({d}%)" },
    legend: {
      bottom: 0,
      textStyle: { fontSize: 10, color: "var(--n-text-color-2)" },
      type: "scroll",
    },
    series: [
      {
        type: "pie",
        radius: ["35%", "65%"],
        center: ["50%", "45%"],
        data,
        label: { fontSize: 10, formatter: "{b}\n{d}%" },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" },
        },
        itemStyle: {
          borderRadius: 2,
          borderColor: "rgba(0,0,0,0.3)",
          borderWidth: 1,
        },
      },
    ],
  };
});

// ---- 计算属性 ----
const updateTime = computed(() => {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
});

const marketStatus = computed<"open" | "closed">(() => {
  const h = new Date().getHours();
  const m = new Date().getMinutes();
  const t = h * 60 + m;
  return t >= 570 && t <= 900 ? "open" : "closed";
});

const changeClass = computed(() => {
  if (!indexInfo.value) return "";
  const v = indexInfo.value.change;
  if (v > 0) return "text-up";
  if (v < 0) return "text-down";
  return "";
});

const quickStats = computed(() => {
  const d = indexInfo.value;
  if (!d) return [];
  return [
    {
      icon: "Money",
      label: "成交额",
      value: d.amount != null ? (d.amount / 1e8).toFixed(0) + "亿" : "--",
      sub: d.vol != null ? "成交量 " + (d.vol / 1e8).toFixed(1) + "亿手" : "",
      colorClass: "",
    },
    {
      icon: "TrendingUp",
      label: "市盈率 PE",
      value: d.pe != null ? d.pe.toFixed(2) : "--",
      sub: d.pe != null ? (d.pe < 15 ? "较低估" : d.pe < 25 ? "合理" : d.pe < 40 ? "偏高" : "高估") : "",
      colorClass: d.pe != null ? (d.pe < 15 ? "text-down" : d.pe > 40 ? "text-up" : "") : "",
    },
    {
      icon: "BarChart",
      label: "市净率 PB",
      value: d.pb != null ? d.pb.toFixed(2) : "--",
      sub: d.pb != null ? (d.pb < 1.5 ? "较低估" : d.pb < 3 ? "合理" : d.pb < 5 ? "偏高" : "高估") : "",
      colorClass: d.pb != null ? (d.pb < 1.5 ? "text-down" : d.pb > 5 ? "text-up" : "") : "",
    },
    {
      icon: "Home",
      label: "总市值",
      value: d.total_mv != null ? (d.total_mv / 1e12).toFixed(1) + "万亿" : "--",
      sub: (d.components_count != null ? d.components_count + " 只成分股" : ""),
      colorClass: "",
    },
  ];
});

const filteredComponents = computed(() => {
  const kw = componentSearch.value.trim().toLowerCase();
  if (!kw) return components.value;
  return components.value.filter(
    (c) =>
      c.code.toLowerCase().includes(kw) || c.name.toLowerCase().includes(kw),
  );
});

const componentsTabLabel = computed(
  () => `成分股 (${components.value.length})`,
);

// ---- 表格列定义 ----
const componentColumns: DataTableColumns<ComponentStock> = [
  { title: "代码", key: "code", width: 100, ellipsis: true },
  { title: "名称", key: "name", width: 120, ellipsis: true },
  {
    title: "最新价",
    key: "price",
    width: 100,
    align: "right",
    render(row) {
      return row.price != null ? row.price.toFixed(2) : "--";
    },
  },
  {
    title: "涨跌幅",
    key: "change_pct",
    width: 100,
    align: "right",
    sortOrder: false,
    sorter: (a: ComponentStock, b: ComponentStock) =>
      (a.change_pct || 0) - (b.change_pct || 0),
    render(row) {
      const v = row.change_pct;
      if (v == null) return "--";
      const cls = v > 0 ? "text-up" : v < 0 ? "text-down" : "";
      return h("span", { class: cls }, (v > 0 ? "+" : "") + v.toFixed(2) + "%");
    },
  },
  {
    title: "权重",
    key: "weight",
    width: 100,
    align: "right",
    render(row) {
      return row.weight != null ? row.weight.toFixed(2) + "%" : "--";
    },
  },
  {
    title: "总市值",
    key: "market_cap",
    width: 130,
    align: "right",
    render(row) {
      return row.market_cap != null ? formatAmount(row.market_cap) : "--";
    },
  },
];

// ---- 行点击 ----
function componentRowProps(row: ComponentStock) {
  return { style: "cursor: pointer;" };
}
function componentRowClass(row: ComponentStock) {
  return "component-row";
}

// ---- 方法 ----
function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function formatPrice(v: number | null | undefined) {
  if (v == null) return "--";
  return v.toFixed(2);
}

function formatChange(v: number | null | undefined) {
  if (v == null) return "--";
  return (v > 0 ? "+" : "") + v.toFixed(2);
}

function formatPercent(v: number | null | undefined) {
  if (v == null) return "--";
  return (v > 0 ? "+" : "") + v.toFixed(2) + "%";
}

function formatNumber(v: number | null | undefined) {
  if (v == null) return "--";
  return v.toFixed(2);
}

function formatAmount(v: number) {
  const abs = Math.abs(v);
  if (abs >= 1e8) return (abs / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return (abs / 1e4).toFixed(2) + "万";
  return abs.toFixed(2);
}

function formatVolume(v: number) {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿手";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万手";
  return v.toFixed(0) + "手";
}

function getCompareClass(value: number, base: number) {
  if (value > base) return "text-up";
  if (value < base) return "text-down";
  return "";
}

function getValueClass(v: number | null | undefined) {
  if (v == null) return "";
  return v > 0 ? "text-up" : "text-down";
}

async function loadData() {
  loading.value = true;
  error.value = false;

  try {
    const idxCode = code.value || "000001.SH";

    const [detail, hist, val, wts, sec] = await Promise.all([
      marketApi.getIndexDetail(idxCode).catch(() => null),
      marketApi.getIndexHistory(idxCode, 2000).catch(() => []),
      marketApi.getIndexValuation(idxCode, 2000).catch(() => []),
      marketApi.getIndexWeights(idxCode, 0, weightsPageSize.value).catch(() => ({ total: 0, items: [] })),
      marketApi.getIndexSectorExposure(idxCode).catch(() => []),
    ]);

    if (!detail) {
      error.value = true;
      loading.value = false;
      return;
    }

    indexInfo.value = { ...detail } as unknown as IndexDetailData;
    history.value = hist || [];
    indexValuation.value = val || [];
    indexWeights.value = wts?.items || [];
    weightsTotal.value = wts?.total || 0;
    weightsPage.value = 1;
    sectorExposure.value = sec || [];
    components.value = (wts?.items || []).map((w: any) => ({
      code: w.ts_code || "",
      name: w.name || w.ts_code || "",
      price: w.close ?? 0,
      change_pct: w.pct_chg ?? 0,
      weight: w.weight ?? 0,
      market_cap: w.total_mv ?? 0,
    }));
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

async function loadWeightsPage(p: number) {
  try {
    const result = await marketApi.getIndexWeights(
      code.value,
      (p - 1) * weightsPageSize.value,
      weightsPageSize.value,
    );
    indexWeights.value = result?.items || [];
    weightsTotal.value = result?.total || 0;
    weightsPage.value = p;
  } catch { /* ignore */ }
}

function refreshData() {
  loadData();
  message.success("数据已刷新");
}

// 监听代码变化（同一页面切换指数时重新加载）
watch(code, () => {
  if (code.value) {
    activeTab.value = "basic";
    componentSearch.value = "";
    loadData();
  }
});

onMounted(() => {
  loadData();
});
</script>

<style lang="scss" scoped>
/* ============================================================
   IndexDetail — 指数详情页
   - 全局背景由 MainLayout 提供，本页 transparent
   - 所有卡片半透明，透出 3D 粒子背景
   - CSS 变量驱动颜色
   ============================================================ */

.index-detail-page {
  height: 100%;
  overflow-y: auto;
  background: transparent;
  animation: fadeIn 0.3s ease-out;
}

/* ---- 半透明卡片 ---- */
:deep(.n-card) {
  --n-color: transparent !important;
  background: var(--color-bg-card, rgba(12, 18, 32, 0.72)) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);

  > .n-card-header,
  > .n-card__content,
  > .n-card-footer {
    background: transparent !important;
  }

  > .n-card__content {
    overflow: hidden;
  }
}

/* ---- 页头内价格展示 ---- */
.index-code-tag {
  font-size: 12px;
  font-weight: 500;
  color: var(--n-text-color-3);
  background: var(--color-bg-secondary, rgba(255, 255, 255, 0.06));
  padding: 2px 8px;
  border-radius: 8px;
  font-family: "SF Mono", "Fira Code", monospace;
  margin-left: 8px;
  vertical-align: middle;
}

.index-price {
  font-size: 15px;
  font-weight: 700;
  color: var(--n-text-color-1);
  font-variant-numeric: tabular-nums;
}

.index-change {
  font-weight: 600;
  margin-left: 6px;
}

.index-change-pct {
  font-weight: 500;
  margin-left: 2px;
}

.index-update {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-left: 10px;
}

.index-status-tag {
  margin-left: 6px;
  vertical-align: middle;
}

/* ============================================================
   内容区
   ============================================================ */
.main-content {
  padding: 0;
}

.section {
  padding: 8px 24px;
  margin-bottom: 8px;

  &:first-child {
    padding-top: 20px;
  }
  &:last-child {
    padding-bottom: 24px;
  }
}

/* ============================================================
   B. 快速统计
   ============================================================ */
.stat-card-inner {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;

  .stat-icon-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .stat-icon {
    font-size: 16px;
    color: var(--color-primary, #448AFF);
    flex-shrink: 0;
  }
  .stat-label {
    font-size: 12px;
    color: var(--n-text-color-3);
    font-weight: 500;
  }
  .stat-value {
    font-size: 22px;
    font-weight: 700;
    color: var(--n-text-color-1);
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }
  .stat-sub {
    font-size: 11px;
    color: var(--n-text-color-3);
    line-height: 1.3;
  }
}

/* ============================================================
   C. K线图
   ============================================================ */
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.chart-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0;

  .title-icon {
    font-size: 16px;
    color: var(--color-primary, #448aff);
  }
}

.chart-body {
  min-height: 420px;
}

/* ============================================================
   D. 选项卡
   ============================================================ */
.info-descriptions {
  margin-top: 4px;
}

/* ---- 成分股工具栏 ---- */
.components-toolbar {
  margin-bottom: 12px;
}

.search-input {
  max-width: 300px;
}

/* ---- 成分股表格 ---- */
:deep(.component-row) {
  cursor: pointer;

  &:hover {
    background: var(--color-bg-hover, rgba(68, 138, 255, 0.05)) !important;
  }
}

/* ============================================================
   状态色工具类
   ============================================================ */
.text-up {
  color: var(--color-stock-up, #ff5252);
  font-weight: 500;
}

.text-down {
  color: var(--color-stock-down, #00e676);
  font-weight: 500;
}

/* ---- 响应式 ---- */
@media (max-width: 1024px) {
  .page-header .header-content {
    flex-wrap: wrap;
  }
  .index-price {
    font-size: 14px;
  }
}

@media (max-width: 768px) {
  .section {
    padding-left: 12px;
    padding-right: 12px;
  }

  .chart-body {
    min-height: 300px;
  }

  .search-input {
    max-width: 100%;
  }
}

/* ---- 入场动画 ---- */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
