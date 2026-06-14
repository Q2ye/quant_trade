<template>
  <div class="sync-detail bg-gradient-mesh bg-noise">
    <!-- Header -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步任务详情</h1>
          <p class="page-description">查看数据同步任务执行详情与统计信息</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="goBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="detail-content">
      <!-- Loading -->
      <n-skeleton v-if="loading" :text="true" :repeat="8" height="40px" />

      <!-- Error -->
      <n-result
        v-else-if="error"
        status="500"
        title="加载失败"
        description="无法加载任务详情"
      >
        <template #footer>
          <n-button type="primary" @click="loadTask">重试</n-button>
        </template>
      </n-result>

      <!-- Data -->
      <template v-else-if="task">
        <!-- Overview Card -->
        <n-card class="detail-card" :bordered="true">
          <template #header>
            <div class="card-title-row">
              <span>概览</span>
              <n-tag :type="statusTagType(task.status)" size="small">{{
                statusLabel(task.status)
              }}</n-tag>
            </div>
          </template>
          <n-grid :cols="2" :x-gap="16" :y-gap="12">
            <n-grid-item
              ><span class="meta-label">任务ID</span
              ><span class="meta-value mono">{{
                task.task_id
              }}</span></n-grid-item
            >
            <n-grid-item
              ><span class="meta-label">类型</span
              ><span class="meta-value">{{
                task.task_label || task.task_type
              }}</span></n-grid-item
            >
            <n-grid-item
              ><span class="meta-label">开始时间</span
              ><span class="meta-value">{{
                fmtDate(task.start_time)
              }}</span></n-grid-item
            >
            <n-grid-item
              ><span class="meta-label">结束时间</span
              ><span class="meta-value">{{
                fmtDate(task.end_time) || "—"
              }}</span></n-grid-item
            >
            <n-grid-item v-if="duration"
              ><span class="meta-label">耗时</span
              ><span class="meta-value">{{ duration }}</span></n-grid-item
            >
            <n-grid-item
              ><span class="meta-label">用户</span
              ><span class="meta-value">{{
                task.user_id || "—"
              }}</span></n-grid-item
            >
            <n-grid-item v-if="task.data_types?.length" :span="2">
              <span class="meta-label">包含类型</span>
              <span class="meta-value">{{ task.data_types.join("、") }}</span>
            </n-grid-item>
          </n-grid>
        </n-card>

        <!-- Stats Card -->
        <n-card class="detail-card" :bordered="true">
          <template #header><span>同步统计</span></template>
          <div class="stats-row">
            <div class="stat-item green">
              <span class="stat-num">{{ task.records_succeeded || 0 }}</span
              ><span class="stat-label">新增</span>
            </div>
            <div class="stat-item blue">
              <span class="stat-num">{{ task.records_processed || 0 }}</span
              ><span class="stat-label">处理</span>
            </div>
            <div class="stat-item orange">
              <span class="stat-num">{{ task.total_records || 0 }}</span
              ><span class="stat-label">总计</span>
            </div>
            <div class="stat-item red">
              <span class="stat-num">{{ task.records_failed || 0 }}</span
              ><span class="stat-label">失败</span>
            </div>
          </div>
        </n-card>

        <!-- Children Tasks (batch 任务的子类型明细) -->
        <n-card
          v-if="task.children && task.children.length"
          class="detail-card"
          :bordered="true"
        >
          <template #header
            ><span>子任务明细（{{ task.children.length }} 项）</span></template
          >
          <n-data-table
            :columns="childColumns"
            :data="task.children"
            :bordered="false"
            size="small"
          />
        </n-card>

        <!-- Error Message -->
        <n-card
          v-if="task.error_message"
          class="detail-card error-card"
          :bordered="true"
        >
          <template #header><span class="error-title">错误信息</span></template>
          <n-code :code="task.error_message" language="text" word-wrap />
        </n-card>

        <!-- Parameters -->
        <n-card
          v-if="task.parameters && Object.keys(task.parameters).length"
          class="detail-card"
          :bordered="true"
        >
          <template #header><span>同步参数</span></template>
          <n-code
            :code="JSON.stringify(task.parameters, null, 2)"
            language="json"
          />
        </n-card>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  NCard,
  NButton,
  NTag,
  NGrid,
  NGridItem,
  NSkeleton,
  NResult,
  NCode,
  NDataTable,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import type { SyncTaskRecord } from "@/api/data-sync";
import { dataSyncService } from "@/api/data-sync";
import SmartIcon from "@/components/common/SmartIcon.vue";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const taskId = computed(() => route.params.taskId as string);

