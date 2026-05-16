<template>
  <div class="data-sync-overview sidebar-layout-container no-bleed-through">
    <div class="common-page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据同步概览</h1>
          <p class="page-description">
            统一管理数据同步任务，监控数据质量和同步状态
          </p>
        </div>
        <div class="header-actions">
          <n-button class="refresh-btn" @click="checkSyncStatus">
            <Icon icon="ant-design:reload-outlined" />
            <span class="btn-text">刷新状态</span>
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
            <n-button type="primary" @click="checkSyncStatus">重试</n-button>
          </template>
        </n-result>

        <template v-else>
          <div class="index-overview">
            <h2 class="sync-section-title">
              <Icon icon="ant-design:sync-outlined" class="title-icon" />
              同步状态
            </h2>
            <div class="sync-index-grid">
              <n-card class="sync-index-card" hoverable>
                <div class="index-content">
                  <div class="index-header">
                    <div class="index-name">同步状态</div>
                    <div class="index-code">实时</div>
                  </div>
                  <div class="status-content">
                    <div
                      class="status-icon"
                      :class="getStatusClass(syncStatus)"
                    >
                      <Icon icon="ant-design:sync-outlined" />
                    </div>
                    <div class="status-info">
                      <div class="index-value">{{ statusText }}</div>
                      <div class="index-change">
                        <span class="change-value"
                          >{{ syncStatus?.completed_tasks || 0 }}/{{
                            syncStatus?.total_tasks || 0
                          }}</span
                        >
                        <span class="change-percent">任务完成</span>
                      </div>
                    </div>
                  </div>
                </div>
              </n-card>

              <n-card class="sync-index-card" hoverable>
                <div class="index-content">
                  <div class="index-header">
                    <div class="index-name">任务进度</div>
                    <div class="index-code">百分比</div>
                  </div>
                  <div class="status-content">
                    <div class="status-icon progress">
                      <Icon icon="ant-design:cloud-download-outlined" />
                    </div>
                    <div class="status-info">
                      <div class="index-value">
                        {{ syncStatus?.progress || 0 }}%
                      </div>
                      <div class="index-change">
                        <span class="change-value"
                          >{{ estimatedRemainingTime }}s</span
                        >
                        <span class="change-percent">预计剩余</span>
                      </div>
                    </div>
                  </div>
                </div>
              </n-card>

              <n-card class="sync-index-card" hoverable>
                <div class="index-content">
                  <div class="index-header">
                    <div class="index-name">运行时间</div>
                    <div class="index-code">秒数</div>
                  </div>
                  <div class="status-content">
                    <div class="status-icon time">
                      <Icon icon="ant-design:clock-circle-outlined" />
                    </div>
                    <div class="status-info">
                      <div class="index-value">
                        {{ syncStatus?.elapsed_time || 0 }}s
                      </div>
                      <div class="index-change">
                        <span class="change-value">{{
                          syncConfig.batch_size
                        }}</span>
                        <span class="change-percent">批量大小</span>
                      </div>
                    </div>
                  </div>
                </div>
              </n-card>

              <n-card class="sync-index-card" hoverable>
                <div class="index-content">
                  <div class="index-header">
                    <div class="index-name">数据质量</div>
                    <div class="index-code">评分</div>
                  </div>
                  <div class="status-content">
                    <div class="status-icon remaining">
                      <Icon icon="ant-design:check-circle-outlined" />
                    </div>
                    <div class="status-info">
                      <div class="index-value">
                        {{ qualityStats.completeness }}%
                      </div>
                      <div class="index-change">
                        <span class="change-value"
                          >{{ selectedTypesCount }}/{{
                            supportedTypesCount
                          }}</span
                        >
                        <span class="change-percent">已选类型</span>
                      </div>
                    </div>
                  </div>
                </div>
              </n-card>
            </div>
          </div>

          <div class="function-nav">
            <h2 class="sync-section-title">
              <Icon icon="mdi:apps" class="title-icon" />
              功能导航
            </h2>
            <div class="function-grid">
              <n-card
                class="function-nav-card"
                hoverable
                @click="navigateTo('/events-sync')"
              >
                <div class="function-content">
                  <div class="function-header">
                    <div class="function-icon accent">
                      <Icon icon="ant-design:setting-outlined" />
                    </div>
                    <h3 class="function-title">数据同步</h3>
                  </div>
                  <div class="function-info">
                    <p class="function-description">自定义数据类型同步数据</p>
                    <div class="function-stats">
                      <div class="stat-item">
                        <span class="stat-label">支持类型:</span
                        ><span class="stat-value">{{
                          supportedTypesCount
                        }}</span>
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">已选类型:</span
                        ><span class="stat-value">{{
                          selectedTypesCount
                        }}</span>
                      </div>
                    </div>
                    <div class="function-footer">
                      <span class="update-time"
                        >批量大小: {{ syncConfig.batch_size }}</span
                      >
                    </div>
                  </div>
                </div>
              </n-card>

              <n-card
                class="function-nav-card"
                hoverable
                @click="navigateTo('/events-quality')"
              >
                <div class="function-content">
                  <div class="function-header">
                    <div class="function-icon danger">
                      <Icon icon="ant-design:check-circle-outlined" />
                    </div>
                    <h3 class="function-title">数据质量</h3>
                  </div>
                  <div class="function-info">
                    <p class="function-description">数据完整性和质量检查</p>
                    <div class="function-stats">
                      <div class="stat-item">
                        <span class="stat-label">完整性:</span
                        ><span class="stat-value"
                          >{{ qualityStats.completeness }}%</span
                        >
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">及时性:</span
                        ><span class="stat-value"
                          >{{ qualityStats.timeliness }}%</span
                        >
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">准确性:</span
                        ><span class="stat-value"
                          >{{ qualityStats.accuracy }}%</span
                        >
                      </div>
                    </div>
                    <div class="function-footer">
                      <span class="update-time"
                        >检查时间: {{ qualityStats.checkTime }}</span
                      >
                    </div>
                  </div>
                </div>
              </n-card>

              <n-card
                class="function-nav-card"
                hoverable
                @click="navigateTo('/events-sync/tasks')"
              >
                <div class="function-content">
                  <div class="function-header">
                    <div class="function-icon purple">
                      <Icon icon="ant-design:monitor-outlined" />
                    </div>
                    <h3 class="function-title">任务监控</h3>
                  </div>
                  <div class="function-info">
                    <p class="function-description">实时监控同步任务状态</p>
                    <div class="function-stats">
                      <div class="stat-item">
                        <span class="stat-label">运行中:</span
                        ><span class="stat-value">{{
                          monitorStats.running
                        }}</span>
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">已完成:</span
                        ><span class="stat-value">{{
                          monitorStats.completed
                        }}</span>
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">等待中:</span
                        ><span class="stat-value">{{
                          monitorStats.pending
                        }}</span>
                      </div>
                    </div>
                    <div class="function-footer">
                      <span class="update-time"
                        >更新: {{ monitorStats.updateTime }}</span
                      >
                    </div>
                  </div>
                </div>
              </n-card>

              <n-card
                class="function-nav-card"
                hoverable
                @click="navigateTo('/events-sync/history')"
              >
                <div class="function-content">
                  <div class="function-header">
                    <div class="function-icon info">
                      <Icon icon="ant-design:history-outlined" />
                    </div>
                    <h3 class="function-title">同步历史</h3>
                  </div>
                  <div class="function-info">
                    <p class="function-description">查看历史同步任务记录</p>
                    <div class="function-stats">
                      <div class="stat-item">
                        <span class="stat-label">总任务数:</span
                        ><span class="stat-value">{{
                          historyStats.total
                        }}</span>
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">成功:</span
                        ><span class="stat-value success">{{
                          historyStats.completed
                        }}</span>
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">失败:</span
                        ><span class="stat-value danger">{{
                          historyStats.failed
                        }}</span>
                      </div>
                    </div>
                    <div class="function-footer">
                      <span class="update-time"
                        >最近同步: {{ historyStats.lastSync }}</span
                      >
                    </div>
                  </div>
                </div>
              </n-card>
            </div>
          </div>

          <div class="sync-hotspots">
            <h2 class="sync-section-title">
              <Icon icon="ant-design:monitor-outlined" class="title-icon" />
              实时监控
            </h2>
            <div class="hotspot-grid">
              <n-card class="hotspot-card" :bordered="true" size="small">
                <template #header>
                  <div class="card-header">
                    <div class="card-title">
                      <Icon
                        icon="ant-design:cloud-download-outlined"
                        class="card-title-icon"
                      />
                      当前任务进度
                    </div>
                    <n-button text size="small" @click="checkSyncStatus"
                      >刷新状态</n-button
                    >
                  </div>
                </template>
                <div class="progress-list">
                  <div v-if="syncStatus?.is_running" class="progress-item">
                    <div class="progress-info">
                      <div class="progress-name">批量数据同步</div>
                      <div class="progress-details">
                        {{ syncStatus.completed_tasks }}/{{
                          syncStatus.total_tasks
                        }}
                        任务完成
                      </div>
                    </div>
                    <n-progress
                      :percentage="syncStatus.progress"
                      :status="syncStatus.error ? 'error' : 'success'"
                    />
                    <div class="progress-time">
                      已运行: {{ syncStatus.elapsed_time }}s | 预计剩余:
                      {{ estimatedRemainingTime }}s
                    </div>
                  </div>
                  <div v-else class="no-task">
                    <div class="no-task-icon">
                      <Icon icon="ant-design:check-circle-outlined" />
                    </div>
                    <div class="no-task-text">暂无运行中的任务</div>
                    <n-button
                      type="primary"
                      size="small"
                      @click="navigateTo('/events-sync/config')"
                      >开始新任务</n-button
                    >
                  </div>
                </div>
              </n-card>

              <n-card class="hotspot-card" :bordered="true" size="small">
                <template #header>
                  <div class="card-header">
                    <div class="card-title">
                      <Icon
                        icon="ant-design:history-outlined"
                        class="card-title-icon"
                      />
                      最近同步记录
                    </div>
                    <n-button
                      text
                      size="small"
                      @click="navigateTo('/events-sync/history')"
                      >查看全部</n-button
                    >
                  </div>
                </template>
                <div class="history-list">
                  <div
                    v-for="record in recentHistory"
                    :key="record.id"
                    class="history-item"
                  >
                    <div class="item-icon">
                      <Icon
                        :icon="getHistoryIcon(record.status)"
                        :class="getHistoryIconClass(record.status)"
                      />
                    </div>
                    <div class="history-info">
                      <div class="history-type">
                        {{ record.data_types.join(", ") }}
                      </div>
                      <div class="history-time">
                        {{ formatTime(record.start_time) }}
                      </div>
                    </div>
                    <div class="history-status">
                      <n-tag
                        :type="getStatusTagType(record.status)"
                        size="small"
                        >{{ getStatusText(record.status) }}</n-tag
                      >
                    </div>
                  </div>
                  <div v-if="recentHistory.length === 0" class="no-history">
                    暂无同步记录
                  </div>
                </div>
              </n-card>
            </div>
          </div>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { NResult, NSpin } from "naive-ui";

