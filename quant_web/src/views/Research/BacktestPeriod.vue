<template>
  <div class="backtest-period bg-gradient-mesh bg-noise">
    <div class="page-header">
      <h1 class="page-title">回溯周期</h1>
      <n-space :size="8">
        <n-button type="primary" @click="handleCreatePeriod">
          <template #icon><Icon icon="mdi:plus" /></template>
          新建周期
        </n-button>
        <n-button @click="exportPeriods">
          <template #icon><Icon icon="mdi:download" /></template>
          导出配置
        </n-button>
      </n-space>
    </div>

    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取回溯周期数据失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="loadPeriods">重试</n-button></template
      >
    </n-result>

    <n-spin v-else :show="loading">
      <n-card class="period-config">
        <template #header>
          <div class="card-header">
            <span>回溯周期配置</span>
            <n-space :size="8">
              <n-input
                v-model:value="searchKeyword"
                placeholder="搜索周期名称"
                style="width: 200px"
                clearable
              >
                <template #prefix>
                  <n-icon><Icon icon="mdi:magnify" /></n-icon>
                </template>
              </n-input>
              <n-select
                v-model:value="filterStatus"
                placeholder="状态"
                style="width: 100px"
                clearable
                :options="statusOptions"
              />
            </n-space>
          </div>
        </template>

        <n-empty
          v-if="filteredPeriods.length === 0"
          description="暂无回溯周期数据"
        />

        <template v-else>
          <n-data-table
            :columns="periodColumns"
            :data="filteredPeriods"
            :bordered="false"
            size="small"
          />

          <div class="pagination-container">
            <n-pagination
              v-model:page="pagination.currentPage"
              v-model:page-size="pagination.pageSize"
              :item-count="pagination.total"
            />
          </div>
        </template>
      </n-card>
    </n-spin>

    <n-card class="period-analysis">
      <template #header><span>周期性能分析</span></template>

      <n-grid :x-gap="16" :cols="2">
        <n-grid-item>
          <div
            ref="performanceChartRef"
            class="chart-container"
            style="height: 300px"
          ></div>
        </n-grid-item>
        <n-grid-item>
          <div class="analysis-stats">
            <n-descriptions title="统计摘要" :column="1" bordered>
              <n-descriptions-item label="总周期数">{{
                analysisStats.totalPeriods
              }}</n-descriptions-item>
              <n-descriptions-item label="平均收益率">
                <span :class="getReturnClass(analysisStats.avgReturn)">{{
                  formatPercent(analysisStats.avgReturn)
                }}</span>
              </n-descriptions-item>
              <n-descriptions-item label="最优周期">{{
                analysisStats.bestPeriod
              }}</n-descriptions-item>
              <n-descriptions-item label="最差周期">{{
                analysisStats.worstPeriod
              }}</n-descriptions-item>
              <n-descriptions-item label="胜率">{{
                formatPercent(analysisStats.winRate)
              }}</n-descriptions-item>
            </n-descriptions>
          </div>
        </n-grid-item>
      </n-grid>
    </n-card>

    <n-card class="period-comparison">
      <template #header><span>周期对比分析</span></template>

      <n-form :model="comparisonConfig" label-width="100px">
        <n-grid :x-gap="20" :cols="3">
          <n-grid-item>
            <n-form-item label="对比周期">
              <n-select
                v-model:value="comparisonConfig.selectedPeriods"
                multiple
                placeholder="请选择对比周期"
                :options="periodOptions"
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="对比指标">
              <n-select
                v-model:value="comparisonConfig.metric"
                placeholder="请选择对比指标"
                :options="metricOptions"
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item>
              <n-button
                type="primary"
                @click="runComparison"
                :loading="comparing"
              >
                <template #icon><Icon icon="mdi:chart-bar" /></template>
                运行对比
              </n-button>
            </n-form-item>
          </n-grid-item>
        </n-grid>
      </n-form>

      <div v-if="comparisonResults" class="comparison-results">
        <div class="chart-header">
          <span
            >周期对比结果 - {{ getMetricLabel(comparisonConfig.metric) }}</span
          >
        </div>
        <div
          ref="comparisonChartRef"
          class="chart-container"
          style="height: 400px"
        ></div>
      </div>
    </n-card>

    <n-modal
      v-model:show="periodDialogVisible"
      preset="dialog"
      :title="isEditMode ? '编辑回溯周期' : '新建回溯周期'"
      positive-text="保存"
      negative-text="取消"
      @positive-click="handleSavePeriod"
    >
      <n-form
        ref="periodFormRef"
        :model="periodForm"
        :rules="periodRules"
        label-width="100px"
      >
        <n-form-item label="周期名称" path="name">
          <n-input
            v-model:value="periodForm.name"
            placeholder="请输入周期名称"
          />
        </n-form-item>
        <n-form-item label="周期描述" path="description">
          <n-input
            v-model:value="periodForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入周期描述"
          />
        </n-form-item>
        <n-form-item label="时间范围" path="dateRange">
          <n-date-picker
            v-model:value="periodForm.dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="状态">
          <n-switch
            v-model:value="periodForm.status"
            :checked-value="'active'"
            :unchecked-value="'inactive'"
          />
          <span style="margin-left: 10px; color: var(--n-text-color-3)">{{
            periodForm.status === "active" ? "启用" : "停用"
          }}</span>
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  reactive,
  computed,
  onMounted,
  nextTick,
  onUnmounted,
  h,
} from "vue";
import { useMessage, useDialog, NTag, NButton, NResult } from "naive-ui";
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";

