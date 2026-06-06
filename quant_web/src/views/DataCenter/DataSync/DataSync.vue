<!-- DataSync.vue - 数据同步主页 -->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import {
  useMessage,
  useDialog,
  NCard,
  NButton,
  NGrid,
  NGridItem,
  NInputNumber,
  NSelect,
  NCollapse,
  NCollapseItem,
  NDatePicker,
  NInput,
  NAlert,
  NFormItem,
  NSkeleton,
  NResult,
  NTag,
  NModal,
  NCheckbox,
  NSpace,
  NDivider,
} from "naive-ui";
import { useRouter, useRoute } from "vue-router";
import type {
  BatchSyncRequest,
  DataTypeInfo,
  SyncResponse,
  SyncStatusResponse,
  SyncTaskItem,
  DataQualityResponse,
} from "@/api/data-sync";
import { dataSyncService } from "@/api/data-sync";
import type { SyncTaskRecord } from "@/api/data-sync";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { useSyncTimer } from "@/composables/useSyncTimer";
import { useSyncEventHandler } from "@/composables/useSyncEventHandler";
import { useQualityMetrics } from "@/composables/useQualityMetrics";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();
const route = useRoute();

// --- 页面状态 ---
const pageLoading = ref(true);
const pageError = ref(false);
const isLoading = ref(false);
const isFullLoading = ref(false);
const isCheckingStatus = ref(false);
const statusPollingInterval = ref<ReturnType<typeof setInterval> | null>(null);
const lastWsEventTime = ref(0);

const syncStatus = ref<SyncStatusResponse | null>(null);
const supportedDataTypes = ref<DataTypeInfo[]>([]);
const qualityData = ref<DataQualityResponse | null>(null);
const recentTasks = ref<SyncTaskRecord[]>([]);
const currentTaskId = ref<string>("");

const { isRunning, formattedElapsedTime, formattedRemainingTime } = useSyncTimer(syncStatus);
const { qualityScore } = useQualityMetrics(qualityData);

// --- 同步配置 ---
const syncConfig = reactive({
  data_types: [] as string[],
  start_date: "",
  end_date: "",
  exchange: "",
  batch_size: 100,
});

const exchangeOptions = [
  { label: "上交所", value: "SSE" },
  { label: "深交所", value: "SZSE" },
  { label: "北交所", value: "BSE" },
];

const datePickerFormatted = computed({
  get: () => (syncConfig.start_date ? new Date(syncConfig.start_date).getTime() : null),
  set: (val: number | null) => {
    syncConfig.start_date = val ? new Date(val).toISOString().slice(0, 10) : "";
  },
});

const endDateFormatted = computed({
  get: () => (syncConfig.end_date ? new Date(syncConfig.end_date).getTime() : null),
  set: (val: number | null) => {
    syncConfig.end_date = val ? new Date(val).toISOString().slice(0, 10) : "";
  },
});

// --- 派生数据 ---
const statusText = computed(() => {
  if (!syncStatus.value) return "就绪";
  const s = syncStatus.value.status;
  if (s === "failed") return "同步失败";
  if (s === "running") return "同步中";
  if (s === "completed") return "同步完成";
  if (s === "pending") return "等待中";
  if (s === "cancelled") return "已取消";
  if (s === "idle") return "就绪";
  if (s === "partial") return "部分成功";
  return "就绪";
});

const statusBarClass = computed(() => {
  if (isRunning.value) return "running";
  const s = syncStatus.value?.status;
  if (s === "completed") return "completed";
  if (s === "failed") return "failed";
  if (s === "pending") return "pending";
  if (s === "cancelled") return "cancelled";
  if (s === "partial") return "partial";
  return "idle";
});

const statusHint = computed(() => {
  const s = syncStatus.value?.status;
  if (s === "completed") return `最近同步完成 — ${lastSyncTime.value}`;
  if (s === "failed") return syncStatus.value?.message || "同步任务执行失败，请查看历史记录";
  if (s === "partial") return "部分任务成功，部分失败，请查看历史记录";
  if (s === "idle" || !syncStatus.value) return "选择数据类型后点击「开始同步」";
  return syncStatus.value?.message || "选择数据类型后点击「开始同步」";
});

const lastSyncTime = computed(() => {
  const t = syncStatus.value?.updated_at;
  if (!t) return "--";
  try { return new Date(t).toLocaleString("zh-CN"); } catch { return t; }
});

