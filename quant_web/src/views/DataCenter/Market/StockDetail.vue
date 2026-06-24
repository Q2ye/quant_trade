<!-- StockDetail.vue - 个股深度分析，6 Tab -->
<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NCard,
  NGrid,
  NGridItem,
  NTabs,
  NTabPane,
  NSkeleton,
  NEmpty,
  NResult,
  NButton,
  NButtonGroup,
  NTag,
  NSpace,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import type { StockFullResponse, KLineItem } from "@/types/entities/market";
import { tokens } from "@/styles/design-tokens";
import SmartIcon from "@/components/common/SmartIcon.vue";
import LightweightKLine, {
  type SignalMarker,
} from "@/components/charts/LightweightKLine.vue";
import LightweightLineChart, {
  type LineSeriesDef,
  type BarSeriesDef,
} from "@/components/charts/LightweightLineChart.vue";
import StockSignalPanel from "@/components/market/StockSignalPanel.vue";
import BasketSelectorDialog from "@/components/basket/BasketSelectorDialog.vue";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const tsCode = computed(() =>
  ((route.params.code as string) || "").toUpperCase(),
);
const loading = ref(true);
const error = ref(false);
const data = ref<StockFullResponse | null>(null);
const basketDialogShow = ref(false);
const basketStock = ref<{ symbol: string; name: string }>({ symbol: "", name: "" });
const activeTab = ref("overview");
const kPeriod = ref<"daily" | "weekly" | "monthly">("daily");
const signalMarkers = ref<SignalMarker[]>([]);

// ---- K线动态加载缓存 ----
const klineCache = reactive<Record<string, KLineItem[]>>({
  daily: [],
  weekly: [],
  monthly: [],
  moneyflow: [],
});
const klineLoadingMore = ref(false);
const klineHasMore = reactive<Record<string, boolean>>({
  daily: true,
  weekly: true,
  monthly: true,
  moneyflow: true,
});

const klineData = computed(() => klineCache[kPeriod.value] ?? []);

function initKlineCache(resp: StockFullResponse) {
  klineCache.daily = resp.quotes?.daily ?? [];
  klineCache.weekly = resp.quotes?.weekly ?? [];
  klineCache.monthly = resp.quotes?.monthly ?? [];
  klineCache.moneyflow = (resp.moneyflow ?? []) as any;
  klineHasMore.daily = (resp.quotes?.daily ?? []).length >= 1000;
  klineHasMore.weekly = (resp.quotes?.weekly ?? []).length >= 1000;
  klineHasMore.monthly = (resp.quotes?.monthly ?? []).length >= 1000;
  klineHasMore.moneyflow = (resp.moneyflow ?? []).length >= 500;
}

async function loadMoreKline(period: string = kPeriod.value) {
  if (!klineHasMore[period] || klineLoadingMore.value) return;

  const cache = klineCache[period];
  if (!cache.length) return;

  const dateField = period === "moneyflow" ? "trade_date" : "trade_date";
  const oldestDate = (cache[0] as any)[dateField] ?? cache[0].trade_date;
  klineLoadingMore.value = true;

  try {
    const rows = await marketAPI.getStockKline(
      tsCode.value,
      period as "daily" | "weekly" | "monthly" | "moneyflow",
      oldestDate,
      500,
    );
    if (rows.length > 0) {
      const existingDates = new Set(cache.map((d: any) => d.trade_date ?? (d as any).end_date));
      const newRows = rows.filter((r: any) => !existingDates.has(r.trade_date ?? r.end_date));
      if (newRows.length > 0) {
        klineCache[period] = [...newRows, ...cache] as any;
      }
      klineHasMore[period] = rows.length >= 500;
    } else {
      klineHasMore[period] = false;
    }
  } catch (e) {
    console.error("[StockDetail] loadMoreKline error:", e);
  } finally {
    klineLoadingMore.value = false;
  }
}

