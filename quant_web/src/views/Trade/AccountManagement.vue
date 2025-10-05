<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElTable, ElTag, ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption } from 'element-plus'

interface Account {
  id: number
  account_name: string
  broker: string
  account_number: string
  total_asset: number
  available_cash: number
  market_value: number
  status: string
  created_at: string
}

const accounts = ref<Account[]>([])
const dialogVisible = ref(false)
const editingAccount = ref<Account | null>(null)
const accountForm = ref({
  account_name: '',
  broker: 'ht',
  account_number: '',
  status: 'active'
})

// 券商映射
const brokerMap: Record<string, string> = {
  ht: '华泰证券',
  gf: '广发证券',
  zs: '招商证券',
  zx: '中信证券'
}

// 获取账户列表
const fetchAccounts = async () => {
  try {
    // 模拟数据
    accounts.value = [
      {
        id: 1,
        account_name: '主交易账户',
        broker: 'ht',
        account_number: '1234567890',
        total_asset: 1500000,
        available_cash: 500000,
        market_value: 1000000,
        status: 'active',
        created_at: '2024-01-01'
      },
      {
        id: 2,
        account_name: '测试账户',
        broker: 'gf',
        account_number: '0987654321',
        total_asset: 100000,
        available_cash: 100000,
        market_value: 0,
        status: 'active',
        created_at: '2024-01-02'
      }
    ]
  } catch (error) {
    ElMessage.error('获取账户列表失败')
  }
}

// 保存账户
const saveAccount = async () => {
  try {
    if (editingAccount.value) {
      // 更新账户
      const index = accounts.value.findIndex(a => a.id === editingAccount.value!.id)
      if (index !== -1) {
        accounts.value[index] = { ...editingAccount.value, ...accountForm.value }
      }
    } else {
      // 新增账户
      const newAccount: Account = {
        id: Date.now(),
        ...accountForm.value,
        total_asset: 0,
        available_cash: 0,
        market_value: 0,
        created_at: new Date().toISOString().split('T')[0]
      }
      accounts.value.push(newAccount)
    }

    dialogVisible.value = false
    ElMessage.success('账户保存成功')
  } catch (error) {
    ElMessage.error('保存账户失败')
  }
}

// 编辑账户
const editAccount = (account: Account) => {
  editingAccount.value = account
  accountForm.value = { ...account }
  dialogVisible.value = true
}

// 删除账户
const deleteAccount = async (accountId: number) => {
  try {
    accounts.value = accounts.value.filter(a => a.id !== accountId)
    ElMessage.success('账户删除成功')
  } catch (error) {
    ElMessage.error('删除账户失败')
  }
}

// 同步账户信息
const syncAccount = async (account: Account) => {
  ElMessage.info(`正在同步 ${account.account_name} 的账户信息...`)
  // 实际调用券商API同步
}

onMounted(() => {
  fetchAccounts()
})
</script>

<template>
  <div class="account-management">
    <div class="management-header">
      <h3>账户管理</h3>
      <el-button type="primary" @click="dialogVisible = true; editingAccount = null; accountForm = { account_name: '', broker: 'ht', account_number: '', status: 'active' }">
        新增账户
      </el-button>
    </div>

    <el-table :data="accounts" style="width: 100%">
      <el-table-column prop="account_name" label="账户名称" width="150" />

      <el-table-column prop="broker" label="券商" width="120">
        <template #default="{ row }">
          {{ brokerMap[row.broker] || row.broker }}
        </template>
      </el-table-column>

      <el-table-column prop="account_number" label="账户号码" width="150" />

      <el-table-column prop="total_asset" label="总资产" width="120">
        <template #default="{ row }">
          ¥{{ row.total_asset.toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="available_cash" label="可用资金" width="120">
        <template #default="{ row }">
          ¥{{ row.available_cash.toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="market_value" label="持仓市值" width="120">
        <template #default="{ row }">
          ¥{{ row.market_value.toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '活跃' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="editAccount(row)">编辑</el-button>
          <el-button size="small" @click="syncAccount(row)">同步</el-button>
          <el-button size="small" type="danger" @click="deleteAccount(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑账户对话框 -->
    <el-dialog
      :title="editingAccount ? '编辑账户' : '新增账户'"
      v-model="dialogVisible"
      width="500px"
    >
      <el-form :model="accountForm" label-width="100px">
        <el-form-item label="账户名称">
          <el-input v-model="accountForm.account_name" />
        </el-form-item>

        <el-form-item label="券商">
          <el-select v-model="accountForm.broker" style="width: 100%">
            <el-option label="华泰证券" value="ht" />
            <el-option label="广发证券" value="gf" />
            <el-option label="招商证券" value="zs" />
            <el-option label="中信证券" value="zx" />
          </el-select>
        </el-form-item>

        <el-form-item label="账户号码">
          <el-input v-model="accountForm.account_number" />
        </el-form-item>

        <el-form-item label="状态">
          <el-select v-model="accountForm.status" style="width: 100%">
            <el-option label="活跃" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAccount">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.account-management {
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