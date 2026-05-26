<!-- views/DataCenter/DataQuality.vue -->
<template>
  <div class="data-quality">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据质量监控</h1>
          <p class="page-description">监控数据完整性、准确性和时效性</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-spin :show="loading">
        <n-result
          v-if="error"
          status="500"
          title="数据加载失败"
          description="请检查网络连接后重试"
        >
          <template #footer>
            <n-button type="primary" @click="loadData">重试</n-button>
          </template>
        </n-result>

        <template v-else>
          <n-grid :x-gap="16" :cols="4" responsive="screen" class="stats-row">
            <n-grid-item>
              <n-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon success">
                    <Icon icon="mdi:check-circle" />
                  </div>
                  <div class="stat-info">
                    <div class="stat-value">98.5%</div>
                    <div class="stat-label">数据完整性</div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon warning">
                    <Icon icon="mdi:alert-circle" />
                  </div>
                  <div class="stat-info">
                    <div class="stat-value">23</div>
                    <div class="stat-label">数据异常</div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon info">
                    <Icon icon="mdi:clock" />
                  </div>
                  <div class="stat-info">
                    <div class="stat-value">99.2%</div>
                    <div class="stat-label">数据时效性</div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
            <n-grid-item>
              <n-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon primary-accent">
                    <Icon icon="mdi:database" />
                  </div>
                  <div class="stat-info">
                    <div class="stat-value">1.2TB</div>
                    <div class="stat-label">数据总量</div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>

          <n-card class="main-card">
            <template #header>
              <div class="card-header">
                <span>数据质量详情</span>
                <n-button type="primary" @click="refreshData">刷新数据</n-button>
              </div>
            </template>

            <n-tabs v-model:value="activeTab">
              <n-tab-pane name="completeness" tab="完整性检查">
                <DataCompletenessTable />
              </n-tab-pane>
              <n-tab-pane name="accuracy" tab="准确性验证">
                <DataAccuracyTable />
              </n-tab-pane>
              <n-tab-pane name="anomalies" tab="异常监控">
                <DataAnomaliesTable />
              </n-tab-pane>
            </n-tabs>
          </n-card>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  useMessage,
  NButton,
  NCard,
  NGrid,
  NGridItem,
  NTabs,
  NTabPane,
  NSpin,
  NResult,
} from "naive-ui";
import { useRouter } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import DataCompletenessTable from "@/components/data/DataCompletenessTable.vue";
import DataAccuracyTable from "@/components/data/DataAccuracyTable.vue";
import DataAnomaliesTable from "@/components/data/DataAnomaliesTable.vue";
import { Icon } from "@iconify/vue";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
const activeTab = ref("completeness");
const router = useRouter();

const handleBack = () => {
  router.push("/data/sync/overview");
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const refreshData = () => loadData().then(() => message.success("数据已刷新"));

onMounted(() => loadData());
</script>

<style lang="scss" scoped>
@use "@/styles/variables" as *;
@use "@/styles/mixins" as mixin;
@use "sass:map";
@use "sass:color" as sassColor;

.data-quality {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

/* .page-header 已迁移至全局样式（global.scss） */

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;

  /* .action-btn 圆形成样式已迁移至全局 global.scss */
}

.stats-row {
  margin-bottom: map.get($spacers, 4);
}

.stat-card {
  border-radius: $border-radius-large;
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

.stat-icon.primary-accent {
  background: rgba($primary-color, 0.1);
  color: $primary-color;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: $font-weight-bold;
  color: $text-color-1;
  line-height: 1.2;
}

.stat-label {
  @include mixin.text-secondary;
  margin-top: map.get($spacers, 1);
}

.main-card {
  border-radius: $border-radius-large;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

// 响应式：.page-header 已迁移至全局样式（global.scss）
</style>
