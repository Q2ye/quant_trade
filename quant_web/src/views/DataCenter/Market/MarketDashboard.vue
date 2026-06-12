<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { NCard, NGrid, NGridItem, NSkeleton, NEmpty, NResult, NButton, NTag, NSpace, NDataTable, useMessage } from "naive-ui"
import type { DataTableColumns } from "naive-ui"
import marketAPI from "@/api/market"
import type { DashboardOverview, TopVolumeItem, TopMoneyflowItem } from "@/types/entities/market"
import SmartIcon from "@/components/common/SmartIcon.vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { LineChart, BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent])

const router = useRouter()
const message = useMessage()
const loading = ref(true); const error = ref(false)
const data = ref<DashboardOverview | null>(null)
const expandedIndex = ref("")
const indexHistory = ref<Record<string, any[]>>({})
const indexVals = ref<Record<string, any[]>>({})

const pctColor = (v: number | null) => v == null ? "" : v > 0 ? "#ef5350" : "#26a69a"
const pctText = (v: number | null) => v == null ? "-" : (v > 0 ? "+" : "") + v.toFixed(2) + "%"
const amtText = (v: number | null) => v == null ? "-" : (v / 1e8).toFixed(1) + "亿"
const mvText = (v: number | null) => v == null ? "-" : (v / 1e8).toFixed(0) + "亿"

// ---- breadth ----
const dataDateText = computed(() => {
  const d = data.value?.data_date
  if (!d) return ""
  const dt = new Date(d)
  const dayNames = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")} ${dayNames[dt.getDay()]}`
})

const upRatio = computed(() => {
  if (!data.value) return 0
  const t = data.value.market_breadth.total || 1
  return (data.value.market_breadth.up / t * 100)
})

// ---- index accordion charts ----
const sparklineOption = computed(() => {
  const raw = indexHistory.value[expandedIndex.value]
  if (!raw?.length) return null
  const vals = raw.map((d: any) => d.close ?? 0)
  const vMin = Math.min(...vals), vMax = Math.max(...vals)
  const pad = Math.max((vMax - vMin) * 0.05, 1)
  const items = [...raw].reverse()
  return {
    grid: { top: 5, right: 5, bottom: 15, left: 42 },
    xAxis: { type: "category", data: items.map((d: any) => d.trade_date?.slice(5) ?? ""), axisLabel: { fontSize: 9, rotate: 30 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: "value", min: vMin - pad, max: vMax + pad, splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } }, axisLabel: { fontSize: 10 } },
    tooltip: { trigger: "axis" },
    series: [{ type: "line", data: items.map((d: any) => d.close ?? 0), smooth: true, lineStyle: { color: "#ef5350", width: 1.5 }, areaStyle: { color: "rgba(239,83,80,0.1)" }, symbol: "none" }],
  }
})

const pePbOption = computed(() => {
  const raw = indexVals.value[expandedIndex.value]
  if (!raw?.length) return null
  const peVals = raw.map((d: any) => d.pe ?? 0), pbVals = raw.map((d: any) => d.pb ?? 0)
  const peMin = Math.min(...peVals), peMax = Math.max(...peVals)
  const pbMin = Math.min(...pbVals), pbMax = Math.max(...pbVals)
  const pePad = Math.max((peMax - peMin) * 0.05, 0.5)
  const pbPad = Math.max((pbMax - pbMin) * 0.05, 0.1)
  const items = [...raw].reverse()
  return {
    grid: { top: 5, right: 42, bottom: 15, left: 42 },
    xAxis: { type: "category", data: items.map((d: any) => d.trade_date?.slice(5) ?? ""), axisLabel: { fontSize: 9, rotate: 30 }, axisLine: { show: false } },
    yAxis: [
      { type: "value", name: "PE", min: peMin - pePad, max: peMax + pePad, splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } }, axisLabel: { fontSize: 10 } },
      { type: "value", name: "PB", min: pbMin - pbPad, max: pbMax + pbPad, axisLabel: { fontSize: 10 } },
    ],
    tooltip: { trigger: "axis" },
    series: [
      { name: "PE", type: "line", yAxisIndex: 0, data: items.map((d: any) => d.pe ?? 0), smooth: true, lineStyle: { color: "#ef5350", width: 1.5 }, symbol: "none" },
      { name: "PB", type: "line", yAxisIndex: 1, data: items.map((d: any) => d.pb ?? 0), smooth: true, lineStyle: { color: "#2196f3", width: 1.5 }, symbol: "none" },
    ],
  }
})

