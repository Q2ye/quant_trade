<!-- /components/dataCenter/DataAnomaliesTable.vue -->
<template>
  <div class="data-anomalies-table">
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
            v-model="filterParams.anomalyType"
            placeholder="异常类型"
            clearable
            @change="handleFilter"
          >
            <template #prefix>
              <Icon icon="mdi:alert-circle" class="input-icon" />
            </template>
            <el-option label="数据缺失" value="missing" />
            <el-option label="数据异常" value="outlier" />
            <el-option label="格式错误" value="format" />
            <el-option label="逻辑错误" value="logic" />
            <el-option label="重复数据" value="duplicate" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="filterParams.severity"
            placeholder="严重程度"
            clearable
            @change="handleFilter"
          >
            <template #prefix>
              <Icon icon="mdi:alert" class="input-icon" />
            </template>
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="严重" value="critical" />
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
          <el-button type="warning" @click="handleExportAnomalies">
            <Icon icon="mdi:file-export" class="button-icon" />
            导出异常报告
          </el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 表格内容保持不变，只添加图标到操作按钮 -->
    <el-table
      :data="tableData"
      v-loading="loading"
      style="width: 100%"
      :default-sort="{ prop: 'detectedTime', order: 'descending' }"
    >
      <!-- 表格列定义保持不变 -->
      <el-table-column label="操作" width="180" fixed="right">
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
            v-if="row.status === 'pending'"
            link
            type="success"
            size="small"
            @click="handleMarkResolved(row)"
          >
            <Icon icon="mdi:check-circle" class="button-icon" />
            标记解决
          </el-button>
          <el-button
            v-if="row.status === 'pending'"
            link
            type="warning"
            size="small"
            @click="handleIgnoreAnomaly(row)"
          >
            <Icon icon="mdi:eye-off" class="button-icon" />
            忽略
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

    <!-- 异常详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="`异常详情 - ${currentAnomaly?.tableName}`"
      width="900px"
    >
      <AnomalyDetail :anomaly-data="currentAnomaly" v-if="detailDialogVisible" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import AnomalyDetail from "@/components/dataCenter/AnomalyDetail.vue";

// 数据类型定义
interface DataAnomaly {
  id: string
  tableName: string
  anomalyType: string
  description: string
  severity: string
  detectedTime: string
  status: string
  suggestedAction: string
  affectedRecords?: number
  isCoreTable: boolean
  details?: {
    fieldName?: string
    expectedValue?: any
    actualValue?: any
    errorCount?: number
    sampleRecords?: any[]
  }
}

interface FilterParams {
  tableName: string
  anomalyType: string
  severity: string
}

interface Pagination {
  currentPage: number
  pageSize: number
  total: number
}

