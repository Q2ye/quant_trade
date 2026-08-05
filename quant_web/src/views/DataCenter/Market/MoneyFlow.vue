<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NCard,
  NButton,
  NGrid,
  NGridItem,
  NDataTable,
  NSelect,
  NSpace,
  NSkeleton,
  NEmpty,
  NResult,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import { tokens } from "@/styles/design-tokens";
import SmartIcon from "@/components/common/SmartIcon.vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent]);

const router = useRouter();
const message = useMessage();
const loading = ref(true);
const error = ref(false);
const topData = ref<any[]>([]);
const hsgtData = ref<any[]>([]);
const sectorData = ref<any[]>([]);
const direction = ref("net_inflow");

const hsgtOption = computed(() => {
  if (!hsgtData.value.length) return undefined;
  const items = [...hsgtData.value].reverse();
  let cum = 0;
  const cumData = items.map((d: any) => {
    cum += d.net_inflow ?? 0;
    return cum / 1e8;
  });
  const daily = items.map((d: any) => (d.net_inflow ?? 0) / 1e8);
  return {
    grid: { top: 10, right: 60, bottom: 10, left: 60 },
    xAxis: {
      type: "category",
      data: items.map((d: any) => d.trade_date?.slice(5) ?? ""),
      axisLabel: { fontSize: 9 },
    },
    yAxis: [
      {
        type: "value",
        axisLabel: { fontSize: 10, formatter: (v: number) => v.toFixed(0) },
      },
      {
        type: "value",
        axisLabel: { fontSize: 10, formatter: (v: number) => v.toFixed(0) },
      },
    ],
    tooltip: { trigger: "axis" },
    series: [
      {
        name: "累计净流入(亿)",
        type: "line",
        yAxisIndex: 0,
        data: cumData,
        smooth: true,
        lineStyle: { color: "#ff9800", width: 2 },
        areaStyle: { color: "rgba(255,152,0,0.2)" },
        symbol: "none",
      },
      {
        name: "日净流入(亿)",
        type: "bar",
        yAxisIndex: 1,
        data: daily,
        itemStyle: {
          color: (p: any) => (p.value >= 0 ? "#ef5350" : "#26a69a"),
        },
        barMaxWidth: 8,
      },
    ],
  };
});

const topColumns: DataTableColumns<any> = [
  { title: "代码", key: "ts_code", width: 100 },
  { title: "简称", key: "name", width: 90 },
  {
    title: "最新价",
    key: "close",
    width: 70,
    render: (r) => r.close?.toFixed(2) ?? "-",
  },
  {
    title: "涨跌幅",
    key: "pct_chg",
    width: 80,
    render: (r) =>
      h(
        "span",
        { style: { color: (r.pct_chg ?? 0) >= 0 ? "#ef5350" : "#26a69a" } },
        r.pct_chg != null
          ? (r.pct_chg > 0 ? "+" : "") + r.pct_chg.toFixed(2) + "%"
          : "-",
      ),
  },
  {
    title: "净流入(亿)",
    key: "net_mf_amount",
    width: 85,
    render: (r) =>
      r.net_mf_amount != null ? (r.net_mf_amount / 1e8).toFixed(2) : "-",
  },
  {
    title: "资金强度",
    key: "intensity",
    width: 80,
    render: (r) => {
      const inflow = r.net_mf_amount;
      const mv = r.circ_mv; // 流通市值
      if (inflow != null && mv != null && mv > 0) {
        const v = (inflow / mv) * 100;
        return h(
          "span",
          {
            style: { color: v >= 0 ? "#ef5350" : "#26a69a", fontSize: "12px" },
          },
          (v >= 0 ? "+" : "") + v.toFixed(2) + "%",
        );
      }
      return "-";
    },
  },
  {
    title: "超大单买(亿)",
    key: "buy_elg_amount",
    render: (r) =>
      r.buy_elg_amount != null ? (r.buy_elg_amount / 1e8).toFixed(2) : "-",
  },
  {
    title: "超大单卖(亿)",
    key: "sell_elg_amount",
    render: (r) =>
      r.sell_elg_amount != null ? (r.sell_elg_amount / 1e8).toFixed(2) : "-",
  },
  {
    title: "大单买(亿)",
    key: "buy_lg_amount",
    render: (r) =>
      r.buy_lg_amount != null ? (r.buy_lg_amount / 1e8).toFixed(2) : "-",
  },
  {
    title: "大单卖(亿)",
    key: "sell_lg_amount",
    render: (r) =>
      r.sell_lg_amount != null ? (r.sell_lg_amount / 1e8).toFixed(2) : "-",
  },
];

