<template>
  <div class="research-history bg-gradient-mesh bg-noise">
    <!-- Page Header -->
    <div class="page-header" :class="tokens.surface.glass">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">研究历史</h1>
          <p class="page-description">
            共 {{ totalCount }} 个研究任务
          </p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" size="small" @click="loadTasks" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" size="small" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-row">
      <div class="filter-controls">
        <n-button size="small" :type="filterStatus === '' ? 'primary' : 'default'" quaternary @click="filterStatus = ''">
          全部
        </n-button>
        <n-button size="small" :type="filterStatus === 'running' ? 'info' : 'default'" quaternary @click="filterStatus = 'running'">
          运行中
        </n-button>
        <n-button size="small" :type="filterStatus === 'completed' ? 'success' : 'default'" quaternary @click="filterStatus = 'completed'">
          已完成
        </n-button>
        <n-button size="small" :type="filterStatus === 'failed' ? 'error' : 'default'" quaternary @click="filterStatus = 'failed'">
          失败
        </n-button>
        <n-button v-if="checkedRowKeys.length > 0" size="small" type="error" quaternary @click="confirmBatchDelete">
          删除选中 ({{ checkedRowKeys.length }})
        </n-button>
      </div>
    </div>

    <!-- Content Area -->
    <div class="content-area">
      <!-- Loading -->
      <n-card v-if="loading && tasks.length === 0" :class="tokens.surface.card">
        <n-skeleton text :repeat="8" />
      </n-card>

      <!-- Error -->
      <n-result
        v-else-if="error"
        status="error"
        title="加载失败"
        description="获取研究任务列表失败，请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadTasks">重试</n-button>
        </template>
      </n-result>

      <!-- Empty -->
      <div v-else-if="filteredTasks.length === 0 && !loading" class="empty-state">
        <n-empty
          :description="filterStatus ? '没有匹配状态的研究任务' : '暂无研究任务'"
          style="padding: 60px 0"
        >
          <template #extra>
            <n-button
              v-if="!filterStatus"
              type="primary"
              @click="router.push('/factors')"
            >
              发起第一个研究
            </n-button>
          </template>
        </n-empty>
      </div>

      <!-- Data Table -->
      <n-card v-else :class="tokens.surface.card" size="small" content-class="!p-0">
        <n-data-table
          :columns="columns"
          :data="filteredTasks"
          :row-key="(row: ResearchTaskSummary) => row.research_id"
          :row-props="rowProps"
          :checked-row-keys="checkedRowKeys"
          @update:checked-row-keys="(keys: any) => checkedRowKeys = keys"
          size="small"
          :loading="loading"
          :single-line="false"
        />
      </n-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
  NCard,
  NDataTable,
  NTag,
  NProgress,
  NButton,
  NSelect,
  NEmpty,
  NSkeleton,
  NResult,
  useMessage,
  useDialog,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import dataAPI from "@/api/data";
import type { ResearchTaskSummary, ResearchStatus } from "@/types/api-research";
import { useResearchStatus } from "@/composables/useResearchStatus";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();

// ---- State ----
const loading = ref(true);
const error = ref(false);
const tasks = ref<ResearchTaskSummary[]>([]);
const totalCount = ref(0);
const filterStatus = ref("");
const checkedRowKeys = ref<string[]>([]);

const statusOptions = [
  { label: "全部", value: "" },
  { label: "运行中", value: "running" as string },
  { label: "已完成", value: "completed" as string },
  { label: "失败", value: "failed" as string },
  { label: "已取消", value: "cancelled" as string },
  { label: "等待中", value: "pending" as string },
];

// ---- Derived ----
const filteredTasks = computed(() => {
  if (!filterStatus.value) return tasks.value;
  return tasks.value.filter((t) => t.status === filterStatus.value);
});

const { statusTagType, statusLabel } = useResearchStatus();

