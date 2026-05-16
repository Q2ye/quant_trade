<template>
  <div class="recent-trades">
    <NDataTable
      :data="trades"
      :columns="columns"
      :max-height="250"
      size="small"
      :bordered="false"
    />
  </div>
</template>

<script setup lang="ts">
import { h } from "vue";
import { NDataTable, NTag } from "naive-ui";
import type { DataTableColumn } from "naive-ui";

interface Trade {
  time: string;
  symbol: string;
  name: string;
  direction: string;
  price: number;
  quantity: number;
}

defineProps<{
  trades: Trade[];
}>();

const columns: DataTableColumn<any>[] = [
  { key: "time", title: "时间", width: 90 },
  { key: "symbol", title: "代码", width: 80 },
  { key: "name", title: "名称", width: 100 },
  {
    key: "direction",
    title: "方向",
    render: (row: Trade) =>
      h(
        "span",
        { class: row.direction === "买入" ? "buy" : "sell" },
        row.direction,
      ),
  },
  {
    key: "price",
    title: "价格",
    width: 80,
    render: (row: Trade) => row.price.toFixed(2),
  },
  { key: "quantity", title: "数量", width: 70 },
  {
    key: "amount",
    title: "金额",
    render: (row: Trade) => (row.price * row.quantity).toLocaleString(),
  },
  {
    key: "status",
    title: "状态",
    render: () =>
      h(NTag, { size: "small", type: "success" }, { default: () => "已完成" }),
  },
];
</script>

<style scoped>
.recent-trades {
  height: 100%;
}
</style>

<style>
.buy {
  color: #f56c6c;
  font-weight: bold;
}

.sell {
  color: #5cb87a;
  font-weight: bold;
}
</style>