async function toggleIndex(code: string) {
  if (expandedIndex.value === code) { expandedIndex.value = ""; return }
  expandedIndex.value = code
  if (!indexHistory.value[code]) {
    try {
      const [hist, val] = await Promise.all([
        marketAPI.getIndexHistory(code, 60),
        marketAPI.getIndexValuation(code, 60),
      ])
      indexHistory.value[code] = hist || []
      indexVals.value[code] = val || []
    } catch { indexHistory.value[code] = []; indexVals.value[code] = [] }
  }
}

// ---- TOP10 columns ----
const volumeCols: DataTableColumns<TopVolumeItem> = [
  { title: "股票", key: "name", width: 80, ellipsis: { tooltip: true } },
  { title: "行业", key: "industry", width: 65, ellipsis: { tooltip: true } },
  { title: "涨跌", key: "pct_chg", width: 65, render: (r) => h("span", { style: { color: pctColor(r.pct_chg) } }, pctText(r.pct_chg)) },
  { title: "成交额", key: "amount", width: 75, render: (r) => amtText(r.amount) },
  { title: "市值", key: "total_mv", width: 75, render: (r) => r.total_mv ? mvText(r.total_mv) : "-" },
  { title: "换手", key: "turnover_rate", width: 60, render: (r) => r.turnover_rate ? r.turnover_rate.toFixed(1) + "%" : "-" },
]

const flowCols: DataTableColumns<TopMoneyflowItem> = [
  { title: "股票", key: "name", width: 80, ellipsis: { tooltip: true } },
  { title: "涨跌", key: "pct_chg", width: 65, render: (r) => h("span", { style: { color: pctColor(r.pct_chg) } }, pctText(r.pct_chg)) },
  { title: "净流入", key: "net_mf_amount", width: 75, render: (r) => { const v = r.net_mf_amount; return v == null ? "-" : h("span", { style: { color: v >= 0 ? "#ef5350" : "#26a69a" } }, amtText(v)) } },
  { title: "超大单", key: "elg", width: 75, render: (r) => amtText((r.buy_elg_amount ?? 0) - (r.sell_elg_amount ?? 0)) },
  { title: "大单", key: "lg", width: 75, render: (r) => amtText((r.buy_lg_amount ?? 0) - (r.sell_lg_amount ?? 0)) },
]

// ---- HSGT bars ----
const hBarSH = computed(() => {
  const hsgt = data.value?.hsgt_flow
  if (!hsgt) return 0
  const sh = Math.abs(hsgt.sh_inflow ?? 0)
  const sz = Math.abs(hsgt.sz_inflow ?? 0)
  const total = sh + sz
  return total > 0 ? (sh / total * 100) : 50
})
const hBarSZ = computed(() => 100 - hBarSH.value)

// ---- heatmap chart ----
const heatmapOption = computed(() => ({
  grid: { top: 5, right: 10, bottom: 20, left: 40 },
  xAxis: { show: false, type: "category", data: data.value?.industry_heatmap.map(i => i.name) ?? [] },
  yAxis: { show: true, axisLabel: { fontSize: 10 }, splitLine: { show: false } },
  tooltip: { trigger: "axis" },
  series: [{
    type: "bar", barMaxWidth: 12, barCategoryGap: "30%",
    data: data.value?.industry_heatmap.map(i => i.pct_chg ?? 0) ?? [],
    itemStyle: { color: (p: any) => p.value >= 0 ? "#ef5350" : "#26a69a", borderRadius: 2 },
  }],
}))

