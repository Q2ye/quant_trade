<template>
  <div class="factor-research bg-gradient-mesh bg-noise">
    <div class="page-header">
      <h1 class="page-title">
        <Icon icon="mdi:flask" />
        因子研究
      </h1>
      <n-space :size="8">
        <n-button type="primary" @click="runQuickTest" :loading="testing">
          <template #icon><Icon icon="mdi:play" /></template>
          快速测试
        </n-button>
        <n-button
          @click="compareFactors"
          :disabled="selectedFactors.length < 2"
        >
          <template #icon><Icon icon="mdi:compare" /></template>
          因子对比
        </n-button>
        <n-button @click="gotoFactorLibrary">
          <template #icon><Icon icon="mdi:cog" /></template>
          管理因子库
        </n-button>
      </n-space>
    </div>

    <n-spin :show="loading">
      <n-result
        v-if="pageError"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadFactorData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-card class="quick-test-panel">
          <template #header>
            <div class="card-header">
              <span>快速因子测试</span>
              <n-button text @click="showAdvanced = !showAdvanced">
                {{ showAdvanced ? "简化配置" : "高级配置" }}
              </n-button>
            </div>
          </template>

          <n-grid :x-gap="20" :cols="3">
            <n-grid-item>
              <div class="factor-selection">
                <div class="section-title">
                  <Icon icon="mdi:check-circle" />
                  选择测试因子
                </div>

                <n-tabs v-model:value="activeCategory" class="factor-tabs">
                  <n-tab-pane name="value" tab="价值因子">
                    <FactorSelector
                      :factors="valueFactors"
                      v-model="selectedFactors"
                      category="value"
                    />
                  </n-tab-pane>
                  <n-tab-pane name="growth" tab="成长因子">
                    <FactorSelector
                      :factors="growthFactors"
                      v-model="selectedFactors"
                      category="growth"
                    />
                  </n-tab-pane>
                  <n-tab-pane name="quality" tab="质量因子">
                    <FactorSelector
                      :factors="qualityFactors"
                      v-model="selectedFactors"
                      category="quality"
                    />
                  </n-tab-pane>
                </n-tabs>

                <div class="selected-count">
                  已选择 {{ selectedFactors.length }} 个因子
                </div>
              </div>
            </n-grid-item>

            <n-grid-item>
              <div class="test-config">
                <div class="section-title">
                  <Icon icon="mdi:settings" />
                  测试配置
                </div>

                <n-form :model="quickConfig" label-width="80px" size="small">
                  <n-form-item label="测试周期">
                    <n-date-picker
                      v-model:value="quickConfig.dateRange"
                      type="daterange"
                      start-placeholder="开始日期"
                      end-placeholder="结束日期"
                      style="width: 100%"
                    />
                  </n-form-item>

                  <n-form-item label="股票池">
                    <n-select
                      v-model:value="quickConfig.universe"
                      style="width: 100%"
                      :options="universeOptions"
                    />
                  </n-form-item>

                  <n-form-item label="初始资金">
                    <n-input-number
                      v-model:value="quickConfig.initialCapital"
                      :min="100000"
                      :step="100000"
                      style="width: 100%"
                    >
                      <template #suffix>元</template>
                    </n-input-number>
                  </n-form-item>

                  <div v-if="showAdvanced" class="advanced-config">
                    <n-form-item label="调仓频率">
                      <n-select
                        v-model:value="quickConfig.rebalanceFreq"
                        style="width: 100%"
                        :options="rebalanceOptions"
                      />
                    </n-form-item>

                    <n-form-item label="分组数量">
                      <n-slider
                        v-model:value="quickConfig.groupCount"
                        :min="3"
                        :max="10"
                        :step="1"
                        :marks="groupMarks"
                      />
                    </n-form-item>
                  </div>
                </n-form>
              </div>
            </n-grid-item>

            <n-grid-item>
              <div class="quick-results">
                <div class="section-title">
                  <Icon icon="mdi:chart-line" />
                  快速结果
                </div>

                <n-result
                  v-if="error"
                  status="500"
                  title="测试失败"
                  description="因子测试失败，请稍后重试"
                  size="small"
                >
                  <template #footer
                    ><n-button size="small" @click="runQuickTest"
                      >重试</n-button
                    ></template
                  >
                </n-result>

                <div v-else-if="quickResults" class="results-preview">
                  <div class="result-metrics">
                    <div class="metric-item">
                      <div class="metric-value positive">
                        {{ formatPercent(quickResults.annualReturn) }}
                      </div>
                      <div class="metric-label">年化收益</div>
                    </div>
                    <div class="metric-item">
                      <div class="metric-value">
                        {{ quickResults.sharpeRatio.toFixed(2) }}
                      </div>
                      <div class="metric-label">夏普比率</div>
                    </div>
                    <div class="metric-item">
                      <div class="metric-value negative">
                        {{ formatPercent(quickResults.maxDrawdown) }}
                      </div>
                      <div class="metric-label">最大回撤</div>
                    </div>
                  </div>

                  <n-button
                    text
                    type="primary"
                    @click="showDetailAnalysis"
                    style="width: 100%; margin-top: 10px"
                  >
                    查看详细分析
                  </n-button>
                </div>

                <n-empty v-else description="暂无测试结果" size="small">
                  <template #extra
                    ><p style="color: var(--n-text-color-3)">
                      选择因子并点击"快速测试"查看结果
                    </p></template
                  >
                </n-empty>
              </div>
            </n-grid-item>
          </n-grid>
        </n-card>

        <n-card v-if="comparisonResults" class="comparison-panel">
          <template #header><span>因子对比分析</span></template>

          <n-tabs v-model:value="comparisonTab">
            <n-tab-pane name="returns" tab="收益对比">
              <div
                ref="returnsComparisonChartRef"
                class="chart-container"
                style="height: 300px"
              ></div>
            </n-tab-pane>
            <n-tab-pane name="risk" tab="风险指标">
              <n-data-table
                :columns="comparisonColumns"
                :data="comparisonResults.riskMetrics"
                :bordered="false"
                size="small"
              />
            </n-tab-pane>
          </n-tabs>
        </n-card>

        <n-modal
          v-model:show="detailDialogVisible"
          preset="dialog"
          title="因子详细分析"
          style="width: 90%"
          :fullscreen="true"
        >
          <FactorDetailAnalysis
            :factor="selectedFactor"
            :test-config="quickConfig"
            :test-results="quickResults"
          />
        </n-modal>
      </template>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, h, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useMessage, NTag, NResult, NSpin } from "naive-ui";
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";
import FactorSelector from "@/components/research/FactorSelector.vue";
import FactorDetailAnalysis from "@/components/research/FactorDetailAnalysis.vue";

