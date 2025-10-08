<!-- /components/dataCenter/AccuracyDetail.vue -->
<template>
  <div class="accuracy-detail" v-if="verificationData">
    <el-descriptions :column="2" border>
      <el-descriptions-item label="数据表">{{ verificationData.tableName }}</el-descriptions-item>
      <el-descriptions-item label="验证类型">
        <el-tag :type="getVerificationTypeTagType(verificationData.verificationType)" size="small">
          {{ getVerificationTypeText(verificationData.verificationType) }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="准确率">
        <span :class="getRateTextClass(verificationData.accuracyRate)">
          {{ verificationData.accuracyRate.toFixed(2) }}%
        </span>
      </el-descriptions-item>
      <el-descriptions-item label="验证状态">
        <el-tag :type="getStatusTagType(verificationData.status)" size="small">
          {{ getStatusText(verificationData.status) }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="检查记录数">{{ formatNumber(verificationData.checkedRecords) }}</el-descriptions-item>
      <el-descriptions-item label="错误记录数">
        <span :class="getErrorCountClass(verificationData.errorRecords)">
          {{ formatNumber(verificationData.errorRecords) }}
        </span>
      </el-descriptions-item>
      <el-descriptions-item label="最后验证时间">{{ verificationData.lastVerificationTime }}</el-descriptions-item>
      <el-descriptions-item label="验证描述" :span="2">
        {{ verificationData.description }}
      </el-descriptions-item>
    </el-descriptions>

    <div class="details-section" v-if="verificationData.details">
      <h4>验证规则详情</h4>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="规则描述">
          {{ verificationData.details.ruleDescription }}
        </el-descriptions-item>
        <el-descriptions-item label="通过率">
          {{ verificationData.details.passRate?.toFixed(2) }}%
        </el-descriptions-item>
      </el-descriptions>

      <div class="validation-rules" v-if="verificationData.details.validationRules">
        <h5>具体验证规则</h5>
        <ul class="rules-list">
          <li v-for="(rule, index) in verificationData.details.validationRules" :key="index">
            {{ rule }}
          </li>
        </ul>
      </div>

      <div class="error-examples" v-if="verificationData.details.errorExamples">
        <h5>错误示例</h5>
        <el-table :data="verificationData.details.errorExamples" size="small" border>
          <el-table-column
            v-for="key in Object.keys(verificationData.details.errorExamples[0] || {})"
            :key="key"
            :prop="key"
            :label="key"
          />
        </el-table>
      </div>
    </div>

    <div class="action-section">
      <el-button type="primary" @click="handleExportReport">
        <Icon icon="mdi:file-export" class="button-icon" />
        导出验证报告
      </el-button>
      <el-button type="warning" @click="handleRerunVerification">
        <Icon icon="mdi:refresh" class="button-icon" />
        重新验证
      </el-button>
      <el-button @click="handleViewRules">
        <Icon icon="mdi:eye" class="button-icon" />
        查看验证规则
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'

interface Props {
  verificationData: any
}

defineProps<Props>()

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

const getRateTextClass = (rate: number) => {
  if (rate >= 99) return 'rate-high'
  if (rate >= 95) return 'rate-medium'
  return 'rate-low'
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

// 事件处理
const handleExportReport = () => {
  ElMessage.success('导出验证报告功能开发中')
}

const handleRerunVerification = () => {
  ElMessage.success('重新验证功能开发中')
}

const handleViewRules = () => {
  ElMessage.success('查看验证规则功能开发中')
}
</script>

<style scoped>
.accuracy-detail {
  padding: 0;
}

.details-section {
  margin-top: 20px;
}

.details-section h4 {
  margin: 0 0 12px 0;
  color: #606266;
}

.validation-rules {
  margin-top: 16px;
}

.validation-rules h5 {
  margin: 16px 0 8px 0;
  color: #606266;
}

.rules-list {
  padding-left: 20px;
  color: #606266;
}

.rules-list li {
  margin-bottom: 4px;
  line-height: 1.4;
}

.error-examples {
  margin-top: 16px;
}

.error-examples h5 {
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

.rate-high {
  color: #67c23a;
  font-weight: 500;
}

.rate-medium {
  color: #e6a23c;
  font-weight: 500;
}

.rate-low {
  color: #f56c6c;
  font-weight: 500;
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
</style>