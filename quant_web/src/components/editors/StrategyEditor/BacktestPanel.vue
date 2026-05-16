<script setup lang="ts">
import { ref, reactive } from "vue";
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NDatePicker,
  NInputNumber,
  NSelect,
  NSwitch,
  NSlider,
  NProgress,
} from "naive-ui";
import { useMessage } from "naive-ui";
import { useStore } from "vuex";

const message = useMessage();
const store = useStore();

const backtestConfig = reactive({
  startDate: "2023-01-01",
  endDate: "2023-12-31",
  initialCapital: 1000000,
  commission: 0.0003,
  tax: 0.001,
  slippage: 0.001,
  frequency: "daily",
  benchmark: "000300.SH",
  enableShort: false,
  maxPositionRatio: 1.0,
});

const backtestStatus = ref<"idle" | "running" | "completed" | "error">("idle");
const backtestProgress = ref(0);
const backtestResult = ref<any>(null);

const benchmarkOptions = [
  { label: "沪深300", value: "000300.SH" },
  { label: "上证指数", value: "000001.SH" },
  { label: "深证成指", value: "399001.SZ" },
  { label: "创业板指", value: "399006.SZ" },
];

const frequencyOptions = [
  { label: "日线", value: "daily" },
  { label: "分钟线", value: "minutely" },
];

const validateConfig = () => {
  if (!backtestConfig.startDate || !backtestConfig.endDate) {
    message.error("请选择回测时间范围");
    return false;
  }
  if (backtestConfig.initialCapital <= 0) {
    message.error("初始资金必须大于0");
    return false;
  }
  if (new Date(backtestConfig.startDate) >= new Date(backtestConfig.endDate)) {
    message.error("开始时间必须早于结束时间");
    return false;
  }
  return true;
};

const runBacktest = async () => {
  if (!validateConfig()) return;
  backtestStatus.value = "running";
  backtestProgress.value = 0;
  try {
    const progressInterval = setInterval(() => {
      backtestProgress.value += Math.random() * 10;
      if (backtestProgress.value >= 100) {
        clearInterval(progressInterval);
        backtestProgress.value = 100;
      }
    }, 200);
    const result = await store.dispatch("strategy/runBacktest", backtestConfig);
    backtestResult.value = result;
    backtestStatus.value = "completed";
    message.success("回测完成");
  } catch (error) {
    backtestStatus.value = "error";
    message.error("回测执行失败");
  }
};

const stopBacktest = () => {
  backtestStatus.value = "idle";
  backtestProgress.value = 0;
};

const exportResult = () => {
  if (!backtestResult.value) {
    message.warning("没有可导出的结果");
    return;
  }
  message.success("导出成功");
};

const resetConfig = () => {
  Object.assign(backtestConfig, {
    startDate: "2023-01-01",
    endDate: "2023-12-31",
    initialCapital: 1000000,
    commission: 0.0003,
    tax: 0.001,
    slippage: 0.001,
    frequency: "daily",
    benchmark: "000300.SH",
    enableShort: false,
    maxPositionRatio: 1.0,
  });
};
</script>

