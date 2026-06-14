<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NCard,
  NGrid,
  NGridItem,
  NSkeleton,
  NEmpty,
  NResult,
  NButton,
  NButtonGroup,
  NTag,
  NSpace,
  NDataTable,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import type {
  DashboardOverview,
  TopVolumeItem,
  TopMoneyflowItem,
} from "@/types/entities/market";
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
const data = ref<DashboardOverview | null>(null);
const styleFactors = ref<any[]>([]);
const sectorTurnover = ref<number | null>(null);

// ---- macro interpretations ----
const macroNotes = computed(() => {
  const cpi = data.value?.macro_latest?.cpi?.cpi_yoy
  const ppi = data.value?.macro_latest?.ppi?.ppi_yoy
  const gdp = data.value?.macro_latest?.gdp?.gdp_yoy
  return {
    cpi:
      cpi == null ? "" :
      cpi > 3 ? "⚠ 通胀压力 · 利空债市" :
      cpi > 1 ? "温和通胀 · 经济健康" :
      cpi > 0 ? "低通胀 · 消费偏弱" :
      cpi > -1 ? "通缩风险 · 利好债市" :
      "⚠ 通缩 · 需求不足",
    ppi:
      ppi == null ? "" :
      ppi > 3 ? "⚠ 上游过热 · 挤压中下游" :
      ppi > 0 ? "工业回暖 · 盈利改善" :
      ppi > -3 ? "工业偏冷 · 需求不足" :
      "⚠ 深度通缩 · 产能过剩",
    gdp:
      gdp == null ? "" :
      gdp > 7 ? "🔥 经济过热" :
      gdp > 5 ? "稳健增长 · 利好权益" :
      gdp > 3 ? "温和增长 · 符合预期" :
      gdp > 0 ? "增长放缓 · 政策或加码" :
      "⚠ 经济收缩 · 避险升温",
  }
})

