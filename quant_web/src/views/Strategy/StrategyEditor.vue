<template>
  <StrategyLayout>
    <template #header>
      <div class="editor-header">
        <div class="strategy-info">
          <h2>{{ strategy.name }}</h2>
          <n-tag :type="statusType[strategy.status] as any">
            {{ statusText[strategy.status] }}
          </n-tag>
        </div>
        <n-space :size="8">
          <n-button
            :type="strategy.status === 'running' ? 'error' : 'success'"
            :loading="toggling"
            @click="toggleStrategy"
          >
            {{ strategy.status === "running" ? "停止策略" : "启动策略" }}
          </n-button>
          <n-button type="primary" :loading="saving" @click="saveStrategy"
            >保存</n-button
          >
          <n-button @click="runBacktest">回测</n-button>
        </n-space>
      </div>
    </template>

    <template #editor>
      <CodeEditor
        v-model="strategy.code"
        language="python"
        :readOnly="isReadOnly"
        @save="saveStrategy"
      />
    </template>

    <template #config>
      <div class="config-section">
        <h3>策略参数配置</h3>
        <n-form label-width="100px">
          <n-form-item
            v-for="(_val, key) in strategy.parameters"
            :key="key"
            :label="paramLabels[key]"
          >
            <n-input-number
              v-model:value="strategy.parameters[key]"
              :min="paramMins[key]"
              :max="paramMaxs[key]"
              :step="paramSteps[key]"
              size="small"
            />
            <span class="param-desc">{{ paramDescs[key] }}</span>
          </n-form-item>
        </n-form>
      </div>

      <div class="config-section">
        <h3>股票池配置</h3>
        <StockPoolSelector v-model="strategy.stockPool" :multiple="true" />
      </div>

      <div class="config-section">
        <h3>回测设置</h3>
      </div>
    </template>

    <template #monitor>
      <div class="monitor-tabs">
        <n-tabs v-model:value="activeMonitorTab">
          <n-tab-pane name="logs" tab="实时日志">
            <BacktestLogs :logs="logs" />
          </n-tab-pane>
          <n-tab-pane name="variables" tab="变量监控">
            <VariableMonitor :variables="variables" />
          </n-tab-pane>
          <n-tab-pane name="signals" tab="信号跟踪">
            <SignalTimeline :signals="signals" />
          </n-tab-pane>
          <n-tab-pane name="performance" tab="性能分析">
            <RealTimePerformance :metrics="performanceMetrics" />
          </n-tab-pane>
        </n-tabs>
      </div>
    </template>
  </StrategyLayout>
</template>

<script setup lang="ts">
import { ref, inject } from "vue";
import { useStore } from "vuex";
import { useMessage } from "naive-ui";
import StockPoolSelector from "@/components/strategy/StockPoolSelector.vue";
import RealTimePerformance from "@/components/strategy/RealTimePerformance.vue";
import StrategyLayout from "@/layouts/StrategyLayout.vue";
import BacktestLogs from "@/components/strategy/BacktestLogs.vue";
import VariableMonitor from "@/components/strategy/VariableMonitor.vue";
import SignalTimeline from "@/views/Signal/SignalTimeline.vue";

const message = useMessage();
const store = useStore<any>();

const strategy = inject<any>(
  "strategy",
  ref({ name: "", status: "stopped", code: "", parameters: {}, stockPool: [] }),
);
const logs = inject<any[]>("logs", []);
const variables = inject<any[]>("variables", []);
const signals = inject<any[]>("signals", []);
const isReadOnly = inject<boolean>("isReadOnly", false);

const saving = ref(false);
const toggling = ref(false);
const activeMonitorTab = ref("logs");
const performanceMetrics = ref({});

const statusType: Record<string, string> = {
  running: "success",
  stopped: "default",
  error: "error",
};
const statusText: Record<string, string> = {
  running: "运行中",
  stopped: "已停止",
  error: "异常",
};

const paramLabels: Record<string, string> = {
  fastPeriod: "快线周期",
  slowPeriod: "慢线周期",
  tradeSize: "仓位比例",
};
const paramDescs: Record<string, string> = {
  fastPeriod: "短期均线周期，通常5-20",
  slowPeriod: "长期均线周期，通常20-60",
  tradeSize: "每次交易仓位比例，0-1之间",
};
const paramMins: Record<string, number> = {
  fastPeriod: 1,
  slowPeriod: 5,
  tradeSize: 0.1,
};
const paramMaxs: Record<string, number> = {
  fastPeriod: 50,
  slowPeriod: 100,
  tradeSize: 1.0,
};
const paramSteps: Record<string, number> = {
  fastPeriod: 1,
  slowPeriod: 5,
  tradeSize: 0.05,
};

const toggleStrategy = async () => {
  toggling.value = true;
  try {
    if (strategy.value.status === "running")
      await store.dispatch("strategy/stopStrategy", strategy.value.id);
    else await store.dispatch("strategy/startStrategy", strategy.value.id);
    message.success("操作成功");
  } catch (e: any) {
    message.error("操作失败: " + e.message);
  } finally {
    toggling.value = false;
  }
};

const saveStrategy = async () => {
  saving.value = true;
  try {
    await store.dispatch("strategy/updateStrategy", strategy.value);
    message.success("保存成功");
  } catch (e: any) {
    message.error("保存失败: " + e.message);
  } finally {
    saving.value = false;
  }
};

const runBacktest = () =>
  store.dispatch("backtest/runBacktest", strategy.value);
</script>

<style scoped>
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background: var(--n-card-color);
  border-bottom: 1px solid var(--n-border-color);
}

.strategy-info {
  display: flex;
  align-items: center;
  gap: 15px;
}
.strategy-info h2 {
  margin: 0;
  color: var(--n-text-color-1);
}

.param-desc {
  margin-left: 10px;
  font-size: 12px;
  color: var(--n-text-color-3);
}
.monitor-tabs {
  height: 100%;
}

.config-section {
  margin-bottom: 20px;
}
.config-section h3 {
  margin: 0 0 12px;
  color: var(--n-text-color-1);
  font-size: 14px;
}
</style>