const historySummary = computed(() => {
  const tasks = recentTasks.value;
  const completed = tasks.filter((t) => t.status === "completed").length;
  const failed = tasks.filter((t) => t.status === "failed").length;
  return { completed, failed, total: tasks.length };
});

const subTaskDots = computed(() => {
  const isSyncRunning = syncStatus.value?.status === "running";
  const results = syncStatus.value?.results;
  if (results && results.length > 0) {
    // 按 data_type 去重，避免历史任务重复展示
    const seen = new Set<string>();
    const deduped: typeof results = [];
    for (const r of results) {
      if (!seen.has(r.data_type)) {
        seen.add(r.data_type);
        deduped.push(r);
      }
    }
    return deduped.map((r: any) => {
      const cancelled = r.cancelled || r.status === "cancelled";
      const success = isSyncRunning ? false : r.success;
      const status = isSyncRunning ? "running" : cancelled ? "cancelled" : (success ? "completed" : "failed");
      const icon = isSyncRunning ? "ant-design:sync-outlined" : cancelled ? "ant-design:warning-filled" : (success ? "ant-design:check-circle-filled" : "ant-design:close-circle-filled");
      return { label: r.data_type, status, icon };
    });
  }
  const progress = syncStatus.value?.progress;
  if (progress && progress.total_tasks > 0) {
    const dots: { label: string; status: "completed" | "running" | "pending"; icon: string }[] = [];
    for (let i = 0; i < progress.total_tasks; i++) {
      const isDone = i < progress.completed_tasks;
      const isRunningTask = i === progress.completed_tasks && progress.current_task;
      dots.push({
        label: isRunningTask && progress.current_task ? progress.current_task : `任务${i + 1}`,
        status: isDone ? "completed" : isRunningTask ? "running" : "pending",
        icon: isDone ? "ant-design:check-circle-filled" : isRunningTask ? "ant-design:sync-outlined" : "ant-design:clock-circle-outlined",
      });
    }
    return dots;
  }
  return [];
});

const formatDataTypeDisplay = (t: SyncTaskRecord): string => {
  const types = t.data_types && t.data_types.length > 0 ? t.data_types : [t.task_type];
  return types.map(code => {
    const info = supportedDataTypes.value.find(dt => dt.code === code);
    return info ? info.name : code;
  }).join(" · ");
};

const recentHistoryDisplay = computed(() => {
  return recentTasks.value.slice(0, 3).map((t) => {
    const startTime = t.start_time ? (() => { try { return new Date(t.start_time).toLocaleString("zh-CN"); } catch { return t.start_time; } })() : "--";
    return {
      id: t.task_id,
      data_type: formatDataTypeDisplay(t),
      status: t.status,
      start_time: startTime,
      records: t.total_records || 0,
      statusLabel: t.status === "completed" ? "完成" : t.status === "failed" ? "失败" : t.status === "running" ? "运行中" : t.status === "pending" ? "等待中" : t.status === "cancelled" ? "已取消" : t.status,
      statusType: (t.status === "completed" ? "success" : t.status === "failed" ? "error" : t.status === "running" ? "info" : t.status === "cancelled" ? "warning" : "default") as "success" | "error" | "info" | "warning" | "default",
    };
  });
});

// --- WS 事件 ---
useSyncEventHandler(syncStatus, {
  onStarted(taskId: string) {
    lastWsEventTime.value = Date.now();
    currentTaskId.value = taskId;
    if (!statusPollingInterval.value) startStatusPolling();
  },
  onCompleted() { stopStatusPolling(); currentTaskId.value = ""; refreshRecentTasks(); refreshQualityData(); },
  onFailed() { stopStatusPolling(); currentTaskId.value = ""; refreshRecentTasks(); refreshQualityData(); },
  onCancelled() { stopStatusPolling(); currentTaskId.value = ""; refreshRecentTasks(); refreshQualityData(); },
});

// --- 数据加载 ---
const initializePage = async () => {
  pageLoading.value = true;
  pageError.value = false;
  try {
    const [status, types, quality, tasksResult] = await Promise.all([
      dataSyncService.getSyncStatus().catch(() => null),
      dataSyncService.getSupportedDataTypes().catch(() => [] as DataTypeInfo[]),
      dataSyncService.getDataQuality().catch(() => null),
      dataSyncService.getSyncTasks({ limit: 10 }).catch(() => ({ success: true, tasks: [], total: 0 })),
    ]);
    syncStatus.value = status;
    supportedDataTypes.value = [...types].sort((a, b) => {
      if (a.is_available === false && b.is_available !== false) return 1;
      if (a.is_available !== false && b.is_available === false) return -1;
      return 0;
    });
    qualityData.value = quality;
    recentTasks.value = tasksResult.tasks || [];

    if (status?.status === "running") {
      currentTaskId.value = status.task_id || "";
      startStatusPolling();
    }
  } catch {
    pageError.value = true;
  } finally {
    pageLoading.value = false;
  }
};

