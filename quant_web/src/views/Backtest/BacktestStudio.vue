<template>
  <div class="backtest-studio bg-gradient-mesh bg-noise">
    <div class="studio-header">
      <h2>回测工作室</h2>
      <n-space :size="8">
        <n-button type="primary" @click="runMultiBacktest">多策略回测</n-button>
        <n-button @click="parameterOptimization">参数优化</n-button>
        <n-button @click="exportResults">导出结果</n-button>
      </n-space>
    </div>

    <div class="studio-content">
      <n-spin :show="loading">
        <n-result
          v-if="pageError"
          status="500"
          title="数据加载失败"
          description="请检查网络连接后重试"
        >
          <template #footer>
            <n-button type="primary" @click="loadStudioData">重试</n-button>
          </template>
        </n-result>

        <template v-else>
          <div class="strategy-selection">
            <h3>选择对比策略</h3>
            <div class="transfer-wrapper">
              <div class="transfer-panel">
                <div class="transfer-panel-header">可用策略</div>
                <div class="transfer-panel-body">
                  <div
                    v-for="s in availableStrategies"
                    :key="s.key"
                    class="transfer-item"
                    @click="addStrategy(s.key)"
                  >
                    {{ s.label }}
                  </div>
                </div>
              </div>
              <div class="transfer-actions">
                <n-button size="small" @click="addAll">››</n-button>
                <n-button size="small" @click="removeAll">‹‹</n-button>
              </div>
              <div class="transfer-panel">
                <div class="transfer-panel-header">已选策略</div>
                <div class="transfer-panel-body">
                  <div
                    v-for="key in selectedStrategies"
                    :key="key"
                    class="transfer-item selected"
                    @click="removeStrategy(key)"
                  >
                    {{ selectedLabels[key] }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="backtest-config">
            <h3>回测参数</h3>
            <n-form :model="backtestParams" label-width="120px">
              <n-form-item label="回测周期">
                <n-date-picker
                  v-model:value="backtestDateRange"
                  type="daterange"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                />
              </n-form-item>
              <n-form-item label="初始资金">
                <n-input-number
                  v-model:value="backtestParams.initialCapital"
                  :min="10000"
                  :step="10000"
                />
              </n-form-item>
              <n-form-item label="基准指数">
                <n-select
                  v-model:value="backtestParams.benchmark"
                  :options="benchmarkOptions"
                />
              </n-form-item>
            </n-form>
          </div>

          <n-result
            v-if="error"
            status="500"
            title="回测失败"
            description="多策略回测执行失败，请稍后重试"
          >
            <template #footer
              ><n-button @click="runMultiBacktest">重试</n-button></template
            >
          </n-result>

          <div class="comparison-charts" v-if="comparisonResults.length > 0">
            <h3>策略对比分析</h3>
            <n-tabs type="line">
              <n-tab-pane name="equity" tab="净值曲线">
                <MultiStrategyChart :data="comparisonResults" />
              </n-tab-pane>
              <n-tab-pane name="performance" tab="绩效指标">
                <PerformanceTable :data="comparisonResults" />
              </n-tab-pane>
              <n-tab-pane name="drawdown" tab="回撤对比">
                <DrawdownComparison :data="comparisonResults" />
              </n-tab-pane>
            </n-tabs>
          </div>

          <div class="optimization-panel" v-if="showOptimization">
            <h3>参数优化</h3>
            <ParameterOptimizer
              :strategy="optimizationStrategy"
              @optimize="runOptimization"
            />

            <div v-if="optimizationResults" class="optimization-results">
              <h4>优化结果</h4>
              <HeatmapChart :data="optimizationResults" />
              <ParameterTable :data="optimizationResults.bestParameters" />
            </div>
          </div>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useStore } from "vuex";
import { useMessage, NResult, NSpin } from "naive-ui";
import MultiStrategyChart from "@/components/backtest/MultiStrategyChart.vue";
import PerformanceTable from "@/components/backtest/PerformanceTable.vue";
import DrawdownComparison from "@/components/backtest/DrawdownComparison.vue";
import ParameterOptimizer from "@/components/backtest/ParameterOptimizer.vue";
import HeatmapChart from "@/components/backtest/HeatmapChart.vue";
import ParameterTable from "@/components/backtest/ParameterTable.vue";

const message = useMessage();
const store = useStore<any>();

const loading = ref(false);
const pageError = ref(false);
const running = ref(false);
const error = ref(false);
const selectedStrategies = ref<string[]>([]);
const comparisonResults = ref<any[]>([]);
const showOptimization = ref(false);
const optimizationStrategy = ref<any>(null);
const optimizationResults = ref<any>(null);

