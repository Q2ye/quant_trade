<template>
  <div class="risk-monitor bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">实时监控</h1>
        </div>
        <div class="header-actions">
          <n-space :size="12">
            <n-button type="primary" @click="refreshData" :loading="loading">
              <template #icon><Icon icon="ep:refresh" /></template>
              刷新
            </n-button>
            <n-button @click="exportData">
              <template #icon><Icon icon="ep:download" /></template>
              导出
            </n-button>
          </n-space>
        </div>
      </div>
    </div>

    <!-- Error state -->
    <n-result
      v-if="pageError"
      status="500"
      title="数据加载失败"
      description="请检查网络连接后重试"
    >
      <template #footer>
        <n-button type="primary" @click="refreshData">重试</n-button>
      </template>
    </n-result>

    <div v-else class="main-content">
      <!-- 监控概览卡片 -->
      <n-grid
        :x-gap="16"
        :y-gap="16"
        :cols="4"
        responsive="screen"
        class="overview-grid"
      >
        <n-grid-item>
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="getStatusClass(riskStats.totalRiskLevel)"
              >
                {{ riskStats.totalAlerts }}
              </div>
              <div class="metric-label">总警报数</div>
            </div>
            <template #footer>
              <div class="metric-footer">
                <span :class="getTrendClass(riskStats.alertTrend)"
                  >{{ riskStats.alertTrend > 0 ? "↑" : "↓" }}
                  {{ Math.abs(riskStats.alertTrend) }}</span
                >
                较昨日
              </div>
            </template>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="getStatusClass(riskStats.positionRiskLevel)"
              >
                {{ riskStats.positionAlerts }}
              </div>
              <div class="metric-label">持仓风险</div>
            </div>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="getStatusClass(riskStats.accountRiskLevel)"
              >
                ¥{{ formatNumber(riskStats.accountRiskAmount) }}
              </div>
              <div class="metric-label">账户风险金额</div>
            </div>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="getStatusClass(riskStats.systemRiskLevel)"
              >
                {{ riskStats.systemAlerts }}
              </div>
              <div class="metric-label">系统风险</div>
            </div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <!-- 实时风险图表 -->
      <n-grid
        :x-gap="16"
        :y-gap="16"
        :cols="2"
        responsive="screen"
        class="chart-grid"
      >
        <n-grid-item>
          <n-card class="chart-card">
            <template #header>
              <div class="chart-header">
                <span>风险事件趋势</span>
                <n-select
                  v-model:value="trendPeriod"
                  size="small"
                  style="width: 120px"
                  :options="periodOptions"
                />
              </div>
            </template>
            <div ref="riskTrendChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card class="chart-card">
            <template #header>
              <div class="chart-header"><span>风险类型分布</span></div>
            </template>
            <div ref="riskTypeChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <!-- 实时警报列表 -->
      <n-card class="alerts-card">
        <template #header>
          <div class="alerts-header">
            <span>实时风险警报</span>
            <n-space :size="8">
              <n-select
                v-model:value="alertFilter.level"
                placeholder="风险等级"
                size="small"
                style="width: 100px"
                clearable
                :options="levelOptions"
              />
              <n-select
                v-model:value="alertFilter.type"
                placeholder="风险类型"
                size="small"
                style="width: 120px"
                clearable
                :options="typeOptions"
              />
            </n-space>
          </div>
        </template>

        <n-spin :show="loading">
          <n-data-table
            :columns="alertColumns"
            :data="filteredAlerts"
            :bordered="false"
            size="small"
          >
            <template #empty>
              <n-empty description="暂无风险警报" />
            </template>
          </n-data-table>

          <div class="pagination-container">
            <n-pagination
              v-model:page="currentPage"
              :item-count="filteredAlerts.length"
              :page-size="10"
            />
          </div>
        </n-spin>
      </n-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, h } from "vue";
import { useMessage, useDialog, NTag, NButton } from "naive-ui";
import { Icon } from "@iconify/vue";
import riskAPI from "@/api/risk";
import * as echarts from "echarts";

const message = useMessage();
const dialog = useDialog();

