<!-- ETFMarket.vue — ETF Hub（列表 + 内联展开详情 + K线图 + 远程分页）-->
<script setup lang="ts">
import { computed, h, onMounted, onBeforeUnmount, ref, watch, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NCard,
  NButton,
  NDataTable,
  NSelect,
  NInput,
  NSkeleton,
  NEmpty,
  NResult,
  NTag,
  NDescriptions,
  NDescriptionsItem,
  NSpace,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import SmartIcon from "@/components/common/SmartIcon.vue";
import BasketSelectorDialog from "@/components/basket/BasketSelectorDialog.vue";
import LightweightKLine from "@/components/charts/LightweightKLine.vue";
import { tokens } from "@/styles/design-tokens";
import {
  createChart,
  ColorType,
  AreaSeries,
  type IChartApi,
  type ISeriesApi,
  type AreaData,
  type Time,
} from "lightweight-charts";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const loading = ref(true);
const error = ref(false);
const etfList = ref<any[]>([]);
const total = ref(0);
const filterType = ref<string | null>(null);
const filterSearch = ref("");
const filterStatus = ref<string>("L");
const expandedCode = ref<string | null>(null);
const expandedData = ref<any>(null);
const expandedLoading = ref(false);
const basketDialogShow = ref(false);
const basketStock = ref<{ symbol: string; name: string }>({ symbol: "", name: "" });
const page = ref(1);
const pageSize = ref(10);

// K-line data
const klineData = ref<any[]>([]);
const klineLoading = ref(false);

const typeOptions = [
  { label: "全部", value: null },
  { label: "宽基", value: "宽基" },
  { label: "行业", value: "行业" },
  { label: "主题", value: "主题" },
  { label: "跨境", value: "跨境" },
  { label: "债券", value: "债券" },
  { label: "货币", value: "货币" },
];

const statusOptions = [
  { label: "已上市", value: "L" },
  { label: "全部", value: "" },
  { label: "待上市", value: "P" },
  { label: "已退市", value: "D" },
];

const columns: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 110 },
  { title: "简称", key: "name", width: 120, ellipsis: { tooltip: true } },
  {
    title: "类型",
    key: "fund_type",
    width: 70,
    render: (r: any) =>
      r.fund_type
        ? h(NTag, { size: "tiny", bordered: false }, { default: () => r.fund_type })
        : "-",
  },
  {
    title: "最新价",
    key: "latest_price",
    width: 80,
    render: (r: any) => (r.latest_price != null ? r.latest_price.toFixed(3) : "-"),
  },
  {
    title: "涨跌幅",
    key: "latest_pct_chg",
    width: 80,
    render: (r: any) =>
      h(
        "span",
        { style: { color: (r.latest_pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } },
        r.latest_pct_chg != null
          ? (r.latest_pct_chg > 0 ? "+" : "") + r.latest_pct_chg.toFixed(2) + "%"
          : "-",
      ),
  },
  { title: "管理人", key: "manager", width: 90, ellipsis: { tooltip: true }, render: (r: any) => r.manager || "-" },
];

// shares chart — lightweight-charts area chart
const sharesChartContainer = ref<HTMLDivElement>();
let sharesChart: IChartApi | null = null;
let sharesSeries: ISeriesApi<"Area", Time> | null = null;

function toEpoch(d: string): Time {
  return (Math.floor(new Date((d?.slice(0, 10) || d) + "T00:00:00Z").getTime() / 1000)) as Time;
}

function buildSharesChart() {
  const el = sharesChartContainer.value;
  if (!el || el.clientWidth <= 0) return;
  if (sharesChart) { sharesChart.remove(); sharesChart = null; sharesSeries = null; }
  const w = el.clientWidth;

  sharesChart = createChart(el, {
    layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#a0a0a0", attributionLogo: false },
    grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
    rightPriceScale: { autoScale: true, scaleMargins: { top: 0.1, bottom: 0.1 } },
    timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: false },
    handleScroll: { vertTouchDrag: false },
    width: w,
    height: 220,
  });
  // 移除左下角 logo
  el.querySelector('a')?.remove();

  sharesSeries = sharesChart.addSeries(AreaSeries, {
    lineColor: "#4caf50",
    topColor: "rgba(76,175,80,0.2)",
    bottomColor: "rgba(76,175,80,0.01)",
    lineWidth: 2,
    priceFormat: { type: "volume" },
  });
}

