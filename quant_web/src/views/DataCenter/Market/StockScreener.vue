<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NCard,
  NGrid,
  NGridItem,
  NInputNumber,
  NSelect,
  NButton,
  NDataTable,
  NSkeleton,
  NEmpty,
  NResult,
  NSpace,
  NInput,
  NRadioGroup,
  NRadioButton,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import type { ScreenerStockItem, ScreenerEtfItem } from "@/types/entities/market";
import { tokens } from "@/styles/design-tokens";
import SmartIcon from "@/components/common/SmartIcon.vue";
import BasketSelectorDialog from "@/components/basket/BasketSelectorDialog.vue";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const loading = ref(false);
const error = ref(false);
const stocks = ref<ScreenerStockItem[]>([]);
const total = ref(0);
const page = ref(1);
const checkedRowKeys = ref<string[]>([]);
const basketDialogShow = ref(false);
const basketStock = ref<{ symbol: string; name: string }>({ symbol: "", name: "" });

const selectedCodes = computed(() => checkedRowKeys.value.join(","));
const hasSelection = computed(() => checkedRowKeys.value.length > 0);

function doBatchBacktest() {
  if (!hasSelection.value) return;
  router.push("/backtest?stock=" + selectedCodes.value);
}
function doBatchBasket() {
  if (!hasSelection.value) {
    message.warning("请先选择股票");
    return;
  }
  // 批量模式：打开篮子弹窗，把选中的第一只股票带入（后续可扩展批量 ADD）
  const first = stocks.value.find((s: any) => checkedRowKeys.value.includes(s.ts_code));
  if (first) {
    basketStock.value = { symbol: first.ts_code, name: first.name || first.ts_code };
    basketDialogShow.value = true;
  }
}
function doBatchCompare() {
  if (!hasSelection.value) return;
  router.push("/market/financial-compare?codes=" + selectedCodes.value);
}

const filters = reactive({
  market: [] as string[],
  industry: [] as string[],
  pe_min: null as number | null,
  pe_max: null as number | null,
  pb_min: null as number | null,
  pb_max: null as number | null,
  pct_chg_min: null as number | null,
  pct_chg_max: null as number | null,
  turnover_min: null as number | null,
  roe_min: null as number | null,
  sort_by: "pct_chg",
  sort_dir: "desc",
});

const marketOpts = [
  { label: "沪市 (SH)", value: "SH" },
  { label: "深市 (SZ)", value: "SZ" },
];

