<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useStore } from "vuex";
import {
  NTag, NSwitch, NButton, NSpin, NResult,
  NInputNumber, NInput, NDrawer, NDrawerContent, NDivider,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";

const store = useStore();
const message = useMessage();

const loading = ref(false);
const error = ref(false);
const searchKeyword = ref("");
const filterRuleType = ref("");
const currentPage = ref(1);
const pageSize = ref(20);
const drawerVisible = ref(false);
const selectedRule = ref<any>(null);
const editingParams = ref<Record<string, any>>({});
const saving = ref(false);

const ruleTypeMap: Record<string, string> = {
  position_limit: "总仓位限制", single_position_limit: "单只仓位限制",
  position_concentration: "仓位集中度", sector_concentration: "行业集中度",
  stock_stop_loss: "个股止损", account_balance: "账户余额",
  loss_limit: "亏损限制", drawdown_limit: "回撤限制",
  capital_change: "资金变化", trade_count: "日交易次数",
  blacklist: "黑名单", market_blacklist: "市场黑名单",
  sector_blacklist: "行业黑名单", liquidity: "流动性",
  price: "价格限制", volatility: "波动率",
  market_status: "市场状态", limit_up_down: "涨跌停检查",
  suspension: "停牌检查",
};
const actionMap: Record<string, { label: string; type: "warning" | "error" | "info" }> = {
  alert: { label: "报警", type: "warning" },
  stop_strategy: { label: "停止策略", type: "error" },
  cancel_orders: { label: "撤单", type: "info" },
};
const inputLabels: Record<string, string> = {
  total_asset: "总资产", position_value: "持仓市值", trade_amount: "交易金额",
  available_cash: "可用资金", initial_capital: "初始资金", peak_asset: "峰值资产",
  previous_asset: "前日资产", positions: "持仓列表", ts_code: "股票代码",
  market: "市场", sector: "行业", liquidity: "流动性",
  close: "收盘价", high: "最高价", low: "最低价",
  volatility: "波动率", market_status: "市场状态",
  pre_close: "昨收价", direction: "买卖方向", is_st: "ST标志",
  cost_price: "成本价", current_price: "现价", volume: "成交量",
  suspended: "停牌标志", daily_trade_count: "日交易次数",
};
const paramLabels: Record<string, string> = {
  max_position_ratio: "最大仓位比例", max_single_position_ratio: "单只最大仓位比例",
  max_top_n_ratio: "最大 Top-N 比例", top_n: "Top N 只",
  max_loss_percent: "最大亏损比例", max_drawdown_percent: "最大回撤比例",
  max_daily_change_percent: "最大日变化比例", max_daily_trades: "日最大交易次数",
  max_sector_ratio: "最大行业比例", min_liquidity: "最低流动性",
  min_price: "最低价格", max_price: "最高价格", max_volatility: "最大波动率",
};

const ruleTypeOptions = Object.entries(ruleTypeMap).map(([value, label]) => ({ label, value }));
const rules = computed(() => store.state.risk.riskRules.rules);

const filteredRules = computed(() => {
  let result = rules.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter((r: any) =>
      (r.name || "").toLowerCase().includes(kw) ||
      (r.description || "").toLowerCase().includes(kw)
    );
  }
  if (filterRuleType.value)
    result = result.filter((r: any) => r.type === filterRuleType.value);
  return result;
});

const columns = [
  { title: "规则名称", key: "name", width: 170 },
  {
    title: "分类", key: "type", width: 130,
    render: (row: any) => h(NTag, { size: "small" }, { default: () => ruleTypeMap[row.type] || row.type }),
  },
  {
    title: "触发动作", key: "action", width: 110,
    render: (row: any) => {
      const a = actionMap[row.action] || { label: row.action, type: "info" as const };
      return h(NTag, { type: a.type, size: "small" }, { default: () => a.label });
    },
  },
  {
    title: "规则描述", key: "description", minWidth: 250, ellipsis: { tooltip: true },
  },
  {
    title: "状态", key: "enabled", width: 80,
    render: (row: any) =>
      h(NSwitch, {
        value: row.enabled, size: "small",
        onUpdateValue: (v: boolean) => handleToggle(row, v),
      }),
  },
  {
    title: "", key: "op", width: 60,
    render: (row: any) =>
      h(NButton, {
        size: "small", quaternary: true,
        onClick: () => openDrawer(row),
      }, { default: () => "详情" }),
  },
];

const fetchRules = async () => {
  loading.value = true; error.value = false;
  try { await store.dispatch("risk/fetchRiskRules"); }
  catch { error.value = true; }
  finally { loading.value = false; }
};

const handleToggle = async (row: any, enabled: boolean) => {
  try {
    await store.dispatch("risk/toggleRiskRule", { ruleName: row.name, enabled });
    message.success(enabled ? `「${row.name}」已启用` : `「${row.name}」已禁用`);
  } catch { message.error("操作失败"); row.enabled = !enabled; }
};

const openDrawer = (row: any) => {
  selectedRule.value = row;
  editingParams.value = { ...(row.params || {}) };
  drawerVisible.value = true;
};

const closeDrawer = () => {
  drawerVisible.value = false;
  selectedRule.value = null;
  editingParams.value = {};
};

const saveParams = async () => {
  if (!selectedRule.value) return;
  saving.value = true;
  try {
    await store.dispatch("risk/toggleRiskRule", {
      ruleName: selectedRule.value.name, params: editingParams.value,
    });
    message.success("参数已保存，即时生效");
    closeDrawer();
  } catch { message.error("保存失败"); }
  finally { saving.value = false; }
};

