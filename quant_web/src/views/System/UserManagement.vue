<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue"
import {
  useMessage,
  useDialog,
  NTag,
  NButton,
  NSwitch,
  NSpin,
  NResult,
} from "naive-ui"
import { tokens } from "@/styles/design-tokens"
import systemAPI from "@/api/system"

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const error = ref(false)
const saving = ref(false)

interface User {
  id: string
  username: string
  email: string
  phone: string
  real_name: string
  role: string
  is_active: boolean
  last_login: string
  created_at: string
}

const users = ref<User[]>([])
const showModal = ref(false)
const editingUser = ref<User | null>(null)
const userForm = ref({
  username: "",
  password: "",
  email: "",
  phone: "",
  real_name: "",
  role: "user",
  is_active: true,
})
const searchKeyword = ref("")
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const roleOptions = [
  { label: "普通用户", value: "user" },
  { label: "管理员", value: "admin" },
  { label: "超级管理员", value: "super_admin" },
]

const filteredUsers = computed(() => {
  if (!searchKeyword.value) return users.value
  const kw = searchKeyword.value.toLowerCase()
  return users.value.filter(
    (u) =>
      u.username.toLowerCase().includes(kw) ||
      (u.real_name || "").toLowerCase().includes(kw) ||
      (u.email || "").toLowerCase().includes(kw),
  )
})

const resetForm = () => {
  userForm.value = {
    username: "",
    password: "",
    email: "",
    phone: "",
    real_name: "",
    role: "user",
    is_active: true,
  }
}

const fetchUsers = async () => {
  loading.value = true
  error.value = false
  try {
    const res = await systemAPI.getUsers({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      keyword: searchKeyword.value,
    })
    // 处理后端响应包装
    const raw = res.data?.items || res.data?.users || res.users || res.data || []
    users.value = Array.isArray(raw) ? raw.map((u: any) => ({
      id: u.id || "",
      username: u.username || "",
      email: u.email || "",
      phone: u.phone || "",
      real_name: u.real_name || "",
      role: u.role || "user",
      is_active: u.is_active !== false,
      last_login: u.last_login || "-",
      created_at: u.created_at || "-",
    })) : []
    total.value = res.data?.total || res.total || users.value.length
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchUsers()
}

const handleAdd = () => {
  editingUser.value = null
  resetForm()
  showModal.value = true
}

const editUser = (user: User) => {
  editingUser.value = user
  userForm.value = {
    username: user.username,
    password: "",
    email: user.email || "",
    phone: user.phone || "",
    real_name: user.real_name || "",
    role: user.role || "user",
    is_active: user.is_active,
  }
  showModal.value = true
}

const saveUser = async () => {
  saving.value = true
  try {
    if (editingUser.value) {
      await systemAPI.updateUser(editingUser.value.id, {
        email: userForm.value.email,
        phone: userForm.value.phone,
        real_name: userForm.value.real_name,
        role: userForm.value.role,
        is_active: userForm.value.is_active,
      })
      message.success("用户已更新")
    } else {
      await systemAPI.createUser({
        username: userForm.value.username,
        password: userForm.value.password,
        email: userForm.value.email,
        phone: userForm.value.phone,
        real_name: userForm.value.real_name,
        role: userForm.value.role,
      })
      message.success("用户已创建")
    }
    showModal.value = false
    await fetchUsers()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "操作失败")
  } finally {
    saving.value = false
  }
}

const resetPassword = async (row: User) => {
  dialog.warning({
    title: "重置密码",
    content: `确定要重置「${row.username}」的密码吗？`,
    positiveText: "确认",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        // TODO: 调用后端重置密码接口
        message.info("密码重置功能开发中（需 SMTP 配置）")
      } catch {
        message.error("重置失败")
      }
    },
  })
}

const confirmDelete = (row: User) => {
  dialog.warning({
    title: "确认删除",
    content: `确定要删除用户「${row.username}」吗？此操作不可撤销。`,
    positiveText: "确认删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await systemAPI.deleteUser(row.id)
        message.success("用户已删除")
        await fetchUsers()
      } catch (e: any) {
        message.error(e?.response?.data?.detail || "删除失败")
      }
    },
  })
}

