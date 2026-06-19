<!-- IndustryMomentumChart.vue — 动量和量能散点图 (wrapper) -->
<script setup lang="ts">
import IndustryMomentumScatter from "@/components/market/IndustryMomentumScatter.vue";
import type { SwHeatmapItem } from "@/types/entities/market";

defineProps<{
  data: SwHeatmapItem[];
  loading?: boolean;
  error?: boolean;
}>();

const emit = defineEmits<{
  select: [code: string, name: string];
  retry: [];
}>();
</script>

<template>
  <IndustryMomentumScatter
    :data="data"
    :loading="loading"
    :error="error"
    @select="(code: string, name: string) => emit('select', code, name)"
    @retry="emit('retry')"
  />
</template>
