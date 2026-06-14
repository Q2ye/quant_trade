<script setup lang="ts">
import { ref, computed, watch, onMounted, h } from "vue";
import { useMessage, useDialog, NTag, NButton, NSpin, NResult } from "naive-ui";

const message = useMessage();
const dialog = useDialog();
const loading = ref(false);
const error = ref(false);

interface BlacklistItem {
  id: number;
  ts_code: string;
  name: string;
  reason: string;
  added_by: string;
  added_at: string;
  is_active: boolean;
}

const blacklist = ref<BlacklistItem[]>([]);
const showModal = ref(false);
const newItem = ref({ ts_code: "", reason: "st_risk" });
const resolvedName = ref("");
const resolvingName = ref(false);

// 本地股票名称 lookup（mock，生产环境应调用后端 API）
const stockNameMap: Record<string, string> = {
  "600000.SH": "浦发银行",
  "600036.SH": "招商银行",
  "600519.SH": "贵州茅台",
  "600086.SH": "退市金钰",
  "000001.SZ": "平安银行",
  "000858.SZ": "五粮液",
  "000979.SZ": "中弘退",
  "002594.SZ": "比亚迪",
  "300750.SZ": "宁德时代",
  "601318.SH": "中国平安",
};
const searchKeyword = ref("");
const currentPage = ref(1);
const pageSize = ref(20);

const reasonMap: Record<string, string> = {
  st_risk: "ST风险",
  financial_risk: "财务风险",
  regulatory_risk: "监管风险",
  manual_add: "手动添加",
};
const reasonOptions = Object.entries(reasonMap).map(([value, label]) => ({
  label,
  value,
}));

const filteredList = computed(() => {
  if (!searchKeyword.value) return blacklist.value;
  const kw = searchKeyword.value.toLowerCase();
  return blacklist.value.filter(
    (item) =>
      item.ts_code.toLowerCase().includes(kw) ||
      item.name.toLowerCase().includes(kw) ||
      (reasonMap[item.reason] || "").includes(kw),
  );
});

const columns = [
  { title: "股票代码", key: "ts_code", width: 120 },
  { title: "股票名称", key: "name", width: 150 },
  {
    title: "原因",
    key: "reason",
    width: 120,
    render: (row: BlacklistItem) => reasonMap[row.reason] || row.reason,
  },
  { title: "添加人", key: "added_by", width: 100 },
  { title: "添加时间", key: "added_at", width: 120 },
  {
    title: "状态",
    key: "is_active",
    width: 100,
    render: (row: BlacklistItem) =>
      h(
        NTag,
        { type: row.is_active ? "error" : "default", size: "small" },
        { default: () => (row.is_active ? "生效中" : "已失效") },
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 80,
    render: (row: BlacklistItem) =>
      h(
        NButton,
        {
          size: "small",
          type: "error",
          onClick: () => confirmRemove(row),
        },
        { default: () => "移除" },
      ),
  },
];

const fetchBlacklist = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    blacklist.value = [
      {
        id: 1,
        ts_code: "600086.SH",
        name: "退市金钰",
        reason: "st_risk",
        added_by: "system",
        added_at: "2024-01-01",
        is_active: true,
      },
      {
        id: 2,
        ts_code: "000979.SZ",
        name: "中弘退",
        reason: "regulatory_risk",
        added_by: "admin",
        added_at: "2024-01-02",
        is_active: true,
      },
    ];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

// 根据股票代码自动查询名称
watch(
  () => newItem.value.ts_code,
  async (code) => {
    if (!code || code.length < 9) {
      resolvedName.value = "";
      return;
    }
    resolvingName.value = true;
    // 模拟异步查询延迟
    await new Promise((r) => setTimeout(r, 200));
    resolvedName.value = stockNameMap[code] || "";
    resolvingName.value = false;
  },
);

const handleAdd = () => {
  resolvedName.value = "";
  newItem.value = { ts_code: "", reason: "st_risk" };
  showModal.value = true;
};

const addToBlacklist = async () => {
  if (!newItem.value.ts_code) {
    message.warning("请输入股票代码");
    return;
  }
  try {
    blacklist.value.push({
      id: Date.now(),
      ts_code: newItem.value.ts_code,
      name: resolvedName.value || `股票${newItem.value.ts_code}`,
      reason: newItem.value.reason,
      added_by: "current_user",
      added_at: new Date().toISOString().split("T")[0],
      is_active: true,
    });
    showModal.value = false;
    newItem.value = { ts_code: "", reason: "st_risk" };
    message.success("添加成功");
  } catch {
    message.error("添加失败");
  }
};

const confirmRemove = (item: BlacklistItem) => {
  dialog.warning({
    title: "确认移除",
    content: `确定要将 ${item.name}(${item.ts_code}) 从黑名单中移除吗？`,
    positiveText: "确认",
    negativeText: "取消",
    onPositiveClick: () => {
      blacklist.value = blacklist.value.filter((i) => i.id !== item.id);
      message.success("移除成功");
    },
  });
};

const handleImport = () => message.info("导入功能开发中");

const exportBlacklist = () => {
  const csvContent = blacklist.value
    .map(
      (item) =>
        `${item.ts_code},${item.name},${reasonMap[item.reason]},${item.added_at}`,
    )
    .join("\n");
  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `blacklist_${new Date().toISOString().split("T")[0]}.csv`;
  a.click();
  window.URL.revokeObjectURL(url);
};

onMounted(() => fetchBlacklist());
</script>

<template>
  <div class="blacklist-management bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">黑名单管理</h1>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="handleAdd">添加黑名单</n-button>
          <n-button @click="handleImport">导入</n-button>
          <n-button @click="exportBlacklist">导出</n-button>
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
          <n-button type="primary" @click="fetchBlacklist">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>黑名单列表</span>
              <n-input
                v-model:value="searchKeyword"
                placeholder="搜索代码/名称..."
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
              <template #empty
                ><n-empty description="暂无黑名单记录"
              /></template>
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
      </template>
    </div>

    <n-modal
      v-model:show="showModal"
      preset="dialog"
      title="添加黑名单"
      positive-text="确认添加"
      negative-text="取消"
      @positive-click="addToBlacklist"
    >
      <n-form :model="newItem" label-width="80px">
        <n-form-item label="股票代码">
          <n-input
            v-model:value="newItem.ts_code"
            placeholder="例如：600000.SH"
          />
        </n-form-item>
        <n-form-item v-if="resolvedName || resolvingName" label="股票名称">
          <n-spin :show="resolvingName" size="small">
            <span class="resolved-name">{{
              resolvedName || "未匹配到名称"
            }}</span>
          </n-spin>
        </n-form-item>
        <n-form-item label="原因">
          <n-select v-model:value="newItem.reason" :options="reasonOptions" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<style scoped>
.blacklist-management {
  padding: 0;
  height: 100%;
  overflow-y: auto;
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

.resolved-name {
  font-size: 14px;
  color: var(--n-text-color-2, rgba(255, 255, 255, 0.64));
}
</style>