const refreshRecentTasks = async () => {
  try {
    const result = await dataSyncService.getSyncTasks({ limit: 10 });
    recentTasks.value = result.tasks || [];
  } catch { /* 静默失败 */ }
};

const refreshQualityData = async () => {
  try {
    const q = await dataSyncService.getDataQuality();
    qualityData.value = q;
  } catch { /* 静默失败 */ }
};

const checkSyncStatus = async () => {
  isCheckingStatus.value = true;
  try {
    const status = await dataSyncService.getSyncStatus();
    syncStatus.value = status;
    if (status.status === "running" && !statusPollingInterval.value) startStatusPolling();
    else if (status.status !== "running" && statusPollingInterval.value) stopStatusPolling();
  } catch {
    message.error("获取同步状态失败");
  } finally {
    isCheckingStatus.value = false;
  }
};

// --- 轮询 ---
const startStatusPolling = () => {
  if (statusPollingInterval.value) return;
  statusPollingInterval.value = setInterval(async () => {
    try {
      const wsActive = Date.now() - lastWsEventTime.value < 5000;
      const status = currentTaskId.value
        ? await dataSyncService.getSyncStatus(currentTaskId.value)
        : await dataSyncService.getSyncStatus();
      if (wsActive) {
        if (syncStatus.value) {
          syncStatus.value.results = status.results;
          syncStatus.value.updated_at = status.updated_at;
          syncStatus.value.message = status.message;
        }
      } else {
        syncStatus.value = status;
      }
      if (status.status !== "running" && status.status !== "pending") {
        stopStatusPolling();
        currentTaskId.value = "";
        refreshRecentTasks();
        refreshQualityData();
      }
    } catch {
      // 超时不中止轮询，任务可能仍在运行
    }
  }, 3000);
};

const stopStatusPolling = () => {
  if (statusPollingInterval.value) {
    clearInterval(statusPollingInterval.value);
    statusPollingInterval.value = null;
  }
};

// --- 同步操作 ---
const handleBatchSync = async () => {
  if (!syncConfig.data_types.length) {
    message.warning("请选择至少一种数据类型");
    return;
  }
  isLoading.value = true;
  try {
    const tasks: SyncTaskItem[] = syncConfig.data_types.map((dt) => {
      const item: SyncTaskItem = { data_type: dt };
      if (syncConfig.start_date) item.start_date = syncConfig.start_date;
      if (syncConfig.end_date) item.end_date = syncConfig.end_date;
      return item;
    });
    const response: SyncResponse = await dataSyncService.batchSyncData({
      tasks,
      priority: "medium",
      notify_on_complete: true,
    });
    message.success(response.message);
    if (response.task_id) {
      currentTaskId.value = response.task_id;
      startStatusPolling();
    }
  } catch {
    message.error("连接服务器失败，请检查后端服务");
  } finally {
    isLoading.value = false;
    refreshRecentTasks();
  }
};

const showFullSyncModal = ref(false);
const fullSyncSelected = reactive<Record<string, boolean>>({});

const fullSyncGroups = computed(() => {
  const groups: { label: string; types: DataTypeInfo[] }[] = [];
  const available = supportedDataTypes.value.filter(t => t.is_available !== false);
  const core = available.filter(t => t.is_core);
  const extended = available.filter(t => !t.is_core && !t.code.includes("minute") && !t.code.includes("tick"));
  if (core.length) groups.push({ label: "核心 · 默认选中", types: core });
  if (extended.length) groups.push({ label: "扩展 · 需手动勾选", types: extended });
  return groups;
});

const openFullSyncModal = () => {
  if (isRunning.value) {
    message.warning("已有同步任务正在进行中");
    return;
  }
  supportedDataTypes.value.forEach(t => {
    fullSyncSelected[t.code] = t.is_core;
  });
  showFullSyncModal.value = true;
};