const message = useMessage();
const dialog = useDialog();

const loading = ref(false);
const error = ref(false);
const comparing = ref(false);
const periodDialogVisible = ref(false);
const isEditMode = ref(false);
const searchKeyword = ref("");
const filterStatus = ref("");
const performanceChartRef = ref<HTMLElement | null>(null);
const comparisonChartRef = ref<HTMLElement | null>(null);
const periodFormRef = ref<any>(null);

const statusOptions = [
  { label: "全部", value: "" },
  { label: "启用", value: "active" },
  { label: "停用", value: "inactive" },
];

const metricOptions = [
  { label: "年化收益率", value: "annualReturn" },
  { label: "夏普比率", value: "sharpeRatio" },
  { label: "最大回撤", value: "maxDrawdown" },
  { label: "胜率", value: "winRate" },
];

const periodOptions = computed(() =>
  periods.value.map((p) => ({ label: p.name, value: p.id })),
);

const pagination = reactive({ currentPage: 1, pageSize: 10, total: 0 });

const comparisonConfig = reactive({
  selectedPeriods: [] as string[],
  metric: "annualReturn",
});

const periodForm = reactive({
  id: "",
  name: "",
  description: "",
  dateRange: [] as any[],
  status: "active",
});

const periodRules = {
  name: [{ required: true, message: "请输入周期名称", trigger: "blur" }],
  description: [{ required: true, message: "请输入周期描述", trigger: "blur" }],
  dateRange: [{ required: true, message: "请选择时间范围", trigger: "change" }],
};

const periodColumns = [
  {
    title: "序号",
    key: "index",
    width: 60,
    render: (_: any, __: number) =>
      __ + 1 + (pagination.currentPage - 1) * pagination.pageSize,
  },
  { title: "周期名称", key: "name", width: 150 },
  {
    title: "周期描述",
    key: "description",
    minWidth: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: "开始日期",
    key: "startDate",
    width: 120,
    render: (row: any) => formatDate(row.startDate),
  },
  {
    title: "结束日期",
    key: "endDate",
    width: 120,
    render: (row: any) => formatDate(row.endDate),
  },
  {
    title: "周期长度",
    key: "duration",
    width: 100,
    render: (row: any) => `${row.duration}天`,
  },
  { title: "测试次数", key: "testCount", width: 100 },
  {
    title: "状态",
    key: "status",
    width: 80,
    render: (row: any) =>
      h(
        NTag,
        {
          type: row.status === "active" ? "success" : "default",
          size: "small",
        },
        { default: () => (row.status === "active" ? "启用" : "停用") },
      ),
  },
  {
    title: "最后测试",
    key: "lastTest",
    width: 120,
    render: (row: any) => (row.lastTest ? formatDate(row.lastTest) : "--"),
  },
  {
    title: "操作",
    key: "op",
    width: 200,
    render: (row: any) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(
          NButton,
          { size: "small", onClick: () => handleEditPeriod(row) },
          { default: () => "编辑" },
        ),
        h(
          NButton,
          { size: "small", onClick: () => handleRunBacktest(row) },
          { default: () => "回测" },
        ),
        h(
          NButton,
          {
            size: "small",
            type: "error",
            onClick: () => handleDeletePeriod(row),
          },
          { default: () => "删除" },
        ),
      ]),
  },
];

interface Period {
  id: string;
  name: string;
  description: string;
  startDate: Date;
  endDate: Date;
  duration: number;
  testCount: number;
  status: string;
  lastTest: Date | null;
  performance: {
    annualReturn: number;
    sharpeRatio: number;
    maxDrawdown: number;
  };
}