function nav(p: string) { router.push(p) }
async function load() { loading.value = true; error.value = false; try { data.value = await marketAPI.getDashboardOverview() } catch { error.value = true } finally { loading.value = false } }
onMounted(load)
</script>

<template>
  <div class="market-dashboard bg-gradient-mesh bg-noise">
    <!-- Page Header (global pattern: page-header > header-content > title-section + header-actions) -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场总览</h1>
          <p class="page-description" v-if="data">数据日期：{{ dataDateText }} ｜ {{ data.market_breadth.total }} 只股票有行情</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="load" quaternary><template #icon><SmartIcon name="Refresh" /></template></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <n-grid v-if="loading" :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
        <n-grid-item v-for="i in 4" :key="i"><n-card><n-skeleton :text="true" :repeat="3" /></n-card></n-grid-item>
      </n-grid>
      <n-result v-else-if="error" status="500" title="加载失败"><template #footer><n-button @click="load">重试</n-button></template></n-result>

      <template v-else-if="data">
      <!-- Row 1: 核心指数(3) + 涨跌统计(1) + 北向(1) -->
      <n-grid :x-gap="16" :y-gap="16" :cols="5" responsive="screen" class="row-equal">
        <n-grid-item :span="3">
          <n-card title="核心指数" size="small" class="full-height-card">
            <div class="index-grid">
              <div v-for="idx in data.indices" :key="idx.code" class="idx-item"
                   :class="{ active: expandedIndex === idx.code }"
                   @click="toggleIndex(idx.code)">
                <span class="idx-name">{{ idx.name?.slice(0, 4) || idx.code }}</span>
                <span class="idx-close">{{ idx.close?.toFixed(2) ?? "-" }}</span>
                <span class="idx-pct" :style="{ color: pctColor(idx.pct_chg) }">{{ pctText(idx.pct_chg) }}</span>
              </div>
            </div>
            <!-- Expanded detail -->
            <template v-if="expandedIndex">
              <n-grid :x-gap="12" style="margin-top:12px;border-top:1px solid var(--n-border-color);padding-top:12px" :cols="2">
                <n-grid-item>
                  <VChart v-if="sparklineOption" :option="sparklineOption" autoresize style="height:180px" />
                  <n-skeleton v-else :text="true" height="180px" />
                  <div style="text-align:center;font-size:12px;color:var(--n-text-color-3);margin-top:2px">最近60日走势</div>
                </n-grid-item>
                <n-grid-item>
                  <VChart v-if="pePbOption" :option="pePbOption" autoresize style="height:180px" />
                  <n-skeleton v-else :text="true" height="180px" />
                  <div style="text-align:center;font-size:12px;color:var(--n-text-color-3);margin-top:2px">PE/PB 趋势</div>
                </n-grid-item>
              </n-grid>
              <div style="text-align:center;margin-top:6px;font-size:12px">
                <n-button size="tiny" quaternary @click.stop="nav('/market/index/' + expandedIndex)">查看指数详情 →</n-button>
              </div>
            </template>
          </n-card>
        </n-grid-item>

        <!-- 涨跌统计 -->
        <n-grid-item>
          <n-card title="涨跌统计" size="small" class="full-height-card card-body-center">
            <div class="breadth">
              <div class="breadth-bar"><div class="bar-up" :style="{ width: upRatio + '%' }" /><div class="bar-down" :style="{ width: (100 - upRatio) + '%' }" /></div>
              <div class="b-stat-row">
                <div class="b-stat" style="cursor:pointer" @click="nav('/market/limit-events')">
                  <span class="b-stat-num up">{{ data.market_breadth.up.toLocaleString() }}</span>
                  <span class="b-stat-label">上涨</span>
                  <span class="b-stat-pct up">{{ upRatio.toFixed(1) }}%</span>
                </div>
                <div class="b-stat" style="cursor:pointer" @click="nav('/market/limit-events')">
                  <span class="b-stat-num down">{{ data.market_breadth.down.toLocaleString() }}</span>
                  <span class="b-stat-label">下跌</span>
                  <span class="b-stat-pct down">{{ (100 - upRatio).toFixed(1) }}%</span>
                </div>
                <div class="b-stat">
                  <span class="b-stat-num">{{ data.market_breadth.flat.toLocaleString() }}</span>
                  <span class="b-stat-label">平盘</span>
                  <span class="b-stat-pct">{{ data.market_breadth.total ? (data.market_breadth.flat / data.market_breadth.total * 100).toFixed(1) : "0" }}%</span>
                </div>
              </div>
              <n-space style="margin-top:12px" justify="center">
                <n-tag type="error" size="small" style="cursor:pointer" @click="nav('/market/limit-events')">涨停 {{ data.market_breadth.limit_up }}</n-tag>
                <n-tag type="info" size="small" style="cursor:pointer" @click="nav('/market/limit-events')">跌停 {{ data.market_breadth.limit_down }}</n-tag>
              </n-space>
            </div>
          </n-card>
        </n-grid-item>

        <!-- 北向资金 -->
        <n-grid-item>
          <n-card title="北向资金" size="small" class="full-height-card card-body-center">
            <template v-if="data.hsgt_flow">
              <div class="hsgt">
                <div class="h-dir">{{ (data.hsgt_flow.net_inflow ?? 0) >= 0 ? '↗' : '↘' }}</div>
                <div class="h-main"><span class="h-val" :class="{ up: (data.hsgt_flow.net_inflow ?? 0) > 0, down: (data.hsgt_flow.net_inflow ?? 0) < 0 }">{{ Math.abs(data.hsgt_flow.net_inflow ?? 0) > 0 ? (Math.abs(data.hsgt_flow.net_inflow!) / 1e8).toFixed(1) : "0" }}</span><span class="h-unit">亿</span></div>
                <div class="h-bar-wrap">
                  <div class="h-bar-item">
                    <span class="h-bar-label">沪</span>
                    <div class="h-bar-track"><div class="h-bar-fill sh" :style="{ width: hBarSH + '%' }" /></div>
                    <span class="h-bar-val">{{ (data.hsgt_flow.sh_inflow ?? 0) > 0 ? "+" : "" }}{{ data.hsgt_flow.sh_inflow ? (data.hsgt_flow.sh_inflow / 1e8).toFixed(1) : "0" }}亿</span>
                  </div>
                  <div class="h-bar-item">
                    <span class="h-bar-label">深</span>
                    <div class="h-bar-track"><div class="h-bar-fill sz" :style="{ width: hBarSZ + '%' }" /></div>
                    <span class="h-bar-val">{{ (data.hsgt_flow.sz_inflow ?? 0) > 0 ? "+" : "" }}{{ data.hsgt_flow.sz_inflow ? (data.hsgt_flow.sz_inflow / 1e8).toFixed(1) : "0" }}亿</span>
                  </div>
                </div>
              </div>
            </template>
            <n-empty v-else description="暂无" size="small" />
          </n-card>
        </n-grid-item>
      </n-grid>

      <!-- Row 2: 行业热力图 -->
      <n-card title="申万一级行业" size="small" style="margin-top:16px">
        <template #header-extra><n-button size="tiny" quaternary @click="nav('/market/industry')">详情 →</n-button></template>
        <div style="height:200px">
          <VChart v-if="data.industry_heatmap.length" :option="heatmapOption" autoresize style="height:200px" />
          <n-empty v-else description="暂无" style="padding:40px" />
        </div>
      </n-card>

      <!-- Row 3: TOP10 -->
      <n-grid :x-gap="16" :y-gap="16" :cols="2" style="margin-top:16px">
        <n-grid-item>
          <n-card title="成交额 TOP10" size="small">
            <template #header-extra><n-button size="tiny" quaternary @click="nav('/market/screener')">筛选 →</n-button></template>
            <n-dataTable :columns="volumeCols" :data="data.top_volume" size="small" :bordered="false" max-height="340"
              :row-props="(row: TopVolumeItem) => ({ style: 'cursor:pointer', onClick: () => nav('/market/stock/' + row.ts_code) })" />
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="资金流入 TOP10" size="small">
            <template #header-extra><n-button size="tiny" quaternary @click="nav('/market/money-flow')">详情 →</n-button></template>
            <n-dataTable :columns="flowCols" :data="data.top_moneyflow" size="small" :bordered="false" max-height="340"
              :row-props="(row: TopMoneyflowItem) => ({ style: 'cursor:pointer', onClick: () => nav('/market/stock/' + row.ts_code) })" />
          </n-card>
        </n-grid-item>
      </n-grid>

      <!-- Row 4: 快捷入口 -->
      <n-card title="快捷入口" size="small" style="margin-top:16px">
        <n-space>
          <n-button secondary @click="nav('/market/screener')">股票筛选器</n-button>
          <n-button secondary @click="nav('/market/financial')">财务数据中心</n-button>
          <n-button secondary @click="nav('/market/macro')">宏观经济</n-button>
          <n-button secondary @click="nav('/market/etf-market')">ETF 市场</n-button>
        </n-space>
      </n-card>
    </template>
  </div>
  </div>
