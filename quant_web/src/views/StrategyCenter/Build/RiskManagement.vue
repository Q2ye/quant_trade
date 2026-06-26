<template>
  <div class="risk-management bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">风险管理</h1>
          <p class="page-description">配置风险规则，监控警报记录</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <div class="risk-summary">
        <div
          class="summary-card critical"
          :class="tokens.motion.hover"
          @click="drillDownToAlerts('critical')"
        >
          <div class="summary-title">
            <SmartIcon name="AlertCircle" />
            严重警报
          </div>
          <div class="summary-value">{{ criticalAlerts.length }}</div>
          <div class="summary-sub">
            <span :class="criticalAlerts.length > 0 ? 'text-down' : ''">{{
              criticalAlerts.length > 0 ? "需关注" : "正常"
            }}</span>
          </div>
        </div>
        <div
          class="summary-card active"
          :class="tokens.motion.hover"
          @click="drillDownToAlerts('处理中')"
        >
          <div class="summary-title">
            <SmartIcon name="Warning" />
            活跃警报
          </div>
          <div class="summary-value">{{ activeAlerts.length }}</div>
          <div class="summary-sub">今日新增 {{ todayNewAlerts }}</div>
        </div>
        <div
          class="summary-card rules"
          :class="tokens.motion.hover"
          @click="drillDownToRules()"
        >
          <div class="summary-title">
            <SmartIcon name="ShieldCheckmark" />
            生效规则
          </div>
          <div class="summary-value">{{ enabledRulesCount }}</div>
          <div class="summary-sub">
            共 {{ accountRiskRules.length + strategyRiskRules.length }} 条规则
          </div>
        </div>
      </div>

      <template v-if="pageState === 'loading'">
        <div class="section-block">
          <n-card :class="tokens.surface.card">
            <n-skeleton :text="true" :repeat="10" />
          </n-card>
        </div>
      </template>

      <template v-else-if="pageState === 'error'">
        <div class="section-block">
          <n-result
            status="500"
            title="数据加载失败"
            description="请检查网络连接后重试"
          >
            <template #footer>
              <n-button type="primary" @click="loadData">重试</n-button>
            </template>
          </n-result>
        </div>
      </template>

      <template v-else>
        <div class="section-block">
          <n-tabs v-model:value="activeTab" type="line" class="risk-tabs">
            <!-- 规则配置 -->
            <n-tab-pane name="rules" tab="规则配置">
              <div class="rules-container">
                <n-radio-group
                  v-model:value="activeRuleType"
                  name="rule-type"
                  size="small"
                  class="rule-type-group"
                >
                  <n-radio-button value="account"
                    >账户级风险规则</n-radio-button
                  >
                  <n-radio-button value="strategy"
                    >策略级风险规则</n-radio-button
                  >
                </n-radio-group>

                <div class="filter-bar">
                  <div class="filter-row">
                    <n-input
                      v-model:value="ruleSearchKeyword"
                      placeholder="搜索规则名称或描述"
                      style="width: 220px"
                      clearable
                    >
                      <template #prefix><SmartIcon name="Search" /></template>
                    </n-input>
                    <n-select
                      v-model:value="ruleFilterType"
                      placeholder="规则类型"
                      style="width: 140px"
                      clearable
                      :options="ruleTypeFilterOptions"
                    />
                  </div>
                </div>

                <n-space
                  v-if="checkedRuleKeys.length > 0"
                  :size="8"
                  class="batch-actions"
                  :wrap="false"
                >
                  <span class="batch-hint"
                    >已选 {{ checkedRuleKeys.length }} 项</span
                  >
                  <n-button
                    size="small"
                    type="primary"
                    @click="batchEnable(true)"
                    >批量启用</n-button
                  >
                  <n-button size="small" @click="batchEnable(false)"
                    >批量禁用</n-button
                  >
                  <n-button size="small" type="error" @click="batchDeleteRules"
                    >批量删除</n-button
                  >
                  <n-button size="small" @click="checkedRuleKeys = []"
                    >取消选择</n-button
                  >
                </n-space>

                <div
                  v-show="!showNewRuleForm && activeRuleType === 'account'"
                  class="rule-section"
                >
                  <div class="section-header">
                    <h3>账户级风险规则</h3>
                    <n-button
                      type="primary"
                      size="small"
                      @click="openNewRule('account')"
                      >添加规则</n-button
                    >
                  </div>

                  <n-data-table
                    :columns="accountRuleColumns"
                    :data="filteredAccountRules"
                    :row-key="(row: RiskRule) => row.id"
                    :bordered="false"
                    size="small"
                  >
                    <template #empty
                      ><n-empty description="暂无账户级规则"
                    /></template>
                  </n-data-table>
                </div>

                <div
                  v-show="!showNewRuleForm && activeRuleType === 'strategy'"
                  class="rule-section"
                >
                  <div class="section-header">
                    <h3>策略级风险规则</h3>
                    <n-button
                      type="primary"
                      size="small"
                      @click="openNewRule('strategy')"
                      >添加规则</n-button
                    >
                  </div>

                  <n-data-table
                    :columns="strategyRuleColumns"
                    :data="filteredStrategyRules"
                    :row-key="(row: RiskRule) => row.id"
                    :bordered="false"
                    size="small"
                    :checked-row-keys="checkedRuleKeys"
                    @update:checked-row-keys="handleRuleCheck"
                  >
                    <template #empty
                      ><n-empty description="暂无策略级规则"
                    /></template>
                  </n-data-table>
                </div>

                <n-modal
                  v-model:show="showNewRuleForm"
                  preset="dialog"
                  :title="isEditing ? '编辑规则' : '添加新规则'"
                  positive-text="保存"
                  negative-text="取消"
                  @positive-click="saveRule"
                  @negative-click="resetRuleForm"
                >
                  <n-form :model="newRule" label-width="100px">
                    <n-form-item label="适用范围">
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

                    <n-form-item label="执行动作">
                      <n-select
                        v-model:value="newRule.action"
                        :options="actionOptions"
                      />
                    </n-form-item>

                    <n-form-item label="风险级别">
                      <n-select
                        v-model:value="newRule.severity"
                        :options="severityOptions"
                      />
                    </n-form-item>

                    <n-form-item label="规则类型">
                      <n-select
                        v-model:value="newRule.rule_type"
                        :options="ruleTypeFilterOptions"
                      />
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
                  </n-form>
                </n-modal>
              </div>
            </n-tab-pane>

            <!-- 警报记录 -->
            <n-tab-pane name="alerts" tab="警报记录">
              <div class="alerts-container">
                <div class="section-header">
                  <h3>警报记录列表</h3>
                </div>
                <div class="filter-row alerts-filter">
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
                </div>

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
        </div>
      </template>
    </div>

    <n-modal
      v-model:show="showResolutionModal"
      preset="dialog"
      title="处理风险警报"
      positive-text="确认处理"
      negative-text="取消"
      @positive-click="confirmResolveAlert"
      @negative-click="showResolutionModal = false"
    >
      <div class="resolution-content">
        <p class="resolution-alert-info">
          规则: <strong>{{ resolvingAlert?.rule }}</strong
          ><br />
          事件发生于: {{ resolvingAlert?.time }}
        </p>
        <n-form-item label="处理备注">
          <n-input
            v-model:value="resolutionNotes"
            type="textarea"
            placeholder="请输入处理说明或原因（可选）"
            :rows="4"
          />
        </n-form-item>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import { RiskLevel } from "@/types/common";