const message = useMessage();
const router = useRouter();

const loading = ref(false);
const pageError = ref(false);
const testing = ref(false);
const error = ref(false);
const showAdvanced = ref(false);
const activeCategory = ref("value");
const selectedFactors = ref<any[]>([]);
const selectedFactor = ref<any>(null);
const quickResults = ref<any>(null);
const comparisonResults = ref<any>(null);
const comparisonTab = ref("returns");
const detailDialogVisible = ref(false);
const returnsComparisonChartRef = ref<HTMLElement | null>(null);

const quickConfig = reactive({
  dateRange: [new Date(Date.now() - 365 * 24 * 60 * 60 * 1000), new Date()],
  universe: "all",
  initialCapital: 1000000,
  rebalanceFreq: "monthly",
  groupCount: 5,
});

const universeOptions = [
  { label: "全A股", value: "all" },
  { label: "沪深300", value: "hs300" },
  { label: "中证500", value: "zz500" },
];
const rebalanceOptions = [
  { label: "每日", value: "daily" },
  { label: "每周", value: "weekly" },
  { label: "每月", value: "monthly" },
];
const groupMarks = { 3: "3", 5: "5", 7: "7", 10: "10" };

const valueFactors = ref([
  {
    id: "pe_ratio",
    name: "市盈率(PE)",
    description: "市值与净利润比率",
    category: "value",
  },
  {
    id: "pb_ratio",
    name: "市净率(PB)",
    description: "市值与净资产比率",
    category: "value",
  },
  {
    id: "dividend_yield",
    name: "股息率",
    description: "年度股息与股价比率",
    category: "value",
  },
  {
    id: "ev_ebitda",
    name: "EV/EBITDA",
    description: "企业价值与税息折旧摊销前利润比率",
    category: "value",
  },
]);

const growthFactors = ref([
  {
    id: "revenue_growth",
    name: "营收增长率",
    description: "营业收入同比增长率",
    category: "growth",
  },
  {
    id: "profit_growth",
    name: "利润增长率",
    description: "净利润同比增长率",
    category: "growth",
  },
  {
    id: "roe_growth",
    name: "ROE增长率",
    description: "净资产收益率变化率",
    category: "growth",
  },
]);

const qualityFactors = ref([
  {
    id: "roe",
    name: "净资产收益率(ROE)",
    description: "净利润与净资产比率",
    category: "quality",
  },
  {
    id: "roa",
    name: "总资产收益率(ROA)",
    description: "净利润与总资产比率",
    category: "quality",
  },
  {
    id: "profit_margin",
    name: "净利润率",
    description: "净利润与营业收入比率",
    category: "quality",
  },
]);

