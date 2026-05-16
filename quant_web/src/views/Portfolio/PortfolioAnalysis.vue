<template>
  <n-spin :show="loading" class="portfolio-analysis">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取组合数据失败，请稍后重试"
    >
      <template #footer><n-button @click="loadData">重试</n-button></template>
    </n-result>

    <template v-else>
      <div class="page-header">
        <h1>组合分析</h1>
        <p>多维度分析投资组合表现和风险特征</p>
      </div>

      <n-grid :x-gap="16" :cols="24" class="portfolio-overview">
        <n-grid-item :span="8">
          <n-card>
            <template #header><span>组合概况</span></template>
            <div class="overview-stats">
              <div class="stat-item">
                <label>总资产</label>
                <span class="value"
                  >¥{{ formatNumber(portfolioStats.totalValue) }}</span
                >
              </div>
              <div class="stat-item">
                <label>今日收益</label>
                <span
                  :class="[
                    'value',
                    portfolioStats.dailyPnL >= 0 ? 'positive' : 'negative',
                  ]"
                >
                  {{ portfolioStats.dailyPnL >= 0 ? "+" : ""
                  }}{{ portfolioStats.dailyPnL.toFixed(2) }}%
                </span>
              </div>
              <div class="stat-item">
                <label>累计收益</label>
                <span
                  :class="[
                    'value',
                    portfolioStats.totalReturn >= 0 ? 'positive' : 'negative',
                  ]"
                >
                  {{ portfolioStats.totalReturn >= 0 ? "+" : ""
                  }}{{ portfolioStats.totalReturn.toFixed(2) }}%
                </span>
              </div>
              <div class="stat-item">
                <label>年化收益</label>
                <span class="value"
                  >{{ portfolioStats.annualReturn.toFixed(2) }}%</span
                >
              </div>
              <div class="stat-item">
                <label>最大回撤</label>
                <span class="value negative"
                  >{{ portfolioStats.maxDrawdown.toFixed(2) }}%</span
                >
              </div>
              <div class="stat-item">
                <label>夏普比率</label>
                <span class="value">{{
                  portfolioStats.sharpeRatio.toFixed(2)
                }}</span>
              </div>
            </div>
          </n-card>
        </n-grid-item>

        <n-grid-item :span="16">
          <n-card>
            <template #header><span>净值曲线</span></template>
            <div ref="equityChart" style="height: 300px"></div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <div class="analysis-tabs">
        <n-card>
          <template #header>
            <n-tabs v-model:value="activeTab">
              <n-tab-pane name="holdings" tab="持仓分析" />
              <n-tab-pane name="risk" tab="风险分析" />
              <n-tab-pane name="attribution" tab="绩效归因" />
              <n-tab-pane name="optimization" tab="组合优化" />
            </n-tabs>
          </template>
          <HoldingsAnalysis v-if="activeTab === 'holdings'" />
          <RiskAnalysis v-if="activeTab === 'risk'" />
          <AttributionAnalysis v-if="activeTab === 'attribution'" />
          <PortfolioOptimization v-if="activeTab === 'optimization'" />
        </n-card>
      </div>
    </template>
  </n-spin>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import * as echarts from "echarts";
import HoldingsAnalysis from "@/components/portfolio/HoldingsAnalysis.vue";
import RiskAnalysis from "@/components/portfolio/RiskAnalysis.vue";
import AttributionAnalysis from "@/components/portfolio/AttributionAnalysis.vue";
import PortfolioOptimization from "@/components/portfolio/PortfolioOptimization.vue";

const loading = ref(false);
const error = ref(false);
const activeTab = ref("holdings");
const equityChart = ref<HTMLElement>();

const portfolioStats = ref({
  totalValue: 1250000,
  dailyPnL: 1.25,
  totalReturn: 25.8,
  annualReturn: 18.5,
  maxDrawdown: -15.2,
  sharpeRatio: 1.8,
});

const formatNumber = (num: number) => num.toLocaleString("zh-CN");

const loadData = () => {
  loading.value = true;
  error.value = false;
  setTimeout(() => { loading.value = false; }, 1000);
};

onMounted(() => {
  if (equityChart.value) {
    const chart = echarts.init(equityChart.value);
    const option = {
      tooltip: { trigger: "axis" },
      legend: { data: ["组合净值", "基准指数"] },
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
      yAxis: { type: "value" },
      series: [
        {
          name: "组合净值",
          type: "line",
          data: [
            1.0, 1.05, 1.12, 1.08, 1.15, 1.22, 1.18, 1.25, 1.3, 1.28, 1.32,
            1.35,
          ],
          smooth: true,
          lineStyle: { width: 3 },
        },
        {
          name: "基准指数",
          type: "line",
          data: [
            1.0, 1.02, 1.08, 1.05, 1.1, 1.15, 1.12, 1.18, 1.22, 1.2, 1.25, 1.28,
          ],
          smooth: true,
          lineStyle: { width: 2, type: "dashed" },
        },
      ],
    };
    chart.setOption(option);
    window.addEventListener("resize", () => chart.resize());
  }
});
</script>

<style scoped>
.portfolio-analysis {
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.portfolio-overview {
  margin-bottom: 24px;
}
.overview-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--n-border-color);
}
.stat-item:last-child {
  border-bottom: none;
}
.stat-item label {
  color: var(--n-text-color-3);
  font-size: 14px;
}
.stat-item .value {
  font-weight: 600;
  font-size: 16px;
}
.stat-item .positive {
  color: #f56c6c;
}
.stat-item .negative {
  color: #67c23a;
}
.analysis-tabs {
  margin-top: 24px;
}
</style>
