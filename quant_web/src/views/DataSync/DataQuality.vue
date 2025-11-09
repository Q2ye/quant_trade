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
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color' as sassColor;

.data-quality {
  padding: map.get($spacers, 4);
  background: $primary-bg;
  min-height: 100vh;
}

.page-header {
  background: $page-header-bg;
  color: white;
  padding: map.get($spacers, 4) 0;
  margin-bottom: map.get($spacers, 4);

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 map.get($spacers, 4);

    .header-actions-right {
      display: flex;
      align-items: center;
      gap: map.get($spacers, 2);
    }
  }

  .title-section {
    flex: 1;

    .page-title {
      margin: 0;
      font-size: $page-title-font-size;
      font-weight: $font-weight-bold;
      color: white;
    }

    .page-description {
      margin: map.get($spacers, 1) 0 0 0;
      opacity: 0.9;
      font-size: $page-description-font-size;
      color: rgba(255, 255, 255, 0.9);
    }
  }
}

.back-btn {
  @include mixin.button-base(rgba(255, 255, 255, 0.15), white);
  border: 1px solid rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(10px);
  box-shadow: $card-shadow;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
  }
}

.stats-row {
  margin-bottom: map.get($spacers, 4);
}

.stat-card {
  @include mixin.card-base;
  border-radius: $border-radius-lg;
}

.stat-content {
  display: flex;
  align-items: center;
  padding: map.get($spacers, 2);
}

.stat-icon {
  width: $status-icon-size;
  height: $status-icon-size;
  border-radius: $border-radius;
  @include mixin.flex-center;
  margin-right: map.get($spacers, 3);
  font-size: 1.5rem;
}

.stat-icon.success {
  background: rgba($success-color, 0.1);
  color: $success-color;
}

.stat-icon.warning {
  background: rgba($warning-color, 0.1);
  color: $warning-color;
}

.stat-icon.info {
  background: rgba($info-color, 0.1);
  color: $info-color;
}

.stat-icon.primary {
  background: rgba($accent-color, 0.1);
  color: $accent-color;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: $font-weight-bold;
  color: $text-primary;
  line-height: 1.2;
}

.stat-label {
  @include mixin.text-secondary;
  margin-top: map.get($spacers, 1);
}

.main-card {
  @include mixin.card-base;
  border-radius: $border-radius-lg;

  :deep(.el-card__header) {
    background: $toolbar-bg;
    border-bottom: 1px solid $border-color;
    padding: map.get($spacers, 3);
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  :deep(.el-button) {
    @include mixin.button-base;

    &.el-button--primary {
      background-color: $accent-color;
      border-color: $accent-color;

      &:hover {
        background-color: sassColor.adjust($accent-color, $lightness: -10%);
        border-color: sassColor.adjust($accent-color, $lightness: -10%);
      }
    }
  }
}

:deep(.el-tabs) {
  .el-tabs__header {
    background: $secondary-bg;
    padding: 0 map.get($spacers, 3);
    margin: 0;
  }

  .el-tabs__nav-wrap::after {
    background-color: $border-color;
  }

  .el-tabs__item {
    color: $text-secondary;
    font-weight: $font-weight-medium;

    &.is-active {
      color: $accent-color;
    }

    &:hover {
      color: $accent-color;
    }
  }

  .el-tabs__active-bar {
    background-color: $accent-color;
  }
}

// 响应式调整
@include mixin.media-breakpoint-down(md) {
  .page-header .header-content {
    flex-direction: column;
    gap: map.get($spacers, 3);
    align-items: center;
    text-align: center;

    .header-actions-right {
      order: -1;
      align-self: flex-end;
      margin-bottom: map.get($spacers, 2);
    }
  }
}
</style>