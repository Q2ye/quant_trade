<script setup lang="ts">
import { ref, onMounted, h } from "vue";
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
        { type: row.is_active ? "error" : "default" },
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
          onClick: () => removeFromBlacklist(row),
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

const handleAdd = () => {
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
      name: `股票${newItem.value.ts_code}`,
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

const removeFromBlacklist = async (item: BlacklistItem) => {
  try {
    blacklist.value = blacklist.value.filter((i) => i.id !== item.id);
    message.success("移除成功");
  } catch {
    message.error("移除失败");
  }
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
    <div class="management-header">
      <h3>黑名单管理</h3>
      <n-space :size="8">
        <n-button type="primary" @click="handleAdd">添加黑名单</n-button>
        <n-button @click="handleImport">导入</n-button>
        <n-button @click="exportBlacklist">导出</n-button>
      </n-space>
    </div>

    <n-spin :show="loading">
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
        <n-data-table
          :columns="columns"
          :data="blacklist"
          :bordered="false"
          size="small"
        >
          <template #empty><n-empty description="暂无黑名单记录" /></template>
        </n-data-table>
      </template>
    </n-spin>

    <!-- 添加黑名单对话框 -->
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
        <n-form-item label="原因">
          <n-select v-model:value="newItem.reason" :options="reasonOptions" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<style scoped>
.blacklist-management {
  padding: 20px;
}

.management-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}

.management-header h3 {
  margin: 0;
  color: var(--n-text-color-1);
}
</style>
