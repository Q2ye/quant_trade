<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import {
  NCard, NSkeleton, NEmpty, NTag, NGrid, NGridItem,
} from "naive-ui";
import marketAPI from "@/api/market";
import type { MarketStateResponse } from "@/types/entities/market";
import LightweightLineChart, {
  type LineSeriesDef,
} from "@/components/charts/LightweightLineChart.vue";

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

// 宽度曲线（单系列）
const breadthSeries = computed<LineSeriesDef[]>(() => [{
  name: "宽度",
  color: "#448AFF",
  data: (data.value?.dates || []).map((d, i) => ({ time: d, value: data.value?.breadth[i] ?? null })),
}]);

// 深度曲线（涨停/跌停双系列）
const depthSeries = computed<LineSeriesDef[]>(() => [
  {
    name: "涨停",
    color: "#ef5350",
    data: (data.value?.limit_dates || []).map((d, i) => ({ time: d, value: data.value?.limit_up[i] ?? null })),
  },
  {
    name: "跌停",
    color: "#26a69a",
    data: (data.value?.limit_dates || []).map((d, i) => ({ time: d, value: data.value?.limit_down[i] ?? null })),
  },
]);

// 波动率曲线（单系列）
const volatilitySeries = computed<LineSeriesDef[]>(() => [{
  name: "波动率",
  color: "#ff9800",
  data: (data.value?.dates || []).map((d, i) => ({ time: d, value: data.value?.volatility[i] ?? null })),
}]);

const volPctl = computed(() => {
  const p = data.value?.latest.volatility_pctl;
  return p == null ? null : Math.round(p * 100);
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
    <n-grid :x-gap="16" :y-gap="16" :cols="24" responsive="screen">
      <!-- ① 牛熊仪表 -->
      <n-grid-item span="24 s:24 m:6 l:6">
        <n-card size="small" class="radar-card">
          <template #header>牛熊状态</template>
          <n-skeleton v-if="loading" :text="true" :repeat="3" />
          <n-empty v-else-if="error" description="加载失败" size="small" />
          <div v-else-if="data" class="regime-body">
            <n-tag :type="regimeType" size="large" round :bordered="false">
              {{ regimeLabel }}
            </n-tag>
            <div class="regime-sub">{{ data.latest.regime }}</div>
            <div class="year-line">
              年线门：
              <span :class="(data.latest.year_line_pct ?? 0) >= 0 ? 'up' : 'down'">
                {{ (data.latest.year_line_pct ?? 0) >= 0 ? "+" : "" }}{{ data.latest.year_line_pct?.toFixed(2) ?? "--" }}%
              </span>
            </div>
            <div class="year-line-note">中证500 相对 MA250</div>
          </div>
        </n-card>
      </n-grid-item>

      <!-- ② 宽度 -->
      <n-grid-item span="24 s:24 m:6 l:6">
        <n-card size="small" class="radar-card">
          <template #header>市场宽度</template>
          <div class="card-current" v-if="data">{{ (data.latest.breadth ?? 0).toFixed(2) }}</div>
          <LightweightLineChart
            :line-series="breadthSeries"
            :height="130"
            :loading="loading"
            empty-text="暂无宽度数据"
          />
        </n-card>
      </n-grid-item>

      <!-- ③ 深度（涨跌停家数） -->
      <n-grid-item span="24 s:24 m:12 l:6">
        <n-card size="small" class="radar-card">
          <template #header>市场深度（涨跌停家数）</template>
          <LightweightLineChart
            :line-series="depthSeries"
            :height="150"
            :loading="loading"
            empty-text="暂无涨跌停数据"
          />
        </n-card>
      </n-grid-item>

      <!-- ④ 恐慌贪婪 -->
      <n-grid-item span="24 s:24 m:12 l:6">
        <n-card size="small" class="radar-card">
          <template #header>恐慌贪婪</template>
          <div class="card-current" v-if="data">
            分位 {{ volPctl != null ? volPctl + "%" : "--" }}
          </div>
          <LightweightLineChart
            :line-series="volatilitySeries"
            :height="130"
            :loading="loading"
            empty-text="暂无波动率数据"
          />
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<style scoped>
.market-state-radar {
  margin-bottom: 16px;
}
.radar-card {
  height: 100%;
}
.regime-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}
.regime-sub {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.year-line {
  font-size: 13px;
  color: var(--n-text-color-2);
}
.year-line .up { color: #ef5350; }
.year-line .down { color: #26a69a; }
.year-line-note {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.card-current {
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin-bottom: 4px;
}
.header-hint {
  font-size: 11px;
  font-weight: 400;
  color: var(--n-text-color-3);
  margin-left: 8px;
}
</style>
