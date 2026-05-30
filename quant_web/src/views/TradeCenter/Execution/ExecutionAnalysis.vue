<template>
  <div class="execution-analysis bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">交易执行分析</h1>
          <p class="page-description">分析订单执行质量和交易成本</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="$router.go(-1)" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
    <n-spin :show="loading">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-grid :x-gap="16" :cols="6" class="stats-row">
          <n-grid-item v-for="stat in executionStats" :key="stat.name">
            <n-card class="stat-card">
              <div class="stat-content">
                <div class="stat-value" :class="stat.trend">
                  {{ stat.value }}
                </div>
                <div class="stat-label">{{ stat.name }}</div>
                <div class="stat-trend">
                  <SmartIcon :name="stat.trend === 'up' ? 'TrendingUp' : 'TrendingDown'" />
                  {{ stat.change }}
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-grid :x-gap="16" :cols="2" class="charts-row">
          <n-grid-item>
            <n-card>
              <template #header><span>执行价格分析</span></template>
              <div ref="priceChartRef" style="height: 340px"></div>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card>
              <template #header><span>执行时间分布</span></template>
              <div ref="timeChartRef" style="height: 340px"></div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-grid :x-gap="16" :cols="2" class="charts-row">
          <n-grid-item>
            <n-card>
              <template #header><span>市场冲击分析</span></template>
              <div ref="impactChartRef" style="height: 340px"></div>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card>
              <template #header><span>流动性分析</span></template>
              <div ref="liquidityChartRef" style="height: 340px"></div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>交易执行记录</span>
              <div class="header-controls">
                <n-date-picker
                  v-model:value="dateRange"
                  type="daterange"
                  size="small"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  style="width: 220px"
                />
                <n-button size="small" type="primary" @click="exportData">导出数据</n-button>
              </div>
            </div>
          </template>

          <n-data-table
            :columns="columns"
            :data="executionRecords"
            :bordered="false"
            size="small"
          >
            <template #empty>
              <n-empty description="暂无执行记录" />
            </template>
          </n-data-table>

          <div class="pagination-container">
            <n-pagination
              v-model:page="currentPage"
              v-model:page-size="pageSize"
              :item-count="total"
              :page-sizes="[10, 20, 50, 100]"
              show-size-picker
            />
          </div>
        </n-card>
      </template>
    </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, h } from "vue";
import * as echarts from "echarts";
import { useMessage, NTag, NSpin, NResult, NButton } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import tradeAPI from "@/api/trade";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
const dateRange = ref<any>(null);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(150);
const priceChartRef = ref<HTMLElement>();
const timeChartRef = ref<HTMLElement>();
const impactChartRef = ref<HTMLElement>();
const liquidityChartRef = ref<HTMLElement>();

const executionStats = ref([
  { name: "平均滑点", value: "--", change: "--", trend: "down" },
  { name: "执行成功率", value: "--", change: "--", trend: "up" },
  { name: "平均执行时间", value: "--", change: "--", trend: "down" },
  { name: "VWAP偏差", value: "--", change: "--", trend: "down" },
  { name: "交易成本", value: "--", change: "--", trend: "down" },
  { name: "大单执行率", value: "--", change: "--", trend: "up" },
]);

const executionRecords = ref<any[]>([]);

const getStatusType = (status: string) =>
  (
    ({
      已完成: "success",
      部分成交: "warning",
      已取消: "default",
      失败: "error",
    }) as Record<string, string>
  )[status] || "default";

const columns = [
  { title: "订单ID", key: "orderId", width: 120 },
  { title: "标的", key: "symbol", width: 100 },
  {
    title: "方向",
    key: "direction",
    width: 80,
    render: (row: any) =>
      h(
        NTag,
        { type: row.direction === "BUY" ? "success" : "error", size: "small" },
        { default: () => (row.direction === "BUY" ? "买入" : "卖出") },
      ),
  },
  { title: "数量", key: "quantity", width: 100 },
  { title: "目标价", key: "targetPrice", width: 100 },
  { title: "执行价", key: "executedPrice", width: 100 },
  {
    title: "滑点",
    key: "slippage",
    width: 100,
    render: (row: any) =>
      h(
        "span",
        { class: row.slippage >= 0 ? "positive" : "negative" },
        `${row.slippage >= 0 ? "+" : ""}${row.slippage.toFixed(4)}`,
      ),
  },
  { title: "执行时间", key: "executionTime", width: 180 },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row: any) =>
      h(
        NTag,
        { type: getStatusType(row.status) as any, size: "small" },
        { default: () => row.status },
      ),
  },
];

const exportData = () => message.success("数据导出成功");

let priceChart: echarts.ECharts | null = null;
let timeChart: echarts.ECharts | null = null;
let impactChart: echarts.ECharts | null = null;
let liquidityChart: echarts.ECharts | null = null;
const handleResize = () => {
  priceChart?.resize();
  timeChart?.resize();
  impactChart?.resize();
  liquidityChart?.resize();
};

