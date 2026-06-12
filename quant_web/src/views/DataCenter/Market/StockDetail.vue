<!-- StockDetail.vue - 个股深度分析，6 Tab -->
<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import {
  NCard, NGrid, NGridItem, NTabs, NTabPane, NSkeleton, NEmpty, NResult, NButton,
  NTag, NSpace, NDataTable, NStatistic, NDescriptions, NDescriptionsItem, useMessage,
} from "naive-ui"
import type { DataTableColumns } from "naive-ui"
import marketAPI from "@/api/market"
import type { StockFullResponse, KLineItem } from "@/types/entities/market"
import { tokens } from "@/styles/design-tokens"
import SmartIcon from "@/components/common/SmartIcon.vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { CandlestickChart, LineChart, BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, MarkLineComponent } from "echarts/components"

use([CanvasRenderer, CandlestickChart, LineChart, BarChart,
     GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, MarkLineComponent])

const route = useRoute()
const router = useRouter()
const message = useMessage()
const tsCode = computed(() => (route.params.code as string || "").toUpperCase())
const loading = ref(true)
const error = ref(false)
const data = ref<StockFullResponse | null>(null)
const activeTab = ref("overview")

const pctColor = (v: number | null) =>
  v == null ? "" : v > 0 ? "#ef5350" : v < 0 ? "#26a69a" : ""

const pctText = (v: number | null) =>
  v == null ? "-" : (v > 0 ? "+" : "") + v.toFixed(2) + "%"

// ---- K线图 option ----
const klineOption = computed(() => {
  if (!data.value?.quotes?.daily?.length) return {}
  const raw = data.value.quotes.daily.slice(-120)
  const dates = raw.map((d: KLineItem) => d.trade_date)
  const ohlc = raw.map((d: KLineItem) => [d.open ?? 0, d.close ?? 0, d.low ?? 0, d.high ?? 0])
  const vols = raw.map((d: KLineItem) => d.vol ?? 0)
  const ma5: (number | null)[] = []; const ma10: (number | null)[] = []; const ma20: (number | null)[] = []
  for (let i = 0; i < ohlc.length; i++) {
    const slice5 = ohlc.slice(Math.max(0, i - 4), i + 1)
    ma5.push(slice5.length === 5 ? slice5.reduce((s, v) => s + v[1], 0) / 5 : null)
    const slice10 = ohlc.slice(Math.max(0, i - 9), i + 1)
    ma10.push(slice10.length === 10 ? slice10.reduce((s, v) => s + v[1], 0) / 10 : null)
    const slice20 = ohlc.slice(Math.max(0, i - 19), i + 1)
    ma20.push(slice20.length === 20 ? slice20.reduce((s, v) => s + v[1], 0) / 20 : null)
  }
  return {
    grid: [
      { left: "3%", right: "3%", top: 10, height: "55%" },
      { left: "3%", right: "3%", top: "72%", height: "20%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
      { type: "category", data: dates, gridIndex: 1, axisLabel: { fontSize: 10 }, axisLine: { show: false } },
    ],
    yAxis: [
      { type: "value", gridIndex: 0, scale: true, splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } } },
      { type: "value", gridIndex: 1, axisLabel: { show: false } },
    ],
    tooltip: { trigger: "axis", axisPointer: { type: "cross", crossStyle: { color: "#999" } } },
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1], start: 50, end: 100 }],
    series: [
      { name: "K线", type: "candlestick", data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: "#ef5350", color0: "#26a69a", borderColor: "#ef5350", borderColor0: "#26a69a" } },
      { name: "MA5", type: "line", data: ma5, xAxisIndex: 0, yAxisIndex: 0, smooth: true, lineStyle: { width: 1, color: "#ff9800" }, symbol: "none" },
      { name: "MA10", type: "line", data: ma10, xAxisIndex: 0, yAxisIndex: 0, smooth: true, lineStyle: { width: 1, color: "#2196f3" }, symbol: "none" },
      { name: "MA20", type: "line", data: ma20, xAxisIndex: 0, yAxisIndex: 0, smooth: true, lineStyle: { width: 1, color: "#9c27b0" }, symbol: "none" },
      { name: "成交量", type: "bar", data: vols, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: (p: any) => {
          const idx = p.dataIndex; const d = raw[idx]
          return d && d.close >= d.open ? "#ef5350" : "#26a69a"
        } } },
    ],
  }
})