function onTimeRangeChange(range: { from: number; to: number }, period?: string) {
  const p = period ?? kPeriod.value;
  if (!klineHasMore[p] || klineLoadingMore.value) return;

  const cache = klineCache[p];
  if (!cache.length) return;

  const dateField = p === "moneyflow" ? "trade_date" : "trade_date";
  const oldestDate = (cache[0] as any)[dateField] ?? cache[0].trade_date;
  const oldestTime = Math.floor(
    new Date(oldestDate + "T00:00:00Z").getTime() / 1000,
  );
  const visibleSpan = range.to - range.from;
  const threshold = visibleSpan * 0.3;

  if (range.from - threshold <= oldestTime) {
    loadMoreKline(p);
  }
}

async function addToWatchlist() {
  const basic = data.value?.basic;
  if (!basic) return;
  try {
    // fetch current list, toggle this code
    const current = await marketAPI.getWatchlist();
    const codes = current.map((w: any) => w.ts_code);
    const idx = codes.indexOf(basic.ts_code);
    if (idx >= 0) {
      codes.splice(idx, 1);
      message.success("已从自选移除");
    } else {
      codes.push(basic.ts_code);
      message.success("已加入自选股");
    }
    await marketAPI.saveWatchlist(codes);
  } catch {
    message.warning("操作失败");
  }
}

const pctColor = (v: number | null) =>
  v == null ? "" : v > 0 ? "#ef5350" : v < 0 ? "#26a69a" : "";

const pctText = (v: number | null) =>
  v == null ? "-" : (v > 0 ? "+" : "") + v.toFixed(2) + "%";

// ---- 资金流向 chart ----
const moneyflowSeries = computed<BarSeriesDef[]>(() => {
  const raw = klineCache.moneyflow as any[];
  if (!raw?.length) return [];
  const items = [...raw].reverse();
  return [
    {
      name: "主力净流入",
      data: items.map((d: any) => ({
        time: d.trade_date?.slice(0, 10) ?? "",
        value: d.net_mf_amount ?? null,
        color: (d.net_mf_amount ?? 0) >= 0 ? "rgba(239,83,80,0.6)" : "rgba(38,166,154,0.6)",
      })),
    },
  ];
});
const moneyflowColumns: any = [
  { title: "日期", key: "trade_date", width: 100 },
  {
    title: "净流入(亿)",
    key: "net_mf_amount",
    render: (r: any) => {
      const v = r.net_mf_amount;
      return v != null ? (v / 1e8).toFixed(2) : "-";
    },
  },
  {
    title: "超大单买(亿)",
    key: "buy_elg_amount",
    render: (r: any) =>
      r.buy_elg_amount != null ? (r.buy_elg_amount / 1e8).toFixed(2) : "-",
  },
  {
    title: "超大单卖(亿)",
    key: "sell_elg_amount",
    render: (r: any) =>
      r.sell_elg_amount != null ? (r.sell_elg_amount / 1e8).toFixed(2) : "-",
  },
  {
    title: "大单买(亿)",
    key: "buy_lg_amount",
    render: (r: any) =>
      r.buy_lg_amount != null ? (r.buy_lg_amount / 1e8).toFixed(2) : "-",
  },
  {
    title: "大单卖(亿)",
    key: "sell_lg_amount",
    render: (r: any) =>
      r.sell_lg_amount != null ? (r.sell_lg_amount / 1e8).toFixed(2) : "-",
  },
];

// ---- 因子数据 ----
const factorData = computed(
  () =>
    data.value?.factors?.stk_factor ||
    data.value?.factors?.stk_factor_pro ||
    [],
);
const factorColors = ["#ff9800", "#448AFF", "#E040FB", "#00bcd4", "#ff5722", "#8bc34a"];