const loading = ref(true);
const error = ref(false);
const task = ref<SyncTaskRecord | null>(null);

const duration = computed(() => {
  if (!task.value?.start_time) return "";
  const end = task.value.end_time ? new Date(task.value.end_time) : new Date();
  const start = new Date(task.value.start_time);
  const secs = Math.round((end.getTime() - start.getTime()) / 1000);
  if (secs < 60) return `${secs}秒`;
  if (secs < 3600) return `${Math.floor(secs / 60)}分${secs % 60}秒`;
  return `${Math.floor(secs / 3600)}时${Math.floor((secs % 3600) / 60)}分`;
});

function goBack() {
  router.push({ name: "SyncHistory" });
}

const childColumns: DataTableColumns<SyncTaskRecord> = [
  {
    title: "类型",
    key: "task_label",
    width: 180,
    render: (row) => row.task_label || row.task_type,
  },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row) =>
      h(NTag, { type: statusTagType(row.status), size: "tiny" }, () =>
        statusLabel(row.status),
      ),
  },
  {
    title: "新增",
    key: "records_succeeded",
    width: 80,
    render: (row) => row.records_succeeded?.toLocaleString() || "0",
  },
  {
    title: "更新",
    key: "records_processed",
    width: 80,
    render: (row) =>
      (
        (row.records_processed || 0) - (row.records_succeeded || 0)
      ).toLocaleString(),
  },
  {
    title: "失败",
    key: "records_failed",
    width: 80,
    render: (row) =>
      h(
        "span",
        { style: row.records_failed ? "color:var(--color-error)" : "" },
        row.records_failed?.toLocaleString() || "0",
      ),
  },
  {
    title: "耗时",
    key: "duration",
    width: 100,
    render: (row) => {
      if (!row.start_time) return "—";
      const s = new Date(row.start_time);
      const e = row.end_time ? new Date(row.end_time) : new Date();
      const sec = Math.round((e.getTime() - s.getTime()) / 1000);
      return sec < 60
        ? `${sec}s`
        : sec < 3600
          ? `${Math.floor(sec / 60)}m`
          : `${Math.floor(sec / 3600)}h`;
    },
  },
];

function fmtDate(s?: string): string {
  if (!s) return "";
  const d = new Date(s);
  return d.toLocaleString("zh-CN", { hour12: false });
}

function statusTagType(
  s: string,
): "success" | "error" | "warning" | "info" | "default" {
  const map: Record<string, string> = {
    completed: "success",
    failed: "error",
    running: "info",
    cancelled: "warning",
    pending: "default",
  };
  return (map[s] || "default") as any;
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    completed: "已完成",
    failed: "失败",
    running: "运行中",
    cancelled: "已取消",
    pending: "等待中",
  };
  return map[s] || s;
}

async function loadTask() {
  loading.value = true;
  error.value = false;
  try {
    const tasksRes = await dataSyncService.getSyncTasks({ limit: 200 });
    const found = tasksRes?.tasks?.find(
      (t: SyncTaskRecord) =>
        t.task_id === taskId.value || t.id === taskId.value,
    );
    if (found) {
      task.value = found;
    } else {
      error.value = true;
      message.warning("未找到该任务记录");
    }
  } catch (e: any) {
    error.value = true;
    message.error(e?.message || "加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(loadTask);
</script>

<style lang="scss" scoped>
.detail-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-card {
  border-radius: 12px;
}
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.meta-label {
  font-size: 13px;
  color: var(--n-text-color-3);
  display: block;
}
.meta-value {
  font-size: 14px;
  &.mono {
    font-family: monospace;
    font-size: 12px;
  }
}
.stats-row {
  display: flex;
  gap: 24px;
  justify-content: center;
}
.stat-item {
  text-align: center;
}
.stat-num {
  display: block;
  font-size: 28px;
  font-weight: 700;
}
.stat-label {
  font-size: 13px;
  color: var(--n-text-color-3);
}
.stat-item.green .stat-num {
  color: var(--n-success-color);
}
.stat-item.blue .stat-num {
  color: var(--n-info-color);
}
.stat-item.orange .stat-num {
  color: var(--n-warning-color);
}
.stat-item.red .stat-num {
  color: var(--n-error-color);
}
.error-card {
  border-color: var(--n-error-color);
}
.error-title {
  color: var(--n-error-color);
}

@media (max-width: 768px) {
  .detail-content {
    padding: 0 12px;
  }
}
</style>
