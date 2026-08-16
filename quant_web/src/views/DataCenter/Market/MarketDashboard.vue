<script setup lang="ts">
// 市场总览 Dashboard v5 —— 市场状态驾驶舱（L0 状态条 → L1 状态 → L2 机会 → L3 情绪资金 → L4 风险折叠）
// 布局依据：docs/02-功能设计/市场模块/Market概览页重设计方案v5.md §4.6
import { computed, h, onMounted, onUnmounted, ref } from "vue";
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
  NCollapse,
  NCollapseItem,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import marketAPI from "@/api/market";
import type {
  DashboardOverview,
  TopVolumeItem,
  TopMoneyflowItem,
  MarketTemperature,
  LimitLadder,
  BreadthLeaders,
  Crowding,
  BreadthMetrics,
} from "@/types/entities/market";
import SmartIcon from "@/components/common/SmartIcon.vue";
import StyleRotation from "@/components/market/StyleRotation.vue";
import MarketTemperatureGauge from "@/components/market/MarketTemperatureGauge.vue";
import PositionAdviceCard from "@/components/market/PositionAdviceCard.vue";
import LimitLadderCard from "@/components/market/LimitLadderCard.vue";
import BreadthLeadersCard from "@/components/market/BreadthLeadersCard.vue";
import WatchlistStrip from "@/components/market/WatchlistStrip.vue";
import CrowdingCard from "@/components/market/CrowdingCard.vue";
import VolatilityPercentileCard from "@/components/market/VolatilityPercentileCard.vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
use([CanvasRenderer, BarChart, GridComponent, TooltipComponent]);

const router = useRouter();
const loading = ref(true);
const error = ref(false);
const data = ref<DashboardOverview | null>(null);
const temperature = ref<MarketTemperature | null>(null);
const limitLadder = ref<LimitLadder | null>(null);
const breadthLeaders = ref<BreadthLeaders | null>(null);
const crowding = ref<Crowding | null>(null);
const breadthMetrics = ref<BreadthMetrics | null>(null);
const sectorMoneyflow = ref<{ name: string; net_amount_yi: number }[]>([]);
const watchlist = ref<any[]>([]);
const swHeatmap = ref<any[]>([]);
const industryWindow = ref("pct_1d");
const focusSectors = ref(false);

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
  // P2：仅保留未来 7 天内的事件（宏观日历 7 天化）
  const limit = new Date(today.getTime() + 7 * 86400000);
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
    .filter((e) => {
      const d = new Date(e.date + "T00:00:00");
      return d >= today && d <= limit;
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
const fmtPct = (v: number | null) => (v == null ? "—" : v.toFixed(0) + "%");

// ---- 拥挤行业集合（分位>80%，用于行业轮动柱图标记） ----
const crowdedNames = computed(() => {
  const s = new Set<string>();
  for (const c of crowding.value?.top_crowded_industries ?? []) {
    if (c.percentile > 80) s.add(c.name);
  }
  return s;
});

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

// ---- HSGT bars（北向当日 沪/深） ----
const hBarSH = computed(() => {
  const hsgt = data.value?.hsgt_flow;
  if (!hsgt) return 0;
  const sh = Math.abs(hsgt.sh_inflow ?? 0);
  const sz = Math.abs(hsgt.sz_inflow ?? 0);
  const total = sh + sz;
  return total > 0 ? (sh / total) * 100 : 50;
});
const hBarSZ = computed(() => 100 - hBarSH.value);

// ---- 行业轮动柱图 (multi-window) ----
const industryWindows = [
  { key: "pct_1d", label: "1日" },
  { key: "pct_5d", label: "5日" },
  { key: "pct_10d", label: "10日" },
  { key: "pct_20d", label: "20日" },
  { key: "pct_30d", label: "30日" },
  { key: "pct_60d", label: "60日" },
];
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
    grid: { top: 5, right: 80, bottom: 5, left: 80 },
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
        const crowded = crowdedNames.value.has(item.name);
        return (
          "<strong>" +
          item.name +
          (crowded ? " ⚠拥挤" : "") +
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
          label: crowdedNames.value.has(items[i].name)
            ? { show: true, position: "right", formatter: "⚠拥挤", fontSize: 9, color: "#ff9800" }
            : undefined,
        })),
        barMaxWidth: 18,
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.3)" },
        },
      },
    ],
  };
});

