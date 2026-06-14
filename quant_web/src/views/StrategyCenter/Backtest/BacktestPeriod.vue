<template>
  <div class="backtest-period bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">回溯周期</h1>
        </div>
        <div class="header-actions">
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
          <n-button class="action-btn" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
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
      <div class="content-section">
        <n-card class="period-config">
          <template #header>
            <div class="card-header">
              <span>回溯周期配置</span>
              <div class="filter-bar">
                <n-input
                  v-model:value="searchKeyword"
                  placeholder="搜索周期名称"
                  style="width: 180px"
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
              </div>
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
      </div>
    </n-spin>

    <div class="content-section">
      <n-card class="period-analysis">
        <template #header><span>周期性能分析</span></template>

        <n-grid :x-gap="16" :cols="2">
          <n-grid-item>
            <div class="analysis-stats">
              <div class="stats-header">
                <Icon icon="mdi:chart-bar" :width="18" />
                <span>周期收益概览</span>
              </div>
              <div
                ref="performanceChartRef"
                class="chart-container"
                style="height: 264px"
              ></div>
            </div>
          </n-grid-item>
          <n-grid-item>
            <div class="analysis-stats">
              <div class="stats-header">
                <Icon icon="mdi:chart-box-outline" :width="18" />
                <span>统计摘要</span>
              </div>
              <div class="stats-body">
                <div class="stat-row">
                  <span class="stat-label">总周期数</span>
                  <span class="stat-value">{{
                    analysisStats.totalPeriods
                  }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">平均收益率</span>
                  <span
                    class="stat-value"
                    :class="getReturnClass(analysisStats.avgReturn)"
                    >{{ formatPercent(analysisStats.avgReturn) }}</span
                  >
                </div>
                <div class="stat-divider" />
                <div class="stat-row">
                  <span class="stat-label">最优周期</span>
                  <span class="stat-value stat-name">{{
                    analysisStats.bestPeriod
                  }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">最差周期</span>
                  <span class="stat-value stat-name">{{
                    analysisStats.worstPeriod
                  }}</span>
                </div>
                <div class="stat-divider" />
                <div class="stat-row">
                  <span class="stat-label">胜率</span>
                  <span class="stat-value stat-highlight">{{
                    formatPercent(analysisStats.winRate)
                  }}</span>
                </div>
              </div>
            </div>
          </n-grid-item>
        </n-grid>
      </n-card>
    </div>

    <div class="content-section">
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
                <n-space :size="8">
                  <n-button
                    type="primary"
                    @click="runComparison"
                    :loading="comparing"
                  >
                    <template #icon><Icon icon="mdi:chart-bar" /></template>
                    运行对比
                  </n-button>
                  <n-button
                    @click="openInStudio"
                    :disabled="comparisonConfig.selectedPeriods.length === 0"
                  >
                    <template #icon><Icon icon="mdi:flask" /></template>
                    在工作室对比
                  </n-button>
                </n-space>
              </n-form-item>
            </n-grid-item>
          </n-grid>
        </n-form>

        <div v-if="comparisonResults" class="comparison-results">
          <div class="chart-header">
            <span
              >周期对比结果 -
              {{ getMetricLabel(comparisonConfig.metric) }}</span
            >
          </div>
          <div
            ref="comparisonChartRef"
            class="chart-container"
            style="height: 400px"
          ></div>
        </div>
      </n-card>
    </div>

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
import { useRouter } from "vue-router";
import { useMessage, useDialog, NTag, NButton, NResult } from "naive-ui";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import * as echarts from "echarts";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();

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
    winRate: number;
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
      winRate: 0.6,
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
      winRate: 0.5,
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
      winRate: 0.3333,
    },
  },
]);

const analysisStats = computed(() => {
  const list = periods.value;
  if (list.length === 0)
    return {
      totalPeriods: 0,
      avgReturn: 0,
      bestPeriod: "--",
      worstPeriod: "--",
      winRate: 0,
    };
  const returns = list.map((p) => p.performance.annualReturn);
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const best = list.reduce(
    (prev, curr) =>
      curr.performance.annualReturn > prev.performance.annualReturn
        ? curr
        : prev,
    list[0],
  );
  const worst = list.reduce(
    (prev, curr) =>
      curr.performance.annualReturn < prev.performance.annualReturn
        ? curr
        : prev,
    list[0],
  );
  const winCount = list.filter((p) => p.performance.annualReturn > 0).length;
  return {
    totalPeriods: list.length,
    avgReturn,
    bestPeriod: best.name,
    worstPeriod: worst.name,
    winRate: winCount / list.length,
  };
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
const formatDateParam = (date: any) =>
  date ? new Date(date).toISOString().split("T")[0] : "";
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

const handleRunBacktest = (period: Period) => {
  const startStr = formatDateParam(period.startDate);
  const endStr = formatDateParam(period.endDate);
  router.push({
    path: "/backtest/config",
    query: { startDate: startStr, endDate: endStr, period: period.name },
  });
};

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
      if (idx > -1) {
        const { dateRange: _range, ...rest } = periodForm as any;
        periods.value[idx] = {
          ...rest,
          startDate,
          endDate,
          duration,
          lastTest: new Date(),
        } as any;
      }
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
        performance: {
          annualReturn: 0,
          sharpeRatio: 0,
          maxDrawdown: 0,
          winRate: 0,
        },
      });
      message.success("回溯周期创建成功");
    }
    periodDialogVisible.value = false;
    initPerformanceChart();
  } catch {
    message.error("表单验证失败");
  }
};