import wsService from "@/api/websocket";
import { useMessage, useDialog, NTag, NButton, NSwitch } from "naive-ui";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();
type PageState = "loading" | "error" | "data";
const pageState = ref<PageState>("loading");

const activeTab = ref("rules");
const activeRuleType = ref("account");
const showNewRuleForm = ref(false);
const isEditing = ref(false);
const editingRuleId = ref<number | null>(null);
const checkedRuleKeys = ref<number[]>([]);
const ruleSearchKeyword = ref("");
const ruleFilterType = ref("");

const getDefaultRule = (scope: "account" | "strategy") => ({
  type: scope,
  name: "",
  value: "",
  unit: "%",
  enabled: true,
  description: "",
  action: "alert" as "alert" | "soft_block" | "hard_block",
  severity: "medium" as RiskLevel,
  rule_type: "position_limit",
});

const openNewRule = (scope: "account" | "strategy") => {
  isEditing.value = false;
  editingRuleId.value = null;
  newRule.value = getDefaultRule(scope);
  showNewRuleForm.value = true;
};

const editRule = (rule: RiskRule) => {
  isEditing.value = true;
  editingRuleId.value = rule.id;
  const scope = accountRiskRules.value.some((r) => r.id === rule.id)
    ? "account"
    : "strategy";
  newRule.value = {
    type: scope,
    name: rule.name,
    value: String(rule.value),
    unit: rule.unit,
    enabled: rule.enabled,
    description: rule.description,
    action: rule.action,
    severity: rule.severity,
    rule_type: rule.rule_type,
  };
  showNewRuleForm.value = true;
};

