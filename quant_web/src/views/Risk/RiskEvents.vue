<script setup lang="ts">
import { ref, computed, onMounted, h, watch } from "vue";
import { useStore } from "vuex";
import { NTag, NButton, NSpin, NResult, useMessage } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { usePagedList } from "@/composables/usePagedList";

const store = useStore();
const message = useMessage();

const loading = ref(false);
const error = ref(false);
const searchKeyword = ref("");
const filterLevel = ref("");
const detailEvent = ref<any>(null);
const showDetail = ref(false);

const levelOptions = [
  { label: "严重", value: "critical" },
  { label: "警告", value: "error" },
  { label: "信息", value: "info" },
];

const events = computed(() => store.state.risk.riskEvents.events);

const filteredEvents = computed(() => {
  let result = events.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter(
      (e: any) =>
        (e.message || "").toLowerCase().includes(kw) ||
        (e.ruleId || "").toLowerCase().includes(kw) ||
        (e.type || "").toLowerCase().includes(kw),
    );
  }
  if (filterLevel.value) {
    result = result.filter((e: any) => e.level === filterLevel.value);
  }
  return result;
});

// 客户端分页：表格展示切片后的当前页
const {
  page: currentPage,
  pageSize,
  itemCount: eventTotal,
  pagedData: pagedEvents,
} = usePagedList(filteredEvents, 20);

// 搜索/级别筛选变化时回到第一页
watch([searchKeyword, filterLevel], () => {
  currentPage.value = 1;
});

const todayCount = computed(
  () =>
    events.value.filter((e: any) => {
      const today = new Date().toISOString().split("T")[0];
      return (e.timestamp || "").startsWith(today);
    }).length,
);

const columns = [
  {
    title: "发生时间",
    key: "timestamp",
    minWidth: 160,
    ellipsis: { tooltip: true },
  },
  {
    title: "触发规则",
    key: "ruleId",
    minWidth: 130,
    ellipsis: { tooltip: true },
  },
  {
    title: "事件类型",
    key: "type",
    minWidth: 100,
    ellipsis: { tooltip: true },
    render: (row: any) =>
      h(
        NTag,
        { type: row.level === "critical" ? "error" : row.level === "error" ? "warning" : "info", size: "small" },
        { default: () => row.type || "未知" },
      ),
  },
  {
    title: "级别",
    key: "level",
    width: 70,
    render: (row: any) =>
      h(
        NTag,
        {
          type: row.level === "critical" ? "error" : row.level === "error" ? "warning" : "info",
          size: "small",
        },
        {
          default: () =>
            row.level === "critical"
              ? "严重"
              : row.level === "error"
                ? "警告"
                : "信息",
        },
      ),
  },
  {
    title: "事件描述",
    key: "message",
    ellipsis: { tooltip: true },
  },
  {
    title: "操作",
    key: "op",
    width: 70,
    render: (row: any) =>
      h(
        NButton,
        { size: "small", onClick: () => viewDetail(row) },
        { default: () => "详情" },
      ),
  },
];

const fetchEvents = async () => {
  loading.value = true;
  error.value = false;
  try {
    await store.dispatch("risk/fetchRiskEvents", {
      page: 1,
      page_size: 100,
    });
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const viewDetail = (event: any) => {
  detailEvent.value = event;
  showDetail.value = true;
};

onMounted(() => fetchEvents());
</script>

<template>
  <div class="risk-events bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">风险事件记录</h1>
          <p class="page-subtitle">
            记录风控引擎在信号检查和定时巡检中触发的所有风险事件。
          </p>
        </div>
        <div class="header-actions">
          <span class="stat-badge">今日事件: {{ todayCount }}</span>
          <span class="stat-badge">总事件数: {{ events.length }}</span>
          <n-button class="action-btn" @click="fetchEvents" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查风控引擎是否正常启动后重试"
      >
        <template #footer>
          <n-button type="primary" @click="fetchEvents">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>风险事件列表</span>
              <div class="header-controls">
                <n-input
                  v-model:value="searchKeyword"
                  placeholder="搜索规则/类型/描述..."
                  size="small"
                  clearable
                  style="width: 200px"
                />
                <n-select
                  v-model:value="filterLevel"
                  placeholder="事件级别"
                  size="small"
                  clearable
                  style="width: 100px"
                  :options="levelOptions"
                />
              </div>
            </div>
          </template>

          <n-spin :show="loading">
            <n-data-table
              :columns="columns"
              :data="pagedEvents"
              :bordered="false"
              size="small"
            >
              <template #empty>
                <n-empty description="暂无风险事件。风控引擎运行正常时，事件将在触发后显示于此" />
              </template>
            </n-data-table>

            <div class="pagination-container">
              <n-pagination
                v-model:page="currentPage"
                v-model:page-size="pageSize"
                :item-count="eventTotal"
                :page-sizes="[10, 20, 50]"
                show-size-picker
              />
            </div>
          </n-spin>
        </n-card>
      </template>
    </div>

    <n-modal
      v-model:show="showDetail"
      preset="card"
      title="事件详情"
      style="width: 600px"
    >
      <n-descriptions v-if="detailEvent" :column="2" bordered size="small">
        <n-descriptions-item label="发生时间">{{
          detailEvent.timestamp
        }}</n-descriptions-item>
        <n-descriptions-item label="触发规则">{{
          detailEvent.ruleId || "-"
        }}</n-descriptions-item>
        <n-descriptions-item label="关联策略">{{
          detailEvent.strategyId || "系统级"
        }}</n-descriptions-item>
        <n-descriptions-item label="事件类型">{{
          detailEvent.type
        }}</n-descriptions-item>
        <n-descriptions-item label="事件级别">
          <n-tag
            :type="
              detailEvent.level === 'critical'
                ? 'error'
                : detailEvent.level === 'error'
                  ? 'warning'
                  : 'info'
            "
            size="small"
          >
            {{
              detailEvent.level === "critical"
                ? "严重"
                : detailEvent.level === "error"
                  ? "警告"
                  : "信息"
            }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="触发值">
          <code>{{ JSON.stringify(detailEvent.triggerValue) }}</code>
        </n-descriptions-item>
        <n-descriptions-item label="事件描述" :span="2">{{
          detailEvent.message
        }}</n-descriptions-item>
      </n-descriptions>
    </n-modal>
  </div>
</template>

<style scoped>
.risk-events {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--n-text-color-3, rgba(255, 255, 255, 0.48));
}

.stat-badge {
  color: var(--n-text-color-2, rgba(255, 255, 255, 0.64));
  font-size: 13px;
  padding: 4px 12px;
  background: var(--color-bg-secondary, rgba(255, 255, 255, 0.04));
  border-radius: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

code {
  font-size: 12px;
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  word-break: break-all;
}
</style>
