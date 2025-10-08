<!-- /components/dataCenter/DataCompletenessTable.vue -->
<template>
  <div class="data-completeness-table">
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
            v-model="filterParams.dataType"
            placeholder="数据类型"
            clearable
            @change="handleFilter"
          >
            <template #prefix>
              <Icon icon="mdi:database" class="input-icon" />
            </template>
            <el-option label="行情数据" value="market" />
            <el-option label="财务数据" value="financial" />
            <el-option label="基础信息" value="basic" />
            <el-option label="ETF数据" value="etf" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="filterParams.completenessStatus"
            placeholder="完整状态"
            clearable
            @change="handleFilter"
          >
            <template #prefix>
              <Icon icon="mdi:chart-box" class="input-icon" />
            </template>
            <el-option label="完整" value="complete" />
            <el-option label="部分缺失" value="partial" />
            <el-option label="严重缺失" value="incomplete" />
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
        </el-col>
      </el-row>
    </div>

    <!-- 表格内容保持不变，只添加图标到操作按钮 -->
    <el-table
      :data="tableData"
      v-loading="loading"
      style="width: 100%"
      :default-sort="{ prop: 'completenessRate', order: 'descending' }"
    >
      <!-- 表格列定义保持不变 -->
      <el-table-column label="操作" width="120" fixed="right">
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
            v-if="row.completenessRate < 95"
            link
            type="warning"
            size="small"
            @click="handleSyncData(row)"
          >
            <Icon icon="mdi:sync" class="button-icon" />
            同步
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

    <!-- 数据表详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="`数据表详情 - ${currentTable?.tableName}`"
      width="800px"
    >
      <DataTableDetail :table-data="currentTable" v-if="detailDialogVisible" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import DataTableDetail from "@/components/dataCenter/DataTableDetail.vue";

// 数据类型定义
interface TableCompleteness {
  id: string
  tableName: string
  tableDescription: string
  dataType: string
  totalRecords: number
  expectedRecords: number
  completenessRate: number
  missingPeriods: string[]
  lastUpdateTime: string
  dataFreshness: string
  isCoreTable: boolean
}

interface FilterParams {
  tableName: string
  dataType: string
  completenessStatus: string
}

interface Pagination {
  currentPage: number
  pageSize: number
  total: number
}

// 响应式数据
const loading = ref(false)
const tableData = ref<TableCompleteness[]>([])
const filterParams = reactive<FilterParams>({
  tableName: '',
  dataType: '',
  completenessStatus: ''
})
const pagination = reactive<Pagination>({
  currentPage: 1,
  pageSize: 20,
  total: 0
})
const detailDialogVisible = ref(false)
const currentTable = ref<TableCompleteness | null>(null)

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

    // 模拟数据 - 基于设计文档中的数据库表
    const mockData: TableCompleteness[] = [
      {
        id: '1',
        tableName: 'stock_daily',
        tableDescription: 'A股日线行情表',
        dataType: 'market',
        totalRecords: 12500000,
        expectedRecords: 12800000,
        completenessRate: 97.7,
        missingPeriods: ['2023-01-03', '2023-05-08', '2023-10-02'],
        lastUpdateTime: '2024-01-15 16:30:00',
        dataFreshness: 'fresh',
        isCoreTable: true
      },
      {
        id: '2',
        tableName: 'stock_basic',
        tableDescription: '股票基础信息表',
        dataType: 'basic',
        totalRecords: 5200,
        expectedRecords: 5500,
        completenessRate: 94.5,
        missingPeriods: [],
        lastUpdateTime: '2024-01-15 09:00:00',
        dataFreshness: 'fresh',
        isCoreTable: true
      },
      {
        id: '3',
        tableName: 'stock_minutes',
        tableDescription: '股票分钟行情表',
        dataType: 'market',
        totalRecords: 185000000,
        expectedRecords: 200000000,
        completenessRate: 92.5,
        missingPeriods: ['2023-12-29 14:30', '2024-01-02 10:15', '2024-01-08 15:45'],
        lastUpdateTime: '2024-01-15 17:00:00',
        dataFreshness: 'fresh',
        isCoreTable: true
      },
      {
        id: '4',
        tableName: 'stock_income_core',
        tableDescription: '利润表核心信息表',
        dataType: 'financial',
        totalRecords: 85000,
        expectedRecords: 95000,
        completenessRate: 89.5,
        missingPeriods: ['2023Q1', '2023Q2', '2023Q3'],
        lastUpdateTime: '2024-01-10 14:20:00',
        dataFreshness: 'stale',
        isCoreTable: false
      },
      {
        id: '5',
        tableName: 'etf_daily',
        tableDescription: 'ETF日线行情',
        dataType: 'etf',
        totalRecords: 3200000,
        expectedRecords: 3300000,
        completenessRate: 97.0,
        missingPeriods: ['2023-11-15'],
        lastUpdateTime: '2024-01-15 16:45:00',
        dataFreshness: 'fresh',
        isCoreTable: false
      },
      {
        id: '6',
        tableName: 'stock_moneyflow',
        tableDescription: '个股资金流向表',
        dataType: 'market',
        totalRecords: 9800000,
        expectedRecords: 10500000,
        completenessRate: 93.3,
        missingPeriods: ['2023-08-14', '2023-09-28'],
        lastUpdateTime: '2024-01-15 17:30:00',
        dataFreshness: 'fresh',
        isCoreTable: false
      }
    ]

    tableData.value = mockData
    pagination.total = mockData.length
  } catch (error) {
    ElMessage.error('数据加载失败')
    console.error('加载数据完整性表格失败:', error)
  } finally {
    loading.value = false
  }
}

