<!-- quant_web/src/views/DataSync/SyncHistory.vue -->
<script setup lang="ts">
import { onMounted, reactive, ref, h } from "vue";
import {
  NAlert,
  NButton,
  NCard,
  NDatePicker,
  NDescriptions,
  NDescriptionsItem,
  NDivider,
  NDrawer,
  NSelect,
  NSpace,
  NTag,
  NDataTable,
} from "naive-ui";
import { useRouter } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import type { Dayjs } from "dayjs";
import type { DataTableColumns } from "naive-ui";

const router = useRouter();

const handleBack = () => {
  router.go(-1);
};

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
  results: Record<string, any>;
  error?: string;
}

const loading = ref(false);
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
  dateRange: null as [string, string] | null,
});

const statusOptions = [
  { label: "完成", value: "completed" },
  { label: "运行中", value: "running" },
  { label: "失败", value: "failed" },
  { label: "已取消", value: "cancelled" },
];

const getStatusType = (
  status: string,
): "default" | "success" | "info" | "warning" | "error" => {
  const types: Record<
    string,
    "default" | "success" | "info" | "warning" | "error"
  > = {
    completed: "success",
    running: "info",
    failed: "error",
    cancelled: "warning",
  };
  return types[status] || "default";
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

const columns: DataTableColumns<SyncRecord> = [
  {
    title: "任务ID",
    key: "task_id",
    width: 120,
  },
  {
    title: "数据类型",
    key: "data_types",
    render: (row) => row.data_types.join(", "),
  },
  {
    title: "状态",
    key: "status",
    render: (row) =>
      h(
        NTag,
        { type: getStatusType(row.status), bordered: false, size: "small" },
        { default: () => getStatusText(row.status) },
      ),
  },
  {
    title: "开始时间",
    key: "start_time",
  },
  {
    title: "完成进度",
    key: "progress",
    render: (row) => `${row.completed_tasks}/${row.total_tasks}`,
  },
  {
    title: "操作",
    key: "actions",
    render: (row) =>
      h(
        NButton,
        { text: true, onClick: () => showDetails(row) },
        { default: () => "详情" },
      ),
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

const handleSearch = () => {
  pagination.current = 1;
  loadHistory();
};

const handleReset = () => {
  filters.status = "";
  filters.dateRange = null;
  pagination.current = 1;
  loadHistory();
};

const loadHistory = async () => {
  loading.value = true;
  try {
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
        results: {
          市场数据: { error: null },
          K线数据: { error: null },
        },
      },
    ];
    pagination.total = records.value.length;
  } catch (error) {
    console.error("加载同步历史失败:", error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadHistory();
});
</script>

<template>
  <div class="sync-history-page">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">同步历史记录</h1>
          <p class="page-description">查看和管理历史数据同步任务记录</p>
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

    <n-card class="history-card">
      <div class="filter-bar">
        <n-space :size="16" wrap>
          <n-select
            v-model:value="filters.status"
            placeholder="状态筛选"
            style="width: 120px"
            clearable
            :options="statusOptions"
          />

          <n-date-picker
            v-model:formatted-value="filters.dateRange"
            type="daterange"
            style="width: 240px"
            clearable
          />

          <n-button type="primary" @click="handleSearch">
            <template #icon>
              <SmartIcon name="Search" />
            </template>
            搜索
          </n-button>

          <n-button @click="handleReset">重置</n-button>

          <n-button @click="loadHistory" :loading="loading">
            <template #icon>
              <SmartIcon name="Reload" />
            </template>
            刷新
          </n-button>
        </n-space>
      </div>

      <n-data-table
        :columns="columns"
        :data="records"
        :pagination="{
          page: pagination.current,
          pageSize: pagination.pageSize,
          itemCount: pagination.total,
          onChange: (page: number) => {
            pagination.current = page;
            loadHistory();
          },
          onUpdatePageSize: (pageSize: number) => {
            pagination.pageSize = pageSize;
            loadHistory();
          },
        }"
        :loading="loading"
        :row-key="(row: SyncRecord) => row.id"
        :scroll-x="1000"
        remote
      />

      <n-drawer
        :show="drawerVisible"
        title="同步任务详情"
        placement="right"
        :width="600"
        @update:show="
          (val: boolean) => {
            if (!val) closeDrawer();
          }
        "
      >
        <template v-if="selectedRecord">
          <n-descriptions
            label-placement="left"
            bordered
            :column="1"
            size="small"
          >
            <n-descriptions-item label="任务ID">
              {{ selectedRecord.task_id }}
            </n-descriptions-item>
            <n-descriptions-item label="数据类型">
              {{ selectedRecord.data_types.join(", ") }}
            </n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag
                :type="getStatusType(selectedRecord.status)"
                :bordered="false"
                size="small"
              >
                {{ getStatusText(selectedRecord.status) }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="开始时间">
              {{ selectedRecord.start_time }}
            </n-descriptions-item>
            <n-descriptions-item label="结束时间">
              {{ selectedRecord.end_time || "-" }}
            </n-descriptions-item>
            <n-descriptions-item label="持续时间">
              {{
                selectedRecord.duration
                  ? `${Math.round(selectedRecord.duration / 60)}分钟`
                  : "-"
              }}
            </n-descriptions-item>
            <n-descriptions-item label="完成进度">
              {{ selectedRecord.completed_tasks }}/{{
                selectedRecord.total_tasks
              }}
            </n-descriptions-item>
          </n-descriptions>

          <n-divider />

          <n-descriptions
            label-placement="left"
            bordered
            :column="1"
            size="small"
          >
            <template
              v-for="(result, dataType) in selectedRecord.results"
              :key="dataType"
            >
              <n-descriptions-item :label="dataType">
                <n-tag
                  :type="result.error ? 'error' : 'success'"
                  :bordered="false"
                  size="small"
                >
                  {{ result.error ? "失败" : "成功" }}
                </n-tag>
                <span v-if="result.error" class="error-text">
                  {{ result.error }}
                </span>
              </n-descriptions-item>
            </template>
          </n-descriptions>

          <n-alert
            v-if="selectedRecord.error"
            :title="selectedRecord.error"
            type="error"
            :show-icon="true"
            class="error-alert"
          />
        </template>
      </n-drawer>
    </n-card>
  </div>
</template>

<style scoped lang="scss">
@use "@/styles/variables" as *;
@use "@/styles/mixins" as mixin;
@use "sass:map";

.sync-history-page {
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
}

.history-card {
  margin: 0 map.get($spacers, 4);
}

.filter-bar {
  margin-bottom: map.get($spacers, 3);
  padding: map.get($spacers, 3);
  background: $secondary-bg;
  border-radius: $border-radius;
  border: 1px solid $border-color;
}

.error-text {
  color: $error-color;
  margin-left: map.get($spacers, 2);
}

.error-alert {
  margin-top: map.get($spacers, 3);
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

  .history-card {
    margin: 0 map.get($spacers, 3);
  }

  .filter-bar {
    padding: map.get($spacers, 2);
  }
}

@include mixin.media-breakpoint-down(sm) {
  .history-card {
    margin: 0 map.get($spacers, 2);
  }
}
</style>
