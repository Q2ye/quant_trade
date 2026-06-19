<!-- FinStatementTable.vue — 财务报表懒加载子组件 -->
<script setup lang="ts">
import { h, onMounted, ref, watch } from "vue";
import { NDataTable, NSkeleton, NEmpty } from "naive-ui";
import marketAPI from "@/api/market";

const props = defineProps<{
  code: string;
  type: "income" | "balance" | "cashflow";
}>();

const loading = ref(false);
const data = ref<any[]>([]);

const typeLabel: Record<string, string> = {
  income: "利润表",
  balance: "资产负债表",
  cashflow: "现金流量表",
};

// 根据报表类型动态生成列
const columns: Record<string, any[]> = {
  income: [
    { title: "报告期", key: "end_date", width: 100, fixed: "left" as const },
    {
      title: "营业收入(亿)",
      key: "revenue",
      width: 110,
      render: (r: any) =>
        r.revenue != null ? (r.revenue / 1e8).toFixed(2) : "-",
    },
    {
      title: "营业成本(亿)",
      key: "oper_cost",
      width: 110,
      render: (r: any) =>
        r.oper_cost != null ? (r.oper_cost / 1e8).toFixed(2) : "-",
    },
    {
      title: "营业利润(亿)",
      key: "oper_profit",
      width: 110,
      render: (r: any) =>
        r.oper_profit != null ? (r.oper_profit / 1e8).toFixed(2) : "-",
    },
    {
      title: "利润总额(亿)",
      key: "total_profit",
      width: 110,
      render: (r: any) =>
        r.total_profit != null ? (r.total_profit / 1e8).toFixed(2) : "-",
    },
    {
      title: "净利润(亿)",
      key: "n_income",
      width: 110,
      render: (r: any) =>
        r.n_income != null ? (r.n_income / 1e8).toFixed(2) : "-",
    },
    {
      title: "EPS",
      key: "eps",
      width: 80,
      render: (r: any) => (r.eps != null ? r.eps.toFixed(2) : "-"),
    },
  ],
  balance: [
    { title: "报告期", key: "end_date", width: 100, fixed: "left" as const },
    {
      title: "总资产(亿)",
      key: "total_assets",
      width: 120,
      render: (r: any) =>
        r.total_assets != null ? (r.total_assets / 1e8).toFixed(2) : "-",
    },
    {
      title: "总负债(亿)",
      key: "total_liab",
      width: 120,
      render: (r: any) =>
        r.total_liab != null ? (r.total_liab / 1e8).toFixed(2) : "-",
    },
    {
      title: "股东权益(亿)",
      key: "total_hldr_eqy_exc_min_int",
      width: 130,
      render: (r: any) =>
        r.total_hldr_eqy_exc_min_int != null
          ? (r.total_hldr_eqy_exc_min_int / 1e8).toFixed(2)
          : "-",
    },
    {
      title: "流动资产(亿)",
      key: "total_cur_assets",
      width: 120,
      render: (r: any) =>
        r.total_cur_assets != null
          ? (r.total_cur_assets / 1e8).toFixed(2)
          : "-",
    },
    {
      title: "流动负债(亿)",
      key: "total_cur_liab",
      width: 120,
      render: (r: any) =>
        r.total_cur_liab != null ? (r.total_cur_liab / 1e8).toFixed(2) : "-",
    },
  ],
  cashflow: [
    { title: "报告期", key: "end_date", width: 100, fixed: "left" as const },
    {
      title: "经营CF(亿)",
      key: "n_cashflow_act",
      width: 120,
      render: (r: any) =>
        r.n_cashflow_act != null ? (r.n_cashflow_act / 1e8).toFixed(2) : "-",
    },
    {
      title: "投资CF(亿)",
      key: "n_cashflow_inv_act",
      width: 120,
      render: (r: any) =>
        r.n_cashflow_inv_act != null
          ? (r.n_cashflow_inv_act / 1e8).toFixed(2)
          : "-",
    },
    {
      title: "筹资CF(亿)",
      key: "n_cash_fin_act",
      width: 120,
      render: (r: any) =>
        r.n_cash_fin_act != null ? (r.n_cash_fin_act / 1e8).toFixed(2) : "-",
    },
  ],
};

async function load() {
  if (!props.code) return;
  loading.value = true;
  try {
    const result = await marketAPI.getFinancialStatements(
      props.code,
      props.type,
      10,
    );
    data.value = result || [];
  } catch {
    data.value = [];
  } finally {
    loading.value = false;
  }
}

watch(() => [props.code, props.type], load);
onMounted(load);
</script>

<template>
  <n-skeleton v-if="loading" :text="true" :repeat="4" style="padding: 16px" />
  <n-empty
    v-else-if="!data.length"
    :description="'暂无' + typeLabel[type] + '数据'"
    style="padding: 60px"
  />
  <n-dataTable
    v-else
    :columns="columns[type]"
    :data="data"
    size="small"
    :bordered="true"
    max-height="360"
  />
</template>
