<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { useMessage, NTag, NButton, NSwitch, NSpin, NResult } from "naive-ui";

const message = useMessage();
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

const columns = [
  { title: "规则名称", key: "rule_name", width: 200 },
  {
    title: "规则类型",
    key: "rule_type",
    width: 150,
    render: (row: RiskRule) =>
      h(
        NTag,
        {},
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
        { type: actionMap[row.action]?.type || "info" },
        { default: () => actionMap[row.action]?.label || row.action },
      ),
  },
  {
    title: "状态",
    key: "is_active",
    width: 100,
    render: (row: RiskRule) =>
      h(NSwitch, {
        value: row.is_active,
        onUpdateValue: (v: boolean) => {
          row.is_active = v;
        },
      }),
  },
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
          { size: "small", type: "error", onClick: () => deleteRule(row.id) },
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
};

const handleAdd = () => {
  editingRule.value = null;
  resetForm();
  showModal.value = true;
};

const editRule = (rule: RiskRule) => {
  editingRule.value = rule;
  ruleForm.value = { ...rule };
  showModal.value = true;
};

const saveRule = async () => {
  try {
    if (editingRule.value) {
      Object.assign(editingRule.value, ruleForm.value);
      message.success("规则已更新");
    } else {
      rules.value.push({
        id: Date.now(),
        ...ruleForm.value,
        condition: {},
        created_at: new Date().toISOString().split("T")[0],
      });
      message.success("规则已创建");
    }
    showModal.value = false;
  } catch {
    message.error("保存失败");
  }
};

const deleteRule = (id: number) => {
  rules.value = rules.value.filter((r) => r.id !== id);
  message.success("规则已删除");
};

onMounted(() => fetchRiskRules());
</script>

<template>
  <div class="risk-rules bg-gradient-mesh bg-noise">
    <div class="page-header">
      <h3>风控规则配置</h3>
      <n-button type="primary" @click="handleAdd">添加规则</n-button>
    </div>

    <n-spin :show="loading">
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
        <n-data-table
          :columns="columns"
          :data="rules"
          :bordered="false"
          size="small"
        >
          <template #empty><n-empty description="暂无风控规则" /></template>
        </n-data-table>
      </template>
    </n-spin>

    <n-modal
      v-model:show="showModal"
      preset="dialog"
      :title="editingRule ? '编辑规则' : '添加规则'"
      positive-text="保存"
      negative-text="取消"
      @positive-click="saveRule"
    >
      <n-form :model="ruleForm" label-width="100px">
        <n-form-item label="规则名称">
          <n-input v-model:value="ruleForm.rule_name" />
        </n-form-item>
        <n-form-item label="规则类型">
          <n-select
            v-model:value="ruleForm.rule_type"
            :options="ruleTypeOptions"
          />
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
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}

.page-header h3 {
  margin: 0;
  color: var(--n-text-color-1);
}
</style>