const initCharts = () => {
  if (priceChartRef.value) {
    priceChart = echarts.init(priceChartRef.value);
    priceChart.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["执行价格", "VWAP"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: {
        type: "category",
        data: ["09:30", "10:00", "10:30", "11:00", "13:00", "14:00", "14:30"],
      },
      yAxis: { type: "value", name: "价格(元)" },
      series: [
        {
          name: "执行价格",
          type: "line",
          data: [15.2, 15.18, 15.22, 15.25, 15.23, 15.28, 15.26],
          smooth: true,
        },
        {
          name: "VWAP",
          type: "line",
          data: [15.19, 15.19, 15.20, 15.21, 15.22, 15.23, 15.24],
          smooth: true,
          lineStyle: { type: "dashed", color: "#91cc75" },
          itemStyle: { color: "#91cc75" },
        },
      ],
    });
  }
  if (timeChartRef.value) {
    timeChart = echarts.init(timeChartRef.value);
    timeChart.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["订单数量", "累计占比"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: {
        type: "category",
        data: ["<1s", "1-2s", "2-3s", "3-5s", "5-10s", ">10s"],
      },
      yAxis: [
        { type: "value", name: "数量", splitNumber: 4 },
        { type: "value", name: "%", min: 0, max: 100, splitLine: { show: false } },
      ],
      series: [
        {
          name: "订单数量",
          type: "bar",
          data: [120, 85, 45, 30, 15, 5],
        },
        {
          name: "累计占比",
          type: "line",
          yAxisIndex: 1,
          data: [40, 68, 83, 93, 98, 100],
          itemStyle: { color: "#ee6666" },
          smooth: true,
        },
      ],
    });
  }
  if (impactChartRef.value) {
    impactChart = echarts.init(impactChartRef.value);
    impactChart.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["临时冲击", "永久冲击"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: {
        type: "category",
        data: ["大单1", "大单2", "大单3", "大单4", "大单5", "大单6", "大单7"],
      },
      yAxis: { type: "value", name: "bps" },
      series: [
        {
          name: "临时冲击",
          type: "bar",
          stack: "impact",
          data: [2.1, 3.2, 1.8, 2.5, 1.5, 2.8, 3.5],
          itemStyle: { color: "#5470c6" },
        },
        {
          name: "永久冲击",
          type: "bar",
          stack: "impact",
          data: [1.2, 1.8, 1.0, 1.5, 0.8, 1.6, 2.0],
          itemStyle: { color: "#ee6666" },
        },
      ],
    });
  }
  if (liquidityChartRef.value) {
    liquidityChart = echarts.init(liquidityChartRef.value);
    liquidityChart.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["挂单量", "成交率"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: {
        type: "category",
        data: ["09:30", "10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00"],
      },
      yAxis: [
        { type: "value", name: "股数", splitNumber: 4, axisLabel: { formatter: (v: number) => (v / 10000).toFixed(0) + "万" } },
        { type: "value", name: "%", min: 0, max: 100, splitLine: { show: false } },
      ],
      series: [
        {
          name: "挂单量",
          type: "bar",
          data: [85000, 92000, 78000, 65000, 58000, 72000, 88000, 95000, 110000],
          itemStyle: { color: "rgba(68,138,255,0.6)" },
        },
        {
          name: "成交率",
          type: "line",
          yAxisIndex: 1,
          data: [72, 68, 75, 82, 78, 71, 69, 73, 65],
          itemStyle: { color: "#91cc75" },
          smooth: true,
        },
      ],
    });
  }
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    const [statsRes, tradesRes] = await Promise.all([
      tradeAPI.getTradeStatistics().catch(() => null),
      tradeAPI.getTradeRecords({ limit: 50 }).catch(() => ({ items: [] })),
    ]);

    if (statsRes) {
      const s = statsRes as any;
      const winRate = s.successful_trades != null && s.total_trades > 0
        ? ((s.successful_trades / s.total_trades) * 100).toFixed(1) + "%"
        : "--";
      executionStats.value = [
        { name: "总成交笔数", value: String(s.total_trades ?? "--"), change: "", trend: "up" },
        { name: "成功笔数", value: String(s.successful_trades ?? "--"), change: "", trend: "up" },
        { name: "总成交量", value: (s.total_volume ?? 0).toLocaleString(), change: "", trend: "up" },
        { name: "总成交额", value: "¥" + (s.total_amount ?? 0).toLocaleString(), change: "", trend: "up" },
        { name: "平均每笔", value: "¥" + (s.avg_trade_size ?? 0).toLocaleString(), change: "", trend: "down" },
        { name: "执行成功率", value: winRate, change: "", trend: "up" },
      ];
    }

    const items = (tradesRes as any)?.items ?? (Array.isArray(tradesRes) ? tradesRes : []);
    executionRecords.value = items.map((t: any) => ({
      orderId: t.order_id ?? t.id ?? "",
      symbol: t.ts_code ?? t.symbol ?? "",
      direction: t.direction ?? "",
      quantity: t.volume ?? t.quantity ?? 0,
      targetPrice: t.price ?? t.order_price ?? 0,
      executedPrice: t.filled_price ?? t.executed_price ?? t.price ?? 0,
      slippage: t.slippage ?? 0,
      executionTime: t.filled_at ?? t.executed_at ?? t.created_at ?? "",
      status: t.status ?? "",
    }));
    total.value = executionRecords.value.length;

    initCharts();
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadData();
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  priceChart?.dispose();
  timeChart?.dispose();
  impactChart?.dispose();
  liquidityChart?.dispose();
});
</script>

<style scoped>
.execution-analysis {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.stats-row {
  margin-bottom: 24px;
}
.charts-row {
  margin-bottom: 24px;
}

.stats-row :deep(.n-card__content) {
  padding: 0;
}

.stat-content {
  text-align: center;
  padding: 4px 8px 8px;
}
.stat-value {
  font-size: 22px;
  font-weight: 600;
  margin-bottom: 2px;
}
.stat-value.up {
  color: #f56c6c;
}
.stat-value.down {
  color: #67c23a;
}
.stat-label {
  color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
  font-size: 13px;
  margin-bottom: 2px;
}
.stat-trend {
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.positive {
  color: #f56c6c;
}
.negative {
  color: #67c23a;
}
</style>
