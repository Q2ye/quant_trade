<!-- views/Research/FactorLibrary.vue -->
<template>
  <div class="factor-library">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Icon icon="mdi:database-cog" /></el-icon>
        因子库管理
      </h1>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreateFactor">
          <el-icon><Icon icon="mdi:plus" /></el-icon>
          新建因子
        </el-button>
        <el-button @click="importFactors">
          <el-icon><Icon icon="mdi:upload" /></el-icon>
          批量导入
        </el-button>
        <el-button @click="exportFactors">
          <el-icon><Icon icon="mdi:download" /></el-icon>
          导出配置
        </el-button>
        <el-button @click="runBatchTest" :disabled="selectedFactors.length === 0">
          <el-icon><Icon icon="mdi:play-circle" /></el-icon>
          批量测试
        </el-button>
      </div>
    </div>

    <!-- 因子库管理 -->
    <el-card class="library-management">
      <template #header>
        <div class="card-header">
          <span>因子库管理</span>
          <div class="filter-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索因子名称、代码或描述"
              style="width: 200px"
              clearable
            >
              <template #prefix>
                <el-icon><Icon icon="mdi:magnify" /></el-icon>
              </template>
            </el-input>
            <el-select v-model="filterCategory" placeholder="因子类别" style="width: 120px">
              <el-option label="全部" value="" />
              <el-option label="价值因子" value="value" />
              <el-option label="成长因子" value="growth" />
              <el-option label="质量因子" value="quality" />
              <el-option label="动量因子" value="momentum" />
            </el-select>
            <el-select v-model="filterStatus" placeholder="状态" style="width: 100px">
              <el-option label="全部" value="" />
              <el-option label="启用" value="active" />
              <el-option label="停用" value="inactive" />
            </el-select>
          </div>
        </div>
      </template>

      <!-- 批量操作栏 -->
      <div v-if="selectedFactors.length > 0" class="batch-actions">
        <span class="selected-text">已选择 {{ selectedFactors.length }} 个因子</span>
        <el-button size="small" @click="batchEnable">批量启用</el-button>
        <el-button size="small" @click="batchDisable">批量停用</el-button>
        <el-button size="small" type="danger" @click="batchDelete">批量删除</el-button>
      </div>

      <el-table
        :data="filteredFactors"
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="因子名称" width="150" />
        <el-table-column prop="code" label="因子代码" width="120" />
        <el-table-column prop="category" label="类别" width="100">
          <template #default="{ row }">
            <el-tag :type="getCategoryTag(row.category)" size="small">
              {{ getCategoryText(row.category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="因子描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="dataFields" label="数据字段" width="120">
          <template #default="{ row }">
            <el-tooltip :content="row.dataFields.join(', ')" placement="top">
              <span>{{ row.dataFields.length }}个字段</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="performance" label="近期表现" width="100">
          <template #default="{ row }">
            <performance-badge :performance="row.performance" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-switch
              v-model="row.status"
              :active-value="'active'"
              :inactive-value="'inactive'"
              @change="handleStatusChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="lastUpdate" label="最后更新" width="120">
          <template #default="{ row }">
            {{ formatDate(row.lastUpdate) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEditFactor(row)">
              <el-icon><Icon icon="mdi:pencil" /></el-icon>
              编辑
            </el-button>
            <el-button size="small" @click="handleTestFactor(row)">
              <el-icon><Icon icon="mdi:test-tube" /></el-icon>
              测试
            </el-button>
            <el-button size="small" type="danger" @click="handleDeleteFactor(row)">
              <el-icon><Icon icon="mdi:delete" /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 批量测试面板 -->
    <el-card v-if="batchTestResults" class="batch-test-results">
      <template #header>
        <span>批量测试结果</span>
        <el-button type="text" @click="exportBatchResults">导出报告</el-button>
      </template>

      <el-table :data="batchTestResults" border>
        <el-table-column prop="factorName" label="因子名称" />
        <el-table-column prop="annualReturn" label="年化收益" width="100">
          <template #default="{ row }">
            <span :class="row.annualReturn >= 0 ? 'positive' : 'negative'">
              {{ formatPercent(row.annualReturn) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="sharpeRatio" label="夏普比率" width="100">
          <template #default="{ row }">
            {{ row.sharpeRatio.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="maxDrawdown" label="最大回撤" width="100">
          <template #default="{ row }">
            <span class="negative">{{ formatPercent(row.maxDrawdown) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="winRate" label="胜率" width="80">
          <template #default="{ row }">
            {{ formatPercent(row.winRate) }}
          </template>
        </el-table-column>
        <el-table-column prop="icMean" label="IC均值" width="80">
          <template #default="{ row }">
            {{ row.icMean.toFixed(3) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="viewFactorDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 专业分析工具 -->
    <el-card class="analysis-tools">
      <template #header>
        <span>专业分析工具</span>
      </template>

      <el-row :gutter="20">
        <el-col :span="8">
          <el-card shadow="hover" class="tool-card" @click="openFactorCorrelation">
            <div class="tool-content">
              <el-icon size="24" color="#409EFF"><Icon icon="mdi:chart-scatter-plot" /></el-icon>
              <div class="tool-info">
                <div class="tool-title">因子相关性分析</div>
                <div class="tool-desc">分析因子间的相关性矩阵</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="tool-card" @click="openStabilityAnalysis">
            <div class="tool-content">
              <el-icon size="24" color="#67C23A"><Icon icon="mdi:chart-timeline" /></el-icon>
              <div class="tool-info">
                <div class="tool-title">因子稳定性分析</div>
                <div class="tool-desc">检验因子表现的稳定性</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="tool-card" @click="openCombinationAnalysis">
            <div class="tool-content">
              <el-icon size="24" color="#E6A23C"><Icon icon="mdi:chart-bell-curve" /></el-icon>
              <div class="tool-info">
                <div class="tool-title">因子组合优化</div>
                <div class="tool-desc">寻找最优因子组合权重</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 因子编辑对话框 -->
    <factor-edit-dialog
      v-model="factorDialogVisible"
      :factor="editingFactor"
      :mode="editMode"
      @save="handleSaveFactor"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'

// 组件
import PerformanceBadge from '@/components/Research/PerformanceBadge.vue'
import FactorEditDialog from '@/components/Research/FactorEditDialog.vue'

// 响应式数据
const loading = ref(false)
const searchKeyword = ref('')
const filterCategory = ref('')
const filterStatus = ref('')
const selectedFactors = ref([])
const factorDialogVisible = ref(false)
const editingFactor = ref(null)
const editMode = ref('create')
const batchTestResults = ref(null)

const pagination = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

// 因子数据
const factors = ref([
  {
    id: '1',
    name: '市盈率因子',
    code: 'PE',
    category: 'value',
    description: '基于市盈率的估值因子，低市盈率表示价值被低估',
    dataFields: ['pe'],
    formula: '1 / pe if pe > 0 else 0',
    performance: { score: 85, trend: 'up' },
    status: 'active',
    lastUpdate: new Date('2024-01-15')
  },
  {
    id: '2',
    name: '动量因子',
    code: 'MOMENTUM_1M',
    category: 'momentum',
    description: '一个月动量因子，计算过去一个月的收益率',
    dataFields: ['close'],
    formula: 'close / close.shift(20) - 1',
    performance: { score: 72, trend: 'stable' },
    status: 'active',
    lastUpdate: new Date('2024-01-15')
  },
  {
    id: '3',
    name: '波动率因子',
    code: 'VOLATILITY_20D',
    category: 'technical',
    description: '20日历史波动率因子',
    dataFields: ['close'],
    formula: 'close.pct_change().rolling(20).std()',
    performance: { score: 68, trend: 'down' },
    status: 'inactive',
    lastUpdate: new Date('2024-01-14')
  }
])

// 计算属性
const filteredFactors = computed(() => {
  let result = factors.value

  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(factor =>
      factor.name.toLowerCase().includes(keyword) ||
      factor.description.toLowerCase().includes(keyword) ||
      factor.code.toLowerCase().includes(keyword)
    )
  }

  if (filterCategory.value) {
    result = result.filter(factor => factor.category === filterCategory.value)
  }

  if (filterStatus.value) {
    result = result.filter(factor => factor.status === filterStatus.value)
  }

  pagination.total = result.length
  const start = (pagination.currentPage - 1) * pagination.pageSize
  const end = start + pagination.pageSize
  return result.slice(start, end)
})

// 方法
const getCategoryTag = (category) => {
  const map = {
    value: 'success',
    growth: 'warning',
    quality: 'primary',
    momentum: 'danger',
    technical: 'info'
  }
  return map[category] || 'info'
}

const getCategoryText = (category) => {
  const map = {
    value: '价值因子',
    growth: '成长因子',
    quality: '质量因子',
    momentum: '动量因子',
    technical: '技术因子'
  }
  return map[category] || '其他'
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('zh-CN')
}

const formatPercent = (value) => {
  return `${(value * 100).toFixed(2)}%`
}

const handleSelectionChange = (selection) => {
  selectedFactors.value = selection
}

const handleCreateFactor = () => {
  editMode.value = 'create'
  editingFactor.value = null
  factorDialogVisible.value = true
}

const handleEditFactor = (factor) => {
  editMode.value = 'edit'
  editingFactor.value = { ...factor }
  factorDialogVisible.value = true
}

const handleTestFactor = (factor) => {
  ElMessage.info(`开始测试因子: ${factor.name}`)
  // 跳转到详细测试页面或打开测试面板
}

const handleDeleteFactor = async (factor) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除因子 "${factor.name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const index = factors.value.findIndex(f => f.id === factor.id)
    if (index > -1) {
      factors.value.splice(index, 1)
      ElMessage.success('因子删除成功')
    }
  } catch (error) {
    // 用户取消
  }
}

const handleStatusChange = (factor) => {
  ElMessage.success(`因子 ${factor.name} 已${factor.status === 'active' ? '启用' : '停用'}`)
}

const handleSaveFactor = (factorData) => {
  if (editMode.value === 'create') {
    // 添加新因子
    const newFactor = {
      ...factorData,
      id: Date.now().toString(),
      lastUpdate: new Date(),
      performance: { score: 0, trend: 'stable' }
    }
    factors.value.push(newFactor)
    ElMessage.success('因子创建成功')
  } else {
    // 更新现有因子
    const index = factors.value.findIndex(f => f.id === editingFactor.value.id)
    if (index > -1) {
      factors.value[index] = {
        ...factorData,
        lastUpdate: new Date()
      }
      ElMessage.success('因子更新成功')
    }
  }
  factorDialogVisible.value = false
}

// 批量操作
const batchEnable = () => {
  selectedFactors.value.forEach(factor => {
    factor.status = 'active'
  })
  ElMessage.success(`已启用 ${selectedFactors.value.length} 个因子`)
  selectedFactors.value = []
}

const batchDisable = () => {
  selectedFactors.value.forEach(factor => {
    factor.status = 'inactive'
  })
  ElMessage.success(`已停用 ${selectedFactors.value.length} 个因子`)
  selectedFactors.value = []
}

const batchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedFactors.value.length} 个因子吗？`,
      '批量删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const idsToDelete = new Set(selectedFactors.value.map(f => f.id))
    factors.value = factors.value.filter(f => !idsToDelete.has(f.id))
    ElMessage.success(`已删除 ${selectedFactors.value.length} 个因子`)
    selectedFactors.value = []
  } catch (error) {
    // 用户取消
  }
}

const runBatchTest = async () => {
  if (selectedFactors.value.length === 0) {
    ElMessage.warning('请选择要测试的因子')
    return
  }

  loading.value = true
  try {
    // 模拟批量测试
    await new Promise(resolve => setTimeout(resolve, 3000))

    // 模拟测试结果
    batchTestResults.value = selectedFactors.value.map(factor => ({
      factorId: factor.id,
      factorName: factor.name,
      annualReturn: Math.random() * 0.3 - 0.05,
      sharpeRatio: Math.random() * 2,
      maxDrawdown: Math.random() * -0.2 - 0.1,
      winRate: Math.random() * 0.3 + 0.5,
      icMean: Math.random() * 0.1
    }))

    ElMessage.success(`批量测试完成，共测试 ${selectedFactors.value.length} 个因子`)
  } catch (error) {
    ElMessage.error('批量测试失败')
  } finally {
    loading.value = false
  }
}

const exportBatchResults = () => {
  ElMessage.info('导出批量测试报告')
}

const viewFactorDetail = (result) => {
  const factor = factors.value.find(f => f.id === result.factorId)
  if (factor) {
    handleTestFactor(factor)
  }
}

const importFactors = () => {
  ElMessage.info('导入功能开发中')
}

const exportFactors = () => {
  ElMessage.info('导出功能开发中')
}

const openFactorCorrelation = () => {
  ElMessage.info('打开因子相关性分析工具')
}

const openStabilityAnalysis = () => {
  ElMessage.info('打开因子稳定性分析工具')
}

const openCombinationAnalysis = () => {
  ElMessage.info('打开因子组合优化工具')
}

const handlePageChange = (page) => {
  pagination.currentPage = page
}

// 生命周期
onMounted(() => {
  pagination.total = factors.value.length
})
</script>

<style lang="scss" scoped>
.factor-library {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .page-title {
    margin: 0;
    color: #303133;
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.library-management {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.batch-actions {
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;

  .selected-text {
    color: #606266;
    margin-right: 10px;
  }
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.batch-test-results,
.analysis-tools {
  margin-top: 20px;
}

.tool-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1) !important;
  }

  .tool-content {
    display: flex;
    align-items: center;
    gap: 12px;

    .tool-info {
      .tool-title {
        font-weight: 500;
        margin-bottom: 4px;
      }

      .tool-desc {
        font-size: 12px;
        color: #909399;
      }
    }
  }
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>