// ---- 标的类型切换（v5.11：股票 / ETF，对齐 TradingView/富途 统一筛选器模式） ----
const assetType = ref<"stock" | "etf">("stock");
const etfSearch = ref("");
const etfType = ref<string | null>(null);
const etfTypeOpts = ref<Array<{ label: string; value: string }>>([]);
const etfSortBy = ref("amount");
const etfSortOpts = [
  { label: "成交额", value: "amount" },
  { label: "涨跌幅", value: "pct_chg" },
  { label: "最新价", value: "close" },
  { label: "规模", value: "scale" },
];
function onAssetTypeChange() {
  checkedRowKeys.value = [];
  search(1);
}
const etfColumns: DataTableColumns<ScreenerEtfItem> = [
  { title: "代码", key: "ts_code", width: 100, fixed: "left" },
  { title: "简称", key: "name", width: 120, fixed: "left" },
  {
    title: "类型",
    key: "fund_type",
    width: 70,
    render: (r) => r.fund_type ?? "-",
  },
  {
    title: "最新价",
    key: "close",
    width: 80,
    render: (r) => r.close?.toFixed(3) ?? "-",
  },
  {
    title: "涨跌幅",
    key: "pct_chg",
    width: 80,
    render: (r) =>
      h(
        "span",
        { style: { color: (r.pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } },
        r.pct_chg != null
          ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%"
          : "-",
      ),
  },
  {
    // etf_daily.amount 千元 → /1e5 = 亿
    title: "成交额(亿)",
    key: "amount",
    width: 90,
    render: (r) => (r.amount != null ? (r.amount / 1e5).toFixed(1) + "亿" : "-"),
  },
  {
    // issue_amount 万份 × 面值≈1 元 → /1e4 = 亿元
    title: "规模(亿)",
    key: "scale_wan",
    width: 80,
    render: (r) => (r.scale_wan != null ? (r.scale_wan / 1e4).toFixed(1) + "亿" : "-"),
  },
];
const sortOpts = [
  { label: "涨跌幅", value: "pct_chg" },
  { label: "PE", value: "pe" },
  { label: "PB", value: "pb" },
  { label: "市值", value: "total_mv" },
  { label: "换手率", value: "turnover_rate" },
  { label: "成交额", value: "amount" },
  { label: "ROE", value: "roe" },
];

const columns: DataTableColumns<ScreenerStockItem> = [
  { type: "selection", width: 40 },
  { title: "代码", key: "ts_code", width: 100, fixed: "left" },
  { title: "简称", key: "name", width: 90, fixed: "left" },
  {
    title: "最新价",
    key: "close",
    width: 70,
    render: (r) => r.close?.toFixed(2) ?? "-",
  },
  {
    title: "涨跌幅",
    key: "pct_chg",
    width: 80,
    render: (r) =>
      h(
        "span",
        { style: { color: (r.pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } },
        r.pct_chg != null
          ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%"
          : "-",
      ),
  },
  { title: "PE", key: "pe", width: 70, render: (r) => r.pe?.toFixed(1) ?? "-" },
  { title: "PB", key: "pb", width: 70, render: (r) => r.pb?.toFixed(2) ?? "-" },
  {
    title: "市值(亿)",
    key: "total_mv",
    width: 90,
    render: (r) => (r.total_mv ? (r.total_mv / 1e8).toFixed(0) : "-"),
  },
  {
    title: "换手%",
    key: "turnover_rate",
    width: 70,
    render: (r) => r.turnover_rate?.toFixed(2) ?? "-",
  },
  {
    title: "ROE",
    key: "roe",
    width: 70,
    render: (r) => r.roe?.toFixed(1) ?? "-",
  },
  { title: "行业", key: "industry", width: 80 },
];

let timer: ReturnType<typeof setTimeout> | null = null;
async function search(p?: number) {
  loading.value = true;
  error.value = false;
  const pg = p || page.value;
  try {
    const result = await marketAPI.getScreener(
      assetType.value === "etf"
        ? {
            asset_type: "etf",
            search: etfSearch.value || undefined,
            fund_type: etfType.value || undefined,
            sort_by: etfSortBy.value,
            sort_dir: "desc",
            page: pg,
            limit: 50,
          }
        : {
            ...filters,
            asset_type: "stock",
            page: pg,
            limit: 50,
          },
    );
    stocks.value = result.stocks;
    total.value = result.total;
    page.value = pg;
  } catch {
    error.value = true;
    message.error("筛选失败");
  } finally {
    loading.value = false;
  }
}

function onFilterChange() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => search(1), 500);
}

function reset() {
  filters.market = [];
  filters.industry = [];
  filters.pe_min = null;
  filters.pe_max = null;
  filters.pb_min = null;
  filters.pb_max = null;
  filters.pct_chg_min = null;
  filters.pct_chg_max = null;
  filters.turnover_min = null;
  filters.roe_min = null;
  filters.sort_by = "pct_chg";
  filters.sort_dir = "desc";
  etfSearch.value = "";
  etfType.value = null;
  etfSortBy.value = "amount";
  search();
}

const industryOpts = ref<Array<{ label: string; value: string }>>([])

onMounted(async () => {
  const qIndustry = route.query.industry as string;
  if (qIndustry) {
    filters.industry = [qIndustry];
  }
  // 行业下拉：stock_basic.industry 去重（东财口径，保证与后端过滤一致）
  industryOpts.value = (await marketAPI.getScreenerIndustries()).map((name) => ({
    label: name,
    value: name,
  }));
  // ETF 类型下拉：etf_basic.fund_type 去重
  etfTypeOpts.value = (await marketAPI.getScreenerEtfTypes()).map((name) => ({
    label: name,
    value: name,
  }));
  search();
});
</script>

