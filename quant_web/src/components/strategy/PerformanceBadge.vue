<!-- Factor performance badge with trend indicator -->
<template>
  <div class="performance-badge">
    <NTooltip placement="top">
      <template #trigger>
        <div class="performance-content">
          <Icon
            v-if="performance.trend === 'up'"
            icon="mdi:trending-up"
            class="trend-up"
          />
          <Icon
            v-else-if="performance.trend === 'down'"
            icon="mdi:trending-down"
            class="trend-down"
          />
          <Icon v-else icon="mdi:trending-neutral" class="trend-stable" />
          <span class="score" :class="scoreClass">{{ performance.score }}</span>
        </div>
      </template>
      {{ performanceText }}
    </NTooltip>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NTooltip } from "naive-ui";
import { Icon } from "@iconify/vue";

const props = withDefaults(
  defineProps<{
    performance: { score: number; trend: string };
  }>(),
  {
    performance: () => ({ score: 0, trend: "stable" }),
  },
);

const performanceText = computed(() => {
  const trendText: Record<string, string> = {
    up: "上升",
    down: "下降",
    stable: "稳定",
  };
  return `表现得分: ${props.performance.score} (${trendText[props.performance.trend]})`;
});

const scoreClass = computed(() => {
  const score = props.performance.score;
  if (score >= 80) return "score-excellent";
  if (score >= 60) return "score-good";
  if (score >= 40) return "score-average";
  return "score-poor";
});
</script>

<style lang="scss" scoped>
.performance-badge {
  .performance-content {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    cursor: pointer;
    .trend-up {
      color: #67c23a;
    }
    .trend-down {
      color: #f56c6c;
    }
    .trend-stable {
      color: #e6a23c;
    }
    .score {
      font-weight: 600;
      &.score-excellent {
        color: #67c23a;
      }
      &.score-good {
        color: #409eff;
      }
      &.score-average {
        color: #e6a23c;
      }
      &.score-poor {
        color: #f56c6c;
      }
    }
  }
}
</style>
