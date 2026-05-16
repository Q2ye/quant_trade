<script setup lang="ts">
import { NSlider } from "naive-ui";

const props = defineProps<{
  paramName: string;
  config: { min: number; max: number; step: number; default: number };
  modelValue: number;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: number];
  change: [name: string, value: number];
}>();

const formatLabel = (value: number) =>
  value % 1 === 0 ? value : value.toFixed(2);
</script>

<template>
  <div class="param-slider">
    <div class="param-header">
      <span class="param-name">{{ paramName }}</span>
      <span class="param-value">{{ modelValue.toFixed(2) }}</span>
    </div>
    <div class="slider-container">
      <span class="min-value">{{ formatLabel(config.min) }}</span>
      <NSlider
        :value="modelValue"
        :min="config.min"
        :max="config.max"
        :step="config.step"
        :format-tooltip="(v: number) => v.toFixed(2)"
        style="flex: 1"
        @update:value="(v: number) => emit('update:modelValue', v)"
      />
      <span class="max-value">{{ formatLabel(config.max) }}</span>
    </div>
    <div class="param-description">
      <span>默认值: {{ config.default.toFixed(2) }}</span>
    </div>
  </div>
</template>

<style scoped>
.param-slider {
  padding: 10px 15px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  background: var(--n-card-color);
}
.param-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}
.param-name {
  font-weight: 500;
  color: var(--n-text-color-1);
  text-transform: capitalize;
}
.param-value {
  font-weight: bold;
  color: var(--n-color-target);
}
.slider-container {
  display: flex;
  align-items: center;
  gap: 10px;
}
.min-value,
.max-value {
  font-size: 12px;
  color: var(--n-text-color-3);
  min-width: 40px;
  text-align: center;
}
.param-description {
  margin-top: 5px;
  font-size: 12px;
  color: var(--n-text-color-3);
}
</style>