<template>
  <div class="screener-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">股票筛选器</h1>
          <p class="page-description">多因子条件筛选满足条件的股票</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="() => $router.back()" quaternary
            ><template #icon><SmartIcon name="ArrowLeft" /></template
          ></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- 标的类型切换（股票 / ETF） -->
      <n-space style="margin-bottom: 12px" align="center">
        <n-radio-group v-model:value="assetType" size="small" @update:value="onAssetTypeChange">
          <n-radio-button value="stock">股票</n-radio-button>
          <n-radio-button value="etf">ETF</n-radio-button>
        </n-radio-group>
        <span style="font-size: 12px; color: var(--n-text-color-3)">
          {{
            assetType === "etf"
              ? "按 类型/规模/成交额 筛选 ETF（与 ETF 市场页同数据源）"
              : "多因子筛选 A 股（市场/行业/PE/PB/市值/涨跌幅/换手/ROE）"
          }}
        </span>
      </n-space>

      <!-- 股票筛选条件 -->
      <n-grid
        v-if="assetType === 'stock'"
        :x-gap="16"
        :y-gap="12"
        :cols="6"
        style="margin-bottom: 16px"
      >
        <n-grid-item
          ><n-select
            v-model:value="filters.market"
            multiple
            placeholder="市场"
            :options="marketOpts"
            clearable
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-select
            v-model:value="filters.industry"
            :options="industryOpts"
            multiple
            placeholder="行业"
            clearable
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.pe_min"
            placeholder="PE低"
            :min="0"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.pe_max"
            placeholder="PE高"
            :min="0"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.pb_min"
            placeholder="PB低"
            :min="0"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.pb_max"
            placeholder="PB高"
            :min="0"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.pct_chg_min"
            placeholder="涨跌>"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.pct_chg_max"
            placeholder="涨跌<"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.turnover_min"
            placeholder="换手率>"
            :min="0"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-input-number
            v-model:value="filters.roe_min"
            placeholder="ROE>"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-select
            v-model:value="filters.sort_by"
            :options="sortOpts"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-button @click="reset" size="small" quaternary>重置</n-button
          ><n-button
            type="primary"
            size="small"
            @click="search()"
            style="margin-left: 8px"
            >搜索</n-button
          ></n-grid-item
        >
      </n-grid>

      <!-- ETF 筛选条件 -->
      <n-grid v-else :x-gap="16" :y-gap="12" :cols="6" style="margin-bottom: 16px">
        <n-grid-item
          ><n-input
            v-model:value="etfSearch"
            placeholder="代码或名称"
            clearable
            @update:value="onFilterChange"
            @keyup.enter="search(1)"
        /></n-grid-item>
        <n-grid-item
          ><n-select
            v-model:value="etfType"
            :options="etfTypeOpts"
            placeholder="类型"
            clearable
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-select
            v-model:value="etfSortBy"
            :options="etfSortOpts"
            @update:value="onFilterChange"
        /></n-grid-item>
        <n-grid-item
          ><n-button @click="reset" size="small" quaternary>重置</n-button
          ><n-button
            type="primary"
            size="small"
            @click="search()"
            style="margin-left: 8px"
            >搜索</n-button
          ></n-grid-item
        >
      </n-grid>

      <n-skeleton v-if="loading" :text="true" :repeat="6" />
      <n-result v-else-if="error" status="500" title="加载失败"
        ><template #footer
          ><n-button @click="search()">重试</n-button></template
        ></n-result
      >
      <n-empty v-else-if="!stocks.length" description="无匹配结果" />

      <n-card v-else :class="tokens.surface.card">
        <div
          v-if="hasSelection && assetType === 'stock'"
          style="
            margin-bottom: 12px;
            display: flex;
            gap: 8px;
            align-items: center;
          "
        >
          <span style="font-size: 13px; color: var(--n-text-color-2)"
            >已选 {{ checkedRowKeys.length }} 只</span
          >
          <n-button size="tiny" type="primary" ghost @click="doBatchBacktest"
            >批量回测</n-button
          >
          <n-button size="tiny" @click="doBatchBasket">批量加入篮子</n-button>
          <n-button size="tiny" @click="doBatchCompare">加入财务对比</n-button>
        </div>
        <n-dataTable
          :columns="assetType === 'etf' ? etfColumns : columns"
          :data="stocks"
          :row-key="(row: ScreenerStockItem | ScreenerEtfItem) => row.ts_code"
          v-model:checked-row-keys="checkedRowKeys"
          size="small"
          :bordered="false"
          remote
          max-height="calc(100vh - 360px)"
          :row-props="
            (row: ScreenerStockItem | ScreenerEtfItem) => ({
              style: 'cursor:pointer',
              onClick: () =>
                assetType === 'etf'
                  ? router.push('/market/etf?focus=' + row.ts_code)
                  : router.push('/market/stock/' + row.ts_code),
            })
          "
          :pagination="{
            page: page,
            pageSize: 50,
            itemCount: total,
            onChange: (p: number) => search(p),
          }"
        />
      </n-card>
    </div>
  </div>
  <BasketSelectorDialog v-if="basketDialogShow" v-model:show="basketDialogShow" :stock="basketStock" />
</template>

<style lang="scss" scoped>
.screener-page {
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}
</style>
