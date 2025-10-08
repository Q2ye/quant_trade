<!-- views/DataCenter/DataQuality.vue -->
<template>
  <div class="data-quality">
    <div class="page-header">
      <h1>数据质量监控</h1>
      <p>监控数据完整性、准确性和时效性</p>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon success">
              <Icon icon="mdi:check-circle" />
            </div>
            <div class="stat-info">
              <div class="stat-value">98.5%</div>
              <div class="stat-label">数据完整性</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon warning">
              <Icon icon="mdi:alert-circle" />
            </div>
            <div class="stat-info">
              <div class="stat-value">23</div>
              <div class="stat-label">数据异常</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon info">
              <Icon icon="mdi:clock" />
            </div>
            <div class="stat-info">
              <div class="stat-value">99.2%</div>
              <div class="stat-label">数据时效性</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon primary">
              <Icon icon="mdi:database" />
            </div>
            <div class="stat-info">
              <div class="stat-value">1.2TB</div>
              <div class="stat-label">数据总量</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>数据质量详情</span>
          <el-button type="primary" @click="refreshData">刷新数据</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="完整性检查" name="completeness">
          <DataCompletenessTable />
        </el-tab-pane>
        <el-tab-pane label="准确性验证" name="accuracy">
          <DataAccuracyTable />
        </el-tab-pane>
        <el-tab-pane label="异常监控" name="anomalies">
          <DataAnomaliesTable />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import DataCompletenessTable from "@/components/dataCenter/DataCompletenessTable.vue";
import DataAccuracyTable from "@/components/dataCenter/DataAccuracyTable.vue";
import DataAnomaliesTable from "@/components/dataCenter/DataAnomaliesTable.vue";

const activeTab = ref('completeness')

const refreshData = () => {
  ElMessage.success('数据已刷新')
}
</script>

<style scoped>
.data-quality {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  color: #303133;
  font-size: 24px;
}

.page-header p {
  margin: 8px 0 0;
  color: #909399;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 8px;
}

.stat-content {
  display: flex;
  align-items: center;
  padding: 8px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  font-size: 24px;
}

.stat-icon.success {
  background: #f0f9ff;
  color: #1890ff;
}

.stat-icon.warning {
  background: #fef6e6;
  color: #e6a23c;
}

.stat-icon.info {
  background: #f0f9eb;
  color: #67c23a;
}

.stat-icon.primary {
  background: #fdf4ff;
  color: #722ed1;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  color: #909399;
  font-size: 14px;
}

.main-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>