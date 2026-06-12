<script setup lang="ts">
import { h, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { NCard, NDataTable, NSkeleton, NEmpty, NResult, NButton, NTag, useMessage } from "naive-ui"
import type { DataTableColumns } from "naive-ui"
import marketAPI from "@/api/market"
import { tokens } from "@/styles/design-tokens"
import SmartIcon from "@/components/common/SmartIcon.vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const router = useRouter()
const message = useMessage()
const loading = ref(true)
const error = ref(false)
const etfList = ref<any[]>([])
const moneyflow = ref<any[]>([])

const flowOption = ref({})

const columns: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 100 },
  { title: "简称", key: "name", width: 90 },
  { title: "最新价", key: "close", width: 80, render: (r) => r.close?.toFixed(3) ?? "-" },
  { title: "涨跌幅", key: "pct_chg", width: 80, render: (r) => h("span", { style: { color: (r.pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } }, r.pct_chg != null ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%" : "-") },
  { title: "成交额(亿)", key: "amount", render: (r) => r.amount ? (r.amount / 1e8).toFixed(2) : "-" },
]

async function load() {
  loading.value = true; error.value = false
  try {
    const [etfs, flow] = await Promise.all([
      marketAPI.getScreener({ market: ["SH"], limit: 100, sort_by: "amount", sort_dir: "desc" }),
      marketAPI.getHsgtHistory(7),
    ])
    etfList.value = etfs.stocks.filter((s: any) => s.ts_code?.startsWith("51") || s.ts_code?.startsWith("58") || s.ts_code?.startsWith("56"))
    moneyflow.value = flow
    if (flow.length) {
      const items = [...flow].reverse().slice(-7)
      flowOption.value = {
        grid: { top: 10, right: 10, bottom: 10, left: 50 },
        xAxis: { type: "category", data: items.map((d: any) => d.trade_date?.slice(5) ?? ""), axisLabel: { fontSize: 10 } },
        yAxis: { type: "value", axisLabel: { fontSize: 10, formatter: (v: number) => (v / 1e8).toFixed(0) + "亿" } },
        tooltip: { trigger: "axis" },
        series: [{ name: "北向净流入", type: "bar", data: items.map((d: any) => d.net_inflow ?? 0),
          itemStyle: { color: (p: any) => p.value >= 0 ? "#ef5350" : "#26a69a", borderRadius: 2 }, barMaxWidth: 24 }],
      }
    }
  } catch { error.value = true }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="etf-page bg-gradient-mesh bg-noise">
    <div class="page-header"><div class="header-content"><div class="title-section"><h1 class="page-title">ETF 市场</h1></div><div class="header-actions"><n-button class="action-btn" @click="() => $router.back()" quaternary><template #icon><SmartIcon name="ArrowLeft" /></template></n-button></div></div></div>

    <div class="main-content">
    <n-skeleton v-if="loading" :text="true" :repeat="4" />
    <n-result v-else-if="error" status="500"><template #footer><n-button @click="load">重试</n-button></template></n-result>

    <template v-else>
      <n-card :class="tokens.surface.card" title="北向资金（近7日）" size="small" style="margin-bottom:16px">
        <VChart v-if="moneyflow.length" :option="flowOption" autoresize style="height:200px" />
        <n-empty v-else description="暂无" style="padding:40px" />
      </n-card>

      <n-card :class="tokens.surface.card" title="沪市 ETF 列表" size="small">
        <n-empty v-if="!etfList.length" description="暂无数据" />
        <n-dataTable v-else :columns="columns" :data="etfList" size="small" :bordered="false" max-height="500"
          :row-props="(row: any) => ({ style: 'cursor:pointer', onClick: () => router.push('/market/etf/' + row.ts_code) })" />
      </n-card>
    </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.etf-page { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.page-header { padding: 16px 0; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; }
</style>
