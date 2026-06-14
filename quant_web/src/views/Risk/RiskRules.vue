<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import {
  useMessage,
  useDialog,
  NTag,
  NButton,
  NSwitch,
  NSpin,
  NResult,
} from "naive-ui";

const message = useMessage();
const dialog = useDialog();
const loading = ref(false);
const error = ref(false);

interface RiskRule {
  id: number;
  rule_name: string;
  rule_type: string;
  condition: any;
  action: string;
  is_active: boolean;
  created_at: string;
}

const rules = ref<RiskRule[]>([]);
const showModal = ref(false);
const editingRule = ref<RiskRule | null>(null);
const ruleForm = ref({
  rule_name: "",
  rule_type: "position_limit",
  condition: {},
  action: "alert",
  is_active: true,
});
const conditionEntries = ref<{ key: string; value: string }[]>([]);
const searchKeyword = ref("");
const filterRuleType = ref("");
const checkedRuleKeys = ref<number[]>([]);
const currentPage = ref(1);
const pageSize = ref(20);

const ruleTypeMap: Record<string, string> = {
  position_limit: "持仓限制",
  daily_loss_limit: "单日亏损限制",
  blacklist: "黑名单",
  volatility_limit: "波动率限制",
};
const ruleTypeOptions = Object.entries(ruleTypeMap).map(([value, label]) => ({
  label,
  value,
}));
const actionOptions = [
  { label: "报警", value: "alert" },
  { label: "停止策略", value: "stop_strategy" },
  { label: "撤单", value: "cancel_orders" },
];
const actionMap: Record<
  string,
  { label: string; type: "warning" | "error" | "info" }
> = {
  alert: { label: "报警", type: "warning" },
  stop_strategy: { label: "停止策略", type: "error" },
  cancel_orders: { label: "撤单", type: "info" },
};

const filteredRules = computed(() => {
  let result = rules.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter((r) => r.rule_name.toLowerCase().includes(kw));
  }
  if (filterRuleType.value) {
    result = result.filter((r) => r.rule_type === filterRuleType.value);
  }
  return result;
});

const columns = [
  {
    type: "selection",
    width: 40,
  },
  { title: "规则名称", key: "rule_name", width: 180 },
  {
    title: "规则类型",
    key: "rule_type",
    width: 140,
    render: (row: RiskRule) =>
      h(
        NTag,
        { size: "small" },
        { default: () => ruleTypeMap[row.rule_type] || row.rule_type },
      ),
  },
  {
    title: "规则条件",
    key: "condition",
    minWidth: 200,
    render: (row: RiskRule) => JSON.stringify(row.condition),
  },
  {
    title: "触发动作",
    key: "action",
    width: 120,
    render: (row: RiskRule) =>
      h(
        NTag,
        { type: actionMap[row.action]?.type || "info", size: "small" },
        { default: () => actionMap[row.action]?.label || row.action },
      ),
  },
  {
    title: "状态",
    key: "is_active",
    width: 90,
    render: (row: RiskRule) =>
      h(NSwitch, {
        value: row.is_active,
        size: "small",
        onUpdateValue: (v: boolean) => {
          row.is_active = v;
          message.success(v ? "规则已启用" : "规则已禁用");
        },
      }),
  },
  { title: "创建时间", key: "created_at", width: 110 },
  {
    title: "操作",
    key: "op",
    width: 150,
    render: (row: RiskRule) =>
      h("div", { style: { display: "flex", gap: "8px" } }, [
        h(
          NButton,
          { size: "small", onClick: () => editRule(row) },
          { default: () => "编辑" },
        ),
        h(
          NButton,
          { size: "small", type: "error", onClick: () => confirmDelete(row) },
          { default: () => "删除" },
        ),
      ]),
  },
];

const fetchRiskRules = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    rules.value = [
      {
        id: 1,
        rule_name: "单股仓位限制",
        rule_type: "position_limit",
        condition: { max_position_ratio: 0.2 },
        action: "alert",
        is_active: true,
        created_at: "2024-01-01",
      },
      {
        id: 2,
        rule_name: "单日亏损限制",
        rule_type: "daily_loss_limit",
        condition: { max_daily_loss: -0.05 },
        action: "stop_strategy",
        is_active: true,
        created_at: "2024-01-02",
      },
      {
        id: 3,
        rule_name: "ST股票黑名单",
        rule_type: "blacklist",
        condition: { blacklist_types: ["st_risk", "financial_risk"] },
        action: "cancel_orders",
        is_active: false,
        created_at: "2024-01-03",
      },
    ];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  ruleForm.value = {
    rule_name: "",
    rule_type: "position_limit",
    condition: {},
    action: "alert",
    is_active: true,
  };
  conditionEntries.value = [];
};

const handleAdd = () => {
  editingRule.value = null;
  resetForm();
  showModal.value = true;
};

const editRule = (rule: RiskRule) => {
  editingRule.value = rule;
  ruleForm.value = { ...rule };
  conditionEntries.value = Object.entries(rule.condition || {}).map(
    ([k, v]) => ({
      key: k,
      value: typeof v === "string" ? v : JSON.stringify(v),
    }),
  );
  showModal.value = true;
};

const buildCondition = (): Record<string, any> => {
  const cond: Record<string, any> = {};
  for (const entry of conditionEntries.value) {
    if (!entry.key.trim()) continue;
    const v = entry.value.trim();
    // try parse as number
    const num = Number(v);
    cond[entry.key.trim()] = isNaN(num) ? v : num;
  }
  return cond;
};

const addConditionEntry = () => {
  conditionEntries.value.push({ key: "", value: "" });
};

const removeConditionEntry = (index: number) => {
  conditionEntries.value.splice(index, 1);
};

