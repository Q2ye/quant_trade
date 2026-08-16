<script setup lang="ts">
// 四维状态雷达（v5，lightweight-charts 5 版）—— 顶部状态条 + 单图四线
// 三条曲线 = 宽度 / 涨停家数 / 波动率 每日值在各自可用窗口内的分位（0~100），
// 虚线"基准线"= 50（窗口内中位）。x 坐标均为时间（epoch 线性时间轴，自动按日期对齐）。
import { ref, computed, onMounted } from "vue";
import { NSkeleton, NEmpty, NTag } from "naive-ui";
import marketAPI from "@/api/market";
import type { MarketStateResponse } from "@/types/entities/market";
import LightweightLineChart, {
  type LineSeriesDef,
} from "@/components/charts/LightweightLineChart.vue";
import PctlBar from "@/components/market/PctlBar.vue";

const loading = ref(true);
const error = ref(false);
const data = ref<MarketStateResponse | null>(null);

const regimeLabel = computed(() => {
  const r = data.value?.latest.regime;
  if (r === "BULL") return "牛市";
  if (r === "BEAR") return "熊市";
  return "震荡";
});
const regimeType = computed<"success" | "error" | "warning">(() => {
  const r = data.value?.latest.regime;
  if (r === "BULL") return "success";
  if (r === "BEAR") return "error";
  return "warning";
});

const volPctl = computed(() => {
  const p = data.value?.latest.volatility_pctl;
  return p == null ? null : Math.round(p * 100);
});
const breadthPctl = computed(() => data.value?.latest.breadth_pctl ?? null);
const limitUpPctl = computed(() => data.value?.latest.limit_up_pctl ?? null);

// 分位化序列：每日值在"自身可用窗口"中的分位（0~100，null 占位 → lightweight-charts 按时间对齐并断线）
function rankPctSeries(vals: (number | null)[]): (number | null)[] {
  const avail = vals.filter((v): v is number => v != null);
  return vals.map((v) => {
    if (v == null) return null;
    const le = avail.filter((x) => x <= v).length;
    return Math.round((le / Math.max(avail.length, 1)) * 1000) / 10;
  });
}

const seriesDefs = computed<LineSeriesDef[]>(() => {
  const d = data.value;
  if (!d || !d.dates.length) return [];
  const dates = d.dates.map((x) => String(x));
  // 涨跌停数据可能短于 60 日（未同步完整）→ 按日期对齐，缺失处 null
  const limitByDate = new Map<string, number>();
  d.limit_dates.forEach((dt, i) => limitByDate.set(String(dt), d.limit_up[i]));
  const limitRaw = d.dates.map((dt) => limitByDate.get(String(dt)) ?? null);
  const breadthP = rankPctSeries([...d.breadth]);
  const limitP = rankPctSeries(limitRaw);
  const volP = rankPctSeries([...d.volatility]);
  return [
    {
      name: "宽度",
      color: "#448aff",
      data: dates.map((t, i) => ({ time: t, value: breadthP[i] })),
    },
    {
      name: "涨停家数",
      color: "#ef5350",
      data: dates.map((t, i) => ({ time: t, value: limitP[i] })),
    },
    {
      name: "波动率",
      color: "#ff9800",
      data: dates.map((t, i) => ({ time: t, value: volP[i] })),
    },
    {
      name: "基准线",
      color: "rgba(255,255,255,0.35)",
      lineStyle: 2, // Dashed
      lineWidth: 1,
      data: dates.map((t) => ({ time: t, value: 50 })),
    },
  ];
});

async function load() {
  loading.value = true;
  error.value = false;
  try {
    data.value = await marketAPI.getMarketState(60);
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="market-state-radar">
    <n-skeleton v-if="loading" :text="true" :repeat="4" />
    <n-empty v-else-if="error" description="加载失败" size="small" />
    <template v-else-if="data">
      <!-- 顶部状态条：牛熊 + 年线 + 三维当前分位 -->
      <div class="rs-header">
        <div class="rs-regime">
          <n-tag :type="regimeType" size="small" round :bordered="false">
            {{ regimeLabel }}
          </n-tag>
          <span class="rs-year">
            年线
            <b :class="(data.latest.year_line_pct ?? 0) >= 0 ? 'up' : 'down'">
              {{ (data.latest.year_line_pct ?? 0) >= 0 ? "+" : ""
              }}{{ data.latest.year_line_pct?.toFixed(2) ?? "--" }}%
            </b>
          </span>
        </div>
        <div class="rs-pctls">
          <div class="rs-pctl">
            <span class="rs-pctl-label">宽度</span>
            <PctlBar :value="breadthPctl" color="#448aff" />
          </div>
          <div class="rs-pctl">
            <span class="rs-pctl-label">涨停</span>
            <PctlBar :value="limitUpPctl" color="#ef5350" />
          </div>
          <div class="rs-pctl">
            <span class="rs-pctl-label">波动</span>
            <PctlBar :value="volPctl" color="#ff9800" />
          </div>
        </div>
      </div>
      <!-- 单图四线：x = 时间（lightweight-charts，滚轮缩放 / 拖拽平移） -->
      <div class="rs-chart">
        <LightweightLineChart
          :line-series="seriesDefs"
          :height="200"
          :loading="false"
          empty-text="暂无状态数据"
        />
      </div>
      <div class="radar-note">
        曲线 = 每日值在各自可用窗口内的分位（0~100）· 虚线 50 = 基准线（窗口内中位）· 牛熊 = MA20/60 体系 · 年线 = MA250
      </div>
    </template>
  </div>
</template>

<style scoped>
.market-state-radar {
  padding: 4px 0;
}
.rs-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.rs-regime {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.rs-year {
  font-size: 11px;
  color: var(--n-text-color-3);
  b {
    font-weight: 600;
  }
  .up {
    color: #ef5350;
  }
  .down {
    color: #26a69a;
  }
}
.rs-pctls {
  flex: 1;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.rs-pctl {
  display: flex;
  align-items: center;
  gap: 6px;
}
.rs-pctl-label {
  width: 28px;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--n-text-color-3);
  text-align: right;
}
.rs-chart {
  margin-top: 4px;
}
.radar-note {
  margin-top: 4px;
  font-size: 10px;
  line-height: 1.4;
  color: var(--n-text-color-3);
  text-align: center;
}
</style>
