<template>
  <n-card size="small" class="real-time-performance">
    <template #header><span>实时表现</span></template>
    <n-grid :cols="2" :x-gap="12" :y-gap="8">
      <n-grid-item>
        <n-statistic label="今日收益" :value="performance.dailyReturn">
          <template #suffix>%</template>
        </n-statistic>
      </n-grid-item>
      <n-grid-item>
        <n-statistic label="累计收益" :value="performance.totalReturn">
          <template #suffix>%</template>
        </n-statistic>
      </n-grid-item>
      <n-grid-item>
        <n-statistic label="夏普比率" :value="performance.sharpeRatio" />
      </n-grid-item>
      <n-grid-item>
        <n-statistic label="最大回撤" :value="performance.maxDrawdown">
          <template #suffix>%</template>
        </n-statistic>
      </n-grid-item>
    </n-grid>
  </n-card>
</template>

<script setup lang="ts">
import { ref } from "vue";

const performance = ref({
  dailyReturn: 1.25,
  totalReturn: 15.42,
  sharpeRatio: 1.23,
  maxDrawdown: -8.76,
});
</script>

<style scoped>
.real-time-performance {
  min-width: 200px;
}
</style>
