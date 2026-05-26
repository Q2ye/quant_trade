<template>
  <div class="stock-pool-selector">
    <n-select
      v-model:value="selectedStocks"
      multiple
      filterable
      placeholder="选择股票池"
      :options="stockOptions"
      @update:value="emit('update:modelValue', $event)"
    />
    <div class="selected-tags" v-if="selectedStocks.length > 0">
      <n-tag
        v-for="code in selectedStocks"
        :key="code"
        closable
        size="small"
        @close="removeStock(code)"
      >
        {{ getLabel(code) }}
      </n-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{ modelValue?: string[]; multiple?: boolean }>();
const emit = defineEmits<{ (e: "update:modelValue", value: string[]): void }>();

const selectedStocks = ref<string[]>(props.modelValue || []);

const stockOptions = [
  { label: "贵州茅台 (600519)", value: "600519.SH" },
  { label: "五粮液 (000858)", value: "000858.SZ" },
  { label: "中国平安 (601318)", value: "601318.SH" },
  { label: "招商银行 (600036)", value: "600036.SH" },
  { label: "美的集团 (000333)", value: "000333.SZ" },
  { label: "格力电器 (000651)", value: "000651.SZ" },
  { label: "恒瑞医药 (600276)", value: "600276.SH" },
  { label: "东方财富 (300059)", value: "300059.SZ" },
  { label: "宁德时代 (300750)", value: "300750.SZ" },
  { label: "立讯精密 (002475)", value: "002475.SZ" },
];

const getLabel = (code: string) =>
  stockOptions.find((s) => s.value === code)?.label || code;

const removeStock = (code: string) => {
  selectedStocks.value = selectedStocks.value.filter((c) => c !== code);
  emit("update:modelValue", selectedStocks.value);
};
</script>

<style scoped>
.stock-pool-selector {
  width: 100%;
}
.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
</style>