// 工具函数
const getDataTypeTagType = (type: string) => {
  const typeMap: { [key: string]: string } = {
    market: 'primary',
    financial: 'success',
    basic: 'info',
    etf: 'warning'
  }
  return typeMap[type] || 'info'
}

const getDataTypeText = (type: string) => {
  const textMap: { [key: string]: string } = {
    market: '行情数据',
    financial: '财务数据',
    basic: '基础信息',
    etf: 'ETF数据'
  }
  return textMap[type] || type
}

const getProgressStatus = (rate: number) => {
  if (rate >= 98) return 'success'
  if (rate >= 95) return 'warning'
  return 'exception'
}

const getRateTextClass = (rate: number) => {
  if (rate >= 98) return 'rate-high'
  if (rate >= 95) return 'rate-medium'
  return 'rate-low'
}

const getFreshnessTagType = (freshness: string) => {
  const freshnessMap: { [key: string]: string } = {
    fresh: 'success',
    stale: 'warning',
    outdated: 'danger'
  }
  return freshnessMap[freshness] || 'info'
}

const getFreshnessText = (freshness: string) => {
  const textMap: { [key: string]: string } = {
    fresh: '最新',
    stale: '较旧',
    outdated: '过时'
  }
  return textMap[freshness] || freshness
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
    dataType: '',
    completenessStatus: ''
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

const handleViewDetail = (row: TableCompleteness) => {
  currentTable.value = row
  detailDialogVisible.value = true
}

const handleSyncData = async (row: TableCompleteness) => {
  try {
    await ElMessageBox.confirm(
      `确定要同步 ${row.tableName} 表的数据吗？`,
      '数据同步确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    loading.value = true
    // 模拟同步操作
    await new Promise(resolve => setTimeout(resolve, 2000))

    ElMessage.success(`开始同步 ${row.tableName} 数据`)
    // 这里实际应该调用后端的同步接口
  } catch (error) {
    // 用户取消操作
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.data-completeness-table {
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

.table-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.name-text {
  font-weight: 500;
}

.completeness-rate {
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

.missing-periods {
  max-height: 200px;
  overflow-y: auto;
}

.period-item {
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
}

.period-item:last-child {
  border-bottom: none;
}

.more-periods {
  padding: 8px 0;
  color: #909399;
  font-style: italic;
  text-align: center;
}

.no-missing {
  color: #67c23a;
  font-size: 12px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 16px 0;
}
</style>