const router = useRouter();
const loading = ref(false);
const error = ref(false);

const syncStatus = ref({
  is_running: false,
  progress: 0,
  total_tasks: 0,
  completed_tasks: 0,
  elapsed_time: 0,
  error: null,
});

const syncConfig = ref({ data_types: [], days: 30, batch_size: 100 });

const supportedDataTypes = ref([
  { code: "stock_basic", name: "股票列表" },
  { code: "trade_calendar", name: "交易日历" },
  { code: "daily", name: "日线行情" },
  { code: "moneyflow", name: "资金流向" },
  { code: "etf", name: "ETF数据" },
]);

const historyStats = ref({
  total: 156,
  completed: 142,
  failed: 8,
  lastSync: "2024-01-15 15:30",
});

const getStatusClass = (data: any) => {
  if (data?.is_running) return "running";
  if (data?.error) return "remaining";
  return "time";
};

const getHistoryIcon = (status: string) => {
  const icons: Record<string, string> = {
    completed: "ant-design:check-circle-outlined",
    running: "ant-design:sync-outlined",
    failed: "ant-design:close-circle-outlined",
    cancelled: "ant-design:stop-outlined",
  };
  return icons[status] || "ant-design:question-circle-outlined";
};

const getHistoryIconClass = (status: string) => {
  const classes: Record<string, string> = {
    completed: "up",
    running: "flat",
    failed: "down",
    cancelled: "flat",
  };
  return classes[status] || "flat";
};

