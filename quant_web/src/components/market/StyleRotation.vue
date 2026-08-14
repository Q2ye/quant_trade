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
            :height="200"
            :loading="false"
            empty-text="暂无指数数据"
          />
          <div class="sr-note">首日=1 归一化，沪深300/中证500/中证1000 相对强弱</div>
        </div>
        <div class="sr-industry">
          <div class="sr-industry-title">行业强度 Top（近30日）</div>
          <div v-for="it in topIndustries" :key="it.name" class="sr-ind-row">
            <span class="sr-ind-name">{{ it.name }}</span>
            <span :class="it.ret_30d >= 0 ? 'up' : 'down'">
              {{ it.ret_30d >= 0 ? "+" : "" }}{{ it.ret_30d.toFixed(1) }}%
            </span>
          </div>
        </div>
      </div>
    </template>
  </n-card>
</template>

<style scoped>
.style-rotation {
  margin-bottom: 16px;
}
.sr-layout {
  display: flex;
  gap: 16px;
}
.sr-chart {
  flex: 1;
  min-width: 0;
}
.sr-note {
  font-size: 11px;
  color: var(--n-text-color-3);
  margin-top: 4px;
}
.sr-industry {
  width: 200px;
  flex-shrink: 0;
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
.up { color: #ef5350; }
.down { color: #26a69a; }
@media (max-width: 768px) {
  .sr-layout { flex-direction: column; }
  .sr-industry { width: 100%; }
}
</style>
