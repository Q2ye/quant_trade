<script setup lang="ts">
import { h, onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { NCard, NGrid, NGridItem, NInputNumber, NSelect, NButton, NDataTable, NSkeleton, NEmpty, NResult, NSpace, useMessage } from "naive-ui"
import type { DataTableColumns } from "naive-ui"
import marketAPI from "@/api/market"
import type { ScreenerStockItem } from "@/types/entities/market"
import { tokens } from "@/styles/design-tokens"
import SmartIcon from "@/components/common/SmartIcon.vue"

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const error = ref(false)
const stocks = ref<ScreenerStockItem[]>([])
const total = ref(0)
const page = ref(1)

const filters = reactive({
  market: [] as string[], industry: [] as string[],
  pe_min: null as number | null, pe_max: null as number | null,
  pb_min: null as number | null, pb_max: null as number | null,
  pct_chg_min: null as number | null, pct_chg_max: null as number | null,
  turnover_min: null as number | null,
  roe_min: null as number | null,
  sort_by: "pct_chg", sort_dir: "desc",
})

const marketOpts = [{ label: "沪市 (SH)", value: "SH" }, { label: "深市 (SZ)", value: "SZ" }]
const sortOpts = [
  { label: "涨跌幅", value: "pct_chg" }, { label: "PE", value: "pe" },
  { label: "PB", value: "pb" }, { label: "市值", value: "total_mv" },
  { label: "换手率", value: "turnover_rate" }, { label: "成交额", value: "amount" },
  { label: "ROE", value: "roe" },
]

const columns: DataTableColumns<ScreenerStockItem> = [
  { title: "代码", key: "ts_code", width: 100, fixed: "left" },
  { title: "简称", key: "name", width: 90, fixed: "left" },
  { title: "最新价", key: "close", width: 70, render: (r) => r.close?.toFixed(2) ?? "-" },
  { title: "涨跌幅", key: "pct_chg", width: 80, render: (r) => h("span", { style: { color: (r.pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } }, r.pct_chg != null ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%" : "-") },
  { title: "PE", key: "pe", width: 70, render: (r) => r.pe?.toFixed(1) ?? "-" },
  { title: "PB", key: "pb", width: 70, render: (r) => r.pb?.toFixed(2) ?? "-" },
  { title: "市值(亿)", key: "total_mv", width: 90, render: (r) => r.total_mv ? (r.total_mv / 1e8).toFixed(0) : "-" },
  { title: "换手%", key: "turnover_rate", width: 70, render: (r) => r.turnover_rate?.toFixed(2) ?? "-" },
  { title: "ROE", key: "roe", width: 70, render: (r) => r.roe?.toFixed(1) ?? "-" },
  { title: "行业", key: "industry", width: 80 },
]

let timer: ReturnType<typeof setTimeout> | null = null
async function search(p?: number) {
  loading.value = true; error.value = false
  const pg = p || page.value
  try {
    const result = await marketAPI.getScreener({ ...filters, page: pg, limit: 50 })
    stocks.value = result.stocks; total.value = result.total; page.value = pg
  } catch { error.value = true; message.error("筛选失败") }
  finally { loading.value = false }
}

function onFilterChange() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => search(1), 500)
}

function reset() {
  filters.market = []; filters.industry = []; filters.pe_min = null; filters.pe_max = null
  filters.pb_min = null; filters.pb_max = null; filters.pct_chg_min = null; filters.pct_chg_max = null
  filters.turnover_min = null; filters.roe_min = null
}

onMounted(() => search())
</script>

<template>
  <div class="screener-page bg-gradient-mesh bg-noise">
    <div class="page-header"><div class="header-content"><div class="title-section"><h1 class="page-title">股票筛选器</h1></div><div class="header-actions"><n-button class="action-btn" @click="() => $router.back()" quaternary><template #icon><SmartIcon name="ArrowLeft" /></template></n-button></div></div></div>

    <div class="main-content">
    <n-grid :x-gap="16" :y-gap="12" :cols="6" style="margin-bottom:16px">
      <n-grid-item><n-select v-model:value="filters.market" multiple placeholder="市场" :options="marketOpts" clearable @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-input-number v-model:value="filters.pe_min" placeholder="PE低" :min="0" @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-input-number v-model:value="filters.pe_max" placeholder="PE高" :min="0" @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-input-number v-model:value="filters.pb_min" placeholder="PB低" :min="0" @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-input-number v-model:value="filters.pb_max" placeholder="PB高" :min="0" @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-input-number v-model:value="filters.turnover_min" placeholder="换手率>" :min="0" @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-input-number v-model:value="filters.roe_min" placeholder="ROE>" @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-select v-model:value="filters.sort_by" :options="sortOpts" @update:value="onFilterChange" /></n-grid-item>
      <n-grid-item><n-button @click="reset" size="small" quaternary>重置</n-button><n-button type="primary" size="small" @click="search()" style="margin-left:8px">搜索</n-button></n-grid-item>
    </n-grid>

    <n-skeleton v-if="loading" :text="true" :repeat="6" />
    <n-result v-else-if="error" status="500" title="加载失败"><template #footer><n-button @click="search()">重试</n-button></template></n-result>
    <n-empty v-else-if="!stocks.length" description="无匹配结果" />

    <n-card v-else :class="tokens.surface.card">
      <n-dataTable :columns="columns" :data="stocks" size="small" :bordered="false" max-height="calc(100vh - 320px)"
        :row-props="(row: ScreenerStockItem) => ({ style: 'cursor:pointer', onClick: () => router.push('/market/stock/' + row.ts_code) })"
        :pagination="{ page: page, pageSize: 50, itemCount: total, onChange: (p: number) => search(p) }" />
    </n-card>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.screener-page { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.page-header { padding: 16px 0; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; }
</style>