const handleRefresh = async () => { await fetchRules(); message.success("刷新成功"); };
const formatP = (key: string) => paramLabels[key] || key;
const formatI = (key: string) => inputLabels[key] || key;

onMounted(() => fetchRules());
</script>

<template>
  <div class="risk-rules bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">风控规则配置</h1>
          <p class="page-subtitle">共 {{ rules.length }} 条规则。点击「详情」查看/修改参数，开关即时生效。</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="handleRefresh" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result v-if="error" status="500" title="数据加载失败"
        description="请检查风控引擎是否正常启动后重试">
        <template #footer><n-button type="primary" @click="fetchRules">重试</n-button></template>
      </n-result>

      <template v-else>
        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>风控规则列表</span>
              <div class="header-controls">
                <n-input v-model:value="searchKeyword" placeholder="搜索规则..." size="small" clearable style="width: 180px" />
                <n-select v-model:value="filterRuleType" placeholder="分类筛选" size="small" clearable style="width: 130px" :options="ruleTypeOptions" />
              </div>
            </div>
          </template>

          <n-spin :show="loading">
            <n-data-table :columns="columns" :data="filteredRules" :bordered="false" size="small">
              <template #empty><n-empty description="暂无风控规则" /></template>
            </n-data-table>

            <div class="pagination-container">
              <n-pagination v-model:page="currentPage" v-model:page-size="pageSize"
                :item-count="filteredRules.length" :page-sizes="[10, 20, 50]" show-size-picker />
            </div>
          </n-spin>
        </n-card>
      </template>
    </div>

    <!-- 右侧抽屉 -->
    <n-drawer v-model:show="drawerVisible" :width="480" placement="right"
      :style="{ '--n-color': 'var(--color-bg-primary, #10141c)' }"
    >
      <n-drawer-content v-if="selectedRule" :title="selectedRule.name" closable>
        <!-- 基本信息 -->
        <div class="drawer-section">
          <div class="drawer-label">分类</div>
          <n-tag size="small">{{ ruleTypeMap[selectedRule.type] || selectedRule.type }}</n-tag>
        </div>
        <div class="drawer-section">
          <div class="drawer-label">触发动作</div>
          <n-tag :type="(actionMap[selectedRule.action] || {}).type || 'info'" size="small">
            {{ (actionMap[selectedRule.action] || {}).label || selectedRule.action }}
          </n-tag>
        </div>
        <div class="drawer-section">
          <div class="drawer-label">规则描述</div>
          <p class="drawer-text">{{ selectedRule.description }}</p>
        </div>

        <n-divider />

        <!-- 可配置参数 -->
        <h4 class="drawer-heading">可配置参数</h4>
        <div v-if="Object.keys(editingParams).length === 0" class="drawer-empty">
          此规则无配置参数
        </div>
        <div v-else class="drawer-params">
          <div v-for="(val, key) in editingParams" :key="key" class="drawer-param-row">
            <label class="drawer-param-label">{{ formatP(String(key)) }}</label>
            <n-input-number
              v-if="typeof val === 'number'"
              v-model:value="editingParams[String(key)]"
              size="small" style="width: 170px"
              :step="val < 10 && val > 0 ? 0.01 : 1" :min="0"
            />
            <n-input v-else v-model:value="editingParams[String(key)]" size="small" style="width: 170px" />
          </div>
        </div>

        <n-divider />

        <!-- 所需输入 -->
        <h4 class="drawer-heading">检查所需输入字段</h4>
        <div v-if="!selectedRule.inputs || selectedRule.inputs.length === 0" class="drawer-empty">
          无特定输入
        </div>
        <div v-else class="drawer-tags">
          <n-tag v-for="inp in selectedRule.inputs" :key="inp" size="small" type="info"
            style="margin: 2px 4px 2px 0">
            {{ formatI(inp) }}
          </n-tag>
        </div>

        <template #footer>
          <div class="drawer-footer">
            <n-button type="primary" @click="saveParams" :loading="saving">保存参数</n-button>
            <n-button @click="closeDrawer">取消</n-button>
          </div>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.risk-rules { padding: 0; height: 100%; overflow-y: auto; }
.page-subtitle { margin: 4px 0 0; font-size: 13px; color: var(--n-text-color-3, rgba(255,255,255,0.48)); }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-controls { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.pagination-container { margin-top: 16px; display: flex; justify-content: flex-end; }

.drawer-section { margin-bottom: 12px; }
.drawer-label { font-size: 12px; color: var(--n-text-color-3, rgba(255,255,255,0.48)); margin-bottom: 4px; }
.drawer-text { font-size: 13px; color: var(--n-text-color-2, rgba(255,255,255,0.64)); margin: 0; line-height: 1.6; }
.drawer-heading { font-size: 14px; font-weight: 600; margin: 0 0 10px 0; }
.drawer-empty { font-size: 13px; color: var(--n-text-color-3, rgba(255,255,255,0.36)); padding: 4px 0; }

.drawer-params { display: flex; flex-direction: column; gap: 10px; }
.drawer-param-row { display: flex; align-items: center; gap: 10px; }
.drawer-param-label { font-size: 13px; color: var(--n-text-color-2, rgba(255,255,255,0.64)); min-width: 110px; flex-shrink: 0; }
.drawer-tags { padding: 4px 0; }
.drawer-footer { display: flex; gap: 8px; justify-content: flex-end; }
</style>
