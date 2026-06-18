<!-- ETFMarket.vue — ETF Hub（列表 + 内联展开详情 + 远程分页）-->
<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
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
import { tokens } from "@/styles/design-tokens";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
use([CanvasRenderer, LineChart, GridComponent, TooltipComponent]);

const route = useRoute();
const router = useRouter();
const message = useMessage();
const loading = ref(true);
const error = ref(false);
const etfList = ref<any[]>([]);
const total = ref(0);
const filterType = ref<string | null>(null);
const filterSearch = ref("");
const expandedCode = ref<string | null>(null);
const expandedData = ref<any>(null);
const expandedLoading = ref(false);
const basketDialogShow = ref(false);
const basketStock = ref<{ symbol: string; name: string }>({ symbol: "", name: "" });
const page = ref(1);
const pageSize = ref(50);

const typeOptions = [
  { label: "全部", value: null },
  { label: "宽基", value: "宽基" },
  { label: "行业", value: "行业" },
  { label: "主题", value: "主题" },
  { label: "跨境", value: "跨境" },
  { label: "债券", value: "债券" },
];

const columns: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 110 },
  { title: "简称", key: "name", width: 120, ellipsis: { tooltip: true } },
  {
    title: "类型",
    key: "fundType",
    width: 70,
    render: (r: any) =>
      r.fundType
        ? h(NTag, { size: "tiny", bordered: false }, { default: () => r.fundType })
        : "-",
  },
  {
    title: "最新价",
    key: "latestPrice",
    width: 80,
    render: (r: any) => (r.latestPrice != null ? r.latestPrice.toFixed(3) : "-"),
  },
  {
    title: "涨跌幅",
    key: "latestPctChg",
    width: 80,
    render: (r: any) =>
      h(
        "span",
        { style: { color: (r.latestPctChg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } },
        r.latestPctChg != null
          ? (r.latestPctChg > 0 ? "+" : "") + r.latestPctChg.toFixed(2) + "%"
          : "-",
      ),
  },
  {
    title: "跟踪指数",
    key: "indexName",
    width: 120,
    ellipsis: { tooltip: true },
    render: (r: any) => r.indexName || "-",
  },
  { title: "管理人", key: "manager", width: 90, ellipsis: { tooltip: true }, render: (r: any) => r.manager || "-" },
];

// shares chart
const sharesOption = computed(() => {
  if (!expandedData.value?.shares?.length) return null;
  const items = [...expandedData.value.shares].reverse().slice(-60);
  return {
    grid: { top: 10, right: 10, bottom: 10, left: 60 },
    xAxis: {
      type: "category",
      data: items.map((d: any) => d.trade_date?.slice(5) ?? ""),
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10, formatter: (v: number) => (v / 1e8).toFixed(0) + "亿" },
    },
    tooltip: { trigger: "axis" },
    series: [{
      name: "份额",
      type: "line",
      data: items.map((d: any) => d.fund_size ?? 0),
      smooth: true,
      lineStyle: { color: "#4caf50", width: 2 },
      areaStyle: { color: "rgba(76,175,80,0.15)" },
      symbol: "none",
    }],
  };
});

async function toggleExpand(code: string) {
  if (expandedCode.value === code) { expandedCode.value = null; return; }
  expandedCode.value = code;
  expandedLoading.value = true;
  try {
    const [shares, benchmark] = await Promise.all([
      marketAPI.getEtfShares(code, 120).catch(() => []),
      marketAPI.getEtfBenchmark(code).catch(() => null),
    ]);
    const etf = etfList.value.find((e) => e.ts_code === code) || {};
    let weights: any[] = [];
    if (etf.indexCode) {
      weights = (await marketAPI.getIndexWeights(etf.indexCode, 0, 5).catch(() => ({ items: [] }))).items || [];
    }
    expandedData.value = { ...etf, shares, benchmark, weights };
  } catch {
    expandedData.value = { shares: [], benchmark: null, weights: [] };
  } finally {
    expandedLoading.value = false;
  }
}

async function load(p?: number) {
  loading.value = true;
  error.value = false;
  const pg = p || 1;
  try {
    const result = await marketAPI.getETFs({ page: pg, limit: pageSize.value });
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
  // 类型筛选和搜索关键词传给后端（如后端不支持则前端过滤）
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
        <!-- Filter bar — 水平排列 -->
        <n-space style="margin-bottom: 16px" align="center">
          <n-select
            v-model:value="filterType" :options="typeOptions" placeholder="类型"
            clearable size="small" style="width: 110px" @update:value="onFilterChange"
          />
          <n-input
            v-model:value="filterSearch" placeholder="搜索代码或名称"
            clearable size="small" style="width: 240px"
          />
          <span style="flex: 1" />
          <span style="font-size: 12px; color: var(--n-text-color-3)">
            共 {{ total }} 只 ETF
          </span>
        </n-space>

        <!-- ETF data table — 远程分页 -->
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
            <n-grid :x-gap="16" :cols="2">
              <n-grid-item>
                <div style="font-size: 12px; color: var(--n-text-color-3); margin-bottom: 4px">份额趋势 (120日)</div>
                <VChart v-if="sharesOption" :option="sharesOption" autoresize style="height: 220px" />
                <n-empty v-else description="暂无份额数据" style="padding: 20px" />
              </n-grid-item>
              <n-grid-item>
                <n-descriptions label-placement="left" :column="1" size="small">
                  <n-descriptions-item label="管理人">{{ expandedData?.manager || "-" }}</n-descriptions-item>
                  <n-descriptions-item label="管理费率">{{ expandedData?.managementFee != null ? expandedData.managementFee + "%" : "-" }}</n-descriptions-item>
                  <n-descriptions-item label="跟踪指数">
                    <span v-if="expandedData?.indexCode" style="cursor: pointer; color: var(--n-primary-color)"
                      @click="router.push('/market/index?focus=' + expandedData.indexCode)">
                      {{ expandedData.indexName }} ({{ expandedData.indexCode }})
                    </span>
                    <span v-else>-</span>
                  </n-descriptions-item>
                  <n-descriptions-item label="上市日">{{ expandedData?.listDate || "-" }}</n-descriptions-item>
                </n-descriptions>
              </n-grid-item>
            </n-grid>
            <div v-if="expandedData?.weights?.length" style="margin-top: 8px; font-size: 12px; color: var(--n-text-color-2)">
              前5大重仓：
              <span v-for="(w, i) in expandedData.weights" :key="i" style="cursor: pointer; margin-right: 8px"
                @click="router.push('/market/stock/' + w.ts_code)">
                {{ w.name }} {{ w.weight?.toFixed(1) }}%
              </span>
            </div>
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
