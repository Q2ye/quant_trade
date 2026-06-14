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
  NTable,
  NSpace,
  NProgress,
} from "naive-ui";
import { useRouter, useRoute } from "vue-router";
import type {
  BatchSyncRequest,
  DataTypeInfo,
  SyncResponse,
  SyncStatusResponse,
  SyncTaskItem,
  DataQualityResponse,
  SyncTypesMetaResponse,
  SyncGroupMeta,
  SyncTypeMeta,
  SyncPresetMeta,
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
const isCheckingStatus = ref(false);
const statusPollingInterval = ref<ReturnType<typeof setInterval> | null>(null);
const lastWsEventTime = ref(0);

const syncStatus = ref<SyncStatusResponse | null>(null);
const supportedDataTypes = ref<DataTypeInfo[]>([]);
const qualityData = ref<DataQualityResponse | null>(null);
const recentTasks = ref<SyncTaskRecord[]>([]);
const currentTaskId = ref<string>("");

const { isRunning, formattedElapsedTime, formattedRemainingTime } =
  useSyncTimer(syncStatus);
const { qualityScore } = useQualityMetrics(qualityData);

// --- 工作组状态（新7分组布局） ---
const syncMeta = ref<SyncTypesMetaResponse | null>(null);
const activeGroup = ref("1"); // 当前选中的分组
const groupSelection = ref<Record<string, Set<string>>>({}); // 每组已选中的类型

// --- 新布局辅助函数 ---
const currentGroup = computed(() =>
  syncMeta.value?.groups.find((g) => g.id === activeGroup.value),
);
const currentSelected = computed(
  () => groupSelection.value[activeGroup.value] || new Set<string>(),
);
function isSelected(dataType: string) {
  return currentSelected.value.has(dataType);
}
function toggleSelection(dt: string, v: boolean) {
  if (!groupSelection.value[activeGroup.value])
    groupSelection.value[activeGroup.value] = new Set();
  v
    ? groupSelection.value[activeGroup.value].add(dt)
    : groupSelection.value[activeGroup.value].delete(dt);
}
function selectAll() {
  const s = new Set<string>();
  currentGroup.value?.types
    .filter((t) => t.implemented)
    .forEach((t) => s.add(t.data_type));
  groupSelection.value[activeGroup.value] = s;
}
function selectCore() {
  const s = new Set<string>();
  currentGroup.value?.types
    .filter((t) => t.implemented && t.is_core)
    .forEach((t) => s.add(t.data_type));
  groupSelection.value[activeGroup.value] = s;
}
function deselectAll() {
  groupSelection.value[activeGroup.value] = new Set();
}
const estimatedGroupTime = computed(() => {
  let total = 0;
  currentGroup.value?.types.forEach((ty) => {
    if (isSelected(ty.data_type)) total += ty.estimated_time_seconds;
  });
  return total;
});
function fmtRelative(s: string | null) {
  if (!s) return "从未";
  const h = Math.round((Date.now() - new Date(s).getTime()) / 3600000);
  if (h < 1) return "刚刚";
  if (h < 24) return `${h}h前`;
  return `${Math.floor(h / 24)}d前`;
}
function statusType(t: SyncTypeMeta) {
  if (!t.implemented) return "default";
  if (!t.last_sync_at) return "default";
  const h = (Date.now() - new Date(t.last_sync_at).getTime()) / 3600000;
  if (h < 24) return "success";
  if (h < 72) return "warning";
  return "error";
}
function typeStatusText(t: SyncTypeMeta) {
  if (!t.implemented) return "未实现";
  if (!t.last_sync_at) return "未同步";
  const h = (Date.now() - new Date(t.last_sync_at).getTime()) / 3600000;
  if (h < 24) return "已同步";
  if (h < 72) return "待更新";
  return "需同步";
}
async function syncSelected() {
  syncConfig.data_types = [...currentSelected.value];
  await handleBatchSync();
}
const dailyPreset = computed(() =>
  syncMeta.value?.presets?.find((p) => p.id === "daily"),
);
async function runDailyPreset() {
  if (!dailyPreset.value) {
    message.warning("每日行情预设未找到");
    return;
  }
  // 每日行情始终走增量，不受日期选择器影响
  syncConfig.data_types = dailyPreset.value.steps.flatMap((s) => {
    const g = syncMeta.value?.groups.find((gr) => gr.id === s.group_id);
    return g?.types.filter((t) => t.implemented).map((t) => t.data_type) ?? [];
  });
  await handleBatchSync({ skipDates: true });
}

async function runPreset(p: SyncPresetMeta) {
  const types: string[] = [];
  const groupLabels: string[] = [];
  for (const step of p.steps) {
    const group = syncMeta.value?.groups.find((g) => g.id === step.group_id);
    if (group) {
      types.push(
        ...group.types.filter((t) => t.implemented).map((t) => t.data_type),
      );
      groupLabels.push(group.label);
    }
  }
  if (!types.length) {
    message.warning("该预设没有可用的数据类型");
    return;
  }
  syncConfig.data_types = types;

  // 确认弹窗
  dialog.warning({
    title: `确认执行「${p.name}」`,
    content: `将对 ${groupLabels.join("、")} 共 ${types.length} 种类型进行同步，预估耗时 ~${fmtTime(p.estimated_time_seconds)}。`,
    positiveText: "确认执行",
    negativeText: "取消",
    onPositiveClick: async () => {
      await handleBatchSync();
    },
  });
}

function fmtTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

// --- 同步配置 ---
const syncConfig = reactive({
  data_types: [] as string[],
  start_date: "",
  end_date: "",
  exchange: "",
  batch_size: 100,
});

// 日期选择器 ref → syncConfig
const startDate = ref<number | null>(null);
const endDate = ref<number | null>(null);
watch(startDate, (v) => {
  syncConfig.start_date = v ? new Date(v).toISOString().slice(0, 10) : "";
});
watch(endDate, (v) => {
  syncConfig.end_date = v ? new Date(v).toISOString().slice(0, 10) : "";
});

const exchangeOptions = [
  { label: "上交所", value: "SSE" },
  { label: "深交所", value: "SZSE" },
  { label: "北交所", value: "BSE" },
];

const datePickerFormatted = computed({
  get: () =>
    syncConfig.start_date ? new Date(syncConfig.start_date).getTime() : null,
  set: (val: number | null) => {
    syncConfig.start_date = val ? new Date(val).toISOString().slice(0, 10) : "";
  },
});

const endDateFormatted = computed({
  get: () =>
    syncConfig.end_date ? new Date(syncConfig.end_date).getTime() : null,
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
  if (s === "failed")
    return syncStatus.value?.message || "同步任务执行失败，请查看历史记录";
  if (s === "partial") return "部分任务成功，部分失败，请查看历史记录";
  if (s === "idle" || !syncStatus.value)
    return "选择数据类型后点击「开始同步」";
  return syncStatus.value?.message || "选择数据类型后点击「开始同步」";
});

const lastSyncTime = computed(() => {
  const t = syncStatus.value?.updated_at;
  if (!t) return "--";
  try {
    return new Date(t).toLocaleString("zh-CN");
  } catch {
    return t;
  }
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
      const status = isSyncRunning
        ? "running"
        : cancelled
          ? "cancelled"
          : success
            ? "completed"
            : "failed";
      const icon = isSyncRunning
        ? "ant-design:sync-outlined"
        : cancelled
          ? "ant-design:warning-filled"
          : success
            ? "ant-design:check-circle-filled"
            : "ant-design:close-circle-filled";
      return { label: r.data_type, status, icon };
    });
  }
  const progress = syncStatus.value?.progress;
  if (progress && progress.total_tasks > 0) {
    const dots: {
      label: string;
      status: "completed" | "running" | "pending";
      icon: string;
    }[] = [];
    for (let i = 0; i < progress.total_tasks; i++) {
      const isDone = i < progress.completed_tasks;
      const isRunningTask =
        i === progress.completed_tasks && progress.current_task;
      dots.push({
        label:
          isRunningTask && progress.current_task
            ? progress.current_task
            : `任务${i + 1}`,
        status: isDone ? "completed" : isRunningTask ? "running" : "pending",
        icon: isDone
          ? "ant-design:check-circle-filled"
          : isRunningTask
            ? "ant-design:sync-outlined"
            : "ant-design:clock-circle-outlined",
      });
    }
    return dots;
  }
  return [];
});

