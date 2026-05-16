<template>
  <div :class="['bg-gradient-mesh', 'bg-noise', 'strategy-list']">
    <div class="header">
      <h2>策略管理</h2>
      <n-button type="primary" class="hover-lift" @click="createStrategy">新建策略</n-button>
    </div>

    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取策略列表失败，请稍后重试"
    >
      <template #footer
        ><n-button
          @click="
            () => {
              loading = true;
              error = false;
              store
                .dispatch('strategy/loadStrategies')
                .finally(() => (loading = false));
            }
          "
          class="hover-lift">重试</n-button
        ></template
      >
    </n-result>
    <n-spin v-else :show="loading">
      <n-empty v-if="strategies.length === 0" description="暂无策略" />
      <n-data-table
        v-else
        :columns="columns"
        :data="strategies"
        :bordered="false"
        size="small"
      />
    </n-spin>

    <n-modal
      v-model:show="showDialog"
      preset="dialog"
      :title="dialogTitle"
      positive-text="保存"
      negative-text="取消"
      @positive-click="saveStrategy"
    >
      <n-form :model="currentStrategy" label-width="100px">
        <n-form-item label="策略名称" required>
          <n-input v-model:value="currentStrategy.name" />
        </n-form-item>
        <n-form-item label="策略描述">
          <n-input
            v-model:value="currentStrategy.description"
            type="textarea"
            :rows="3"
          />
        </n-form-item>
        <n-form-item label="策略类型">
          <n-select
            v-model:value="currentStrategy.type"
            :options="typeOptions"
          />
        </n-form-item>
        <n-form-item label="基础参数">
          <div class="param-grid">
            <div
              v-for="(_val, key) in currentStrategy.parameters"
              :key="key"
              class="param-item"
            >
              <div class="param-label">{{ paramLabels[key] }}</div>
              <n-input-number
                v-model:value="currentStrategy.parameters[key]"
                :min="paramMins[key]"
                :max="paramMaxs[key]"
                :step="paramSteps[key]"
                size="small"
              />
            </div>
          </div>
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";
import { useMessage, NTag, NButton, NDropdown, NResult } from "naive-ui";

const message = useMessage();
const router = useRouter();
const store = useStore<any>();

const loading = ref(false);
const error = ref(false);
const showDialog = ref(false);
const isEditing = ref(false);
const currentStrategy = ref(getDefaultStrategy());

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

const typeOptions = [
  { label: "趋势跟踪", value: "trend" },
  { label: "均值回归", value: "mean_reversion" },
  { label: "套利策略", value: "arbitrage" },
  { label: "市场中性", value: "market_neutral" },
];

const strategies = computed(() => store.state.strategy?.strategies || []);
const dialogTitle = computed(() => (isEditing.value ? "编辑策略" : "新建策略"));

const columns = [
  { title: "ID", key: "id", width: 80 },
  { title: "策略名称", key: "name", width: 150 },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row: any) =>
      h(
        NTag,
        { type: statusType[row.status] as any },
        { default: () => statusText[row.status] },
      ),
  },
  { title: "策略类", key: "className", width: 150 },
  {
    title: "基础绩效",
    key: "performance",
    width: 120,
    render: (row: any) =>
      `${(row.performance?.annualReturn * 100 || 0).toFixed(2)}%`,
  },
  {
    title: "更新时间",
    key: "updatedAt",
    width: 180,
    render: (row: any) => formatDate(row.updatedAt),
  },
  {
    title: "操作",
    key: "op",
    width: 280,
    render: (row: any) =>
      h(
        "div",
        { style: { display: "flex", gap: "4px", alignItems: "center" } },
        [
          h(
            NButton,
            { size: "tiny", onClick: () => editStrategy(row) },
            { default: () => "编辑" },
          ),
          h(
            NButton,
            {
              size: "tiny",
              type: row.status === "running" ? "error" : "success",
              onClick: () => toggleStrategy(row),
            },
            { default: () => (row.status === "running" ? "停止" : "启动") },
          ),
          h(
            NButton,
            { size: "tiny", onClick: () => viewReport(row) },
            { default: () => "报告" },
          ),
          h(
            NDropdown,
            {
              trigger: "click",
              options: [
                { label: "克隆", key: "clone" },
                { label: "导出", key: "export" },
                { label: "删除", key: "delete" },
              ],
              onSelect: (key: string) => {
                if (key === "clone") cloneStrategy(row);
                else if (key === "export") exportStrategy(row);
                else if (key === "delete") deleteStrategy(row);
              },
            },
            {
              default: () =>
                h(NButton, { size: "tiny" }, { default: () => "更多" }),
            },
          ),
        ],
      ),
  },
];

function getDefaultStrategy() {
  return {
    id: null as number | null,
    name: "",
    description: "",
    type: "trend",
    className: "DualMovingAverage",
    parameters: { fastPeriod: 5, slowPeriod: 20, tradeSize: 0.95 } as Record<
      string,
      number
    >,
    status: "stopped",
  };
}

const formatDate = (date: any) => new Date(date).toLocaleString();

const createStrategy = () => {
  currentStrategy.value = getDefaultStrategy();
  isEditing.value = false;
  showDialog.value = true;
};
const editStrategy = (strategy: any) => {
  currentStrategy.value = { ...strategy };
  isEditing.value = true;
  showDialog.value = true;
};

const saveStrategy = async () => {
  try {
    if (isEditing.value)
      await store.dispatch("strategy/updateStrategy", currentStrategy.value);
    else await store.dispatch("strategy/createStrategy", currentStrategy.value);
    showDialog.value = false;
    message.success("保存成功");
  } catch (e: any) {
    message.error("保存失败: " + e.message);
  }
};

const toggleStrategy = async (strategy: any) => {
  try {
    if (strategy.status === "running")
      await store.dispatch("strategy/stopStrategy", strategy.id);
    else await store.dispatch("strategy/startStrategy", strategy.id);
  } catch (e: any) {
    message.error("操作失败: " + e.message);
  }
};

const viewReport = (strategy: any) =>
  router.push({ name: "BacktestReport", params: { id: strategy.id } });

const cloneStrategy = (strategy: any) => {
  currentStrategy.value = {
    ...strategy,
    id: null,
    name: strategy.name + "_副本",
  };
  isEditing.value = false;
  showDialog.value = true;
};

const exportStrategy = (strategy: any) => {
  const dataStr = JSON.stringify(strategy, null, 2);
  const blob = new Blob([dataStr], { type: "application/json" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${strategy.name}.json`;
  a.click();
  window.URL.revokeObjectURL(url);
};

const deleteStrategy = async (strategy: any) => {
  try {
    await store.dispatch("strategy/deleteStrategy", strategy.id);
    message.success("删除成功");
  } catch (e: any) {
    message.error("删除失败: " + e.message);
  }
};

onMounted(async () => {
  loading.value = true;
  try {
    await store.dispatch("strategy/loadStrategies");
    error.value = false;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.strategy-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.param-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}
</style>