const executeFullSync = async () => {
  const selectedTypes = Object.entries(fullSyncSelected)
    .filter(([, v]) => v)
    .map(([k]) => k);
  if (!selectedTypes.length) {
    message.warning("请至少选择一种数据类型");
    return;
  }
  showFullSyncModal.value = false;
  isFullLoading.value = true;
  try {
    const tasks: SyncTaskItem[] = selectedTypes.map(dt => ({ data_type: dt }));
    const response: SyncResponse = await dataSyncService.batchSyncData({
      tasks,
      priority: "medium",
      notify_on_complete: true,
    });
    message.success(response.message);
    if (response.task_id) {
      currentTaskId.value = response.task_id;
      startStatusPolling();
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || "全量同步失败");
  } finally {
    isFullLoading.value = false;
  }
};

const selectedFullSyncCount = computed(() =>
  Object.values(fullSyncSelected).filter(Boolean).length
);

const selectAllDataTypes = () => {
  syncConfig.data_types = supportedDataTypes.value
    .filter((t) => t.is_core && t.is_available !== false)
    .map((t) => t.code);
};
const clearAllDataTypes = () => {
  syncConfig.data_types = [];
};

const handleRecordClick = (taskId: string) => {
  router.push("/data/sync/history");
};

const handleCancelSync = () => {
  if (!currentTaskId.value) return;
  dialog.error({
    title: "确认取消同步",
    content: `确定要取消当前同步任务吗？已完成的数据不会被回滚。`,
    positiveText: "确认取消",
    negativeText: "返回",
    onPositiveClick: () => {
      // 先关弹窗、停轮询，再发取消请求（不阻塞 UI）
      stopStatusPolling();
      dataSyncService.cancelSync()
        .then(() => {
          message.success("取消请求已发送");
          setTimeout(async () => {
            const status = await dataSyncService.getSyncStatus().catch(() => null);
            if (status) syncStatus.value = status;
            refreshRecentTasks();
          }, 2000);
        })
        .catch(() => message.error("取消失败，请稍后重试"));
    },
  });
};

const isDataTypeSelected = (code: string) => syncConfig.data_types.includes(code);
const toggleDataType = (code: string) => {
  const dt = supportedDataTypes.value.find(t => t.code === code);
  if (!dt || dt.is_available === false) return;
  const idx = syncConfig.data_types.indexOf(code);
  if (idx >= 0) syncConfig.data_types.splice(idx, 1);
  else syncConfig.data_types.push(code);
};

// --- 生命周期 ---
onMounted(() => { initializePage(); });
onUnmounted(() => { stopStatusPolling(); });

watch(
  () => route.path,
  async (path) => {
    if (path === "/data/sync" && !pageLoading.value) {
      const [status, tasksResult] = await Promise.all([
        dataSyncService.getSyncStatus().catch(() => null),
        dataSyncService.getSyncTasks({ limit: 10 }).catch(() => ({ success: true, tasks: [], total: 0 })),
      ]);
      syncStatus.value = status;
      recentTasks.value = tasksResult.tasks || [];
    }
  },
);
</script>

