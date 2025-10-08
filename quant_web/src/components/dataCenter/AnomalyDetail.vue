<!-- /components/dataCenter/AnomalyDetail.vue -->
<template>
  <div class="anomaly-detail" v-if="anomalyData">
    <el-descriptions :column="2" border>
      <el-descriptions-item label="数据表">{{ anomalyData.tableName }}</el-descriptions-item>
      <el-descriptions-item label="异常类型">
        <el-tag :type="getAnomalyTypeTagType(anomalyData.anomalyType)" size="small">
          {{ getAnomalyTypeText(anomalyData.anomalyType) }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="严重程度">
        <el-tag :type="getSeverityTagType(anomalyData.severity)" size="small">
          {{ getSeverityText(anomalyData.severity) }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="处理状态">
        <el-tag :type="getStatusTagType(anomalyData.status)" size="small">
          {{ getStatusText(anomalyData.status) }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="检测时间">{{ anomalyData.detectedTime }}</el-descriptions-item>
      <el-descriptions-item label="影响记录数">
        {{ anomalyData.affectedRecords || 0 }} 条
      </el-descriptions-item>
      <el-descriptions-item label="异常描述" :span="2">
        {{ anomalyData.description }}
      </el-descriptions-item>
      <el-descriptions-item label="建议操作" :span="2">
        {{ anomalyData.suggestedAction }}
      </el-descriptions-item>
    </el-descriptions>

    <div class="details-section" v-if="anomalyData.details">
      <h4>异常详情</h4>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="字段名称" v-if="anomalyData.details.fieldName">
          {{ anomalyData.details.fieldName }}
        </el-descriptions-item>
        <el-descriptions-item label="预期值" v-if="anomalyData.details.expectedValue">
          {{ anomalyData.details.expectedValue }}
        </el-descriptions-item>
        <el-descriptions-item label="实际值" v-if="anomalyData.details.actualValue">
          {{ anomalyData.details.actualValue }}
        </el-descriptions-item>
        <el-descriptions-item label="错误数量" v-if="anomalyData.details.errorCount">
          {{ anomalyData.details.errorCount }} 条
        </el-descriptions-item>
      </el-descriptions>

      <div class="sample-records" v-if="anomalyData.details.sampleRecords">
        <h5>异常记录示例</h5>
        <el-table :data="anomalyData.details.sampleRecords" size="small" border>
          <el-table-column
            v-for="key in Object.keys(anomalyData.details.sampleRecords[0] || {})"
            :key="key"
            :prop="key"
            :label="key"
          />
        </el-table>
      </div>
    </div>

    <div class="action-section">
      <el-button type="primary" @click="handleExportAnomaly">
        <Icon icon="mdi:file-export" class="button-icon" />
        导出异常详情
      </el-button>
      <el-button type="success" @click="handleMarkResolved" v-if="anomalyData.status === 'pending'">
        <Icon icon="mdi:check-circle" class="button-icon" />
        标记为已解决
      </el-button>
      <el-button type="warning" @click="handleIgnore" v-if="anomalyData.status === 'pending'">
        <Icon icon="mdi:eye-off" class="button-icon" />
        忽略此异常
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'

interface Props {
  anomalyData: any
}

defineProps<Props>()

// 工具函数（与主组件中相同）
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

// 事件处理
const handleExportAnomaly = () => {
  ElMessage.success('导出异常详情功能开发中')
}

const handleMarkResolved = () => {
  ElMessage.success('标记解决功能开发中')
}

const handleIgnore = () => {
  ElMessage.success('忽略异常功能开发中')
}
</script>


<style scoped>
.anomaly-detail {
  padding: 0;
}

.details-section {
  margin-top: 20px;
}

.details-section h4 {
  margin: 0 0 12px 0;
  color: #606266;
}

.sample-records {
  margin-top: 16px;
}

.sample-records h5 {
  margin: 16px 0 8px 0;
  color: #606266;
}

.action-section {
  margin-top: 20px;
  text-align: center;
}

.button-icon {
  margin-right: 4px;
}
</style>