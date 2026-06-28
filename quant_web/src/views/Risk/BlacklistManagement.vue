<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useStore } from "vuex";
import { NTag, NButton, NSwitch, NSpin, NResult, NModal, NForm, NFormItem, NInput, NSelect, useMessage } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";

const store = useStore();
const message = useMessage();

const loading = ref(false);
const error = ref(false);
const searchKeyword = ref("");
const currentPage = ref(1);
const pageSize = ref(20);

// ---- 新增黑名单弹窗 ----
const showAddModal = ref(false);
const addForm = ref({ ts_code: "", target_name: "", list_type: "global", reason: "" });
const adding = ref(false);
const listTypeOptions = [
  { label: "全局", value: "global" },
  { label: "用户自定义", value: "user_specific" },
  { label: "系统", value: "system" },
];

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

// ---- 黑名单股票列表（来自 DB） ----
const blacklistStocks = computed(() => store.state.risk.blacklist.stocks || []);

const ruleTypeLabel: Record<string, string> = {
  blacklist: "股票黑名单",
  market_blacklist: "市场黑名单",
  sector_blacklist: "行业黑名单",
};

const ruleColumns = [
  { title: "规则名称", key: "name", minWidth: 160, ellipsis: { tooltip: true } },
  {
    title: "黑名单类型", key: "type", minWidth: 120,
    render: (row: any) =>
      h(NTag, { type: row.type === "blacklist" ? "error" : row.type === "market_blacklist" ? "warning" : "info", size: "small" },
        { default: () => ruleTypeLabel[row.type] || row.type }),
  },
  { title: "规则描述", key: "description", minWidth: 200, ellipsis: { tooltip: true } },
  {
    title: "状态", key: "enabled", width: 80,
    render: (row: any) =>
      h(NSwitch, { value: row.enabled, size: "small", onUpdateValue: (v: boolean) => handleToggle(row, v) }),
  },
];

const stockColumns = [
  { title: "股票代码", key: "symbol", minWidth: 120, ellipsis: { tooltip: true } },
  { title: "名称", key: "name", minWidth: 100, ellipsis: { tooltip: true } },
  {
    title: "黑名单类型", key: "listType", minWidth: 110,
    render: (row: any) =>
      h(NTag, { type: row.listType === "global" ? "error" : "info", size: "small" },
        { default: () => row.listType === "global" ? "全局" : row.listType === "user_specific" ? "自定义" : "系统" }),
  },
  { title: "原因", key: "reason", minWidth: 150, ellipsis: { tooltip: true } },
  { title: "加入日期", key: "addedDate", width: 110 },
  {
    title: "操作", key: "op", width: 80,
    render: (row: any) =>
      h(NButton, { size: "tiny", type: "error", quaternary: true, onClick: () => handleRemoveStock(row) },
        { default: () => "移除" }),
  },
];

const fetchData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await Promise.all([
      store.dispatch("risk/fetchRiskRules"),
      store.dispatch("risk/fetchBlacklist"),
    ]);
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleToggle = async (row: any, enabled: boolean) => {
  try {
    await store.dispatch("risk/toggleRiskRule", { ruleName: row.name, enabled });
    message.success(enabled ? `「${row.name}」已启用` : `「${row.name}」已禁用`);
  } catch {
    message.error("操作失败，请重试");
  }
};

const handleRefresh = async () => { await fetchData(); message.success("刷新成功"); };

// ---- 黑名单股票增删 ----
const handleAddStock = async () => {
  if (!addForm.value.ts_code) { message.warning("请输入股票代码"); return; }
  adding.value = true;
  try {
    await store.dispatch("risk/addToBlacklist", { ...addForm.value });
    message.success(`已添加 ${addForm.value.ts_code} 到黑名单`);
    showAddModal.value = false;
    addForm.value = { ts_code: "", target_name: "", list_type: "global", reason: "" };
  } catch {
    message.error("添加失败");
  } finally { adding.value = false; }
};

const handleRemoveStock = async (row: any) => {
  try {
    await store.dispatch("risk/removeFromBlacklist", row.id);
    message.success(`已移除 ${row.symbol}`);
  } catch { message.error("移除失败"); }
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
            管理黑名单规则配置和黑名单股票列表。加入黑名单的股票将被风控引擎拦截。
          </p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="handleRefresh" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result v-if="error" status="500" title="数据加载失败" description="请检查风控引擎是否正常启动后重试">
        <template #footer><n-button type="primary" @click="fetchData">重试</n-button></template>
      </n-result>

      <template v-else>
        <!-- 黑名单股票列表（新） -->
        <n-card class="main-card" style="margin-bottom: 16px">
          <template #header>
            <div class="card-header">
              <span>黑名单股票列表</span>
              <n-button size="small" type="primary" @click="showAddModal = true">+ 添加股票</n-button>
            </div>
          </template>
          <n-spin :show="loading">
            <n-data-table :columns="stockColumns" :data="blacklistStocks" :bordered="false" size="small">
              <template #empty><n-empty description="暂无黑名单股票，点击「添加股票」添加" /></template>
            </n-data-table>
          </n-spin>
        </n-card>

        <!-- 黑名单规则卡片 -->
        <n-card class="main-card" style="margin-bottom: 16px">
          <template #header>
            <div class="card-header">
              <span>黑名单规则配置</span>
              <n-input v-model:value="searchKeyword" placeholder="搜索规则..." size="small" clearable style="width: 200px" />
            </div>
          </template>
          <n-spin :show="loading">
            <n-data-table :columns="ruleColumns" :data="filteredList" :bordered="false" size="small">
              <template #empty><n-empty description="暂无黑名单规则" /></template>
            </n-data-table>
          </n-spin>
        </n-card>
      </template>
    </div>

    <!-- 添加黑名单弹窗 -->
    <n-modal v-model:show="showAddModal" preset="card" title="添加股票到黑名单" style="width: 420px" :mask-closable="false">
      <n-form :model="addForm" label-width="80px" size="small">
        <n-form-item label="股票代码" required>
          <n-input v-model:value="addForm.ts_code" placeholder="如 000001.SZ" />
        </n-form-item>
        <n-form-item label="股票名称">
          <n-input v-model:value="addForm.target_name" placeholder="如 平安银行（可选）" />
        </n-form-item>
        <n-form-item label="类型">
          <n-select v-model:value="addForm.list_type" :options="listTypeOptions" style="width: 160px" />
        </n-form-item>
        <n-form-item label="原因">
          <n-input v-model:value="addForm.reason" placeholder="如 ST 股票、财务风险等（可选）" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showAddModal = false">取消</n-button>
          <n-button type="primary" :loading="adding" @click="handleAddStock">确认添加</n-button>
        </n-space>
      </template>
    </n-modal>
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
