<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElTable, ElTag, ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElSwitch } from 'element-plus'

interface RiskRule {
  id: number
  rule_name: string
  rule_type: string
  condition: any
  action: string
  is_active: boolean
  created_at: string
}

const rules = ref<RiskRule[]>([])
const dialogVisible = ref(false)
const editingRule = ref<RiskRule | null>(null)
const ruleForm = ref({
  rule_name: '',
  rule_type: 'position_limit',
  condition: {},
  action: 'alert',
  is_active: true
})

// 规则类型映射
const ruleTypeMap: Record<string, string> = {
  position_limit: '持仓限制',
  daily_loss_limit: '单日亏损限制',
  blacklist: '黑名单',
  volatility_limit: '波动率限制'
}

// 获取风控规则
const fetchRiskRules = async () => {
  try {
    // 模拟数据
    rules.value = [
      {
        id: 1,
        rule_name: '单股仓位限制',
        rule_type: 'position_limit',
        condition: { max_position_ratio: 0.2 },
        action: 'alert',
        is_active: true,
        created_at: '2024-01-01'
      },
      {
        id: 2,
        rule_name: '单日亏损限制',
        rule_type: 'daily_loss_limit',
        condition: { max_daily_loss: 0.05 },
        action: 'stop_strategy',
        is_active: true,
        created_at: '2024-01-01'
      }
    ]
  } catch (error) {
    ElMessage.error('获取风控规则失败')
  }
}

// 保存规则
const saveRule = async () => {
  try {
    if (editingRule.value) {
      // 更新规则
      const index = rules.value.findIndex(r => r.id === editingRule.value!.id)
      if (index !== -1) {
        rules.value[index] = { ...editingRule.value, ...ruleForm.value }
      }
    } else {
      // 新增规则
      const newRule: RiskRule = {
        id: Date.now(),
        ...ruleForm.value,
        created_at: new Date().toISOString().split('T')[0]
      }
      rules.value.push(newRule)
    }

    dialogVisible.value = false
    ElMessage.success('规则保存成功')
  } catch (error) {
    ElMessage.error('保存规则失败')
  }
}

// 编辑规则
const editRule = (rule: RiskRule) => {
  editingRule.value = rule
  ruleForm.value = { ...rule }
  dialogVisible.value = true
}

// 删除规则
const deleteRule = async (ruleId: number) => {
  try {
    rules.value = rules.value.filter(r => r.id !== ruleId)
    ElMessage.success('规则删除成功')
  } catch (error) {
    ElMessage.error('删除规则失败')
  }
}

// 切换规则状态
const toggleRuleStatus = async (rule: RiskRule) => {
  rule.is_active = !rule.is_active
  ElMessage.success(`规则已${rule.is_active ? '启用' : '禁用'}`)
}

onMounted(() => {
  fetchRiskRules()
})
</script>

<template>
  <div class="risk-rules">
    <div class="rules-header">
      <h3>风控规则管理</h3>
      <el-button type="primary" @click="dialogVisible = true; editingRule = null; ruleForm = { rule_name: '', rule_type: 'position_limit', condition: {}, action: 'alert', is_active: true }">
        新增规则
      </el-button>
    </div>

    <el-table :data="rules" style="width: 100%">
      <el-table-column prop="rule_name" label="规则名称" width="200" />

      <el-table-column prop="rule_type" label="规则类型" width="150">
        <template #default="{ row }">
          <el-tag>{{ ruleTypeMap[row.rule_type] || row.rule_type }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="condition" label="规则条件" min-width="200">
        <template #default="{ row }">
          <pre style="margin: 0; font-size: 12px;">{{ JSON.stringify(row.condition, null, 2) }}</pre>
        </template>
      </el-table-column>

      <el-table-column prop="action" label="触发动作" width="120">
        <template #default="{ row }">
          {{ row.action === 'alert' ? '报警' : '停止策略' }}
        </template>
      </el-table-column>

      <el-table-column prop="is_active" label="状态" width="100">
        <template #default="{ row }">
          <el-switch
            v-model="row.is_active"
            @change="toggleRuleStatus(row)"
          />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="editRule(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteRule(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑规则对话框 -->
    <el-dialog
      :title="editingRule ? '编辑规则' : '新增规则'"
      v-model="dialogVisible"
      width="600px"
    >
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="ruleForm.rule_name" />
        </el-form-item>

        <el-form-item label="规则类型">
          <el-select v-model="ruleForm.rule_type" style="width: 100%">
            <el-option label="持仓限制" value="position_limit" />
            <el-option label="单日亏损限制" value="daily_loss_limit" />
            <el-option label="黑名单" value="blacklist" />
            <el-option label="波动率限制" value="volatility_limit" />
          </el-select>
        </el-form-item>

        <el-form-item label="触发动作">
          <el-select v-model="ruleForm.action" style="width: 100%">
            <el-option label="报警" value="alert" />
            <el-option label="停止策略" value="stop_strategy" />
            <el-option label="撤单" value="cancel_orders" />
          </el-select>
        </el-form-item>

        <el-form-item label="启用状态">
          <el-switch v-model="ruleForm.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.risk-rules {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.rules-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}
</style>