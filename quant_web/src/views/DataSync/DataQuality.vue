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
          <n-button class="back-btn" @click="handleBack">
            <template #icon>
              <SmartIcon name="ArrowLeft" />
            </template>
            返回
          </n-button>
        </div>
      </div>
    </div>

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
import DataCompletenessTable from "@/components/dataCenter/DataCompletenessTable.vue";
import DataAccuracyTable from "@/components/dataCenter/DataAccuracyTable.vue";
import DataAnomaliesTable from "@/components/dataCenter/DataAnomaliesTable.vue";
import { Icon } from "@iconify/vue";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
const activeTab = ref("completeness");
const router = useRouter();

const handleBack = () => {
  router.go(-1);
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
  padding: map.get($spacers, 4);
  background: $body-color;
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
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
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
