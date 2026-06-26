<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useStore } from "vuex";
import { NTag, NSwitch, NButton, NSpin, NResult, useMessage } from "naive-ui";

const store = useStore();
const message = useMessage();

const loading = ref(false);
const error = ref(false);
const searchKeyword = ref("");
const filterRuleType = ref("");
const currentPage = ref(1);
const pageSize = ref(20);

// 14 种规则类型的中文映射（与后端 RiskEngine._classify_rule 对齐）
const ruleTypeMap: Record<string, string> = {
  // 仓位规则
  position_limit: "总仓位限制",
  single_position_limit: "单只仓位限制",
  position_concentration: "仓位集中度",
  // 账户规则
  account_balance: "账户余额",
  loss_limit: "亏损限制",
  drawdown_limit: "回撤限制",
  capital_change: "资金变化",
  // 黑名单规则
  blacklist: "黑名单",
  market_blacklist: "市场黑名单",
  sector_blacklist: "行业黑名单",
  // 市场规则
  liquidity: "流动性",
  price: "价格限制",
  volatility: "波动率",
  market_status: "市场状态",
};
const ruleTypeOptions = Object.entries(ruleTypeMap).map(([value, label]) => ({
  label,
  value,
}));

const rules = computed(() => store.state.risk.riskRules.rules);

const filteredRules = computed(() => {
  let result = rules.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter(
      (r: any) =>
        (r.name || "").toLowerCase().includes(kw) ||
        (r.description || "").toLowerCase().includes(kw),
    );
  }
  if (filterRuleType.value) {
    result = result.filter((r: any) => r.type === filterRuleType.value);
  }
  return result;
});

const columns = [
  { title: "规则名称", key: "name", width: 180 },
  {
    title: "规则类型",
    key: "type",
    width: 140,
    render: (row: any) =>
      h(
        NTag,
        { size: "small" },
        { default: () => ruleTypeMap[row.type] || row.type },
      ),
  },
  {
    title: "规则描述",
    key: "description",
    minWidth: 220,
    ellipsis: { tooltip: true },
  },
  {
    title: "状态",
    key: "enabled",
    width: 90,
    render: (row: any) =>
      h(NSwitch, {
        value: row.enabled,
        size: "small",
        onUpdateValue: (v: boolean) => handleToggle(row, v),
      }),
  },
];

const fetchRules = async () => {
  loading.value = true;
  error.value = false;
  try {
    await store.dispatch("risk/fetchRiskRules");
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleToggle = async (row: any, enabled: boolean) => {
  try {
    await store.dispatch("risk/toggleRiskRule", {
      ruleName: row.name,
      enabled,
    });
    message.success(enabled ? `「${row.name}」已启用` : `「${row.name}」已禁用`);
  } catch {
    message.error("操作失败，请重试");
    // 回滚 UI
    row.enabled = !enabled;
  }
};

const handleRefresh = async () => {
  await fetchRules();
  message.success("刷新成功");
};

onMounted(() => fetchRules());
</script>

<template>
  <div class="risk-rules bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">风控规则配置</h1>
          <p class="page-subtitle">
            当前共 {{ rules.length }} 条规则，由风控引擎自动加载。
            规则启停即时生效，修改后自动参与信号检查和定时巡检。
          </p>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="handleRefresh" :loading="loading">
            刷新
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查风控引擎是否正常启动后重试"
      >
        <template #footer>
          <n-button type="primary" @click="fetchRules">重试</n-button>
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
                  placeholder="搜索规则名称或描述..."
                  size="small"
                  clearable
                  style="width: 200px"
                />
                <n-select
                  v-model:value="filterRuleType"
                  placeholder="规则类型"
                  size="small"
                  clearable
                  style="width: 140px"
                  :options="ruleTypeOptions"
                />
              </div>
            </div>
          </template>

          <n-spin :show="loading">
            <n-data-table
              :columns="columns"
              :data="filteredRules"
              :bordered="false"
              size="small"
            >
              <template #empty>
                <n-empty description="暂无风控规则，请检查风控引擎是否正常启动" />
              </template>
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
  </div>
</template>

<style scoped>
.risk-rules {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
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

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
