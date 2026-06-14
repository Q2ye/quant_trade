<template>
  <StrategyLayout>
    <template #header>
      <div class="page-header">
        <div class="header-content">
          <div class="title-section">
            <h1 class="page-title">{{ strategy.name }}</h1>
          </div>
          <div class="header-actions">
            <n-tag :type="STRATEGY_STATUS_MAP[strategy.status] as any">
              {{ STRATEGY_STATUS_TEXT[strategy.status] }}
            </n-tag>
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
          </div>
        </div>
      </div>
    </template>

    <template #editor>
      <CodeEditorPanel
        :code="strategy.code"
        language="python"
        :readOnly="isReadOnly"
        @update:code="(val: string) => (strategy.code = val)"
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
            :label="PARAM_LABELS[key]"
          >
            <n-input-number
              v-model:value="strategy.parameters[key]"
              :min="PARAM_MINS[key]"
              :max="PARAM_MAXS[key]"
              :step="PARAM_STEPS[key]"
              size="small"
            />
            <span class="param-desc">{{ PARAM_DESCS[key] }}</span>
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
import CodeEditorPanel from "@/components/editors/CodeEditorPanel.vue";
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

import {
  PARAM_LABELS,
  PARAM_DESCS,
  PARAM_MINS,
  PARAM_MAXS,
  PARAM_STEPS,
  STRATEGY_STATUS_MAP,
  STRATEGY_STATUS_TEXT,
} from "./constants";

const toggleStrategy = async () => {
  toggling.value = true;
  try {
    if (strategy.value.status === "running")
      await store.dispatch("strategy/stopStrategy", strategy.value.id);
    else
      await store.dispatch("strategy/startStrategy", {
        strategyId: strategy.value.id,
      });
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
  store.dispatch("strategy/runBacktest", {
    strategyId: strategy.value.id,
    config: strategy.value,
  });
</script>

<style scoped>
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