const factorSeries = computed<LineSeriesDef[]>(() => {
  if (!factorData.value.length) return [];
  const raw = [...factorData.value].slice(-60);
  if (!raw.length) return [];

  const metaKeys = new Set(["ts_code", "trade_date", "id", "created_at", "updated_at"]);

  // 统计每个因子 key 的非空数据点数 + 方差
  const keyStats = new Map<string, { cnt: number; mean: number; std: number; min: number; max: number }>();
  for (const row of raw) {
    for (const k of Object.keys(row)) {
      if (metaKeys.has(k)) continue;
      const v = (row as any)[k];
      if (v == null || isNaN(v) || typeof v !== "number") continue;
      if (!keyStats.has(k)) keyStats.set(k, { cnt: 0, mean: 0, std: 0, min: Infinity, max: -Infinity });
      const st = keyStats.get(k)!;
      st.cnt++; st.mean += v; st.min = Math.min(st.min, v); st.max = Math.max(st.max, v);
    }
  }

  // 计算均值/方差，过滤常量
  const candidates: { key: string; cnt: number; std: number; mean: number; min: number; max: number }[] = [];
  for (const [k, st] of keyStats) {
    if (st.cnt < 10) continue;
    st.mean /= st.cnt;
    // 二次遍历计算方差
    let variance = 0;
    for (const row of raw) {
      const v = (row as any)[k];
      if (v != null && !isNaN(v)) variance += (v - st.mean) ** 2;
    }
    variance /= st.cnt;
    st.std = Math.sqrt(variance) || 0.001;
    if (st.max - st.min < 0.0001) continue; // 跳过常量
    candidates.push({ key: k, ...st });
  }

  // 按数据点数排序，取 top 6
  candidates.sort((a, b) => b.cnt - a.cnt);
  const keys = candidates.slice(0, 6).map(c => c.key);
  if (!keys.length) return [];

  const series: LineSeriesDef[] = keys.map((k, i) => {
    const st = candidates.find(c => c.key === k)!;
    return {
      name: k,
      color: factorColors[i % factorColors.length],
      lineWidth: 1.5,
      data: raw.map((d: any) => {
        const v = d[k];
        if (v == null || isNaN(v)) return { time: d.trade_date?.slice(0, 10) ?? "", value: null };
        return { time: d.trade_date?.slice(0, 10) ?? "", value: (v - st.mean) / st.std };
      }),
    };
  });

  // 零线
  if (raw.length > 0) {
    series.push({
      name: "零线", color: "rgba(156,163,175,0.5)", lineWidth: 1, lineStyle: 2,
      data: [
        { time: raw[0].trade_date?.slice(0, 10) ?? "", value: 0 },
        { time: raw[raw.length - 1].trade_date?.slice(0, 10) ?? "", value: 0 },
      ],
    });
  }
  return series;
});

// ---- 股东数据 ----
const holderColumns: any = [
  {
    title: "股东名称",
    key: "holder_name",
    width: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: "持股数",
    key: "hold_num",
    width: 100,
    render: (r: any) => r.hold_num?.toLocaleString() ?? "-",
  },
  {
    title: "持股比例(%)",
    key: "hold_ratio",
    width: 100,
    render: (r: any) => r.hold_ratio?.toFixed(2) ?? "-",
  },
  { title: "报告期", key: "end_date", width: 100 },
];
const holderSeries = computed<LineSeriesDef[]>(() => {
  const raw = data.value?.shareholders?.holdernumber;
  if (!raw?.length) return [];
  // 去重 + 升序排列（lightweight-charts 要求时间严格递增）
  const seen = new Set<string>();
  const items = [...raw]
    .reverse()
    .filter((d: any) => {
      const t = d.end_date?.slice(0, 10) ?? "";
      if (seen.has(t)) return false;
      seen.add(t);
      return true;
    });
  return [
    {
      name: "股东人数",
      color: "#ff9800",
      lineWidth: 2,
      data: items.map((d: any) => ({
        time: d.end_date?.slice(0, 10) ?? "",
        value: d.holder_num ?? null,
      })),
    },
  ];
});