const saveRule = () => {
  if (!newRule.value.name) {
    message.warning("请填写规则名称");
    return;
  }
  // 规则由风控引擎代码定义，通过 API 只能启用/禁用。
  // 新增/编辑规则需修改后端规则类后重启引擎。
  message.info("规则配置由风控引擎代码管理。启用/禁用可通过开关操作，新增规则请联系管理员。");
  showNewRuleForm.value = false;
  resetRuleForm();
};

const resetRuleForm = () => {
  showNewRuleForm.value = false;
};

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
  action: "alert" as "alert" | "soft_block" | "hard_block",
  severity: "medium" as RiskLevel,
  rule_type: "position_limit",
});

const unitOptions = ["%", "元", "次", "天", "手"].map((v) => ({
  label: v,
  value: v,
}));
const actionOptions = [
  { label: "仅告警", value: "alert" },
  { label: "软阻断（禁止新开仓）", value: "soft_block" },
  { label: "硬阻断（强制平仓）", value: "hard_block" },
];
const actionMap: Record<
  string,
  { label: string; type: "warning" | "error" | "info" }
> = {
  alert: { label: "仅告警", type: "info" },
  soft_block: { label: "软阻断", type: "warning" },
  hard_block: { label: "硬阻断", type: "error" },
};
const severityOptions = [
  { label: "低", value: RiskLevel.LOW },
  { label: "中", value: RiskLevel.MEDIUM },
  { label: "高", value: RiskLevel.HIGH },
  { label: "严重", value: RiskLevel.CRITICAL },
];
const levelOptions = [
  { label: "严重", value: "critical" },
  { label: "高", value: "high" },
  { label: "中", value: "medium" },
  { label: "低", value: "low" },
];
const ruleTypeFilterOptions = [
  { label: "仓位限制", value: "position_limit" },
  { label: "亏损限制", value: "daily_loss_limit" },
  { label: "回撤限制", value: "drawdown" },
  { label: "交易次数", value: "trade_count" },
  { label: "持仓天数", value: "holding_days" },
];

const filteredAccountRules = computed(() => {
  let result = accountRiskRules.value;
  if (ruleSearchKeyword.value) {
    const kw = ruleSearchKeyword.value.toLowerCase();
    result = result.filter(
      (r) =>
        r.name.toLowerCase().includes(kw) ||
        r.description.toLowerCase().includes(kw),
    );
  }
  if (ruleFilterType.value)
    result = result.filter((r) => r.rule_type === ruleFilterType.value);
  return result;
});

const filteredStrategyRules = computed(() => {
  let result = strategyRiskRules.value;
  if (ruleSearchKeyword.value) {
    const kw = ruleSearchKeyword.value.toLowerCase();
    result = result.filter(
      (r) =>
        r.name.toLowerCase().includes(kw) ||
        r.description.toLowerCase().includes(kw),
    );
  }
  if (ruleFilterType.value)
    result = result.filter((r) => r.rule_type === ruleFilterType.value);
  return result;
});

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
  /** 执行动作: alert=仅告警, soft_block=软阻断, hard_block=硬阻断 */
  action: "alert" | "soft_block" | "hard_block";
  /** 风险级别 */
  severity: RiskLevel;
  /** 规则类型: position_limit / daily_loss_limit / drawdown / trade_count / holding_days */
  rule_type: string;
  /** 触发条件 JSON */
  condition: Record<string, any>;
  created_at: string;
  updated_at: string;
}
interface AlertRecord {
  id: number;
  /** 触发规则名称 */
  rule: string;
  /** 关联规则 ID（用于追溯） */
  rule_id: string;
  time: string;
  level: string;
  account: string;
  value: number;
  status: string;
  /** 升级计数：同一规则连续触发次数 */
  escalation_count: number;
  /** 处理人 */
  resolved_by?: string;
  /** 处理时间 */
  resolved_at?: string;
  /** 处理备注 */
  resolution?: string;
}

