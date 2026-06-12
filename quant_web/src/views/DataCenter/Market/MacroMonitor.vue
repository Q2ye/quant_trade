<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { NCard, NGrid, NGridItem, NSkeleton, NEmpty, NResult, NButton, NDataTable, useMessage } from "naive-ui"
import request from "@/utils/request"
import { handleResponse } from "@/utils/responseHandler"
import { tokens } from "@/styles/design-tokens"
import SmartIcon from "@/components/common/SmartIcon.vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const message = useMessage()
const loading = ref(true)
const error = ref(false)
const data = ref<Record<string, any[]>>({})

function lineOption(label: string, raw: any[], valKey: string, color: string) {
  if (!raw.length) return {}
  const items = [...raw].reverse()
  return {
    grid: { top: 20, right: 10, bottom: 30, left: 60 },
    xAxis: { type: "category", data: items.map((d: any) => d.end_date?.slice(0, 7) ?? ""), axisLabel: { fontSize: 10, rotate: 45 } },
    yAxis: { type: "value", axisLabel: { fontSize: 10 } },
    tooltip: { trigger: "axis" },
    series: [{ name: label, type: "line", data: items.map((d: any) => d[valKey] ?? 0), smooth: true, lineStyle: { color, width: 2 }, itemStyle: { color }, areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + "33" }, { offset: 1, color: color + "00" }] } } }],
  }
}

const cpiOption = computed(() => lineOption("CPI", data.value.cpi || [], "cpi_yoy", "#ef5350"))
const ppiOption = computed(() => lineOption("PPI", data.value.ppi || [], "ppi_yoy", "#2196f3"))
const gdpOption = computed(() => lineOption("GDP", data.value.gdp || [], "gdp_yoy", "#4caf50"))
const hsgtOption = computed(() => {
  const raw = data.value.hsgt || []
  if (!raw.length) return {}
  const items = [...raw].reverse()
  let cum = 0
  const cumData = items.map((d: any) => { cum += d.net_inflow ?? 0; return (cum / 1e8).toFixed(0) })
  return {
    grid: { top: 20, right: 10, bottom: 30, left: 60 },
    xAxis: { type: "category", data: items.map((d: any) => d.trade_date?.slice(5) ?? ""), axisLabel: { fontSize: 9 } },
    yAxis: { type: "value", axisLabel: { fontSize: 10, formatter: (v: number) => v + "亿" } },
    tooltip: { trigger: "axis" },
    series: [{ name: "累计净流入", type: "line", data: cumData, smooth: true, lineStyle: { color: "#ff9800", width: 2 }, areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(255,152,0,0.3)" }, { offset: 1, color: "rgba(255,152,0,0)" }] } } }],
  }
})

async function load() {
  loading.value = true; error.value = false
  try {
    const [cpi, ppi, gdp, hsgt] = await Promise.all([
      request.get("/quantTrade/market/macro/cpi?limit=24").then(handleResponse).then((d: any) => d.data).catch(() => []),
      request.get("/quantTrade/market/macro/ppi?limit=24").then(handleResponse).then((d: any) => d.data).catch(() => []),
      request.get("/quantTrade/market/macro/gdp?limit=20").then(handleResponse).then((d: any) => d.data).catch(() => []),
      request.get("/quantTrade/market/moneyflow/hsgt?days=120").then(handleResponse).then((d: any) => d.data).catch(() => []),
    ])
    data.value = { cpi, ppi, gdp, hsgt }
  } catch { error.value = true }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="macro-page bg-gradient-mesh bg-noise">
    <div class="page-header"><div class="header-content"><div class="title-section"><h1 class="page-title">宏观经济</h1></div><div class="header-actions"><n-button class="action-btn" @click="() => $router.back()" quaternary><template #icon><SmartIcon name="ArrowLeft" /></template></n-button></div></div></div>

    <div class="main-content">
    <n-skeleton v-if="loading" :text="true" :repeat="4" />
    <n-result v-else-if="error" status="500"><template #footer><n-button @click="load">重试</n-button></template></n-result>

    <template v-else>
      <n-grid :x-gap="16" :y-gap="16" :cols="2" responsive="screen">
        <n-grid-item>
          <n-card :class="tokens.surface.card" title="CPI 居民消费价格 (同比%)" size="small">
            <VChart v-if="data.cpi?.length" :option="cpiOption" autoresize style="height:250px" />
            <n-empty v-else description="暂无" style="padding:60px" />
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card :class="tokens.surface.card" title="PPI 工业出厂价格 (同比%)" size="small">
            <VChart v-if="data.ppi?.length" :option="ppiOption" autoresize style="height:250px" />
            <n-empty v-else description="暂无" style="padding:60px" />
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card :class="tokens.surface.card" title="GDP 国内生产总值 (同比%)" size="small">
            <VChart v-if="data.gdp?.length" :option="gdpOption" autoresize style="height:250px" />
            <n-empty v-else description="暂无" style="padding:60px" />
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card :class="tokens.surface.card" title="北向资金累计净流入" size="small">
            <VChart v-if="data.hsgt?.length" :option="hsgtOption" autoresize style="height:250px" />
            <n-empty v-else description="暂无" style="padding:60px" />
          </n-card>
        </n-grid-item>
      </n-grid>
    </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.macro-page { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.page-header { padding: 16px 0; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; }
</style>
