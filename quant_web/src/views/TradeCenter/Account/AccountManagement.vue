<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { useMessage, NTag, NButton, NSpin, NResult } from "naive-ui";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
interface Account {
  id: number;
  account_name: string;
  broker: string;
  account_number: string;
  total_asset: number;
  available_cash: number;
  market_value: number;
  status: string;
  created_at: string;
}

const accounts = ref<Account[]>([]);
const dialogVisible = ref(false);
const editingAccount = ref<Account | null>(null);
const accountForm = ref({
  account_name: "",
  broker: "ht",
  account_number: "",
  status: "active",
});

const brokerMap: Record<string, string> = {
  ht: "华泰证券",
  gf: "广发证券",
  zs: "招商证券",
  zx: "中信证券",
};
const brokerOptions = Object.entries(brokerMap).map(([v, l]) => ({
  label: l,
  value: v,
}));
const statusOpts = [
  { label: "活跃", value: "active" },
  { label: "禁用", value: "inactive" },
];

const columns = [
  { title: "账户名称", key: "account_name", width: 150 },
  {
    title: "券商",
    key: "broker",
    width: 120,
    render: (row: Account) => brokerMap[row.broker] || row.broker,
  },
  { title: "账户号码", key: "account_number", width: 150 },
  {
    title: "总资产",
    key: "total_asset",
    width: 120,
    render: (row: Account) => `¥${row.total_asset.toLocaleString()}`,
  },
  {
    title: "可用资金",
    key: "available_cash",
    width: 120,
    render: (row: Account) => `¥${row.available_cash.toLocaleString()}`,
  },
  {
    title: "持仓市值",
    key: "market_value",
    width: 120,
    render: (row: Account) => `¥${row.market_value.toLocaleString()}`,
  },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row: Account) =>
      h(
        NTag,
        { type: row.status === "active" ? "success" : "default" },
        { default: () => (row.status === "active" ? "活跃" : "禁用") },
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 200,
    render: (row: Account) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(
          NButton,
          { size: "small", onClick: () => editAccount(row) },
          { default: () => "编辑" },
        ),
        h(
          NButton,
          { size: "small", onClick: () => syncAccount(row) },
          { default: () => "同步" },
        ),
        h(
          NButton,
          {
            size: "small",
            type: "error",
            onClick: () => deleteAccount(row.id),
          },
          { default: () => "删除" },
        ),
      ]),
  },
];

const fetchAccounts = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    accounts.value = [
      {
        id: 1,
        account_name: "主交易账户",
        broker: "ht",
        account_number: "1234567890",
        total_asset: 1500000,
        available_cash: 500000,
        market_value: 1000000,
        status: "active",
        created_at: "2024-01-01",
      },
      {
        id: 2,
        account_name: "测试账户",
        broker: "gf",
        account_number: "0987654321",
        total_asset: 100000,
        available_cash: 100000,
        market_value: 0,
        status: "active",
        created_at: "2024-01-02",
      },
    ];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const saveAccount = async () => {
  if (editingAccount.value) {
    const idx = accounts.value.findIndex(
      (a) => a.id === editingAccount.value!.id,
    );
    if (idx !== -1)
      accounts.value[idx] = { ...editingAccount.value, ...accountForm.value };
  } else {
    accounts.value.push({
      id: Date.now(),
      ...accountForm.value,
      total_asset: 0,
      available_cash: 0,
      market_value: 0,
      created_at: new Date().toISOString().split("T")[0],
    });
  }
  dialogVisible.value = false;
  message.success("账户保存成功");
};

const editAccount = (account: Account) => {
  editingAccount.value = account;
  accountForm.value = { ...account };
  dialogVisible.value = true;
};

const deleteAccount = (id: number) => {
  accounts.value = accounts.value.filter((a) => a.id !== id);
  message.success("账户删除成功");
};

const syncAccount = (account: Account) =>
  message.info(`正在同步 ${account.account_name} 的账户信息...`);

const handleAdd = () => {
  editingAccount.value = null;
  accountForm.value = {
    account_name: "",
    broker: "ht",
    account_number: "",
    status: "active",
  };
  dialogVisible.value = true;
};

onMounted(() => fetchAccounts());
</script>

<template>
  <div class="account-management bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">账户管理</h1>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="handleAdd">新增账户</n-button>
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
          <n-button type="primary" @click="fetchAccounts">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-data-table
          :columns="columns"
          :data="accounts"
          :bordered="false"
          size="small"
        >
          <template #empty><n-empty description="暂无账户" /></template>
        </n-data-table>
      </template>
    </n-spin>

    <n-modal
      v-model:show="dialogVisible"
      preset="dialog"
      :title="editingAccount ? '编辑账户' : '新增账户'"
      positive-text="保存"
      negative-text="取消"
      @positive-click="saveAccount"
    >
      <n-form :model="accountForm" label-width="100px">
        <n-form-item label="账户名称">
          <n-input v-model:value="accountForm.account_name" />
        </n-form-item>
        <n-form-item label="券商">
          <n-select
            v-model:value="accountForm.broker"
            :options="brokerOptions"
          />
        </n-form-item>
        <n-form-item label="账户号码">
          <n-input v-model:value="accountForm.account_number" />
        </n-form-item>
        <n-form-item label="状态">
          <n-select v-model:value="accountForm.status" :options="statusOpts" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<style scoped>
.account-management {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}
</style>