const periods = ref<Period[]>([
  {
    id: "1",
    name: "2023年全年",
    description: "2023年完整年度回测周期",
    startDate: new Date("2023-01-01"),
    endDate: new Date("2023-12-31"),
    duration: 365,
    testCount: 15,
    status: "active",
    lastTest: new Date("2024-01-10"),
    performance: {
      annualReturn: 0.2345,
      sharpeRatio: 1.23,
      maxDrawdown: -0.0876,
    },
  },
  {
    id: "2",
    name: "2023下半年",
    description: "2023年下半年回测周期",
    startDate: new Date("2023-07-01"),
    endDate: new Date("2023-12-31"),
    duration: 184,
    testCount: 8,
    status: "active",
    lastTest: new Date("2024-01-08"),
    performance: {
      annualReturn: 0.1567,
      sharpeRatio: 0.89,
      maxDrawdown: -0.0654,
    },
  },
  {
    id: "3",
    name: "2022熊市",
    description: "2022年熊市环境测试",
    startDate: new Date("2022-01-01"),
    endDate: new Date("2022-12-31"),
    duration: 365,
    testCount: 12,
    status: "inactive",
    lastTest: new Date("2023-12-20"),
    performance: {
      annualReturn: -0.1234,
      sharpeRatio: -0.45,
      maxDrawdown: -0.2345,
    },
  },
]);

const analysisStats = reactive({
  totalPeriods: 3,
  avgReturn: 0.0893,
  bestPeriod: "2023年全年",
  worstPeriod: "2022熊市",
  winRate: 0.6667,
});

const comparisonResults = ref<{
  periods: { name: string; value: number }[];
} | null>(null);

const filteredPeriods = computed(() => {
  let result = periods.value;
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase();
    result = result.filter(
      (p) =>
        p.name.toLowerCase().includes(keyword) ||
        p.description.toLowerCase().includes(keyword),
    );
  }
  if (filterStatus.value)
    result = result.filter((p) => p.status === filterStatus.value);
  pagination.total = result.length;
  return result.slice(
    (pagination.currentPage - 1) * pagination.pageSize,
    pagination.currentPage * pagination.pageSize,
  );
});

const getReturnClass = (v: number) => (v >= 0 ? "positive" : "negative");
const formatDate = (date: any) =>
  date ? new Date(date).toLocaleDateString("zh-CN") : "--";
const formatPercent = (v: number | null | undefined) =>
  v != null ? `${(v * 100).toFixed(2)}%` : "--";
const getMetricLabel = (m: string) =>
  (
    ({
      annualReturn: "年化收益率",
      sharpeRatio: "夏普比率",
      maxDrawdown: "最大回撤",
      winRate: "胜率",
    }) as Record<string, string>
  )[m] || m;

const handleCreatePeriod = () => {
  isEditMode.value = false;
  Object.assign(periodForm, {
    id: "",
    name: "",
    description: "",
    dateRange: [],
    status: "active",
  });
  periodDialogVisible.value = true;
};

const handleEditPeriod = (period: Period) => {
  isEditMode.value = true;
  Object.assign(periodForm, {
    ...period,
    dateRange: [period.startDate, period.endDate],
  });
  periodDialogVisible.value = true;
};

const handleRunBacktest = (period: Period) =>
  message.info(`开始对周期 "${period.name}" 进行回测...`);

const handleDeletePeriod = (period: Period) => {
  dialog.warning({
    title: "删除确认",
    content: `确定要删除回溯周期 "${period.name}" 吗？`,
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: () => {
      const idx = periods.value.findIndex((p) => p.id === period.id);
      if (idx > -1) {
        periods.value.splice(idx, 1);
        message.success("回溯周期删除成功");
        initPerformanceChart();
      }
    },
  });
};

const handleSavePeriod = async () => {
  if (!periodFormRef.value) return;
  try {
    await periodFormRef.value.validate();
    const [startDate, endDate] = periodForm.dateRange;
    const duration = Math.ceil(
      (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24),
    );
    if (isEditMode.value) {
      const idx = periods.value.findIndex((p) => p.id === periodForm.id);
      if (idx > -1)
        periods.value[idx] = {
          ...periodForm,
          startDate,
          endDate,
          duration,
          lastTest: new Date(),
        } as any;
      message.success("回溯周期更新成功");
    } else {
      periods.value.push({
        ...periodForm,
        id: Date.now().toString(),
        startDate,
        endDate,
        duration,
        testCount: 0,
        lastTest: null,
        performance: { annualReturn: 0, sharpeRatio: 0, maxDrawdown: 0 },
      });
      message.success("回溯周期创建成功");
    }
    periodDialogVisible.value = false;
    initPerformanceChart();
  } catch {
    message.error("表单验证失败");
  }
};