const loading = ref(false);
const pageError = ref(false);
const trendPeriod = ref("today");
const riskTrendChart = ref(null);
const riskTypeChart = ref(null);
const currentPage = ref(1);

const periodOptions = [
  { label: "今日", value: "today" },
  { label: "本周", value: "week" },
  { label: "本月", value: "month" },
];
const levelOptions = [
  { label: "高风险", value: "high" },
  { label: "中风险", value: "medium" },
  { label: "低风险", value: "low" },
];
const typeOptions = [
  { label: "持仓风险", value: "position" },
  { label: "账户风险", value: "account" },
  { label: "系统风险", value: "system" },
];

const riskStats = reactive({
  totalAlerts: 12,
  positionAlerts: 5,
  accountRiskAmount: 125000,
  systemAlerts: 3,
  totalRiskLevel: "medium",
  positionRiskLevel: "high",
  accountRiskLevel: "medium",
  systemRiskLevel: "low",
  alertTrend: 2,
});

const alertFilter = reactive({ level: "", type: "" });

const alerts = ref([
  {
    id: 1,
    time: new Date("2024-01-15 14:30:25"),
    strategyName: "双均线策略",
    symbol: "000001.SZ",
    type: "position",
    level: "high",
    description: "持仓集中度超过阈值：45%",
    action: "pending",
  },
  {
    id: 2,
    time: new Date("2024-01-15 14:25:10"),
    strategyName: "动量反转",
    symbol: "600519.SH",
    type: "account",
    level: "medium",
    description: "单日亏损达到预警线：-3.5%",
    action: "processed",
  },
  {
    id: 3,
    time: new Date("2024-01-15 14:20:45"),
    strategyName: "系统监控",
    symbol: "",
    type: "system",
    level: "low",
    description: "数据同步延迟超过5分钟",
    action: "ignored",
  },
]);

const filteredAlerts = computed(() => {
  let result = alerts.value;
  if (alertFilter.level)
    result = result.filter((a) => a.level === alertFilter.level);
  if (alertFilter.type)
    result = result.filter((a) => a.type === alertFilter.type);
  return result;
});

