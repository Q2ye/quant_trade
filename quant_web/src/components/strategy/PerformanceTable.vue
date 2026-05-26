<template>
  <div class="performance-table">
    <NDataTable :data="tableData" :columns="columns" :bordered="false" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NDataTable } from "naive-ui";
import type { DataTableColumn } from "naive-ui";

interface PerfItem {
  strategyName: string;
  totalReturn: number;
  annualReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  calmarRatio: number;
  winRate: number;
  profitLossRatio: number;
  totalTrades: number;
}

const props = withDefaults(
  defineProps<{
    data?: PerfItem[];
  }>(),
  {
    data: () => [],
  },
);

const formatPercent = (value: number) => `${(value * 100).toFixed(2)}%`;

const tableData = computed(() => {
  return props.data.map((item) => ({
    strategy: item.strategyName,
    totalReturn: item.totalReturn || 0,
    annualReturn: item.annualReturn || 0,
    maxDrawdown: item.maxDrawdown || 0,
    sharpeRatio: item.sharpeRatio || 0,
    calmarRatio: item.calmarRatio || 0,
    winRate: item.winRate || 0,
    profitLossRatio: item.profitLossRatio || 0,
    totalTrades: item.totalTrades || 0,
  }));
});

const columns: DataTableColumn<any>[] = [
  { key: "strategy", title: "策略名称", width: 120 },
  {
    key: "totalReturn",
    title: "总收益率",
    width: 100,
    align: "right",
    render: (row: any) => formatPercent(row.totalReturn),
  },
  {
    key: "annualReturn",
    title: "年化收益率",
    width: 100,
    align: "right",
    render: (row: any) => formatPercent(row.annualReturn),
  },
  {
    key: "maxDrawdown",
    title: "最大回撤",
    width: 100,
    align: "right",
    render: (row: any) => formatPercent(row.maxDrawdown),
  },
  {
    key: "sharpeRatio",
    title: "夏普比率",
    width: 100,
    align: "right",
    render: (row: any) => row.sharpeRatio.toFixed(2),
  },
  {
    key: "calmarRatio",
    title: "卡玛比率",
    width: 100,
    align: "right",
    render: (row: any) => row.calmarRatio.toFixed(2),
  },
  {
    key: "winRate",
    title: "胜率",
    width: 100,
    align: "right",
    render: (row: any) => formatPercent(row.winRate),
  },
  {
    key: "profitLossRatio",
    title: "盈亏比",
    width: 100,
    align: "right",
    render: (row: any) => row.profitLossRatio.toFixed(2),
  },
  { key: "totalTrades", title: "总交易次数", width: 100, align: "right" },
];
</script>

<style scoped>
.performance-table {
  margin-top: 20px;
}
</style>