// ---- event calendar (static + dynamic from macro dates) ----
const upcomingEvents = computed(() => {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  // Standard Chinese economic data release schedule (approximate dates)
  const staticEvents: {
    date: string;
    label: string;
    month: number;
    day: number;
  }[] = [
    {
      date: `${y}-${String(m).padStart(2, "0")}-10`,
      label: "CPI/PPI 公布",
      month: m,
      day: 10,
    },
    {
      date: `${y}-${String(m).padStart(2, "0")}-15`,
      label: "工业增加值/社零",
      month: m,
      day: 15,
    },
    {
      date: `${y}-${String(m).padStart(2, "0")}-18`,
      label: "GDP 数据发布",
      month: m <= 3 ? 1 : m <= 6 ? 4 : m <= 9 ? 7 : 10,
      day: 18,
    },
    {
      date: `${y}-${String(m).padStart(2, "0")}-20`,
      label: "LPR 报价日",
      month: m,
      day: 20,
    },
  ];
  // Filter to upcoming events (from today +-5 days buffer)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return staticEvents
    .map((e) => {
      // If event date this month already passed, push to next month
      const d = new Date(y, e.month - 1, e.day);
      if (d < today && e.label !== "GDP 数据发布") {
        d.setMonth(d.getMonth() + 1);
      }
      return {
        date: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`,
        label: e.label,
      };
    })
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 4);
});

const pctColor = (v: number | null) =>
  v == null ? "" : v > 0 ? "#ef5350" : "#26a69a";
const pctText = (v: number | null) =>
  v == null ? "-" : (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const amtText = (v: number | null) =>
  v == null ? "-" : (v / 1e8).toFixed(1) + "亿";
const mvText = (v: number | null) =>
  v == null ? "-" : (v / 1e8).toFixed(0) + "亿";

// ---- breadth ----
const dataDateText = computed(() => {
  const d = data.value?.data_date;
  if (!d) return "";
  const dt = new Date(d);
  const dayNames = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")} ${dayNames[dt.getDay()]}`;
});

const upRatio = computed(() => {
  if (!data.value) return 0;
  const t = data.value.market_breadth.total || 1;
  return (data.value.market_breadth.up / t) * 100;
});

// ---- market environment仪表 ----
const volatility20d = computed(() => {
  // use index daily change from dashboard overview as vol proxy
  const idx = data.value?.indices?.find((i: any) => i.code === "000001.SH");
  const pct = idx?.pct_chg;
  if (pct == null) return null;
  return Math.abs(pct) * Math.sqrt(252);
});
const volPercentile = computed(() => {
  if (volatility20d.value == null) return null;
  const v = volatility20d.value;
  return Math.min(100, Math.max(0, ((v - 10) / 30) * 100));
});
const styleFactorSummary = computed(() => {
  if (!styleFactors.value.length) return null;
  // pick latest row; show momentum/value/size
  const latest = styleFactors.value[styleFactors.value.length - 1];
  return [
    {
      label: "动量",
      key: "momentum",
      val: latest?.momentum ?? latest?.Momentum,
    },
    { label: "价值", key: "value", val: latest?.value ?? latest?.Value },
    { label: "规模", key: "size", val: latest?.size ?? latest?.Size },
  ].map((f) => ({ ...f, val: typeof f.val === "number" ? f.val : null }));
});

const styleFactorPct = (v: number | null | undefined) =>
  v == null ? "-" : (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const styleFactorColor = (v: number | null | undefined) =>
  v == null ? "" : v > 0 ? "#ef5350" : "#26a69a";

function goIndex(code: string) {
  router.push("/market/index?focus=" + code);
}

// ---- TOP10 columns ----
const volumeCols: DataTableColumns<TopVolumeItem> = [
  { title: "股票", key: "name", width: 80, ellipsis: { tooltip: true } },
  { title: "行业", key: "industry", width: 65, ellipsis: { tooltip: true } },
  {
    title: "涨跌",
    key: "pct_chg",
    width: 65,
    render: (r) =>
      h("span", { style: { color: pctColor(r.pct_chg) } }, pctText(r.pct_chg)),
  },
  {
    title: "成交额",
    key: "amount",
    width: 75,
    render: (r) => amtText(r.amount),
  },
  {
    title: "市值",
    key: "total_mv",
    width: 75,
    render: (r) => (r.total_mv ? mvText(r.total_mv) : "-"),
  },
  {
    title: "换手",
    key: "turnover_rate",
    width: 60,
    render: (r) => (r.turnover_rate ? r.turnover_rate.toFixed(1) + "%" : "-"),
  },
];

const flowCols: DataTableColumns<TopMoneyflowItem> = [
  { title: "股票", key: "name", width: 80, ellipsis: { tooltip: true } },
  {
    title: "涨跌",
    key: "pct_chg",
    width: 65,
    render: (r) =>
      h("span", { style: { color: pctColor(r.pct_chg) } }, pctText(r.pct_chg)),
  },
  {
    title: "净流入",
    key: "net_mf_amount",
    width: 75,
    render: (r) => {
      const v = r.net_mf_amount;
      return v == null
        ? "-"
        : h(
            "span",
            { style: { color: v >= 0 ? "#ef5350" : "#26a69a" } },
            amtText(v),
          );
    },
  },
  {
    title: "超大单",
    key: "elg",
    width: 75,
    render: (r) => amtText((r.buy_elg_amount ?? 0) - (r.sell_elg_amount ?? 0)),
  },
  {
    title: "大单",
    key: "lg",
    width: 75,
    render: (r) => amtText((r.buy_lg_amount ?? 0) - (r.sell_lg_amount ?? 0)),
  },
];

// ---- HSGT bars ----
const hBarSH = computed(() => {
  const hsgt = data.value?.hsgt_flow;
  if (!hsgt) return 0;
  const sh = Math.abs(hsgt.sh_inflow ?? 0);
  const sz = Math.abs(hsgt.sz_inflow ?? 0);
  const total = sh + sz;
  return total > 0 ? (sh / total) * 100 : 50;
});
const hBarSZ = computed(() => 100 - hBarSH.value);

// ---- industry bar chart (multi-window) ----
const swHeatmap = ref<any[]>([]);
const industryWindow = ref("pct_1d");
const industryWindows = [
  { key: "pct_1d", label: "1日" },
  { key: "pct_5d", label: "5日" },
  { key: "pct_10d", label: "10日" },
  { key: "pct_20d", label: "20日" },
  { key: "pct_30d", label: "30日" },
  { key: "pct_60d", label: "60日" },
];
const focusSectors = ref(false);
function setIndustryWindow(key: string) {
  industryWindow.value = key;
}
const industryBarOption = computed(() => {
  if (!swHeatmap.value.length) return null;
  let src = [...swHeatmap.value];
  if (focusSectors.value) {
    src.sort(
      (a, b) =>
        Math.abs(b[industryWindow.value] ?? 0) -
        Math.abs(a[industryWindow.value] ?? 0),
    );
    src = src.slice(0, 14);
  }
  const items = src.sort((a, b) => {
    const va = (a[industryWindow.value] ?? -9999) as number;
    const vb = (b[industryWindow.value] ?? -9999) as number;
    return vb - va;
  });
  const names = items.map((d: any) =>
    d.name.length > 6 ? d.name.slice(0, 6) : d.name,
  );
  const values = items.map(
    (d: any) => (d[industryWindow.value] as number) ?? 0,
  );
  return {
    grid: { top: 5, right: 60, bottom: 5, left: 80 },
    xAxis: {
      type: "value",
      axisLabel: { fontSize: 10, formatter: (v: number) => v.toFixed(1) + "%" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    },
    yAxis: {
      type: "category",
      data: names,
      inverse: true,
      axisLabel: { fontSize: 11 },
      triggerEvent: true,
    },
    tooltip: {
      trigger: "axis",
      formatter: (ps: any[]) => {
        const p = ps[0];
        const item = items[p.dataIndex];
        const pct = item[industryWindow.value] as number;
        return (
          "<strong>" +
          item.name +
          "</strong><br/>涨跌幅: " +
          (pct != null ? (pct > 0 ? "+" : "") + pct.toFixed(2) + "%" : "-")
        );
      },
    },
    series: [
      {
        type: "bar",
        data: values.map((v: number, i: number) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? "#ef5350" : "#26a69a",
            borderRadius: [0, 2, 2, 0],
          },
          name: items[i].name,
          code: items[i].code,
        })),
        barMaxWidth: 18,
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.3)" },
        },
      },
    ],
  };
});

