<!-- views/DataCenter/DataQuality.vue -->
<template>
  <div class="data-quality">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据质量监控</h1>
          <p class="page-description">监控数据完整性、准确性和时效性</p>
        </div>
        <div class="header-actions-right">
          <a-button class="back-btn" @click="handleBack">
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon success">
              <Icon icon="mdi:check-circle"/>
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
              <Icon icon="mdi:alert-circle"/>
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
              <Icon icon="mdi:clock"/>
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
              <Icon icon="mdi:database"/>
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
          <DataCompletenessTable/>
        </el-tab-pane>
        <el-tab-pane label="准确性验证" name="accuracy">
          <DataAccuracyTable/>
        </el-tab-pane>
        <el-tab-pane label="异常监控" name="anomalies">
          <DataAnomaliesTable/>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {ref} from 'vue'
import {ElMessage} from 'element-plus'
import {useRouter} from 'vue-router'
import {ArrowLeftOutlined} from '@ant-design/icons-vue'
import DataCompletenessTable from "@/components/dataCenter/DataCompletenessTable.vue";
import DataAccuracyTable from "@/components/dataCenter/DataAccuracyTable.vue";
import DataAnomaliesTable from "@/components/dataCenter/DataAnomaliesTable.vue";
import {Icon} from '@iconify/vue'

const activeTab = ref('completeness')
const router = useRouter()

const handleBack = () => {
  router.go(-1)
}

const refreshData = () => {
  ElMessage.success('数据已刷新')
}
</script>

<style lang="scss" scoped>

.data-quality {
  padding: var(--spacer-4);
  background: var(--primary-bg);
  min-height: 100vh;
}

.page-header {
  background: var(--page-header-bg);
  color: white;
  padding: var(--spacer-4) 0;
  margin-bottom: var(--spacer-4);

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 var(--spacer-4);
    position: relative;


    .header-actions-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }

  .title-section {
    flex: 1;

    .page-title {
      margin: 0;
      font-size: 1.5rem;
      font-weight: 600;
      color: white;
    }

    .page-description {
      margin: var(--spacer-1) 0 0 0;
      opacity: 0.9;
      font-size: 0.875rem;
      color: rgba(255, 255, 255, 0.9);
    }
  }
}

// 返回按钮样式
.back-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  border-radius: var(--border-radius);
  font-weight: 500;
  transition: all var(--transition-fast);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:active {
    transform: translateY(0);
  }
}

.stats-row {
  margin-bottom: var(--spacer-4);
}

.stat-card {
  border-radius: var(--border-radius-lg);
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  transition: all var(--transition-normal);

  &:hover {
    transform: var(--hover-transform);
    box-shadow: var(--hover-shadow);
  }
}

.stat-content {
  display: flex;
  align-items: center;
  padding: var(--spacer-2);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--border-radius);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--spacer-3);
  font-size: 1.5rem;
}

.stat-icon.success {
  background: rgba(var(--success-color-rgb), 0.1);
  color: var(--success-color);
}

.stat-icon.warning {
  background: rgba(var(--warning-color-rgb), 0.1);
  color: var(--warning-color);
}

.stat-icon.info {
  background: rgba(var(--info-color-rgb), 0.1);
  color: var(--info-color);
}

.stat-icon.primary {
  background: rgba(var(--accent-color-rgb), 0.1);
  color: var(--accent-color);
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-top: var(--spacer-1);
}

.main-card {
  border-radius: var(--border-radius-lg);
  background: var(--card-bg);
  border: 1px solid var(--border-color);

  :deep(.el-card__header) {
    background: var(--toolbar-bg);
    border-bottom: 1px solid var(--border-color);
    padding: var(--spacer-3);
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  :deep(.el-button) {
    // 使用 CSS 变量替代 mixin
    padding: 8px 16px;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all var(--transition-fast);
    background-color: var(--accent-color);
    color: white;

    &:hover {
      background-color: var(--accent-color-dark);
      transform: translateY(-1px);
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }

    &.el-button--primary {
      background-color: var(--accent-color);
      border-color: var(--accent-color);

      &:hover {
        background-color: var(--accent-color-dark);
        border-color: var(--accent-color-dark);
      }
    }
  }
}

:deep(.el-tabs) {
  .el-tabs__header {
    background: var(--secondary-bg);
    padding: 0 var(--spacer-3);
    margin: 0;
  }

  .el-tabs__nav-wrap::after {
    background-color: var(--border-color);
  }

  .el-tabs__item {
    color: var(--text-secondary);
    font-weight: 500;

    &.is-active {
      color: var(--accent-color);
    }

    &:hover {
      color: var(--accent-color);
    }
  }

  .el-tabs__active-bar {
    background-color: var(--accent-color);
  }
}

// 响应式调整
@media (max-width: 768px) {
  .page-header .header-content {
    flex-direction: column;
    gap: var(--spacer-3);
    align-items: center;
    text-align: center;

    .header-actions-right {
      order: -1;
      align-self: flex-end;
      margin-bottom: var(--spacer-2);
    }
  }
}
</style>