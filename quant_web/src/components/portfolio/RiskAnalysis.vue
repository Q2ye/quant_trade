<!--风险分析-->
<template>
  <div class="risk-analysis">
    <NGrid :cols="24" :x-gap="16">
      <NGridItem :span="8">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-bell-curve" width="20" />
              <span>风险指标</span>
            </div>
          </template>
          <div class="risk-metrics">
            <div
              v-for="metric in metricsList"
              :key="metric.label"
              class="metric-item"
            >
              <div class="metric-label">
                <Icon :icon="metric.icon" width="16" />
                <span>{{ metric.label }}</span>
              </div>
              <div class="metric-value" :class="metric.cssClass">
                {{ metric.value }}
              </div>
            </div>
          </div>
        </NCard>
      </NGridItem>

      <NGridItem :span="16">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-line" width="20" />
              <span>回撤分析</span>
            </div>
          </template>
          <div ref="drawdownChart" style="height: 300px"></div>
        </NCard>
      </NGridItem>
    </NGrid>

    <NGrid :cols="24" :x-gap="16" style="margin-top: 16px">
      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-box" width="20" />
              <span>风险贡献</span>
            </div>
          </template>
          <div ref="riskContributionChart" style="height: 300px"></div>
        </NCard>
      </NGridItem>

      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-scatter-plot" width="20" />
              <span>风险收益散点图</span>
            </div>
          </template>
          <div ref="riskReturnChart" style="height: 300px"></div>
        </NCard>
      </NGridItem>
    </NGrid>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { NGrid, NGridItem, NCard } from "naive-ui";
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";

const drawdownChart = ref<HTMLElement>();
const riskContributionChart = ref<HTMLElement>();
const riskReturnChart = ref<HTMLElement>();

const riskMetrics = ref({
  volatility: 18.5,
  var: 2.8,
  maxDrawdown: 15.2,
  sharpeRatio: 1.8,
  sortinoRatio: 2.3,
  beta: 0.95,
});

const metricsList = computed(() => [
  {
    label: "年化波动率",
    icon: "mdi:chart-line",
    value: `${riskMetrics.value.volatility}%`,
    cssClass: "",
  },
  {
    label: "VaR (95%)",
    icon: "mdi:alert-octagon",
    value: `-${riskMetrics.value.var}%`,
    cssClass: "negative",
  },
  {
    label: "最大回撤",
    icon: "mdi:trending-down",
    value: `${riskMetrics.value.maxDrawdown}%`,
    cssClass: "negative",
  },
  {
    label: "夏普比率",
    icon: "mdi:chart-timeline",
    value: `${riskMetrics.value.sharpeRatio}`,
    cssClass: "positive",
  },
  {
    label: "索提诺比率",
    icon: "mdi:sigma",
    value: `${riskMetrics.value.sortinoRatio}`,
    cssClass: "positive",
  },
  {
    label: "贝塔系数",
    icon: "mdi:scale-balance",
    value: `${riskMetrics.value.beta}`,
    cssClass: "",
  },
]);

onMounted(() => {
  if (drawdownChart.value) {
    const chart = echarts.init(drawdownChart.value);
    chart.setOption({
      tooltip: { trigger: "axis" },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        data: [
          "1月",
          "2月",
          "3月",
          "4月",
          "5月",
          "6月",
          "7月",
          "8月",
          "9月",
          "10月",
          "11月",
          "12月",
        ],
      },
      yAxis: { type: "value", inverse: true, name: "回撤 (%)" },
      series: [
        {
          name: "组合回撤",
          type: "line",
          data: [
            0, -2.5, -1.8, -8.2, -5.6, -3.1, -12.5, -9.8, -7.2, -15.2, -11.4,
            -8.7,
          ],
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(245,108,108,0.6)" },
              { offset: 1, color: "rgba(245,108,108,0.1)" },
            ]),
          },
          lineStyle: { color: "#f56c6c" },
        },
      ],
    });
  }

  if (riskContributionChart.value) {
    const chart = echarts.init(riskContributionChart.value);
    chart.setOption({
      tooltip: { trigger: "item", formatter: "{a} <br/>{b}: {c}%" },
      legend: { orient: "vertical", right: 10, top: "center" },
      series: [
        {
          name: "风险贡献",
          type: "pie",
          radius: ["40%", "70%"],
          center: ["40%", "50%"],
          data: [
            { value: 28, name: "贵州茅台" },
            { value: 22, name: "宁德时代" },
            { value: 18, name: "腾讯控股" },
            { value: 15, name: "招商银行" },
            { value: 12, name: "中国平安" },
            { value: 5, name: "其他" },
          ],
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: "rgba(0, 0, 0, 0.5)",
            },
          },
        },
      ],
    });
  }

  if (riskReturnChart.value) {
    const chart = echarts.init(riskReturnChart.value);
    chart.setOption({
      tooltip: {
        trigger: "item",
        formatter: function (params: any) {
          return `${params.data[4]}<br/>风险: ${params.data[0]}%<br/>收益: ${params.data[1]}%`;
        },
      },
      grid: { left: "3%", right: "7%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "value",
        name: "风险 (%)",
        nameLocation: "middle",
        nameGap: 30,
      },
      yAxis: {
        type: "value",
        name: "收益 (%)",
        nameLocation: "middle",
        nameGap: 30,
      },
      series: [
        {
          name: "资产",
          type: "scatter",
          symbolSize: function (data: number[]) {
            return Math.sqrt(data[2]) * 5;
          },
          data: [
            [12, 8, 15, 0, "贵州茅台"],
            [25, 15, 12, 1, "宁德时代"],
            [18, 12, 10, 2, "腾讯控股"],
            [8, 6, 8, 3, "招商银行"],
            [10, 5, 7, 4, "中国平安"],
            [6, 4, 5, 5, "现金"],
          ],
          itemStyle: {
            color: function (params: any) {
              const colorList = [
                "#5470c6",
                "#91cc75",
                "#fac858",
                "#ee6666",
                "#73c0de",
                "#3ba272",
              ];
              return colorList[params.data[3]];
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

.risk-metrics {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--n-border-color);
}

.metric-item:last-child {
  border-bottom: none;
}

.metric-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--n-text-color-2);
  font-size: 14px;
}

.metric-value {
  font-weight: 600;
  font-size: 16px;
}

.positive {
  color: #67c23a;
}
.negative {
  color: #f56c6c;
}
</style>
