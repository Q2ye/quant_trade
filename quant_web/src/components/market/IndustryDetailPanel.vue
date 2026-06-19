<!-- IndustryDetailPanel.vue — 行业详情：趋势图 + 阶段统计 + 成分股列表 -->
<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NCard,
  NGrid,
  NGridItem,
  NButton,
  NDataTable,
  NSkeleton,
  NEmpty,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import { tokens } from "@/styles/design-tokens";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
]);

const router = useRouter();

export interface StageStatItem {
  label: string;
  pct: number | null;
  rank: number;
}

const props = withDefaults(
  defineProps<{
    code?: string;
    name?: string;
    visible?: boolean;
    stageStats?: StageStatItem[];
  }>(),
  {
    code: "",
    name: "",
    visible: false,
    stageStats: () => [],
  },
);

const emit = defineEmits<{
  close: [];
}>();

const detailLoading = ref(false);
const members = ref<any[]>([]);
const trendData = ref<any[]>([]);
const benchmarkData = ref<any[]>([]);

// ---- trend chart ----
const trendOption = computed(() => {
  if (!trendData.value.length) return null;
  const items = [...trendData.value].reverse();
  const bench = [...benchmarkData.value].reverse();
  let cumInd = 0;
  const indLine: number[] = [];
  for (const d of items) {
    const pct = d.pct_change ?? d.pct_chg ?? 0;
    cumInd += pct;
    indLine.push(+cumInd.toFixed(2));
  }
  let cumBm = 0;
  const bmLine: number[] = [];
  for (const d of bench) {
    cumBm += d.pct_chg ?? 0;
    bmLine.push(+cumBm.toFixed(2));
  }
  return {
    grid: { top: 10, right: 20, bottom: 10, left: 60 },
    xAxis: {
      type: "category",
      data: items.map((d: any) => d.trade_date?.slice(5) ?? ""),
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10, formatter: (v: number) => v + "%" },
    },
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, textStyle: { fontSize: 10 } },
    series: [
      {
        name: "行业累计",
        type: "line",
        data: indLine,
        smooth: true,
        lineStyle: { color: "#448AFF", width: 2 },
        symbol: "none",
        areaStyle: { color: "rgba(68,138,255,0.1)" },
      },
      {
        name: "沪深300",
        type: "line",
        data: bmLine,
        smooth: true,
        lineStyle: { color: "#999", width: 1.5, type: "dashed" },
        symbol: "none",
      },
    ],
  };
});

// ---- member cols ----
const memberCols: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 100 },
  { title: "简称", key: "name", width: 90, ellipsis: { tooltip: true } },
  {
    title: "最新价",
    key: "close",
    width: 80,
    render: (r: any) => r.close?.toFixed(2) ?? "-",
  },
  {
    title: "涨跌幅",
    key: "pct_chg",
    width: 80,
    render: (r: any) =>
      h(
        "span",
        { style: { color: (r.pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } },
        r.pct_chg != null
          ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%"
          : "-",
      ),
  },
  {
    title: "成交额(亿)",
    key: "amount",
    width: 90,
    render: (r: any) => (r.amount ? (r.amount / 1e8).toFixed(1) : "-"),
  },
];

async function loadDetail(code: string) {
  detailLoading.value = true;
  try {
    const [detail, trend, bench] = await Promise.all([
      marketAPI.getIndustryDetail(code).catch(() => null),
      marketAPI.getIndustryHistory(code, 90).catch(() => []),
      marketAPI.getIndexHistory("000300.SH", 90).catch(() => []),
    ]);
    members.value = detail?.members || [];
    trendData.value = trend || [];
    benchmarkData.value = bench || [];
  } catch {
    members.value = [];
    trendData.value = [];
    benchmarkData.value = [];
  } finally {
    detailLoading.value = false;
  }
}

watch(
  () => props.code,
  (newCode) => {
    if (newCode && props.visible) {
      loadDetail(newCode);
    } else {
      members.value = [];
      trendData.value = [];
      benchmarkData.value = [];
    }
  },
);
</script>

<template>
  <n-card
    v-if="visible && code"
    :class="tokens.surface.card"
    size="small"
    style="margin-top: 16px"
  >
    <template #header>
      <span>{{ name || code }} — 详情</span>
    </template>
    <template #header-extra>
      <n-button
        size="tiny"
        @click="
          router.push(
            '/market/screener?industry=' + encodeURIComponent(name || ''),
          )
        "
      >
        在选股器中打开 →
      </n-button>
      <n-button
        size="tiny"
        quaternary
        style="margin-left: 8px"
        @click="emit('close')"
        >关闭</n-button
      >
    </template>

    <n-skeleton v-if="detailLoading" :text="true" :repeat="4" />
    <template v-else>
      <!-- trend chart -->
      <v-chart
        v-if="trendOption"
        :option="trendOption"
        autoresize
        style="height: 280px"
      />
      <n-empty v-else description="暂无趋势数据" style="padding: 20px" />

      <!-- stage stats -->
      <n-grid :x-gap="8" :cols="6" style="margin-top: 12px">
        <n-grid-item v-for="s in stageStats" :key="s.label">
          <div
            style="
              text-align: center;
              padding: 8px;
              background: rgba(255, 255, 255, 0.03);
              border-radius: 6px;
            "
          >
            <div style="font-size: 11px; color: var(--n-text-color-3)">
              {{ s.label }}
            </div>
            <div
              style="font-size: 15px; font-weight: 600"
              :style="{ color: (s.pct ?? 0) >= 0 ? '#ef5350' : '#26a69a' }"
            >
              {{
                s.pct != null
                  ? (s.pct > 0 ? "+" : "") + s.pct.toFixed(1) + "%"
                  : "-"
              }}
            </div>
            <div style="font-size: 11px; color: var(--n-text-color-3)">
              #{{ s.rank }}/28
            </div>
          </div>
        </n-grid-item>
      </n-grid>

      <!-- members -->
      <n-data-table
        v-if="members.length"
        :columns="memberCols"
        :data="members"
        size="small"
        :bordered="false"
        max-height="400"
        style="margin-top: 12px"
        :row-props="
          (row: any) => ({
            style: 'cursor:pointer',
            onClick: () => router.push('/market/stock/' + row.ts_code),
          })
        "
      />
      <n-empty v-else description="暂无成分股数据" style="padding: 20px" />
    </template>
  </n-card>
</template>
