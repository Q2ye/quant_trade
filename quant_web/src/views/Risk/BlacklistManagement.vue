<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useStore } from "vuex";
import { NTag, NButton, NSwitch, NSpin, NResult, useMessage } from "naive-ui";

const store = useStore();
const message = useMessage();

const loading = ref(false);
const error = ref(false);
const searchKeyword = ref("");
const currentPage = ref(1);
const pageSize = ref(20);

// 只显示黑名单类规则
const blacklistRules = computed(() =>
  store.state.risk.riskRules.rules.filter((r: any) =>
    ["blacklist", "market_blacklist", "sector_blacklist"].includes(r.type),
  ),
);

const filteredList = computed(() => {
  if (!searchKeyword.value) return blacklistRules.value;
  const kw = searchKeyword.value.toLowerCase();
  return blacklistRules.value.filter(
    (item: any) =>
      (item.name || "").toLowerCase().includes(kw) ||
      (item.description || "").toLowerCase().includes(kw),
  );
});

const ruleTypeLabel: Record<string, string> = {
  blacklist: "股票黑名单",
  market_blacklist: "市场黑名单",
  sector_blacklist: "行业黑名单",
};

const columns = [
  {
    title: "规则名称",
    key: "name",
    width: 180,
  },
  {
    title: "黑名单类型",
    key: "type",
    width: 140,
    render: (row: any) =>
      h(
        NTag,
        { type: row.type === "blacklist" ? "error" : row.type === "market_blacklist" ? "warning" : "info", size: "small" },
        { default: () => ruleTypeLabel[row.type] || row.type },
      ),
  },
  {
    title: "规则描述",
    key: "description",
    minWidth: 300,
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

const fetchData = async () => {
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
    message.success(
      enabled ? `「${row.name}」已启用` : `「${row.name}」已禁用`,
    );
  } catch {
    message.error("操作失败，请重试");
    row.enabled = !enabled;
  }
};

const handleRefresh = async () => {
  await fetchData();
  message.success("刷新成功");
};

onMounted(() => fetchData());
</script>

<template>
  <div class="blacklist-management bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">黑名单管理</h1>
          <p class="page-subtitle">
            黑名单规则由风控引擎自动加载，用于拦截特定股票、市场或行业的交易信号。
            启用后，所有交易信号在执⾏前都会经过黑名单规则检查。
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
          <n-button type="primary" @click="fetchData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <!-- 黑名单规则卡片 -->
        <n-card class="main-card" style="margin-bottom: 16px">
          <template #header>
            <div class="card-header">
              <span>黑名单规则配置</span>
              <n-input
                v-model:value="searchKeyword"
                placeholder="搜索规则..."
                size="small"
                clearable
                style="width: 200px"
              />
            </div>
          </template>

          <n-spin :show="loading">
            <n-data-table
              :columns="columns"
              :data="filteredList"
              :bordered="false"
              size="small"
            >
              <template #empty>
                <n-empty description="暂无黑名单规则" />
              </template>
            </n-data-table>
            <div class="pagination-container">
              <n-pagination
                v-model:page="currentPage"
                v-model:page-size="pageSize"
                :item-count="filteredList.length"
                :page-sizes="[10, 20, 50]"
                show-size-picker
              />
            </div>
          </n-spin>
        </n-card>

        <!-- 说明卡片 -->
        <n-card class="info-card">
          <template #header>
            <span>黑名单机制说明</span>
          </template>
          <div class="info-content">
            <p><strong>股票黑名单</strong>：拦截特定股票代码（如 ST、*ST、退市整理期股票）的交易信号。</p>
            <p><strong>市场黑名单</strong>：拦截特定市场板块（如新三板、北交所精选层）的交易信号。</p>
            <p><strong>行业黑名单</strong>：拦截特定行业（如房地产、钢铁等高风险行业）的交易信号。</p>
            <p class="info-note">
              💡 提示：当前黑名单列表由风控规则代码定义。如需自定义黑名单股票列表，
              请编辑对应规则类中的 <code>_blacklist</code> 属性。后续版本将支持通过界面管理黑名单。
            </p>
          </div>
        </n-card>
      </template>
    </div>
  </div>
</template>

<style scoped>
.blacklist-management {
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

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.info-card {
  margin-bottom: 16px;
}

.info-content p {
  margin: 8px 0;
  font-size: 14px;
  color: var(--n-text-color-2, rgba(255, 255, 255, 0.64));
  line-height: 1.6;
}

.info-note {
  padding: 10px 14px;
  background: rgba(68, 138, 255, 0.08);
  border: 1px solid rgba(68, 138, 255, 0.15);
  border-radius: 6px;
  font-size: 13px !important;
}

.info-note code {
  padding: 1px 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  font-size: 12px;
}
</style>