<template>
  <div class="data-sync-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据同步中心</h1>
          <p class="page-description">管理数据同步任务，实时监控同步状态</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="initializePage" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 加载骨架 -->
    <template v-if="pageLoading">
      <div class="main-content">
        <div class="status-summary-bar skeleton-bar">
          <n-skeleton :text="true" width="100%" />
        </div>
        <n-grid :x-gap="24" :cols="24" responsive="screen">
          <n-grid-item :span="16">
            <n-card title="数据类型选择" class="config-card">
              <n-skeleton :text="true" :repeat="5" />
            </n-card>
          </n-grid-item>
          <n-grid-item :span="8">
            <n-card title="同步操作" class="action-card">
              <n-skeleton :text="true" :repeat="3" />
            </n-card>
          </n-grid-item>
        </n-grid>
      </div>
    </template>

    <!-- 加载失败 -->
    <n-result
      v-else-if="pageError"
      status="500"
      title="数据加载失败"
      description="请检查网络连接后重试"
    >
      <template #footer>
        <n-button type="primary" @click="initializePage">重试</n-button>
      </template>
    </n-result>

    <template v-else>
      <div class="main-content">
        <!-- 状态总览条 -->
        <div class="status-summary-bar">
          <div class="summary-item">
            <Icon icon="ant-design:clock-circle-outlined" class="summary-icon" />
            <span class="summary-label">上次同步</span>
            <span class="summary-value">{{ lastSyncTime }}</span>
          </div>
          <div class="summary-divider" />
          <div class="summary-item clickable" @click="router.push('/data/sync/quality')">
            <Icon icon="ant-design:check-circle-outlined" class="summary-icon" />
            <span class="summary-label">数据质量</span>
            <span class="summary-value accent">{{ qualityScore }}分</span>
          </div>
          <div class="summary-divider" />
          <div class="summary-item clickable" @click="router.push('/data/sync/history')">
            <Icon icon="ant-design:history-outlined" class="summary-icon" />
            <span class="summary-label">同步历史</span>
            <span class="summary-value">
              {{ historySummary.completed }}完成
              <span v-if="historySummary.failed > 0" class="failed-count">/{{ historySummary.failed }}失败</span>
            </span>
          </div>
          <div class="summary-spacer" />
          <n-button text size="small" @click="checkSyncStatus" :loading="isCheckingStatus">
            <template #icon><Icon icon="ant-design:reload-outlined" /></template>
          </n-button>
        </div>

        <!-- 主内容区 -->
        <n-grid :x-gap="24" :cols="24" responsive="screen">
          <!-- 左侧: 配置 -->
          <n-grid-item :span="16">
            <n-card class="config-card">
              <template #header>
                <div class="card-header-row">
                  <span>数据类型选择</span>
                  <span class="selected-count">已选 {{ syncConfig.data_types.length }} 种</span>
                </div>
              </template>
              <template #header-extra>
                <div class="header-actions-row">
                  <n-button text size="small" @click="selectAllDataTypes">全选</n-button>
                  <n-button text size="small" @click="clearAllDataTypes">清空</n-button>
                </div>
              </template>

              <div class="data-type-grid">
                <div
                  v-for="type in supportedDataTypes"
                  :key="type.code"
                  class="data-type-card"
                  :class="{ selected: isDataTypeSelected(type.code), disabled: type.is_available === false }"
                  @click="type.is_available !== false && toggleDataType(type.code)"
                >
                  <Icon
                    :icon="isDataTypeSelected(type.code) ? 'ant-design:check-circle-filled' : 'ant-design:check-circle-outlined'"
                    class="check-icon"
                  />
                  <span class="type-name">{{ type.name }}</span>
                  <span class="type-time">{{ type.is_available === false ? '不可用' : '约 ' + type.estimated_time + 's' }}</span>
                </div>
              </div>

              <n-collapse class="advanced-section">
                <n-collapse-item title="高级选项" name="1">
                  <n-grid :x-gap="16" :cols="2" responsive="screen">
                    <n-grid-item>
                      <n-form-item label="开始日期" class="compact-form-item">
                        <n-date-picker
                          v-model:value="datePickerFormatted"
                          type="date"
                          value-format="yyyy-MM-dd"
                          placeholder="不限"
                          clearable
                        />
                      </n-form-item>
                      <n-form-item label="结束日期" class="compact-form-item">
                        <n-date-picker
                          v-model:value="endDateFormatted"
                          type="date"
                          value-format="yyyy-MM-dd"
                          placeholder="不限"
                          clearable
                        />
                      </n-form-item>
                    </n-grid-item>
                    <n-grid-item>
                      <n-form-item label="交易所" class="compact-form-item">
                        <n-select
                          v-model:value="syncConfig.exchange"
                          placeholder="不限"
                          :options="exchangeOptions"
                          clearable
                        />
                      </n-form-item>
                      <n-form-item label="批量大小" class="compact-form-item">
                        <n-input-number v-model:value="syncConfig.batch_size" :min="1" :max="500" />
                      </n-form-item>
                    </n-grid-item>
                  </n-grid>
                </n-collapse-item>
              </n-collapse>
            </n-card>
          </n-grid-item>

          <!-- 右侧: 操作 + 进度 -->
          <n-grid-item :span="8">
            <div class="action-area">
              <n-card class="action-card">
                <div class="action-buttons">
                  <n-button
                    type="primary"
                    @click="handleBatchSync"
                    :loading="isLoading"
                    :disabled="isRunning || !syncConfig.data_types.length"
                    block
                    class="action-button primary"
                    size="large"
                  >
                    <template #icon><Icon icon="ant-design:cloud-download-outlined" /></template>
                    开始同步
                  </n-button>

                  <n-button
                    @click="openFullSyncModal"
                    :loading="isFullLoading"
                    :disabled="isRunning"
                    block
                    class="action-button secondary"
                    size="small"
                  >
                    <template #icon><Icon icon="ant-design:database-outlined" /></template>
                    全量同步（{{ supportedDataTypes.filter(t => t.is_core).length }} 种核心）
                  </n-button>
                </div>

                <!-- 运行中进度 -->
                <div class="sync-status-bar" v-if="isRunning && syncStatus?.progress">
                  <div class="status-row">
                    <span class="status-dot running" />
                    <span class="status-label-text">{{ statusText }}</span>
                    <span class="status-detail">
                      {{ syncStatus.progress.completed_tasks }}/{{ syncStatus.progress.total_tasks }} · {{ formattedElapsedTime }} · 剩余 {{ formattedRemainingTime }}
                    </span>
                  </div>
                  <n-progress
                    :percentage="syncStatus.progress.progress_percentage || 0"
                    :height="6" :border-radius="3"
                    class="status-progress-bar"
                  />
                  <n-button
                    block
                    @click="handleCancelSync"
                    class="action-button danger"
                    :style="{
                      '--n-color': 'rgba(229,69,69,0.12)',
                      '--n-color-hover': 'rgba(229,69,69,0.22)',
                      '--n-color-pressed': 'rgba(229,69,69,0.16)',
                      '--n-text-color': '#E54545',
                      '--n-text-color-hover': '#E54545',
                      '--n-border': '1px solid rgba(229,69,69,0.25)',
                      '--n-border-hover': '1px solid rgba(229,69,69,0.5)',
                    }"
                  >
                    <template #icon><Icon icon="ant-design:close-circle-outlined" /></template>
                    取消同步
                  </n-button>
                  <div v-if="subTaskDots.length > 0" class="sub-task-dots">
                    <span v-for="st in subTaskDots" :key="st.label" class="sub-dot" :class="st.status">
                      <Icon :icon="st.icon" class="dot-icon" />{{ st.label }}
                    </span>
                  </div>

                </div>

                <!-- 非运行中状态 -->
                <div class="sync-status-bar" :class="statusBarClass" v-else>
                  <div class="status-row">
                    <span class="status-dot" :class="statusBarClass" />
                    <span class="status-label-text">{{ statusText }}</span>
                  </div>
                  <div class="status-hint">
                    {{ statusHint }}
                  </div>
                </div>
              </n-card>
            </div>
          </n-grid-item>
        </n-grid>

        <!-- 最近同步记录 -->
        <div class="recent-section">
          <div class="recent-header">
            <h3 class="recent-title">
              <Icon icon="ant-design:history-outlined" class="recent-title-icon" />
              最近同步记录
            </h3>
            <n-button text size="small" type="primary" @click="router.push('/data/sync/history')">
              查看全部 <template #icon><Icon icon="ant-design:arrow-right-outlined" /></template>
            </n-button>
          </div>

          <div v-if="recentHistoryDisplay.length > 0" class="recent-list">
            <div
              v-for="item in recentHistoryDisplay"
              :key="item.id"
              class="recent-item clickable-row"
              @click="handleRecordClick(item.id)"
            >
              <div class="recent-item-icon">
                <Icon
                  :icon="item.status === 'completed' ? 'ant-design:check-circle-filled' : item.status === 'running' ? 'ant-design:sync-outlined' : item.status === 'pending' ? 'ant-design:clock-circle-outlined' : item.status === 'cancelled' ? 'ant-design:minus-circle-filled' : 'ant-design:close-circle-filled'"
                  :class="item.status === 'completed' ? 'icon-success' : item.status === 'running' || item.status === 'pending' ? 'icon-spin' : item.status === 'cancelled' ? 'icon-cancelled' : 'icon-error'"
                />
              </div>
              <div class="recent-item-info">
                <span class="recent-item-type">{{ item.data_type }}</span>
                <span class="recent-item-time">{{ item.start_time }}</span>
              </div>
              <n-tag :type="item.statusType" size="small">{{ item.statusLabel }}</n-tag>
              <span class="recent-item-records">{{ item.records.toLocaleString() }} 条</span>
            </div>
          </div>
          <div v-else class="recent-empty">
            <Icon icon="ant-design:inbox-outlined" class="empty-icon" />
            <span>暂无同步记录</span>
          </div>
        </div>
      </div>

      <!-- 同步失败提示 -->
      <n-alert
        v-if="syncStatus?.status === 'failed' && syncStatus?.message"
        :title="syncStatus.message"
        type="error"
        :show-icon="true"
        class="error-alert"
      />
    </template>
  </div>

  <!-- 全量同步类型选择弹窗 -->
  <n-modal v-model:show="showFullSyncModal" preset="card" title="选择同步数据类型"
    :mask-style="{ background: 'rgba(0,0,0,0.75)' }"
    class="full-sync-modal"
    style="width: 520px; border-radius: 12px;"
    :title-style="{ fontSize: '16px', fontWeight: 600 }"
  >
    <div style="max-height: 55vh; overflow-y: auto; padding-right: 4px;">
      <div v-for="group in fullSyncGroups" :key="group.label" style="margin-bottom: 12px;">
        <n-divider />
        <div style="font-weight: 600; font-size: 13px; color: var(--n-text-color-2); margin-bottom: 8px;">{{ group.label }}</div>
        <n-space vertical :size="4">
          <n-checkbox
            v-for="type in group.types"
            :key="type.code"
            :checked="fullSyncSelected[type.code]"
            @update:checked="(val: boolean) => { fullSyncSelected[type.code] = val; }"
          >
            <span style="font-size: 13px;">{{ type.name }}</span>
            <span style="font-size: 11px; color: var(--n-text-color-3); margin-left: 4px;">{{ type.estimated_time }}s</span>
          </n-checkbox>
        </n-space>
      </div>
    </div>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showFullSyncModal = false">取消</n-button>
        <n-button type="primary" @click="executeFullSync" :loading="isFullLoading">
          开始同步（{{ selectedFullSyncCount }} 种）
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped lang="scss">
@use "@/styles/variables" as *;
@use "@/styles/mixins" as mixin;
@use "sass:map";

