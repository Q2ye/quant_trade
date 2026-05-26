<template>
  <div class="backtest-studio bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">回测工作室</h1>
        </div>
        <div class="header-actions">
          <n-button type="primary" :loading="running" @click="runMultiBacktest">
            {{ running ? `回测中 ${runningProgress}%` : '多策略回测' }}
          </n-button>
          <n-button @click="parameterOptimization">参数优化</n-button>
          <n-button @click="exportResults">导出结果</n-button>
          <n-button class="action-btn" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
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
          <div class="studio-left">
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
          </div>

          <div class="studio-right">
            <!-- 错误状态 -->
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

            <!-- 回测进度 -->
            <div v-else-if="running" class="progress-section">
              <n-card :class="tokens.surface.card" size="small">
                <div class="progress-header">
                  <span class="progress-title">多策略对比回测运行中</span>
                  <span class="progress-sub">{{ runningStatusText }}</span>
                </div>
                <n-progress
                  type="line"
                  :percentage="runningProgress"
                  :status="runningProgress === 100 ? 'success' : 'default'"
                  :height="20"
                  :border-radius="10"
                />
              </n-card>
            </div>

            <!-- 对比结果 -->
            <div v-else-if="comparisonResults.length > 0" class="comparison-charts">
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

            <!-- 参数优化 -->
            <div v-else-if="showOptimization" class="optimization-panel">
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

            <!-- 引导占位 -->
            <div v-else class="studio-guide">
              <div class="guide-icon">
                <Icon icon="mdi:flask-outline" :width="64" :height="64" />
              </div>
              <h3 class="guide-title">多策略对比回测</h3>
              <p class="guide-desc">
                在左侧面板中选择 2 个或更多策略，配置回测参数后点击「多策略回测」按钮，系统将同时对多个策略执行回测，并在此区域展示对比分析结果。
              </p>
              <div class="guide-steps">
                <div class="guide-step">
                  <span class="step-num">1</span>
                  <span>在左侧策略池中选择要对比的策略</span>
                </div>
                <div class="guide-step">
                  <span class="step-num">2</span>
                  <span>设置回测周期和初始资金</span>
                </div>
                <div class="guide-step">
                  <span class="step-num">3</span>
                  <span>点击「多策略回测」开始分析</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { useStore } from "vuex";
import { useMessage, NResult, NSpin } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import backtestAPI from "@/api/backtest";
import webSocketService from "@/api/websocket";
import MultiStrategyChart from "@/components/charts/MultiStrategyChart.vue";
import PerformanceTable from "@/components/strategy/PerformanceTable.vue";
import DrawdownComparison from "@/components/charts/DrawdownComparison.vue";
import ParameterOptimizer from "@/components/strategy/ParameterOptimizer.vue";
import HeatmapChart from "@/components/charts/BacktestHeatmapChart.vue";
import ParameterTable from "@/components/strategy/ParameterTable.vue";

const message = useMessage();
const router = useRouter();
const store = useStore<any>();

const loading = ref(false);
const pageError = ref(false);
const running = ref(false);
const error = ref(false);
const runningProgress = ref(0);
const runningStatusText = ref("");
const selectedStrategies = ref<string[]>([]);
const comparisonResults = ref<any[]>([]);
const showOptimization = ref(false);
const optimizationStrategy = ref<any>(null);
const optimizationResults = ref<any>(null);
let progressTimer: ReturnType<typeof setInterval> | null = null;
let runningTaskIds: string[] = [];

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
  runningProgress.value = 0;
  runningStatusText.value = "提交回测任务...";
  runningTaskIds = [];

  try {
    const tasks = selectedStrategies.value.map((id) => {
      const strat = strategies.value.find((s: any) => s.id === id);
      return {
        id,
        name: strat?.name || `策略_${id}`,
      };
    });

    // 并行创建所有回测任务
    const createPromises = tasks.map((t) =>
      backtestAPI.createTask({
        name: `${t.name}_对比回测`,
        strategyId: String(t.id),
        startDate: backtestParams.value.startDate,
        endDate: backtestParams.value.endDate,
        initialCapital: backtestParams.value.initialCapital,
        commission: 0.0003,
        slippage: 0.001,
        universe: [],
        benchmark: backtestParams.value.benchmark,
      }),
    );

    const results = await Promise.all(createPromises);
    runningTaskIds = results.map((r: any) => r.task_id);

    // 轮询等待所有任务完成
    runningStatusText.value = "回测运行中...";
    await waitForAllTasks(runningTaskIds);

    // 获取所有任务结果
    const resultPromises = runningTaskIds.map((taskId) =>
      backtestAPI.getResult(taskId),
    );
    const allResults = await Promise.all(resultPromises);

    // 组装对比数据
    comparisonResults.value = allResults.map(
      (res: any, idx: number) => ({
        name: tasks[idx].name,
        strategyId: tasks[idx].id,
        taskId: runningTaskIds[idx],
        ...res,
      }),
    );

    runningProgress.value = 100;
    message.success("多策略回测完成");
  } catch (e: any) {
    error.value = true;
    message.error(e.message || "回测执行失败");
  } finally {
    running.value = false;
    runningTaskIds = [];
  }
};

