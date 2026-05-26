<!-- SyncHistory.vue - 同步历史记录页面 -->
<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NAlert,
  NButton,
  NCard,
  NDatePicker,
  NDescriptions,
  NDescriptionsItem,
  NDivider,
  NDrawer,
  NEmpty,
  NProgress,
  NResult,
  NSelect,
  NSkeleton,
  NSpace,
  NSpin,
  NTag,
  NDataTable,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import type { DataTableColumns } from "naive-ui";

const router = useRouter();
const message = useMessage();

interface SyncRecord {
  id: string;
  task_id: string;
  data_types: string[];
  status: "completed" | "running" | "failed" | "cancelled";
  start_time: string;
  end_time?: string;
  duration?: number;
  total_tasks: number;
  completed_tasks: number;
  data_volume?: number;
  results: Record<string, any>;
  error?: string;
}

type PageState = "loading" | "error" | "empty" | "data";

const pageState = ref<PageState>("loading");
const records = ref<SyncRecord[]>([]);
const selectedRecord = ref<SyncRecord | null>(null);
const drawerVisible = ref(false);

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
});

const filters = reactive({
  status: "",
  dataType: "",
  dateRange: null as [number, number] | null,
});

const statusOptions = [
  { label: "全部状态", value: "" },
  { label: "完成", value: "completed" },
  { label: "运行中", value: "running" },
  { label: "失败", value: "failed" },
  { label: "已取消", value: "cancelled" },
];

const dataTypeOptions = [
  { label: "全部类型", value: "" },
  { label: "市场数据", value: "market" },
  { label: "K线数据", value: "kline" },
  { label: "财务数据", value: "financial" },
  { label: "基本面数据", value: "fundamental" },
];

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/");
};

const getStatusType = (
  status: string,
): "default" | "success" | "info" | "warning" | "error" => {
  const map: Record<string, "default" | "success" | "info" | "warning" | "error"> = {
    completed: "success", running: "info", failed: "error", cancelled: "warning",
  };
  return map[status] || "default";
};

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    completed: "完成", running: "运行中", failed: "失败", cancelled: "已取消",
  };
  return map[status] || status;
};

const formatDuration = (seconds?: number) => {
  if (seconds == null) return "-";
  if (seconds < 60) return `${seconds}秒`;
  return `${Math.round(seconds / 60)}分${seconds % 60}秒`;
};

const columns: DataTableColumns<SyncRecord> = [
  {
    title: "任务ID", key: "task_id", width: 110,
  },
  {
    title: "数据类型", key: "data_types", width: 130,
    render: (row) => row.data_types.join(", "),
  },
  {
    title: "状态", key: "status", width: 80,
    render: (row) =>
      h(NTag, { type: getStatusType(row.status), bordered: false, size: "small" }, { default: () => getStatusText(row.status) }),
  },
  {
    title: "进度", key: "progress", width: 120,
    render: (row) =>
      h("div", { style: { display: "flex", alignItems: "center", gap: "8px" } }, [
        h(NProgress, {
          type: "line",
          percentage: row.total_tasks > 0 ? Math.round((row.completed_tasks / row.total_tasks) * 100) : 0,
          status: row.status === "failed" ? "error" : row.status === "completed" ? "success" : "default",
          height: 6,
          borderRadius: 3,
          style: { width: "60px" },
        }),
        h("span", { style: { fontSize: "12px", whiteSpace: "nowrap" } }, `${row.completed_tasks}/${row.total_tasks}`),
      ]),
  },
  {
    title: "数据量", key: "data_volume", width: 80,
    render: (row) => row.data_volume ? `${(row.data_volume / 10000).toFixed(1)}万` : "-",
  },
  {
    title: "开始时间", key: "start_time", width: 140,
  },
  {
    title: "结束时间", key: "end_time", width: 140,
    render: (row) => row.end_time || "-",
  },
  {
    title: "耗时", key: "duration", width: 80,
    render: (row) => formatDuration(row.duration),
  },
  {
    title: "操作", key: "actions", width: 80, fixed: "right",
    render: (row) =>
      h(NButton, { text: true, size: "small", onClick: () => showDetails(row) }, { default: () => "详情" }),
  },
];