const accountRiskRules = ref<RiskRule[]>([]);
const strategyRiskRules = ref<RiskRule[]>([]);
const alertRecords = ref<AlertRecord[]>([]);

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/strategy/build");
};

const loadData = async () => {
  pageState.value = "loading";
  try {
    await Promise.all([fetchRulesFromAPI(), fetchAlertsFromAPI()]);
    pageState.value = "data";
  } catch {
    pageState.value = "error";
  }
};

const fetchRulesFromAPI = async () => {
  try {
    const { default: riskAPI } = await import("@/api/risk");
    const result = await riskAPI.getRiskRules();
    const allRules = result.rules || [];

    // 分类：账户级规则（position/account 类型）vs 策略级规则（其他）
    const accountTypes = ["position_limit", "single_position_limit", "position_concentration",
      "account_balance", "loss_limit", "drawdown_limit", "capital_change"];
    const accountRules: RiskRule[] = [];
    const strategyRules: RiskRule[] = [];

    allRules.forEach((r: any, index: number) => {
      const mapped: RiskRule = {
        id: index + 1,
        name: r.name || r.rule_name || "",
        value: 0,
        unit: "",
        enabled: r.enabled ?? true,
        description: r.description || "",
        action: "alert",
        severity: RiskLevel.MEDIUM,
        rule_type: r.rule_type || "",
        condition: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      if (accountTypes.includes(r.rule_type || "")) {
        accountRules.push(mapped);
      } else {
        strategyRules.push(mapped);
      }
    });

    accountRiskRules.value = accountRules;
    strategyRiskRules.value = strategyRules;
  } catch (e) {
    console.error("获取风控规则失败:", e);
  }
};

const fetchAlertsFromAPI = async () => {
  try {
    const { default: riskAPI } = await import("@/api/risk");
    const result = await riskAPI.getRiskAlerts();
    const items = result.items || [];
    alertRecords.value = items.map((a: any, index: number) => ({
      id: index + 1,
      rule: a.title || a.alert_type || "未知规则",
      rule_id: a.id || String(index),
      time: a.created_at || new Date().toISOString(),
      level: a.level === "critical" ? "critical" : a.level === "warning" ? "high" : "medium",
      account: "主账户",
      value: 0,
      status: a.acknowledged ? "已处理" : "处理中",
      escalation_count: 0,
    }));
  } catch (e) {
    console.error("获取风险告警失败:", e);
  }
};

let wsChannel: string | null = null;
let wsCallback: ((data: any) => void) | null = null;

onMounted(() => {
  loadData();
  wsCallback = (data: any) => {
    const newAlert: AlertRecord = {
      id: Date.now(),
      rule: data.message || "实时预警",
      rule_id: data.alertId || "",
      time: new Date().toISOString().replace("T", " ").slice(0, 19),
      level: data.level || "medium",
      account: data.strategyId || "实时推送",
      value: 0,
      status: "处理中",
      escalation_count: 1,
    };
    alertRecords.value.unshift(newAlert);
  };
  wsChannel = wsService.subscribeRiskAlerts(wsCallback);
});

onBeforeUnmount(() => {
  if (wsChannel && wsCallback) wsService.unsubscribe(wsChannel, wsCallback);
});

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

const accountRuleColumns = [
  { title: "规则名称", key: "name", width: 140 },
  {
    title: "阈值",
    key: "value",
    width: 90,
    render: (row: RiskRule) =>
      h("span", { class: "rule-value" }, `${row.value}${row.unit}`),
  },
  {
    title: "执行动作",
    key: "action",
    width: 100,
    render: (row: RiskRule) =>
      h(
        NTag,
        { type: actionMap[row.action]?.type as any, size: "small" },
        { default: () => actionMap[row.action]?.label || row.action },
      ),
  },
  { title: "描述", key: "description", ellipsis: { tooltip: true } },
  {
    title: "状态",
    key: "enabled",
    width: 80,
    render: (row: RiskRule) =>
      h(NSwitch, {
        value: row.enabled,
        onUpdateValue: (v: boolean) => toggleRuleStatus(row, v),
      }),
  },
  {
    title: "操作",
    key: "op",
    width: 130,
    render: (row: RiskRule) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(
          NButton,
          { size: "tiny", onClick: () => editRule(row) },
          { default: () => "编辑" },
        ),
        h(
          NButton,
          { type: "error", size: "tiny", onClick: () => removeRule(row) },
          { default: () => "删除" },
        ),
      ]),
  },
];

