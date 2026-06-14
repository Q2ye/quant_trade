<!--回测配置面板-->
<template>
  <div class="backtest-config">
    <h3 class="section-title">回测配置</h3>

    <div class="config-section">
      <h4>资金设置</h4>
      <div class="config-row">
        <div class="config-item">
          <label>初始资金 (元)</label>
          <NInputNumber
            v-model:value="config.capital"
            :min="10000"
            :step="10000"
            :decimal-places="0"
          />
        </div>
        <div class="config-item">
          <label>手续费 (%)</label>
          <NInputNumber
            v-model:value="config.commission"
            :min="0"
            :max="0.05"
            :step="0.0001"
            :decimal-places="4"
          />
        </div>
        <div class="config-item">
          <label>滑点 (%)</label>
          <NInputNumber
            v-model:value="config.slippage"
            :min="0"
            :max="0.05"
            :step="0.0001"
            :decimal-places="4"
          />
        </div>
      </div>
    </div>

    <div class="config-section">
      <h4>时间范围</h4>
      <TimeRangeSlider
        v-model="config.timeRange"
        @change="handleTimeRangeChange"
      />
    </div>

    <div class="config-section">
      <h4>回测周期</h4>
      <div class="config-row">
        <div class="config-item">
          <label>数据频率</label>
          <NSelect
            v-model:value="config.frequency"
            :options="frequencyOptions"
          />
        </div>
        <div class="config-item">
          <label>基准指数</label>
          <NSelect
            v-model:value="config.benchmark"
            :options="benchmarkOptions"
          />
        </div>
      </div>
    </div>

    <div v-if="strategy.params" class="config-section">
      <h4>策略参数</h4>
      <div class="params-grid">
        <ParamSlider
          v-for="(param, name) in strategy.params"
          :key="name"
          :param-name="name"
          :config="param"
          v-model="config.params[name]"
          @change="handleParamChange"
        />
      </div>
    </div>

    <div class="action-bar">
      <NButton type="primary" @click="startBacktest">开始回测</NButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from "vue";
import { NInputNumber, NSelect, NButton } from "naive-ui";
import TimeRangeSlider from "../data/TimeRangeSlider.vue";
import ParamSlider from "../strategy/ParamSlider.vue";

const props = defineProps<{
  strategy: {
    params?: Record<
      string,
      { default: number; min: number; max: number; step: number }
    >;
  };
}>();

const emit = defineEmits<{
  start: [config: any];
}>();

const config = reactive({
  capital: 1000000,
  commission: 0.0003,
  slippage: 0.001,
  timeRange: [
    new Date(new Date().setFullYear(new Date().getFullYear() - 1)),
    new Date(),
  ],
  frequency: "daily",
  benchmark: "000300.SH",
  params: {} as Record<string, number>,
});

const frequencyOptions = [
  { value: "daily", label: "日线" },
  { value: "weekly", label: "周线" },
  { value: "monthly", label: "月线" },
  { value: "60min", label: "60分钟" },
  { value: "30min", label: "30分钟" },
];

const benchmarkOptions = [
  { value: "000001.SH", label: "上证指数" },
  { value: "399001.SZ", label: "深证成指" },
  { value: "000300.SH", label: "沪深300" },
  { value: "000905.SH", label: "中证500" },
  { value: "399006.SZ", label: "创业板指" },
];

watch(
  () => props.strategy,
  (newVal) => {
    if (newVal && newVal.params) {
      for (const [key, param] of Object.entries(newVal.params)) {
        if (!(key in config.params)) {
          config.params[key] = param.default;
        }
      }
    }
  },
  { immediate: true },
);

const handleTimeRangeChange = (range: Date[]) => {
  config.timeRange = range as [Date, Date];
};

const handleParamChange = (paramName: string, value: number) => {
  config.params[paramName] = value;
};

const startBacktest = () => {
  emit("start", { ...config });
};
</script>

<style scoped>
.backtest-config {
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}

.section-title {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eaeaea;
  color: #303133;
}

.config-section {
  margin-bottom: 25px;
}

.config-section h4 {
  margin: 0 0 15px 0;
  font-size: 14px;
  font-weight: 600;
  color: #606266;
}

.config-row {
  display: flex;
  gap: 20px;
}

.config-item {
  flex: 1;
}

.config-item label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  color: #909399;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
}

.action-bar {
  margin-top: 20px;
  text-align: center;
}
</style>