const showDetails = (record: SyncRecord) => {
  selectedRecord.value = record;
  drawerVisible.value = true;
};

const closeDrawer = () => {
  drawerVisible.value = false;
  selectedRecord.value = null;
};

const handleReset = () => {
  filters.status = "";
  filters.dataType = "";
  filters.dateRange = null;
  pagination.current = 1;
  loadHistory();
};

const handleRetryTask = (taskId: string) => {
  message.success(`正在重试任务: ${taskId}`);
};

const loadHistory = async () => {
  pageState.value = "loading";
  try {
    await new Promise((r) => setTimeout(r, 500));
    records.value = [
      {
        id: "1",
        task_id: "TASK_001",
        data_types: ["市场数据", "K线数据"],
        status: "completed",
        start_time: "2024-01-15 10:00:00",
        end_time: "2024-01-15 10:15:00",
        duration: 900,
        total_tasks: 100,
        completed_tasks: 100,
        data_volume: 2350000,
        results: { 市场数据: { error: null }, K线数据: { error: null } },
      },
      {
        id: "2",
        task_id: "TASK_002",
        data_types: ["财务数据"],
        status: "failed",
        start_time: "2024-01-15 09:30:00",
        end_time: "2024-01-15 09:33:00",
        duration: 180,
        total_tasks: 50,
        completed_tasks: 23,
        data_volume: 450000,
        results: { 财务数据: { error: "数据库写入超时" } },
        error: "部分数据同步失败，已自动回滚",
      },
      {
        id: "3",
        task_id: "TASK_003",
        data_types: ["基本面数据"],
        status: "cancelled",
        start_time: "2024-01-15 08:00:00",
        end_time: "2024-01-15 08:05:00",
        duration: 300,
        total_tasks: 80,
        completed_tasks: 35,
        results: { 基本面数据: { error: null } },
      },
    ];
    pagination.total = 156;
    pageState.value = records.value.length === 0 ? "empty" : "data";
  } catch {
    pageState.value = "error";
  }
};

// 筛选变更自动查询
watch(
  () => [filters.status, filters.dataType, filters.dateRange],
  () => {
    pagination.current = 1;
    loadHistory();
  },
);

onMounted(() => {
  loadHistory();
});
</script>

