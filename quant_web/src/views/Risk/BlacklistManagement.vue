<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElTable, ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption } from 'element-plus'

interface BlacklistItem {
  id: number
  ts_code: string
  name: string
  reason: string
  added_by: string
  added_at: string
  is_active: boolean
}

const blacklist = ref<BlacklistItem[]>([])
const dialogVisible = ref(false)
const newItem = ref({
  ts_code: '',
  reason: 'st_risk'
})

// 原因映射
const reasonMap: Record<string, string> = {
  st_risk: 'ST风险',
  financial_risk: '财务风险',
  regulatory_risk: '监管风险',
  manual_add: '手动添加'
}

// 获取黑名单
const fetchBlacklist = async () => {
  try {
    // 模拟数据
    blacklist.value = [
      {
        id: 1,
        ts_code: '600086.SH',
        name: '退市金钰',
        reason: 'st_risk',
        added_by: 'system',
        added_at: '2024-01-01',
        is_active: true
      },
      {
        id: 2,
        ts_code: '000979.SZ',
        name: '中弘退',
        reason: 'regulatory_risk',
        added_by: 'admin',
        added_at: '2024-01-02',
        is_active: true
      }
    ]
  } catch (error) {
    ElMessage.error('获取黑名单失败')
  }
}

// 添加黑名单
const addToBlacklist = async () => {
  if (!newItem.value.ts_code) {
    ElMessage.warning('请输入股票代码')
    return
  }

  try {
    const item: BlacklistItem = {
      id: Date.now(),
      ts_code: newItem.value.ts_code,
      name: `股票${newItem.value.ts_code}`, // 实际中需要查询股票名称
      reason: newItem.value.reason,
      added_by: 'current_user',
      added_at: new Date().toISOString().split('T')[0],
      is_active: true
    }

    blacklist.value.push(item)
    dialogVisible.value = false
    newItem.value = { ts_code: '', reason: 'st_risk' }
    ElMessage.success('添加成功')
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

// 移除黑名单
const removeFromBlacklist = async (item: BlacklistItem) => {
  try {
    blacklist.value = blacklist.value.filter(i => i.id !== item.id)
    ElMessage.success('移除成功')
  } catch (error) {
    ElMessage.error('移除失败')
  }
}

// 导入黑名单
const importBlacklist = () => {
  // 实现导入逻辑
  ElMessage.info('导入功能开发中')
}

// 导出黑名单
const exportBlacklist = () => {
  const csvContent = blacklist.value.map(item =>
    `${item.ts_code},${item.name},${reasonMap[item.reason]},${item.added_at}`
  ).join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `blacklist_${new Date().toISOString().split('T')[0]}.csv`
  a.click()
  window.URL.revokeObjectURL(url)
}

onMounted(() => {
  fetchBlacklist()
})
</script>

<template>
  <div class="blacklist-management">
    <div class="management-header">
      <h3>黑名单管理</h3>
      <div class="actions">
        <el-button type="primary" @click="dialogVisible = true">添加黑名单</el-button>
        <el-button @click="importBlacklist">导入</el-button>
        <el-button @click="exportBlacklist">导出</el-button>
      </div>
    </div>

    <el-table :data="blacklist" style="width: 100%">
      <el-table-column prop="ts_code" label="股票代码" width="120" />

      <el-table-column prop="name" label="股票名称" width="150" />

      <el-table-column prop="reason" label="原因" width="120">
        <template #default="{ row }">
          {{ reasonMap[row.reason] || row.reason }}
        </template>
      </el-table-column>

      <el-table-column prop="added_by" label="添加人" width="100" />

      <el-table-column prop="added_at" label="添加时间" width="120" />

      <el-table-column prop="is_active" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'danger' : 'info'">
            {{ row.is_active ? '生效中' : '已失效' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="removeFromBlacklist(row)">
            移除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加黑名单对话框 -->
    <el-dialog title="添加黑名单" v-model="dialogVisible" width="500px">
      <el-form :model="newItem" label-width="80px">
        <el-form-item label="股票代码">
          <el-input v-model="newItem.ts_code" placeholder="例如：600000.SH" />
        </el-form-item>

        <el-form-item label="原因">
          <el-select v-model="newItem.reason" style="width: 100%">
            <el-option label="ST风险" value="st_risk" />
            <el-option label="财务风险" value="financial_risk" />
            <el-option label="监管风险" value="regulatory_risk" />
            <el-option label="手动添加" value="manual_add" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addToBlacklist">确认添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.blacklist-management {
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

.actions {
  display: flex;
  gap: 10px;
}
</style>