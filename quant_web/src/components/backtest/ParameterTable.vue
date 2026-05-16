<template>
  <div class="parameter-table">
    <h4>最优参数组合</h4>
    <NDataTable :data="tableData" :columns="columns" :bordered="false" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NDataTable } from "naive-ui";
import type { DataTableColumn } from "naive-ui";

interface ParamItem {
  name: string;
  value: number;
  performance: number;
  min: number;
  max: number;
}

const props = withDefaults(
  defineProps<{
    data?: ParamItem[];
  }>(),
  {
    data: () => [],
  },
);

const tableData = computed(() => {
  return props.data.map((item) => ({
    parameter: item.name,
    value: item.value,
    performance: item.performance,
    range: `${item.min} - ${item.max}`,
  }));
});

const columns: DataTableColumn<any>[] = [
  { key: "parameter", title: "参数名", width: 150 },
  { key: "value", title: "最优值", width: 120, align: "right" },
  {
    key: "performance",
    title: "性能指标",
    width: 120,
    align: "right",
    render: (row: any) => row.performance.toFixed(4),
  },
  { key: "range", title: "参数范围", width: 200 },
];
</script>

<style scoped>
.parameter-table {
  margin-top: 20px;
}

.parameter-table h4 {
  margin-bottom: 15px;
  color: var(--n-text-color-1);
}
</style>
