<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { useMessage, NTag, NButton, NSwitch, NSpin, NResult } from "naive-ui";

const message = useMessage();
const loading = ref(false);
const error = ref(false);

interface User {
  id: number;
  username: string;
  email: string;
  phone: string;
  real_name: string;
  role: string;
  is_active: boolean;
  last_login: string;
  created_at: string;
}

const users = ref<User[]>([]);
const showModal = ref(false);
const editingUser = ref<User | null>(null);
const userForm = ref({
  username: "",
  email: "",
  phone: "",
  real_name: "",
  role: "user",
  is_active: true,
});

const roleOptions = [
  { label: "普通用户", value: "user" },
  { label: "管理员", value: "admin" },
];

const columns = [
  { title: "用户名", key: "username", width: 120 },
  { title: "真实姓名", key: "real_name", width: 100 },
  { title: "邮箱", key: "email", width: 200 },
  { title: "手机号", key: "phone", width: 120 },
  {
    title: "角色",
    key: "role",
    width: 100,
    render: (row: User) =>
      h(
        NTag,
        { type: row.role === "admin" ? "error" : "info" },
        { default: () => (row.role === "admin" ? "管理员" : "普通用户") },
      ),
  },
  {
    title: "状态",
    key: "is_active",
    width: 80,
    render: (row: User) =>
      h(
        NTag,
        { type: row.is_active ? "success" : "default" },
        { default: () => (row.is_active ? "激活" : "禁用") },
      ),
  },
  { title: "最后登录", key: "last_login", width: 180 },
  {
    title: "操作",
    key: "op",
    width: 200,
    render: (row: User) =>
      h("div", { style: { display: "flex", gap: "8px" } }, [
        h(
          NButton,
          { size: "small", onClick: () => editUser(row) },
          { default: () => "编辑" },
        ),
        h(
          NButton,
          { size: "small", onClick: () => resetPassword(row) },
          { default: () => "重置密码" },
        ),
        h(
          NButton,
          { size: "small", type: "error", onClick: () => deleteUser(row.id) },
          { default: () => "删除" },
        ),
      ]),
  },
];

const fetchUsers = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
    users.value = [
      {
        id: 1,
        username: "admin",
        email: "admin@quant.com",
        phone: "13800138000",
        real_name: "管理员",
        role: "admin",
        is_active: true,
        last_login: "2024-01-15 14:30:00",
        created_at: "2024-01-01",
      },
      {
        id: 2,
        username: "trader01",
        email: "trader@quant.com",
        phone: "13900139000",
        real_name: "交易员张",
        role: "user",
        is_active: true,
        last_login: "2024-01-15 10:20:00",
        created_at: "2024-01-05",
      },
    ];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  userForm.value = {
    username: "",
    email: "",
    phone: "",
    real_name: "",
    role: "user",
    is_active: true,
  };
};

const handleAdd = () => {
  editingUser.value = null;
  resetForm();
  showModal.value = true;
};

const editUser = (user: User) => {
  editingUser.value = user;
  userForm.value = { ...user };
  showModal.value = true;
};

const saveUser = async () => {
  try {
    if (editingUser.value) {
      Object.assign(editingUser.value, userForm.value);
      message.success("用户已更新");
    } else {
      users.value.push({
        id: Date.now(),
        ...userForm.value,
        last_login: "-",
        created_at: new Date().toISOString().split("T")[0],
      });
      message.success("用户已创建");
    }
    showModal.value = false;
  } catch {
    message.error("保存失败");
  }
};

const resetPassword = (row: User) =>
  message.info(`重置 ${row.username} 的密码`);
const deleteUser = (id: number) => {
  users.value = users.value.filter((u) => u.id !== id);
  message.success("用户已删除");
};

onMounted(() => fetchUsers());
</script>

<template>
  <div class="user-management bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">用户管理</h1>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="handleAdd">添加用户</n-button>
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
          <n-button type="primary" @click="fetchUsers">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-data-table
          :columns="columns"
          :data="users"
          :bordered="false"
          size="small"
        >
          <template #empty><n-empty description="暂无用户" /></template>
        </n-data-table>
      </template>
    </n-spin>

    <n-modal
      v-model:show="showModal"
      preset="dialog"
      :title="editingUser ? '编辑用户' : '添加用户'"
      positive-text="保存"
      negative-text="取消"
      @positive-click="saveUser"
    >
      <n-form :model="userForm" label-width="80px">
        <n-form-item label="用户名">
          <n-input v-model:value="userForm.username" />
        </n-form-item>
        <n-form-item label="真实姓名">
          <n-input v-model:value="userForm.real_name" />
        </n-form-item>
        <n-form-item label="邮箱">
          <n-input v-model:value="userForm.email" />
        </n-form-item>
        <n-form-item label="手机号">
          <n-input v-model:value="userForm.phone" />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="userForm.role" :options="roleOptions" />
        </n-form-item>
        <n-form-item label="状态">
          <n-switch v-model:value="userForm.is_active" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<style scoped>
.user-management {
  padding: 20px;
}

/* .page-header 已迁移至全局样式（global.scss） */
</style>
