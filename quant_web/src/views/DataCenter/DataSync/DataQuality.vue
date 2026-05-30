<!-- views/DataCenter/DataQuality.vue -->
<template>
  <div class="data-quality bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据质量监控</h1>
          <p class="page-description">监控数据完整性、准确性和时效性</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="handleDeleteRecords" :loading="isDeleting" quaternary type="error">
            <template #icon><SmartIcon name="Delete" /></template>
          </n-button>
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Error -->
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

      <!-- Loading skeleton -->
      <template v-else-if="loading">
        <n-grid :x-gap="16" :cols="4" responsive="screen" class="stats-row">
          <n-grid-item v-for="i in 4" :key="i">
            <n-card class="stat-card">
              <n-skeleton :text="true" :repeat="2" />
            </n-card>
          </n-grid-item>
        </n-grid>
        <n-card class="main-card">
          <template #header><n-skeleton :text="true" width="30%" /></template>
          <n-skeleton :text="true" :repeat="6" />
        </n-card>
      </template>

      <template v-else>
        <!-- Stats Cards -->
        <n-grid :x-gap="16" :cols="4" responsive="screen" class="stats-row">
          <n-grid-item>
            <n-card class="stat-card">
              <div class="stat-content">
                <div class="stat-icon" :class="qualityLevelClass">
                  <Icon :icon="qualityLevelIcon" />
                </div>
                <div class="stat-info">
                  <div class="stat-value">{{ qualityScore }}%</div>
                  <div class="stat-label">数据质量评分</div>
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
                  <div class="stat-value">{{ issuesCount }}</div>
                  <div class="stat-label">数据问题</div>
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
                  <div class="stat-value">{{ qualityLevel }}</div>
                  <div class="stat-label">质量等级</div>
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
                  <div class="stat-value">{{ metricsCount }}</div>
                  <div class="stat-label">指标数量</div>
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- Recommendations -->
        <n-card v-if="recommendations.length > 0" class="rec-card">
          <template #header>
            <div class="card-header"><span>改进建议</span></div>
          </template>
          <ul class="rec-list">
            <li v-for="(rec, i) in recommendations" :key="i" class="rec-item">
              <Icon icon="mdi:lightbulb-outline" class="rec-icon" />
              {{ rec }}
            </li>
          </ul>
        </n-card>

        <!-- Detail Tabs -->
        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>数据质量详情</span>
              <n-button type="primary" size="small" @click="refreshData" :loading="loading">检查质量</n-button>
            </div>
          </template>

          <n-tabs v-model:value="activeTab">
            <n-tab-pane name="completeness" tab="完整性检查">
              <DataCompletenessTable :metrics="qualityData?.metrics ?? []" />
            </n-tab-pane>
            <n-tab-pane name="accuracy" tab="准确性验证">
              <DataAccuracyTable :metrics="qualityData?.metrics ?? []" />
            </n-tab-pane>
            <n-tab-pane name="anomalies" tab="异常监控">
              <DataAnomaliesTable :issues="qualityData?.issues ?? []" />
            </n-tab-pane>
          </n-tabs>
        </n-card>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  useMessage,
  useDialog,
  NButton,
  NCard,
  NGrid,
  NGridItem,
  NTabs,
  NTabPane,
  NSkeleton,
  NResult,
} from "naive-ui";
import { useRouter } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import DataCompletenessTable from "@/components/data/DataCompletenessTable.vue";
import DataAccuracyTable from "@/components/data/DataAccuracyTable.vue";
import DataAnomaliesTable from "@/components/data/DataAnomaliesTable.vue";
import { Icon } from "@iconify/vue";
import { dataSyncService } from "@/api/data-sync";
import type { DataQualityResponse } from "@/api/data-sync";
import { useQualityMetrics } from "@/composables/useQualityMetrics";

const message = useMessage();
const dialog = useDialog();
const loading = ref(false);
const error = ref(false);
const isDeleting = ref(false);
const activeTab = ref("completeness");
const router = useRouter();
const qualityData = ref<DataQualityResponse | null>(null);

const {
  qualityScore,
  qualityLevel,
  qualityLevelClass,
  qualityLevelIcon,
  issuesCount,
  metricsCount,
  recommendations,
} = useQualityMetrics(qualityData);

const handleBack = () => {
  router.push("/data/sync");
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    qualityData.value = await dataSyncService.getDataQuality();
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const refreshData = async () => {
  loading.value = true;
  try {
    qualityData.value = await dataSyncService.runQualityCheck();
    message.success("质量检查完成");
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleDeleteRecords = () => {
  dialog.warning({
    title: "确认清空质量记录",
    content: "将删除所有数据质量检查记录，此操作不可恢复。确定继续吗？",
    positiveText: "确认删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      isDeleting.value = true;
      try {
        const result = await dataSyncService.deleteQualityRecords();
        message.success(`已删除 ${result.deleted} 条质量记录`);
        await loadData();
      } catch {
        message.error("删除失败");
      } finally {
        isDeleting.value = false;
      }
    },
  });
};

onMounted(() => loadData());
</script>

<style lang="scss" scoped>
@use "@/styles/variables" as *;
@use "@/styles/mixins" as mixin;
@use "sass:map";

.data-quality {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
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
.stat-icon.danger {
  background: rgba($danger-color, 0.1);
  color: $danger-color;
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

.rec-card {
  margin-bottom: map.get($spacers, 4);
  border-radius: $border-radius-large;
}

.rec-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rec-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: var(--n-text-color-2);
  font-size: 13px;
  line-height: 1.5;
}

.rec-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--n-warning-color);
}

.main-card {
  border-radius: $border-radius-large;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