.data-sync-page {
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

// --- 状态总览条 ---
.status-summary-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  margin-bottom: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid $border-color;
  border-radius: $border-radius;
  font-size: $font-size-base * 0.85;
  flex-wrap: wrap;

  &.skeleton-bar {
    padding: 14px 16px;
  }
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;

  &.clickable {
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    transition: background $transition-fast;

    &:hover { background: rgba(255, 255, 255, 0.05); }
  }
}

.summary-icon {
  font-size: $font-size-base;
  color: $text-color-3;
}

.summary-label {
  color: $text-color-3;
}

.summary-value {
  color: $text-color-1;
  font-weight: $font-weight-medium;

  &.accent { color: $primary-color; }
}

.failed-count {
  color: $error-color;
}

.summary-divider {
  width: 1px;
  height: 16px;
  background: $border-color;
}

.summary-spacer {
  flex: 1;
}

// --- 配置卡片 ---
.config-card {
  border-radius: $border-radius-large;
}

.card-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-count {
  font-weight: 400;
  font-size: $font-size-base * 0.85;
  color: $text-color-2;
}

.header-actions-row {
  display: flex;
  gap: 4px;
}

.data-type-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;

  @include mixin.media-breakpoint-down(xl) { grid-template-columns: repeat(4, 1fr); }
  @include mixin.media-breakpoint-down(md) { grid-template-columns: repeat(3, 1fr); }
  @include mixin.media-breakpoint-down(sm) { grid-template-columns: repeat(2, 1fr); }
}