// ---- 资金流向 chart ----
const moneyflowOption = computed(() => {
  if (!data.value?.moneyflow?.length) return null
  const raw = [...data.value.moneyflow].reverse()
  return {
    grid: { top: 10, right: 10, bottom: 10, left: 60 },
    xAxis: { type: "category", data: raw.map((d: any) => d.trade_date?.slice(5) ?? ""), axisLabel: { fontSize: 10 } },
    yAxis: { type: "value", axisLabel: { fontSize: 10, formatter: (v: number) => (v / 1e8).toFixed(0) + "亿" } },
    tooltip: { trigger: "axis" },
    series: [
      { name: "主力净流入", type: "line", data: raw.map((d: any) => d.net_mf_amount ?? 0), smooth: true,
        areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: "rgba(239,83,80,0.3)" }, { offset: 1, color: "rgba(239,83,80,0)" }] } },
        lineStyle: { color: "#ef5350", width: 2 }, itemStyle: { color: "#ef5350" } },
    ],
  }
})
const moneyflowColumns: any = [
  { title: "日期", key: "trade_date", width: 100 },
  { title: "净流入(亿)", key: "net_mf_amount", render: (r: any) => { const v = r.net_mf_amount; return v != null ? (v / 1e8).toFixed(2) : "-" } },
  { title: "超大单买(亿)", key: "buy_elg_amount", render: (r: any) => r.buy_elg_amount != null ? (r.buy_elg_amount / 1e8).toFixed(2) : "-" },
  { title: "超大单卖(亿)", key: "sell_elg_amount", render: (r: any) => r.sell_elg_amount != null ? (r.sell_elg_amount / 1e8).toFixed(2) : "-" },
  { title: "大单买(亿)", key: "buy_lg_amount", render: (r: any) => r.buy_lg_amount != null ? (r.buy_lg_amount / 1e8).toFixed(2) : "-" },
  { title: "大单卖(亿)", key: "sell_lg_amount", render: (r: any) => r.sell_lg_amount != null ? (r.sell_lg_amount / 1e8).toFixed(2) : "-" },
]

// ---- 因子数据 ----
const factorData = computed(() => data.value?.factors?.stk_factor || data.value?.factors?.stk_factor_pro || [])
const factorOption = computed(() => {
  if (!factorData.value.length) return null
  const raw = [...factorData.value].reverse().slice(-60)
  const keys = Object.keys(raw[0] || {}).filter(k => !["ts_code", "trade_date", "id", "created_at", "updated_at"].includes(k) && typeof raw[0][k] === "number")
  if (!keys.length) return null
  return {
    grid: { top: 10, right: 10, bottom: 10, left: 60 },
    xAxis: { type: "category", data: raw.map((d: any) => d.trade_date?.slice(5) ?? ""), axisLabel: { fontSize: 10 } },
    yAxis: { type: "value", axisLabel: { fontSize: 10 } },
    tooltip: { trigger: "axis" },
    legend: { data: keys.slice(0, 5), bottom: 0, textStyle: { fontSize: 10 } },
    series: keys.slice(0, 5).map((k: string, i: number) => ({
      name: k, type: "line", data: raw.map((d: any) => d[k] ?? 0),
      smooth: true, lineStyle: { width: 1.5 }, symbol: "none",
    })),
  }
})

// ---- 股东数据 ----
const holderColumns: any = [
  { title: "股东名称", key: "holder_name", width: 200, ellipsis: { tooltip: true } },
  { title: "持股数", key: "hold_num", width: 100, render: (r: any) => r.hold_num?.toLocaleString() ?? "-" },
  { title: "持股比例(%)", key: "hold_ratio", width: 100, render: (r: any) => r.hold_ratio?.toFixed(2) ?? "-" },
  { title: "报告期", key: "end_date", width: 100 },
]
const holderChartOption = computed(() => {
  const raw = data.value?.shareholders?.holdernumber
  if (!raw?.length) return null
  const items = [...raw].reverse()
  return {
    grid: { top: 10, right: 10, bottom: 10, left: 60 },
    xAxis: { type: "category", data: items.map((d: any) => d.end_date?.slice(0, 7) ?? ""), axisLabel: { fontSize: 10 } },
    yAxis: { type: "value", axisLabel: { fontSize: 10 } },
    tooltip: { trigger: "axis" },
    series: [{ name: "股东人数", type: "line", data: items.map((d: any) => d.holder_num ?? 0), smooth: true, lineStyle: { color: "#ff9800", width: 2 }, areaStyle: { color: "rgba(255,152,0,0.15)" } }],
  }
})

function goBack() { router.back() }