<template>
  <div class="sync-history-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步历史记录</h1>
          <p class="page-description">查看和管理历史数据同步任务记录</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="loadHistory" quaternary>
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
        <n-card class="history-card">
          <div class="filter-bar"><n-skeleton :text="true" width="60%" /></div>
          <n-skeleton :text="true" :repeat="8" />
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
          <n-button type="primary" @click="loadHistory">重试</n-button>
        </template>
      </n-result>

      <!-- Empty -->
      <n-card v-else-if="pageState === 'empty'" class="history-card">
        <div class="filter-bar">
          <n-space :size="12" wrap>
            <n-select
              v-model:value="filters.status"
              placeholder="状态筛选"
              style="width: 120px"
              clearable
              :options="statusOptions"
            />
            <n-select
              v-model:value="filters.dataType"
              placeholder="数据类型"
              style="width: 130px"
              clearable
              :options="dataTypeOptions"
            />
            <n-date-picker
              v-model:value="filters.dateRange"
              type="daterange"
              style="width: 240px"
              clearable
            />
            <n-button @click="handleReset">重置</n-button>
          </n-space>
        </div>
        <n-empty description="暂无符合条件的记录" class="empty-result">
          <template #extra>
            <n-button size="small" @click="handleReset">清除筛选</n-button>
          </template>
        </n-empty>
      </n-card>

      <!-- Data -->
      <n-card v-else class="history-card">
        <div class="filter-bar">
          <n-space :size="12" wrap>
            <n-select
              v-model:value="filters.status"
              placeholder="状态筛选"
              style="width: 120px"
              clearable
              :options="statusOptions"
            />
            <n-select
              v-model:value="filters.dataType"
              placeholder="数据类型"
              style="width: 130px"
              clearable
              :options="dataTypeOptions"
            />
            <n-date-picker
              v-model:value="filters.dateRange"
              type="daterange"
              style="width: 240px"
              clearable
            />
            <n-button @click="handleReset">重置</n-button>
          </n-space>
        </div>

        <n-data-table
          :columns="columns"
          :data="records"
          :pagination="{
            page: pagination.current,
            pageSize: pagination.pageSize,
            itemCount: pagination.total,
            onChange: (page: number) => { pagination.current = page; loadHistory(); },
            onUpdatePageSize: (pageSize: number) => { pagination.pageSize = pageSize; loadHistory(); },
          }"
          :row-key="(row: SyncRecord) => row.id"
          :scroll-x="1000"
          size="small"
          remote
        />
      </n-card>

      <!-- 详情抽屉 -->
      <n-drawer
        :show="drawerVisible"
        title="同步任务详情"
        placement="right"
        :width="560"
        @update:show="(val: boolean) => { if (!val) closeDrawer(); }"
      >
        <template v-if="selectedRecord">
          <n-descriptions label-placement="left" bordered :column="1" size="small">
            <n-descriptions-item label="任务ID">{{ selectedRecord.task_id }}</n-descriptions-item>
            <n-descriptions-item label="数据类型">{{ selectedRecord.data_types.join(", ") }}</n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag :type="getStatusType(selectedRecord.status)" :bordered="false" size="small">
                {{ getStatusText(selectedRecord.status) }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="开始时间">{{ selectedRecord.start_time }}</n-descriptions-item>
            <n-descriptions-item label="结束时间">{{ selectedRecord.end_time || "-" }}</n-descriptions-item>
            <n-descriptions-item label="耗时">{{ formatDuration(selectedRecord.duration) }}</n-descriptions-item>
            <n-descriptions-item label="完成进度">
              {{ selectedRecord.completed_tasks }}/{{ selectedRecord.total_tasks }}
            </n-descriptions-item>
            <n-descriptions-item v-if="selectedRecord.data_volume" label="数据量">
              {{ (selectedRecord.data_volume / 10000).toFixed(1) }}万条
            </n-descriptions-item>
          </n-descriptions>

          <n-divider />

          <n-descriptions
            v-if="Object.keys(selectedRecord.results).length > 0"
            label-placement="left"
            bordered
            :column="1"
            size="small"
            title="子任务结果"
          >
            <n-descriptions-item v-for="(result, dataType) in selectedRecord.results" :key="dataType" :label="dataType">
              <n-tag :type="result.error ? 'error' : 'success'" :bordered="false" size="small">
                {{ result.error ? "失败" : "成功" }}
              </n-tag>
              <span v-if="result.error" class="error-text">{{ result.error }}</span>
            </n-descriptions-item>
          </n-descriptions>

          <n-empty v-else description="无子任务结果" size="small" />

          <n-alert
            v-if="selectedRecord.error"
            :title="selectedRecord.error"
            type="error"
            :show-icon="true"
            class="error-alert"
          />

          <div class="drawer-actions">
            <n-button
              v-if="selectedRecord.status === 'failed'"
              type="primary"
              @click="handleRetryTask(selectedRecord.task_id)"
            >
              <template #icon><SmartIcon name="Refresh" /></template>
              重试任务
            </n-button>
            <n-button @click="message.info('日志功能开发中')">
              <template #icon><SmartIcon name="DocumentText" /></template>
              查看日志
            </n-button>
          </div>
        </template>
      </n-drawer>
    </div>
  </div>
</template>

<style scoped lang="scss">
.sync-history-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;

  /* .action-btn 圆形成样式已迁移至全局 global.scss */
}

.history-card {
  /* margin handled by main-content padding */
}

.filter-bar {
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 6px;
  border: 1px solid var(--n-border-color);
}

.empty-result {
  margin: 40px 0;
}

.error-text {
  color: var(--color-stock-down, #00E676);
  margin-left: 8px;
  font-size: 12px;
}

.error-alert {
  margin-top: 12px;
}

.drawer-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--n-border-color);
}

// 响应式
@media (max-width: 768px) {
  .filter-bar {
    padding: 8px;
  }
}
</style>
