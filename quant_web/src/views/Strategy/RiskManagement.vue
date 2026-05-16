<template>
  <div class="risk-management bg-gradient-mesh bg-noise">
    <div class="risk-header">
      <h2>风险管理</h2>
      <div class="risk-summary">
        <div class="summary-card critical">
          <div class="summary-title">严重警报</div>
          <div class="summary-value">{{ criticalAlerts.length }}</div>
        </div>
        <div class="summary-card active">
          <div class="summary-title">活跃警报</div>
          <div class="summary-value">{{ activeAlerts.length }}</div>
        </div>
        <div class="summary-card rules">
          <div class="summary-title">生效规则</div>
          <div class="summary-value">{{ enabledRulesCount }}</div>
        </div>
      </div>
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
        <n-tabs v-model:value="activeTab" type="line" class="risk-tabs">
          <!-- 规则配置 -->
          <n-tab-pane name="rules" tab="规则配置">
            <div class="rules-container">
              <div class="rule-types">
                <div
                  :class="[
                    'rule-type',
                    { active: activeRuleType === 'account' },
                  ]"
                  @click="activeRuleType = 'account'"
                >
                  账户级风险规则
                </div>
                <div
                  :class="[
                    'rule-type',
                    { active: activeRuleType === 'strategy' },
                  ]"
                  @click="activeRuleType = 'strategy'"
                >
                  策略级风险规则
                </div>
              </div>

              <div v-show="activeRuleType === 'account'" class="rule-section">
                <div class="section-header">
                  <h3>账户级风险规则</h3>
                  <n-button
                    type="primary"
                    size="small"
                    @click="activeRuleType = 'new'"
                    >添加规则</n-button
                  >
                </div>

                <n-data-table
                  :columns="ruleColumns"
                  :data="accountRiskRules"
                  :bordered="false"
                  size="small"
                >
                  <template #empty
                    ><n-empty description="暂无账户级规则"
                  /></template>
                </n-data-table>
              </div>

              <div v-show="activeRuleType === 'strategy'" class="rule-section">
                <div class="section-header">
                  <h3>策略级风险规则</h3>
                  <n-button
                    type="primary"
                    size="small"
                    @click="activeRuleType = 'new'"
                    >添加规则</n-button
                  >
                </div>

                <n-data-table
                  :columns="ruleColumns"
                  :data="strategyRiskRules"
                  :bordered="false"
                  size="small"
                >
                  <template #empty
                    ><n-empty description="暂无策略级规则"
                  /></template>
                </n-data-table>
              </div>

              <div v-show="activeRuleType === 'new'" class="new-rule-section">
                <div class="section-header">
                  <h3>添加新规则</h3>
                  <n-button @click="activeRuleType = 'account'">返回</n-button>
                </div>

                <div class="rule-form">
                  <n-form :model="newRule" label-width="120px">
                    <n-form-item label="规则类型">
                      <n-radio-group v-model:value="newRule.type">
                        <n-radio value="account">账户级规则</n-radio>
                        <n-radio value="strategy">策略级规则</n-radio>
                      </n-radio-group>
                    </n-form-item>

                    <n-form-item label="规则名称" required>
                      <n-input
                        v-model:value="newRule.name"
                        placeholder="输入规则名称"
                      />
                    </n-form-item>

                    <n-form-item label="规则值" required>
                      <div class="value-input">
                        <n-input
                          v-model:value="newRule.value"
                          placeholder="输入阈值"
                        />
                        <n-select
                          v-model:value="newRule.unit"
                          style="width: 100px; margin-left: 10px"
                          :options="unitOptions"
                        />
                      </div>
                    </n-form-item>

                    <n-form-item label="规则描述">
                      <n-input
                        v-model:value="newRule.description"
                        type="textarea"
                        :rows="3"
                        placeholder="输入规则描述"
                      />
                    </n-form-item>

                    <n-form-item label="状态">
                      <n-switch v-model:value="newRule.enabled">
                        <template #checked>启用</template>
                        <template #unchecked>禁用</template>
                      </n-switch>
                    </n-form-item>

                    <n-form-item>
                      <n-button type="primary" @click="addRule"
                        >保存规则</n-button
                      >
                      <n-button class="ml-2" @click="activeRuleType = 'account'"
                        >取消</n-button
                      >
                    </n-form-item>
                  </n-form>
                </div>
              </div>
            </div>
          </n-tab-pane>

          <!-- 警报记录 -->
          <n-tab-pane name="alerts" tab="警报记录">
            <div class="alerts-container">
              <n-space :size="12" class="alerts-filter">
                <n-select
                  v-model:value="filterLevel"
                  placeholder="全部级别"
                  clearable
                  style="width: 140px"
                  :options="levelOptions"
                />
                <n-select
                  v-model:value="filterStatus"
                  placeholder="全部状态"
                  clearable
                  style="width: 140px"
                  :options="alertStatusOptions"
                />
                <n-date-picker
                  v-model:value="dateRange"
                  type="daterange"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                />
              </n-space>

              <n-data-table
                :columns="alertColumns"
                :data="filteredAlertRecords"
                :bordered="false"
                size="small"
              >
                <template #empty
                  ><n-empty description="暂无警报记录"
                /></template>
              </n-data-table>
            </div>
          </n-tab-pane>
        </n-tabs>
      </template>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted } from "vue";
