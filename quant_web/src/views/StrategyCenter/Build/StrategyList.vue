<template>
  <div class="strategy-list bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略管理</h1>
          <p class="page-description">管理交易策略，创建、编辑、启停策略</p>
        </div>
        <div class="header-actions">
          <n-button type="primary" class="hover-lift" @click="createStrategy">新建策略</n-button>
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result
        v-if="pageState === 'error'"
        status="500"
        title="加载失败"
        description="获取策略列表失败，请稍后重试"
      >
        <template #footer>
          <n-button @click="loadStrategies" class="hover-lift">重试</n-button>
        </template>
      </n-result>
      <n-empty v-else-if="pageState === 'empty'" description="暂无策略">
        <template #extra>
          <n-button type="primary" @click="createStrategy">
            <template #icon><SmartIcon name="Plus" /></template>
            新建策略
          </n-button>
        </template>
      </n-empty>
      <template v-else-if="pageState === 'data'">
        <div class="section-block">
          <n-data-table
            :columns="columns"
            :data="strategies"
            :bordered="false"
            size="small"
          />
        </div>
      </template>
    </div>

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
            :options="STRATEGY_TYPE_OPTIONS"
          />
        </n-form-item>
        <n-form-item label="基础参数">
          <div class="param-grid">
            <div
              v-for="(_val, key) in currentStrategy.parameters"
              :key="key"
              class="param-item"
            >
              <div class="param-label">{{ PARAM_LABELS[key] }}</div>
              <n-input-number
                v-model:value="currentStrategy.parameters[key]"
                :min="PARAM_MINS[key]"
                :max="PARAM_MAXS[key]"
                :step="PARAM_STEPS[key]"
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
import SmartIcon from "@/components/common/SmartIcon.vue";
import { useStore } from "vuex";
import { useMessage, useDialog, NTag, NButton, NDropdown, NResult } from "naive-ui";
import {
  PARAM_LABELS,
  PARAM_MINS,
  PARAM_MAXS,
  PARAM_STEPS,
  STRATEGY_TYPE_OPTIONS,
  STRATEGY_STATUS_MAP,
  STRATEGY_STATUS_TEXT,
} from "./constants";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();
const store = useStore<any>();

type PageState = "loading" | "error" | "empty" | "data";
const pageState = ref<PageState>("loading");
const showDialog = ref(false);
const isEditing = ref(false);
const currentStrategy = ref(getDefaultStrategy());

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
        { type: STRATEGY_STATUS_MAP[row.status] as any },
        { default: () => STRATEGY_STATUS_TEXT[row.status] },
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

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/strategy/build");
};

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
    else await store.dispatch("strategy/startStrategy", { strategyId: strategy.id });
  } catch (e: any) {
    message.error("操作失败: " + e.message);
  }
};

const viewReport = (strategy: any) =>
  router.push({ name: "BacktestReport", params: { taskId: strategy.id } });

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

const deleteStrategy = (strategy: any) => {
  dialog.warning({
    title: "删除确认",
    content: `确定要删除策略"${strategy.name}"吗？此操作不可撤销。`,
    positiveText: "确定删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await store.dispatch("strategy/deleteStrategy", strategy.id);
        message.success("删除成功");
      } catch (e: any) {
        message.error("删除失败: " + e.message);
      }
    },
  });
};

const loadStrategies = async () => {
  pageState.value = "loading";
  try {
    await store.dispatch("strategy/loadStrategies");
    pageState.value = strategies.value.length === 0 ? "empty" : "data";
  } catch {
    pageState.value = "error";
  }
};

onMounted(() => loadStrategies());
</script>

<style scoped>
.strategy-list {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.section-block {
  margin-bottom: 24px;
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