const waitForAllTasks = async (taskIds: string[]): Promise<void> => {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const statuses = await Promise.all(
          taskIds.map((id) =>
            backtestAPI.getTask(id).catch(() => null),
          ),
        );

        const allDone = statuses.every(
          (s: any) =>
            s &&
            (s.status === "completed" ||
              s.status === "failed" ||
              s.status === "cancelled"),
        );

        const totalProgress = statuses.reduce(
          (sum: number, s: any) =>
            sum + (s?.progress ?? s?.progress_percent ?? 0),
          0,
        );
        runningProgress.value = Math.floor(totalProgress / taskIds.length);

        const active = statuses.filter(
          (s: any) => s && s.status === "running",
        ).length;
        runningStatusText.value = `已完成 ${taskIds.length - active}/${taskIds.length} 个任务`;

        if (allDone) {
          const hasFailed = statuses.some(
            (s: any) => s && s.status === "failed",
          );
          if (hasFailed) {
            reject(new Error("部分回测任务执行失败"));
          } else {
            resolve();
          }
        } else {
          setTimeout(check, 2000);
        }
      } catch {
        setTimeout(check, 2000);
      }
    };
    check();
  });
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
  if (!optimizationStrategy.value) return;
  try {
    const res = await backtestAPI.optimizeParameters({
      strategyId: String(optimizationStrategy.value.id),
      parameterRanges: parameters,
      optimizationTarget: "sharpe_ratio",
      startDate: backtestParams.value.startDate,
      endDate: backtestParams.value.endDate,
      initialCapital: backtestParams.value.initialCapital,
    });
    optimizationResults.value = res;
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
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `backtest_results_${new Date().toISOString().split("T")[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
  message.success("导出成功");
};

onMounted(() => loadStudioData());
onBeforeUnmount(() => {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
});
</script>

<style scoped>
.backtest-studio {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}
.studio-content {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 24px;
  align-items: start;
}

.studio-left {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.studio-right {
  min-height: 400px;
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
  background: var(--n-card-color);
  padding: 20px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
.comparison-charts h3,
.optimization-panel h3 {
  margin: 0 0 16px;
  color: var(--n-text-color-1);
}
.optimization-results {
  margin-top: 20px;
}

/* 引导占位 */
.studio-guide {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 32px;
  text-align: center;
  background: var(--n-card-color);
  border-radius: 8px;
  border: 1px dashed var(--n-border-color);
  min-height: 400px;
}
.guide-icon {
  color: var(--n-text-color-3);
  opacity: 0.5;
  margin-bottom: 20px;
}
.guide-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0 0 12px;
}
.guide-desc {
  font-size: 14px;
  color: var(--n-text-color-3);
  line-height: 1.6;
  max-width: 420px;
  margin: 0 0 28px;
}
.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: left;
}
.guide-step {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: var(--n-text-color-2);
}
.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--n-primary-color);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.progress-section {
  margin-bottom: 0;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.progress-title {
  font-weight: 600;
  color: var(--n-text-color-1);
}
.progress-sub {
  font-size: 13px;
  color: var(--n-text-color-3);
}
</style>