// ---- 停牌记录推断（从日线数据缺口 >1 交易日的推断为停牌期）----
const suspensionPeriods = computed(() => {
  const daily = data.value?.quotes?.daily;
  if (!daily?.length) return [];
  const periods: { start: string; end: string; days: number }[] = [];
  const sorted = [...daily].sort((a, b) =>
    a.trade_date.localeCompare(b.trade_date),
  );
  for (let i = 1; i < sorted.length; i++) {
    const prev = new Date(sorted[i - 1].trade_date);
    const curr = new Date(sorted[i].trade_date);
    const gapMs = curr.getTime() - prev.getTime();
    const gapDays = Math.round(gapMs / 86400000);
    // > 3 calendar days gap while markets trade ~5 days/week → likely suspension
    if (gapDays > 3) {
      periods.push({
        start: sorted[i - 1].trade_date,
        end: sorted[i].trade_date,
        days: gapDays - 1,
      });
    }
  }
  return periods.slice(-5); // last 5 suspension periods
});

function goBack() {
  router.back();
}

async function load() {
  loading.value = true;
  error.value = false;
  try {
    const resp = await marketAPI.getStockFull(tsCode.value);
    console.log("[StockDetail] API response:", resp);
    if (!resp) {
      console.warn("[StockDetail] getStockFull returned null/undefined");
      error.value = true;
      return;
    }
    if (!resp.basic) {
      console.warn("[StockDetail] response.basic is missing — stock may not exist in DB");
      error.value = true;
      return;
    }
    data.value = resp;
    initKlineCache(resp);
    // fetch signals in background (graceful fallback)
    marketAPI
      .getStockSignals(tsCode.value, 20)
      .then((s) => {
        if (s?.length) signalMarkers.value = s;
      })
      .catch(() => {});
  } catch (e) {
    console.error("[StockDetail] load error:", e);
    error.value = true;
  } finally {
    loading.value = false;
  }
}

watch(tsCode, load);
onMounted(load);
</script>

