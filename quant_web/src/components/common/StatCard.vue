<template>
  <n-card size="small" class="stat-card">
    <div class="stat-content">
      <div class="stat-title">{{ title }}</div>
      <div :class="['stat-value', trendClass]">{{ value }}</div>
    </div>
  </n-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ title: string; value: string; trend?: string }>();

const trendClass = computed(() => {
  if (props.trend === "up") return "trend-up";
  if (props.trend === "down") return "trend-down";
  return "";
});
</script>

<style scoped>
.stat-card {
  text-align: center;
}
.stat-title {
  font-size: 13px;
  color: var(--n-text-color-3);
  margin-bottom: 8px;
}
.stat-value {
  font-size: 22px;
  font-weight: bold;
}
.trend-up {
  color: #f56c6c;
}
.trend-down {
  color: #67c23a;
}
</style>
