<template>
  <div class="backtest-config bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略回测配置</h1>
        </div>
        <div class="header-actions">
          <n-button
            type="primary"
            :loading="isBacktesting"
            @click="runBacktest"
          >
            {{ isBacktesting ? `回测中 ${backtestProgress}%` : "启动回测" }}
          </n-button>
          <n-button
            type="success"
            :loading="isOptimizing"
            @click="optimizeParams"
            >参数优化</n-button
          >
        </div>
      </div>
    </div>

    <!-- 回测进度条 -->
    <div v-if="isBacktesting" class="progress-section">
      <n-card :class="tokens.surface.card" size="small">
        <div class="progress-header">
          <span class="progress-title">回测执行中</span>
          <span class="progress-status">{{ backtestStatusText }}</span>
        </div>
        <n-progress
          type="line"
          :percentage="backtestProgress"
          :status="backtestProgress === 100 ? 'success' : 'default'"
          :indicator-text="() => `${backtestProgress}%`"
          :height="24"
          :border-radius="12"
        />
        <div v-if="currentTaskId" class="progress-task-id">
          任务ID: {{ currentTaskId }}
        </div>
      </n-card>
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
        <n-tabs v-model:value="activeTab" type="line">
          <n-tab-pane name="basic" tab="基本配置">
            <div class="config-section">
              <h3>策略选择</h3>
              <div class="strategy-grid">
                <div
                  v-for="strategy in strategyOptions"
                  :key="strategy.id"
                  :class="[
                    'strategy-card',
                    { selected: selectedStrategy?.id === strategy.id },
                  ]"
                  @click="selectStrategy(strategy)"
                >
                  <div class="strategy-name">{{ strategy.name }}</div>
                  <div class="strategy-type">{{ strategy.type }}</div>
                  <div class="strategy-desc">{{ strategy.description }}</div>
                </div>
              </div>

              <div v-if="selectedStrategy" class="selected-strategy">
                <h4>已选策略: {{ selectedStrategy.name }}</h4>
                <p>{{ selectedStrategy.description }}</p>
              </div>
            </div>

            <div class="config-section">
              <h3>股票池</h3>
              <div class="stock-pool">
                <n-select
                  :key="stockPoolSelectKey"
                  v-model:value="stockPool"
                  multiple
                  filterable
                  virtual-scroll
                  placeholder="添加股票到回测池"
                  :options="stockSelectOptions"
                  style="margin-bottom: 15px"
                  @update:value="onStockPoolChange"
                />
                <div class="selected-stocks">
                  <n-tag
                    v-for="code in stockPool"
                    :key="code"
                    closable
                    @close="stockPool = stockPool.filter((c) => c !== code)"
                  >
                    {{ stockOptions.find((s) => s.code === code)?.name }} ({{
                      code
                    }})
                  </n-tag>
                </div>
              </div>
            </div>
          </n-tab-pane>

          <n-tab-pane name="params" tab="参数配置">
            <div v-if="selectedStrategy" class="param-config">
              <h3>{{ selectedStrategy.name }} 参数配置</h3>
              <div class="param-grid">
                <div
                  v-for="param in currentParams"
                  :key="param.name"
                  class="param-item"
                >
                  <div class="param-info">
                    <div class="param-label">{{ param.label }}</div>
                    <div class="param-value">
                      {{ strategyParams[param.name] }}
                    </div>
                  </div>
                  <div class="param-slider">
                    <n-slider
                      v-model:value="strategyParams[param.name]"
                      :min="param.min"
                      :max="param.max"
                      :step="param.step"
                    />
                    <n-input-number
                      v-model:value="strategyParams[param.name]"
                      :min="param.min"
                      :max="param.max"
                      :step="param.step"
                      size="small"
                      style="width: 80px; margin-left: 12px"
                    />
                  </div>
                </div>
              </div>
            </div>
            <n-alert
              v-else
              title="请先选择策略"
              type="warning"
              class="no-strategy"
            >
              请在"基本配置"标签页选择一个策略进行参数配置
            </n-alert>
          </n-tab-pane>

          <n-tab-pane name="settings" tab="回测设置">
            <div class="settings-form">
              <n-form :model="backtestSettings" label-width="120px">
                <n-form-item label="初始资金">
                  <n-input-number
                    v-model:value="backtestSettings.capital"
                    :min="10000"
                    :max="10000000"
                    :step="10000"
                  />
                  <span class="unit">元</span>
                </n-form-item>

                <n-form-item label="回测周期">
                  <n-space :size="8">
                    <n-date-picker
                      v-model:value="backtestSettings.startDate"
                      type="date"
                      placeholder="开始日期"
                    />
                    <span class="date-separator">至</span>
                    <n-date-picker
                      v-model:value="backtestSettings.endDate"
                      type="date"
                      placeholder="结束日期"
                    />
                  </n-space>
                </n-form-item>

                <n-form-item label="佣金费率">
                  <div class="slider-with-input">
                    <n-slider
                      v-model:value="backtestSettings.commission"
                      :min="0"
                      :max="0.005"
                      :step="0.0001"
                      style="flex: 1"
                    />
                    <n-input-number
                      v-model:value="backtestSettings.commission"
                      :min="0"
                      :max="0.005"
                      :step="0.0001"
                      size="small"
                      style="width: 100px; margin-left: 12px"
                    />
                  </div>
                </n-form-item>

                <n-form-item label="滑点设置">
                  <div class="slider-with-input">
                    <n-slider
                      v-model:value="backtestSettings.slippage"
                      :min="0"
                      :max="0.02"
                      :step="0.0005"
                      style="flex: 1"
                    />
                    <n-input-number
                      v-model:value="backtestSettings.slippage"
                      :min="0"
                      :max="0.02"
                      :step="0.0005"
                      size="small"
                      style="width: 100px; margin-left: 12px"
                    />
                  </div>
                </n-form-item>

                <n-form-item label="基准指数">
                  <n-select
                    v-model:value="backtestSettings.benchmark"
                    :options="benchmarkSelectOptions"
                  />
                </n-form-item>

                <n-form-item label="交易限制">
                  <n-checkbox-group v-model:value="tradeRestrictions">
                    <n-space :size="12">
                      <n-checkbox value="noT0">禁止T+0</n-checkbox>
                      <n-checkbox value="noShort">禁止做空</n-checkbox>
                      <n-checkbox value="noST">禁止交易ST股</n-checkbox>
                      <n-checkbox value="noLimitUp">禁止交易涨停股</n-checkbox>
                    </n-space>
                  </n-checkbox-group>
                </n-form-item>
              </n-form>
            </div>
          </n-tab-pane>
        </n-tabs>
      </template>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useMessage } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import backtestAPI from "@/api/backtest";
