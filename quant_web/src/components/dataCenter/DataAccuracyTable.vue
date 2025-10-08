<!-- /components/dataCenter/DataAccuracyTable.vue -->
<template>
  <div class="data-accuracy-table">
    <div class="table-header">
      <el-row :gutter="16" class="filter-row">
        <el-col :span="6">
          <el-input
            v-model="filterParams.tableName"
            placeholder="搜索表名"
            clearable
            @clear="handleFilter"
            @keyup.enter="handleFilter"
          >
            <template #prefix>
              <Icon icon="mdi:magnify" class="input-icon" />
            </template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="filterParams.accuracyStatus"
            placeholder="准确状态"
            clearable
            @change="handleFilter"
          >
            <template #prefix>
              <Icon icon="mdi:filter" class="input-icon" />
            </template>
            <el-option label="准确" value="accurate" />
            <el-option label="警告" value="warning" />
            <el-option label="错误" value="error" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="filterParams.verificationType"
            placeholder="验证类型"
            clearable
            @change="handleFilter"
          >
            <template #prefix>
              <Icon icon="mdi:format-list-bulleted-type" class="input-icon" />
            </template>
            <el-option label="数据一致性" value="consistency" />
            <el-option label="业务逻辑" value="business_logic" />
            <el-option label="数据范围" value="data_range" />
            <el-option label="数据关联" value="data_relation" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="handleFilter">
            <Icon icon="mdi:magnify" class="button-icon" />
            查询
          </el-button>
          <el-button @click="handleReset">
            <Icon icon="mdi:refresh" class="button-icon" />
            重置
          </el-button>
          <el-button type="success" @click="handleRunVerification">
            <Icon icon="mdi:play" class="button-icon" />
            执行验证
          </el-button>
        </el-col>
      </el-row>
    </div>

    <el-table
      :data="tableData"
      v-loading="loading"
      style="width: 100%"
      :default-sort="{ prop: 'accuracyRate', order: 'descending' }"
    >
      <el-table-column type="index" label="序号" width="60" />

      <el-table-column prop="tableName" label="数据表" min-width="120">
        <template #default="{ row }">
          <div class="table-name">
            <span class="name-text">{{ row.tableName }}</span>
            <el-tag v-if="row.isCoreTable" size="small" type="success">
              <Icon icon="mdi:star" class="tag-icon" />
              核心
            </el-tag>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="verificationType" label="验证类型" width="120">
        <template #default="{ row }">
          <el-tag :type="getVerificationTypeTagType(row.verificationType)" size="small">
            {{ getVerificationTypeText(row.verificationType) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="description" label="验证描述" min-width="180">
        <template #default="{ row }">
          <div class="verification-description">
            {{ row.description }}
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="accuracyRate" label="准确率" width="120" sortable>
        <template #default="{ row }">
          <div class="accuracy-rate">
            <el-progress
              :percentage="row.accuracyRate"
              :status="getAccuracyStatus(row.accuracyRate)"
              :show-text="false"
            />
            <span class="rate-text" :class="getRateTextClass(row.accuracyRate)">
              {{ row.accuracyRate.toFixed(1) }}%
            </span>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="checkedRecords" label="检查记录数" width="110" align="right">
        <template #default="{ row }">
          {{ formatNumber(row.checkedRecords) }}
        </template>
      </el-table-column>

      <el-table-column prop="errorRecords" label="错误记录数" width="110" align="right">
        <template #default="{ row }">
          <span :class="getErrorCountClass(row.errorRecords)">
            {{ formatNumber(row.errorRecords) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column prop="lastVerificationTime" label="最后验证时间" width="140" sortable>
        <template #default="{ row }">
          {{ formatTime(row.lastVerificationTime) }}
        </template>
      </el-table-column>

      <el-table-column prop="status" label="验证状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusTagType(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            size="small"
            @click="handleViewDetail(row)"
          >
            <Icon icon="mdi:eye" class="button-icon" />
            详情
          </el-button>
          <el-button
            link
            type="warning"
            size="small"
            @click="handleRerunVerification(row)"
          >
            <Icon icon="mdi:refresh" class="button-icon" />
            重新验证
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container">
      <el-pagination
        v-model:current-page="pagination.currentPage"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 准确性详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="`准确性验证详情 - ${currentVerification?.tableName}`"
      width="900px"
    >
      <AccuracyDetail :verification-data="currentVerification" v-if="detailDialogVisible" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import AccuracyDetail from "@/components/dataCenter/AccuracyDetail.vue";

// 数据类型定义
interface DataAccuracy {
  id: string
  tableName: string
  verificationType: string
  description: string
  accuracyRate: number
  checkedRecords: number
  errorRecords: number
  lastVerificationTime: string
  status: string
  isCoreTable: boolean
  details?: {
    ruleDescription: string
    errorExamples?: any[]
    passRate: number
    validationRules?: string[]
  }
}

interface FilterParams {
  tableName: string
  accuracyStatus: string
  verificationType: string
}

interface Pagination {
  currentPage: number
  pageSize: number
  total: number
}

// 响应式数据
const loading = ref(false)
const tableData = ref<DataAccuracy[]>([])
const filterParams = reactive<FilterParams>({
  tableName: '',
  accuracyStatus: '',
  verificationType: ''
})
const pagination = reactive<Pagination>({
  currentPage: 1,
  pageSize: 20,
  total: 0
})
const detailDialogVisible = ref(false)
const currentVerification = ref<DataAccuracy | null>(null)

// 初始化数据
onMounted(() => {
  loadTableData()
})

// 加载表格数据
const loadTableData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))

    // 模拟准确性验证数据
    const mockData: DataAccuracy[] = [
      {
        id: '1',
        tableName: 'stock_daily',
        verificationType: 'data_range',
        description: '价格数据范围验证：开盘价、收盘价、最高价、最低价逻辑关系',
        accuracyRate: 99.8,
        checkedRecords: 12500000,
        errorRecords: 25000,
        lastVerificationTime: '2024-01-15 18:00:00',
        status: 'accurate',
        isCoreTable: true,
        details: {
          ruleDescription: '验证最高价 >= 开盘价/收盘价 >= 最低价',
          passRate: 99.8,
          validationRules: ['high >= open', 'high >= close', 'low <= open', 'low <= close']
        }
      },
      {
        id: '2',
        tableName: 'stock_basic',
        verificationType: 'consistency',
        description: '股票基础信息一致性验证：代码格式、市场分类',
        accuracyRate: 98.5,
        checkedRecords: 5200,
        errorRecords: 78,
        lastVerificationTime: '2024-01-15 17:30:00',
        status: 'warning',
        isCoreTable: true
      },
      {
        id: '3',
        tableName: 'stock_minutes',
        verificationType: 'business_logic',
        description: '分钟数据时间连续性验证',
        accuracyRate: 97.2,
        checkedRecords: 185000000,
        errorRecords: 5180000,
        lastVerificationTime: '2024-01-15 16:45:00',
        status: 'error',
        isCoreTable: true
      },
      {
        id: '4',
        tableName: 'stock_income_core',
        verificationType: 'business_logic',
        description: '财务报表逻辑验证：利润表各项目关系',
        accuracyRate: 95.8,
        checkedRecords: 85000,
        errorRecords: 3580,
        lastVerificationTime: '2024-01-15 15:20:00',
        status: 'warning',
        isCoreTable: false
      },
      {
        id: '5',
        tableName: 'etf_daily',
        verificationType: 'data_relation',
        description: 'ETF净值与成分股关系验证',
        accuracyRate: 99.5,
        checkedRecords: 3200000,
        errorRecords: 16000,
        lastVerificationTime: '2024-01-15 14:15:00',
        status: 'accurate',
        isCoreTable: false
      },
      {
        id: '6',
        tableName: 'stock_moneyflow',
        verificationType: 'consistency',
        description: '资金流向数据内部一致性验证',
        accuracyRate: 98.9,
        checkedRecords: 9800000,
        errorRecords: 107800,
        lastVerificationTime: '2024-01-15 13:30:00',
        status: 'accurate',
        isCoreTable: false
      }
    ]

    tableData.value = mockData
    pagination.total = mockData.length
  } catch (error) {
    ElMessage.error('数据加载失败')
    console.error('加载准确性验证数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 工具函数
const getVerificationTypeTagType = (type: string) => {
  const typeMap: { [key: string]: string } = {
    consistency: 'primary',
    business_logic: 'success',
    data_range: 'warning',
    data_relation: 'info'
  }
  return typeMap[type] || 'info'
}

const getVerificationTypeText = (type: string) => {
  const textMap: { [key: string]: string } = {
    consistency: '数据一致性',
    business_logic: '业务逻辑',
    data_range: '数据范围',
    data_relation: '数据关联'
  }
  return textMap[type] || type
}

const getAccuracyStatus = (rate: number) => {
  if (rate >= 99) return 'success'
  if (rate >= 95) return 'warning'
  return 'exception'
}

const getRateTextClass = (rate: number) => {
  if (rate >= 99) return 'rate-high'
  if (rate >= 95) return 'rate-medium'
  return 'rate-low'
}

const getStatusTagType = (status: string) => {
  const statusMap: { [key: string]: string } = {
    accurate: 'success',
    warning: 'warning',
    error: 'danger'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: { [key: string]: string } = {
    accurate: '准确',
    warning: '警告',
    error: '错误'
  }
  return textMap[status] || status
}

const getErrorCountClass = (count: number) => {
  if (count === 0) return 'error-zero'
  if (count < 1000) return 'error-low'
  return 'error-high'
}

const formatNumber = (num: number) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

const formatTime = (time: string) => {
  return time.replace(' ', '\n')
}

// 事件处理
const handleFilter = () => {
  pagination.currentPage = 1
  loadTableData()
}

const handleReset = () => {
  Object.assign(filterParams, {
    tableName: '',
    accuracyStatus: '',
    verificationType: ''
  })
  handleFilter()
}

const handleSizeChange = (size: number) => {
  pagination.pageSize = size
  loadTableData()
}

const handleCurrentChange = (page: number) => {
  pagination.currentPage = page
  loadTableData()
}

const handleViewDetail = (row: DataAccuracy) => {
  currentVerification.value = row
  detailDialogVisible.value = true
}

const handleRerunVerification = async (row: DataAccuracy) => {
  try {
    await ElMessageBox.confirm(
      `确定要重新验证 ${row.tableName} 的数据准确性吗？`,
      '重新验证确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    loading.value = true
    // 模拟验证过程
    await new Promise(resolve => setTimeout(resolve, 2000))

    ElMessage.success(`已完成 ${row.tableName} 的准确性验证`)
    // 重新加载数据
    loadTableData()
  } catch (error) {
    // 用户取消操作
  } finally {
    loading.value = false
  }
}

const handleRunVerification = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要执行全量数据准确性验证吗？这可能需要较长时间。',
      '执行验证确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    loading.value = true
    // 模拟验证过程
    await new Promise(resolve => setTimeout(resolve, 3000))

    ElMessage.success('全量数据准确性验证已完成')
    // 重新加载数据
    loadTableData()
  } catch (error) {
    // 用户取消操作
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.data-accuracy-table {
  padding: 0;
}

.table-header {
  margin-bottom: 16px;
}

.filter-row {
  margin-bottom: 16px;
}

.input-icon {
  color: #c0c4cc;
  margin-right: 4px;
}

.button-icon {
  margin-right: 4px;
}

.tag-icon {
  margin-right: 2px;
}

.table-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.name-text {
  font-weight: 500;
}

.verification-description {
  line-height: 1.4;
  font-size: 13px;
}

.accuracy-rate {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rate-text {
  font-size: 12px;
  font-weight: 500;
}

.rate-high {
  color: #67c23a;
}

.rate-medium {
  color: #e6a23c;
}

.rate-low {
  color: #f56c6c;
}

.error-zero {
  color: #67c23a;
}

.error-low {
  color: #e6a23c;
}

.error-high {
  color: #f56c6c;
  font-weight: 500;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 16px 0;
}
</style>