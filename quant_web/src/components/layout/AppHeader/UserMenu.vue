<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

// 用户信息
const userInfo = computed(() => userStore.userInfo)

// 下拉菜单选项
const menuOptions = [
  {
    label: '个人中心',
    icon: 'User',
    command: 'profile'
  },
  {
    label: '账户设置',
    icon: 'Setting',
    command: 'settings'
  },
  {
    type: 'divider'
  },
  {
    label: '退出登录',
    icon: 'SwitchButton',
    command: 'logout'
  }
]

// 处理菜单点击
const handleCommand = async (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/user/profile')
      break
    case 'settings':
      router.push('/user/settings')
      break
    case 'logout':
      await handleLogout()
      break
  }
}

// 处理退出登录
const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await userStore.logout()
    ElMessage.success('退出成功')
    router.push('/login')
  } catch (error) {
    // 用户取消退出
  }
}

// 显示用户角色标签
const getRoleLabel = (role: string) => {
  const roleMap: Record<string, string> = {
    admin: '管理员',
    user: '普通用户',
    guest: '访客'
  }
  return roleMap[role] || role
}

const getRoleColor = (role: string) => {
  const colorMap: Record<string, string> = {
    admin: '#f56c6c',
    user: '#409eff',
    guest: '#909399'
  }
  return colorMap[role] || '#909399'
}
</script>

<template>
  <div class="user-menu">
    <el-dropdown @command="handleCommand" trigger="click">
      <div class="user-info">
        <el-avatar
          :size="32"
          :src="userInfo?.avatar"
          class="user-avatar"
        >
          {{ userInfo?.username?.charAt(0).toUpperCase() }}
        </el-avatar>

        <div class="user-details" v-if="!$route.meta.hideUserInfo">
          <div class="username">{{ userInfo?.username }}</div>
          <div class="user-role" :style="{ color: getRoleColor(userInfo?.role || '') }">
            {{ getRoleLabel(userInfo?.role || '') }}
          </div>
        </div>

        <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
      </div>

      <template #dropdown>
        <el-dropdown-menu>
          <!-- 用户信息展示 -->
          <el-dropdown-item class="user-profile-item" disabled>
            <div class="dropdown-user-info">
              <el-avatar :size="40" :src="userInfo?.avatar">
                {{ userInfo?.username?.charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="dropdown-user-details">
                <div class="username">{{ userInfo?.username }}</div>
                <div class="email">{{ userInfo?.email }}</div>
              </div>
            </div>
          </el-dropdown-item>

          <el-dropdown-item divided />

          <!-- 菜单选项 -->
          <el-dropdown-item
            v-for="item in menuOptions"
            :key="item.label"
            :command="item.command"
            :divided="item.type === 'divider'"
          >
            <el-icon v-if="item.icon">
              <component :is="item.icon" />
            </el-icon>
            <span>{{ item.label }}</span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style scoped>
.user-menu {
  margin-left: auto;
}

.user-info {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: var(--el-fill-color-light);
}

.user-avatar {
  margin-right: 8px;
}

.user-details {
  margin-right: 8px;
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.user-role {
  font-size: 12px;
  margin-top: 2px;
}

.dropdown-arrow {
  color: var(--el-text-color-secondary);
  transition: transform 0.3s;
}

.user-info:hover .dropdown-arrow {
  transform: rotate(180deg);
}

/* 下拉菜单样式 */
:deep(.user-profile-item) {
  padding: 12px 16px;
  cursor: default;
}

:deep(.user-profile-item:hover) {
  background-color: transparent !important;
}

.dropdown-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dropdown-user-details {
  display: flex;
  flex-direction: column;
}

.dropdown-user-details .username {
  font-weight: bold;
}

.dropdown-user-details .email {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .user-details {
    display: none;
  }

  .user-info {
    padding: 4px 8px;
  }
}
</style>