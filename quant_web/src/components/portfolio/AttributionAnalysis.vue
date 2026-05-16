<!--绩效归因-->
<template>
  <div class="attribution-analysis">
    <NGrid :cols="24" :x-gap="16">
      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-bar" width="20" />
              <span>收益归因</span>
            </div>
          </template>
          <div ref="attributionChart" style="height: 350px"></div>
        </NCard>
      </NGridItem>

      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-waterfall" width="20" />
              <span>收益分解</span>
            </div>
          </template>
          <div ref="waterfallChart" style="height: 350px"></div>
        </NCard>
      </NGridItem>
    </NGrid>

    <NGrid :cols="24" :x-gap="16" style="margin-top: 16px">
      <NGridItem :span="24">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:table" width="20" />
              <span>归因明细</span>
            </div>
          </template>
          <NDataTable
            :data="attributionDetails"
            :columns="columns"
            :bordered="false"
          />
        </NCard>
      </NGridItem>
    </NGrid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { NGrid, NGridItem, NCard, NDataTable } from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";
import * as echarts from "echarts";

const attributionChart = ref<HTMLElement>();
const waterfallChart = ref<HTMLElement>();

const attributionDetails = ref([
  {
    factor: "股票选择",
    contribution: 8.2,
    allocation: 2.1,
    selection: 5.8,
    interaction: 0.3,
    description: "优秀的个股选择能力",
  },
  {
    factor: "行业配置",
    contribution: 4.5,
    allocation: 3.2,
    selection: 1.1,
    interaction: 0.2,
    description: "超配科技和消费行业",
  },
  {
    factor: "市场时机",
    contribution: 2.8,
    allocation: 1.5,
    selection: 0.9,
    interaction: 0.4,
    description: "适时的仓位调整",
  },
  {
    factor: "债券配置",
    contribution: 1.2,
    allocation: 0.8,
    selection: 0.3,
    interaction: 0.1,
    description: "稳定的债券收益",
  },
  {
    factor: "现金管理",
    contribution: 0.5,
    allocation: 0.3,
    selection: 0.1,
    interaction: 0.1,
    description: "流动性管理收益",
  },
  {
    factor: "其他",
    contribution: -1.2,
    allocation: -0.5,
    selection: -0.6,
    interaction: -0.1,
    description: "交易成本及其他",
  },
]);

const formatSign = (val: number) => `${val >= 0 ? "+" : ""}${val}`;
const signClass = (val: number) => (val >= 0 ? "positive" : "negative");

const columns: DataTableColumn<any>[] = [
  { key: "factor", title: "归因因子", width: 180 },
  {
    key: "contribution",
    title: "贡献度 (%)",
    width: 120,
    render: (row: any) =>
      h(
        "span",
        { class: signClass(row.contribution) },
        formatSign(row.contribution),
      ),
  },
  {
    key: "allocation",
    title: "配置效应 (%)",
    width: 120,
    render: (row: any) =>
      h(
        "span",
        { class: signClass(row.allocation) },
        formatSign(row.allocation),
      ),
  },
  {
    key: "selection",
    title: "选择效应 (%)",
    width: 120,
    render: (row: any) =>
      h("span", { class: signClass(row.selection) }, formatSign(row.selection)),
  },
  {
    key: "interaction",
    title: "交互效应 (%)",
    width: 120,
    render: (row: any) =>
      h(
        "span",
        { class: signClass(row.interaction) },
        formatSign(row.interaction),
      ),
  },
  { key: "description", title: "说明" },
];

onMounted(() => {
  if (attributionChart.value) {
    const chart = echarts.init(attributionChart.value);
    chart.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { data: ["配置效应", "选择效应", "交互效应"] },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        data: [
          "股票选择",
          "行业配置",
          "市场时机",
          "债券配置",
          "现金管理",
          "其他",
        ],
      },
      yAxis: { type: "value", name: "贡献度 (%)" },
      series: [
        {
          name: "配置效应",
          type: "bar",
          stack: "total",
          data: [2.1, 3.2, 1.5, 0.8, 0.3, -0.5],
          itemStyle: { color: "#5470c6" },
        },
        {
          name: "选择效应",
          type: "bar",
          stack: "total",
          data: [5.8, 1.1, 0.9, 0.3, 0.1, -0.6],
          itemStyle: { color: "#91cc75" },
        },
        {
          name: "交互效应",
          type: "bar",
          stack: "total",
          data: [0.3, 0.2, 0.4, 0.1, 0.1, -0.1],
          itemStyle: { color: "#fac858" },
        },
      ],
    });
  }

  if (waterfallChart.value) {
    const chart = echarts.init(waterfallChart.value);
    chart.setOption({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: function (params: any) {
          const tar = params[1];
          return tar.name + "<br/>" + tar.seriesName + " : " + tar.value;
        },
      },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        data: [
          "期初净值",
          "股票选择",
          "行业配置",
          "市场时机",
          "债券配置",
          "其他",
          "期末净值",
        ],
      },
      yAxis: { type: "value" },
      series: [
        {
          name: "辅助",
          type: "bar",
          stack: "Total",
          itemStyle: { borderColor: "transparent", color: "transparent" },
          emphasis: {
            itemStyle: { borderColor: "transparent", color: "transparent" },
          },
          data: [1.0, 1.082, 1.127, 1.155, 1.167, 1.162, 0],
        },
        {
          name: "净值变化",
          type: "bar",
          stack: "Total",
          label: { show: true, position: "inside" },
          data: [
            { value: 1.0, itemStyle: { color: "#73c0de" } },
            { value: 0.082, itemStyle: { color: "#5470c6" } },
            { value: 0.045, itemStyle: { color: "#5470c6" } },
            { value: 0.028, itemStyle: { color: "#5470c6" } },
            { value: 0.012, itemStyle: { color: "#5470c6" } },
            { value: -0.005, itemStyle: { color: "#ee6666" } },
            { value: 1.162, itemStyle: { color: "#73c0de" } },
          ],
        },
      ],
    });
  }
});
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

:deep(.positive) {
  color: #67c23a;
}
:deep(.negative) {
  color: #f56c6c;
}
</style>