const strategyRuleColumns = [
  { type: "selection" as const, width: 40 },
  ...accountRuleColumns,
];

const alertColumns = [
  {
    title: "级别",
    key: "level",
    width: 110,
    render: (row: AlertRecord) => {
      const children = [
        h(
          NTag,
          { type: levelTagMap[row.level] as any, size: "small" },
          { default: () => levelTextMap[row.level] },
        ),
      ];
      if (row.escalation_count > 1) {
        children.push(
          h(
            "span",
            {
              class: "escalation-badge",
              title: `已连续触发 ${row.escalation_count} 次`,
            },
            `x${row.escalation_count}`,
          ),
        );
      }
      return h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "6px" } },
        children,
      );
    },
  },
  { title: "规则", key: "rule", width: 140 },
  { title: "时间", key: "time", width: 170 },
  { title: "账户/策略", key: "account", width: 100 },
  {
    title: "实际值",
    key: "value",
    width: 90,
    render: (row: AlertRecord) =>
      h(
        "span",
        { class: row.value < 0 ? "text-down" : "text-up" },
        `${row.value > 0 ? "+" : ""}${row.value}${row.rule.includes("亏损") || row.rule.includes("回撤") ? "%" : ""}`,
      ),
  },
  {
    title: "状态",
    key: "status",
    width: 80,
    render: (row: AlertRecord) =>
      h(
        NTag,
        { type: statusTagMap[row.status] as any, size: "small" },
        { default: () => row.status },
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 220,
    render: (row: AlertRecord) => {
      const buttons: any[] = [];
      if (row.status === "处理中") {
        buttons.push(
          h(
            NButton,
            {
              type: "success",
              size: "tiny",
              onClick: () => resolveAlertWithNotes(row),
            },
            { default: () => "处理" },
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
        );
      } else {
        buttons.push(
          h(
            NButton,
            {
              type: "warning",
              size: "tiny",
              onClick: () => reopenAlert(row.id),
            },
            { default: () => "重新打开" },
          ),
        );
      }
      return h("div", { style: { display: "flex", gap: "4px" } }, buttons);
    },
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
const todayStr = new Date().toISOString().split("T")[0];
const todayNewAlerts = computed(
  () => alertRecords.value.filter((a) => a.time.startsWith(todayStr)).length,
);

const drillDownToAlerts = (filter: string) => {
  activeTab.value = "alerts";
  if (filter === "critical") {
    filterLevel.value = "critical";
    filterStatus.value = "";
  } else if (filter === "处理中") {
    filterStatus.value = "处理中";
    filterLevel.value = "";
  }
};

const drillDownToRules = () => {
  activeTab.value = "rules";
};

const enabledRulesCount = computed(
  () =>
    accountRiskRules.value.filter((r) => r.enabled).length +
    strategyRiskRules.value.filter((r) => r.enabled).length,
);

const removeRule = (rule: RiskRule) => {
  dialog.warning({
    title: "删除确认",
    content: `规则由风控引擎代码定义，不支持通过界面删除。「${rule.name}」可通过开关禁用。`,
    positiveText: "禁用它",
    negativeText: "取消",
    onPositiveClick: () => {
      rule.enabled = false;
      message.success(`「${rule.name}」已禁用`);
    },
  });
};

const batchEnable = async (enabled: boolean) => {
  const allRules = [...accountRiskRules.value, ...strategyRiskRules.value];
  const targets = allRules.filter((r) => checkedRuleKeys.value.includes(r.id));
  let success = 0;
  for (const r of targets) {
    try {
      const { default: riskAPI } = await import("@/api/risk");
      await riskAPI.toggleRiskRule(r.name, enabled);
      r.enabled = enabled;
      success++;
    } catch {
      // 跳过失败的
    }
  }
  message.success(
    `已${enabled ? "启用" : "禁用"} ${success}/${targets.length} 条规则`,
  );
  checkedRuleKeys.value = [];
};

const batchDeleteRules = () => {
  message.info("规则由风控引擎代码定义，不支持删除。可通过禁用规则来停用。");
  checkedRuleKeys.value = [];
};

const handleRuleCheck = (keys: number[]) => {
  checkedRuleKeys.value = keys;
};

const toggleRuleStatus = async (rule: RiskRule, v: boolean) => {
  try {
    const { default: riskAPI } = await import("@/api/risk");
    await riskAPI.toggleRiskRule(rule.name, v);
    rule.enabled = v;
    message.success(`「${rule.name}」已${v ? "启用" : "禁用"}`);
  } catch {
    message.error("操作失败，请重试");
  }
};
const showResolutionModal = ref(false);
const resolvingAlert = ref<AlertRecord | null>(null);
const resolutionNotes = ref("");

const resolveAlertWithNotes = (alert: AlertRecord) => {
  resolvingAlert.value = alert;
  resolutionNotes.value = "";
  showResolutionModal.value = true;
};

const confirmResolveAlert = () => {
  if (resolvingAlert.value) {
    resolvingAlert.value.status = "已处理";
    resolvingAlert.value.resolved_at = new Date().toISOString();
    resolvingAlert.value.resolution = resolutionNotes.value || undefined;
    resolvingAlert.value.resolved_by = "当前用户";
    message.success("警报已标记为已处理");
  }
  showResolutionModal.value = false;
  resolvingAlert.value = null;
};

const reopenAlert = (id: number) => {
  const a = alertRecords.value.find((aa) => aa.id === id);
  if (a) {
    a.status = "处理中";
    a.resolved_at = undefined;
    a.resolved_by = undefined;
    a.resolution = undefined;
    message.success("警报已重新打开");
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
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.section-block {
  margin-bottom: 24px;
}

.risk-summary {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
}

.summary-card {
  flex: 1;
  border-radius: 8px;
  padding: 15px;
  text-align: center;
  background: var(--n-card-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
}

@media (max-width: 768px) {
  .risk-summary {
    flex-direction: column;
    gap: 12px;
  }
}
.summary-card.critical {
  border-top: 4px solid var(--n-error-color, #d03050);
}
.summary-card.active {
  border-top: 4px solid var(--n-warning-color, #f0a020);
}
.summary-card.rules {
  border-top: 4px solid var(--n-success-color, #18a058);
}
.summary-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 14px;
  color: var(--n-text-color-3);
  margin-bottom: 10px;
}
.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--n-text-color-1);
}
.summary-sub {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-top: 8px;
}

.rules-container {
  padding: 20px;
}

.rule-type-group {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.filter-bar {
  margin-bottom: 12px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.batch-actions {
  padding: 8px 16px;
  margin-bottom: 12px;
  background: var(--n-color-embedded);
  border-radius: 6px;
  align-items: center;
}

.batch-hint {
  font-size: 13px;
  color: var(--n-text-color-2);
  font-weight: 500;
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
  color: var(--n-warning-color, #f0a020);
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
  gap: 12px;
}

.escalation-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 5px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 9px;
  background: var(--n-error-color-suppl, rgba(208, 48, 80, 0.15));
  color: var(--n-error-color, #d03050);
}

.resolution-content {
  padding: 8px 0;
}
.resolution-alert-info {
  font-size: 13px;
  color: var(--n-text-color-2);
  margin-bottom: 16px;
  line-height: 1.6;
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
