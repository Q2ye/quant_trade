<template>
  <n-data-table
    :data="trades"
    :columns="columns"
    :bordered="false"
    striped
    :max-height="400"
    :row-key="(row: any) => row.id"
  />
</template>

<script setup lang="ts">
import { computed, h } from "vue";
import { NTag } from "naive-ui";

const props = defineProps<{
  trades: Array<{
    id: number;
    symbol: string;
    name: string;
    direction: string;
    date: string;
    price: number;
    quantity: number;
    amount: number;
    fee: number;
  }>;
}>();

const columns = computed(() => [
  { title: "ID", key: "id", width: 60 },
  { title: "代码", key: "symbol", width: 100 },
  { title: "名称", key: "name", width: 120 },
  {
    title: "方向",
    key: "direction",
    width: 80,
    render(row: any) {
      const isBuy = row.direction === "buy";
      return h(
        NTag,
        { type: isBuy ? "success" : "error", size: "small" },
        { default: () => (isBuy ? "买入" : "卖出") },
      );
    },
  },
  { title: "日期", key: "date", width: 110 },
  {
    title: "价格",
    key: "price",
    width: 100,
    render(row: any) {
      return row.price?.toFixed(2);
    },
  },
  { title: "数量", key: "quantity", width: 80 },
  {
    title: "金额",
    key: "amount",
    width: 120,
    render(row: any) {
      return row.amount?.toLocaleString();
    },
  },
  {
    title: "手续费",
    key: "fee",
    width: 80,
    render(row: any) {
      return row.fee?.toFixed(2);
    },
  },
]);
</script>