</template>

<style lang="scss" scoped>
.market-dashboard { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.index-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.idx-item { display: flex; flex-direction: column; align-items: center; padding: 8px 4px; border-radius: 8px; background: rgba(255,255,255,0.03); cursor: pointer; transition: all .2s;
  &:hover { background: rgba(255,255,255,0.08); }
  &.active { background: rgba(239,83,80,0.1); border: 1px solid rgba(239,83,80,0.3); }
  .idx-name { font-size: 12px; color: var(--n-text-color-3); }
  .idx-close { font-size: 15px; font-weight: 600; font-family: monospace; margin: 2px 0; }
  .idx-pct { font-size: 13px; font-weight: 600; }
}
.breadth-bar { display: flex; height: 6px; border-radius: 3px; overflow: hidden; margin: 8px 0 16px; }
.bar-up { background: #ef5350; transition: width .3s; }
.bar-down { background: #26a69a; transition: width .3s; }
.b-stat-row { display: flex; justify-content: space-around; }
.b-stat { display: flex; flex-direction: column; align-items: center; gap: 5px; padding: 4px 8px; border-radius: 6px; transition: background .15s;
  &:hover { background: rgba(255,255,255,0.04); }
  .b-stat-num { font-size: 18px; font-weight: 700; font-family: monospace;
    &.up { color: #ef5350; } &.down { color: #26a69a; }
  }
  .b-stat-label { font-size: 11px; color: var(--n-text-color-3); }
  .b-stat-pct { font-size: 12px; font-weight: 500;
    &.up { color: #ef5350; } &.down { color: #26a69a; }
  }
}
.hsgt {
  .h-dir { text-align: center; font-size: 22px; line-height: 1; margin-bottom: 2px; }
  .h-main { text-align: center; margin: 6px 0 16px; }
  .h-val { font-size: 28px; font-weight: 700; font-family: monospace; color: #ff9800;
    &.up { color: #ef5350; } &.down { color: #26a69a; }
  }
  .h-unit { font-size: 14px; color: var(--n-text-color-3); margin-left: 4px; }
  .h-bar-wrap { display: flex; flex-direction: column; gap: 8px; }
  .h-bar-item { display: flex; align-items: center; gap: 6px; font-size: 12px; }
  .h-bar-label { width: 18px; color: var(--n-text-color-3); text-align: center; }
  .h-bar-track { flex: 1; height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
  .h-bar-fill { height: 100%; border-radius: 2px; transition: width .3s;
    &.sh { background: #ef5350; } &.sz { background: #2196f3; }
  }
  .h-bar-val { width: 72px; text-align: right; color: var(--n-text-color-2); font-family: monospace; }
}
.row-equal { align-items: stretch; }
.full-height-card { height: 100%; }
.card-body-center {
  :deep(.n-card__content) { display: flex; align-items: center; min-height: 0; }
}
</style>