const alertColumns = [
  {
    title: "时间",
    key: "time",
    width: 140,
    render: (row) => new Date(row.time).toLocaleTimeString("zh-CN"),
  },
  { title: "策略", key: "strategyName", width: 120 },
  { title: "标的", key: "symbol", width: 100 },
  {
    title: "风险类型",
    key: "type",
    width: 100,
    render: (row) =>
      h(
        NTag,
        {
          type:
            row.type === "position"
              ? "error"
              : row.type === "account"
                ? "warning"
                : "info",
          size: "small",
        },
        {
          default: () =>
            row.type === "position"
              ? "持仓风险"
              : row.type === "account"
                ? "账户风险"
                : "系统风险",
        },
      ),
  },
  {
    title: "风险等级",
    key: "level",
    width: 100,
    render: (row) =>
      h(
        NTag,
        {
          type:
            row.level === "high"
              ? "error"
              : row.level === "medium"
                ? "warning"
                : "info",
          size: "small",
        },
        {
          default: () =>
            row.level === "high"
              ? "高风险"
              : row.level === "medium"
                ? "中风险"
                : "低风险",
        },
      ),
  },
  { title: "风险描述", key: "description", minWidth: 200 },
  {
    title: "处理动作",
    key: "action",
    width: 120,
    render: (row) =>
      h(
        NTag,
        {
          type:
            row.action === "pending"
              ? "warning"
              : row.action === "processed"
                ? "success"
                : "info",
          size: "small",
        },
        {
          default: () =>
            row.action === "pending"
              ? "待处理"
              : row.action === "processed"
                ? "已处理"
                : "已忽略",
        },
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 80,
    render: (row) =>
      h(
        NButton,
        { size: "small", onClick: () => handleAlertAction(row) },
        { default: () => "处理" },
      ),
  },
];

const getStatusClass = (level) =>
  ({ high: "status-high", medium: "status-medium", low: "status-low" })[
    level
  ] || "status-low";
const getTrendClass = (trend) => (trend > 0 ? "trend-up" : "trend-down");
const formatNumber = (num) => new Intl.NumberFormat("zh-CN").format(num);

const refreshData = async () => {
  await loadData();
  message.success("数据刷新成功");
};

const exportData = () => message.info("导出功能开发中");

const handleAlertAction = (alert) => {
  dialog.warning({
    title: "处理风险警报",
    content: `确定要处理这条风险警报吗？\n${alert.description}`,
    positiveText: "确认处理",
    negativeText: "取消",
    onPositiveClick: () => {
      alert.action = "processed";
      message.success("风险警报已处理");
    },
  });
};

let trendChartInstance = null;
let typeChartInstance = null;
const handleRiskResize = () => {
  trendChartInstance?.resize();
  typeChartInstance?.resize();
};

const initCharts = () => {
  // dispose old instances before re-init
  if (trendChartInstance) { trendChartInstance.dispose(); trendChartInstance = null; }
  if (typeChartInstance) { typeChartInstance.dispose(); typeChartInstance = null; }
  if (riskTrendChart.value) {
    trendChartInstance = echarts.init(riskTrendChart.value);
    trendChartInstance.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["高风险", "中风险", "低风险"], bottom: 0 },
      grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
      xAxis: {
        type: "category",
        data: ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
      },
      yAxis: { type: "value" },
      series: [
        {
          name: "高风险",
          type: "line",
          data: [2, 3, 1, 4, 2, 3, 2],
          itemStyle: { color: "#f56c6c" },
        },
        {
          name: "中风险",
          type: "line",
          data: [5, 4, 6, 3, 5, 4, 3],
          itemStyle: { color: "#e6a23c" },
        },
        {
          name: "低风险",
          type: "line",
          data: [3, 2, 4, 2, 3, 1, 2],
          itemStyle: { color: "#909399" },
        },
      ],
    });
  }
  if (riskTypeChart.value) {
    typeChartInstance = echarts.init(riskTypeChart.value);
    typeChartInstance.setOption({
      tooltip: { trigger: "item" },
      legend: { bottom: 0 },
      series: [
        {
          name: "风险类型",
          type: "pie",
          radius: ["40%", "70%"],
          center: ["50%", "45%"],
          itemStyle: { borderRadius: 10, borderColor: "#fff", borderWidth: 2 },
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 18, fontWeight: "bold" } },
          data: [
            { value: 45, name: "持仓风险", itemStyle: { color: "#f56c6c" } },
            { value: 30, name: "账户风险", itemStyle: { color: "#e6a23c" } },
            { value: 25, name: "系统风险", itemStyle: { color: "#67c23a" } },
          ],
        },
      ],
    });
  }
};

const loadData = async () => {
  loading.value = true;
  pageError.value = false;
  try {
    const alerts = await riskAPI.getRiskAlerts().catch(() => []);
    if (Array.isArray(alerts) && alerts.length > 0) {
      riskStats.totalAlerts = alerts.length;
    }
    initCharts();
  } catch {
    pageError.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadData();
  window.addEventListener("resize", handleRiskResize);
});
onUnmounted(() => {
  window.removeEventListener("resize", handleRiskResize);
  trendChartInstance?.dispose();
  typeChartInstance?.dispose();
});
</script>

<style lang="scss" scoped>
.risk-monitor {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.overview-grid {
  margin-bottom: 24px;

  :deep(.n-card) {
    height: 100%;
  }
  :deep(.n-card__content) {
    padding: 12px 16px 8px;
  }
  :deep(.n-card-footer) {
    padding: 4px 16px 10px;
  }
}

.metric-content {
  text-align: center;
  .metric-value {
    font-size: 26px;
    font-weight: bold;
    margin-bottom: 4px;
  }
  .metric-label {
    color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
    font-size: 12px;
  }
}

.status-high {
  color: #f56c6c;
}
.status-medium {
  color: #e6a23c;
}
.status-low {
  color: #67c23a;
}

.metric-footer {
  text-align: center;
  color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
  font-size: 12px;
}
.trend-up {
  color: #f56c6c;
}
.trend-down {
  color: #67c23a;
}

.chart-grid {
  margin-bottom: 24px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chart-container {
  height: 300px;
}

.alerts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
