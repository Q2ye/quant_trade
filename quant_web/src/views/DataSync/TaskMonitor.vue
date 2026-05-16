<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import {
  NButton,
  NCard,
  NList,
  NListItem,
  NProgress,
  NSpace,
  NTag,
  NEmpty,
} from "naive-ui";
import { useRouter } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";

const router = useRouter();

interface SyncTask {
  id: string;
  taskType: string;
  dataCategory: string;
  progress: number;
  status: "running" | "paused" | "completed" | "failed";
  startTime: string;
  elapsedTime: string;
  currentStep: string;
  details: string;
}

const handleBack = () => {
  router.go(-1);
};

const tasks = ref<SyncTask[]>([]);
const loading = ref(false);
let refreshInterval: number | undefined;

const loadTasks = async () => {
  loading.value = true;
  try {
    tasks.value = [
      {
        id: "1",
        taskType: "数据同步",
        dataCategory: "市场数据",
        progress: 75,
        status: "running",
        startTime: "2024-01-15 10:00:00",
        elapsedTime: "15分钟",
        currentStep: "处理K线数据",
        details: "同步沪深300指数数据",
      },
    ];
  } catch (error) {
    console.error("加载任务失败:", error);
  } finally {
    loading.value = false;
  }
};

const handleControlTask = async (
  taskId: string,
  action: "pause" | "resume" | "stop",
) => {
  try {
    console.log(`执行操作: ${action} 任务: ${taskId}`);
    await loadTasks();
  } catch (error) {
    console.error("操作失败:", error);
  }
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    running: "var(--color-primary)",
    paused: "var(--color-warning)",
    completed: "var(--color-success)",
    failed: "var(--color-error)",
  };
  return colors[status] || "default";
};

const getStatusType = (
  status: string,
): "default" | "success" | "warning" | "error" | "info" => {
  const types: Record<
    string,
    "default" | "success" | "warning" | "error" | "info"
  > = {
    running: "info",
    paused: "warning",
    completed: "success",
    failed: "error",
  };
  return types[status] || "default";
};

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    running: "运行中",
    paused: "已暂停",
    completed: "已完成",
    failed: "失败",
  };
  return texts[status] || status;
};

onMounted(() => {
  loadTasks();
  refreshInterval = window.setInterval(loadTasks, 5000);
});

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>

<template>
  <div class="task-monitor-page">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步任务监控</h1>
          <p class="page-description">实时监控数据同步任务执行状态和进度</p>
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

    <n-card class="monitor-card">
      <n-list v-if="tasks.length > 0">
        <n-list-item v-for="item in tasks" :key="item.id" class="task-item">
          <div class="task-item-content">
            <div class="task-header">
              <div class="task-title">
                <span class="task-name"
                  >{{ item.dataCategory }} - {{ item.taskType }}</span
                >
                <n-tag
                  :type="getStatusType(item.status)"
                  :bordered="false"
                  size="small"
                >
                  {{ getStatusText(item.status) }}
                </n-tag>
              </div>
              <div class="task-description">{{ item.details }}</div>
            </div>

            <n-progress
              :percentage="item.progress"
              :status="item.status === 'failed' ? 'error' : 'default'"
              :color="
                item.status === 'failed'
                  ? 'var(--color-error)'
                  : 'var(--color-primary)'
              "
              :height="6"
              class="task-progress"
            />

            <div class="task-footer">
              <span class="task-meta">开始时间: {{ item.startTime }}</span>
              <span class="task-meta">已运行: {{ item.elapsedTime }}</span>
              <span class="task-meta">当前步骤: {{ item.currentStep }}</span>
            </div>

            <div class="task-actions">
              <n-button
                v-if="item.status === 'running'"
                type="warning"
                size="small"
                @click="handleControlTask(item.id, 'pause')"
              >
                <template #icon>
                  <SmartIcon name="PauseCircle" />
                </template>
                暂停
              </n-button>
              <n-button
                v-if="item.status === 'paused'"
                type="success"
                size="small"
                @click="handleControlTask(item.id, 'resume')"
              >
                <template #icon>
                  <SmartIcon name="PlayCircle" />
                </template>
                继续
              </n-button>
              <n-button
                type="error"
                size="small"
                @click="handleControlTask(item.id, 'stop')"
              >
                <template #icon>
                  <SmartIcon name="CloseCircle" />
                </template>
                停止
              </n-button>
            </div>
          </div>
        </n-list-item>
      </n-list>

      <n-empty v-else description="暂无同步任务">
        <template #extra>
          <n-button size="small" @click="loadTasks">刷新</n-button>
        </template>
      </n-empty>
    </n-card>
  </div>
</template>
<style scoped lang="scss">
@use "@/styles/variables" as *;
@use "@/styles/mixins" as mixin;
@use "sass:map";

.task-monitor-page {
  padding: 0;
  max-width: 1400px;
  margin: 0 auto;
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
      flex-shrink: 0;
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
  height: $button-height;

  :deep(.n-button__border) {
    border-color: rgba(255, 255, 255, 0.3);
  }
}

.monitor-card {
  margin: 0 map.get($spacers, 4);
}

.task-item {
  margin-bottom: map.get($spacers, 2);
  padding: map.get($spacers, 3);
  border-radius: var(--n-border-radius);
  border: 1px solid var(--n-border-color);
  transition: all $transition-normal;

  &:hover {
    background: $hover-bg;
    transform: $hover-transform;
    box-shadow: $card-hover-shadow;
  }
}

.task-item-content {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: map.get($spacers, 2);
}

.task-header {
  display: flex;
  flex-direction: column;
  gap: map.get($spacers, 1);
}

.task-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: map.get($spacers, 2);
}

.task-name {
  color: $text-color-1;
  font-weight: $font-weight-semibold;
}

.task-description {
  color: $text-color-2;
  font-size: 0.85rem;
}

.task-progress {
  max-width: 100%;
}

.task-footer {
  display: flex;
  flex-wrap: wrap;
  gap: map.get($spacers, 3);
}

.task-meta {
  color: $text-color-3;
  font-size: 0.8rem;
}

.task-actions {
  display: flex;
  gap: map.get($spacers, 2);
}

// 响应式调整
@include mixin.media-breakpoint-down(md) {
  .page-header .header-content {
    flex-direction: column;
    gap: map.get($spacers, 3);
    text-align: center;

    .header-actions-right {
      order: -1;
      align-self: stretch;
      justify-content: space-between;
      margin-bottom: map.get($spacers, 2);
    }
  }

  .monitor-card {
    margin: 0 map.get($spacers, 3);
  }
}

@include mixin.media-breakpoint-down(sm) {
  .monitor-card {
    margin: 0 map.get($spacers, 2);
  }

  .task-actions {
    flex-direction: column;

    .n-button {
      width: 100%;
      justify-content: center;
    }
  }
}
</style>
