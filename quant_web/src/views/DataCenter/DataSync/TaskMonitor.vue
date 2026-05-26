<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NEmpty,
  NGrid,
  NGridItem,
  NList,
  NListItem,
  NProgress,
  NResult,
  NSkeleton,
  NSpin,
  NStatistic,
  NTag,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";

const router = useRouter();
const message = useMessage();

interface SyncTask {
  id: string;
  taskType: string;
  dataCategory: string;
  progress: number;
  status: "running" | "paused" | "completed" | "failed";
  startTime: string;
  elapsedTime: string;
  estimatedTime: string;
  currentStep: string;
  details: string;
  syncedCount: number;
  totalCount: number;
  errorMsg?: string;
}

type PageState = "loading" | "error" | "empty" | "data";

const pageState = ref<PageState>("loading");
const tasks = ref<SyncTask[]>([]);
const autoRefresh = ref(true);
let refreshInterval: number | undefined;

const stats = computed(() => ({
  running: tasks.value.filter(t => t.status === "running").length,
  paused: tasks.value.filter(t => t.status === "paused").length,
  completed: tasks.value.filter(t => t.status === "completed").length,
  failed: tasks.value.filter(t => t.status === "failed").length,
}));

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/");
};

const loadTasks = async (showLoading = true) => {
  if (showLoading) pageState.value = "loading";
  try {
    await new Promise((r) => setTimeout(r, 600));
    tasks.value = [
      {
        id: "1",
        taskType: "全量同步",
        dataCategory: "市场数据",
        progress: 75,
        status: "running",
        startTime: "2024-01-15 10:00:00",
        elapsedTime: "15分钟",
        estimatedTime: "约5分钟",
        currentStep: "处理K线数据",
        details: "同步沪深300指数日线数据",
        syncedCount: 3750,
        totalCount: 5000,
      },
      {
        id: "2",
        taskType: "增量同步",
        dataCategory: "财务数据",
        progress: 100,
        status: "completed",
        startTime: "2024-01-15 09:30:00",
        elapsedTime: "8分钟",
        estimatedTime: "-",
        currentStep: "已完成",
        details: "同步2023Q4财报数据",
        syncedCount: 1200,
        totalCount: 1200,
      },
      {
        id: "3",
        taskType: "增量同步",
        dataCategory: "基本面数据",
        progress: 35,
        status: "failed",
        startTime: "2024-01-15 10:05:00",
        elapsedTime: "3分钟",
        estimatedTime: "-",
        currentStep: "写入数据库",
        details: "同步上市公司基本信息",
        syncedCount: 700,
        totalCount: 2000,
        errorMsg: "数据库连接超时，已重试3次",
      },
      {
        id: "4",
        taskType: "全量同步",
        dataCategory: "指数成分股",
        progress: 0,
        status: "paused",
        startTime: "2024-01-15 10:10:00",
        elapsedTime: "2分钟",
        estimatedTime: "约12分钟",
        currentStep: "获取成分股列表",
        details: "同步中证500成分股变动",
        syncedCount: 0,
        totalCount: 500,
      },
    ];
    pageState.value = tasks.value.length === 0 ? "empty" : "data";
  } catch {
    pageState.value = "error";
  }
};

const handleControlTask = async (
  taskId: string,
  action: "pause" | "resume" | "stop" | "retry",
) => {
  try {
    const task = tasks.value.find((t) => t.id === taskId);
    const actionText: Record<string, string> = {
      pause: "已暂停",
      resume: "已恢复",
      stop: "已停止",
      retry: "正在重试",
    };
    message.success(`${actionText[action]}任务: ${task?.dataCategory || taskId}`);
    await loadTasks(false);
  } catch {
    message.error("操作失败，请重试");
  }
};

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) {
    refreshInterval = window.setInterval(() => loadTasks(false), 5000);
  } else {
    if (refreshInterval) clearInterval(refreshInterval);
  }
};