import strategyAPI from "@/api/strategy";
import dataAPI from "@/api/data";
import { useBacktestPolling } from "@/composables/useBacktestPolling";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const loading = ref(false);
const error = ref(false);
const isBacktesting = ref(false);
const isOptimizing = ref(false);
const backtestProgress = ref(0);
const backtestStatus = ref("");
const currentTaskId = ref("");

// ---- 回测轮询（自适应间隔 + 容错） ----

const { start: startPolling, stop: clearProgressPolling } = useBacktestPolling(
  currentTaskId,
  {
    onProgress: (task) => {
      backtestProgress.value = task.progress ?? task.progress_percent ?? 0;
      backtestStatus.value = task.status || backtestStatus.value;
    },
    onCompleted: (task) => {
      message.success("回测完成");
      isBacktesting.value = false;
      router.push(`/backtest/report/${currentTaskId.value}`);
    },
    onFailed: (task) => {
      message.error(task?.error_message || "回测失败");
      isBacktesting.value = false;
    },
    onCancelled: () => {
      message.warning("回测已取消");
      isBacktesting.value = false;
    },
  },
);

const backtestStatusText = computed(() => {
  const map: Record<string, string> = {
    pending: "排队中...",
    running: "运行中...",
    data_loading: "加载行情数据...",
    data_preprocessing: "数据预处理...",
    strategy_initialization: "策略初始化...",
    simulation_running: "模拟交易中...",
    performance_calculation: "计算绩效指标...",
    report_generation: "生成报告...",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return map[backtestStatus.value] || backtestStatus.value || "等待中...";
});

const activeTab = ref("basic");
const selectedStrategy = ref<any>(null);
const stockPool = ref<string[]>([]);
const stockPoolSelectKey = ref(0);
const onStockPoolChange = (val: string[]) => {
  stockPool.value = val;
  stockPoolSelectKey.value++;
};
const tradeRestrictions = ref<string[]>([]);

// 从 API 加载的策略列表
const strategyOptions = ref<Array<{ id: string; name: string; type: string; description: string }>>([]);
// 从 API 加载的股票列表
const stockOptions = ref<Array<{ code: string; name: string }>>([]);
const stockSelectOptions = computed(() =>
  stockOptions.value.map((s) => ({
    label: `${s.name} (${s.code})`,
    value: s.code,
  }))
);

const backtestSettings = ref({
  capital: 1000000,
  startDate: Date.now() - 3 * 365 * 24 * 60 * 60 * 1000,
  endDate: Date.now(),
  commission: 0.0003,
  slippage: 0.001,
  benchmark: "000300.SH",
});

const benchmarkOptions = [
  { code: "000001.SH", name: "上证指数" },
  { code: "399001.SZ", name: "深证成指" },
  { code: "000300.SH", name: "沪深300" },
  { code: "000905.SH", name: "中证500" },
  { code: "399006.SZ", name: "创业板指" },
];
const benchmarkSelectOptions = benchmarkOptions.map((b) => ({
  label: `${b.name} (${b.code})`,
  value: b.code,
}));

const strategyParams = ref<Record<string, number>>({
  fastPeriod: 5,
  slowPeriod: 20,
  rsiPeriod: 14,
  overbought: 70,
  oversold: 30,
  bbPeriod: 20,
  bbStdDev: 2,
  macdFast: 12,
  macdSlow: 26,
  macdSignal: 9,
});

const paramGroups: Record<
  string,
  { name: string; label: string; min: number; max: number; step: number }[]
> = {
  trend: [
    { name: "fastPeriod", label: "快线周期", min: 1, max: 20, step: 1 },
    { name: "slowPeriod", label: "慢线周期", min: 10, max: 60, step: 1 },
  ],
  reversal: [
    { name: "rsiPeriod", label: "RSI周期", min: 5, max: 30, step: 1 },
    { name: "overbought", label: "超买阈值", min: 60, max: 90, step: 1 },
    { name: "oversold", label: "超卖阈值", min: 10, max: 40, step: 1 },
  ],
  breakout: [
    { name: "bbPeriod", label: "布林带周期", min: 10, max: 30, step: 1 },
    { name: "bbStdDev", label: "标准差倍数", min: 1.5, max: 3, step: 0.1 },
  ],
  macd: [
    { name: "macdFast", label: "快线周期", min: 5, max: 20, step: 1 },
    { name: "macdSlow", label: "慢线周期", min: 20, max: 50, step: 1 },
    { name: "macdSignal", label: "信号周期", min: 5, max: 20, step: 1 },
  ],
};

const currentParams = computed(() => {
  if (!selectedStrategy.value) return [];
  const typeMap: Record<string, string> = {
    趋势跟踪: "trend",
    反转策略: "reversal",
    突破策略: "breakout",
    MACD策略: "macd",
  };
  return paramGroups[typeMap[selectedStrategy.value.type]] || [];
});

const selectStrategy = (strategy: any) => {
  selectedStrategy.value = strategy;
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    const [strategies, stocks] = await Promise.all([
      strategyAPI.getStrategies().catch(() => []),
      dataAPI.getStockList().catch(() => []),
    ]);

    // 填充策略选项
    if (Array.isArray(strategies) && strategies.length > 0) {
      strategyOptions.value = strategies
        .filter((s: any) => s.id)  // 只显示有 ID 的策略
        .map((s: any) => ({
          id: s.id,
          name: s.name || s.id,
        type: s.strategy_type || s.type || "自定义",
        description: s.description || "",
      }));
    } else {
      // fallback：后端无策略时展示提示
      strategyOptions.value = [];
    }

    // 填充股票选项
    if (Array.isArray(stocks) && stocks.length > 0) {
      stockOptions.value = stocks.map((s: any) => ({
        code: s.ts_code || s.code || s.symbol,
        name: s.name || s.ts_code || "",
      }));
    }

    // 从 URL query 预填
    const qStrategy = route.query.strategy as string;
    const qStock = route.query.stock as string;
    if (qStrategy) {
      const found = strategyOptions.value.find(
        (s) => s.id === qStrategy || s.name === qStrategy
      );
      if (found) selectedStrategy.value = found;
    }
    if (qStock) {
      const codes = qStock.split(",").map((c) => c.trim()).filter(Boolean);
      // 自动补全 .SZ/.SH 后缀
      stockPool.value = codes.map((c) =>
        /\.(SZ|SH|BJ)$/i.test(c) ? c : c.length === 6 ? `${c}.${c.startsWith("6") ? "SH" : "SZ"}` : c
      );
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const runBacktest = async () => {
  if (!selectedStrategy.value) {
    message.warning("请选择一个策略");
    return;
  }
  if (stockPool.value.length === 0) {
    message.warning("请添加至少一个股票到股票池");
    return;
  }

  isBacktesting.value = true;
  backtestProgress.value = 0;
  backtestStatus.value = "pending";
  currentTaskId.value = "";

  try {
    const startDate = new Date(backtestSettings.value.startDate)
      .toISOString()
      .split("T")[0];
    const endDate = new Date(backtestSettings.value.endDate)
      .toISOString()
      .split("T")[0];

    const res = await backtestAPI.createTask({
      name: `${selectedStrategy.value.name}_回测_${startDate}`,
      strategy_id: selectedStrategy.value.id,
      start_date: startDate,
      end_date: endDate,
      initial_capital: backtestSettings.value.capital,
      commission_rate: backtestSettings.value.commission,
      slippage_rate: backtestSettings.value.slippage,
      symbols: stockPool.value,
      benchmark: backtestSettings.value.benchmark,
      parameters: {
        strategy_params: { ...strategyParams.value },
        ts_code: stockPool.value,
      },
    });

    currentTaskId.value = res.task_id;
    backtestStatus.value = "running";
    startPolling();
  } catch (err: any) {
    message.error(err.message || "回测启动失败");
    isBacktesting.value = false;
    clearProgressPolling();
  }
};

const optimizeParams = async () => {
  if (!selectedStrategy.value) {
    message.warning("请选择一个策略");
    return;
  }
  isOptimizing.value = true;
  try {
    const startDate = new Date(backtestSettings.value.startDate)
      .toISOString()
      .split("T")[0];
    const endDate = new Date(backtestSettings.value.endDate)
      .toISOString()
      .split("T")[0];

    const res = await backtestAPI.optimizeParameters({
      strategyId: selectedStrategy.value.id,
      parameterRanges: {
        // 根据当前策略类型构建参数范围
        fastPeriod: { min: 2, max: 20, step: 1 },
        slowPeriod: { min: 10, max: 60, step: 2 },
      },
      optimizationTarget: "sharpe_ratio",
      startDate,
      endDate,
      initialCapital: backtestSettings.value.capital,
    });

    message.success("参数优化完成，请查看结果");
    if (res?.task_id) {
      router.push(`/backtest/report/${res.task_id}`);
    }
  } catch (err: any) {
    message.error(err.message || "参数优化启动失败");
  } finally {
    isOptimizing.value = false;
  }
};

onMounted(() => loadData());
onBeforeUnmount(() => {
  clearProgressPolling();
});
</script>

<style scoped>
.backtest-config {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}
.config-section {
  background: var(--n-color-embedded);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}
.config-section h3 {
  margin: 0 0 20px;
  color: var(--n-text-color-1);
}

.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.strategy-card {
  background: var(--n-card-color);
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid var(--n-border-color);
}
.strategy-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  border-color: var(--n-primary-color);
}
.strategy-card.selected {
  background: color-mix(
    in srgb,
    var(--n-primary-color) 15%,
    var(--n-card-color)
  );
  border-color: var(--n-primary-color);
}
.strategy-name {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 5px;
  color: var(--n-text-color-1);
}
.strategy-type {
  font-size: 14px;
  color: #ff9800;
  margin-bottom: 10px;
}
.strategy-desc {
  font-size: 13px;
  color: var(--n-text-color-3);
  line-height: 1.5;
}

.selected-strategy {
  background: color-mix(
    in srgb,
    var(--n-primary-color) 10%,
    var(--n-card-color)
  );
  border-left: 4px solid var(--n-primary-color);
  padding: 15px;
  border-radius: 4px;
}
.selected-strategy h4 {
  margin: 0 0 8px;
  color: var(--n-text-color-1);
}
.selected-strategy p {
  color: var(--n-text-color-3);
}

.stock-pool {
  background: var(--n-card-color);
  border-radius: 8px;
  padding: 20px;
}
.selected-stocks {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  min-height: 40px;
}

.param-config {
  background: var(--n-color-embedded);
  border-radius: 8px;
  padding: 20px;
}
.param-config h3 {
  margin: 0 0 20px;
  color: var(--n-text-color-1);
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}
.param-item {
  background: var(--n-card-color);
  border-radius: 8px;
  padding: 15px;
}
.param-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}
.param-label {
  font-weight: bold;
  color: var(--n-text-color-1);
}
.param-value {
  color: #ff9800;
  font-weight: bold;
}
.param-slider {
  display: flex;
  align-items: center;
}

.settings-form {
  background: var(--n-color-embedded);
  border-radius: 8px;
  padding: 20px;
}
.slider-with-input {
  display: flex;
  align-items: center;
  width: 100%;
}

.unit {
  margin-left: 10px;
  color: var(--n-text-color-3);
}
.date-separator {
  color: var(--n-text-color-3);
}

.no-strategy {
  text-align: center;
}

.progress-section {
  margin-bottom: 20px;
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
.progress-status {
  font-size: 13px;
  color: var(--n-text-color-3);
}
.progress-task-id {
  margin-top: 8px;
  font-size: 12px;
  color: var(--n-text-color-3);
  font-family: monospace;
}
</style>
