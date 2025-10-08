<!-- /components/dataCenter/DataTableDetail.vue -->
<template>
  <div class="data-table-detail" v-if="tableData">
    <el-descriptions :column="2" border>
      <el-descriptions-item label="表名">{{ tableData.tableName }}</el-descriptions-item>
      <el-descriptions-item label="描述">{{ tableData.tableDescription }}</el-descriptions-item>
      <el-descriptions-item label="数据类型">
        <el-tag :type="getDataTypeTagType(tableData.dataType)" size="small">
          {{ getDataTypeText(tableData.dataType) }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="是否核心表">
        <el-tag :type="tableData.isCoreTable ? 'success' : 'info'" size="small">
          <Icon icon="mdi:star" class="tag-icon" />
          {{ tableData.isCoreTable ? '是' : '否' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="总记录数">{{ formatNumber(tableData.totalRecords) }}</el-descriptions-item>
      <el-descriptions-item label="预期记录数">{{ formatNumber(tableData.expectedRecords) }}</el-descriptions-item>
      <el-descriptions-item label="完整率">
        <span :class="getRateTextClass(tableData.completenessRate)">
          {{ tableData.completenessRate.toFixed(2) }}%
        </span>
      </el-descriptions-item>
      <el-descriptions-item label="缺失记录数">
        {{ formatNumber(tableData.expectedRecords - tableData.totalRecords) }}
      </el-descriptions-item>
      <el-descriptions-item label="最后更新时间" :span="2">
        <Icon icon="mdi:clock-outline" class="desc-icon" />
        {{ tableData.lastUpdateTime }}
      </el-descriptions-item>
      <el-descriptions-item label="数据新鲜度" :span="2">
        <el-tag :type="getFreshnessTagType(tableData.dataFreshness)" size="small">
          <Icon icon="mdi:update" class="tag-icon" />
          {{ getFreshnessText(tableData.dataFreshness) }}
        </el-tag>
      </el-descriptions-item>
    </el-descriptions>

    <div class="missing-section" v-if="tableData.missingPeriods && tableData.missingPeriods.length > 0">
      <h4>
        <Icon icon="mdi:alert-circle" class="section-icon" />
        缺失时段详情
      </h4>
      <el-timeline>
        <el-timeline-item
          v-for="(period, index) in tableData.missingPeriods"
          :key="index"
          :timestamp="period"
          type="warning"
        >
          <Icon icon="mdi:calendar-remove" class="timeline-icon" />
          数据缺失
        </el-timeline-item>
      </el-timeline>
    </div>

    <div class="action-section">
      <el-button type="primary" @click="handleExportReport">
        <Icon icon="mdi:file-export" class="button-icon" />
        导出报告
      </el-button>
      <el-button type="warning" @click="handleSyncNow">
        <Icon icon="mdi:sync" class="button-icon" />
        立即同步
      </el-button>
      <el-button @click="handleViewSchema">
        <Icon icon="mdi:table-eye" class="button-icon" />
        查看表结构
      </el-button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'

interface Props {
  tableData: any
}

defineProps<Props>()

// 工具函数（与主组件中相同）
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

// 事件处理
const handleExportReport = () => {
  ElMessage.success('导出报告功能开发中')
}

const handleSyncNow = () => {
  ElMessage.success('开始同步数据...')
}

const handleViewSchema = () => {
  ElMessage.success('查看表结构功能开发中')
}
</script>


<style scoped>
.data-table-detail {
  padding: 0;
}

.missing-section {
  margin-top: 20px;
  padding: 16px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.missing-section h4 {
  margin: 0 0 12px 0;
  color: #606266;
  display: flex;
  align-items: center;
}

.section-icon {
  margin-right: 8px;
}

.timeline-icon {
  margin-right: 8px;
}

.desc-icon {
  margin-right: 4px;
}

.tag-icon {
  margin-right: 2px;
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
</style>