<!--持仓分析-->
<template>
  <div class="holdings-analysis">
    <NGrid :cols="24" :x-gap="16">
      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-pie" width="20" />
              <span>资产配置</span>
            </div>
          </template>
          <div ref="assetAllocationChart" style="height: 300px"></div>
        </NCard>
      </NGridItem>

      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:finance" width="20" />
              <span>行业分布</span>
            </div>
          </template>
          <div ref="sectorChart" style="height: 300px"></div>
        </NCard>
      </NGridItem>
    </NGrid>

    <NCard style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <Icon icon="mdi:table" width="20" />
          <span>持仓明细</span>
        </div>
      </template>
      <NDataTable :data="holdings" :columns="columns" :bordered="false" />
    </NCard>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { NGrid, NGridItem, NCard, NDataTable, NProgress } from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";
import * as echarts from "echarts";

const assetAllocationChart = ref<HTMLElement>();
const sectorChart = ref<HTMLElement>();

const holdings = ref([
  {
    name: "贵州茅台",
    symbol: "600519",
    icon: "mdi:glass-wine",
    weight: 15.5,
    currentPrice: 1650.8,
    quantity: 1000,
    marketValue: 1650800,
    dailyChange: 2.35,
    totalReturn: 45.6,
  },
  {
    name: "宁德时代",
    symbol: "300750",
    icon: "mdi:battery",
    weight: 12.2,
    currentPrice: 210.5,
    quantity: 5000,
    marketValue: 1052500,
    dailyChange: -1.25,
    totalReturn: 32.8,
  },
  {
    name: "腾讯控股",
    symbol: "00700",
    icon: "mdi:chat",
    weight: 10.8,
    currentPrice: 320.4,
    quantity: 3000,
    marketValue: 961200,
    dailyChange: 0.85,
    totalReturn: 28.4,
  },
  {
    name: "招商银行",
    symbol: "600036",
    icon: "mdi:bank",
    weight: 8.7,
    currentPrice: 35.2,
    quantity: 20000,
    marketValue: 704000,
    dailyChange: 0.56,
    totalReturn: 15.2,
  },
  {
    name: "中国平安",
    symbol: "601318",
    icon: "mdi:shield-events",
    weight: 7.3,
    currentPrice: 48.9,
    quantity: 12000,
    marketValue: 586800,
    dailyChange: -0.42,
    totalReturn: 8.7,
  },
]);

const formatNumber = (num: number) => num.toLocaleString("zh-CN");

const columns: DataTableColumn<any>[] = [
  {
    key: "name",
    title: "资产名称",
    width: 180,
    render: (row: any) =>
      h("div", { class: "asset-info" }, [
        h(Icon, { icon: row.icon, width: "16" }),
        h("span", { style: { marginLeft: "8px" } }, row.name),
      ]),
  },
  { key: "symbol", title: "代码", width: 100 },
  {
    key: "weight",
    title: "权重",
    width: 120,
    render: (row: any) =>
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h(NProgress, {
            percentage: row.weight,
            showIndicator: false,
            color: row.weight > 10 ? "#67c23a" : "#409eff",
          }),
          h("span", `${row.weight}%`),
        ],
      ),
  },
  {
    key: "currentPrice",
    title: "当前价格",
    width: 120,
    render: (row: any) => `¥${row.currentPrice}`,
  },
  { key: "quantity", title: "持仓数量", width: 120 },
  {
    key: "marketValue",
    title: "市值",
    width: 140,
    render: (row: any) => `¥${formatNumber(row.marketValue)}`,
  },
  {
    key: "dailyChange",
    title: "日涨跌幅",
    width: 120,
    render: (row: any) => {
      const cls = row.dailyChange >= 0 ? "positive" : "negative";
      const sign = row.dailyChange >= 0 ? "+" : "";
      return h("span", { class: cls }, `${sign}${row.dailyChange}%`);
    },
  },
  {
    key: "totalReturn",
    title: "累计收益",
    width: 120,
    render: (row: any) => {
      const cls = row.totalReturn >= 0 ? "positive" : "negative";
      const sign = row.totalReturn >= 0 ? "+" : "";
      return h("span", { class: cls }, `${sign}${row.totalReturn}%`);
    },
  },
];

onMounted(() => {
  if (assetAllocationChart.value) {
    const chart = echarts.init(assetAllocationChart.value);
    chart.setOption({
      tooltip: { trigger: "item", formatter: "{a} <br/>{b}: {c} ({d}%)" },
      legend: { orient: "vertical", left: "left", top: "center" },
      series: [
        {
          name: "资产配置",
          type: "pie",
          radius: ["40%", "70%"],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 10, borderColor: "#fff", borderWidth: 2 },
          label: { show: false, position: "center" },
          emphasis: { label: { show: true, fontSize: 18, fontWeight: "bold" } },
          labelLine: { show: false },
          data: [
            { value: 45, name: "股票" },
            { value: 25, name: "债券" },
            { value: 15, name: "现金" },
            { value: 10, name: "商品" },
            { value: 5, name: "其他" },
          ],
        },
      ],
    });
  }

  if (sectorChart.value) {
    const chart = echarts.init(sectorChart.value);
    chart.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        data: ["科技", "消费", "金融", "医药", "能源", "工业", "材料"],
      },
      yAxis: { type: "value", name: "权重 (%)" },
      series: [
        {
          name: "行业权重",
          type: "bar",
          data: [25, 20, 18, 15, 8, 7, 7],
          itemStyle: {
            color: function (params: any) {
              const colorList = [
                "#5470c6",
                "#91cc75",
                "#fac858",
                "#ee6666",
                "#73c0de",
                "#3ba272",
                "#fc8452",
              ];
              return colorList[params.dataIndex];
            },
          },
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

.asset-info {
  display: flex;
  align-items: center;
}

:deep(.positive) {
  color: #f56c6c;
}
:deep(.negative) {
  color: #67c23a;
}
</style>
