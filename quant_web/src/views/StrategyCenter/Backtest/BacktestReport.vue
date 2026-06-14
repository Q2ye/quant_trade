<template>
  <n-spin :show="loading" class="backtest-report-page">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取回测报告失败，请稍后重试"
    >
      <template #footer><n-button @click="loadReport">重试</n-button></template>
    </n-result>

    <ReportLayout v-else>
      <template #header>
        <div class="report-header">
          <h2>{{ strategy.name }} - 回测报告</h2>
          <div class="summary-stats">
            <StatCard
              title="年化收益"
              :value="`${(report.summary.annualReturn * 100).toFixed(2)}%`"
              :trend="report.summary.annualReturn > 0 ? 'up' : 'down'"
            />
            <StatCard
              title="累计收益"
              :value="`${(report.summary.totalReturn * 100).toFixed(2)}%`"
              :trend="report.summary.totalReturn > 0 ? 'up' : 'down'"
            />
            <StatCard
              title="最大回撤"
              :value="`${(report.summary.maxDrawdown * 100).toFixed(2)}%`"
              trend="down"
            />
            <StatCard
              title="夏普比率"
              :value="report.summary.sharpeRatio.toFixed(2)"
            />
            <StatCard
              title="胜率"
              :value="`${(report.summary.winRate * 100).toFixed(1)}%`"
            />
          </div>
        </div>
      </template>

      <template #content>
        <div class="section">
          <h3>净值曲线</h3>
          <NetValueChart
            :data="report.equityCurve"
            :benchmark="report.benchmark"
          />
        </div>

        <div class="metrics-grid">
          <div class="metric-card">
            <h3>回撤分析</h3>
            <DrawdownChart :data="report.drawdown" />
          </div>
          <div class="metric-card">
            <h3>月度收益</h3>
            <MonthlyReturnChart :data="report.monthlyReturns" />
          </div>
        </div>

        <div class="section">
          <h3>交易分析</h3>
          <n-tabs v-model:value="activeTradeTab">
            <n-tab-pane name="trades" tab="交易列表">
              <TradeTable :trades="report.trades" />
            </n-tab-pane>
            <n-tab-pane name="distribution" tab="收益分布">
              <ProfitDistributionChart :data="report.profitDistribution" />
            </n-tab-pane>
            <n-tab-pane name="holdings" tab="持仓分析">
              <HoldingAnalysisChart :data="report.holdings" />
            </n-tab-pane>
          </n-tabs>
        </div>

        <div class="section">
          <h3>参数敏感性分析</h3>
          <ParameterSensitivity :data="report.parameterSensitivity" />
        </div>
      </template>

      <template #footer>
        <div class="report-footer">
          <n-space justify="center" :size="12">
            <n-button type="primary" @click="saveReport">保存报告</n-button>
            <n-button @click="exportPDF">导出PDF</n-button>
            <n-button @click="addToBasket">加入股票篮子</n-button>
          </n-space>
        </div>
      </template>
    </ReportLayout>
  </n-spin>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useStore } from "vuex";
import { useMessage, NResult, NSpin } from "naive-ui";
import ReportLayout from "@/layouts/ReportLayout.vue";
import NetValueChart from "@/components/charts/NetValueChart.vue";
import DrawdownChart from "@/components/charts/DrawdownChart.vue";
import MonthlyReturnChart from "@/components/charts/MonthlyReturnChart.vue";
import ProfitDistributionChart from "@/components/charts/ProfitDistributionChart.vue";
import HoldingAnalysisChart from "@/components/charts/HoldingAnalysisChart.vue";
import ParameterSensitivity from "@/components/charts/ParameterSensitivity.vue";
import TradeTable from "@/components/data/TradeTable.vue";
import StatCard from "@/components/common/StatCard.vue";

const props = defineProps<{ id?: string }>();
const message = useMessage();
const store = useStore<any>();

const loading = ref(false);
const error = ref(false);
const activeTradeTab = ref("trades");
const report = ref({
  summary: {
    annualReturn: 0.152,
    totalReturn: 0.482,
    maxDrawdown: -0.215,
    sharpeRatio: 1.28,
    winRate: 0.65,
    profitFactor: 1.82,
    tradesCount: 142,
    avgTradeReturn: 0.012,
  },
  equityCurve: [
    { date: "2022-01", value: 100000 },
    { date: "2022-02", value: 102500 },
  ],
  benchmark: [
    { date: "2022-01", value: 100000 },
    { date: "2022-02", value: 101200 },
  ],
  drawdown: [
    { date: "2022-01", value: -0.05 },
    { date: "2022-02", value: -0.12 },
  ],
  monthlyReturns: [
    { month: "2022-01", return: 0.025 },
    { month: "2022-02", return: 0.018 },
  ],
  profitDistribution: {
    bins: [-0.05, -0.03, -0.01, 0.01, 0.03, 0.05],
    counts: [5, 12, 28, 35, 42, 20],
  },
  holdings: [
    { symbol: "600519.SH", name: "贵州茅台", weight: 0.15, return: 0.32 },
  ],
  trades: [
    {
      id: 1,
      symbol: "600519.SH",
      name: "贵州茅台",
      direction: "buy",
      date: "2022-01-15",
      price: 1850.5,
      quantity: 100,
      amount: 185050,
      fee: 55.52,
    },
  ],
  parameterSensitivity: {
    params: ["sma_short", "sma_long", "trade_size"],
    metrics: ["annualReturn", "maxDrawdown", "sharpeRatio"],
    data: [],
  },
});

const strategy = computed(
  () => store.state.strategy?.currentStrategy || { name: "未知策略" },
);

const loadReport = () => {
  loading.value = true;
  error.value = false;
  setTimeout(() => {
    loading.value = false;
  }, 1000);
};

const saveReport = () => {
  store.dispatch("strategy/saveBacktestReport", {
    id: props.id,
    report: report.value,
  });
  message.success("回测报告已保存");
};
const exportPDF = () => message.info("PDF导出功能正在开发中");
const addToBasket = () => {
  store.dispatch("basket/createBasketFromReport", {
    reportId: props.id,
    basketName: `${strategy.value.name}_股票池`,
  });
  message.success(`已创建股票篮子: ${strategy.value.name}_股票池`);
};
</script>

<style scoped>
.report-header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--n-border-color);
}
.report-header h2 {
  color: var(--n-text-color-1);
}
.summary-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
  margin-top: 20px;
}

.section {
  margin-bottom: 30px;
  padding: 20px;
  background: var(--n-card-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.section h3 {
  color: var(--n-text-color-1);
  margin-bottom: 16px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
}
.metric-card {
  padding: 20px;
  background: var(--n-card-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.metric-card h3 {
  color: var(--n-text-color-1);
  margin-bottom: 16px;
}

.report-footer {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--n-border-color);
}
</style>