// sector chart (with click → IndustryAnalysis)
function onSectorClick(params: any) {
  const name = sectorData.value[params.dataIndex]?.name;
  if (name) router.push("/market/industry?focus=" + encodeURIComponent(name));
}
const sectorOption = computed(() => {
  if (!sectorData.value.length) return undefined;
  const items = [...sectorData.value];
  return {
    grid: { top: 5, right: 60, bottom: 5, left: 100 },
    xAxis: {
      type: "value",
      axisLabel: {
        fontSize: 10,
        formatter: (v: number) => v.toFixed(0) + "亿",
      },
    },
    yAxis: {
      type: "category",
      data: items.map((d: any) => d.name ?? d.industry),
      axisLabel: { fontSize: 10 },
      inverse: true,
      triggerEvent: true,
    },
    tooltip: { trigger: "axis" },
    series: [
      {
        name: "净流入(亿)",
        type: "bar",
        data: items.map((d: any) => d.net_amount_yi ?? 0),
        itemStyle: {
          color: (p: any) => (p.value >= 0 ? "#ef5350" : "#26a69a"),
          borderRadius: 2,
        },
        barMaxWidth: 16,
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.3)" },
        },
      },
    ],
  };
});

// order-size aggregation
const orderSummary = computed(() => {
  if (!topData.value.length) return undefined;
  let elg = 0,
    lg = 0,
    md = 0,
    sm = 0,
    elgBuy = 0,
    elgSell = 0,
    lgBuy = 0,
    lgSell = 0,
    mdBuy = 0,
    mdSell = 0,
    smBuy = 0,
    smSell = 0;
  for (const r of topData.value) {
    elg += (r.buy_elg_amount ?? 0) - (r.sell_elg_amount ?? 0);
    lg += (r.buy_lg_amount ?? 0) - (r.sell_lg_amount ?? 0);
    md += (r.buy_md_amount ?? 0) - (r.sell_md_amount ?? 0);
    sm += (r.buy_sm_amount ?? 0) - (r.sell_sm_amount ?? 0);
    elgBuy += r.buy_elg_amount ?? 0;
    elgSell += r.sell_elg_amount ?? 0;
    lgBuy += r.buy_lg_amount ?? 0;
    lgSell += r.sell_lg_amount ?? 0;
    mdBuy += r.buy_md_amount ?? 0;
    mdSell += r.sell_md_amount ?? 0;
    smBuy += r.buy_sm_amount ?? 0;
    smSell += r.sell_sm_amount ?? 0;
  }
  return [
    { label: "超大单", net: elg, buy: elgBuy, sell: elgSell },
    { label: "大单", net: lg, buy: lgBuy, sell: lgSell },
    { label: "中单", net: md, buy: mdBuy, sell: mdSell },
    { label: "小单", net: sm, buy: smBuy, sell: smSell },
  ];
});