.data-type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 8px 6px;
  border: 1px solid $border-color;
  border-radius: $border-radius-sm;
  background: $secondary-bg;
  cursor: pointer;
  transition: all $transition-fast;
  text-align: center;

  &:hover {
    border-color: $primary-color;
    background: rgba($primary-color, 0.04);
  }

  &.selected {
    border-color: $primary-color;
    background: rgba($primary-color, 0.08);

    .check-icon { color: $primary-color; }
    .type-name { color: $primary-color; }
  }

  .check-icon {
    font-size: $font-size-base * 0.95;
    color: $text-color-3;
    transition: color $transition-fast;
  }

  .type-name {
    font-size: $font-size-base * 0.75;
    font-weight: $font-weight-medium;
    color: $text-color-1;
    line-height: 1.2;
  }

  .type-time {
    font-size: $font-size-base * 0.65;
    color: $text-color-3;
  }

  &.disabled {
    opacity: 0.4;
    cursor: not-allowed;
    &:hover {
      border-color: $border-color;
      background: $secondary-bg;
    }
  }
}

.compact-form-item {
  margin-bottom: map.get($spacers, 3);
}

.advanced-section {
  margin-top: map.get($spacers, 3);

  :deep(.n-collapse-item__header) {
    font-size: $font-size-base * 0.9;
  }
}

