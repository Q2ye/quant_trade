<template>
  <div class="dashboard bg-gradient-mesh bg-noise">
    <ParticleBackground />
    <!-- Loading -->
    <template v-if="pageState === 'loading'">
      <n-grid :x-gap="20" :y-gap="20" :cols="24">
        <n-grid-item v-for="i in 6" :key="i" :span="i <= 2 ? 12 : 12">
          <n-card><n-skeleton :text="true" :repeat="3" /></n-card>
        </n-grid-item>
      </n-grid>
    </template>

    <!-- Error -->
    <n-result
      v-else-if="pageState === 'error'"
      status="500"
      title="数据加载失败"
      description="请检查网络连接后重试"
    >
      <template #footer>
        <n-button type="primary" @click="loadDashboardData">重试</n-button>
      </template>
    </n-result>

    <!-- Empty -->
    <n-empty v-else-if="pageState === 'empty'" description="暂无交易数据" />

    <!-- Data -->
    <n-grid v-else :x-gap="20" :y-gap="20" :cols="24">
      <n-grid-item :span="16">
        <n-card>
          <template #header>
            <div class="card-header">
              <span>资金曲线</span>
              <n-select
                v-model:value="timeRange"
                size="small"
                style="width: 120px"
                :options="rangeOptions"
              />
            </div>
          </template>
          <NetValueChart :data="equityCurve" />
        </n-card>
      </n-grid-item>

      <n-grid-item :span="8">
        <n-card>
          <template #header><span>风险矩阵</span></template>
          <RiskMatrix
            :maxDrawdown="riskData.maxDrawdown"
            :positionRatio="riskData.positionRatio"
            :dailyLoss="riskData.dailyLoss"
            :stocks="riskData.stocks"
          />
        </n-card>
      </n-grid-item>

      <n-grid-item :span="12">
        <n-card>
          <template #header><span>持仓分布</span></template>
          <PositionDistribution :positions="positions" />
        </n-card>
      </n-grid-item>

      <n-grid-item :span="12">
        <n-card>
          <template #header><span>板块强度</span></template>
          <IndustryStrength :industries="industryStrength" />
        </n-card>
      </n-grid-item>

      <n-grid-item :span="12">
        <n-card>
          <template #header><span>今日成交</span></template>
          <RecentTrades :trades="recentTrades" />
        </n-card>
      </n-grid-item>

      <n-grid-item :span="12">
        <n-card>
          <template #header><span>关联公告</span></template>
          <StockAnnouncements :announcements="announcements" />
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineAsyncComponent } from "vue";
const ParticleBackground = defineAsyncComponent(
  () => import("@/components/three/ParticleBackground.vue"),
);
import NetValueChart from "@/components/charts/NetValueChart.vue";
import RiskMatrix from "@/components/trade/RiskMatrix.vue";
import PositionDistribution from "@/components/trade/PositionDistribution.vue";
import IndustryStrength from "@/views/Market/IndustryStrength.vue";
import RecentTrades from "@/components/trade/RecentTrades.vue";
import StockAnnouncements from "@/components/data/StockAnnouncements.vue";

const timeRange = ref("30d");
const pageState = ref<"loading" | "error" | "empty" | "data">("data");

const loadDashboardData = async () => {
  pageState.value = "loading";
  try {
    await new Promise((resolve) => setTimeout(resolve, 800));
    pageState.value = "data";
  } catch {
    pageState.value = "error";
  }
};

onMounted(() => {
  loadDashboardData();
});
const rangeOptions = [
  { label: "7天", value: "7d" },
  { label: "30天", value: "30d" },
  { label: "90天", value: "90d" },
];

const equityCurve = ref([
  { date: "2023-07-10", value: 1000000 },
  { date: "2023-07-17", value: 1023500 },
  { date: "2023-07-24", value: 1056200 },
  { date: "2023-07-31", value: 1037800 },
  { date: "2023-08-07", value: 1074500 },
]);

const riskData = ref({
  maxDrawdown: 4.2,
  positionRatio: 78.5,
  dailyLoss: 1.8,
  stocks: ["600519.SH", "000858.SZ", "601318.SH"],
});

const positions = ref([
  { symbol: "600519.SH", name: "贵州茅台", ratio: 18.2, industry: "食品饮料" },
  { symbol: "000858.SZ", name: "五粮液", ratio: 15.5, industry: "食品饮料" },
  { symbol: "601318.SH", name: "中国平安", ratio: 12.8, industry: "保险" },
  { symbol: "600036.SH", name: "招商银行", ratio: 11.2, industry: "银行" },
  { symbol: "600900.SH", name: "长江电力", ratio: 9.7, industry: "电力" },
]);

const industryStrength = ref([
  { name: "计算机", change: 2.8, strength: 85 },
  { name: "通信", change: 1.5, strength: 78 },
  { name: "传媒", change: 3.2, strength: 92 },
  { name: "电子", change: -0.5, strength: 65 },
  { name: "医药生物", change: 0.8, strength: 72 },
]);

const recentTrades = ref([
  {
    id: 1001,
    symbol: "600519.SH",
    name: "贵州茅台",
    direction: "买入",
    price: 1850.5,
    quantity: 100,
    time: "10:15:23",
  },
  {
    id: 1002,
    symbol: "000001.SH",
    name: "上证指数",
    direction: "卖出",
    price: 3245.67,
    quantity: 200,
    time: "09:42:11",
  },
  {
    id: 1003,
    symbol: "300750.SZ",
    name: "宁德时代",
    direction: "买入",
    price: 232.8,
    quantity: 300,
    time: "13:28:45",
  },
]);

const announcements = ref([
  {
    symbol: "600519.SH",
    title: "贵州茅台2023年半年度业绩预告",
    type: "利好",
    time: "2023-08-08",
  },
  {
    symbol: "601318.SH",
    title: "中国平安7月保费收入公告",
    type: "中性",
    time: "2023-08-07",
  },
  {
    symbol: "000858.SZ",
    title: "五粮液股东减持计划公告",
    type: "利空",
    time: "2023-08-05",
  },
]);
</script>

<style scoped>
.dashboard {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
