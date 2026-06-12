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
  NDrawer,
  NEmpty,
  NResult,
  NSelect,
  NSkeleton,
  NSpace,
  NTag,
  NDataTable,
  useMessage,
  useDialog,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { dataSyncService } from "@/api/data-sync";
import type { DataTableColumns } from "naive-ui";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();

interface SyncRecord {
  id: string;
  db_id: string;
  data_type: string;
  data_types?: string[];
  data_desc: string;
  status: string;
  start_time: string;
  end_time?: string;
  duration?: number;
  records_processed: number;
  records_added: number;
  total_records: number;
  records_failed: number;
  children?: SyncRecord[];
  parameters?: Record<string, any>;
  error?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
}

type PageState = "loading" | "error" | "empty" | "data";

const pageState = ref<PageState>("loading");
const allRecords = ref<SyncRecord[]>([]);
const totalCount = ref(0);
const selectedRecord = ref<SyncRecord | null>(null);
const drawerVisible = ref(false);
const checkedRowKeys = ref<string[]>([]);

const pagination = reactive({
  current: 1,
  pageSize: 20,
});

const filters = reactive({
  status: "" as string,
  group: "" as string,
  dataType: "" as string,
  dateRange: null as [number, number] | null,
});

const statusOptions = [
  { label: "全部状态", value: "" },
  { label: "运行中", value: "running" },
  { label: "完成", value: "completed" },
  { label: "失败", value: "failed" },
  { label: "已取消", value: "cancelled" },
];

const groupOptions = [
  { label: "全部", value: "" },
  { label: "1-每日行情", value: "1" },
  { label: "2-财务数据", value: "2" },
  { label: "3-公司治理", value: "3" },
  { label: "4-因子数据", value: "4" },
  { label: "5-事件驱动", value: "5" },
  { label: "6-宏观数据", value: "6" },
  { label: "7-基础数据", value: "7" },
];

const dataTypeOptions = computed(() => {
  const types = [...new Set(allRecords.value.map((r) => r.data_type))];
  return [{ label: "全部类型", value: "" }, ...types.map((t) => ({ label: TYPE_NAME_MAP[t] || t, value: t }))];
});

// 跟踪各下拉框/弹出层的打开状态，避免下拉框关闭时 click 事件
// 穿透到表格行导致意外跳转详情页
const popupOpen = reactive({
  status: false,
  group: false,
  dataType: false,
  datePicker: false,
});

// 任意弹出层打开时，忽略表格行点击
const isAnyPopupOpen = computed(() =>
  popupOpen.status || popupOpen.group || popupOpen.dataType || popupOpen.datePicker
);

onMounted(() => {
  loadHistory();
});

// Server-side: API handles filtering + pagination
const paginationTotal = computed(() => totalCount.value);

const handleBack = () => {
  router.push({ name: "DataSync" });
};

const handleDeleteRecord = (row: SyncRecord) => {
  const doDelete = async (force?: boolean) => {
    try {
      await dataSyncService.deleteSyncTask(row.id, force);
      message.success("记录已删除");
      allRecords.value = allRecords.value.filter((r) => r.id !== row.id);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || "";
      if (msg.includes("运行中") || msg.includes("running")) {
        dialog.warning({
          title: "任务可能已中断",
          content: "该任务状态为运行中（可能是服务器停机导致未更新）。确定要强制删除吗？",
          positiveText: "强制删除",
          negativeText: "取消",
          onPositiveClick: () => doDelete(true),
        });
      } else {
        message.error("删除失败，请重试");
      }
    }
  };
  dialog.error({
    title: "确认删除",
    content: `确定要删除「${row.data_desc || row.data_type}」的同步记录吗？此操作不可恢复。`,
    positiveText: "确认删除",
    negativeText: "取消",
    onPositiveClick: () => doDelete(),
  });
};

