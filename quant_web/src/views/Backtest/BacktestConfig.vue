<template>
  <div class="backtest-config bg-gradient-mesh bg-noise">
    <div class="config-header">
      <h2>策略回测配置</h2>
      <n-space :size="8">
        <n-button type="primary" :loading="isBacktesting" @click="runBacktest"
          >启动回测</n-button
        >
        <n-button type="success" :loading="isOptimizing" @click="optimizeParams"
          >参数优化</n-button
        >
      </n-space>
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
                  v-model:value="stockPool"
                  multiple
                  filterable
                  placeholder="添加股票到回测池"
                  :options="stockSelectOptions"
                  style="margin-bottom: 15px"
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
import { ref, computed, onMounted } from "vue";
import { useMessage } from "naive-ui";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
const isBacktesting = ref(false);
const isOptimizing = ref(false);
const activeTab = ref("basic");
const selectedStrategy = ref<any>(null);
const stockPool = ref<string[]>([]);
const tradeRestrictions = ref<string[]>([]);

const strategyOptions = [
  {
    id: 1,
    name: "双均线策略",
    type: "趋势跟踪",
    description: "基于短期和长期均线交叉进行交易",
  },
  {
    id: 2,
    name: "RSI超买超卖",
    type: "反转策略",
    description: "在RSI指标超买超卖区域进行反向交易",
  },
  {
    id: 3,
    name: "布林带突破",
    type: "突破策略",
    description: "在价格突破布林带上下轨时进行交易",
  },
  {
    id: 4,
    name: "MACD金叉死叉",
    type: "趋势跟踪",
    description: "基于MACD指标的金叉和死叉信号进行交易",
  },
];

const stockOptions = [
  { code: "600519", name: "贵州茅台" },
  { code: "000858", name: "五粮液" },
  { code: "601318", name: "中国平安" },
  { code: "600036", name: "招商银行" },
  { code: "000333", name: "美的集团" },
  { code: "000651", name: "格力电器" },
  { code: "600276", name: "恒瑞医药" },
  { code: "300059", name: "东方财富" },
];
const stockSelectOptions = stockOptions.map((s) => ({
  label: `${s.name} (${s.code})`,
  value: s.code,
}));

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
    await new Promise((r) => setTimeout(r, 300));
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
  try {
    await new Promise((r) => setTimeout(r, 500));
    message.success("回测已启动，请查看回测报告");
  } catch {
    message.error("回测启动失败");
  } finally {
    isBacktesting.value = false;
  }
};

const optimizeParams = async () => {
  isOptimizing.value = true;
  try {
    await new Promise((r) => setTimeout(r, 500));
    message.info("参数优化已启动，请稍后查看结果");
  } catch {
    message.error("参数优化启动失败");
  } finally {
    isOptimizing.value = false;
  }
};

onMounted(() => loadData());
</script>

<style scoped>
.backtest-config {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}
.config-header h2 {
  margin: 0;
  color: var(--n-text-color-1);
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
</style>