// 响应式数据
const loading = ref(false)
const tableData = ref<DataAnomaly[]>([])
const filterParams = reactive<FilterParams>({
  tableName: '',
  anomalyType: '',
  severity: ''
})
const pagination = reactive<Pagination>({
  currentPage: 1,
  pageSize: 20,
  total: 0
})
const detailDialogVisible = ref(false)
const currentAnomaly = ref<DataAnomaly | null>(null)

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

    // 模拟异常数据
    const mockData: DataAnomaly[] = [
      {
        id: '1',
        tableName: 'stock_daily',
        anomalyType: 'outlier',
        description: '收盘价异常波动，超过3倍标准差',
        severity: 'high',
        detectedTime: '2024-01-15 18:30:00',
        status: 'pending',
        suggestedAction: '检查数据源，验证异常价格',
        affectedRecords: 23,
        isCoreTable: true,
        details: {
          fieldName: 'close',
          expectedValue: '正常价格区间',
          actualValue: '异常高价',
          errorCount: 23,
          sampleRecords: [
            { ts_code: '000001.SZ', trade_date: '2024-01-15', close: 150.50 },
            { ts_code: '600000.SH', trade_date: '2024-01-15', close: 145.80 }
          ]
        }
      },
      {
        id: '2',
        tableName: 'stock_basic',
        anomalyType: 'missing',
        description: '新上市股票基础信息缺失',
        severity: 'medium',
        detectedTime: '2024-01-15 17:45:00',
        status: 'pending',
        suggestedAction: '同步最新股票基础信息',
        affectedRecords: 5,
        isCoreTable: true
      },
      {
        id: '3',
        tableName: 'stock_minutes',
        anomalyType: 'format',
        description: '分钟数据时间戳格式错误',
        severity: 'low',
        detectedTime: '2024-01-15 16:20:00',
        status: 'resolved',
        suggestedAction: '已修复时间戳格式',
        affectedRecords: 1200,
        isCoreTable: true
      },
      {
        id: '4',
        tableName: 'stock_income_core',
        anomalyType: 'logic',
        description: '利润表数据逻辑错误：营业收入 < 营业成本',
        severity: 'critical',
        detectedTime: '2024-01-15 15:30:00',
        status: 'pending',
        suggestedAction: '验证财务数据准确性',
        affectedRecords: 8,
        isCoreTable: false
      },
      {
        id: '5',
        tableName: 'etf_daily',
        anomalyType: 'duplicate',
        description: 'ETF日线数据重复记录',
        severity: 'medium',
        detectedTime: '2024-01-15 14:15:00',
        status: 'ignored',
        suggestedAction: '清理重复数据',
        affectedRecords: 45,
        isCoreTable: false
      },
      {
        id: '6',
        tableName: 'stock_moneyflow',
        anomalyType: 'outlier',
        description: '资金流向数据异常：净流入量异常大',
        severity: 'high',
        detectedTime: '2024-01-15 13:45:00',
        status: 'pending',
        suggestedAction: '检查资金流向计算逻辑',
        affectedRecords: 12,
        isCoreTable: false
      }
    ]

    tableData.value = mockData
    pagination.total = mockData.length
  } catch (error) {
    ElMessage.error('数据加载失败')
    console.error('加载异常监控数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 工具函数
const getAnomalyTypeTagType = (type: string) => {
  const typeMap: { [key: string]: string } = {
    missing: 'warning',
    outlier: 'danger',
    format: 'info',
    logic: 'danger',
    duplicate: 'warning'
  }
  return typeMap[type] || 'info'
}

const getAnomalyTypeText = (type: string) => {
  const textMap: { [key: string]: string } = {
    missing: '数据缺失',
    outlier: '数据异常',
    format: '格式错误',
    logic: '逻辑错误',
    duplicate: '重复数据'
  }
  return textMap[type] || type
}

const getSeverityTagType = (severity: string) => {
  const severityMap: { [key: string]: string } = {
    low: 'info',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return severityMap[severity] || 'info'
}

const getSeverityText = (severity: string) => {
  const textMap: { [key: string]: string } = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '严重'
  }
  return textMap[severity] || severity
}

const getStatusTagType = (status: string) => {
  const statusMap: { [key: string]: string } = {
    pending: 'warning',
    resolved: 'success',
    ignored: 'info'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: { [key: string]: string } = {
    pending: '待处理',
    resolved: '已解决',
    ignored: '已忽略'
  }
  return textMap[status] || status
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
    anomalyType: '',
    severity: ''
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

const handleViewDetail = (row: DataAnomaly) => {
  currentAnomaly.value = row
  detailDialogVisible.value = true
}

const handleMarkResolved = async (row: DataAnomaly) => {
  try {
    await ElMessageBox.confirm(
      `确定要将该异常标记为已解决吗？`,
      '标记解决确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 模拟API调用
    loading.value = true
    await new Promise(resolve => setTimeout(resolve, 500))

    row.status = 'resolved'
    ElMessage.success('异常已标记为已解决')
  } catch (error) {
    // 用户取消操作
  } finally {
    loading.value = false
  }
}

const handleIgnoreAnomaly = async (row: DataAnomaly) => {
  try {
    await ElMessageBox.confirm(
      `确定要忽略该异常吗？忽略后将从监控列表中移除。`,
      '忽略异常确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 模拟API调用
    loading.value = true
    await new Promise(resolve => setTimeout(resolve, 500))

    row.status = 'ignored'
    ElMessage.success('异常已忽略')
  } catch (error) {
    // 用户取消操作
  } finally {
    loading.value = false
  }
}

const handleExportAnomalies = () => {
  ElMessage.success('开始导出异常报告...')
  // 实际实现中这里会调用导出API
}
</script>

<style scoped>
.data-anomalies-table {
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

.anomaly-description {
  line-height: 1.4;
}

.affected-records {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.suggested-action {
  color: #e6a23c;
  font-size: 12px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 16px 0;
}
</style>