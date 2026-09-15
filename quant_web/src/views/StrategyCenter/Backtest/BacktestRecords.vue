<template>
  <div class="backtest-records-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">回测记录</h1>
          <p class="page-description">共 {{ taskTotal }} 个回测任务 · 点击行查看报告</p>
        </div>
        <div class="header-actions">
          <n-input v-model:value="searchQuery" placeholder="搜索任务名" clearable style="width: 200px" />
          <n-select v-model:value="statusFilter" :options="statusOptions" style="width: 130px" @update:value="onStatusChange" />
          <n-button class="action-btn" @click="loadList" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-card :class="tokens.surface.card" size="small">
        <n-data-table
          :columns="columns"
          :data="filteredList"
          :row-key="(row: any) => row.id"
          :loading="loading"
          :bordered="false"
          size="small"
          @row-click="(row: any) => goReport(row.id)"
        />
        <div class="pagination-row">
          <n-pagination
            v-model:page="page"
            :page-size="pageSize"
            :item-count="taskTotal"
            :page-slot="7"
            size="small"
            @update:page="onPageChange"
          />
        </div>
      </n-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useRouter } from "vue-router";
import { NCard, NButton, NTag, NDataTable, NPagination, NInput, NSelect, useMessage } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import backtestAPI from "@/api/backtest";

const router = useRouter();
const msg = useMessage();

const taskList = ref<any[]>([]);
const loading = ref(false);
const searchQuery = ref("");
const statusFilter = ref("all");
const page = ref(1);
const pageSize = ref(20);
const taskTotal = ref(0);

const statusOptions = [
  { label: "全部状态", value: "all" },
  { label: "已完成", value: "completed" },
  { label: "运行中", value: "running" },
  { label: "失败", value: "failed" },
  { label: "已取消", value: "cancelled" },
  { label: "等待中", value: "pending" },
];

const statusType = (s: string) => {
  const map: Record<string, any> = { running: "info", completed: "success", failed: "error", cancelled: "warning", pending: "default" };
  return map[s] || "default";
};
const statusLabel = (s: string) => {
  const map: Record<string, string> = { running: "运行中", completed: "已完成", failed: "失败", cancelled: "已取消", pending: "等待中" };
  return map[s] || s;
};

function formatDuration(start: string, end: string): string {
  if (!start) return "--";
  const endTime = end ? new Date(end).getTime() : Date.now();
  const ms = endTime - new Date(start).getTime();
  if (ms < 0) return "--";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

const filteredList = computed(() => {
  if (!searchQuery.value) return taskList.value;
  const q = searchQuery.value.toLowerCase();
  return taskList.value.filter((t) => (t.name || t.task_id || "").toLowerCase().includes(q));
});

const columns = [
  { title: "任务名", key: "name", ellipsis: { tooltip: true }, render: (row: any) => row.name || row.task_id?.slice(0, 8) },
  { title: "回测区间", key: "period", width: 190, render: (row: any) => (row.start_date && row.end_date ? `${row.start_date} ~ ${row.end_date}` : "--") },
  { title: "金额", key: "capital", width: 90, render: (row: any) => (row.initial_capital ? `¥${(Number(row.initial_capital) / 1e4).toFixed(0)}万` : "--") },
  { title: "状态", key: "status", width: 85, render: (row: any) => h(NTag, { type: statusType(row.status), size: "small" }, { default: () => statusLabel(row.status) }) },
  { title: "执行耗时", key: "duration", width: 100, render: (row: any) => formatDuration(row.started_at, row.completed_at) },
  {
    title: "操作", key: "actions", width: 200,
    render: (row: any) => h("div", { class: "record-actions" }, [
      h(NButton, { size: "tiny", type: "primary", text: true, onClick: () => goReport(row.id) }, { default: () => "查看报告" }),
      row.status === "running" ? h(NButton, { size: "tiny", type: "warning", text: true, onClick: () => cancelTask(row.id) }, { default: () => "取消" }) : null,
      h(NButton, { size: "tiny", type: "error", text: true, onClick: () => deleteTask(row.id) }, { default: () => "删除" }),
    ]),
  },
];

async function loadList() {
  loading.value = true;
  try {
    const res = await backtestAPI.getTasksPaged({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value === "all" ? undefined : statusFilter.value,
    });
    taskList.value = res?.data || [];
    taskTotal.value = res?.pagination?.total ?? taskList.value.length;
  } finally {
    loading.value = false;
  }
}

function onStatusChange() {
  page.value = 1;
  loadList();
}
function onPageChange(p: number) {
  page.value = p;
  loadList();
}
function goReport(taskId: string) {
  router.push(`/backtest/report/${taskId}`);
}
async function deleteTask(taskId: string) {
  try {
    await backtestAPI.deleteTask(taskId);
    msg.success("已删除");
    loadList();
  } catch {
    msg.error("删除失败");
  }
}

async function cancelTask(taskId: string) {
  try {
    await backtestAPI.cancelTask(taskId);
    msg.success("已发送取消请求");
    loadList();
  } catch {
    msg.error("取消失败");
  }
}

onMounted(loadList);
</script>

<style lang="scss" scoped>
.backtest-records-page {
  height: 100%;
  overflow-y: auto;
}
.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.record-actions {
  display: flex;
  gap: 4px;
}
</style>