import { useMessage, NTag, NButton, NSwitch, NSpin, NResult } from "naive-ui";

const message = useMessage();
const loading = ref(false);
const error = ref(false);

const activeTab = ref("rules");
const activeRuleType = ref("account");
const filterLevel = ref("");
const filterStatus = ref("");
const dateRange = ref<[number, number] | null>(null);

const newRule = ref({
  type: "account",
  name: "",
  value: "",
  unit: "%",
  enabled: true,
  description: "",
});

const unitOptions = ["%", "元", "次", "天", "手"].map((v) => ({
  label: v,
  value: v,
}));
const levelOptions = [
  { label: "严重", value: "critical" },
  { label: "高", value: "high" },
  { label: "中", value: "medium" },
  { label: "低", value: "low" },
];
const alertStatusOptions = [
  { label: "处理中", value: "处理中" },
  { label: "已处理", value: "已处理" },
  { label: "已忽略", value: "已忽略" },
];

interface RiskRule {
  id: number;
  name: string;
  value: number;
  unit: string;
  enabled: boolean;
  description: string;
}
interface AlertRecord {
  id: number;
  rule: string;
  time: string;
  level: string;
  account: string;
  value: number;
  status: string;
}

const accountRiskRules = ref<RiskRule[]>([]);
const strategyRiskRules = ref<RiskRule[]>([]);
const alertRecords = ref<AlertRecord[]>([]);

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    accountRiskRules.value = [
      {
        id: 1,
        name: "单日最大亏损",
        value: 5,
        unit: "%",
        enabled: true,
        description: "账户单日亏损达到该值时触发警报",
      },
      {
        id: 2,
        name: "最大回撤",
        value: 15,
        unit: "%",
        enabled: true,
        description: "账户净值从最高点回撤达到该值时触发警报",
      },
      {
        id: 3,
        name: "仓位上限",
        value: 80,
        unit: "%",
        enabled: true,
        description: "账户总持仓市值占总资产的比例上限",
      },
    ];
    strategyRiskRules.value = [
      {
        id: 1,
        name: "单股最大仓位",
        value: 20,
        unit: "%",
        enabled: true,
        description: "单个股票持仓市值占总资产的比例上限",
      },
      {
        id: 2,
        name: "单策略最大亏损",
        value: 10,
        unit: "%",
        enabled: true,
        description: "单个策略亏损达到该值时自动停止",
      },
      {
        id: 3,
        name: "单日最大交易次数",
        value: 5,
        unit: "次",
        enabled: true,
        description: "单个策略单日最大交易次数限制",
      },
      {
        id: 4,
        name: "最大持仓天数",
        value: 10,
        unit: "天",
        enabled: false,
        description: "单个股票最大持仓天数限制",
      },
    ];
    alertRecords.value = [
      {
        id: 1,
        rule: "单日最大亏损",
        time: "2023-08-10 14:30:25",
        level: "high",
        account: "主账户",
        value: -5.2,
        status: "已处理",
      },
      {
        id: 2,
        rule: "单股最大仓位",
        time: "2023-08-09 10:15:42",
        level: "medium",
        account: "策略A",
        value: 22.5,
        status: "处理中",
      },
      {
        id: 3,
        rule: "最大回撤",
        time: "2023-08-08 15:45:18",
        level: "high",
        account: "主账户",
        value: -16.8,
        status: "已忽略",
      },
      {
        id: 4,
        rule: "单策略最大亏损",
        time: "2023-08-07 11:20:33",
        level: "critical",
        account: "策略B",
        value: -12.3,
        status: "已处理",
      },
    ];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => loadData());

