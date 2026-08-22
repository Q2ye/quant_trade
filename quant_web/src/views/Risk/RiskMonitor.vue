<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, h, watch } from "vue";
import { useStore } from "vuex";
import { NTag, NButton, NSpin, NResult, useMessage, useDialog } from "naive-ui";
import * as echarts from "echarts";
import riskAPI from "@/api/risk";
import type { RiskAlert, RiskMetricsData } from "@/api/risk";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { usePagedList } from "@/composables/usePagedList";

const store = useStore();
const message = useMessage();
const dialog = useDialog();

const loading = ref(false);
const pageError = ref(false);
const trendPeriod = ref("today");
const riskTrendChart = ref<HTMLDivElement | null>(null);
const riskTypeChart = ref<HTMLDivElement | null>(null);

// 从 store 读取的实时指标
const metricsData = ref<RiskMetricsData | null>(null);
const alerts = ref<RiskAlert[]>([]);
const events = computed(() => store.state.risk.riskEvents.events);

const periodOptions = [
  { label: "今日", value: "today" },
  { label: "本周", value: "week" },
  { label: "本月", value: "month" },
];
const levelOptions = [
  { label: "严重", value: "critical" },
  { label: "警告", value: "warning" },
  { label: "信息", value: "info" },
];

const alertFilter = reactive({ level: "", type: "" });

// 统计卡片数据（从 metrics API 计算）
const riskStats = computed(() => {
  const m = metricsData.value;
  return {
    totalAlerts: m?.breach_count ?? alerts.value.length,
    positionRatio: m?.position_ratio ?? 0,
    drawdown: m?.drawdown ?? 0,
    riskLevel: m?.overall_risk_level ?? "normal",
    breachCount: m?.breach_count ?? 0,
  };
});

const filteredAlerts = computed(() => {
  let result = alerts.value;
  if (alertFilter.level)
    result = result.filter((a) => a.level === alertFilter.level);
  return result;
});

// 客户端分页：表格展示切片后的当前页
const {
  page: currentPage,
  itemCount: alertTotal,
  pagedData: pagedAlerts,
} = usePagedList(filteredAlerts, 10);

// 告警级别筛选变化时回到第一页
watch(
  () => alertFilter.level,
  () => {
    currentPage.value = 1;
  },
);