const handleBatchDelete = () => {
  dialog.error({
    title: "批量删除",
    content: `确定要删除选中的 ${checkedRowKeys.value.length} 条记录吗？此操作不可恢复。`,
    positiveText: "确认删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        const result = await dataSyncService.batchDeleteSyncTasks([...checkedRowKeys.value]);
        const deleted = result.deleted.length;
        const failed = result.failed.length;
        if (deleted > 0) {
          message.success(`已删除 ${deleted} 条记录${failed > 0 ? `，${failed} 条失败` : ""}`);
          allRecords.value = allRecords.value.filter(r => !result.deleted.includes(r.id));
        } else {
          message.warning(`${failed} 条记录删除失败`);
        }
        checkedRowKeys.value = [];
      } catch {
        message.error("批量删除失败，请重试");
      }
    },
  });
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
  if (seconds == null || seconds <= 0) return "-";
  if (seconds < 60) return `${seconds}秒`;
  return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`;
};

const columns: DataTableColumns<SyncRecord> = [
  { type: "selection" as const },
  {
    title: "数据类型", key: "data_type", width: 160,
    render: (row) => h("span", {}, row.data_desc || row.task_label || row.data_type),
  },
  {
    title: "说明", key: "data_desc", width: 120,
    render: (row) => h("span", {}, row.data_desc),
  },
  {
    title: "状态", key: "status", width: 80,
    render: (row) =>
      h(NTag, { type: getStatusType(row.status), bordered: false, size: "small" }, { default: () => getStatusText(row.status) }),
  },
  {
    title: "已处理", key: "records_processed", width: 70,
    render: (row) => row.records_processed.toLocaleString(),
  },
  {
    title: "成功", key: "records_added", width: 70,
    render: (row) => row.records_added.toLocaleString(),
  },
  {
    title: "总计", key: "total_records", width: 70,
    render: (row) => row.total_records.toLocaleString(),
  },
  {
    title: "失败", key: "records_failed", width: 70,
    render: (row) => (row.records_failed > 0 ? h("span", { style: { color: "var(--color-error, #E53935)" } }, row.records_failed.toLocaleString()) : "0"),
  },
  {
    title: "开始时间", key: "start_time", width: 150,
    render: (row) => row.start_time ? new Date(row.start_time).toLocaleString("zh-CN") : "-",
  },
  {
    title: "结束时间", key: "end_time", width: 150,
    render: (row) => row.end_time ? new Date(row.end_time).toLocaleString("zh-CN") : "-",
  },
  {
    title: "耗时", key: "duration", width: 80,
    render: (row) => formatDuration(row.duration),
  },
  {
    title: "操作", key: "actions", width: 120, fixed: "right",
    render: (row) =>
      h(NSpace, { size: "small" as any }, {
        default: () => [
          h(NButton, { text: true, size: "small", onClick: () => showDetails(row) }, { default: () => "详情" }),
          h(NButton, { text: true, size: "small", type: "error", onClick: () => handleDeleteRecord(row) }, { default: () => "删除" }),
        ],
      }),
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
  filters.group = "";
  filters.dataType = "";
  filters.dateRange = null;
  pagination.current = 1;
  checkedRowKeys.value = [];
};

const TYPE_NAME_MAP: Record<string, string> = {
  // 股票基础
  stock_list: "股票列表", st_list: "ST 列表", company: "公司信息",
  calendar: "交易日历",
  // 股票行情
  daily_quotes: "日线行情", weekly_quotes: "周线行情", monthly_quotes: "月线行情",
  minute_quotes: "分钟行情", tick_quotes: "Tick 行情",
  moneyflow: "资金流向", adj_factor: "复权因子", daily_basic: "每日指标",
  suspend: "停复牌信息",
  // ETF
  etf_basic: "ETF 基础信息", etf_daily: "ETF 日线行情",
  etf_minute: "ETF 分钟行情", fund_adj_factor: "基金复权因子",
  etf_index: "ETF 基准指数", etf_share: "ETF 份额规模",
  // 指数
  index_basic: "指数基本信息", index_daily: "指数日线行情",
  index_data: "指数数据(旧)",
  // 财务报表
  financial_data: "财务报表(三表)", financial_income: "利润表",
  financial_balance: "资产负债表", financial_cashflow: "现金流量表",
  // 财务衍生
  forecast: "业绩预告", express: "业绩快报", dividend: "分红送股",
  financial_indicator: "财务指标", audit_opinion: "审计意见",
  business_income: "主营业务构成",
  // 公司治理
  managers: "管理层信息", rewards: "薪酬持股",
  // 宏观经济
  cpi: "CPI居民消费价格", ppi: "PPI工业出厂价格", gdp: "GDP国内生产总值",
  // 指数扩展
  index_weight: "指数成分权重", index_weekly: "指数周线行情",
  // Phase 1 新增
  stock_hsgt: "沪深港通列表", st_stockrisk: "ST风险警示板",
  disclosure_date: "财报披露日期", share_float: "限售股解禁",
  // Phase 2 新增
  stk_holdernumber: "股东人数", top10_holders: "前十大股东",
  top10_floatholders: "前十大流通股东", pledge_stat: "股权质押统计",
  stk_holdertrade: "股东增减持",
  // Phase 3 新增
  index_sw_classify: "申万行业分类", index_sw_member: "申万行业成分",
  index_sw_daily: "申万行业日线", index_dailybasic: "大盘指数指标",
  forecast_pro: "券商盈利预测", moneyflow_hsgt: "沪深港通资金流",
  // Phase 4 新增
  daily_limit: "涨跌停价格", stk_factor: "技术因子(基础)",
  stk_factor_pro: "技术因子(专业)", idx_factor_pro: "指数技术因子(专业)",
  // 其他补充
  suspend_info: "停复牌信息",
  // 批量
  batch_sync: "批量同步",
};

const formatDataTypeName = (codes: string[]): string =>
  codes.map(c => TYPE_NAME_MAP[c] || c).join(" · ");

const loadHistory = async () => {
  pageState.value = "loading";
  try {
    const offset = (pagination.current - 1) * pagination.pageSize;
    const result = await dataSyncService.getSyncTasks({
      limit: pagination.pageSize, offset,
      status: filters.status || undefined,
      group: filters.group || undefined,
    });
    const tasks = result.tasks || [];
    const mapTask = (t: any): SyncRecord => {
      const startTime = t.start_time ? new Date(t.start_time) : null;
      const endTime = t.end_time ? new Date(t.end_time) : null;
      const duration = startTime && endTime
        ? Math.round((endTime.getTime() - startTime.getTime()) / 1000)
        : undefined;
      const types = t.data_types && t.data_types.length > 0 ? t.data_types : [t.task_type];
      return {
        id: t.task_id,
        db_id: t.id,
        data_type: types.join(" · "),
        data_desc: formatDataTypeName(types),
        data_types: t.data_types,
        status: t.status,
        start_time: t.start_time || "",
        end_time: t.end_time,
        duration,
        records_processed: t.records_processed || 0,
        records_added: t.records_succeeded || 0,
        total_records: t.total_records || 0,
        records_failed: t.records_failed || 0,
        parameters: t.parameters,
        error: t.error_message,
        created_at: t.created_at,
        updated_at: t.updated_at,
        completed_at: t.completed_at,
        children: t.children ? t.children.map(mapTask) : undefined,
      };
    };
    allRecords.value = tasks.map(mapTask);
    totalCount.value = result.total || 0;
    pageState.value = allRecords.value.length === 0 ? "empty" : "data";
  } catch {
    pageState.value = "error";
  }
};

// Reset pagination when filters change
watch(
  () => [filters.status, filters.group, filters.dataType, filters.dateRange],
  () => {
    pagination.current = 1;
  },
);

// Reload from server when group filter changes (server-side filter)
watch(
  () => filters.group,
  () => {
    loadHistory();
  },
);

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

      <!-- Data + Empty (shared filter-bar) -->
      <n-card v-else class="history-card">
        <div class="filter-bar">
          <n-space :size="12" wrap>
            <n-select
              v-model:value="filters.status"
              placeholder="状态筛选"
              style="width: 120px"
              clearable
              :options="statusOptions"
              @update:show="(val: boolean) => popupOpen.status = val"
            />
            <n-select
              v-model:value="filters.group"
              placeholder="分组筛选"
              style="width: 140px"
              clearable
              :options="groupOptions"
              @update:show="(val: boolean) => popupOpen.group = val"
            />
            <n-select
              v-model:value="filters.dataType"
              placeholder="数据类型"
              style="width: 130px"
              clearable
              :options="dataTypeOptions"
              @update:show="(val: boolean) => popupOpen.dataType = val"
            />
            <n-date-picker
              v-model:value="filters.dateRange"
              type="daterange"
              style="width: 240px"
              clearable
              @update:show="(val: boolean) => popupOpen.datePicker = val"
            />
            <n-button @click="handleReset">重置</n-button>
            <n-button
              v-if="checkedRowKeys.length > 0"
              type="error"
              size="small"
              @click="handleBatchDelete"
            >
              删除选中 ({{ checkedRowKeys.length }})
            </n-button>
          </n-space>
        </div>

        <n-empty
          v-if="pageState === 'empty'"
          description="暂无符合条件的记录"
          class="empty-result"
        >
          <template #extra>
            <n-button size="small" @click="handleReset">清除筛选</n-button>
          </template>
        </n-empty>

        <n-data-table
          v-else
          :columns="columns"
          :data="allRecords"
          v-model:checked-row-keys="checkedRowKeys"
          :row-props="(row: SyncRecord) => ({
            class: 'clickable-row',
            onClick: (e: MouseEvent) => {
              const t = e.target as HTMLElement
              // 忽略展开按钮、操作按钮、标签等交互元素上的点击
              if (t.closest('button') || t.closest('.n-data-table-expand-trigger') || t.closest('.n-tag')) return
              if (isAnyPopupOpen.value) return
              showDetails(row)
            }
          })"
          :pagination="{
            page: pagination.current,
            pageSize: pagination.pageSize,
            itemCount: paginationTotal,
            onChange: (page: number) => { pagination.current = page; loadHistory(); },
            onUpdatePageSize: (pageSize: number) => { pagination.pageSize = pageSize; pagination.current = 1; loadHistory(); },
          }"
          :row-key="(row: SyncRecord) => row.id"
          :scroll-x="1050"
          size="small"
        />
      </n-card>

      <!-- 详情抽屉 -->
      <n-drawer
        :show="drawerVisible"
        title="同步任务详情"
        placement="right"
        :width="600"
        @update:show="(val: boolean) => { if (!val) closeDrawer(); }"
      >
        <template v-if="selectedRecord">
          <n-descriptions label-placement="left" bordered :column="2" size="small">
            <n-descriptions-item label="记录ID" :span="2">{{ selectedRecord.db_id }}</n-descriptions-item>
            <n-descriptions-item label="任务ID" :span="2">{{ selectedRecord.id }}</n-descriptions-item>
            <n-descriptions-item label="任务类型">{{ selectedRecord.data_desc || selectedRecord.task_label || selectedRecord.data_type }}</n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag :type="getStatusType(selectedRecord.status)" :bordered="false" size="small">
                {{ getStatusText(selectedRecord.status) }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item v-if="selectedRecord.data_types?.length" label="数据类型" :span="2">
              <n-tag v-for="dt in selectedRecord.data_types" :key="dt" size="small" style="margin-right: 4px">{{ TYPE_NAME_MAP[dt] || dt }}</n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="创建时间">{{ selectedRecord.created_at ? new Date(selectedRecord.created_at).toLocaleString("zh-CN") : "-" }}</n-descriptions-item>
            <n-descriptions-item label="更新时间">{{ selectedRecord.updated_at ? new Date(selectedRecord.updated_at).toLocaleString("zh-CN") : "-" }}</n-descriptions-item>
            <n-descriptions-item label="开始时间">{{ selectedRecord.start_time ? new Date(selectedRecord.start_time).toLocaleString("zh-CN") : "-" }}</n-descriptions-item>
            <n-descriptions-item label="结束时间">{{ selectedRecord.end_time ? new Date(selectedRecord.end_time).toLocaleString("zh-CN") : "-" }}</n-descriptions-item>
            <n-descriptions-item label="完成时间">{{ selectedRecord.completed_at ? new Date(selectedRecord.completed_at).toLocaleString("zh-CN") : "-" }}</n-descriptions-item>
            <n-descriptions-item label="耗时">{{ formatDuration(selectedRecord.duration) }}</n-descriptions-item>
            <n-descriptions-item label="已处理">{{ selectedRecord.records_processed.toLocaleString() }} 条</n-descriptions-item>
            <n-descriptions-item label="成功">{{ selectedRecord.records_added.toLocaleString() }} 条</n-descriptions-item>
            <n-descriptions-item label="失败">{{ selectedRecord.records_failed.toLocaleString() }} 条</n-descriptions-item>
            <n-descriptions-item label="总计">{{ selectedRecord.total_records.toLocaleString() }} 条</n-descriptions-item>
          </n-descriptions>

          <n-descriptions
            v-if="selectedRecord.parameters && Object.keys(selectedRecord.parameters).length > 0"
            label-placement="left"
            bordered
            :column="1"
            size="small"
            title="任务参数"
            class="params-section"
          >
            <n-descriptions-item v-for="(val, key) in selectedRecord.parameters" :key="key" :label="key">
              {{ typeof val === 'object' ? JSON.stringify(val) : val }}
            </n-descriptions-item>
          </n-descriptions>

          <n-alert
            v-if="selectedRecord.error"
            :title="selectedRecord.error"
            type="error"
            :show-icon="true"
            class="error-alert"
          />

          <div class="drawer-actions">
            <n-button @click="closeDrawer">
              关闭
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
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
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

.error-alert {
  margin-top: 12px;
}

.params-section {
  margin-top: 12px;
}

.drawer-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--n-border-color);
}

.clickable-row { cursor: pointer; transition: background 0.15s; &:hover { background: var(--n-action-color); } }

@media (max-width: 768px) {
  .filter-bar {
    padding: 8px;
  }
}
</style>