const levelTagMap: Record<string, string> = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "default",
};
const levelTextMap: Record<string, string> = {
  critical: "严重",
  high: "高",
  medium: "中",
  low: "低",
};
const statusTagMap: Record<string, string> = {
  已处理: "success",
  处理中: "warning",
  已忽略: "default",
};

const ruleColumns = [
  { title: "规则名称", key: "name", width: 180 },
  {
    title: "阈值",
    key: "value",
    render: (row: RiskRule) =>
      h("span", { class: "rule-value" }, `${row.value}${row.unit}`),
  },
  { title: "描述", key: "description" },
  {
    title: "状态",
    key: "enabled",
    width: 100,
    render: (row: RiskRule) =>
      h(NSwitch, {
        value: row.enabled,
        onUpdateValue: (v: boolean) => toggleRuleStatus(row, v),
      }),
  },
  {
    title: "操作",
    key: "op",
    width: 120,
    render: (row: RiskRule) =>
      h(
        NButton,
        { type: "error", size: "tiny", onClick: () => removeRule(row.id) },
        { default: () => "删除" },
      ),
  },
];

const alertColumns = [
  {
    title: "级别",
    key: "level",
    width: 100,
    render: (row: AlertRecord) =>
      h(
        NTag,
        { type: levelTagMap[row.level] as any },
        { default: () => levelTextMap[row.level] },
      ),
  },
  { title: "规则", key: "rule", width: 150 },
  { title: "时间", key: "time", width: 180 },
  { title: "账户/策略", key: "account", width: 120 },
  {
    title: "实际值",
    key: "value",
    render: (row: AlertRecord) =>
      h(
        "span",
        { class: row.value < 0 ? "negative-value" : "positive-value" },
        `${row.value > 0 ? "+" : ""}${row.value}${row.rule.includes("亏损") || row.rule.includes("回撤") ? "%" : ""}`,
      ),
  },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row: AlertRecord) =>
      h(
        NTag,
        { type: statusTagMap[row.status] as any },
        { default: () => row.status },
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 200,
    render: (row: AlertRecord) =>
      h(
        "div",
        { style: { display: "flex", gap: "8px" } },
        row.status === "处理中"
          ? [
              h(
                NButton,
                {
                  type: "success",
                  size: "tiny",
                  onClick: () => resolveAlert(row.id),
                },
                { default: () => "标记为已处理" },
              ),
              h(
                NButton,
                {
                  type: "default",
                  size: "tiny",
                  onClick: () => ignoreAlert(row.id),
                },
                { default: () => "忽略" },
              ),
            ]
          : [],
      ),
  },
];

const filteredAlertRecords = computed(() => {
  let result = alertRecords.value;
  if (filterLevel.value)
    result = result.filter((a) => a.level === filterLevel.value);
  if (filterStatus.value)
    result = result.filter((a) => a.status === filterStatus.value);
  return result;
});

