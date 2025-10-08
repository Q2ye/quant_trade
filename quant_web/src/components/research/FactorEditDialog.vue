<!-- components/Research/FactorEditDialog.vue -->
<!-- 因子创建和编辑的完整表单-->
<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="600px"
    :before-close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="100px"
      label-position="left"
    >
      <el-form-item label="因子名称" prop="name">
        <el-input
          v-model="formData.name"
          placeholder="请输入因子名称"
          maxlength="50"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="因子代码" prop="code">
        <el-input
          v-model="formData.code"
          placeholder="请输入因子代码"
          maxlength="20"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="因子类别" prop="category">
        <el-select v-model="formData.category" placeholder="请选择因子类别" style="width: 100%">
          <el-option label="价值因子" value="value" />
          <el-option label="成长因子" value="growth" />
          <el-option label="质量因子" value="quality" />
          <el-option label="动量因子" value="momentum" />
          <el-option label="技术因子" value="technical" />
        </el-select>
      </el-form-item>

      <el-form-item label="因子描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          :rows="3"
          placeholder="请输入因子描述"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="数据字段" prop="dataFields">
        <el-select
          v-model="formData.dataFields"
          multiple
          placeholder="请选择所需数据字段"
          style="width: 100%"
        >
          <el-option label="收盘价" value="close" />
          <el-option label="开盘价" value="open" />
          <el-option label="最高价" value="high" />
          <el-option label="最低价" value="low" />
          <el-option label="成交量" value="volume" />
          <el-option label="市盈率" value="pe" />
          <el-option label="市净率" value="pb" />
          <el-option label="股息率" value="dividend_yield" />
          <el-option label="ROE" value="roe" />
          <el-option label="营收" value="revenue" />
          <el-option label="净利润" value="net_profit" />
        </el-select>
      </el-form-item>

      <el-form-item label="因子公式" prop="formula">
        <el-input
          v-model="formData.formula"
          type="textarea"
          :rows="4"
          placeholder="请输入因子计算公式（Python语法）"
          maxlength="500"
          show-word-limit
        />
        <div class="formula-tips">
          <el-icon><Icon icon="mdi:information" /></el-icon>
          <span>支持Python语法，可使用选中的数据字段进行计算</span>
        </div>
      </el-form-item>

      <el-form-item label="状态" prop="status">
        <el-switch
          v-model="formData.status"
          :active-value="'active'"
          :inactive-value="'inactive'"
          active-text="启用"
          inactive-text="停用"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">
          <el-icon><Icon icon="mdi:check" /></el-icon>
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  factor: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'create',
    validator: (value) => ['create', 'edit'].includes(value)
  }
})

const emit = defineEmits(['update:modelValue', 'save'])

// 响应式数据
const formRef = ref(null)
const saving = ref(false)

// 表单数据
const formData = reactive({
  name: '',
  code: '',
  category: '',
  description: '',
  dataFields: [],
  formula: '',
  status: 'active'
})

// 表单验证规则
const formRules = {
  name: [
    { required: true, message: '请输入因子名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入因子代码', trigger: 'blur' },
    { pattern: /^[A-Z0-9_]+$/, message: '只能包含大写字母、数字和下划线', trigger: 'blur' }
  ],
  category: [
    { required: true, message: '请选择因子类别', trigger: 'change' }
  ],
  description: [
    { required: true, message: '请输入因子描述', trigger: 'blur' }
  ],
  dataFields: [
    { required: true, message: '请选择至少一个数据字段', trigger: 'change' }
  ],
  formula: [
    { required: true, message: '请输入因子计算公式', trigger: 'blur' }
  ]
}

// 计算属性
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const dialogTitle = computed(() => {
  return props.mode === 'create' ? '新建因子' : '编辑因子'
})

// 方法
const handleClose = () => {
  dialogVisible.value = false
  resetForm()
}

const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  Object.assign(formData, {
    name: '',
    code: '',
    category: '',
    description: '',
    dataFields: [],
    formula: '',
    status: 'active'
  })
}

const handleSave = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    saving.value = true

    // 模拟保存操作
    await new Promise(resolve => setTimeout(resolve, 1000))

    emit('save', { ...formData })
    handleClose()
  } catch (error) {
    console.error('表单验证失败:', error)
  } finally {
    saving.value = false
  }
}

// 监听因子数据变化
watch(
  () => props.factor,
  (newFactor) => {
    if (newFactor) {
      Object.assign(formData, {
        name: newFactor.name || '',
        code: newFactor.code || '',
        category: newFactor.category || '',
        description: newFactor.description || '',
        dataFields: newFactor.dataFields || [],
        formula: newFactor.formula || '',
        status: newFactor.status || 'active'
      })
    }
  },
  { immediate: true }
)

// 监听对话框显示状态
watch(
  () => props.modelValue,
  (newVal) => {
    if (newVal && props.mode === 'create') {
      resetForm()
    }
  }
)
</script>

<style lang="scss" scoped>
.formula-tips {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 4px;
  font-size: 12px;
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 6px;

  .el-icon {
    font-size: 14px;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>