<template>
  <div class="stock-detail bg-gradient-mesh bg-noise">
    <!-- Header -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <template v-if="data?.basic">
            <h1 class="page-title">
              {{ data.basic.name || tsCode }}
              <span
                style="
                  font-size: 14px;
                  font-weight: 400;
                  color: var(--n-text-color-3);
                "
                >{{ tsCode }}</span
              >
            </h1>
            <p class="page-description">
              <n-tag v-if="data.basic.is_st" type="error" size="small"
                >ST</n-tag
              >
              <n-tag v-if="data.basic.industry" size="small">{{
                data.basic.industry
              }}</n-tag>
            </p>
          </template>
          <h1 v-else class="page-title">{{ tsCode }}</h1>
        </div>
        <div class="header-actions">
          <n-button
            size="tiny"
            type="primary"
            ghost
            @click="router.push('/backtest?stock=' + tsCode)"
            >快速回测</n-button
          >
          <n-button
            size="tiny"
            quaternary
            @click="basketStock = { symbol: tsCode, name: data?.name || tsCode }; basketDialogShow = true"
            >加入篮子</n-button
          >
          <n-button size="tiny" quaternary @click="addToWatchlist"
            >⭐ 自选</n-button
          >
          <n-button
            size="tiny"
            quaternary
            @click="router.push('/market/financial-compare?codes=' + tsCode)"
            >加入财务对比</n-button
          >
          <n-button
            size="tiny"
            quaternary
            @click="
              router.push(
                '/market/screener?industry=' +
                  encodeURIComponent(data?.basic?.industry || ''),
              )
            "
            >同行业股票 →</n-button
          >
          <n-button class="action-btn" @click="goBack" quaternary
            ><template #icon><SmartIcon name="ArrowLeft" /></template
          ></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <n-skeleton
        v-if="loading"
        :text="true"
        :repeat="6"
        style="padding: 24px"
      />

      <!-- Error -->
      <n-result v-else-if="error" status="500" title="加载失败">
        <template #footer>
          <n-space vertical align="center">
            <n-button @click="load">重试</n-button>
            <span style="font-size:12px;color:var(--n-text-color-3);margin-top:8px">
              如后端日志显示 200 但页面无数据，请检查浏览器扩展<br/>
              （如 highlight-manager）是否篡改了 API 响应
            </span>
          </n-space>
        </template>
      </n-result>

      <!-- Data -->
      <template v-else-if="data">
        <!-- Quote Bar -->
        <n-card
          :class="tokens.surface.card"
          size="small"
          style="margin-bottom: 16px"
        >
          <div class="quote-bar">
            <div class="quote-main">
              <span class="quote-price">{{
                data.latest_quote?.close?.toFixed(2) ?? "-"
              }}</span>
              <span
                class="quote-pct"
                :style="{ color: pctColor(data.latest_quote?.pct_chg ?? null) }"
              >
                {{ pctText(data.latest_quote?.pct_chg ?? null) }}
              </span>
            </div>
            <div class="quote-meta">
              <div class="meta-item">
                <span class="meta-label">开盘</span
                ><span>{{ data.latest_quote?.open?.toFixed(2) ?? "-" }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">最高</span
                ><span style="color: #ef5350">{{
                  data.latest_quote?.high?.toFixed(2) ?? "-"
                }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">最低</span
                ><span style="color: #26a69a">{{
                  data.latest_quote?.low?.toFixed(2) ?? "-"
                }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">昨收</span
                ><span>{{
                  data.limit_price?.pre_close?.toFixed(2) ?? "-"
                }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">涨停</span
                ><span style="color: #ef5350">{{
                  data.limit_price?.up_limit?.toFixed(2) ?? "-"
                }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">跌停</span
                ><span style="color: #26a69a">{{
                  data.limit_price?.down_limit?.toFixed(2) ?? "-"
                }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">成交额</span
                ><span>{{
                  data.latest_quote?.amount
                    ? (data.latest_quote.amount / 1e8).toFixed(1) + "亿"
                    : "-"
                }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">成交量</span
                ><span>{{
                  data.latest_quote?.vol
                    ? (data.latest_quote.vol / 1e4).toFixed(0) + "万手"
                    : "-"
                }}</span>
              </div>
            </div>
            <div class="quote-meta" style="margin-top: 6px">
              <div class="meta-item">
                <span class="meta-label">PE(TTM)</span
                ><span>{{ data.latest_basic?.pe?.toFixed(2) ?? "-" }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">PB</span
                ><span>{{ data.latest_basic?.pb?.toFixed(2) ?? "-" }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">总市值</span
                ><span>{{
                  data.latest_basic?.total_mv
                    ? (data.latest_basic.total_mv / 1e8).toFixed(0) + "亿"
                    : "-"
                }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">换手率</span
                ><span
                  >{{
                    data.latest_basic?.turnover_rate?.toFixed(2) ?? "-"
                  }}%</span
                >
              </div>
            </div>
          </div>
        </n-card>

        <!-- K-line + Signal Panel (2-col) -->
        <n-grid :x-gap="16" style="margin-top: 16px" :cols="4">
          <n-grid-item :span="3">
            <n-card :class="tokens.surface.card" size="small" title="K线图表">
              <template #header-extra>
                <n-button-group size="tiny">
                  <n-button
                    :type="kPeriod === 'daily' ? 'primary' : 'default'"
                    @click="kPeriod = 'daily'"
                    >日K</n-button
                  >
                  <n-button
                    :type="kPeriod === 'weekly' ? 'primary' : 'default'"
                    @click="kPeriod = 'weekly'"
                    >周K</n-button
                  >
                  <n-button
                    :type="kPeriod === 'monthly' ? 'primary' : 'default'"
                    @click="kPeriod = 'monthly'"
                    >月K</n-button
                  >
                </n-button-group>
              </template>
              <LightweightKLine
                :key="kPeriod"
                :data="klineData"
                :ma-lines="[5, 10, 20]"
                :show-volume="true"
                :height="450"
                :loading="loading"
                :error="error"
                :signal-markers="signalMarkers"
                @retry="load"
                @timeRangeChange="(r: any) => onTimeRangeChange(r, kPeriod)"
              />
              <div
                v-if="klineLoadingMore"
                style="text-align: center; padding: 4px; font-size: 12px; color: var(--n-text-color-3);"
              >
                加载更多历史数据...
              </div>
              <div
                v-else-if="!klineHasMore[kPeriod] && klineCache[kPeriod].length > 0"
                style="text-align: center; padding: 4px; font-size: 12px; color: var(--n-text-color-3);"
              >
                已加载全部历史数据
              </div>
            </n-card>
          </n-grid-item>
          <n-grid-item :span="1">
            <StockSignalPanel
              :basic-info="data?.basic || null"
              :factor-data="factorData"
              :risk-data="data?.risk || {}"
              :loading="loading"
            />
          </n-grid-item>
        </n-grid>

        <!-- Tabs -->
        <n-card :class="tokens.surface.card" style="margin-top: 16px">
          <n-tabs v-model:value="activeTab" type="line" animated>
            <!-- 概览 Tab -->
            <n-tab-pane name="overview" tab="概览">
              <n-grid :x-gap="16" :y-gap="16" :cols="2">
                <n-grid-item>
                  <n-card title="公司信息" size="small" :bordered="true">
                    <n-descriptions
                      label-placement="left"
                      :column="1"
                      size="small"
                    >
                      <n-descriptions-item label="全称">{{
                        data.basic?.fullname || data.basic?.name || "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="代码">{{
                        tsCode
                      }}</n-descriptions-item>
                      <n-descriptions-item label="行业">{{
                        data.basic?.industry || "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="上市日期">{{
                        data.basic?.list_date || "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="省份">{{
                        data.basic?.province || "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="城市">{{
                        data.basic?.city || "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item
                        label="网站"
                        v-if="data.basic?.website"
                        >{{ data.basic.website }}</n-descriptions-item
                      >
                    </n-descriptions>
                  </n-card>
                </n-grid-item>
                <n-grid-item>
                  <n-card title="估值指标" size="small" :bordered="true">
                    <n-descriptions
                      label-placement="left"
                      :column="1"
                      size="small"
                    >
                      <n-descriptions-item label="PE(TTM)">{{
                        data.latest_basic?.pe?.toFixed(2) ?? "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="PB">{{
                        data.latest_basic?.pb?.toFixed(2) ?? "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="总市值">{{
                        data.latest_basic?.total_mv
                          ? (data.latest_basic.total_mv / 1e8).toFixed(0) + "亿"
                          : "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="流通市值">{{
                        data.latest_basic?.circ_mv
                          ? (data.latest_basic.circ_mv / 1e8).toFixed(0) + "亿"
                          : "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="换手率"
                        >{{
                          data.latest_basic?.turnover_rate?.toFixed(2) ?? "-"
                        }}%</n-descriptions-item
                      >
                      <n-descriptions-item label="量比">{{
                        data.latest_basic?.volume_ratio?.toFixed(2) ?? "-"
                      }}</n-descriptions-item>
                    </n-descriptions>
                  </n-card>
                </n-grid-item>
              </n-grid>
            </n-tab-pane>

            <!-- 资金 Tab -->
            <n-tab-pane name="moneyflow" tab="资金">
              <template v-if="data.moneyflow?.length">
                <n-card title="资金流向趋势" size="small" :bordered="true">
                  <LightweightLineChart
                    :bar-series="moneyflowSeries"
                    :height="300"
                    empty-text="暂无资金数据"
                    @time-range-change="(r: any) => onTimeRangeChange(r, 'moneyflow')"
                  />
                </n-card>
                <n-card
                  title="最近 20 日明细"
                  size="small"
                  :bordered="true"
                  style="margin-top: 16px"
                >
                  <n-dataTable
                    :columns="moneyflowColumns"
                    :data="data.moneyflow.slice(0, 20)"
                    size="small"
                    :bordered="false"
                    max-height="400"
                  />
                </n-card>
              </template>
              <n-empty
                v-else
                description="暂无资金流向数据"
                style="padding: 60px"
              />
            </n-tab-pane>

            <!-- 财务 Tab (Phase 3) -->
            <n-tab-pane name="financial" tab="财务">
              <template v-if="data.financial?.indicators?.length">
                <n-card title="财务指标" size="small" :bordered="true">
                  <n-data-table
                    :columns="[
                      { title: '报告期', key: 'end_date', width: 100 },
                      { title: 'ROE', key: 'roe', width: 80 },
                      { title: 'ROA', key: 'roa', width: 80 },
                      { title: '毛利率', key: 'grossprofit_margin', width: 80 },
                      { title: '净利率', key: 'netprofit_margin', width: 80 },
                      { title: '资产负债率', key: 'debt_to_assets', width: 90 },
                    ]"
                    :data="data.financial.indicators"
                    size="small"
                    :bordered="true"
                    max-height="400"
                  />
                </n-card>
              </template>
              <n-empty
                v-else
                description="暂无财务数据"
                style="padding: 60px"
              />
            </n-tab-pane>

            <!-- 股东 Tab -->
            <n-tab-pane name="shareholder" tab="股东">
              <template v-if="data.shareholders?.top10?.length">
                <n-card title="前十大股东" size="small" :bordered="true">
                  <n-dataTable
                    :columns="holderColumns"
                    :data="data.shareholders.top10"
                    size="small"
                    :bordered="false"
                    max-height="400"
                  />
                </n-card>
              </template>
              <template v-if="data.shareholders?.holdernumber?.length">
                <n-card
                  title="股东人数变化"
                  size="small"
                  :bordered="true"
                  style="margin-top: 16px"
                >
                  <LightweightLineChart
                    :line-series="holderSeries"
                    :height="250"
                    empty-text="暂无股东人数数据"
                  />
                </n-card>
              </template>
              <n-empty
                v-if="
                  !data.shareholders?.top10?.length &&
                  !data.shareholders?.holdernumber?.length
                "
                description="暂无股东数据"
                style="padding: 60px"
              />
            </n-tab-pane>

            <!-- 因子 Tab -->
            <n-tab-pane name="factor" tab="因子">
              <template v-if="factorData.length">
                <n-card title="技术因子趋势" size="small" :bordered="true">
                  <LightweightLineChart
                    :line-series="factorSeries"
                    :height="300"
                    empty-text="暂无因子数据"
                  />
                </n-card>
              </template>
              <n-empty
                v-else
                description="暂无因子数据"
                style="padding: 60px"
              />
            </n-tab-pane>

            <!-- 风险 Tab -->
            <n-tab-pane name="risk" tab="风险">
              <template v-if="data.risk?.st_risk || data.risk?.pledge_stat">
                <n-card size="small" :bordered="true">
                  <n-descriptions
                    label-placement="left"
                    :column="1"
                    size="small"
                  >
                    <n-descriptions-item
                      v-if="data.basic?.is_st"
                      label="ST状态"
                    >
                      <n-tag type="error">ST</n-tag>
                    </n-descriptions-item>
                    <n-descriptions-item v-else label="ST状态"
                      >正常</n-descriptions-item
                    >
                    <template v-if="data.risk.st_risk">
                      <n-descriptions-item label="风险评级">{{
                        data.risk.st_risk.risk_level || "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="风险备注">{{
                        data.risk.st_risk.remarks || "-"
                      }}</n-descriptions-item>
                    </template>
                    <template v-if="data.risk.pledge_stat">
                      <n-descriptions-item label="质押比例">{{
                        data.risk.pledge_stat.pledge_ratio != null
                          ? (data.risk.pledge_stat.pledge_ratio * 100).toFixed(
                              1,
                            ) + "%"
                          : "-"
                      }}</n-descriptions-item>
                      <n-descriptions-item label="质押总股数"
                        >{{
                          data.risk.pledge_stat.pledged_shares?.toLocaleString() ??
                          "-"
                        }}股</n-descriptions-item
                      >
                    </template>
                    <n-descriptions-item label="上市状态">
                      <n-tag
                        v-if="data.basic?.list_status === 'L'"
                        type="success"
                        size="small"
                        >上市</n-tag
                      >
                      <n-tag
                        v-else-if="data.basic?.list_status === 'D'"
                        type="error"
                        size="small"
                        >退市</n-tag
                      >
                      <n-tag
                        v-else-if="data.basic?.list_status === 'P'"
                        type="warning"
                        size="small"
                        >暂停上市</n-tag
                      >
                      <span v-else>-</span>
                    </n-descriptions-item>
                    <n-descriptions-item label="上市日期">{{
                      data.basic?.list_date || "-"
                    }}</n-descriptions-item>
                    <n-descriptions-item label="停牌状态">
                      <n-tag
                        v-if="data.basic?.list_status === 'P'"
                        type="warning"
                        size="small"
                        >当前暂停交易</n-tag
                      >
                      <n-tag v-else type="success" size="small">正常交易</n-tag>
                    </n-descriptions-item>
                    <n-descriptions-item
                      v-if="data.basic?.delist_date"
                      label="退市日期"
                      >{{ data.basic.delist_date }}</n-descriptions-item
                    >
                  </n-descriptions>
                </n-card>
                <!-- 停牌记录（从日线缺口推断） -->
                <n-card
                  v-if="suspensionPeriods.length"
                  size="small"
                  :bordered="true"
                  style="margin-top: 16px"
                  title="历史停牌记录（数据缺口推断）"
                >
                  <n-dataTable
                    :columns="[
                      { title: '起始日', key: 'start', width: 110 },
                      { title: '恢复日', key: 'end', width: 110 },
                      {
                        title: '停牌天数',
                        key: 'days',
                        width: 90,
                        render: (r: any) => r.days + ' 天',
                      },
                    ]"
                    :data="suspensionPeriods"
                    size="small"
                    :bordered="false"
                    max-height="200"
                  />
                </n-card>
              </template>
              <n-empty
                v-else
                description="暂无风险数据"
                style="padding: 60px"
              />
            </n-tab-pane>

            <!-- 信号历史 Tab -->
            <n-tab-pane name="signals" tab="信号历史">
              <template v-if="signalMarkers.length">
                <n-dataTable
                  :columns="[
                    { title: '时间', key: 'time', width: 100 },
                    {
                      title: '类型',
                      key: 'position',
                      width: 70,
                      render: (r: any) =>
                        r.position === 'aboveBar' ? '买入' : '卖出',
                    },
                    {
                      title: '策略',
                      key: 'strategyName',
                      width: 120,
                      ellipsis: { tooltip: true },
                    },
                    { title: '信号', key: 'text', ellipsis: { tooltip: true } },
                  ]"
                  :data="signalMarkers"
                  size="small"
                  :bordered="false"
                  max-height="400"
                />
              </template>
              <n-empty
                v-else
                description="暂无策略信号——策略运行后信号将在此展示"
                style="padding: 60px"
              />
            </n-tab-pane>
          </n-tabs>
        </n-card>
      </template>
    </div>
  </div>
  <BasketSelectorDialog v-if="basketDialogShow" v-model:show="basketDialogShow" :stock="basketStock" />
</template>

<style lang="scss" scoped>
.stock-detail {
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}
.stock-name {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
}
.stock-code {
  font-size: 13px;
  color: var(--n-text-color-3);
  font-family: monospace;
}
.quote-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quote-main {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.quote-price {
  font-size: 32px;
  font-weight: 700;
  font-family: monospace;
}
.quote-pct {
  font-size: 20px;
  font-weight: 600;
}
.quote-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.meta-item {
  display: flex;
  gap: 4px;
  font-size: 13px;
  align-items: baseline;
}
.meta-label {
  color: var(--n-text-color-3);
}
</style>