const monitorStats = ref({
  running: 1,
  completed: 142,
  pending: 0,
  updateTime: "刚刚",
});

const qualityStats = ref({
  completeness: 98.5,
  timeliness: 99.2,
  accuracy: 99.8,
  checkTime: "2024-01-15 16:00",
});

const recentHistory = ref([
  {
    id: "1",
    data_types: ["日线行情", "资金流向"],
    status: "completed",
    start_time: "2024-01-15T15:30:00Z",
  },
  {
    id: "2",
    data_types: ["股票列表", "ETF数据"],
    status: "completed",
    start_time: "2024-01-15T14:20:00Z",
  },
  {
    id: "3",
    data_types: ["全量同步"],
    status: "failed",
    start_time: "2024-01-14T22:10:00Z",
  },
]);

const statusText = computed(() => {
  if (!syncStatus.value) return "未知";
  if (syncStatus.value.error) return "错误";
  if (syncStatus.value.is_running) return "同步中";
  if (syncStatus.value.progress === 100) return "已完成";
  return "就绪";
});

const estimatedRemainingTime = computed(() => {
  if (!syncStatus.value || !syncStatus.value.is_running) return 0;
  const elapsed = syncStatus.value.elapsed_time || 0;
  const progress = syncStatus.value.progress || 0;
  if (progress <= 0) return 0;
  return Math.round((elapsed / progress) * (100 - progress));
});

const supportedTypesCount = computed(() => supportedDataTypes.value.length);
const selectedTypesCount = computed(() => syncConfig.value.data_types.length);

const navigateTo = (path: string) => router.push(path);

const checkSyncStatus = async () => {
  loading.value = true;
  error.value = false;
  try {
    syncStatus.value = await new Promise((resolve) => {
      setTimeout(
        () =>
          resolve({
            is_running: false,
            progress: 0,
            total_tasks: 0,
            completed_tasks: 0,
            elapsed_time: 0,
            error: null,
          }),
        500,
      );
    });
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const formatTime = (timeString: string) => {
  if (!timeString) return "--";
  try {
    return new Date(timeString).toLocaleString("zh-CN");
  } catch {
    return timeString;
  }
};

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    completed: "完成",
    running: "运行中",
    failed: "失败",
    cancelled: "已取消",
  };
  return texts[status] || status;
};

const getStatusTagType = (status: string) => {
  const types: Record<string, string> = {
    completed: "success",
    running: "primary",
    failed: "error",
    cancelled: "warning",
  };
  return (types[status] as any) || "info";
};

onMounted(() => checkSyncStatus());
</script>

<style lang="scss" scoped>
@use "@/styles/data/data-sync-overview";
</style>