const getStatusType = (
  status: string,
): "default" | "success" | "warning" | "error" | "info" => {
  const map: Record<string, "default" | "success" | "warning" | "error" | "info"> = {
    running: "info", paused: "warning", completed: "success", failed: "error",
  };
  return map[status] || "default";
};

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    running: "运行中", paused: "已暂停", completed: "已完成", failed: "失败",
  };
  return map[status] || status;
};

const getProgressStatus = (status: string): "success" | "warning" | "error" | "default" => {
  if (status === "failed") return "error";
  if (status === "completed") return "success";
  if (status === "paused") return "warning";
  return "default";
};

onMounted(() => {
  loadTasks();
  refreshInterval = window.setInterval(() => loadTasks(false), 5000);
});

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>

<template>
  <div class="task-monitor-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步任务监控</h1>
          <p class="page-description">实时监控数据同步任务执行状态和进度</p>
        </div>
        <div class="header-actions">
          <n-tag
            size="small"
            :type="autoRefresh ? 'success' : 'default'"
            :bordered="false"
            round
            class="auto-refresh-tag"
          >
            {{ autoRefresh ? "自动刷新中" : "已停止刷新" }}
          </n-tag>
          <n-button class="action-btn" @click="toggleAutoRefresh" quaternary>
            <template #icon>
              <SmartIcon :name="autoRefresh ? 'PauseCircle' : 'PlayCircle'" />
            </template>
          </n-button>
          <n-button class="action-btn" @click="loadTasks()" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <template v-if="pageState === 'loading'">
        <n-grid :cols="4" :x-gap="16" class="stats-row">
          <n-grid-item v-for="i in 4" :key="i">
            <n-card><n-skeleton :text="true" :repeat="2" /></n-card>
          </n-grid-item>
        </n-grid>
        <n-card class="monitor-card">
          <n-skeleton :text="true" :repeat="6" />
        </n-card>
      </template>

      <!-- Error -->
      <n-result
        v-else-if="pageState === 'error'"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadTasks()">重试</n-button>
        </template>
      </n-result>

      <!-- Empty -->
      <n-empty
        v-else-if="pageState === 'empty'"
        description="暂无同步任务"
        class="empty-state"
      >
        <template #extra>
          <n-button size="small" @click="loadTasks()">刷新</n-button>
        </template>
      </n-empty>

      <!-- Data -->
      <template v-else>
        <n-grid :cols="4" :x-gap="16" class="stats-row">
          <n-grid-item>
            <n-card class="stat-card">
              <n-statistic label="运行中" :value="stats.running">
                <template #prefix>
                  <SmartIcon name="Sync" class="stat-icon running" />
                </template>
              </n-statistic>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card class="stat-card">
              <n-statistic label="已完成" :value="stats.completed">
                <template #prefix>
                  <SmartIcon name="CheckCircle" class="stat-icon completed" />
                </template>
              </n-statistic>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card class="stat-card">
              <n-statistic label="失败" :value="stats.failed">
                <template #prefix>
                  <SmartIcon name="CloseCircle" class="stat-icon failed" />
                </template>
              </n-statistic>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card class="stat-card">
              <n-statistic label="已暂停" :value="stats.paused">
                <template #prefix>
                  <SmartIcon name="PauseCircle" class="stat-icon paused" />
                </template>
              </n-statistic>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-card class="monitor-card">
          <n-list>
            <n-list-item v-for="item in tasks" :key="item.id" class="task-item">
              <div class="task-item-content">
                <div class="task-header">
                  <div class="task-title">
                    <span class="task-name">{{ item.dataCategory }} - {{ item.taskType }}</span>
                    <n-tag :type="getStatusType(item.status)" :bordered="false" size="small">
                      {{ getStatusText(item.status) }}
                    </n-tag>
                  </div>
                  <div class="task-description">{{ item.details }}</div>
                </div>

                <div class="task-progress-section">
                  <n-progress
                    :percentage="item.progress"
                    :status="getProgressStatus(item.status)"
                    :height="6"
                    :border-radius="3"
                    class="task-progress"
                  />
                  <span class="task-count">
                    已同步 {{ item.syncedCount.toLocaleString() }} / {{ item.totalCount.toLocaleString() }} 条
                  </span>
                </div>

                <div class="task-footer">
                  <span class="task-meta">开始时间: {{ item.startTime }}</span>
                  <span class="task-meta">已运行: {{ item.elapsedTime }}</span>
                  <span class="task-meta">预估剩余: {{ item.estimatedTime }}</span>
                  <span class="task-meta">当前: {{ item.currentStep }}</span>
                </div>

                <div v-if="item.errorMsg" class="task-error">
                  <SmartIcon name="AlertCircle" size="14" />
                  {{ item.errorMsg }}
                </div>

                <div class="task-actions">
                  <n-button
                    v-if="item.status === 'running'"
                    type="warning"
                    size="small"
                    @click="handleControlTask(item.id, 'pause')"
                  >
                    <template #icon><SmartIcon name="PauseCircle" /></template>
                    暂停
                  </n-button>
                  <n-button
                    v-if="item.status === 'paused'"
                    type="success"
                    size="small"
                    @click="handleControlTask(item.id, 'resume')"
                  >
                    <template #icon><SmartIcon name="PlayCircle" /></template>
                    继续
                  </n-button>
                  <n-button
                    v-if="item.status === 'failed'"
                    type="primary"
                    size="small"
                    @click="handleControlTask(item.id, 'retry')"
                  >
                    <template #icon><SmartIcon name="Refresh" /></template>
                    重试
                  </n-button>
                  <n-button
                    v-if="item.status === 'running' || item.status === 'paused'"
                    type="error"
                    size="small"
                    @click="handleControlTask(item.id, 'stop')"
                  >
                    <template #icon><SmartIcon name="CloseCircle" /></template>
                    停止
                  </n-button>
                </div>
              </div>
            </n-list-item>
          </n-list>
        </n-card>
      </template>
    </div>
  </div>