const alertColumns = [
  {
    title: "时间",
    key: "created_at",
    width: 160,
    render: (row: RiskAlert) =>
      row.created_at
        ? new Date(row.created_at).toLocaleString("zh-CN")
        : "-",
  },
  {
    title: "级别",
    key: "level",
    width: 80,
    render: (row: RiskAlert) =>
      h(
        NTag,
        {
          type: row.level === "critical" ? "error" : row.level === "warning" ? "warning" : "info",
          size: "small",
        },
        {
          default: () =>
            row.level === "critical" ? "严重" : row.level === "warning" ? "警告" : "信息",
        },
      ),
  },
  { title: "标题", key: "title", minWidth: 150, ellipsis: { tooltip: true } },
  { title: "消息", key: "message", minWidth: 200, ellipsis: { tooltip: true } },
  {
    title: "状态",
    key: "acknowledged",
    width: 80,
    render: (row: RiskAlert) =>
      h(
        NTag,
        { type: row.acknowledged ? "success" : "warning", size: "small" },
        { default: () => (row.acknowledged ? "已确认" : "待处理") },
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 80,
    render: (row: RiskAlert) =>
      !row.acknowledged
        ? h(
            NButton,
            {
              size: "small",
              onClick: () => handleAcknowledge(row),
            },
            { default: () => "确认" },
          )
        : h("span", { style: { color: "var(--n-text-color-3)" } }, "-"),
  },
];

// ==================== 数据加载 ====================

const loadMetrics = async () => {
  try {
    const data = await riskAPI.getRiskMetrics();
    metricsData.value = data;
  } catch {
    // metrics 可能因引擎未就绪而失败，静默处理
    metricsData.value = null;
  }
};

const loadAlerts = async () => {
  try {
    const result = await riskAPI.getRiskAlerts();
    alerts.value = result.items || [];
  } catch {
    alerts.value = [];
  }
};

const loadEvents = async () => {
  try {
    await store.dispatch("risk/fetchRiskEvents", { page: 1, page_size: 100 });
  } catch {
    // 事件为空时静默处理
  }
};

const loadData = async () => {
  loading.value = true;
  pageError.value = false;
  try {
    await Promise.all([loadMetrics(), loadAlerts(), loadEvents()]);
  } catch {
    pageError.value = true;
  } finally {
    loading.value = false;
  }
};

const refreshData = async () => {
  await loadData();
  initCharts();
  message.success("数据刷新成功");
};

const handleAcknowledge = async (alert: RiskAlert) => {
  if (!alert.id) return;
  try {
    await riskAPI.acknowledgeRiskAlert(alert.id);
    alert.acknowledged = true;
    message.success("告警已确认");
  } catch {
    message.error("确认失败");
  }
};

// ==================== ECharts ====================

let trendChartInstance: echarts.ECharts | null = null;
let typeChartInstance: echarts.ECharts | null = null;

const handleRiskResize = () => {
  trendChartInstance?.resize();
  typeChartInstance?.resize();
};

const initCharts = () => {
  // 清理旧实例
  trendChartInstance?.dispose();
  typeChartInstance?.dispose();

  // 风险事件趋势图
  if (riskTrendChart.value) {
    trendChartInstance = echarts.init(riskTrendChart.value);
    const evts = events.value;
    if (evts.length > 0) {
      // 按小时聚合事件数
      const hourBuckets: Record<string, number> = {};
      evts.forEach((e: any) => {
        const hour = e.timestamp
          ? new Date(e.timestamp).toISOString().slice(11, 13) + ":00"
          : "--:--";
        hourBuckets[hour] = (hourBuckets[hour] || 0) + 1;
      });
      const sortedHours = Object.keys(hourBuckets).sort();
      const criticalCounts = sortedHours.map(
        (h) => evts.filter((e: any) => {
          const eh = e.timestamp ? new Date(e.timestamp).toISOString().slice(11, 13) + ":00" : "";
          return eh === h && e.level === "critical";
        }).length,
      );
      const warningCounts = sortedHours.map(
        (h) => evts.filter((e: any) => {
          const eh = e.timestamp ? new Date(e.timestamp).toISOString().slice(11, 13) + ":00" : "";
          return eh === h && (e.level === "error" || e.level === "warning");
        }).length,
      );
      const infoCounts = sortedHours.map(
        (h) => evts.filter((e: any) => {
          const eh = e.timestamp ? new Date(e.timestamp).toISOString().slice(11, 13) + ":00" : "";
          return eh === h && e.level === "info";
        }).length,
      );

      trendChartInstance.setOption({
        tooltip: { trigger: "axis" },
        legend: { data: ["严重", "警告", "信息"], bottom: 0 },
        grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
        xAxis: { type: "category", data: sortedHours },
        yAxis: { type: "value", minInterval: 1 },
        series: [
          { name: "严重", type: "line", data: criticalCounts, itemStyle: { color: "#f56c6c" }, smooth: true },
          { name: "警告", type: "line", data: warningCounts, itemStyle: { color: "#e6a23c" }, smooth: true },
          { name: "信息", type: "line", data: infoCounts, itemStyle: { color: "#909399" }, smooth: true },
        ],
      });
    } else {
      trendChartInstance.setOption({
        title: { text: "暂无事件数据", left: "center", top: "center", textStyle: { color: "#909399", fontSize: 14 } },
        grid: { left: "3%", right: "4%", top: 12, bottom: 32, containLabel: true },
        xAxis: { type: "category", data: [] },
        yAxis: { type: "value" },
        series: [],
      });
    }
  }

  // 风险类型分布饼图
  if (riskTypeChart.value) {
    typeChartInstance = echarts.init(riskTypeChart.value);
    const evts = events.value;
    if (evts.length > 0) {
      const typeBuckets: Record<string, number> = {};
      evts.forEach((e: any) => {
        const t = e.type || "未知";
        typeBuckets[t] = (typeBuckets[t] || 0) + 1;
      });
      const pieData = Object.entries(typeBuckets).map(([name, value], i) => ({
        value,
        name,
        itemStyle: {
          color: ["#f56c6c", "#e6a23c", "#67c23a", "#409eff", "#909399"][i % 5],
        },
      }));

      typeChartInstance.setOption({
        tooltip: { trigger: "item" },
        legend: { bottom: 0 },
        series: [
          {
            name: "风险类型",
            type: "pie",
            radius: ["40%", "70%"],
            center: ["50%", "45%"],
            itemStyle: { borderRadius: 10, borderColor: "transparent", borderWidth: 2 },
            label: { show: false },
            emphasis: { label: { show: true, fontSize: 16, fontWeight: "bold" } },
            data: pieData,
          },
        ],
      });
    } else {
      typeChartInstance.setOption({
        title: { text: "暂无事件数据", left: "center", top: "center", textStyle: { color: "#909399", fontSize: 14 } },
        series: [
          {
            type: "pie",
            radius: ["40%", "70%"],
            center: ["50%", "45%"],
            data: [{ value: 1, name: "等待数据", itemStyle: { color: "#363840" } }],
            label: { show: false },
            silent: true,
          },
        ],
      });
    }
  }
};

// 数据变化时重绘图表
watch(events, () => {
  initCharts();
});

// ==================== 生命周期 ====================

onMounted(() => {
  loadData().then(() => initCharts());
  window.addEventListener("resize", handleRiskResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleRiskResize);
  trendChartInstance?.dispose();
  typeChartInstance?.dispose();
});
</script>

<template>
  <div class="risk-monitor bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">实时风险监控</h1>
          <p class="page-subtitle">
            风险指标来自风控引擎定时巡检（默认每 60 秒），告警和事件实时推送更新。
          </p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- Error state -->
    <n-result
      v-if="pageError"
      status="500"
      title="数据加载失败"
      description="请检查风控引擎是否正常启动后重试"
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
                :class="
                  riskStats.riskLevel === 'critical'
                    ? 'status-critical'
                    : riskStats.riskLevel === 'warning'
                      ? 'status-warning'
                      : 'status-normal'
                "
              >
                {{ riskStats.totalAlerts }}
              </div>
              <div class="metric-label">违规/告警次数</div>
            </div>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="riskStats.positionRatio > 80 ? 'status-critical' : riskStats.positionRatio > 60 ? 'status-warning' : 'status-normal'"
              >
                {{ riskStats.positionRatio.toFixed(1) }}%
              </div>
              <div class="metric-label">仓位比例</div>
            </div>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card class="metric-card">
            <div class="metric-content">
              <div
                class="metric-value"
                :class="riskStats.drawdown > 20 ? 'status-critical' : riskStats.drawdown > 10 ? 'status-warning' : 'status-normal'"
              >
                {{ riskStats.drawdown.toFixed(1) }}%
              </div>
              <div class="metric-label">当前回撤</div>
            </div>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value status-normal">
                {{ events.length }}
              </div>
              <div class="metric-label">事件总数</div>
            </div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <!-- 风险图表 -->
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
                  style="width: 100px"
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
              <div class="chart-header">
                <span>事件类型分布</span>
              </div>
            </template>
            <div ref="riskTypeChart" class="chart-container"></div>
          </n-card>
        </n-grid-item>
      </n-grid>

      <!-- 实时告警列表 -->
      <n-card class="alerts-card">
        <template #header>
          <div class="alerts-header">
            <span>实时风险告警</span>
            <n-select
              v-model:value="alertFilter.level"
              placeholder="告警级别"
              size="small"
              style="width: 100px"
              clearable
              :options="levelOptions"
            />
          </div>
        </template>

        <n-spin :show="loading">
          <n-data-table
            :columns="alertColumns"
            :data="pagedAlerts"
            :bordered="false"
            size="small"
          >
            <template #empty>
              <n-empty description="暂无风险告警。风控引擎运行正常时，告警将在触发后显示于此" />
            </template>
          </n-data-table>

          <div class="pagination-container">
            <n-pagination
              v-model:page="currentPage"
              :item-count="alertTotal"
              :page-size="10"
            />
          </div>
        </n-spin>
      </n-card>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.risk-monitor {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
}

.overview-grid {
  margin-bottom: 24px;

  :deep(.n-card) {
    height: 100%;
  }
  :deep(.n-card__content) {
    padding: 12px 16px 8px;
  }
}

.metric-content {
  text-align: center;
  .metric-value {
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 4px;
  }
  .metric-label {
    color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
    font-size: 12px;
  }
}

.status-critical { color: #f56c6c; }
.status-warning { color: #e6a23c; }
.status-normal { color: #67c23a; }

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