const saveRule = async () => {
  if (!ruleForm.value.rule_name.trim()) {
    message.warning("请输入规则名称");
    return;
  }
  try {
    const condition = buildCondition();
    if (editingRule.value) {
      Object.assign(editingRule.value, { ...ruleForm.value, condition });
      message.success("规则已更新");
    } else {
      rules.value.push({
        id: Date.now(),
        ...ruleForm.value,
        condition,
        created_at: new Date().toISOString().split("T")[0],
      });
      message.success("规则已创建");
    }
    showModal.value = false;
  } catch {
    message.error("保存失败");
  }
};

const confirmDelete = (row: RiskRule) => {
  dialog.warning({
    title: "确认删除",
    content: `确定要删除规则「${row.rule_name}」吗？此操作不可撤销。`,
    positiveText: "确认",
    negativeText: "取消",
    onPositiveClick: () => {
      rules.value = rules.value.filter((r) => r.id !== row.id);
      message.success("规则已删除");
    },
  });
};

const batchEnable = () => {
  rules.value
    .filter((r) => checkedRuleKeys.value.includes(r.id))
    .forEach((r) => (r.is_active = true));
  message.success("批量启用完成");
  checkedRuleKeys.value = [];
};

const batchDisable = () => {
  rules.value
    .filter((r) => checkedRuleKeys.value.includes(r.id))
    .forEach((r) => (r.is_active = false));
  message.success("批量禁用完成");
  checkedRuleKeys.value = [];
};

const batchDelete = () => {
  if (checkedRuleKeys.value.length === 0) return;
  dialog.warning({
    title: "批量删除",
    content: `确定要删除选中的 ${checkedRuleKeys.value.length} 条规则吗？此操作不可撤销。`,
    positiveText: "确认",
    negativeText: "取消",
    onPositiveClick: () => {
      rules.value = rules.value.filter(
        (r) => !checkedRuleKeys.value.includes(r.id),
      );
      checkedRuleKeys.value = [];
      message.success("批量删除完成");
    },
  });
};

onMounted(() => fetchRiskRules());
</script>

<template>
  <div class="risk-rules bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">风控规则配置</h1>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="handleAdd">添加规则</n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="fetchRiskRules">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>风控规则列表</span>
              <div class="header-controls">
                <n-input
                  v-model:value="searchKeyword"
                  placeholder="搜索规则名称..."
                  size="small"
                  clearable
                  style="width: 180px"
                />
                <n-select
                  v-model:value="filterRuleType"
                  placeholder="规则类型"
                  size="small"
                  clearable
                  style="width: 130px"
                  :options="ruleTypeOptions"
                />
              </div>
            </div>
          </template>

          <div v-if="checkedRuleKeys.length > 0" class="batch-bar">
            <span class="batch-text">已选 {{ checkedRuleKeys.length }} 项</span>
            <n-button size="small" @click="batchEnable">批量启用</n-button>
            <n-button size="small" @click="batchDisable">批量禁用</n-button>
            <n-button size="small" type="error" @click="batchDelete"
              >批量删除</n-button
            >
          </div>

          <n-spin :show="loading">
            <n-data-table
              :columns="columns"
              :data="filteredRules"
              :bordered="false"
              size="small"
              :checked-row-keys="checkedRuleKeys"
              @update:checked-row-keys="
                (keys: number[]) => (checkedRuleKeys = keys)
              "
            >
              <template #empty><n-empty description="暂无风控规则" /></template>
            </n-data-table>

            <div class="pagination-container">
              <n-pagination
                v-model:page="currentPage"
                v-model:page-size="pageSize"
                :item-count="filteredRules.length"
                :page-sizes="[10, 20, 50]"
                show-size-picker
              />
            </div>
          </n-spin>
        </n-card>
      </template>
    </div>

    <n-modal
      v-model:show="showModal"
      preset="dialog"
      :title="editingRule ? '编辑规则' : '添加规则'"
      positive-text="保存"
      negative-text="取消"
      @positive-click="saveRule"
    >
      <n-form :model="ruleForm" label-width="80px">
        <n-form-item label="规则名称">
          <n-input
            v-model:value="ruleForm.rule_name"
            placeholder="请输入规则名称"
          />
        </n-form-item>
        <n-form-item label="规则类型">
          <n-select
            v-model:value="ruleForm.rule_type"
            :options="ruleTypeOptions"
          />
        </n-form-item>
        <n-form-item label="规则条件">
          <div class="condition-editor">
            <div
              v-for="(entry, idx) in conditionEntries"
              :key="idx"
              class="condition-row"
            >
              <n-input
                v-model:value="entry.key"
                placeholder="参数名"
                size="small"
                style="width: 140px"
              />
              <n-input
                v-model:value="entry.value"
                placeholder="参数值"
                size="small"
                style="width: 160px"
              />
              <n-button
                size="small"
                type="error"
                text
                @click="removeConditionEntry(idx)"
              >
                删除
              </n-button>
            </div>
            <n-button size="small" dashed @click="addConditionEntry">
              添加条件
            </n-button>
          </div>
        </n-form-item>
        <n-form-item label="触发动作">
          <n-select v-model:value="ruleForm.action" :options="actionOptions" />
        </n-form-item>
        <n-form-item label="启用状态">
          <n-switch v-model:value="ruleForm.is_active" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<style scoped>
.risk-rules {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: rgba(68, 138, 255, 0.08);
  border: 1px solid rgba(68, 138, 255, 0.15);
  border-radius: 6px;
}

.batch-text {
  font-size: 13px;
  color: var(--n-text-color-2, rgba(255, 255, 255, 0.64));
  margin-right: 8px;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.condition-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.condition-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