const comparisonColumns = [
  { title: "因子名称", key: "factorName" },
  {
    title: "年化收益",
    key: "annualReturn",
    render: (row: any) =>
      h(
        "span",
        { class: row.annualReturn >= 0 ? "positive" : "negative" },
        formatPercent(row.annualReturn),
      ),
  },
  { title: "夏普比率", key: "sharpeRatio" },
  {
    title: "最大回撤",
    key: "maxDrawdown",
    render: (row: any) =>
      h("span", { class: "negative" }, formatPercent(row.maxDrawdown)),
  },
  {
    title: "胜率",
    key: "winRate",
    render: (row: any) => formatPercent(row.winRate),
  },
];

const formatPercent = (v: number) => `${(v * 100).toFixed(2)}%`;

const loadFactorData = async () => {
  loading.value = true;
  pageError.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
  } catch {
    pageError.value = true;
  } finally {
    loading.value = false;
  }
};

const runQuickTest = async () => {
  if (selectedFactors.value.length === 0) {
    message.warning("请选择至少一个因子进行测试");
    return;
  }
  testing.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    quickResults.value = {
      annualReturn: 0.156,
      sharpeRatio: 1.24,
      maxDrawdown: -0.153,
      winRate: 0.625,
      groupReturns: [0.156, 0.123, 0.089, 0.045, -0.012],
      icSeries: [0.045, 0.056, 0.032, -0.012, 0.067, 0.023, 0.078, 0.034],
    };
    error.value = false;
    message.success("因子测试完成");
  } catch (e: any) {
    error.value = true;
  } finally {
    testing.value = false;
  }
};

const compareFactors = async () => {
  if (selectedFactors.value.length < 2) {
    message.warning("请选择至少两个因子进行对比");
    return;
  }
  testing.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    comparisonResults.value = {
      riskMetrics: selectedFactors.value.map((f) => ({
        factorName: f.name,
        annualReturn: Math.random() * 0.3 - 0.05,
        sharpeRatio: Math.random() * 2,
        maxDrawdown: Math.random() * -0.2 - 0.1,
        winRate: Math.random() * 0.3 + 0.5,
      })),
    };
    initComparisonChart();
  } catch (e: any) {
    message.error("对比分析失败: " + e.message);
  } finally {
    testing.value = false;
  }
};

const showDetailAnalysis = () => {
  if (selectedFactors.value.length > 0) {
    selectedFactor.value = selectedFactors.value[0];
    detailDialogVisible.value = true;
  }
};

const gotoFactorLibrary = () => router.push("/strategies/factor-library");

let comparisonChartInstance: echarts.ECharts | null = null;

const initComparisonChart = () => {
  if (!comparisonResults.value || !returnsComparisonChartRef.value) return;
  comparisonChartInstance = echarts.init(returnsComparisonChartRef.value);
  const colors = [
    "#5470c6",
    "#91cc75",
    "#fac858",
    "#ee6666",
    "#73c0de",
    "#3ba272",
    "#fc8452",
  ];
  comparisonChartInstance.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: selectedFactors.value.map((f) => f.name) },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: {
      type: "category",
      data: ["1月", "2月", "3月", "4月", "5月", "6月", "7月"],
    },
    yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    series: selectedFactors.value.map((f, i) => ({
      name: f.name,
      type: "line",
      data: Array(7)
        .fill(0)
        .map(() => Math.random() * 20 + 5),
      itemStyle: { color: colors[i % colors.length] },
    })),
  });
};

onUnmounted(() => {
  comparisonChartInstance?.dispose();
});
onMounted(() => loadFactorData());
</script>

<style lang="scss" scoped>
.factor-research {
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
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.quick-test-panel {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: var(--n-text-color-1);
}

.factor-selection {
  .factor-tabs {
    height: 300px;
  }
  .selected-count {
    margin-top: 10px;
    padding: 8px;
    background: var(--n-color-embedded);
    border-radius: 4px;
    text-align: center;
    color: var(--n-text-color-2);
  }
}

.test-config {
  .advanced-config {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid var(--n-border-color);
  }
}

.quick-results {
  .results-preview {
    .result-metrics {
      display: flex;
      justify-content: space-around;
      text-align: center;
      .metric-item {
        .metric-value {
          font-size: 18px;
          font-weight: bold;
          margin-bottom: 4px;
        }
        .metric-label {
          font-size: 12px;
          color: var(--n-text-color-3);
        }
      }
    }
  }
}

.comparison-panel {
  margin-top: 20px;
}
.chart-container {
  width: 100%;
}
.positive {
  color: #67c23a;
}
.negative {
  color: #f56c6c;
}
</style>
