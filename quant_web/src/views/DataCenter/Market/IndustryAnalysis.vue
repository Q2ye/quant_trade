<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { NCard, NDataTable, NSkeleton, NEmpty, NResult, NButton, NSelect, NTag, NSpace, useMessage } from "naive-ui"
import type { DataTableColumns } from "naive-ui"
import marketAPI from "@/api/market"
import type { IndustryNode, IndustryHeatmapItem } from "@/types/entities/market"
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
const heatmap = ref<IndustryHeatmapItem[]>([])
const members = ref<any[]>([])
const selectedName = ref("")

const heatmapOption = computed(() => ({
  grid: { top: 5, right: 10, bottom: 60, left: 50 },
  xAxis: { type: "category", data: heatmap.value.map(i => i.name), axisLabel: { rotate: 90, fontSize: 9 } },
  yAxis: { type: "value", axisLabel: { fontSize: 10 } },
  tooltip: { trigger: "axis" },
  series: [{
    type: "bar", barMaxWidth: 16, barCategoryGap: "25%",
    data: heatmap.value.map(i => i.pct_chg ?? 0),
    itemStyle: { color: (p: any) => p.value >= 0 ? "#ef5350" : "#26a69a", borderRadius: 2 },
  }],
}))

const memberColumns: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 100 },
  { title: "简称", key: "name", width: 90 },
  { title: "最新价", key: "close", width: 80, render: (r) => r.close?.toFixed(2) ?? "-" },
  { title: "涨跌幅", key: "pct_chg", width: 80, render: (r) => h("span", { style: { color: (r.pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } }, r.pct_chg != null ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%" : "-") },
  { title: "成交额(亿)", key: "amount", render: (r) => r.amount ? (r.amount / 1e8).toFixed(1) : "-" },
]

async function load() {
  loading.value = true; error.value = false
  try { heatmap.value = await marketAPI.getIndustryHeatmap() }
  catch { error.value = true; message.error("行业数据加载失败") }
  finally { loading.value = false }
}

async function selectIndustry(item: IndustryHeatmapItem) {
  selectedName.value = item.name
  try {
    const detail = await marketAPI.getIndustryDetail(item.code)
    members.value = detail.members
  } catch { members.value = [] }
}

onMounted(load)
</script>

<template>
  <div class="industry-page bg-gradient-mesh bg-noise">
    <div class="page-header"><div class="header-content"><div class="title-section"><h1 class="page-title">行业分析</h1></div><div class="header-actions"><n-button class="action-btn" @click="() => $router.back()" quaternary><template #icon><SmartIcon name="ArrowLeft" /></template></n-button></div></div></div>

    <div class="main-content">
    <n-skeleton v-if="loading" :text="true" :repeat="4" />
    <n-result v-else-if="error" status="500" title="加载失败"><template #footer><n-button @click="load">重试</n-button></template></n-result>

    <template v-else>
      <n-card :class="tokens.surface.card" title="申万一级行业涨跌幅" size="small">
        <div style="height:300px">
          <VChart v-if="heatmap.length" :option="heatmapOption" autoresize style="height:300px" />
          <n-empty v-else description="暂无数据" style="padding:60px" />
        </div>
      </n-card>

      <n-card :class="tokens.surface.card" title="点击行业查看成分股" size="small" style="margin-top:16px">
        <div class="tag-cloud">
          <n-tag v-for="item in heatmap" :key="item.code" size="small"
            :type="selectedName === item.name ? 'primary' : 'default'"
            style="cursor:pointer;margin:2px" @click="selectIndustry(item)">
            {{ item.name }} {{ (item.pct_chg != null) ? (item.pct_chg > 0 ? "+" : "") + item.pct_chg.toFixed(1) + "%" : "" }}
          </n-tag>
        </div>
      </n-card>

      <n-card v-if="members.length" :class="tokens.surface.card" :title="selectedName + ' — 成分股'" size="small" style="margin-top:16px">
        <n-dataTable :columns="memberColumns" :data="members" size="small" :bordered="false" max-height="500"
          :row-props="(row: any) => ({ style: 'cursor:pointer', onClick: () => router.push('/market/stock/' + row.ts_code) })" />
      </n-card>
    </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.industry-page { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.page-header { padding: 16px 0; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; }
.tag-cloud { display: flex; flex-wrap: wrap; gap: 2px; }
</style>