const columns = [
  { title: "用户名", key: "username", width: 120 },
  { title: "姓名", key: "real_name", width: 100 },
  { title: "邮箱", key: "email", width: 180 },
  { title: "手机号", key: "phone", width: 130 },
  {
    title: "角色", key: "role", width: 100,
    render(row: User) {
      return h(NTag, { type: row.role === "admin" || row.role === "super_admin" ? "error" : "info", size: "small" },
        () => row.role || "user")
    },
  },
  {
    title: "状态", key: "is_active", width: 80,
    render(row: User) {
      return h(NTag, { type: row.is_active ? "success" : "default", size: "small" },
        () => row.is_active ? "激活" : "停用")
    },
  },
  { title: "最后登录", key: "last_login", width: 150 },
  {
    title: "操作", key: "actions", width: 220,
    render(row: User) {
      return h("div", { style: { display: "flex", gap: "4px" } }, [
        h(NButton, { size: "tiny", text: true, onClick: () => editUser(row) }, () => "编辑"),
        h(NButton, { size: "tiny", text: true, onClick: () => resetPassword(row) }, () => "重置密码"),
        h(NButton, { size: "tiny", text: true, type: "error", onClick: () => confirmDelete(row) }, () => "删除"),
      ])
    },
  },
]

// 用户统计
const userStats = computed(() => ({
  total: users.value.length,
  active: users.value.filter((u: User) => u.is_active).length,
  admin: users.value.filter((u: User) => u.role === "admin" || u.role === "super_admin").length,
}))

onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <div class="user-mgmt bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">用户管理</h1>
            <p class="page-description">管理系统用户账号、角色与访问权限</p>
        </div>
        <div class="header-actions">
          <n-button type="primary" size="small" @click="handleAdd">添加用户</n-button>
        </div>
      </div>
    </div>
    <div class="main-content">
      <!-- 错误 -->
      <n-result
        v-if="error"
        status="500"
        title="加载失败"
        description="获取用户数据失败"
      >
        <template #footer><n-button type="primary" @click="fetchUsers">重试</n-button></template>
      </n-result>

      <!-- 主体 -->
      <n-card v-else :class="tokens.surface.card">
        <template #header>
          <div class="card-header-row">
            <span>用户列表</span>
            <n-input
              v-model:value="searchKeyword"
              placeholder="搜索用户名/姓名/邮箱"
              size="small"
              clearable
              style="width: 240px"
              @keyup.enter="handleSearch"
            />
          </div>
        </template>
        <n-spin :show="loading">
          <n-empty v-if="!loading && filteredUsers.length === 0" description="暂无用户" />
          <n-data-table
            v-else
            :columns="columns"
            :data="filteredUsers"
            :row-key="(r: User) => r.id"
            size="small"
            :bordered="false"
            :single-line="true"
          />
        </n-spin>
        <!-- 分页（服务端分页，翻页重新请求） -->
        <div v-if="total > pageSize" class="pagination-container">
          <n-pagination
            v-model:page="currentPage"
            :page-size="pageSize"
            :item-count="total"
            size="small"
            @update:page="fetchUsers"
          />
        </div>
      </n-card>

      <!-- 添加/编辑弹窗 -->
      <n-modal
        v-model:show="showModal"
        preset="card"
        :title="editingUser ? '编辑用户' : '添加用户'"
        style="width: 520px"
        :mask-closable="false"
      >
        <n-form label-width="100px">
          <n-form-item label="用户名" required>
            <n-input
              v-model:value="userForm.username"
              :disabled="!!editingUser"
              placeholder="字母数字组合"
            />
          </n-form-item>
          <n-form-item :label="editingUser ? '新密码（留空不修改）' : '密码'" :required="!editingUser">
            <n-input
              v-model:value="userForm.password"
              type="password"
              show-password-on="click"
            />
          </n-form-item>
          <n-form-item label="姓名">
            <n-input v-model:value="userForm.real_name" />
          </n-form-item>
          <n-form-item label="邮箱">
            <n-input v-model:value="userForm.email" />
          </n-form-item>
          <n-form-item label="手机号">
            <n-input v-model:value="userForm.phone" />
          </n-form-item>
          <n-form-item label="角色">
            <n-select
              v-model:value="userForm.role"
              :options="roleOptions"
              style="width: 160px"
            />
          </n-form-item>
          <n-form-item v-if="editingUser" label="激活状态">
            <n-switch v-model:value="userForm.is_active" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showModal = false">取消</n-button>
            <n-button type="primary" :loading="saving" @click="saveUser">
              {{ editingUser ? '保存' : '创建' }}
            </n-button>
          </n-space>
        </template>
      </n-modal>
    </div>
  </div>
</template>

<style scoped>
.user-mgmt {
  padding: 0;
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