const formatDataTypeDisplay = (t: SyncTaskRecord): string => {
  // 使用 syncMeta 的类型标签（统一来源）
  if (syncMeta.value) {
    for (const g of syncMeta.value.groups) {
      const found = g.types.find((ty) => ty.data_type === t.task_type);
      if (found) return found.label;
    }
  }
  // 兜底：旧 supportedDataTypes
  if (t.data_types?.length) {
    return t.data_types
      .map((code) => {
        const info = supportedDataTypes.value.find((dt) => dt.code === code);
        return info ? info.name : code;
      })
      .join(" · ");
  }
  return t.task_type;
};

const recentHistoryDisplay = computed(() => {
  return recentTasks.value.slice(0, 3).map((t) => {
    const startTime = t.start_time
      ? (() => {
          try {
            return new Date(t.start_time).toLocaleString("zh-CN");
          } catch {
            return t.start_time;
          }
        })()
      : "--";
    return {
      id: t.task_id,
      data_type: formatDataTypeDisplay(t),
      status: t.status,
      start_time: startTime,
      records: t.total_records || 0,
      statusLabel:
        t.status === "completed"
          ? "完成"
          : t.status === "failed"
            ? "失败"
            : t.status === "running"
              ? "运行中"
              : t.status === "pending"
                ? "等待中"
                : t.status === "cancelled"
                  ? "已取消"
                  : t.status,
      statusType: (t.status === "completed"
        ? "success"
        : t.status === "failed"
          ? "error"
          : t.status === "running"
            ? "info"
            : t.status === "cancelled"
              ? "warning"
              : "default") as
        | "success"
        | "error"
        | "info"
        | "warning"
        | "default",
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
  onCompleted() {
    stopStatusPolling();
    currentTaskId.value = "";
    refreshRecentTasks();
    refreshQualityData();
  },
  onFailed() {
    stopStatusPolling();
    currentTaskId.value = "";
    refreshRecentTasks();
    refreshQualityData();
  },
  onCancelled() {
    stopStatusPolling();
    currentTaskId.value = "";
    refreshRecentTasks();
    refreshQualityData();
  },
});

// --- 数据加载 ---
const initializePage = async () => {
  pageLoading.value = true;
  pageError.value = false;
  try {
    const [status, types, quality, tasksResult, meta] = await Promise.all([
      dataSyncService.getSyncStatus().catch(() => null),
      dataSyncService.getSupportedDataTypes().catch(() => [] as DataTypeInfo[]),
      dataSyncService.getDataQuality().catch(() => null),
      dataSyncService
        .getSyncTasks({ limit: 10 })
        .catch(() => ({ success: true, tasks: [], total: 0 })),
      dataSyncService.getSyncTypesMeta().catch(() => null),
    ]);
    syncStatus.value = status;
    syncMeta.value = meta;
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
  } catch {
    /* 静默失败 */
  }
};

const refreshQualityData = async () => {
  try {
    const q = await dataSyncService.getDataQuality();
    qualityData.value = q;
  } catch {
    /* 静默失败 */
  }
};

const checkSyncStatus = async () => {
  isCheckingStatus.value = true;
  try {
    const status = await dataSyncService.getSyncStatus();
    syncStatus.value = status;
    if (status.status === "running" && !statusPollingInterval.value)
      startStatusPolling();
    else if (status.status !== "running" && statusPollingInterval.value)
      stopStatusPolling();
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
const handleBatchSync = async (opts?: { skipDates?: boolean }) => {
  if (!syncConfig.data_types.length) {
    message.warning("请选择至少一种数据类型");
    return;
  }
  isLoading.value = true;
  try {
    const tasks: SyncTaskItem[] = syncConfig.data_types.map((dt) => {
      const item: SyncTaskItem = { data_type: dt };
      if (!opts?.skipDates) {
        if (syncConfig.start_date) item.start_date = syncConfig.start_date;
        if (syncConfig.end_date) item.end_date = syncConfig.end_date;
      }
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
      dataSyncService
        .cancelSync()
        .then(() => {
          message.success("取消请求已发送");
          setTimeout(async () => {
            const status = await dataSyncService
              .getSyncStatus()
              .catch(() => null);
            if (status) syncStatus.value = status;
            refreshRecentTasks();
          }, 2000);
        })
        .catch(() => message.error("取消失败，请稍后重试"));
    },
  });
};

const isDataTypeSelected = (code: string) =>
  syncConfig.data_types.includes(code);
const toggleDataType = (code: string) => {
  const dt = supportedDataTypes.value.find((t) => t.code === code);
  if (!dt || dt.is_available === false) return;
  const idx = syncConfig.data_types.indexOf(code);
  if (idx >= 0) syncConfig.data_types.splice(idx, 1);
  else syncConfig.data_types.push(code);
};

// --- 生命周期 ---
onMounted(() => {
  initializePage();
});
onUnmounted(() => {
  stopStatusPolling();
});

watch(
  () => route.path,
  async (path) => {
    if (path === "/data/sync" && !pageLoading.value) {
      const [status, tasksResult] = await Promise.all([
        dataSyncService.getSyncStatus().catch(() => null),
        dataSyncService
          .getSyncTasks({ limit: 10 })
          .catch(() => ({ success: true, tasks: [], total: 0 })),
      ]);
      syncStatus.value = status;
      recentTasks.value = tasksResult.tasks || [];
    }
  },
);
</script>

<template>
  <div class="data-sync-page bg-gradient-mesh bg-noise">
    <!-- Page Header -->
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
        <n-skeleton :text="true" :repeat="6" />
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

    <!-- 主内容 -->
    <template v-else>
      <div class="sync-workbench">
        <!-- 日期 + 每日行情 -->
        <div
          style="
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
            align-items: stretch;
          "
        >
          <!-- 日期卡 -->
          <n-card
            size="small"
            style="width: 540px; flex-shrink: 0; border-radius: 10px"
          >
            <div style="display: flex; gap: 12px; align-items: flex-end">
              <div>
                <span
                  style="
                    font-size: 11px;
                    color: var(--n-text-color-3);
                    display: block;
                    margin-bottom: 4px;
                  "
                  >起始日期</span
                >
                <n-date-picker
                  v-model:value="startDate"
                  type="date"
                  clearable
                  placeholder="自动增量"
                  style="width: 245px"
                />
              </div>
              <div>
                <span
                  style="
                    font-size: 11px;
                    color: var(--n-text-color-3);
                    display: block;
                    margin-bottom: 4px;
                  "
                  >结束日期</span
                >
                <n-date-picker
                  v-model:value="endDate"
                  type="date"
                  clearable
                  placeholder="今天"
                  style="width: 245px"
                />
              </div>
            </div>
          </n-card>
          <!-- 每日行情卡 -->
          <n-card
            v-if="dailyPreset"
            size="small"
            style="
              min-width: 0;
              flex-shrink: 1;
              cursor: pointer;
              border-radius: 10px;
              transition: all 0.15s;
            "
            :class="{ disabled: isRunning }"
            @click="runDailyPreset"
          >
            <div style="display: flex; align-items: center; gap: 16px">
              <div style="flex: 1; min-width: 0">
                <div
                  style="font-size: 14px; font-weight: 600; margin-bottom: 6px"
                >
                  {{ dailyPreset.name }}
                </div>
                <div style="display: flex; align-items: center; gap: 8px">
                  <span
                    style="
                      font-size: 12px;
                      color: var(--n-text-color-3);
                      overflow: hidden;
                      text-overflow: ellipsis;
                      white-space: nowrap;
                    "
                    >{{ dailyPreset.description }}</span
                  >
                  <span
                    style="
                      font-size: 12px;
                      color: var(--n-text-color-3);
                      white-space: nowrap;
                      flex-shrink: 0;
                    "
                    >~{{ fmtTime(dailyPreset.estimated_time_seconds) }}</span
                  >
                </div>
              </div>
              <n-button
                type="primary"
                :disabled="isRunning"
                style="
                  flex-shrink: 0;
                  width: 32px;
                  height: 32px;
                  padding: 0;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  font-size: 16px;
                "
                >&#9654;</n-button
              >
            </div>
          </n-card>
        </div>

        <!-- Running Sync Status Bar -->
        <div v-if="isRunning && syncStatus?.progress" class="sync-running-bar">
          <div class="running-info">
            <span class="running-dot" />
            <span class="running-label">同步中</span>
            <span class="running-detail">
              {{ syncStatus.progress.completed_tasks }}/{{
                syncStatus.progress.total_tasks
              }}
              · {{ formattedElapsedTime }} · 剩余 {{ formattedRemainingTime }}
            </span>
          </div>
          <n-progress
            :percentage="syncStatus.progress.progress_percentage || 0"
            :height="6"
            :border-radius="3"
            class="running-progress"
          />
          <div class="running-actions">
            <span v-if="subTaskDots.length > 0" class="sub-task-dots">
              <span
                v-for="st in subTaskDots"
                :key="st.label"
                class="sub-dot"
                :class="st.status"
              >
                <Icon :icon="st.icon" class="dot-icon" />{{ st.label }}
              </span>
            </span>
            <n-button
              size="tiny"
              type="error"
              @click="handleCancelSync"
              quaternary
            >
              取消
            </n-button>
          </div>
        </div>

        <!-- Status Summary Bar -->
        <div class="status-summary-bar">
          <div class="summary-item">
            <Icon
              icon="ant-design:clock-circle-outlined"
              class="summary-icon"
            />
            <span class="summary-label">上次同步</span>
            <span class="summary-value">{{ lastSyncTime }}</span>
          </div>
          <div class="summary-divider" />
          <div
            class="summary-item clickable"
            @click="router.push('/data/sync/quality')"
          >
            <Icon
              icon="ant-design:check-circle-outlined"
              class="summary-icon"
            />
            <span class="summary-label">数据质量</span>
            <span class="summary-value accent">{{ qualityScore }}分</span>
          </div>
          <div class="summary-divider" />
          <div
            class="summary-item clickable"
            @click="router.push('/data/sync/history')"
          >
            <Icon icon="ant-design:history-outlined" class="summary-icon" />
            <span class="summary-label">同步历史</span>
            <span class="summary-value">
              {{ historySummary.completed }}完成
              <span v-if="historySummary.failed > 0" class="failed-count"
                >/{{ historySummary.failed }}失败</span
              >
            </span>
          </div>
          <div class="summary-spacer" />
          <n-button
            text
            size="small"
            @click="checkSyncStatus"
            :loading="isCheckingStatus"
          >
            <template #icon
              ><Icon icon="ant-design:reload-outlined"
            /></template>
          </n-button>
        </div>

        <!-- Main: Sidebar + Content -->
        <div class="main-layout">
          <!-- Sidebar -->
          <div class="sidebar">
            <div
              v-for="g in syncMeta?.groups"
              :key="g.id"
              class="sidebar-item"
              :class="{ active: activeGroup === g.id }"
              @click="activeGroup = g.id"
            >
              <span class="sidebar-dot" :style="{ background: g.color }"></span>
              <span class="sidebar-label">{{ g.label }}</span>
              <span class="sidebar-count"
                >{{ g.types.filter((t) => t.implemented).length }}/{{
                  g.types.length
                }}</span
              >
            </div>
          </div>

          <!-- Content Table -->
          <div class="content">
            <div class="content-header">
              <h3>{{ currentGroup?.label }}</h3>
              <span class="content-desc">{{ currentGroup?.description }}</span>
              <div class="content-toolbar">
                <n-button size="tiny" @click="selectAll">全选</n-button>
                <n-button size="tiny" @click="selectCore">仅必需</n-button>
                <n-button size="tiny" @click="deselectAll">清空</n-button>
              </div>
            </div>

            <n-table :single-line="false" size="small">
              <thead>
                <tr>
                  <th style="width: 40px">选择</th>
                  <th>类型</th>
                  <th style="width: 100px">上次同步</th>
                  <th style="width: 80px">预估耗时</th>
                  <th style="width: 60px">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="t in currentGroup?.types"
                  :key="t.data_type"
                  :class="{
                    'row-disabled': !t.implemented,
                    'row-selected': isSelected(t.data_type),
                  }"
                  @click="
                    t.implemented &&
                    toggleSelection(t.data_type, !isSelected(t.data_type))
                  "
                >
                  <td>
                    <n-checkbox
                      :checked="isSelected(t.data_type)"
                      :disabled="!t.implemented"
                      @update:checked="
                        (v: boolean) => toggleSelection(t.data_type, v)
                      "
                    />
                  </td>
                  <td>
                    <span class="type-label">{{ t.label }}</span>
                  </td>
                  <td>
                    <span class="last-sync">{{
                      fmtRelative(t.last_sync_at)
                    }}</span>
                  </td>
                  <td>
                    <span class="est-time">{{
                      fmtTime(t.estimated_time_seconds)
                    }}</span>
                  </td>
                  <td>
                    <n-tag :type="statusType(t)" size="tiny" :bordered="false">
                      {{ typeStatusText(t) }}
                    </n-tag>
                  </td>
                </tr>
              </tbody>
            </n-table>

            <div class="content-footer">
              <span
                >已选 {{ currentSelected.size }} 项 · 预估 ~{{
                  fmtTime(estimatedGroupTime)
                }}</span
              >
              <n-button
                type="primary"
                :disabled="currentSelected.size === 0 || isRunning"
                :loading="isLoading"
                @click="syncSelected"
              >
                &#9654; 同步已选
              </n-button>
            </div>
          </div>
        </div>

        <!-- 最近同步记录 -->
        <div class="recent-section">
          <div class="recent-header">
            <h3 class="recent-title">
              <Icon
                icon="ant-design:history-outlined"
                class="recent-title-icon"
              />
              最近同步记录
            </h3>
            <n-button
              text
              size="small"
              type="primary"
              @click="router.push('/data/sync/history')"
            >
              查看全部
              <template #icon
                ><Icon icon="ant-design:arrow-right-outlined"
              /></template>
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
                  :icon="
                    item.status === 'completed'
                      ? 'ant-design:check-circle-filled'
                      : item.status === 'running'
                        ? 'ant-design:sync-outlined'
                        : item.status === 'pending'
                          ? 'ant-design:clock-circle-outlined'
                          : item.status === 'cancelled'
                            ? 'ant-design:minus-circle-filled'
                            : 'ant-design:close-circle-filled'
                  "
                  :class="
                    item.status === 'completed'
                      ? 'icon-success'
                      : item.status === 'running' || item.status === 'pending'
                        ? 'icon-spin'
                        : item.status === 'cancelled'
                          ? 'icon-cancelled'
                          : 'icon-error'
                  "
                />
              </div>
              <div class="recent-item-info">
                <span class="recent-item-type">{{ item.data_type }}</span>
                <span class="recent-item-time">{{ item.start_time }}</span>
              </div>
              <n-tag :type="item.statusType" size="small">{{
                item.statusLabel
              }}</n-tag>
              <span class="recent-item-records"
                >{{ item.records.toLocaleString() }} 条</span
              >
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

// --- Sync Workbench ---
.sync-workbench {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
}

// --- Quick Actions Bar ---
.quick-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.preset-card {
  flex: 1;
  min-width: 280px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;

  &.recommended {
    border-color: var(--n-color-success);
  }

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
}

.preset-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preset-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.preset-name {
  font-weight: 600;
  font-size: 14px;
}

.preset-desc {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.preset-action {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.preset-time {
  font-size: 12px;
  color: var(--n-text-color-3);
}

// --- Sync Running Bar ---
.sync-running-bar {
  padding: 10px 14px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.running-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.running-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: $primary-color;
  animation: pulse-dot 1.5s ease infinite;
}

@keyframes pulse-dot {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.running-label {
  font-size: 13px;
  font-weight: 500;
  color: $text-color-1;
}

.running-detail {
  font-size: 12px;
  color: $text-color-3;
}

.running-progress {
  margin: 0;
}

.running-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sub-task-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sub-dot {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: $text-color-3;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);

  .dot-icon {
    font-size: 12px;
    flex-shrink: 0;
  }

  &.completed {
    color: $success-color;
    .dot-icon {
      color: $success-color;
    }
  }
  &.running {
    color: $info-color;
    .dot-icon {
      animation: pulse-dot 1.2s ease infinite;
    }
  }
  &.failed {
    color: $error-color;
    .dot-icon {
      color: $error-color;
    }
  }
}

// --- Status Summary Bar ---
.status-summary-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid $border-color;
  border-radius: $border-radius;
  font-size: $font-size-base * 0.85;
  flex-wrap: wrap;
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

    &:hover {
      background: rgba(255, 255, 255, 0.05);
    }
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

  &.accent {
    color: $primary-color;
  }
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

// --- Main Layout: Sidebar + Content ---
.main-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

// --- Sidebar ---
.sidebar {
  width: 180px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--n-card-color);
  border-radius: 10px;
  padding: 8px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 14px;
  color: $text-color-1;

  &:hover {
    background: var(--n-action-color);
  }

  &.active {
    background: var(--n-color-primary);
    color: white;
  }
}

.sidebar-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.sidebar-label {
  flex: 1;
}

.sidebar-count {
  font-size: 11px;
  opacity: 0.7;
}

// --- Content ---
.content {
  flex: 1;
  min-width: 0;
  background: var(--n-card-color);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.content-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;

  h3 {
    margin: 0;
    font-size: 16px;
    color: $text-color-1;
  }
}

.content-desc {
  font-size: 13px;
  color: $text-color-3;
}

.content-toolbar {
  margin-left: auto;
  display: flex;
  gap: 6px;
}

/* 同步类型表格行 hover + 选中动效 */
:deep(.n-table) tbody tr {
  transition:
    background 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
  cursor: pointer;

  td {
    transition: background 0.15s ease;
  }

  &:hover:not(.row-disabled):not(.row-selected) {
    background: rgba(68, 138, 255, 0.08);
    transform: translateX(4px);
    box-shadow: inset 3px 0 0 0 #448aff;
    td {
      background: transparent;
    }
  }

  &.row-selected {
    background: rgba(68, 138, 255, 0.25);
    box-shadow: inset 3px 0 0 0 #448aff;
    color: #fff;
    font-weight: 500;
    td {
      background: transparent;
    }
    &:not(.row-disabled) {
      cursor: pointer;
    }
    &:hover {
      background: rgba(68, 138, 255, 0.25);
    }
  }
}

.row-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.type-label {
  font-size: 13px;
}

.last-sync,
.est-time {
  font-size: 12px;
  color: $text-color-3;
}

.content-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid var(--n-border-color);
  font-size: 13px;
  color: $text-color-3;
}

// --- 最近同步记录 ---
.recent-section {
  margin-top: 0;
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

  .icon-success {
    color: $success-color;
  }
  .icon-error {
    color: $error-color;
  }
  .icon-cancelled {
    color: $warning-color;
  }
  .icon-spin {
    color: $info-color;
    animation: icon-spin 1.5s linear infinite;
  }
}

@keyframes icon-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
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

  .empty-icon {
    font-size: $font-size-base * 1.3;
  }
}

// --- Misc ---
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

.main-content {
  padding: 20px 24px;
}
</style>