async function load() {
  loading.value = true; error.value = false
  try {
    const result = await marketAPI.getStockFull(tsCode.value)
    if (!result) { error.value = true; return }
    data.value = result
  } catch { error.value = true }
  finally { loading.value = false }
}

watch(tsCode, load)
onMounted(load)
</script>

<template>
  <div class="stock-detail bg-gradient-mesh bg-noise">
    <!-- Header -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <template v-if="data?.basic">
            <h1 class="page-title">{{ data.basic.name || tsCode }} <span style="font-size:14px;font-weight:400;color:var(--n-text-color-3)">{{ tsCode }}</span></h1>
            <p class="page-description">
              <n-tag v-if="data.basic.is_st" type="error" size="small">ST</n-tag>
              <n-tag v-if="data.basic.industry" size="small">{{ data.basic.industry }}</n-tag>
            </p>
          </template>
          <h1 v-else class="page-title">{{ tsCode }}</h1>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="goBack" quaternary><template #icon><SmartIcon name="ArrowLeft" /></template></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
    <!-- Loading -->
    <n-skeleton v-if="loading" :text="true" :repeat="6" style="padding:24px" />

    <!-- Error -->
    <n-result v-else-if="error" status="500" title="加载失败">
      <template #footer><n-button @click="load">重试</n-button></template>
    </n-result>

    <!-- Data -->
    <template v-else-if="data">
      <!-- Quote Bar -->
      <n-card :class="tokens.surface.card" size="small" style="margin-bottom:16px">
        <div class="quote-bar">
          <div class="quote-main">
            <span class="quote-price">{{ data.latest_quote?.close?.toFixed(2) ?? "-" }}</span>
            <span class="quote-pct" :style="{ color: pctColor(data.latest_quote?.pct_chg ?? null) }">
              {{ pctText(data.latest_quote?.pct_chg ?? null) }}
            </span>
          </div>
          <div class="quote-meta">
            <div class="meta-item"><span class="meta-label">开盘</span><span>{{ data.latest_quote?.open?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">最高</span><span style="color:#ef5350">{{ data.latest_quote?.high?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">最低</span><span style="color:#26a69a">{{ data.latest_quote?.low?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">昨收</span><span>{{ data.limit_price?.pre_close?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">涨停</span><span style="color:#ef5350">{{ data.limit_price?.up_limit?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">跌停</span><span style="color:#26a69a">{{ data.limit_price?.down_limit?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">成交额</span><span>{{ data.latest_quote?.amount ? (data.latest_quote.amount / 1e8).toFixed(1) + "亿" : "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">成交量</span><span>{{ data.latest_quote?.vol ? (data.latest_quote.vol / 1e4).toFixed(0) + "万手" : "-" }}</span></div>
          </div>
          <div class="quote-meta" style="margin-top:6px">
            <div class="meta-item"><span class="meta-label">PE(TTM)</span><span>{{ data.latest_basic?.pe?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">PB</span><span>{{ data.latest_basic?.pb?.toFixed(2) ?? "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">总市值</span><span>{{ data.latest_basic?.total_mv ? (data.latest_basic.total_mv / 1e8).toFixed(0) + "亿" : "-" }}</span></div>
            <div class="meta-item"><span class="meta-label">换手率</span><span>{{ data.latest_basic?.turnover_rate?.toFixed(2) ?? "-" }}%</span></div>
          </div>
        </div>
      </n-card>

      <!-- Tabs -->
      <n-card :class="tokens.surface.card">
        <n-tabs v-model:value="activeTab" type="line" animated>
          <!-- 概览 Tab -->
          <n-tab-pane name="overview" tab="概览">
            <n-grid :x-gap="16" :y-gap="16" :cols="2">
              <n-grid-item>
                <n-card title="公司信息" size="small" :bordered="true">
                  <n-descriptions label-placement="left" :column="1" size="small">
                    <n-descriptions-item label="全称">{{ data.basic?.fullname || data.basic?.name || "-" }}</n-descriptions-item>
                    <n-descriptions-item label="代码">{{ tsCode }}</n-descriptions-item>
                    <n-descriptions-item label="行业">{{ data.basic?.industry || "-" }}</n-descriptions-item>
                    <n-descriptions-item label="上市日期">{{ data.basic?.list_date || "-" }}</n-descriptions-item>
                    <n-descriptions-item label="省份">{{ data.basic?.province || "-" }}</n-descriptions-item>
                    <n-descriptions-item label="城市">{{ data.basic?.city || "-" }}</n-descriptions-item>
                    <n-descriptions-item label="网站" v-if="data.basic?.website">{{ data.basic.website }}</n-descriptions-item>
                  </n-descriptions>
                </n-card>
              </n-grid-item>
              <n-grid-item>
                <n-card title="估值指标" size="small" :bordered="true">
                  <n-descriptions label-placement="left" :column="1" size="small">
                    <n-descriptions-item label="PE(TTM)">{{ data.latest_basic?.pe?.toFixed(2) ?? "-" }}</n-descriptions-item>
                    <n-descriptions-item label="PB">{{ data.latest_basic?.pb?.toFixed(2) ?? "-" }}</n-descriptions-item>
                    <n-descriptions-item label="总市值">{{ data.latest_basic?.total_mv ? (data.latest_basic.total_mv / 1e8).toFixed(0) + "亿" : "-" }}</n-descriptions-item>
                    <n-descriptions-item label="流通市值">{{ data.latest_basic?.circ_mv ? (data.latest_basic.circ_mv / 1e8).toFixed(0) + "亿" : "-" }}</n-descriptions-item>
                    <n-descriptions-item label="换手率">{{ data.latest_basic?.turnover_rate?.toFixed(2) ?? "-" }}%</n-descriptions-item>
                    <n-descriptions-item label="量比">{{ data.latest_basic?.volume_ratio?.toFixed(2) ?? "-" }}</n-descriptions-item>
                  </n-descriptions>
                </n-card>
              </n-grid-item>
            </n-grid>
          </n-tab-pane>

          <!-- K线 Tab -->
          <n-tab-pane name="kline" tab="K线">
            <div style="height:500px">
              <VChart v-if="data.quotes.daily.length" :option="klineOption" autoresize style="height:500px" />
              <n-empty v-else description="暂无 K 线数据" style="padding:100px" />
            </div>
          </n-tab-pane>

          <!-- 资金 Tab -->
          <n-tab-pane name="moneyflow" tab="资金">
            <template v-if="data.moneyflow?.length">
              <n-card title="资金流向趋势" size="small" :bordered="true">
                <VChart v-if="moneyflowOption" :option="moneyflowOption" autoresize style="height:300px" />
              </n-card>
              <n-card title="最近 20 日明细" size="small" :bordered="true" style="margin-top:16px">
                <n-dataTable :columns="moneyflowColumns" :data="data.moneyflow.slice(0, 20)" size="small" :bordered="false" max-height="400" />
              </n-card>
            </template>
            <n-empty v-else description="暂无资金流向数据" style="padding:60px" />
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
                  :data="data.financial.indicators" size="small" :bordered="true" max-height="400" />
              </n-card>
            </template>
            <n-empty v-else description="暂无财务数据" style="padding:60px" />
          </n-tab-pane>

          <!-- 股东 Tab -->
          <n-tab-pane name="shareholder" tab="股东">
            <template v-if="data.shareholders?.top10?.length">
              <n-card title="前十大股东" size="small" :bordered="true">
                <n-dataTable :columns="holderColumns" :data="data.shareholders.top10" size="small" :bordered="false" max-height="400" />
              </n-card>
            </template>
            <template v-if="data.shareholders?.holdernumber?.length">
              <n-card title="股东人数变化" size="small" :bordered="true" style="margin-top:16px">
                <VChart v-if="holderChartOption" :option="holderChartOption" autoresize style="height:250px" />
              </n-card>
            </template>
            <n-empty v-if="!data.shareholders?.top10?.length && !data.shareholders?.holdernumber?.length" description="暂无股东数据" style="padding:60px" />
          </n-tab-pane>

          <!-- 因子 Tab -->
          <n-tab-pane name="factor" tab="因子">
            <template v-if="factorData.length">
              <n-card title="技术因子趋势" size="small" :bordered="true">
                <VChart v-if="factorOption" :option="factorOption" autoresize style="height:300px" />
              </n-card>
            </template>
            <n-empty v-else description="暂无因子数据" style="padding:60px" />
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.stock-detail { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.stock-name { font-size: 20px; font-weight: 700; margin: 0; }
.stock-code { font-size: 13px; color: var(--n-text-color-3); font-family: monospace; }
.quote-bar { display: flex; flex-direction: column; gap: 8px; }
.quote-main { display: flex; align-items: baseline; gap: 12px; }
.quote-price { font-size: 32px; font-weight: 700; font-family: monospace; }
.quote-pct { font-size: 20px; font-weight: 600; }
.quote-meta { display: flex; flex-wrap: wrap; gap: 16px; }
.meta-item { display: flex; gap: 4px; font-size: 13px; align-items: baseline; }
.meta-label { color: var(--n-text-color-3); }
</style>
