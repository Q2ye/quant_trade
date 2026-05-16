<template>
  <div class="execution-analysis bg-gradient-mesh bg-noise">
    <div class="page-header">
      <h1>交易执行分析</h1>
      <p>分析订单执行质量和交易成本</p>
    </div>

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
                  <Icon
                    :icon="
                      stat.trend === 'up'
                        ? 'mdi:trending-up'
                        : 'mdi:trending-down'
                    "
                  />
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
              <div ref="priceChartRef" style="height: 300px"></div>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card>
              <template #header><span>执行时间分布</span></template>
              <div ref="timeChartRef" style="height: 300px"></div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>交易执行记录</span>
              <n-space :size="8">
                <n-date-picker
                  v-model:value="dateRange"
                  type="daterange"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                />
                <n-button type="primary" @click="exportData">导出数据</n-button>
              </n-space>
            </div>
          </template>

          <n-data-table
            :columns="columns"
            :data="executionRecords"
            :bordered="false"
            size="small"
          />

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
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, h } from "vue";
import * as echarts from "echarts";
import { useMessage, NTag, NSpin, NResult } from "naive-ui";
import { Icon } from "@iconify/vue";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
const dateRange = ref<any>(null);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(150);
const priceChartRef = ref<HTMLElement>();
const timeChartRef = ref<HTMLElement>();

const executionStats = ref([
  { name: "平均滑点", value: "-0.0023", change: "0.0012", trend: "down" },
  { name: "执行成功率", value: "99.8%", change: "0.3%", trend: "up" },
  { name: "平均执行时间", value: "1.2s", change: "-0.3s", trend: "down" },
  { name: "VWAP偏差", value: "-0.0015", change: "0.0008", trend: "down" },
  { name: "交易成本", value: "0.12%", change: "-0.02%", trend: "down" },
  { name: "大单执行率", value: "95.6%", change: "1.2%", trend: "up" },
]);

const executionRecords = ref([
  {
    orderId: "ORD001234",
    symbol: "000001.SZ",
    direction: "BUY",
    quantity: 1000,
    targetPrice: 15.2,
    executedPrice: 15.198,
    slippage: -0.002,
    executionTime: "2024-01-15 09:30:15",
    status: "已完成",
  },
]);

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
const handleResize = () => {
  priceChart?.resize();
  timeChart?.resize();
};

const initCharts = () => {
  if (priceChartRef.value) {
    priceChart = echarts.init(priceChartRef.value);
    priceChart.setOption({
      tooltip: { trigger: "axis" },
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
      ],
    });
  }
  if (timeChartRef.value) {
    timeChart = echarts.init(timeChartRef.value);
    timeChart.setOption({
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        data: ["<1s", "1-2s", "2-3s", "3-5s", "5-10s", ">10s"],
      },
      yAxis: { type: "value", name: "订单数量" },
      series: [
        { name: "执行时间分布", type: "bar", data: [120, 85, 45, 30, 15, 5] },
      ],
    });
  }
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
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
});
</script>

<style scoped>
.execution-analysis {
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.page-header h1 {
  margin: 0;
  color: var(--n-text-color-1);
}
.page-header p {
  color: var(--n-text-color-3);
}
.stats-row {
  margin-bottom: 24px;
}
.charts-row {
  margin-bottom: 24px;
}

.stat-content {
  text-align: center;
  padding: 16px 8px;
}
.stat-value {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}
.stat-value.up {
  color: #f56c6c;
}
.stat-value.down {
  color: #67c23a;
}
.stat-label {
  color: var(--n-text-color-3);
  font-size: 14px;
  margin-bottom: 4px;
}
.stat-trend {
  font-size: 12px;
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