async function load() {
  loading.value = true;
  error.value = false;
  try {
    const [top, hsgt, sector] = await Promise.all([
      marketAPI.getTopMoneyflow(direction.value, 50),
      marketAPI.getHsgtHistory(120),
      marketAPI.getSectorMoneyflow().catch(() => []),
    ]);
    topData.value = top;
    hsgtData.value = hsgt;
    sectorData.value = sector;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

async function onDirChange(v: string) {
  direction.value = v;
  await load();
}

onMounted(load);
</script>

<template>
  <div class="moneyflow-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">资金流向</h1>
          <p class="page-description">主力资金与北向资金动态追踪</p>
        </div>
        <div class="header-actions">
          <n-button
            size="tiny"
            type="primary"
            ghost
            @click="
              router.push('/strategies/create?template=moneyflow_tracking')
            "
            >创建资金跟踪策略</n-button
          >
          <n-button class="action-btn" @click="() => $router.back()" quaternary
            ><template #icon><SmartIcon name="ArrowLeft" /></template
          ></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-skeleton v-if="loading" :text="true" :repeat="4" />
      <n-result v-else-if="error" status="500" title="加载失败"
        ><template #footer
          ><n-button @click="load">重试</n-button></template
        ></n-result
      >

      <template v-else>
        <!-- 北向资金累计 -->
        <n-card :class="tokens.surface.card" title="北向资金" size="small">
          <VChart
            v-if="hsgtData.length"
            :option="hsgtOption"
            autoresize
            style="height: 300px"
          />
          <n-empty v-else description="暂无数据" style="padding: 60px" />
        </n-card>

        <!-- 主力订单结构 -->
        <n-card
          v-if="orderSummary"
          :class="tokens.surface.card"
          size="small"
          title="主力订单结构"
          style="margin-top: 16px"
        >
          <n-grid :x-gap="12" :cols="4">
            <n-grid-item v-for="o in orderSummary" :key="o.label">
              <div
                style="
                  text-align: center;
                  padding: 12px 8px;
                  background: rgba(255, 255, 255, 0.03);
                  border-radius: 8px;
                "
              >
                <div style="font-size: 12px; color: var(--n-text-color-3)">
                  {{ o.label }}
                </div>
                <div
                  style="font-size: 20px; font-weight: 700; margin: 4px 0"
                  :style="{ color: o.net >= 0 ? '#ef5350' : '#26a69a' }"
                >
                  {{ o.net >= 0 ? "+" : "" }}{{ (o.net / 1e8).toFixed(1) }}亿
                </div>
                <div style="font-size: 11px; color: var(--n-text-color-3)">
                  买{{ (o.buy / 1e8).toFixed(0) }}亿 卖{{
                    (o.sell / 1e8).toFixed(0)
                  }}亿
                </div>
              </div>
            </n-grid-item>
          </n-grid>
        </n-card>

        <!-- 主力资金 TOP -->
        <n-card
          :class="tokens.surface.card"
          size="small"
          style="margin-top: 16px"
        >
          <template #header>
            <n-space align="center"
              ><span>主力资金</span>
              <n-select
                v-model:value="direction"
                size="small"
                style="width: 120px"
                :options="[
                  { label: '净流入TOP', value: 'net_inflow' },
                  { label: '净流出TOP', value: 'net_outflow' },
                ]"
                @update:value="onDirChange"
              />
            </n-space>
          </template>
          <n-dataTable
            :columns="topColumns"
            :data="topData"
            size="small"
            :bordered="false"
            max-height="600"
            :row-props="
              (row: any) => ({
                style: 'cursor:pointer',
                onClick: () => router.push('/market/stock/' + row.ts_code),
              })
            "
          />
        </n-card>

        <!-- 行业资金分布 -->
        <n-card
          :class="tokens.surface.card"
          size="small"
          title="行业资金分布"
          style="margin-top: 16px"
        >
          <VChart
            v-if="sectorOption"
            :option="sectorOption"
            autoresize
            style="height: 500px"
            @click="onSectorClick"
          />
          <n-empty
            v-else
            description="暂无行业资金数据"
            style="padding: 60px"
          />
        </n-card>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.moneyflow-page {
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}
</style>