// ---- Columns ----
const columns: any[] = [
  { type: "selection" },
  {
    title: "研究名称",
    key: "research_name",
    width: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: "因子",
    key: "factor_name",
    width: 150,
    ellipsis: { tooltip: true },
  },
  {
    title: "状态",
    key: "status",
    width: 90,
    render: (row: ResearchTaskSummary) => {
      return h(NTag, {
        type: statusTagType(row.status),
        size: "small",
        bordered: false,
      }, () => statusLabel(row.status));
    },
  },
  {
    title: "进度",
    key: "progress",
    width: 160,
    render: (row: ResearchTaskSummary) => {
      return h(NProgress, {
        type: "line",
        percentage: Math.round(row.progress || 0),
        indicatorPlacement: "inside",
        height: 20,
        borderRadius: 4,
        status: row.status === "failed" ? "error" : row.status === "completed" ? "success" : "default",
      });
    },
  },
  {
    title: "创建时间",
    key: "created_at",
    width: 160,
    render: (row: ResearchTaskSummary) => {
      const dateStr = row.created_at
        ? new Date(row.created_at).toLocaleString("zh-CN", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "--";
      return dateStr;
    },
  },
  {
    title: "操作",
    key: "actions",
    width: 100,
    render: (row: ResearchTaskSummary) => {
      if (row.status === "running" || row.status === "pending") {
        return h(NButton, {
          size: "tiny",
          type: "warning",
          quaternary: true,
          onClick: () => {
            dialog.warning({
              title: "取消研究",
              content: "确定取消该研究任务吗？",
              positiveText: "确定",
              negativeText: "取消",
              onPositiveClick: () => handleCancel(row.research_id),
            });
          },
        }, () => "取消");
      }
      return h(NButton, {
        size: "tiny",
        type: "error",
        quaternary: true,
        onClick: () => {
          dialog.warning({
            title: "删除记录",
            content: "确定删除该研究记录吗？",
            positiveText: "确定",
            negativeText: "取消",
            onPositiveClick: () => handleDelete(row.research_id),
          });
        },
      }, () => "删除");
    },
  },
];

const rowProps = (_row: ResearchTaskSummary) => ({});

// ---- Actions ----
const loadTasks = async () => {
  checkedRowKeys.value = [];
  loading.value = true;
  error.value = false;
  try {
    const res = await dataAPI.getRecentResearchTasks();
    if (res?.recent_tasks) {
      tasks.value = res.recent_tasks;
      totalCount.value = res.total_count || res.recent_tasks.length;
    } else {
      tasks.value = [];
      totalCount.value = 0;
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleCancel = async (researchId: string) => {
  try {
    const res = await dataAPI.cancelFactorResearch(researchId);
    if (res?.success) {
      message.success("任务已取消");
      // Update local state
      const task = tasks.value.find((t) => t.research_id === researchId);
      if (task) task.status = "cancelled";
    } else {
      message.error(res?.message || "取消失败");
    }
  } catch {
    message.error("取消失败");
  }
};

const handleDelete = async (researchId: string) => {
  try {
    const res = await dataAPI.deleteFactorResearch(researchId).catch(() => null);
    if (res?.success) {
      message.success("已删除");
      tasks.value = tasks.value.filter((t) => t.research_id !== researchId);
    } else {
      message.error(res?.message || "删除失败");
    }
  } catch {
    message.error("删除失败");
  }
};

const handleBatchDelete = async () => {
  let deleted = 0;
  for (const rid of checkedRowKeys.value) {
    const res = await dataAPI.deleteFactorResearch(rid).catch(() => null);
    if (res?.success) deleted++;
  }
  message.success(`已删除 ${deleted}/${checkedRowKeys.value.length} 条`);
  checkedRowKeys.value = [];
  loadTasks();
};

const confirmBatchDelete = () => {
  dialog.warning({
    title: "批量删除",
    content: `确定删除选中的 ${checkedRowKeys.value.length} 条记录吗？`,
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: () => handleBatchDelete(),
  });
};

onMounted(() => {
  loadTasks();
});
</script>

<style lang="scss" scoped>
.research-history {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;

  .page-header {
    flex-shrink: 0;
    position: sticky;
    top: 0;
    z-index: 10;
  }
}

.content-area {
  padding: 10px 24px 24px;
  flex: 1;
}

.filter-row {
  padding: 10px 32px 8px;
  .filter-controls {
    display: flex;
    align-items: center;
    gap: 10px;
  }
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
