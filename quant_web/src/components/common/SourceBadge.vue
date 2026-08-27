<!--
  SourceBadge.vue — 绩效口径角标
  用于标识数据来源口径，避免回测/实盘策略/账户三套口径混淆（2026-08 信息架构重构）。
  类型：
  - backtest  → 回测口径（backtest_tasks，历史模拟）
  - strategy  → 实盘策略口径（strategy_daily_performance，策略体检）
  - account   → 账户口径（账户日资产快照，资金曲线）
  样式仅消费 design-tokens CSS 变量，禁硬编码颜色。
-->
<template>
  <span class="source-badge" :class="`sb-${type}`">
    <span class="sb-dot"></span>{{ label }}·
  </span>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ type: "backtest" | "strategy" | "account" }>();

const META: Record<string, string> = {
  backtest: "回测",
  strategy: "实盘策略",
  account: "账户",
};
const label = computed(() => META[props.type] || props.type);
</script>

<style scoped>
.source-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 400;
  color: var(--color-text-tertiary);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 1px 6px;
  vertical-align: middle;
  white-space: nowrap;
}
.sb-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.sb-backtest .sb-dot {
  background: var(--color-primary, #7c3aed);
}
.sb-strategy .sb-dot {
  background: #18a058;
}
.sb-account .sb-dot {
  background: #3b82f6;
}
</style>