// --- 操作区 ---
.action-area {
  position: sticky;
  top: map.get($spacers, 4);
}

.action-card {
  border-radius: $border-radius-large;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: map.get($spacers, 2);

  .action-button {
    transition: all $transition-normal;

    &.primary {
      background: linear-gradient(135deg, $primary-color, color-mix(in srgb, var(--color-primary) 80%, black));
      border: none;
      color: white;

      &:hover:not(:disabled) {
        transform: $hover-transform;
        box-shadow: 0 6px 20px color-mix(in srgb, var(--color-primary) 40%, transparent);
      }
    }

    &.secondary {
      background: $secondary-bg;
      border-color: $border-color;
      color: $text-color-1;
      height: 32px;
      font-size: $font-size-base * 0.8;

      &:hover:not(:disabled) {
        background: $hover-bg;
        border-color: $primary-color;
      }
    }
  }
}

// --- 进度/状态区 ---
.sync-status-bar {
  padding-top: 12px;
  margin-top: 12px;
  border-top: 1px solid $border-color;

  &.idle    { border-top-style: dashed; }
  &.failed  { border-top-color: rgba($error-color, 0.3); }
  &.completed { border-top-color: rgba($success-color, 0.3); }
  &.partial { border-top-color: rgba($warning-color, 0.3); }
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: $text-color-3;
  flex-shrink: 0;

  &.running   { background: $success-color; animation: pulse-dot 1.5s ease infinite; }
  &.completed { background: $success-color; }
  &.failed    { background: $error-color; }
  &.pending   { background: $warning-color; animation: pulse-dot 1.5s ease infinite; }
  &.partial   { background: $warning-color; }
  &.cancelled { background: $text-color-3; }
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-label-text {
  font-size: $font-size-base * 0.9;
  color: $text-color-1;
}

.status-detail {
  font-size: $font-size-base * 0.78;
  color: $text-color-3;
}

.status-hint {
  margin-top: 8px;
  font-size: $font-size-base * 0.8;
  color: $text-color-3;
  line-height: 1.4;
}

.status-progress-bar { margin: 8px 0; }


.sub-task-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}

.sub-dot {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: $font-size-base * 0.72;
  color: $text-color-3;
  padding: 1px 6px;
  border-radius: $border-radius-sm;
  background: $secondary-bg;

  .dot-icon { font-size: $font-size-base * 0.85; flex-shrink: 0; }

  &.completed { color: $success-color; .dot-icon { color: $success-color; } }
  &.running { color: $info-color; .dot-icon { animation: pulse-dot 1.2s ease infinite; } }
  &.failed { color: $error-color; .dot-icon { color: $error-color; } }
}

// --- 最近同步记录 ---
.recent-section {
  margin-top: 24px;
}

.recent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.recent-title {
  font-size: $font-size-base;
  font-weight: $font-weight-semibold;
  color: $text-color-1;
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
}

.recent-title-icon {
  font-size: $font-size-base * 1.1;
  color: $text-color-2;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid $border-color;
  border-radius: $border-radius-sm;
  transition: background $transition-fast;

  &:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  &.clickable-row {
    cursor: pointer;
  }
}

.recent-item-icon {
  flex-shrink: 0;
  font-size: $font-size-base * 1.1;

  .icon-success { color: $success-color; }
  .icon-error { color: $error-color; }
  .icon-cancelled { color: $warning-color; }
  .icon-spin { color: $info-color; animation: icon-spin 1.5s linear infinite; }
}

@keyframes icon-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.recent-item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.recent-item-type {
  font-size: $font-size-base * 0.85;
  font-weight: $font-weight-medium;
  color: $text-color-1;
}

.recent-item-time {
  font-size: $font-size-base * 0.7;
  color: $text-color-3;
}

.recent-item-records {
  font-size: $font-size-base * 0.78;
  color: $text-color-3;
  white-space: nowrap;
}

.recent-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: $text-color-3;
  font-size: $font-size-base * 0.85;
  border: 1px dashed $border-color;
  border-radius: $border-radius-sm;

  .empty-icon { font-size: $font-size-base * 1.3; }
}

.error-alert {
  margin: map.get($spacers, 4);
  border-radius: $border-radius;
}

.full-sync-modal {
  :deep(.n-card) {
    background: rgb(14, 18, 30) !important;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
}
</style>