const exportPeriods = () => {
  if (periods.value.length === 0) {
    message.warning("没有可导出的周期数据");
    return;
  }
  const data = periods.value.map((p) => ({
    name: p.name,
    description: p.description,
    startDate: formatDateParam(p.startDate),
    endDate: formatDateParam(p.endDate),
    duration: p.duration,
    testCount: p.testCount,
    status: p.status,
    annualReturn: p.performance.annualReturn,
    sharpeRatio: p.performance.sharpeRatio,
    maxDrawdown: p.performance.maxDrawdown,
    winRate: p.performance.winRate,
  }));
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `backtest_periods_${new Date().toISOString().split("T")[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
  message.success("导出成功");
};

const openInStudio = () => {
  if (comparisonConfig.selectedPeriods.length === 0) {
    message.warning("请选择要对比的周期");
    return;
  }
  const periodNames = comparisonConfig.selectedPeriods
    .map((id) => periods.value.find((p) => p.id === id))
    .filter(Boolean)
    .map((p) => p!.name)
    .join(",");
  router.push({
    path: "/backtest/studio",
    query: { periods: periodNames },
  });
};

const runComparison = async () => {
  if (comparisonConfig.selectedPeriods.length === 0) {
    message.warning("请选择要对比的周期");
    return;
  }

  comparing.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    const isPercent = ["annualReturn", "maxDrawdown", "winRate"].includes(
      comparisonConfig.metric,
    );
    comparisonResults.value = {
      periods: comparisonConfig.selectedPeriods
        .map((id) => periods.value.find((pp) => pp.id === id))
        .filter((p): p is Period => p != null)
        .map((p) => ({
          name: p.name,
          value: isPercent
            ? Number(
                ((p.performance as any)[comparisonConfig.metric] * 100).toFixed(
                  2,
                ),
              )
            : (p.performance as any)[comparisonConfig.metric],
        })),
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
  if (performanceChartInstance) {
    performanceChartInstance.dispose();
    performanceChartInstance = null;
  }
  performanceChartInstance = echarts.init(performanceChartRef.value);

  // 双 Y 轴对齐：相同刻度数 → 网格线物理位置完全重合
  const returns = periods.value.map((p) =>
    Number((p.performance.annualReturn * 100).toFixed(1)),
  );
  const sharpes = periods.value.map((p) =>
    Number(p.performance.sharpeRatio.toFixed(2)),
  );
  const drawdowns = periods.value.map((p) =>
    Number((p.performance.maxDrawdown * 100).toFixed(1)),
  );

  // 左轴：以 0 为中心对称，取 10 的倍数
  const lAbsMax = Math.max(
    Math.abs(Math.max(...returns)),
    Math.abs(Math.min(...returns)),
  );
  const L_STEP = 10;
  const lHalf = Math.ceil(lAbsMax / L_STEP) * L_STEP + L_STEP; // 上下各留一档
  const lMin = -lHalf;
  const lMax = lHalf;
  const lTicks = (lMax - lMin) / L_STEP; // 区间数

  // 右轴：扩展范围使其区间数与左轴一致，步长取 5 的倍数
  const rightAll = [...sharpes, ...drawdowns];
  const rDataMax = Math.max(...rightAll);
  const rDataMin = Math.min(...rightAll);
  const R_STEP = 5;
  // 向上下扩展到 5 的倍数
  const rMin = Math.floor(rDataMin / R_STEP) * R_STEP - R_STEP;
  const rMax = Math.ceil(rDataMax / R_STEP) * R_STEP + R_STEP;
  const rTicks = (rMax - rMin) / R_STEP;

  // 如果两边区间数不一致，右轴补齐
  const extraTicks = lTicks - rTicks;
  const rMinFinal =
    extraTicks > 0 ? rMin - Math.ceil(extraTicks / 2) * R_STEP : rMin;
  const rMaxFinal =
    extraTicks > 0 ? rMax + Math.floor(extraTicks / 2) * R_STEP : rMax;

  performanceChartInstance.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: {
      data: ["年化收益", "夏普比率", "最大回撤"],
      bottom: 0,
      left: "center",
      itemWidth: 14,
      itemHeight: 14,
      itemGap: 16,
      textStyle: { fontSize: 11, padding: [2, 0] },
    },
    grid: { left: 64, right: 64, top: 24, bottom: 40 },
    xAxis: {
      type: "category",
      data: periods.value.map((p) => p.name),
      axisLabel: { interval: 0, rotate: periods.value.length > 4 ? 30 : 0 },
      axisTick: { alignWithLabel: true },
    },
    yAxis: [
      {
        type: "value",
        name: "收益率(%)",
        nameTextStyle: { fontSize: 11 },
        nameGap: 14,
        min: lMin,
        max: lMax,
        interval: L_STEP,
        splitNumber: lTicks,
        axisLabel: { formatter: "{value}", fontSize: 11 },
        // 零线高亮：通过 splitLine 中 indexOf(0) 对应的线加粗
        splitLine: {
          show: true,
          lineStyle: {
            color: "var(--n-border-color)",
            type: "dashed",
            width: 1,
          },
        },
      },
      {
        type: "value",
        name: "比率/回撤(%)",
        nameTextStyle: { fontSize: 11 },
        nameGap: 14,
        min: rMinFinal,
        max: rMaxFinal,
        interval: R_STEP,
        splitNumber: Math.round((rMaxFinal - rMinFinal) / R_STEP),
        axisLabel: { formatter: "{value}", fontSize: 11 },
        splitLine: { show: false }, // 右轴隐藏网格线，避免与左轴重叠
      },
    ],
    series: [
      {
        name: "年化收益",
        type: "bar",
        data: periods.value.map((p) =>
          Number((p.performance.annualReturn * 100).toFixed(1)),
        ),
        itemStyle: {
          color: (params: any) => (params.value >= 0 ? "#5470c6" : "#ee6666"),
        },
      },
      {
        name: "夏普比率",
        type: "line",
        yAxisIndex: 1,
        data: periods.value.map((p) =>
          Number(p.performance.sharpeRatio.toFixed(2)),
        ),
        itemStyle: { color: "#91cc75" },
      },
      {
        name: "最大回撤",
        type: "line",
        yAxisIndex: 1,
        data: periods.value.map((p) =>
          Number((p.performance.maxDrawdown * 100).toFixed(1)),
        ),
        itemStyle: { color: "#ee6666" },
      },
    ],
  });
};

const initComparisonChart = () => {
  if (!comparisonChartRef.value || !comparisonResults.value) return;
  if (comparisonChartInstance) {
    comparisonChartInstance.dispose();
    comparisonChartInstance = null;
  }
  comparisonChartInstance = echarts.init(comparisonChartRef.value);
  const isPercentMetric = ["annualReturn", "maxDrawdown", "winRate"].includes(
    comparisonConfig.metric,
  );
  const fmtVal = (v: number) =>
    isPercentMetric ? `${v.toFixed(2)}%` : v.toFixed(2);
  comparisonChartInstance.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: any) =>
        `${params[0].name}<br/>${getMetricLabel(comparisonConfig.metric)}: ${fmtVal(params[0].value)}`,
    },
    grid: { left: 56, right: 56, top: 48, bottom: 32 },
    xAxis: {
      type: "category",
      data: comparisonResults.value.periods.map((p) => p.name),
      axisLabel: { interval: 0 },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: "value",
      name: getMetricLabel(comparisonConfig.metric),
      nameTextStyle: { fontSize: 11 },
      nameGap: 12,
      splitNumber: 5,
      axisLabel: {
        formatter: isPercentMetric ? "{value}%" : "{value}",
        fontSize: 11,
      },
    },
    series: [
      {
        name: getMetricLabel(comparisonConfig.metric),
        type: "bar",
        data: comparisonResults.value.periods.map((p) => ({
          value: p.value,
          label: { position: p.value >= 0 ? "top" : "bottom" },
        })),
        itemStyle: {
          color: (params: any) =>
            comparisonConfig.metric === "maxDrawdown"
              ? params.data.value >= 0
                ? "#ee6666"
                : "#5470c6"
              : params.data.value >= 0
                ? "#5470c6"
                : "#ee6666",
        },
        label: {
          show: true,
          position: "top",
          formatter: (params: any) => fmtVal(params.data.value),
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
    await nextTick();
    initPerformanceChart();
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
  padding: 0 24px;
  height: 100%;
  overflow-y: auto;
}

/* .page-header 已迁移至全局样式（global.scss） */

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
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
  padding: 16px 20px;
}

.stats-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--n-border-color);
}

.stats-body {
  display: flex;
  flex-direction: column;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
}

.stat-label {
  font-size: 13px;
  color: var(--n-text-color-3);
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
  font-variant-numeric: tabular-nums;
}

.stat-value.stat-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--n-text-color-2);
}

.stat-value.stat-highlight {
  font-size: 18px;
  color: var(--n-primary-color);
}

.stat-divider {
  height: 1px;
  background: var(--n-border-color);
  margin: 0;
}

.analysis-stats .positive {
  color: #67c23a;
}

.analysis-stats .negative {
  color: #f56c6c;
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