const exportPeriods = () => message.info("导出功能开发中");

const runComparison = async () => {
  if (comparisonConfig.selectedPeriods.length === 0) {
    message.warning("请选择要对比的周期");
    return;
  }
  comparing.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    comparisonResults.value = {
      periods: comparisonConfig.selectedPeriods.map((id) => {
        const p = periods.value.find((pp) => pp.id === id)!;
        return {
          name: p.name,
          value: (p.performance as any)[comparisonConfig.metric],
        };
      }),
    };
    message.success("对比分析完成");
    nextTick(() => initComparisonChart());
  } catch {
    message.error("对比分析失败");
  } finally {
    comparing.value = false;
  }
};

let performanceChartInstance: echarts.ECharts | null = null;
let comparisonChartInstance: echarts.ECharts | null = null;

const initPerformanceChart = () => {
  if (!performanceChartRef.value) return;
  performanceChartInstance = echarts.init(performanceChartRef.value);
  performanceChartInstance.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { data: ["年化收益", "夏普比率", "最大回撤"] },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: { type: "category", data: periods.value.map((p) => p.name) },
    yAxis: [
      { type: "value", name: "收益率", axisLabel: { formatter: "{value}%" } },
      { type: "value", name: "比率/回撤" },
    ],
    series: [
      {
        name: "年化收益",
        type: "bar",
        data: periods.value.map((p) =>
          (p.performance.annualReturn * 100).toFixed(1),
        ),
        itemStyle: {
          color: (params: any) => (params.data >= 0 ? "#5470c6" : "#ee6666"),
        },
      },
      {
        name: "夏普比率",
        type: "line",
        yAxisIndex: 1,
        data: periods.value.map((p) => p.performance.sharpeRatio.toFixed(2)),
        itemStyle: { color: "#91cc75" },
      },
      {
        name: "最大回撤",
        type: "line",
        yAxisIndex: 1,
        data: periods.value.map((p) =>
          (p.performance.maxDrawdown * 100).toFixed(1),
        ),
        itemStyle: { color: "#ee6666" },
      },
    ],
  });
};

const initComparisonChart = () => {
  if (!comparisonChartRef.value || !comparisonResults.value) return;
  comparisonChartInstance = echarts.init(comparisonChartRef.value);
  const fmtVal = (v: number, m: string) =>
    ["annualReturn", "maxDrawdown", "winRate"].includes(m)
      ? `${(v * 100).toFixed(2)}%`
      : v.toFixed(2);
  comparisonChartInstance.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: any) =>
        `${params[0].name}<br/>${getMetricLabel(comparisonConfig.metric)}: ${fmtVal(params[0].value, comparisonConfig.metric)}`,
    },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: {
      type: "category",
      data: comparisonResults.value.periods.map((p) => p.name),
    },
    yAxis: { type: "value", name: getMetricLabel(comparisonConfig.metric) },
    series: [
      {
        name: getMetricLabel(comparisonConfig.metric),
        type: "bar",
        data: comparisonResults.value.periods.map((p) => p.value),
        itemStyle: {
          color: (params: any) =>
            comparisonConfig.metric === "maxDrawdown"
              ? params.data >= 0
                ? "#ee6666"
                : "#5470c6"
              : params.data >= 0
                ? "#5470c6"
                : "#ee6666",
        },
        label: {
          show: true,
          position: "top",
          formatter: (params: any) =>
            fmtVal(params.data, comparisonConfig.metric),
        },
      },
    ],
  });
};

const handleResize = () => {
  performanceChartInstance?.resize();
  comparisonChartInstance?.resize();
};

const loadPeriods = async () => {
  loading.value = true;
  error.value = false;
  try {
    pagination.total = periods.value.length;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  window.addEventListener("resize", handleResize);
  initPerformanceChart();
  pagination.total = periods.value.length;
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  performanceChartInstance?.dispose();
  comparisonChartInstance?.dispose();
});
</script>

<style lang="scss" scoped>
.backtest-period {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  .page-title {
    margin: 0;
    color: var(--n-text-color-1);
  }
}

.period-config,
.period-analysis,
.period-comparison {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.chart-container {
  width: 100%;
}
.analysis-stats {
  padding: 20px;
}
.comparison-results {
  margin-top: 20px;
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: var(--n-text-color-1);
}

.positive {
  color: #67c23a;
  font-weight: bold;
}
.negative {
  color: #f56c6c;
  font-weight: bold;
}
</style>