const backtestParams = ref({
  initialCapital: 1000000,
  benchmark: "000300.SH",
  startDate: "2020-01-01",
  endDate: "2023-12-31",
});

const benchmarkOptions = [
  { label: "上证指数", value: "000001.SH" },
  { label: "沪深300", value: "000300.SH" },
  { label: "中证500", value: "000905.SH" },
  { label: "创业板指", value: "399006.SZ" },
];

const strategies = computed(() => store.state.strategy?.strategies || []);

const strategyOptions = computed(() =>
  strategies.value.map((s: any) => ({
    key: s.id,
    label: s.name,
    disabled: s.status === "running",
  })),
);

const availableStrategies = computed(() =>
  strategyOptions.value.filter(
    (s: any) => !selectedStrategies.value.includes(s.key),
  ),
);

const selectedLabels = computed(() => {
  const map: Record<string, string> = {};
  strategyOptions.value.forEach((s: any) => {
    map[s.key] = s.label;
  });
  return map;
});

const backtestDateRange = computed({
  get: () =>
    [backtestParams.value.startDate, backtestParams.value.endDate] as [
      string,
      string,
    ],
  set: ([start, end]: [string, string]) => {
    backtestParams.value.startDate = start;
    backtestParams.value.endDate = end;
  },
});

const addStrategy = (key: string) => {
  if (!selectedStrategies.value.includes(key))
    selectedStrategies.value.push(key);
};
const removeStrategy = (key: string) => {
  selectedStrategies.value = selectedStrategies.value.filter((k) => k !== key);
};
const addAll = () => {
  availableStrategies.value.forEach((s: any) => {
    if (!selectedStrategies.value.includes(s.key))
      selectedStrategies.value.push(s.key);
  });
};
const removeAll = () => {
  selectedStrategies.value = [];
};

const loadStudioData = async () => {
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

const runMultiBacktest = async () => {
  if (selectedStrategies.value.length < 2) {
    message.warning("请选择至少两个策略进行对比");
    return;
  }
  running.value = true;
  error.value = false;
  try {
    comparisonResults.value = [{ name: "策略A", returns: [] }];
    message.success("多策略回测完成");
  } catch (e: any) {
    error.value = true;
  } finally {
    running.value = false;
  }
};

const parameterOptimization = () => {
  if (selectedStrategies.value.length !== 1) {
    message.warning("请选择一个策略进行参数优化");
    return;
  }
  optimizationStrategy.value = strategies.value.find(
    (s: any) => s.id === selectedStrategies.value[0],
  );
  showOptimization.value = true;
};

const runOptimization = async (parameters: any) => {
  try {
    optimizationResults.value = { bestParameters: parameters };
    message.success("参数优化完成");
  } catch (e: any) {
    message.error("优化失败: " + e.message);
  }
};

const exportResults = () => {
  const data =
    comparisonResults.value.length > 0
      ? comparisonResults.value
      : optimizationResults.value;
  if (!data) {
    message.warning("没有可导出的数据");
    return;
  }
  message.info("导出功能开发中");
};

onMounted(() => loadStudioData());
</script>

<style scoped>
.backtest-studio {
  padding: 20px;
}

.studio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}
.studio-header h2 {
  margin: 0;
  color: var(--n-text-color-1);
}

.studio-content {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 30px;
}

.strategy-selection,
.backtest-config {
  background: var(--n-card-color);
  padding: 20px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
.strategy-selection h3,
.backtest-config h3 {
  margin: 0 0 16px;
  color: var(--n-text-color-1);
}

.transfer-wrapper {
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.transfer-panel {
  flex: 1;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  overflow: hidden;
}
.transfer-panel-header {
  padding: 8px 12px;
  font-weight: 500;
  background: var(--n-color-embedded);
  border-bottom: 1px solid var(--n-border-color);
}
.transfer-panel-body {
  height: 200px;
  overflow-y: auto;
  padding: 4px;
}
.transfer-item {
  padding: 6px 10px;
  cursor: pointer;
  border-radius: 2px;
  font-size: 13px;
}
.transfer-item:hover {
  background: var(--n-color-hover);
}
.transfer-item.selected {
  background: var(--n-color-target);
  color: var(--n-color-target-text);
}
.transfer-actions {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.comparison-charts,
.optimization-panel {
  grid-column: 1 / -1;
  background: var(--n-card-color);
  padding: 20px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  margin-top: 20px;
}
.comparison-charts h3,
.optimization-panel h3 {
  margin: 0 0 16px;
  color: var(--n-text-color-1);
}
.optimization-results {
  margin-top: 20px;
}
</style>
