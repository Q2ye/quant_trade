<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { NCard, NDataTable, NSkeleton, NEmpty, NResult, NButton, NInput, NTag, NSpace, useMessage } from "naive-ui"
import type { DataTableColumns } from "naive-ui"
import marketAPI from "@/api/market"
import { tokens } from "@/styles/design-tokens"
import SmartIcon from "@/components/common/SmartIcon.vue"

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const error = ref(false)
const data = ref<any[]>([])
const codeInput = ref("")

const columns: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 100, fixed: "left" },
  { title: "简称", key: "name", width: 90, fixed: "left" },
  { title: "报告期", key: "end_date", width: 100 },
  { title: "ROE(%)", key: "roe", width: 80, render: (r) => r.roe?.toFixed(1) ?? "-" },
  { title: "ROA(%)", key: "roa", width: 80, render: (r) => r.roa?.toFixed(1) ?? "-" },
  { title: "毛利率(%)", key: "grossprofit_margin", width: 90, render: (r) => r.grossprofit_margin?.toFixed(1) ?? "-" },
  { title: "净利率(%)", key: "netprofit_margin", width: 90, render: (r) => r.netprofit_margin?.toFixed(1) ?? "-" },
  { title: "负债率(%)", key: "debt_to_assets", width: 90, render: (r) => r.debt_to_assets?.toFixed(1) ?? "-" },
  { title: "EPS", key: "eps", width: 80, render: (r) => r.eps?.toFixed(2) ?? "-" },
  { title: "流动比率", key: "current_ratio", width: 80, render: (r) => r.current_ratio?.toFixed(2) ?? "-" },
  { title: "速动比率", key: "quick_ratio", width: 80, render: (r) => r.quick_ratio?.toFixed(2) ?? "-" },
]

async function search() {
  const codes = codeInput.value.split(/[,; ]+/).filter(Boolean).map(c => c.trim().toUpperCase())
  if (!codes.length) { message.warning("请输入股票代码"); return }
  loading.value = true; error.value = false
  try { data.value = await marketAPI.getFinancialCompare({ codes }) }
  catch { error.value = true; message.error("查询失败") }
  finally { loading.value = false }
}

onMounted(() => {
  codeInput.value = "000001.SZ, 600036.SH, 600519.SH, 000858.SZ, 601318.SH"
  search()
})
</script>

<template>
  <div class="financial-page bg-gradient-mesh bg-noise">
    <div class="page-header"><div class="header-content"><div class="title-section"><h1 class="page-title">财务数据中心</h1></div><div class="header-actions"><n-button class="action-btn" @click="() => $router.back()" quaternary><template #icon><SmartIcon name="ArrowLeft" /></template></n-button></div></div></div>

    <div class="main-content">
    <n-space style="margin-bottom:16px">
      <n-input v-model:value="codeInput" placeholder="输入代码，逗号/空格分隔" style="width:400px" clearable @keyup.enter="search" />
      <n-button type="primary" @click="search">对比</n-button>
    </n-space>

    <n-skeleton v-if="loading" :text="true" :repeat="6" />
    <n-result v-else-if="error" status="500"><template #footer><n-button @click="search">重试</n-button></template></n-result>
    <n-empty v-else-if="!data.length" description="无数据" />

    <n-card v-else :class="tokens.surface.card">
      <n-dataTable :columns="columns" :data="data" size="small" :bordered="true" max-height="calc(100vh - 280px)"
        :row-props="(row: any) => ({ style: 'cursor:pointer', onClick: () => router.push('/market/stock/' + row.ts_code) })" />
    </n-card>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.financial-page { padding-bottom: 24px; height: 100%; overflow-y: auto; }
.page-header { padding: 16px 0; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; }
</style>
