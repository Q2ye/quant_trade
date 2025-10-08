<!-- components/Research/PerformanceBadge.vue -->
<!-- 显示因子表现评分和趋势-->
<template>
  <div class="performance-badge">
    <el-tooltip :content="performanceText" placement="top">
      <div class="performance-content">
        <el-icon v-if="performance.trend === 'up'" class="trend-up">
          <Icon icon="mdi:trending-up" />
        </el-icon>
        <el-icon v-else-if="performance.trend === 'down'" class="trend-down">
          <Icon icon="mdi:trending-down" />
        </el-icon>
        <el-icon v-else class="trend-stable">
          <Icon icon="mdi:trending-neutral" />
        </el-icon>
        <span class="score" :class="scoreClass">{{ performance.score }}</span>
      </div>
    </el-tooltip>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
  performance: {
    type: Object,
    required: true,
    default: () => ({
      score: 0,
      trend: 'stable'
    })
  }
})

const performanceText = computed(() => {
  const trendText = {
    up: '上升',
    down: '下降',
    stable: '稳定'
  }
  return `表现得分: ${props.performance.score} (${trendText[props.performance.trend]})`
})

const scoreClass = computed(() => {
  const score = props.performance.score
  if (score >= 80) return 'score-excellent'
  if (score >= 60) return 'score-good'
  if (score >= 40) return 'score-average'
  return 'score-poor'
})
</script>

<style lang="scss" scoped>
.performance-badge {
  .performance-content {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;

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