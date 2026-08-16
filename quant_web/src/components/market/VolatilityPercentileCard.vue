<script setup lang="ts">
// 波动率分位卡（v5 N5，L4 span8）—— 沪深300 20日年化波动率 + 750日分位 + 收缩/扩张结论
import { computed } from "vue";
import { NSkeleton, NEmpty } from "naive-ui";
import type { BreadthMetrics } from "@/types/entities/market";

const props = defineProps<{
  data: BreadthMetrics | null;
  loading: boolean;
}>();

const vol = computed(() => props.data?.volatility ?? null);

const phase = computed(() => {
  const p = vol.value?.percentile;
  if (p == null) return null;
  if (p > 70) return { label: "波动扩张", color: "#ef5350" };
  if (p < 30) return { label: "波动收缩", color: "#26a69a" };
  return { label: "波动常态", color: "#ff9800" };
});
</script>

<template>
  <n-card size="small" class="full-height-card" title="波动率分位（沪深300）">
    <n-skeleton v-if="loading && !data" :text="true" :repeat="3" />
    <n-empty v-else-if="!data || !vol" description="暂无数据" size="small" style="padding: 24px" />
    <div v-else class="vol-body">
      <div class="vol-main">
        {{ vol.value_20d != null ? vol.value_20d.toFixed(1) + "%" : "—" }}
      </div>
      <div class="vol-sub">20 日年化波动率</div>
      <div class="vol-pctl">
        历史分位
        <b>{{ vol.percentile != null ? vol.percentile.toFixed(1) + "%" : "—" }}</b>
      </div>
      <div v-if="phase" class="vol-phase" :style="{ color: phase.color }">
        {{ phase.label }}
      </div>
      <div class="vol-note">样本：近 750 个交易日 · 分位越高波动越剧烈</div>
    </div>
  </n-card>
</template>

<style lang="scss" scoped>
.full-height-card {
  height: 100%;
  :deep(.n-card__content) {
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
.vol-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  text-align: center;
}
.vol-main {
  font-size: 26px;
  font-weight: 700;
  font-family: monospace;
}
.vol-sub {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.vol-pctl {
  font-size: 13px;
  color: var(--n-text-color-2);
}
.vol-phase {
  font-size: 13px;
  font-weight: 600;
}
.vol-note {
  font-size: 10px;
  color: var(--n-text-color-3);
}
</style>