const criticalAlerts = computed(() =>
  alertRecords.value.filter((a) => a.level === "critical"),
);
const activeAlerts = computed(() =>
  alertRecords.value.filter((a) => a.status === "处理中"),
);
const enabledRulesCount = computed(
  () =>
    accountRiskRules.value.filter((r) => r.enabled).length +
    strategyRiskRules.value.filter((r) => r.enabled).length,
);

const addRule = () => {
  if (!newRule.value.name || !newRule.value.value) {
    message.warning("请填写规则名称和值");
    return;
  }
  const rule = {
    id: Date.now(),
    name: newRule.value.name,
    value: parseFloat(newRule.value.value),
    unit: newRule.value.unit,
    enabled: newRule.value.enabled,
    description: newRule.value.description,
  };
  if (newRule.value.type === "account") accountRiskRules.value.push(rule);
  else strategyRiskRules.value.push(rule);
  message.success("规则添加成功");
  newRule.value = {
    type: "account",
    name: "",
    value: "",
    unit: "%",
    enabled: true,
    description: "",
  };
};

const removeRule = (ruleId: number) => {
  accountRiskRules.value = accountRiskRules.value.filter(
    (r) => r.id !== ruleId,
  );
  strategyRiskRules.value = strategyRiskRules.value.filter(
    (r) => r.id !== ruleId,
  );
  message.info("规则已删除");
};

const toggleRuleStatus = (rule: RiskRule, v: boolean) => {
  rule.enabled = v;
  message.success(`${rule.name}规则已${v ? "启用" : "禁用"}`);
};
const resolveAlert = (id: number) => {
  const a = alertRecords.value.find((aa) => aa.id === id);
  if (a) {
    a.status = "已处理";
    message.success("警报已标记为已处理");
  }
};
const ignoreAlert = (id: number) => {
  const a = alertRecords.value.find((aa) => aa.id === id);
  if (a) {
    a.status = "已忽略";
    message.info("警报已忽略");
  }
};
</script>

<style scoped>
.risk-management {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.risk-header {
  margin-bottom: 25px;
}
.risk-header h2 {
  margin: 0 0 15px;
  color: var(--n-text-color-1);
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}

.risk-summary {
  display: flex;
  gap: 20px;
  margin-top: 20px;
}

.summary-card {
  flex: 1;
  border-radius: 8px;
  padding: 15px;
  text-align: center;
  background: var(--n-card-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
.summary-card.critical {
  border-top: 4px solid #f44336;
}
.summary-card.active {
  border-top: 4px solid #ff9800;
}
.summary-card.rules {
  border-top: 4px solid #4caf50;
}
.summary-title {
  font-size: 14px;
  color: var(--n-text-color-3);
  margin-bottom: 10px;
}
.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--n-text-color-1);
}

.rules-container {
  padding: 20px;
}

.rule-types {
  display: flex;
  margin-bottom: 20px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--n-color-embedded);
}
.rule-type {
  flex: 1;
  text-align: center;
  padding: 12px;
  cursor: pointer;
  transition: background 0.3s;
  color: var(--n-text-color-2);
}
.rule-type.active {
  background: var(--n-color-target);
  color: var(--n-color-target-text);
  font-weight: bold;
}
.rule-type:hover:not(.active) {
  background: var(--n-color-hover);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.section-header h3 {
  margin: 0;
  color: var(--n-text-color-1);
}

.rule-section,
.new-rule-section {
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  background: var(--n-color-embedded);
}

.rule-value {
  font-weight: bold;
  color: #ff9800;
}

.new-rule-section {
  animation: fadeIn 0.3s ease;
}

.rule-form {
  max-width: 700px;
  margin: 0 auto;
}
.value-input {
  display: flex;
}

.alerts-container {
  padding: 20px;
}
.alerts-filter {
  margin-bottom: 20px;
}

.positive-value {
  color: #f44336;
  font-weight: bold;
}
.negative-value {
  color: #4caf50;
  font-weight: bold;
}

.ml-2 {
  margin-left: 8px;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