<template>
  <div class="backtest-panel">
    <div class="panel-header">
      <h3>回测配置</h3>
      <div class="header-actions">
        <NButton
          size="small"
          :disabled="backtestStatus === 'running'"
          @click="resetConfig"
        >
          重置
        </NButton>
        <NButton
          type="primary"
          size="small"
          :loading="backtestStatus === 'running'"
          :disabled="backtestStatus === 'running'"
          @click="runBacktest"
        >
          {{ backtestStatus === "running" ? "回测中..." : "执行回测" }}
        </NButton>
      </div>
    </div>

    <div class="config-form">
      <NCard class="config-section">
        <template #header><span>基本配置</span></template>
        <NForm
          :model="backtestConfig"
          label-placement="left"
          label-width="120px"
        >
          <NFormItem label="时间范围">
            <div class="date-range">
              <NDatePicker
                v-model:formatted-value="backtestConfig.startDate"
                value-format="yyyy-MM-dd"
                type="date"
                placeholder="开始日期"
                style="width: 48%; margin-right: 4%"
              />
              <NDatePicker
                v-model:formatted-value="backtestConfig.endDate"
                value-format="yyyy-MM-dd"
                type="date"
                placeholder="结束日期"
                style="width: 48%"
              />
            </div>
          </NFormItem>

          <NFormItem label="初始资金">
            <NInputNumber
              v-model:value="backtestConfig.initialCapital"
              :min="10000"
              :step="10000"
            />
            <span class="unit">元</span>
          </NFormItem>

          <NFormItem label="回测频率">
            <NSelect
              v-model:value="backtestConfig.frequency"
              :options="frequencyOptions"
            />
          </NFormItem>

          <NFormItem label="基准指数">
            <NSelect
              v-model:value="backtestConfig.benchmark"
              :options="benchmarkOptions"
            />
          </NFormItem>
        </NForm>
      </NCard>

      <NCard class="config-section">
        <template #header><span>交易成本</span></template>
        <NForm
          :model="backtestConfig"
          label-placement="left"
          label-width="120px"
        >
          <NFormItem label="佣金费率">
            <NInputNumber
              v-model:value="backtestConfig.commission"
              :min="0"
              :step="0.0001"
              :decimal-places="4"
            />
            <span class="unit">%</span>
          </NFormItem>
          <NFormItem label="印花税">
            <NInputNumber
              v-model:value="backtestConfig.tax"
              :min="0"
              :step="0.0001"
              :decimal-places="4"
            />
            <span class="unit">%</span>
          </NFormItem>
          <NFormItem label="滑点">
            <NInputNumber
              v-model:value="backtestConfig.slippage"
              :min="0"
              :step="0.0001"
              :decimal-places="4"
            />
            <span class="unit">%</span>
          </NFormItem>
        </NForm>
      </NCard>

      <NCard class="config-section">
        <template #header><span>高级选项</span></template>
        <NForm
          :model="backtestConfig"
          label-placement="left"
          label-width="120px"
        >
          <NFormItem label="允许卖空">
            <NSwitch v-model:value="backtestConfig.enableShort" />
          </NFormItem>
          <NFormItem label="最大持仓比例">
            <NSlider
              v-model:value="backtestConfig.maxPositionRatio"
              :min="0.1"
              :max="1"
              :step="0.1"
              :marks="{ 0.1: '10%', 0.5: '50%', 1: '100%' }"
            />
            <span class="slider-value"
              >{{ (backtestConfig.maxPositionRatio * 100).toFixed(0) }}%</span
            >
          </NFormItem>
        </NForm>
      </NCard>
    </div>

    <div v-if="backtestStatus === 'running'" class="progress-section">
      <NProgress
        :percentage="backtestProgress"
        :status="backtestProgress === 100 ? 'success' : undefined"
        :show-indicator="false"
      />
      <div class="progress-text">
        回测进行中... {{ backtestProgress.toFixed(0) }}%
      </div>
      <NButton size="small" @click="stopBacktest">停止</NButton>
    </div>

    <div
      v-if="backtestStatus === 'completed' && backtestResult"
      class="result-section"
    >
      <div class="result-header">
        <h4>回测结果</h4>
        <NButton size="small" @click="exportResult">导出结果</NButton>
      </div>
      <div class="result-metrics">
        <div class="metric-item">
          <div class="metric-label">年化收益率</div>
          <div
            class="metric-value"
            :class="{ positive: backtestResult.annualReturn > 0 }"
          >
            {{ (backtestResult.annualReturn * 100).toFixed(2) }}%
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-label">夏普比率</div>
          <div class="metric-value">
            {{ backtestResult.sharpeRatio.toFixed(2) }}
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-label">最大回撤</div>
          <div class="metric-value negative">
            {{ (backtestResult.maxDrawdown * 100).toFixed(2) }}%
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-label">总交易次数</div>
          <div class="metric-value">{{ backtestResult.totalTrades }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.backtest-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--n-border-color);
}

.config-form {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.config-section {
  margin-bottom: 16px;
}

.config-section:last-child {
  margin-bottom: 0;
}

.date-range {
  display: flex;
  width: 100%;
}

.unit {
  margin-left: 8px;
  color: var(--n-text-color-3);
}

.slider-value {
  margin-left: 16px;
  min-width: 40px;
  text-align: center;
}

.progress-section {
  padding: 16px;
  border-top: 1px solid var(--n-border-color);
  text-align: center;
}

.progress-text {
  margin: 8px 0;
  color: var(--n-text-color-3);
}

.result-section {
  padding: 16px;
  border-top: 1px solid var(--n-border-color);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.result-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.metric-item {
  text-align: center;
  padding: 12px;
  background: var(--n-color-embedded);
  border-radius: 6px;
}

.metric-label {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: bold;
}

.metric-value.positive {
  color: #f56c6c;
}

.metric-value.negative {
  color: #67c23a;
}
</style>