const hsgtHistory = ref<any[]>([]);
const hsgtChartOption = computed(() => {
  if (!hsgtHistory.value.length) return null;
  const items = [...hsgtHistory.value].reverse();
  let cum = 0;
  const cumData: number[] = [],
    dailyData: number[] = [],
    dates: string[] = [];
  for (const d of items) {
    cum += (d.net_inflow ?? 0) / 1e8;
    cumData.push(+cum.toFixed(1));
    dailyData.push(+((d.net_inflow ?? 0) / 1e8).toFixed(1));
    dates.push(d.trade_date?.slice(5) ?? "");
  }
  return {
    grid: { top: 10, right: 50, bottom: 10, left: 50 },
    xAxis: { type: "category", data: dates, axisLabel: { fontSize: 9 } },
    yAxis: [
      {
        type: "value",
        axisLabel: { fontSize: 9, formatter: (v: number) => v.toFixed(0) },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
      },
      {
        type: "value",
        axisLabel: { fontSize: 9, formatter: (v: number) => v.toFixed(0) },
        splitLine: { show: false },  // 副轴不显示网格，避免双轴网格线错位
      },
    ],
    tooltip: { trigger: "axis" },
    series: [
      {
        name: "累计(亿)",
        type: "line",
        yAxisIndex: 0,
        data: cumData,
        smooth: true,
        lineStyle: { color: "#ff9800", width: 2 },
        areaStyle: { color: "rgba(255,152,0,0.15)" },
        symbol: "none",
      },
      {
        name: "日净流入(亿)",
        type: "bar",
        yAxisIndex: 1,
        data: dailyData,
        itemStyle: {
          color: (p: any) => (p.value >= 0 ? "#ef5350" : "#26a69a"),
        },
        barMaxWidth: 6,
      },
    ],
  };
});
const orderSummary = computed(() => {
  const items = data.value?.top_moneyflow || [];
  if (!items.length) return null;
  let elg = 0,
    lg = 0,
    md = 0,
    sm = 0;
  for (const r of items) {
    elg += (r.buy_elg_amount ?? 0) - (r.sell_elg_amount ?? 0);
    lg += (r.buy_lg_amount ?? 0) - (r.sell_lg_amount ?? 0);
    md += (r.buy_md_amount ?? 0) - (r.sell_md_amount ?? 0);
    sm += (r.buy_sm_amount ?? 0) - (r.sell_sm_amount ?? 0);
  }
  return [
    { label: "超大单", net: elg },
    { label: "大单", net: lg },
    { label: "中单", net: md },
    { label: "小单", net: sm },
  ];
});
function nav(p: string) {
  router.push(p);
}
const watchlist = ref<any[]>([]);
async function loadWatchlist() {
  marketAPI
    .getWatchlist()
    .then((w) => {
      watchlist.value = w || [];
    })
    .catch(() => {});
}
async function load() {
  loading.value = true;
  error.value = false;
  try {
    data.value = await marketAPI.getDashboardOverview();
    marketAPI
      .getHsgtHistory(120)
      .then((h) => {
        hsgtHistory.value = h || [];
      })
      .catch(() => {});
    loadWatchlist();
    marketAPI
      .getIndustryHeatmap({ windows: "1d,5d,10d,20d,30d,60d" })
      .then((h) => {
        swHeatmap.value = h?.length
          ? h
          : data.value?.sw_heatmap ||
            data.value?.industry_heatmap?.map((i: any) => ({
              ...i,
              pct_1d: i.pct_chg,
            })) ||
            [];
      })
      .catch(() => {
        swHeatmap.value = data.value?.sw_heatmap || [];
      });
    marketAPI
      .getStyleFactors()
      .then((f) => {
        styleFactors.value = f || [];
      })
      .catch(() => {});
    marketAPI
      .getSectorTurnover()
      .then((t) => {
        sectorTurnover.value = t?.turnover_rate ?? null;
      })
      .catch(() => {});
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="market-dashboard bg-gradient-mesh bg-noise">
    <!-- Page Header (global pattern: page-header > header-content > title-section + header-actions) -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场总览</h1>
          <p class="page-description" v-if="data">
            数据截止：{{ dataDateText }} ｜
            {{ data.market_breadth.total }} 只股票有行情
          </p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="load" quaternary
            ><template #icon><SmartIcon name="Refresh" /></template
          ></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <n-grid
        v-if="loading"
        :x-gap="16"
        :y-gap="16"
        :cols="4"
        responsive="screen"
      >
        <n-grid-item v-for="i in 4" :key="i"
          ><n-card><n-skeleton :text="true" :repeat="3" /></n-card
        ></n-grid-item>
      </n-grid>
      <n-result v-else-if="error" status="500" title="加载失败"
        ><template #footer
          ><n-button @click="load">重试</n-button></template
        ></n-result
      >

      <template v-else-if="data">
        <!-- Row 0: 自选股条 -->
        <div
          v-if="watchlist.length"
          style="
            margin-bottom: 12px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
          "
        >
          <span style="font-size: 12px; color: var(--n-text-color-3)"
            >⭐ 自选</span
          >
          <n-tag
            v-for="w in watchlist"
            :key="w.ts_code"
            size="small"
            style="cursor: pointer"
            @click="nav('/market/stock/' + w.ts_code)"
          >
            {{ w.name }}
            <span
              :style="{ color: (w.pct_chg ?? 0) >= 0 ? '#ef5350' : '#26a69a' }"
              >{{ (w.pct_chg ?? 0) > 0 ? "+" : ""
              }}{{ w.pct_chg?.toFixed(2) ?? "-" }}%</span
            >
          </n-tag>
        </div>
        <!-- Row 1: 核心指数(3) + 涨跌统计(1) + 北向(1) -->
        <n-grid
          :x-gap="16"
          :y-gap="16"
          :cols="5"
          responsive="screen"
          class="row-equal"
        >
          <n-grid-item :span="3">
            <n-card title="核心指数" size="small" class="full-height-card">
              <div class="index-grid">
                <div
                  v-for="idx in data.indices"
                  :key="idx.code"
                  class="idx-item"
                  style="cursor: pointer"
                  @click="goIndex(idx.code)"
                >
                  <span class="idx-name">{{
                    idx.name?.slice(0, 4) || idx.code
                  }}</span>
                  <span class="idx-close">{{
                    idx.close?.toFixed(2) ?? "-"
                  }}</span>
                  <span
                    class="idx-pct"
                    :style="{ color: pctColor(idx.pct_chg) }"
                    >{{ pctText(idx.pct_chg) }}</span
                  >
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <!-- 涨跌统计 -->
          <n-grid-item>
            <n-card
              title="涨跌统计"
              size="small"
              class="full-height-card card-body-center"
            >
              <div class="breadth">
                <div class="breadth-bar">
                  <div class="bar-up" :style="{ width: upRatio + '%' }" />
                  <div
                    class="bar-down"
                    :style="{ width: 100 - upRatio + '%' }"
                  />
                </div>
                <div class="b-stat-row">
                  <div
                    class="b-stat"
                    style="cursor: pointer"
                    @click="nav('/market/limit-events')"
                  >
                    <span class="b-stat-num up">{{
                      data.market_breadth.up.toLocaleString()
                    }}</span>
                    <span class="b-stat-label">上涨</span>
                    <span class="b-stat-pct up">{{ upRatio.toFixed(1) }}%</span>
                  </div>
                  <div
                    class="b-stat"
                    style="cursor: pointer"
                    @click="nav('/market/limit-events')"
                  >
                    <span class="b-stat-num down">{{
                      data.market_breadth.down.toLocaleString()
                    }}</span>
                    <span class="b-stat-label">下跌</span>
                    <span class="b-stat-pct down"
                      >{{ (100 - upRatio).toFixed(1) }}%</span
                    >
                  </div>
                  <div class="b-stat">
                    <span class="b-stat-num">{{
                      data.market_breadth.flat.toLocaleString()
                    }}</span>
                    <span class="b-stat-label">平盘</span>
                    <span class="b-stat-pct"
                      >{{
                        data.market_breadth.total
                          ? (
                              (data.market_breadth.flat /
                                data.market_breadth.total) *
                              100
                            ).toFixed(1)
                          : "0"
                      }}%</span
                    >
                  </div>
                </div>
                <n-space style="margin-top: 12px" justify="center">
                  <n-tag
                    type="error"
                    size="small"
                    style="cursor: pointer"
                    @click="nav('/market/limit-events')"
                    >涨停 {{ data.market_breadth.limit_up }}</n-tag
                  >
                  <n-tag
                    type="info"
                    size="small"
                    style="cursor: pointer"
                    @click="nav('/market/limit-events')"
                    >跌停 {{ data.market_breadth.limit_down }}</n-tag
                  >
                </n-space>
              </div>
            </n-card>
          </n-grid-item>

          <!-- 北向资金 -->
          <n-grid-item>
            <n-card
              title="北向资金"
              size="small"
              class="full-height-card card-body-center"
            >
              <template v-if="data.hsgt_flow">
                <div class="hsgt">
                  <div class="h-dir">
                    {{ (data.hsgt_flow.net_inflow ?? 0) >= 0 ? "↗" : "↘" }}
                  </div>
                  <div class="h-main">
                    <span
                      class="h-val"
                      :class="{
                        up: (data.hsgt_flow.net_inflow ?? 0) > 0,
                        down: (data.hsgt_flow.net_inflow ?? 0) < 0,
                      }"
                      >{{
                        Math.abs(data.hsgt_flow.net_inflow ?? 0) > 0
                          ? (
                              Math.abs(data.hsgt_flow.net_inflow!) / 1e8
                            ).toFixed(1)
                          : "0"
                      }}</span
                    ><span class="h-unit">亿</span>
                  </div>
                  <div class="h-bar-wrap">
                    <div class="h-bar-item">
                      <span class="h-bar-label">沪</span>
                      <div class="h-bar-track">
                        <div
                          class="h-bar-fill sh"
                          :style="{ width: hBarSH + '%' }"
                        />
                      </div>
                      <span class="h-bar-val"
                        >{{ (data.hsgt_flow.sh_inflow ?? 0) > 0 ? "+" : ""
                        }}{{
                          data.hsgt_flow.sh_inflow
                            ? (data.hsgt_flow.sh_inflow / 1e8).toFixed(1)
                            : "0"
                        }}亿</span
                      >
                    </div>
                    <div class="h-bar-item">
                      <span class="h-bar-label">深</span>
                      <div class="h-bar-track">
                        <div
                          class="h-bar-fill sz"
                          :style="{ width: hBarSZ + '%' }"
                        />
                      </div>
                      <span class="h-bar-val"
                        >{{ (data.hsgt_flow.sz_inflow ?? 0) > 0 ? "+" : ""
                        }}{{
                          data.hsgt_flow.sz_inflow
                            ? (data.hsgt_flow.sz_inflow / 1e8).toFixed(1)
                            : "0"
                        }}亿</span
                      >
                    </div>
                  </div>
                </div>
              </template>
              <n-empty v-else description="暂无" size="small" />
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- Row 1.5: 市场环境仪表 (4 cards) -->
        <n-grid :x-gap="16" :y-gap="16" :cols="4" style="margin-top: 16px">
          <!-- 市场宽度 -->
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <div class="env-card">
                <div class="env-label">市场宽度</div>
                <div class="env-main">
                  <span
                    :style="{
                      color: upRatio >= 50 ? '#ef5350' : '#26a69a',
                      fontSize: '24px',
                      fontWeight: 700,
                    }"
                    >{{ upRatio >= 50 ? "↗" : "↘" }}
                    {{ upRatio.toFixed(0) }}%涨</span
                  >
                </div>
                <div class="env-sub">
                  涨{{ data.market_breadth.up.toLocaleString() }}跌{{
                    data.market_breadth.down.toLocaleString()
                  }}
                </div>
                <div class="env-sub">
                  涨停{{ data.market_breadth.limit_up }} 跌停{{
                    data.market_breadth.limit_down
                  }}
                </div>
              </div>
            </n-card>
          </n-grid-item>
          <!-- 风格因子 -->
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <template v-if="styleFactorSummary">
                <div class="env-card">
                  <div class="env-label">风格因子</div>
                  <div
                    v-for="f in styleFactorSummary"
                    :key="f.label"
                    class="env-row"
                  >
                    <span>{{ f.label }}</span>
                    <span
                      :style="{
                        color: styleFactorColor(f.val),
                        fontWeight: 600,
                      }"
                      >{{ styleFactorPct(f.val) }}</span
                    >
                  </div>
                </div>
              </template>
              <n-empty v-else description="加载中..." size="small" />
            </n-card>
          </n-grid-item>
          <!-- 波动率 -->
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <div class="env-card">
                <div class="env-label">波动率 (20日)</div>
                <div class="env-main" style="font-size: 24px">
                  {{
                    volatility20d != null ? volatility20d.toFixed(1) + "%" : "-"
                  }}
                </div>
                <div class="env-sub" v-if="volPercentile != null">
                  历史分位 {{ volPercentile.toFixed(0) }}%
                </div>
                <div class="env-sub" v-else>数据计算中...</div>
              </div>
            </n-card>
          </n-grid-item>
          <!-- 行业轮动速度 -->
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <div class="env-card">
                <div class="env-label">行业轮动速度</div>
                <div class="env-main" style="font-size: 24px">
                  {{ sectorTurnover != null ? sectorTurnover.toFixed(2) : "-" }}
                </div>
                <div class="env-sub">
                  {{
                    sectorTurnover != null
                      ? sectorTurnover > 0.5
                        ? "轮动较快"
                        : sectorTurnover > 0.3
                          ? "轮动适中"
                          : "轮动较慢"
                      : "加载中..."
                  }}
                </div>
                <div style="margin-top: 4px; font-size: 12px">
                  <n-button
                    size="tiny"
                    quaternary
                    @click="nav('/market/industry')"
                    >查看详情 →</n-button
                  >
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- Row 2: 申万行业轮动 (ECharts BarChart + multi-window) -->
        <n-card title="申万行业轮动" size="small" style="margin-top: 16px">
          <template #header-extra>
            <n-button-group size="tiny">
              <n-button
                v-for="w in industryWindows"
                :key="w.key"
                :type="industryWindow === w.key ? 'primary' : 'default'"
                @click="setIndustryWindow(w.key)"
                >{{ w.label }}</n-button
              >
            </n-button-group>
            <n-button
              size="tiny"
              :type="focusSectors ? 'primary' : 'default'"
              @click="focusSectors = !focusSectors"
              style="margin-left: 4px"
              >☆ 重点</n-button
            >
            <n-button
              size="tiny"
              quaternary
              @click="nav('/market/industry')"
              style="margin-left: 4px"
              >详情 →</n-button
            >
          </template>
          <div style="height: 480px">
            <VChart
              v-if="industryBarOption"
              :option="industryBarOption"
              autoresize
              style="height: 480px"
              @click="
                (e: any) => {
                  const item = swHeatmap.find((d: any) => d.name === e.name);
                  if (item)
                    nav(
                      '/market/industry?focus=' + encodeURIComponent(item.name),
                    );
                }
              "
            />
            <n-empty v-else description="暂无行业数据" style="padding: 40px" />
          </div>
        </n-card>

        <!-- Row 3: TOP10 -->
        <n-grid :x-gap="16" :y-gap="16" :cols="2" style="margin-top: 16px">
          <n-grid-item>
            <n-card title="成交额 TOP10" size="small">
              <template #header-extra
                ><n-button
                  size="tiny"
                  quaternary
                  @click="nav('/market/screener')"
                  >筛选 →</n-button
                ></template
              >
              <n-dataTable
                :columns="volumeCols"
                :data="data.top_volume"
                size="small"
                :bordered="false"
                max-height="340"
                :row-props="
                  (row: TopVolumeItem) => ({
                    style: 'cursor:pointer',
                    onClick: () => nav('/market/stock/' + row.ts_code),
                  })
                "
              />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card title="资金流入 TOP10" size="small">
              <template #header-extra
                ><n-button
                  size="tiny"
                  quaternary
                  @click="nav('/market/money-flow')"
                  >详情 →</n-button
                ></template
              >
              <n-dataTable
                :columns="flowCols"
                :data="data.top_moneyflow"
                size="small"
                :bordered="false"
                max-height="340"
                :row-props="
                  (row: TopMoneyflowItem) => ({
                    style: 'cursor:pointer',
                    onClick: () => nav('/market/stock/' + row.ts_code),
                  })
                "
              />
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- Row 3.5: 北向资金图表 + 主力订单 -->
        <n-grid :x-gap="16" :y-gap="16" :cols="3" style="margin-top: 16px">
          <n-grid-item :span="2"
            ><n-card size="small"
              ><template #header
                >北向资金<small style="color:var(--n-text-color-3);margin-left:8px;font-weight:400">橙=累计流入 柱=当日净流入（亿）</small></template
              ><VChart
                v-if="hsgtChartOption"
                :option="hsgtChartOption"
                autoresize
                style="height: 200px" /><n-empty
                v-else
                description="暂无 hsgt_flow 数据"
                style="padding: 20px" /></n-card
          ></n-grid-item>
          <n-grid-item
            ><n-card size="small"
              ><template #header
                >主力订单<small style="color:var(--n-text-color-3);margin-left:4px;font-weight:400">全市场 TOP10 汇总</small></template
              ><div
                v-if="orderSummary"
                style="display: flex; flex-direction: column; gap: 6px"
              >
                <div
                  v-for="o in orderSummary"
                  :key="o.label"
                  style="
                    display: flex;
                    justify-content: space-between;
                    font-size: 13px;
                  "
                >
                  <span>{{ o.label }}</span
                  ><span :style="{ color: o.net >= 0 ? '#ef5350' : '#26a69a' }"
                    >{{ (o.net / 1e8).toFixed(1) }}亿</span
                  >
                </div>
              </div>
              <n-empty v-else description="暂无数据" /></n-card
          ></n-grid-item>
        </n-grid>
        <!-- Row 3.75: 宏观经济 + 事件日历 -->
        <n-grid :x-gap="16" :y-gap="16" :cols="4" style="margin-top: 16px">
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <div class="env-card">
                <div class="env-label">CPI 居民消费价格</div>
                <div class="env-main" style="font-size: 22px">
                  {{
                    data.macro_latest?.cpi?.cpi_yoy != null
                      ? (data.macro_latest.cpi.cpi_yoy > 0 ? "+" : "") +
                        data.macro_latest.cpi.cpi_yoy.toFixed(1) +
                        "%"
                      : "-"
                  }}
                </div>
                <div class="env-sub">
                  同比 · {{ data.macro_latest?.cpi?.date ?? "-" }}
                </div>
                <div class="env-note" v-if="macroNotes.cpi">{{ macroNotes.cpi }}</div>
              </div>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <div class="env-card">
                <div class="env-label">PPI 工业生产者出厂价</div>
                <div class="env-main" style="font-size: 22px">
                  {{
                    data.macro_latest?.ppi?.ppi_yoy != null
                      ? (data.macro_latest.ppi.ppi_yoy > 0 ? "+" : "") +
                        data.macro_latest.ppi.ppi_yoy.toFixed(1) +
                        "%"
                      : "-"
                  }}
                </div>
                <div class="env-sub">
                  同比 · {{ data.macro_latest?.ppi?.date ?? "-" }}
                </div>
                <div class="env-note" v-if="macroNotes.ppi">{{ macroNotes.ppi }}</div>
              </div>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <div class="env-card">
                <div class="env-label">GDP 国内生产总值</div>
                <div class="env-main" style="font-size: 22px">
                  {{
                    data.macro_latest?.gdp?.gdp_yoy != null
                      ? (data.macro_latest.gdp.gdp_yoy > 0 ? "+" : "") +
                        data.macro_latest.gdp.gdp_yoy.toFixed(1) +
                        "%"
                      : "-"
                  }}
                </div>
                <div class="env-sub">
                  同比 · {{ data.macro_latest?.gdp?.date ?? "-" }}
                </div>
                <div class="env-note" v-if="macroNotes.gdp">{{ macroNotes.gdp }}</div>
              </div>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small" class="full-height-card card-body-center">
              <div class="env-card">
                <div class="env-label">近期事件</div>
                <template v-if="upcomingEvents.length">
                  <div
                    v-for="e in upcomingEvents"
                    :key="e.date"
                    class="env-event-row"
                  >
                    <span class="env-event-date">{{ e.date.slice(5) }}</span>
                    <span class="env-event-label">{{ e.label }}</span>
                  </div>
                </template>
                <div v-else class="env-sub">暂无近期事件</div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
        <!-- Row 4: 快捷入口 -->
        <n-card title="快捷入口" size="small" style="margin-top: 16px">
          <n-space>
            <n-button type="primary" ghost @click="nav('/market/screener')"
              >🔍 选股器</n-button
            >
            <n-button secondary @click="nav('/market/etf')"
              >📦 ETF 市场</n-button
            >
            <n-button secondary @click="nav('/market/limit-analysis')"
              >📈 涨跌停分析</n-button
            >
            <n-button secondary @click="nav('/market/financial-compare')"
              >📋 财务对比</n-button
            >
          </n-space>
        </n-card>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.market-dashboard {
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}
.index-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.idx-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: all 0.2s;
  &:hover {
    background: rgba(255, 255, 255, 0.08);
  }
  &.active {
    background: rgba(239, 83, 80, 0.1);
    border: 1px solid rgba(239, 83, 80, 0.3);
  }
  .idx-name {
    font-size: 12px;
    color: var(--n-text-color-3);
  }
  .idx-close {
    font-size: 15px;
    font-weight: 600;
    font-family: monospace;
    margin: 2px 0;
  }
  .idx-pct {
    font-size: 13px;
    font-weight: 600;
  }
}
.breadth-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  margin: 8px 0 16px;
}
.bar-up {
  background: #ef5350;
  transition: width 0.3s;
}
.bar-down {
  background: #26a69a;
  transition: width 0.3s;
}
.b-stat-row {
  display: flex;
  justify-content: space-around;
}
.b-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.15s;
  &:hover {
    background: rgba(255, 255, 255, 0.04);
  }
  .b-stat-num {
    font-size: 18px;
    font-weight: 700;
    font-family: monospace;
    &.up {
      color: #ef5350;
    }
    &.down {
      color: #26a69a;
    }
  }
  .b-stat-label {
    font-size: 11px;
    color: var(--n-text-color-3);
  }
  .b-stat-pct {
    font-size: 12px;
    font-weight: 500;
    &.up {
      color: #ef5350;
    }
    &.down {
      color: #26a69a;
    }
  }
}
.hsgt {
  .h-dir {
    text-align: center;
    font-size: 22px;
    line-height: 1;
    margin-bottom: 2px;
  }
  .h-main {
    text-align: center;
    margin: 6px 0 16px;
  }
  .h-val {
    font-size: 28px;
    font-weight: 700;
    font-family: monospace;
    color: #ff9800;
    &.up {
      color: #ef5350;
    }
    &.down {
      color: #26a69a;
    }
  }
  .h-unit {
    font-size: 14px;
    color: var(--n-text-color-3);
    margin-left: 4px;
  }
  .h-bar-wrap {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .h-bar-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }
  .h-bar-label {
    width: 18px;
    color: var(--n-text-color-3);
    text-align: center;
  }
  .h-bar-track {
    flex: 1;
    height: 4px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    overflow: hidden;
  }
  .h-bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s;
    &.sh {
      background: #ef5350;
    }
    &.sz {
      background: #2196f3;
    }
  }
  .h-bar-val {
    width: 72px;
    text-align: right;
    color: var(--n-text-color-2);
    font-family: monospace;
  }
}
.row-equal {
  align-items: stretch;
}
.full-height-card {
  height: 100%;
}
.card-body-center {
  :deep(.n-card__content) {
    display: flex;
    align-items: center;
    min-height: 0;
  }
}
.env-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 0;
  width: 100%;
  align-items: center;
  text-align: center;
}
.env-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.env-main {
  font-weight: 700;
  font-family: monospace;
}
.env-sub {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.env-note {
  font-size: 10px;
  color: var(--n-text-color-2);
  margin-top: 2px;
  line-height: 1.3;
}
.env-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
  font-size: 13px;
  padding: 0 8px;
}
.env-event-row {
  display: flex;
  gap: 8px;
  width: 100%;
  font-size: 11px;
  align-items: baseline;
  padding: 2px 0;
}
.env-event-date {
  color: var(--color-primary, #448aff);
  font-family: monospace;
  font-size: 10px;
  min-width: 42px;
}
.env-event-label {
  color: var(--n-text-color-2);
  flex: 1;
  text-align: left;
}
</style>
