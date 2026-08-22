<!--审计日志（2026-08：由 system_logs 空表改为 audit_logs 审计日志）-->
<script setup lang="ts">
import { ref, computed, h } from "vue";
import { useMessage, NTag, NButton, NResult, NEmpty, NSpin, NSpace, NInput, NSelect, NDatePicker, NDataTable, NPagination, NCard } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import systemAPI from "@/api/system";
import dayjs from "dayjs";

const message = useMessage();
const loading = ref(false);
const error = ref(false);
const filteredLogs = ref<any[]>([]);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);

const filters = ref({
  action_type: null as string | null,
  status: null as string | null,
  username: "",
  date: null as string | null, // "yyyy-MM-dd"
});

const ACTION_LABELS: Record<string, string> = {
  login: "登录", logout: "登出", create: "创建", update: "更新", delete: "删除",
  read: "查看", execute: "执行", access: "访问", authorize: "授权",
  config_change: "配置变更", security_event: "安全事件", system_event: "系统事件",
};
const actionOptions = Object.entries(ACTION_LABELS).map(([value, label]) => ({ label, value }));
const statusOptions = [
  { label: "成功", value: "success" },
  { label: "失败", value: "failed" },
  { label: "部分成功", value: "partial" },
];

const columns = [
  { title: "时间", key: "created_at", width: 165, render: (r: any) => fmtTime(r.created_at) },
  { title: "用户", key: "username", width: 100, render: (r: any) => r.username || "-" },
  {
    title: "操作", key: "action_type", width: 100,
    render: (r: any) => h(NTag, { size: "small", type: actionTagType(r.action_type), bordered: false },
      () => ACTION_LABELS[r.action_type] || r.action_type),
  },
  {
    title: "资源", key: "resource", minWidth: 130, ellipsis: { tooltip: true },
    render: (r: any) => `${r.resource_type || "-"}${r.resource_id ? " / " + r.resource_id : ""}`,
  },
  {
    title: "状态", key: "status", width: 80,
    render: (r: any) => h(NTag, {
      size: "small", bordered: false,
      type: r.status === "success" ? "success" : r.status === "failed" ? "error" : "warning",
    }, { default: () => (r.status === "success" ? "成功" : r.status === "failed" ? "失败" : "部分成功") }),
  },
  { title: "IP", key: "ip_address", width: 120, render: (r: any) => r.ip_address || "-" },
  {
    title: "详情", key: "detail", minWidth: 200, ellipsis: { tooltip: true },
    render: (r: any) => {
      if (r.error_message) return r.error_message;
      if (r.changed_fields?.length) return `变更字段: ${r.changed_fields.join(", ")}`;
      if (r.resource_name) return r.resource_name;
      return "-";
    },
  },
];

function actionTagType(a: string): "success" | "error" | "warning" | "info" | "default" {
  if (a === "login" || a === "create") return "success";
  if (a === "delete" || a === "security_event") return "error";
  if (a === "update" || a === "config_change") return "warning";
  return "info";
}

function fmtTime(ts?: string): string {
  if (!ts) return "--";
  return ts.replace("T", " ").slice(0, 19);
}

async function searchLogs() {
  loading.value = true;
  error.value = false;
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    };
    if (filters.value.action_type) params.action_type = filters.value.action_type;
    if (filters.value.status) params.status = filters.value.status;
    if (filters.value.username.trim()) params.username = filters.value.username.trim();
    if (filters.value.date) {
      params.start_date = dayjs(filters.value.date).format("YYYY-MM-DDT00:00:00");
      params.end_date = dayjs(filters.value.date).add(1, "day").format("YYYY-MM-DDT00:00:00");
    }

    const res = await systemAPI.getSystemLogs(params);
    // 兼容两种响应格式：{ data, pagination } 或 { logs, total }
    filteredLogs.value = (res as any).data || (res as any).logs || [];
    total.value = (res as any).pagination?.total || (res as any).total || filteredLogs.value.length;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

const handleSearch = () => { currentPage.value = 1; searchLogs(); };

function exportCSV() {
  const data = filteredLogs.value;
  if (!data.length) return;
  const header = "时间,用户,操作,资源,状态,IP,详情\n";
  const rows = data
    .map((l) => {
      const esc = (s: any) => `"${String(s ?? "").replace(/"/g, '""')}"`;
      const action = ACTION_LABELS[l.action_type] || l.action_type || "";
      const resource = `${l.resource_type || ""}${l.resource_id ? "/" + l.resource_id : ""}`;
      const detail = l.error_message || (l.changed_fields ? l.changed_fields.join(",") : l.resource_name) || "";
      return `${fmtTime(l.created_at)},${esc(l.username)},${esc(action)},${esc(resource)},${esc(l.status)},${esc(l.ip_address)},${esc(detail)}`;
    })
    .join("\n");
  const blob = new Blob(["\ufeff" + header + rows], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `audit_logs_${dayjs().format("YYYY-MM-DD")}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

searchLogs();
</script>

<template>
  <div class="log-viewer bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">审计日志</h1>
          <p class="page-description">记录用户操作与安全事件 — 谁在何时对什么资源做了什么、改了什么</p>
        </div>
        <div class="header-actions">
          <n-space :size="8" wrap>
            <n-select v-model:value="filters.action_type" :options="actionOptions" placeholder="操作类型" size="small" clearable style="width: 130px" />
            <n-select v-model:value="filters.status" :options="statusOptions" placeholder="状态" size="small" clearable style="width: 100px" />
            <n-input v-model:value="filters.username" placeholder="用户名" size="small" clearable style="width: 130px" @keyup.enter="handleSearch" />
            <n-date-picker v-model:formatted-value="filters.date" type="date" placeholder="日期" size="small" clearable style="width: 135px" />
            <n-button type="primary" size="small" @click="handleSearch">查询</n-button>
            <n-button size="small" @click="exportCSV">导出CSV</n-button>
          </n-space>
        </div>
      </div>
    </div>
    <div class="main-content">
      <n-card :class="tokens.surface.card">
        <n-spin :show="loading">
          <n-result v-if="error" status="500" title="加载失败" description="请检查网络连接后重试">
            <template #footer><n-button type="primary" @click="searchLogs">重试</n-button></template>
          </n-result>
          <template v-else>
            <n-empty v-if="filteredLogs.length === 0 && !loading" description="暂无审计日志" style="padding: 60px 0">
              <template #extra>
                <span style="font-size:13px;color:var(--n-text-color-3)">用户登录、账户变更、配置修改等操作将在此显示</span>
              </template>
            </n-empty>
            <n-data-table v-else :columns="columns" :data="filteredLogs" size="small" :bordered="false" :row-key="(r: any) => r.id" />
            <div class="log-pagination" v-if="total > pageSize">
              <n-pagination v-model:page="currentPage" :page-size="pageSize" :item-count="total" size="small" @update:page="searchLogs" />
            </div>
          </template>
        </n-spin>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.log-viewer {
  padding: 0;
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}
.page-description {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
}
.log-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
