<template>
  <div class="data-sync-overview bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据同步概览</h1>
          <p class="page-description">统一管理数据同步任务，监控数据质量和同步状态</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="checkSyncStatus" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
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
          <n-button type="primary" @click="checkSyncStatus">重试</n-button>
        </template>
      </n-result>

      <!-- Loading skeleton -->
      <template v-else-if="loading">
        <div class="sync-index-grid">
          <n-card v-for="i in 2" :key="i" class="sync-index-card">
            <n-skeleton :text="true" :repeat="3" />
          </n-card>
        </div>
        <h2 class="sync-section-title">
          <Icon icon="mdi:apps" class="title-icon" />功能导航
        </h2>
        <div class="function-grid">
          <n-card v-for="i in 3" :key="i" class="function-nav-card">
            <n-skeleton :text="true" :repeat="3" />
          </n-card>
        </div>
      </template>

      <template v-else>
        <!-- 同步状态 -->
        <div class="index-overview content-section">
          <h2 class="sync-section-title">
            <Icon icon="ant-design:sync-outlined" class="title-icon" />同步状态
          </h2>
          <div class="sync-index-grid">
            <!-- 当前同步任务 -->
            <n-card class="sync-index-card task-card" hoverable @click="navigateTo('/data/sync')">
              <div class="index-content">
                <div class="index-header">
                  <div class="index-name">当前同步任务</div>
                  <div class="index-code">
                    {{ isRunning ? '进行中' : (syncStatus?.updated_at ? formatDate(syncStatus.updated_at) : '--') }}
                  </div>
                </div>

                <template v-if="isRunning">
                  <div class="task-progress-area">
                    <n-progress
                      :percentage="syncStatus?.progress?.progress_percentage || 0"
                      :height="8" :border-radius="4"
                      class="task-progress-bar"
                    />
                    <div class="task-metrics">
                      <div class="metric-item">
                        <span class="metric-value">{{ syncStatus?.progress?.completed_tasks || 0 }}/{{ syncStatus?.progress?.total_tasks || 0 }}</span>
                        <span class="metric-label">子任务</span>
                      </div>
                      <div class="metric-item">
                        <span class="metric-value">{{ elapsedTime }}s</span>
                        <span class="metric-label">已用时间</span>
                      </div>
                      <div class="metric-item">
                        <span class="metric-value">{{ estimatedRemainingTime }}s</span>
                        <span class="metric-label">预计剩余</span>
                      </div>
                    </div>
                  </div>
                  <div v-if="subTasks.length > 0" class="sub-task-row">
                    <span v-for="st in subTasks" :key="st.data_type" class="sub-task-dot" :class="st.status"
                      :title="`${st.data_type}: ${subTaskStatusText(st.status)}`">
                      <Icon :icon="subTaskIcon(st.status)" class="sub-task-icon" />
                      <span class="sub-task-name">{{ st.data_type }}</span>
                    </span>
                  </div>
                </template>

                <template v-else>
                  <div class="idle-state">
                    <Icon icon="ant-design:check-circle-outlined" class="idle-icon" />
                    <span class="idle-text">{{ syncStatus?.results?.length ? '最近一次同步完成' : '暂未执行过同步任务' }}</span>
                    <n-button size="small" type="primary" @click.stop="navigateTo('/data/sync')">开始同步</n-button>
                  </div>
                </template>
              </div>
            </n-card>

            <!-- 数据质量 -->
            <n-card class="sync-index-card quality-card" hoverable @click="navigateTo('/data/sync/quality')">
              <div class="index-content">
                <div class="index-header">
                  <div class="index-name">全库数据质量</div>
                  <div class="index-code" :class="qualityLevelClass">{{ qualityLevel }}</div>
                </div>
                <div class="quality-score-area">
                  <div class="score-ring" :class="qualityLevelClass">
                    <span class="score-number">{{ qualityScore }}</span>
                    <span class="score-unit">分</span>
                  </div>
                  <div class="quality-metrics">
                    <div class="quality-row">
                      <span class="q-label">完整性</span><span class="q-value">{{ qualityCompleteness }}%</span>
                    </div>
                    <div class="quality-row">
                      <span class="q-label">及时性</span><span class="q-value">{{ qualityTimeliness }}%</span>
                    </div>
                    <div class="quality-row">
                      <span class="q-label">准确性</span><span class="q-value">{{ qualityAccuracy }}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </n-card>
          </div>
        </div>

        <!-- 功能导航 -->
        <div class="function-nav content-section">
          <h2 class="sync-section-title">
            <Icon icon="mdi:apps" class="title-icon" />功能导航
          </h2>
          <div class="function-grid">
            <n-card class="function-nav-card" hoverable @click="navigateTo('/data/sync')">
              <div class="function-content">
                <div class="function-header">
                  <div class="function-icon accent"><Icon icon="ant-design:setting-outlined" /></div>
                  <h3 class="function-title">数据同步</h3>
                </div>
                <div class="function-info">
                  <p class="function-description">自定义数据类型同步数据</p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">支持类型:</span>
                      <span class="stat-value">{{ supportedTypesCount }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最近同步:</span>
                      <span class="stat-value">{{ lastSyncTime }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </n-card>

            <n-card class="function-nav-card" hoverable @click="navigateTo('/data/sync/quality')">
              <div class="function-content">
                <div class="function-header">
                  <div class="function-icon danger"><Icon icon="ant-design:check-circle-outlined" /></div>
                  <h3 class="function-title">数据质量</h3>
                </div>
                <div class="function-info">
                  <p class="function-description">数据完整性和质量检查</p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">评分:</span>
                      <span class="stat-value">{{ qualityScore }}分</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">问题:</span>
                      <span class="stat-value" :class="{ danger: issuesCount > 0 }">{{ issuesCount }}</span>
                    </div>
                  </div>
                  <div class="function-footer">
                    <span class="update-time">检查时间: {{ qualityCheckTime }}</span>
                  </div>
                </div>
              </div>
            </n-card>

            <n-card class="function-nav-card" hoverable @click="navigateTo('/data/sync/history')">
              <div class="function-content">
                <div class="function-header">
                  <div class="function-icon info"><Icon icon="ant-design:history-outlined" /></div>
                  <h3 class="function-title">同步历史</h3>
                </div>
                <div class="function-info">
                  <p class="function-description">查看历史同步任务记录</p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">完成:</span>
                      <span class="stat-value success">{{ historyStats.completed }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">失败:</span>
                      <span class="stat-value danger">{{ historyStats.failed }}</span>
                    </div>
                  </div>
                  <div class="function-footer">
                    <span class="update-time">最近更新: {{ historyStats.lastSync }}</span>
                  </div>
                </div>
              </div>
            </n-card>
          </div>
        </div>

        <!-- 实时监控 -->
        <div class="sync-hotspots content-section">
          <h2 class="sync-section-title">
            <Icon icon="ant-design:monitor-outlined" class="title-icon" />实时监控
          </h2>
          <div class="hotspot-grid">
            <n-card class="hotspot-card" :bordered="true" size="small">
              <template #header>
                <div class="card-header">
                  <div class="card-title">
                    <Icon icon="ant-design:cloud-download-outlined" class="card-title-icon" />当前任务进度
                  </div>
                  <n-button text size="small" @click="checkSyncStatus">刷新状态</n-button>
                </div>
              </template>
              <div class="progress-list">
                <div v-if="isRunning" class="progress-item">
                  <div class="progress-info">
                    <div class="progress-name">批量数据同步</div>
                    <div class="progress-details">
                      {{ syncStatus?.progress?.completed_tasks || 0 }}/{{ syncStatus?.progress?.total_tasks || 0 }} 任务完成
                    </div>
                  </div>
                  <n-progress
                    :percentage="syncStatus?.progress?.progress_percentage || 0"
                    :status="syncStatus?.status === 'failed' ? 'error' : 'success'"
                  />
                  <div class="progress-time">已运行: {{ elapsedTime }}s | 预计剩余: {{ estimatedRemainingTime }}s</div>
                </div>
                <div v-else class="no-task">
                  <div class="no-task-icon"><Icon icon="ant-design:check-circle-outlined" /></div>
                  <div class="no-task-text">暂无运行中的任务</div>
                  <n-button type="primary" size="small" @click="navigateTo('/data/sync')">开始新任务</n-button>
                </div>
              </div>
            </n-card>

            <n-card class="hotspot-card" :bordered="true" size="small">
              <template #header>
                <div class="card-header">
                  <div class="card-title">
                    <Icon icon="ant-design:history-outlined" class="card-title-icon" />最近同步记录
                  </div>
                  <n-button text size="small" @click="navigateTo('/data/sync/history')">查看全部</n-button>
                </div>
              </template>
              <div class="history-list">
                <div v-for="record in recentHistory" :key="record.id" class="history-item">
                  <div class="item-icon">
                    <Icon :icon="record.status === 'completed' ? 'ant-design:check-circle-outlined' : 'ant-design:close-circle-outlined'"
                      :class="record.status === 'completed' ? 'up' : 'down'" />
                  </div>
                  <div class="history-info">
                    <div class="history-type">{{ record.data_types.join(", ") }}</div>
                    <div class="history-time">{{ record.start_time }}</div>
                  </div>
                  <div class="history-status">
                    <n-tag :type="record.status === 'completed' ? 'success' : 'error'" size="small">
                      {{ record.status === 'completed' ? '完成' : '失败' }}
                    </n-tag>
                  </div>
                </div>
                <div v-if="recentHistory.length === 0" class="no-history">暂无同步记录</div>
              </div>
            </n-card>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { NResult, NSkeleton, NTag, NProgress } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { dataSyncService } from "@/api/data-sync";
import type { DataTypeInfo, DataQualityResponse, SyncResultItem, SyncTaskRecord } from "@/api/data-sync";
import { useQualityMetrics } from "@/composables/useQualityMetrics";
import { useSyncTimer } from "@/composables/useSyncTimer";
import { useSyncEventHandler } from "@/composables/useSyncEventHandler";

const router = useRouter();
const loading = ref(false);
const error = ref(false);

const syncStatus = ref<any>(null);
const supportedTypes = ref<DataTypeInfo[]>([]);
const qualityData = ref<DataQualityResponse | null>(null);
const recentTasks = ref<SyncTaskRecord[]>([]);

const { isRunning, elapsedTime, estimatedRemainingTime } = useSyncTimer(syncStatus);
const {
  qualityScore, qualityLevel, qualityLevelClass,
  qualityCompleteness, qualityTimeliness, qualityAccuracy,
  issuesCount, qualityCheckTime,
} = useQualityMetrics(qualityData);

useSyncEventHandler(syncStatus, {
  onCompleted() { checkSyncStatus(); },
  onFailed() { checkSyncStatus(); },
  onCancelled() { checkSyncStatus(); },
});

const supportedTypesCount = computed(() => supportedTypes.value.length);

const lastSyncTime = computed(() => {
  if (!syncStatus.value?.updated_at) return "--";
  try { return new Date(syncStatus.value.updated_at).toLocaleDateString("zh-CN"); }
  catch { return syncStatus.value.updated_at; }
});

// --- sub-task display ---

const subTasks = computed(() => {
  const results = syncStatus.value?.results;
  if (results && results.length > 0) {
    return results.map((r: SyncResultItem) => ({
      data_type: r.data_type,
      status: r.success ? ("completed" as const) : ("failed" as const),
    }));
  }
  const progress = syncStatus.value?.progress;
  if (progress && progress.total_tasks > 0) {
    const items: { data_type: string; status: "completed" | "running" | "pending" | "failed" }[] = [];
    for (let i = 0; i < progress.total_tasks; i++) {
      items.push({
        data_type: `任务${i + 1}`,
        status: i < progress.completed_tasks ? "completed" : "pending",
      });
    }
    if (progress.current_task) {
      const idx = items.findIndex((t) => t.status === "pending");
      if (idx >= 0) items[idx] = { ...items[idx], status: "running", data_type: progress.current_task! };
    }
    return items;
  }
  return [];
});

const subTaskStatusText = (s: string) => ({ completed: "完成", running: "进行中", failed: "失败", pending: "等待中" }[s] || s);
const subTaskIcon = (s: string) => ({
  completed: "ant-design:check-circle-filled", failed: "ant-design:close-circle-filled",
  running: "ant-design:sync-outlined", pending: "ant-design:clock-circle-outlined",
}[s] || "ant-design:clock-circle-outlined");

// --- history stats (from real task list) ---

const historyStats = computed(() => {
  const tasks = recentTasks.value;
  const completed = tasks.filter((t) => t.status === "completed").length;
  const failed = tasks.filter((t) => t.status === "failed").length;
  const last = tasks.length > 0
    ? (() => { try { return new Date(tasks[0].start_time || "").toLocaleDateString("zh-CN"); } catch { return "--"; } })()
    : "--";
  return { completed, failed, lastSync: last };
});

// --- recent history (from real task list) ---

const recentHistory = computed(() => {
  return recentTasks.value.slice(0, 5).map((t) => ({
    id: t.task_id,
    data_types: t.data_types && t.data_types.length > 0 ? t.data_types : [t.task_type],
    status: t.status,
    start_time: (() => { try { return t.start_time ? new Date(t.start_time).toLocaleString("zh-CN") : "--"; } catch { return "--"; } })(),
  }));
});

// --- helpers ---

const navigateTo = (path: string) => router.push(path);

const formatDate = (timeString: string) => {
  if (!timeString) return "--";
  try { return new Date(timeString).toLocaleDateString("zh-CN"); }
  catch { return timeString; }
};

const checkSyncStatus = async () => {
  loading.value = true;
  error.value = false;
  try {
    const [status, types, quality, tasksResult] = await Promise.all([
      dataSyncService.getSyncStatus().catch(() => null),
      dataSyncService.getSupportedDataTypes().catch(() => [] as DataTypeInfo[]),
      dataSyncService.getDataQuality().catch(() => null),
      dataSyncService.getSyncTasks({ limit: 10 }).catch(() => ({ success: true, tasks: [], total: 0 })),
    ]);
    syncStatus.value = status;
    supportedTypes.value = types;
    qualityData.value = quality;
    recentTasks.value = tasksResult.tasks || [];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  checkSyncStatus();
});
</script>

<style lang="scss" scoped>
@use "@/styles/data/data-sync-overview";
</style>
