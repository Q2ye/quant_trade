<script setup lang="ts">
// 涨停梯队卡（v5 N3）—— 连板高度分布 + 炸板率 + 封板资金(近似) + 情绪周期结论
import { computed } from "vue";
import { useRouter } from "vue-router";
import { NSkeleton, NEmpty, NTag, NButton } from "naive-ui";
import type { LimitLadder } from "@/types/entities/market";

const props = defineProps<{
  data: LimitLadder | null;
  loading: boolean;
}>();

const router = useRouter();

const ladderItems = computed(() => {
  const l = props.data?.ladder;
  if (!l) return [];
  return [
    { label: "首板", n: l.board1 },
    { label: "2连板", n: l.board2 },
    { label: "3连板", n: l.board3 },
    { label: "≥4板", n: l.board4plus },
  ];
});
const maxN = computed(() => Math.max(1, ...ladderItems.value.map((i) => i.n)));

const phaseColor = computed(() => {
  switch (props.data?.emotion_phase) {
    case "冰点":
      return "#26a69a";
    case "修复":
      return "#66bb6a";
    case "发酵":
      return "#ff9800";
    case "高潮":
      return "#ef5350";
    case "退潮":
      return "#7e57c2";
    default:
      return "#94a3b8";
  }
});

// stock_daily.amount 单位千元 → /1e5 = 亿（封板资金=涨停股成交额合计，近似口径）
const sealText = computed(() => {
  const v = props.data?.seal_amount;
  return v == null ? "-" : (v / 1e5).toFixed(1) + "亿";
});

const goDetail = () => router.push("/market/limit-analysis");
</script>

<template>
  <n-card size="small" class="full-height-card" title="涨停梯队">
    <template #header-extra>
      <n-button size="tiny" quaternary @click="goDetail">详情 →</n-button>
    </template>
    <n-skeleton v-if="loading && !data" :text="true" :repeat="3" />
    <n-empty v-else-if="!data" description="暂无梯队数据" size="small" style="padding: 24px" />
    <div v-else class="ladder-body">
      <div class="ladder-rows">
        <div v-for="it in ladderItems" :key="it.label" class="ladder-row">
          <span class="ladder-label">{{ it.label }}</span>
          <div class="ladder-track">
            <div class="ladder-fill" :style="{ width: (it.n / maxN) * 100 + '%' }" />
          </div>
          <span class="ladder-count">{{ it.n }}</span>
        </div>
      </div>
      <div class="ladder-meta">
        <span>
          炸板率
          <b :class="{ 'bust-hot': (data.bust_rate ?? 0) > 35 }">
            {{ data.bust_rate != null ? data.bust_rate.toFixed(1) + "%" : "—" }}
          </b>
        </span>
        <span class="seal-cell">
          封板资金 {{ sealText }}
          <n-tag v-if="data.seal_amount_approx" size="tiny" :bordered="false">成交额近似</n-tag>
        </span>
        <span class="max-h">最高 {{ data.max_height }} 板</span>
      </div>
      <div class="phase-line">
        <n-tag
          size="small"
          :bordered="false"
          :style="{ background: phaseColor + '22', color: phaseColor }"
        >
          {{ data.emotion_phase || "—" }}
        </n-tag>
        <span class="phase-desc">{{ data.phase_desc || "" }}</span>
      </div>
    </div>
  </n-card>
</template>

<style lang="scss" scoped>
.full-height-card {
  height: 100%;
}
.ladder-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  justify-content: space-evenly;
}
.ladder-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ladder-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.ladder-label {
  width: 44px;
  color: var(--n-text-color-3);
  text-align: right;
}
.ladder-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}
.ladder-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #ff9800, #ef5350);
  transition: width 0.3s;
}
.ladder-count {
  width: 24px;
  font-weight: 700;
  font-family: monospace;
  text-align: right;
}
.ladder-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--n-text-color-2);
  flex-wrap: wrap;
  align-items: center;
  .bust-hot {
    color: #ef5350;
  }
  .seal-cell {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .max-h {
    margin-left: auto;
    color: var(--n-text-color-3);
  }
}
.phase-line {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 6px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
}
.phase-desc {
  font-size: 11px;
  color: var(--n-text-color-3);
  line-height: 1.4;
}
</style>