function updateSharesChart(retries = 0) {
  const shares = expandedData.value?.shares;
  if (!shares?.length) return;
  if (!sharesChart || !sharesSeries) {
    buildSharesChart();
    // DOM 可能尚未就绪，重试一次
    if ((!sharesChart || !sharesSeries) && retries < 3) {
      setTimeout(() => updateSharesChart(retries + 1), 100);
      return;
    }
  }
  if (!sharesChart || !sharesSeries) return;

  const items = [...shares].reverse().slice(-120);
  const data: AreaData[] = items.map((d: any) => ({
    time: toEpoch(d.trade_date),
    value: (d.fund_size ?? 0) / 1e8,
  }));
  sharesSeries.setData(data);
  sharesChart.timeScale().fitContent();
}

function destroySharesChart() {
  if (sharesChart) { sharesChart.remove(); sharesChart = null; sharesSeries = null; }
}

watch(() => expandedData.value?.shares, async () => {
  await nextTick();
  if (expandedData.value?.shares?.length) {
    updateSharesChart();
  } else {
    destroySharesChart();
  }
});

// 展开新ETF时强制重建（reset chart for new ETF）
watch(() => expandedCode.value, (code) => {
  if (!code) destroySharesChart();
});

onBeforeUnmount(() => destroySharesChart());

async function toggleExpand(code: string) {
  if (expandedCode.value === code) { expandedCode.value = null; return; }
  expandedCode.value = code;
  expandedLoading.value = true;
  klineLoading.value = true;
  try {
    const [shares, benchmark, kline] = await Promise.all([
      marketAPI.getEtfShares(code, 120).catch(() => []),
      marketAPI.getEtfBenchmark(code).catch(() => null),
      marketAPI.getEtfHistory(code, 1000).catch(() => []),
    ]);
    const etf = etfList.value.find((e) => e.ts_code === code) || {};
    expandedData.value = { ...etf, shares, benchmark };
    // 统一日期格式为 YYYY-MM-DD（兼容后端 YYYYMMDD 和 ISO 两种输出）
    klineData.value = (kline || []).map((d: any) => ({
      ...d,
      trade_date: d.trade_date ? d.trade_date.replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3') : '',
    }));
  } catch {
    expandedData.value = { shares: [], benchmark: null };
    klineData.value = [];
  } finally {
    expandedLoading.value = false;
    klineLoading.value = false;
  }
}

