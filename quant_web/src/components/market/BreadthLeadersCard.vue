<script setup lang="ts">
// 强弱榜（v5 N6）—— 创20日新高 / 创20日新低 / 连涨≥5日，各 TOP10
import { computed, h } from "vue";
import { useRouter } from "vue-router";
import { NSkeleton, NEmpty, NTabs, NTabPane, NDataTable } from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import type { BreadthLeaderRow } from "@/types/entities/market";

const props = defineProps<{
  data: { new_highs: BreadthLeaderRow[]; new_lows: BreadthLeaderRow[]; streak_up: BreadthLeaderRow[] } | null;
  loading: boolean;
}>();

const router = useRouter();

const pctColor = (v: number | null) =>
  v == null ? "" : v >= 0 ? "#ef5350" : "#26a69a";
const pctText = (v: number | null) =>
  v == null ? "-" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
// stock_daily.amount 单位千元 → /1e5 = 亿
const amtText = (v: number | null) =>
  v == null ? "-" : (v / 1e5).toFixed(1) + "亿";

const columns: DataTableColumns<BreadthLeaderRow> = [
  {
    title: "名称",
    key: "name",
    width: 90,
    ellipsis: { tooltip: true },
    render: (r) => r.name ?? r.ts_code,
  },
  {
    title: "行业",
    key: "industry",
    width: 84,
    ellipsis: { tooltip: true },
    render: (r) => r.industry ?? "-",
  },
  {
    title: "涨跌",
    key: "pct_chg",
    width: 72,
    render: (r) =>
      h("span", { style: { color: pctColor(r.pct_chg ?? null) } }, pctText(r.pct_chg ?? null)),
  },
  {
    title: "成交额",
    key: "amount",
    width: 72,
    render: (r) => amtText(r.amount),
  },
];

const rowProps = (row: BreadthLeaderRow) => ({
  style: "cursor:pointer",
  onClick: () => router.push("/market/stock/" + row.ts_code),
});

const tabs = computed(() => [
  { key: "highs", label: "新高", rows: props.data?.new_highs ?? [] },
  { key: "lows", label: "新低", rows: props.data?.new_lows ?? [] },
  { key: "streak", label: "连涨", rows: props.data?.streak_up ?? [] },
]);
</script>

<template>
  <n-card size="small" class="full-height-card" title="强弱榜">
    <n-skeleton v-if="loading && !data" :text="true" :repeat="3" />
    <n-empty v-else-if="!data" description="暂无榜单数据" size="small" style="padding: 24px" />
    <n-tabs v-else type="segment" size="small" default-value="highs">
      <n-tab-pane v-for="t in tabs" :key="t.key" :name="t.key" :tab="t.label + ' ' + t.rows.length">
        <n-empty v-if="!t.rows.length" description="暂无数据" size="small" style="padding: 16px" />
        <n-data-table
          v-else
          :columns="columns"
          :data="t.rows"
          size="small"
          :bordered="false"
          max-height="300"
          :row-props="rowProps"
        />
      </n-tab-pane>
    </n-tabs>
  </n-card>
</template>

<style lang="scss" scoped>
.full-height-card {
  height: 100%;
}
</style>
