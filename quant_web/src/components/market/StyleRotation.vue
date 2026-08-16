<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { NCard, NSkeleton, NEmpty } from "naive-ui";
import marketAPI from "@/api/market";
import type { StyleRotationResponse } from "@/types/entities/market";
import LightweightLineChart, {
  type LineSeriesDef,
} from "@/components/charts/LightweightLineChart.vue";

const loading = ref(true);
const error = ref(false);
const data = ref<StyleRotationResponse | null>(null);

const indexColors: Record<string, string> = {
  "000300.SH": "#448AFF",
  "000905.SH": "#ff9800",
  "000852.SH": "#ef5350",
};

const indexSeries = computed<LineSeriesDef[]>(() => {
  const names = data.value?.index_names || {};
  const dates = data.value?.index_dates || [];
  return Object.entries(data.value?.index_series || {}).map(([code, vals]) => ({
    name: names[code] || code,
    color: indexColors[code] || "#999",
    data: dates.map((d, i) => ({ time: d, value: vals[i] ?? null })),
  }));
});

const topIndustries = computed(() => data.value?.industry_strength.slice(0, 8) || []);

// 当前风格结论：三条线最新值（首日=1）最高者 = 当前占优风格
const styleConclusion = computed(() => {
  const s = data.value?.index_series;
  const names = data.value?.index_names || {};
  if (!s) return null;
  const latest: Record<string, number> = {};
  for (const [code, vals] of Object.entries(s)) {
    if (vals.length) latest[code] = vals[vals.length - 1];
  }
  const codes = Object.keys(latest);
  if (!codes.length) return null;
  const best = codes.reduce((a, b) => (latest[a] > latest[b] ? a : b));
  if (best === "000852.SH")
    return { text: "小盘占优", color: "#ef5350", lead: names[best] || "中证1000" };
  if (best === "000905.SH")
    return { text: "中盘占优", color: "#ff9800", lead: names[best] || "中证500" };
  return { text: "大盘占优", color: "#448aff", lead: names[best] || "沪深300" };
});

async function load() {
  loading.value = true;
  error.value = false;
  try {
    data.value = await marketAPI.getStyleRotation(60);
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <n-card size="small" class="style-rotation">
    <template #header>风格轮动（大盘 vs 小盘 + 行业强度）</template>
    <n-skeleton v-if="loading" :text="true" :repeat="4" />
    <n-empty v-else-if="error" description="加载失败" size="small" />
    <template v-else-if="data">
      <div class="sr-layout">
        <div class="sr-chart">
          <LightweightLineChart
            :line-series="indexSeries"
            :height="240"
            :loading="false"
            empty-text="暂无指数数据"
          />
          <div class="sr-conclusion" v-if="styleConclusion">
            <span class="sr-conclusion-label">当前风格</span>
            <b :style="{ color: styleConclusion.color }">{{ styleConclusion.text }}</b>
            <span class="sr-lead">（{{ styleConclusion.lead }} 领先）</span>
          </div>
        </div>
        <div class="sr-industry">
          <div class="sr-industry-title">行业强度 Top（近30日）</div>
          <div v-for="it in topIndustries" :key="it.name" class="sr-ind-row">
            <span class="sr-ind-name">{{ it.name }}</span>
            <span :class="it.ret_30d >= 0 ? 'up' : 'down'">
              {{ it.ret_30d >= 0 ? "+" : "" }}{{ it.ret_30d.toFixed(1) }}%
            </span>
          </div>
          <div class="sr-note">三条线 = 沪深300/中证500/中证1000 近 60 日相对强弱（首日=1）；线越高代表该风格越强</div>
        </div>
      </div>
    </template>
  </n-card>
</template>

<style scoped>
.style-rotation {
  height: 100%;
}
.sr-layout {
  display: flex;
  gap: 16px;
  height: 100%;
  align-items: flex-start;
}
.sr-chart {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.sr-conclusion {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  padding-top: 4px;
  margin-top: auto;
  .sr-conclusion-label {
    color: var(--n-text-color-3);
  }
  .sr-lead {
    font-size: 11px;
    color: var(--n-text-color-3);
  }
}
.sr-industry {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}
.sr-industry-title {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-bottom: 6px;
}
.sr-ind-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
}
.sr-ind-name {
  color: var(--n-text-color-2);
}
.sr-note {
  font-size: 10px;
  line-height: 1.5;
  color: var(--n-text-color-3);
  margin-top: auto;
  padding-top: 8px;
}
.up { color: #ef5350; }
.down { color: #26a69a; }
@media (max-width: 768px) {
  .sr-layout { flex-direction: column; }
  .sr-industry { width: 100%; }
}
</style>
