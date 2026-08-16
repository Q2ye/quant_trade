<script setup lang="ts">
// 拥挤度卡（v5 N4，L4 span8）—— 全市场成交额分位 + 申万 L1 行业成交额分位 TOP5
import { computed } from "vue";
import { NSkeleton, NEmpty, NTag } from "naive-ui";
import type { Crowding } from "@/types/entities/market";

const props = defineProps<{
  data: Crowding | null;
  loading: boolean;
}>();

const marketPctl = computed(() => props.data?.market_turnover_percentile ?? null);
const pctlColor = (p: number) =>
  p > 80 ? "#ef5350" : p > 50 ? "#ff9800" : "#26a69a";
</script>

<template>
  <n-card size="small" class="full-height-card" title="拥挤度">
    <n-skeleton v-if="loading && !data" :text="true" :repeat="3" />
    <n-empty v-else-if="!data" description="暂无数据" size="small" style="padding: 24px" />
    <div v-else class="crowd-body">
      <div class="crowd-main">
        <span class="crowd-label">全市场成交额分位</span>
        <span
          class="crowd-val"
          :style="{ color: marketPctl != null ? pctlColor(marketPctl) : '' }"
        >
          {{ marketPctl != null ? marketPctl.toFixed(1) + "%" : "—" }}
        </span>
      </div>
      <div class="crowd-sub">近 250 交易日成交额所处位置，>80% 提示过热</div>
      <div class="crowd-list">
        <div class="crowd-list-head">拥挤行业 TOP5（成交额分位）</div>
        <div v-for="c in data.top_crowded_industries" :key="c.name" class="crowd-row">
          <span class="crowd-name">{{ c.name }}</span>
          <n-tag size="tiny" :bordered="false" :type="c.percentile > 80 ? 'error' : 'default'">
            {{ c.percentile.toFixed(0) }}%
          </n-tag>
        </div>
      </div>
    </div>
  </n-card>
</template>

<style lang="scss" scoped>
.full-height-card {
  height: 100%;
}
.crowd-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.crowd-main {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.crowd-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.crowd-val {
  font-size: 26px;
  font-weight: 700;
  font-family: monospace;
}
.crowd-sub {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.crowd-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}
.crowd-list-head {
  font-size: 11px;
  color: var(--n-text-color-3);
}
.crowd-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.crowd-name {
  color: var(--n-text-color-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
}
</style>