</template>
<style scoped lang="scss">
.task-monitor-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;

  /* .action-btn 圆形成样式已迁移至全局 global.scss */
}

.auto-refresh-tag {
  font-size: 11px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  .stat-icon {
    font-size: 20px;
    &.running   { color: var(--n-primary-color); }
    &.completed { color: var(--color-stock-up, #FF5252); }
    &.failed    { color: var(--color-stock-down, #00E676); }
    &.paused    { color: var(--n-warning-color); }
  }
}

.empty-state {
  margin-top: 60px;
}

.monitor-card {
  /* margin handled by main-content padding */
}

.task-item {
  margin-bottom: 12px;
  padding: 16px;
  border-radius: var(--n-border-radius);
  border: 1px solid var(--n-border-color);
  transition: all 0.3s ease;

  &:hover {
    background: rgba(68, 138, 255, 0.04);
    border-color: rgba(68, 138, 255, 0.15);
  }

  :deep(.n-list-item__main) {
    width: 100%;
  }
}

.task-item-content {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.task-name {
  color: var(--n-text-color-1);
  font-weight: 600;
  font-size: 14px;
}

.task-description {
  color: var(--n-text-color-2);
  font-size: 13px;
}

.task-progress-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-progress {
  flex: 1;
  max-width: 400px;
}

.task-count {
  font-size: 12px;
  color: var(--n-text-color-3);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.task-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.task-meta {
  color: var(--n-text-color-3);
  font-size: 12px;
}

.task-error {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 4px;
  background: rgba(208, 48, 80, 0.08);
  color: var(--color-stock-down, #00E676);
  font-size: 12px;
}

.task-actions {
  display: flex;
  gap: 8px;
}

// 响应式
@media (max-width: 768px) {
  .task-actions {
    flex-direction: column;

    .n-button {
      width: 100%;
      justify-content: center;
    }
  }
}
</style>
