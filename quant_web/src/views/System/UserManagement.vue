<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElTable, ElTag, ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElSwitch } from 'element-plus'

interface User {
  id: number
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
const dialogVisible = ref(false)
const editingUser = ref<User | null>(null)
const userForm = ref({
  username: '',
  email: '',
  phone: '',
  real_name: '',
  role: 'user',
  is_active: true
})

// 获取用户列表
const fetchUsers = async () => {
  try {
    // 模拟数据
    users.value = [
      {
        id: 1,
        username: 'admin',
        email: 'admin@quant.com',
        phone: '13800138000',
        real_name: '管理员',
        role: 'admin',
        is_active: true,
        last_login: '2024-01-15 14:30:00',
        created_at: '2024-01-01'
      },
      {
        id: 2,
        username: 'trader1',
        email: 'trader1@quant.com',
        phone: '13900139000',
        real_name: '交易员1',
        role: 'user',
        is_active: true,
        last_login: '2024-01-15 10:20:00',
        created_at: '2024-01-01'
      }
    ]
  } catch (error) {
    ElMessage.error('获取用户列表失败')
  }
}

// 保存用户
const saveUser = async () => {
  try {
    if (editingUser.value) {
      // 更新用户
      const index = users.value.findIndex(u => u.id === editingUser.value!.id)
      if (index !== -1) {
        users.value[index] = { ...editingUser.value, ...userForm.value }
      }
    } else {
      // 新增用户
      const newUser: User = {
        id: Date.now(),
        ...userForm.value,
        last_login: '',
        created_at: new Date().toISOString().split('T')[0]
      }
      users.value.push(newUser)
    }

    dialogVisible.value = false
    ElMessage.success('用户保存成功')
  } catch (error) {
    ElMessage.error('保存用户失败')
  }
}

// 编辑用户
const editUser = (user: User) => {
  editingUser.value = user
  userForm.value = { ...user }
  dialogVisible.value = true
}

// 删除用户
const deleteUser = async (userId: number) => {
  try {
    users.value = users.value.filter(u => u.id !== userId)
    ElMessage.success('用户删除成功')
  } catch (error) {
    ElMessage.error('删除用户失败')
  }
}

// 重置密码
const resetPassword = (user: User) => {
  ElMessage.info(`已发送密码重置邮件给 ${user.email}`)
}

onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <div class="user-management">
    <div class="management-header">
      <h3>用户管理</h3>
      <el-button type="primary" @click="dialogVisible = true; editingUser = null; userForm = { username: '', email: '', phone: '', real_name: '', role: 'user', is_active: true }">
        新增用户
      </el-button>
    </div>

    <el-table :data="users" style="width: 100%">
      <el-table-column prop="username" label="用户名" width="120" />

      <el-table-column prop="real_name" label="真实姓名" width="100" />

      <el-table-column prop="email" label="邮箱" width="200" />

      <el-table-column prop="phone" label="手机号" width="120" />

      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '活跃' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="last_login" label="最后登录" width="180">
        <template #default="{ row }">
          {{ row.last_login || '从未登录' }}
        </template>
      </el-table-column>

      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="editUser(row)">编辑</el-button>
          <el-button size="small" @click="resetPassword(row)">重置密码</el-button>
          <el-button size="small" type="danger" @click="deleteUser(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑用户对话框 -->
    <el-dialog
      :title="editingUser ? '编辑用户' : '新增用户'"
      v-model="dialogVisible"
      width="500px"
    >
      <el-form :model="userForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" />
        </el-form-item>

        <el-form-item label="真实姓名">
          <el-input v-model="userForm.real_name" />
        </el-form-item>

        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" />
        </el-form-item>

        <el-form-item label="手机号">
          <el-input v-model="userForm.phone" />
        </el-form-item>

        <el-form-item label="角色">
          <el-select v-model="userForm.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>

        <el-form-item label="状态">
          <el-switch v-model="userForm.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-management {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.management-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}
</style>