async function load(p?: number) {
  loading.value = true;
  error.value = false;
  const pg = p || 1;
  try {
    const result = await marketAPI.getETFs({
      page: pg,
      limit: pageSize.value,
      type: filterType.value,
      search: filterSearch.value || undefined,
      status: filterStatus.value || undefined,
    });
    etfList.value = result?.etfs || result || [];
    total.value = result?.total || 0;
    page.value = pg;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
  // auto-expand from query param
  const focus = route.query.focus as string;
  if (focus) {
    const found = etfList.value.find((e) => e.ts_code === focus);
    if (found) toggleExpand(focus);
  }
}

function onFilterChange() {
  load(1);
}

function goBack() {
  if (window.history.length > 1) router.back();
  else router.push("/market/dashboard");
}
onMounted(() => load());
</script>

<template>
  <div class="etf-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">ETF 市场</h1>
          <p class="page-description">全市场 ETF 列表，点击行展开详情</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="goBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-skeleton v-if="loading" :text="true" :repeat="6" />
      <n-result v-else-if="error" status="500" title="加载失败">
        <template #footer><n-button @click="load()">重试</n-button></template>
      </n-result>

      <template v-else>
        <!-- Filter bar -->
        <n-space style="margin-bottom: 16px" align="center">
          <n-select
            v-model:value="filterStatus" :options="statusOptions" placeholder="状态"
            size="small" style="width: 100px" @update:value="onFilterChange"
          />
          <n-select
            v-model:value="filterType" :options="typeOptions" placeholder="类型"
            clearable size="small" style="width: 110px" @update:value="onFilterChange"
          />
          <n-input
            v-model:value="filterSearch" placeholder="搜索代码或名称"
            clearable size="small" style="width: 240px" @keyup.enter="onFilterChange"
          />
          <n-button size="small" @click="onFilterChange" secondary>搜索</n-button>
          <span style="flex: 1" />
          <span style="font-size: 12px; color: var(--n-text-color-3)">
            共 {{ total }} 只 ETF
          </span>
        </n-space>

        <!-- ETF data table -->
        <n-card :class="tokens.surface.card" size="small">
          <n-empty v-if="!etfList.length" description="暂无 ETF 数据" style="padding: 40px">
            <template #extra>
              <span style="font-size:12px;color:var(--n-text-color-3)">
                请先在「数据同步」中同步 ETF 基础信息（etf_basic）和 ETF 日线行情（etf_daily）
              </span>
            </template>
          </n-empty>
          <n-dataTable
            v-else
            :columns="columns"
            :data="etfList"
            :remote="true"
            :pagination="{
              page: page,
              pageSize: pageSize,
              itemCount: total,
              onChange: (p: number) => load(p),
              onUpdatePageSize: (s: number) => { pageSize = s; load(1); },
            }"
            :row-key="(r: any) => r.ts_code"
            :row-props="(r: any) => ({ style: 'cursor:pointer', onClick: () => toggleExpand(r.ts_code) })"
            size="small" :bordered="false" max-height="calc(100vh - 280px)" striped
          />
        </n-card>

        <!-- Expanded detail -->
        <n-card v-if="expandedCode" :class="tokens.surface.card" size="small" style="margin-top: 12px">
          <n-skeleton v-if="expandedLoading" :text="true" :repeat="3" />
          <template v-else>
            <!-- K-line chart -->
            <div style="margin-bottom: 16px">
              <div style="font-size: 12px; color: var(--n-text-color-3); margin-bottom: 4px">{{ expandedCode }} 日K线图</div>
              <LightweightKLine
                v-if="klineData.length"
                :data="klineData"
                :ma-lines="[5, 10, 20]"
                :show-volume="true"
                :height="320"
                :loading="klineLoading"
                :error="false"
              />
              <n-empty v-else-if="!klineLoading" description="暂无K线数据" style="padding: 20px" />
              <n-skeleton v-else :text="true" :repeat="3" />
            </div>

            <n-grid :x-gap="16" :cols="2">
              <n-grid-item>
                <div style="font-size: 12px; color: var(--n-text-color-3); margin-bottom: 4px">份额趋势 (120日)</div>
                <div v-if="expandedData?.shares?.length" ref="sharesChartContainer" style="width:100%;height:220px;zoom:1.25" />
                <n-empty v-else description="暂无份额数据" style="padding: 20px" />
              </n-grid-item>
              <n-grid-item>
                <n-descriptions label-placement="left" :column="1" size="small">
                  <n-descriptions-item label="资产类型">{{ expandedData?.asset_type || "-" }}</n-descriptions-item>
                  <n-descriptions-item label="管理人">{{ expandedData?.manager || "-" }}</n-descriptions-item>
                  <n-descriptions-item label="管理费率">{{ expandedData?.management_fee != null ? expandedData.management_fee + "%" : "-" }}</n-descriptions-item>
                  <n-descriptions-item label="上市日">{{ expandedData?.list_date ? expandedData.list_date.slice(0, 10) : "-" }}</n-descriptions-item>
                </n-descriptions>
              </n-grid-item>
            </n-grid>
            <div style="display: flex; gap: 8px; margin-top: 8px; justify-content: flex-end">
              <n-button size="tiny" type="primary" ghost @click="router.push('/backtest?stock=' + expandedCode)">快速回测</n-button>
              <n-button size="tiny" quaternary @click="basketStock = { symbol: expandedCode, name: expandedCode }; basketDialogShow = true">加入篮子</n-button>
              <n-button size="tiny" quaternary @click="expandedCode = null">收拢</n-button>
            </div>
          </template>
        </n-card>
      </template>
    </div>
  </div>
  <BasketSelectorDialog v-if="basketDialogShow" v-model:show="basketDialogShow" :stock="basketStock" />
</template>

<style lang="scss" scoped>
.etf-page { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.main-content { padding: 0 16px; }
</style>
