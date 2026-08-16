<script setup lang="ts">
// 分位条 —— 通用"基准线可视化"：0~100 分位刻度条，50% 处标历史中位线
// color：自定义基色（渐变自基色浅色到基色）；不传则用 绿→橙→红 通用渐变
import { computed } from "vue";

const props = defineProps<{ value: number | null; color?: string }>();

const fillStyle = computed(() =>
  props.color
    ? { background: `linear-gradient(90deg, ${props.color}55, ${props.color})` }
    : { background: "linear-gradient(90deg, #26a69a, #ff9800, #ef5350)" },
);
</script>

<template>
  <div class="pctl-bar">
    <div class="pctl-track">
      <div class="pctl-mid" />
      <div
        v-if="value != null"
        class="pctl-fill"
        :style="{ ...fillStyle, width: Math.min(100, Math.max(0, value)) + '%' }"
      />
    </div>
    <span class="pctl-text">{{ value != null ? value.toFixed(0) + "%" : "—" }}</span>
  </div>
</template>

<style scoped>
.pctl-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.pctl-track {
  position: relative;
  flex: 1;
  height: 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}
.pctl-mid {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.4);
  z-index: 1;
}
.pctl-fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  border-radius: 3px;
}
.pctl-text {
  width: 38px;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--n-text-color-3);
  font-family: monospace;
  text-align: right;
}
</style>