// ---- 主力订单四单结构（全市场 TOP10 汇总，单位万元 → /1e4 = 亿） ----
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

// ---- 北向近 20 日净流入迷你柱图（补足 L3A 北向+主力卡内容） ----
const hsgtHistory = ref<any[]>([]);
const hsgtMiniOption = computed(() => {
  if (!hsgtHistory.value.length) return null;
  // 接口返回倒序（最新在前）→ 反转后取最后 20 条，保证 x 轴时间升序
  const items = [...hsgtHistory.value].reverse().slice(-20);
  return {
    grid: { top: 4, right: 4, bottom: 4, left: 4 },
    xAxis: {
      type: "category",
      data: items.map((d: any) => (d.trade_date ?? "").slice(5)),
      axisLabel: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    tooltip: {
      trigger: "axis",
      formatter: (ps: any[]) => {
        const p = ps[0];
        const it = items[p.dataIndex];
        return (
          it.trade_date +
          "<br/>净流入: " +
          ((it.net_inflow ?? 0) / 1e4).toFixed(1) +
          "亿"
        );
      },
    },
    series: [
      {
        type: "bar",
        data: items.map((d: any) => ({
          value: +(((d.net_inflow ?? 0) / 1e4).toFixed(1)),
          itemStyle: { color: (d.net_inflow ?? 0) >= 0 ? "#ef5350" : "#26a69a" },
        })),
        barMaxWidth: 10,
      },
    ],
  };
});

function loadHsgtHistory() {
  marketAPI
    .getHsgtHistory(20)
    .then((h) => {
      hsgtHistory.value = h || [];
    })
    .catch(() => {});
}

// ---- 行业资金强度：纯 CSS 双向条形图（流入 TOP8 红向右 / 流出 TOP5 绿向左，零轴居中） ----
const sectorTop = computed(() => {
  const rows = sectorMoneyflow.value.map((r) => ({
    name: r.name,
    net: Number(r.net_amount_yi) || 0,
  }));
  // 流入 TOP5 + 流出 TOP5 = 10 行，避免超出 span4 卡高
  const up = rows.filter((r) => r.net > 0).slice(0, 5);
  const down = rows.filter((r) => r.net < 0).slice(-5);
  return [...up, ...down].sort((a, b) => b.net - a.net);
});
const sectorMax = computed(() =>
  Math.max(1, ...sectorTop.value.map((r) => Math.abs(r.net))),
);

function nav(p: string) {
  router.push(p);
}
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
      h("span", { style: { color: pctColor(r.pct_chg ?? null) } }, pctText(r.pct_chg ?? null)),
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
      h("span", { style: { color: pctColor(r.pct_chg ?? null) } }, pctText(r.pct_chg ?? null)),
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

// ---- 数据加载（allSettled 并行，单失败不阻塞） ----
async function loadWatchlist() {
  marketAPI
    .getWatchlist()
    .then((w) => {
      watchlist.value = w || [];
    })
    .catch(() => {});
}

async function loadHeatmap() {
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
}

async function load() {
  loading.value = true;
  error.value = false;
  // P2 性能：首屏优先 —— overview（自带 60s 缓存，约 1s）先渲染，其余 6 端点后台并行填充，
  // 避免冷启动被温度计等 4~6s 的重查询拖住首屏
  marketAPI
    .getDashboardOverview()
    .then((d) => {
      if (d) data.value = d;
      else error.value = true;
    })
    .catch(() => {
      error.value = true;
    })
    .finally(() => {
      loading.value = false;
    });
  Promise.allSettled([
    marketAPI.getMarketTemperature(),
    marketAPI.getLimitLadder(),
    marketAPI.getBreadthLeaders(),
    marketAPI.getSectorMoneyflow(),
    marketAPI.getCrowding(),
    marketAPI.getBreadthMetrics(),
  ]).then(([tp, ld, brd, sec, cwd, bmt]) => {
    if (tp.status === "fulfilled") temperature.value = tp.value;
    if (ld.status === "fulfilled") limitLadder.value = ld.value;
    if (brd.status === "fulfilled") breadthLeaders.value = brd.value;
    if (sec.status === "fulfilled") sectorMoneyflow.value = sec.value || [];
    if (cwd.status === "fulfilled") crowding.value = cwd.value;
    if (bmt.status === "fulfilled") breadthMetrics.value = bmt.value;
  });
  loadWatchlist();
  loadHeatmap();
  loadHsgtHistory();
}

// ---- 轮询：L1 组 60s / L2-L3 组 120s；页面隐藏时跳过 ----
let timers: number[] = [];
async function pollL1() {
  if (document.hidden) return;
  marketAPI
    .getDashboardOverview()
    .then((d) => {
      if (d) data.value = d;
    })
    .catch(() => {});
  marketAPI
    .getMarketTemperature()
    .then((t) => {
      if (t) temperature.value = t;
    })
    .catch(() => {});
  marketAPI
    .getLimitLadder()
    .then((l) => {
      if (l) limitLadder.value = l;
    })
    .catch(() => {});
}
async function pollL2() {
  if (document.hidden) return;
  marketAPI
    .getBreadthLeaders()
    .then((b) => {
      if (b) breadthLeaders.value = b;
    })
    .catch(() => {});
  marketAPI
    .getSectorMoneyflow()
    .then((s) => {
      if (s) sectorMoneyflow.value = s || [];
    })
    .catch(() => {});
  marketAPI
    .getCrowding()
    .then((c) => {
      if (c) crowding.value = c;
    })
    .catch(() => {});
  marketAPI
    .getBreadthMetrics()
    .then((m) => {
      if (m) breadthMetrics.value = m;
    })
    .catch(() => {});
  loadHeatmap();
  loadHsgtHistory();
}

onMounted(() => {
  load();
  timers.push(window.setInterval(pollL1, 60000));
  timers.push(window.setInterval(pollL2, 120000));
});
onUnmounted(() => timers.forEach((t) => window.clearInterval(t)));
</script>

<template>
  <div class="market-dashboard bg-gradient-mesh bg-noise">
    <!-- Page Header (global pattern) -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场总览</h1>
          <p class="page-description" v-if="data">
            市场状态驾驶舱 ｜ {{ data.market_breadth.total }} 只股票有行情
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
        <!-- L0 数据状态条 -->
        <div class="l0-status-bar">
          <div class="l0-left">
            <span class="l0-text">数据截止 {{ dataDateText }}</span>
            <span class="l0-muted">· 60s 自动刷新（L1 组 60s / L2-L3 组 120s）</span>
          </div>
          <div class="l0-right">
            <n-button size="tiny" quaternary @click="nav('/market/screener')">🔍 选股</n-button>
            <n-button size="tiny" quaternary @click="nav('/market/etf')">📦 ETF</n-button>
            <n-button size="tiny" quaternary @click="nav('/market/limit-analysis')">📈 涨跌停</n-button>
            <n-button size="tiny" quaternary @click="nav('/market/financial-compare')">📋 财务</n-button>
          </div>
        </div>

        <!-- L1 市场状态驾驶舱：温度计(4) + 仓位卡(2) + 涨停梯队(3) + 核心指数(3) -->
        <n-grid :x-gap="16" :y-gap="16" :cols="12" responsive="screen" class="row-equal">
          <n-grid-item :span="4" s="12" m="6">
            <MarketTemperatureGauge :data="temperature" :loading="loading" />
          </n-grid-item>
          <n-grid-item :span="2" s="12" m="6">
            <PositionAdviceCard :temperature="temperature?.temperature ?? null" />
          </n-grid-item>
          <n-grid-item :span="3" s="12" m="6">
            <LimitLadderCard :data="limitLadder" :loading="loading" />
          </n-grid-item>
          <n-grid-item :span="3" s="12" m="6">
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
        </n-grid>

        <!-- L2 机会地图：行业轮动(5) + 风格因子(3) + 强弱榜(4) -->
        <n-grid :x-gap="16" :y-gap="16" :cols="12" responsive="screen" class="row-equal" style="margin-top: 16px">
          <n-grid-item :span="5" s="12" m="6">
            <n-card title="申万行业轮动" size="small" class="full-height-card">
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
              <div style="height: 320px">
                <VChart
                  v-if="industryBarOption"
                  :option="industryBarOption"
                  autoresize
                  style="height: 320px"
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
          </n-grid-item>
          <n-grid-item :span="3" s="12" m="6">
            <StyleRotation />
          </n-grid-item>
          <n-grid-item :span="4" s="12" m="12">
            <BreadthLeadersCard :data="breadthLeaders" :loading="loading" />
          </n-grid-item>
        </n-grid>

        <!-- 自选股条（折叠，移出首屏） -->
        <div v-if="watchlist.length" style="margin-top: 12px">
          <WatchlistStrip :items="watchlist" :loading="loading" />
        </div>

        <!-- L3 情绪与资金 · 行A：北向+主力(4) + 行业资金强度(4) + 成交额TOP10(4) -->
        <n-grid :x-gap="16" :y-gap="16" :cols="12" responsive="screen" class="row-equal" style="margin-top: 16px">
          <n-grid-item :span="4" s="12" m="6">
            <n-card size="small" class="full-height-card" title="北向 + 主力订单">
              <template #header-extra>
                <n-button size="tiny" quaternary @click="nav('/market/money-flow')">详情 →</n-button>
              </template>
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
                      >{{ ((data.hsgt_flow.net_inflow ?? 0) / 1e4).toFixed(1) }}</span
                    ><span class="h-unit">亿</span>
                  </div>
                  <div class="h-bar-wrap">
                    <div class="h-bar-item">
                      <span class="h-bar-label">沪</span>
                      <div class="h-bar-track">
                        <div class="h-bar-fill sh" :style="{ width: hBarSH + '%' }" />
                      </div>
                      <span class="h-bar-val"
                        >{{ (data.hsgt_flow.sh_inflow ?? 0) > 0 ? "+" : ""
                        }}{{
                          data.hsgt_flow.sh_inflow
                            ? (data.hsgt_flow.sh_inflow / 1e4).toFixed(1)
                            : "0"
                        }}亿</span
                      >
                    </div>
                    <div class="h-bar-item">
                      <span class="h-bar-label">深</span>
                      <div class="h-bar-track">
                        <div class="h-bar-fill sz" :style="{ width: hBarSZ + '%' }" />
                      </div>
                      <span class="h-bar-val"
                        >{{ (data.hsgt_flow.sz_inflow ?? 0) > 0 ? "+" : ""
                        }}{{
                          data.hsgt_flow.sz_inflow
                            ? (data.hsgt_flow.sz_inflow / 1e4).toFixed(1)
                            : "0"
                        }}亿</span
                      >
                    </div>
                  </div>
                </div>
              </template>
              <n-empty v-else description="暂无" size="small" />
              <div class="hsgt-mini">
                <div class="hsgt-mini-title">近 20 日净流入（亿）</div>
                <VChart
                  v-if="hsgtMiniOption"
                  :option="hsgtMiniOption"
                  autoresize
                  style="height: 64px"
                />
                <n-empty v-else description="暂无" size="small" style="padding: 4px" />
              </div>
              <div v-if="orderSummary" class="order-summary">
                <div v-for="o in orderSummary" :key="o.label" class="order-row">
                  <span>{{ o.label }}</span
                  ><span :style="{ color: o.net >= 0 ? '#ef5350' : '#26a69a' }"
                    >{{ (o.net / 1e4).toFixed(1) }}亿</span
                  >
                </div>
              </div>
            </n-card>
          </n-grid-item>
          <n-grid-item :span="4" s="12" m="6">
            <n-card size="small" class="full-height-card" title="行业资金强度 TOP">
              <template #header-extra>
                <n-button size="tiny" quaternary @click="nav('/market/money-flow')">详情 →</n-button>
              </template>
              <div class="sector-sub">
                当日主力净流入 · 东财行业聚合 · 与风格轮动的"申万 30 日涨幅榜"口径不同（价 vs 资金）
              </div>
              <div v-if="sectorTop.length" class="sector-bars">
                <div v-for="s in sectorTop" :key="s.name" class="sbar-row">
                  <span class="sbar-name">{{ s.name }}</span>
                  <div class="sbar-track">
                    <div class="sbar-zero" />
                    <div
                      class="sbar-fill"
                      :class="s.net >= 0 ? 'pos' : 'neg'"
                      :style="
                        s.net >= 0
                          ? { left: '50%', width: (Math.abs(s.net) / sectorMax) * 50 + '%' }
                          : { right: '50%', width: (Math.abs(s.net) / sectorMax) * 50 + '%' }
                      "
                    />
                  </div>
                  <span class="sbar-val" :class="s.net >= 0 ? 'up' : 'down'">
                    {{ s.net > 0 ? "+" : "" }}{{ s.net.toFixed(1) }}亿
                  </span>
                </div>
              </div>
              <n-empty v-else description="暂无数据" size="small" />
            </n-card>
          </n-grid-item>
          <n-grid-item :span="4" s="12" m="12">
            <n-card title="成交额 TOP10" size="small" class="full-height-card">
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
                max-height="260"
                :row-props="
                  (row: TopVolumeItem) => ({
                    style: 'cursor:pointer',
                    onClick: () => nav('/market/stock/' + row.ts_code),
                  })
                "
              />
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- L3 情绪与资金 · 行B：资金流入TOP10(6) + 涨跌统计(6) -->
        <n-grid :x-gap="16" :y-gap="16" :cols="12" responsive="screen" class="row-equal" style="margin-top: 16px">
          <n-grid-item :span="6" s="12">
            <n-card title="资金流入 TOP10" size="small" class="full-height-card">
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
                max-height="260"
                :row-props="
                  (row: TopMoneyflowItem) => ({
                    style: 'cursor:pointer',
                    onClick: () => nav('/market/stock/' + row.ts_code),
                  })
                "
              />
            </n-card>
          </n-grid-item>
          <n-grid-item :span="6" s="12">
            <n-card title="涨跌统计 · 市场宽度" size="small" class="full-height-card breadth-card">
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
                <div v-if="breadthMetrics" class="width-metrics">
                  <div class="w-row">
                    <span class="w-item"
                      >新高 <b class="up">{{ breadthMetrics.new_highs ?? "—" }}</b></span
                    >
                    <span class="w-item"
                      >新低 <b class="down">{{ breadthMetrics.new_lows ?? "—" }}</b></span
                    >
                  </div>
                  <div class="w-ma-row">
                    <span class="w-ma-label">全市场 MA20</span>
                    <div class="w-ma-track">
                      <div
                        class="w-ma-fill"
                        :style="{ width: (breadthMetrics.above_ma20_market ?? 0) + '%' }"
                      />
                    </div>
                    <span class="w-ma-val">{{ fmtPct(breadthMetrics.above_ma20_market) }}</span>
                  </div>
                  <div class="w-ma-row">
                    <span class="w-ma-label">全市场 MA60</span>
                    <div class="w-ma-track">
                      <div
                        class="w-ma-fill"
                        :style="{ width: (breadthMetrics.above_ma60_market ?? 0) + '%' }"
                      />
                    </div>
                    <span class="w-ma-val">{{ fmtPct(breadthMetrics.above_ma60_market) }}</span>
                  </div>
                  <div class="w-note">
                    沪深300：MA20 {{ fmtPct(breadthMetrics.above_ma20_hs300) }} · MA60
                    {{ fmtPct(breadthMetrics.above_ma60_hs300) }}
                  </div>
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- L4 风险与日历（默认折叠：拥挤度 / 波动率分位 / 宏观事件） -->
        <n-collapse style="margin-top: 16px" :default-expanded-names="[]">
          <n-collapse-item
            title="风险与日历（拥挤度 · 波动率分位 · 宏观事件 7 天，默认折叠）"
            name="risk-l4"
          >
            <n-grid :x-gap="16" :y-gap="16" :cols="24" responsive="screen">
              <n-grid-item span="8 s:24 m:12 l:8">
                <CrowdingCard :data="crowding" :loading="loading" />
              </n-grid-item>
              <n-grid-item span="8 s:24 m:12 l:8">
                <VolatilityPercentileCard :data="breadthMetrics" :loading="loading" />
              </n-grid-item>
              <n-grid-item span="8 s:24 m:12 l:8">
                <n-card size="small" class="full-height-card" title="宏观 + 事件日历">
                  <n-grid :x-gap="8" :y-gap="8" :cols="2">
                    <n-grid-item>
                      <div class="env-card">
                        <div class="env-label">CPI 居民消费价格</div>
                        <div class="env-main" style="font-size: 20px">
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
                    </n-grid-item>
                    <n-grid-item>
                      <div class="env-card">
                        <div class="env-label">PPI 工业生产者出厂价</div>
                        <div class="env-main" style="font-size: 20px">
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
                    </n-grid-item>
                    <n-grid-item>
                      <div class="env-card">
                        <div class="env-label">GDP 国内生产总值</div>
                        <div class="env-main" style="font-size: 20px">
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
                    </n-grid-item>
                    <n-grid-item>
                      <div class="env-card">
                        <div class="env-label">近期事件（未来 7 天）</div>
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
                    </n-grid-item>
                  </n-grid>
                </n-card>
              </n-grid-item>
            </n-grid>
          </n-collapse-item>
        </n-collapse>
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
// ---- L0 数据状态条 ----
.l0-status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  .l0-text {
    font-size: 12px;
    color: var(--n-text-color-2);
  }
  .l0-muted {
    font-size: 11px;
    color: var(--n-text-color-3);
  }
  .l0-right {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
}
// ---- 核心指数 ----
.index-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 6px;
  height: 100%;
}
.idx-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
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
// ---- 涨跌统计 ----
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
// ---- 北向资金 ----
.hsgt {
  .h-dir {
    text-align: center;
    font-size: 22px;
    line-height: 1;
    margin-bottom: 2px;
  }
  .h-main {
    text-align: center;
    margin: 6px 0 12px;
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
// ---- 主力订单 / 行业资金 ----
.order-summary {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 9px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
  padding-top: 10px;
  .order-row {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
  }
}
.sector-bars {
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  gap: 10px;
  padding: 6px 0;
  height: 100%;
}
.sector-sub {
  font-size: 11px;
  line-height: 1.4;
  color: var(--n-text-color-3);
  margin-bottom: 4px;
}
.sbar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.sbar-name {
  width: 70px;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--n-text-color-2);
}
.sbar-track {
  position: relative;
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.04);
}
.sbar-zero {
  position: absolute;
  left: 50%;
  top: -3px;
  bottom: -3px;
  width: 1px;
  background: rgba(255, 255, 255, 0.3);
}
.sbar-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 4px;
  &.pos {
    background: linear-gradient(90deg, #ff9800, #ef5350);
  }
  &.neg {
    background: linear-gradient(90deg, #448aff, #26a69a);
  }
}
.sbar-val {
  width: 58px;
  flex-shrink: 0;
  text-align: right;
  font-family: monospace;
  &.up {
    color: #ef5350;
  }
  &.down {
    color: #26a69a;
  }
}
// ---- 市场宽度 ----
.breadth-card {
  :deep(.n-card__content) {
    display: flex;
    height: calc(100% - 40px);
  }
}
.breadth {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
}
.width-metrics {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
  .w-row {
    display: flex;
    justify-content: space-around;
    flex-wrap: wrap;
    gap: 8px;
  }
  .w-item {
    font-size: 12px;
    color: var(--n-text-color-3);
    b {
      color: var(--n-text-color-2);
      &.up {
        color: #ef5350;
      }
      &.down {
        color: #26a69a;
      }
    }
  }
  .w-ma-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    .w-ma-label {
      width: 86px;
      color: var(--n-text-color-3);
      text-align: right;
      flex-shrink: 0;
    }
    .w-ma-track {
      flex: 1;
      height: 6px;
      border-radius: 3px;
      background: rgba(255, 255, 255, 0.06);
      overflow: hidden;
      .w-ma-fill {
        height: 100%;
        border-radius: 3px;
        background: linear-gradient(90deg, #448aff, #26a69a);
        transition: width 0.3s;
      }
    }
    .w-ma-val {
      width: 40px;
      font-family: monospace;
      color: var(--n-text-color-2);
      text-align: right;
    }
  }
  .w-note {
    font-size: 11px;
    color: var(--n-text-color-3);
    text-align: center;
  }
}
// ---- 北向 20 日迷你图 ----
.hsgt-mini {
  margin-top: 10px;
  .hsgt-mini-title {
    font-size: 11px;
    color: var(--n-text-color-3);
    margin-bottom: 2px;
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
// ---- P2 移动端适配 ----
@media (max-width: 768px) {
  .l0-muted {
    display: none;
  }
  .market-dashboard {
    padding-bottom: 12px;
  }
  .l0-right {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
