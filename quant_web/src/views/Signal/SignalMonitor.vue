<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useRouter } from "vue-router";
import {
  NTag, NButton, NProgress, NSpin, NResult, NEmpty,
  NSelect, NDatePicker, NInput, NSpace, NStatistic, NCard,
  NDataTable, useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import tradeAPI from "@/api/trade";
import SmartIcon from "@/components/common/SmartIcon.vue";
import TradeRecordModal from "@/components/trade/TradeRecordModal.vue";
import SignalTraceModal from "@/components/trade/SignalTraceModal.vue";

const message = useMessage();
const router = useRouter();

// ============================================================
// State
// ============================================================
const loading = ref(false);
const error = ref(false);
const signals = ref<any[]>([]);

const filters = ref({
  status: null as string | null,
  signal_type: null as string | null,
  dateRange: null as [number, number] | null,
  ts_code: "",
});

const pagination = ref({ page: 1, page_size: 20, total: 0 });
const reviewing = ref<Set<string>>(new Set());

// ============================================================
// Stats
// ============================================================
// 后端 signal_status → 前端展示/过滤状态归一化（后端字段为 signal_status）
const signalStatus = (x: any): string => {
  const raw = x?.signal_status ?? x?.status ?? "pending";
  if (raw === "pending" || raw === "pending_manual") return "pending";
  if (raw === "confirmed") return "approved";
  return raw; // approved / rejected / executed / failed / error
};

const stats = computed(() => {
  const s = signals.value;
  return {
    pending: s.filter((x) => signalStatus(x) === "pending").length,
    approved: s.filter((x) => signalStatus(x) === "approved").length,
    executed: s.filter((x) => signalStatus(x) === "executed").length,
    rejected: s.filter((x) => signalStatus(x) === "rejected").length,
    total: s.length,
  };
});

// ============================================================
// Data loader
// ============================================================
const loadSignals = async () => {
  loading.value = true;
  error.value = false;
  try {
    const params: any = {
      page: pagination.value.page,
      page_size: pagination.value.page_size,
    };
    if (filters.value.status) params.status = filters.value.status;
    if (filters.value.signal_type) params.signal_type = filters.value.signal_type;
    if (filters.value.ts_code) params.ts_code = filters.value.ts_code;
    if (filters.value.dateRange) {
      params.start_date = (filters.value.dateRange as any)[0];
      params.end_date = (filters.value.dateRange as any)[1];
    }

    const res = await tradeAPI.getSignals(params);
    const data = (res as any)?.data ?? (Array.isArray(res) ? res : []);
    signals.value = Array.isArray(data) ? data : [];
    pagination.value.total = (res as any)?.pagination?.total ?? signals.value.length;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  pagination.value.page = 1;
  loadSignals();
};

const handleReset = () => {
  filters.value = { status: null, signal_type: null, dateRange: null, ts_code: "" };
  pagination.value.page = 1;
  loadSignals();
};

const handlePageChange = (page: number) => {
  pagination.value.page = page;
  loadSignals();
};

// ============================================================
// Actions
// ============================================================
// v3.4: 信号链路追溯
const showTrace = ref(false);
const traceSignalId = ref("");
const openTrace = (row: any) => {
  traceSignalId.value = row.signal_id || row.id;
  showTrace.value = true;
};

const handleReview = async (signalId: string, action: string) => {
  const found = signals.value.find((s) => (s.signal_id || s.id) === signalId);
  const prevStatus = found?.signal_status;
  if (found) found.signal_status = action;

  reviewing.value.add(signalId);
  try {
    await tradeAPI.reviewSignal(signalId, action);
    message.success(action === "approved" ? "已采纳" : "已拒绝");
  } catch (e: any) {
    if (found) found.signal_status = prevStatus;
    message.error(e?.response?.data?.detail || "操作失败");
  } finally {
    reviewing.value.delete(signalId);
  }
};

// ============================================================
// 录入成交（复用 TradeRecordModal，与驾驶舱一致）
// ============================================================
const showRecordModal = ref(false);
const recordPrefill = ref<any>(null);

const openFill = (row: any) => {
  recordPrefill.value = {
    signal_id: row.signal_id || row.id,
    strategy_id: row.strategy_id,
    ts_code: row.ts_code,
    direction: (row.signal_type || row.direction || "").toLowerCase() === "sell" ? "sell" : "buy",
    price: row.price,
    quantity: row.quantity,
  };
  showRecordModal.value = true;
};

const handleRecordSubmitted = () => {
  showRecordModal.value = false;
  loadSignals();
};

// ============================================================
// Filter options
// ============================================================
const statusOpts = [
  { label: "全部状态", value: null },
  { label: "待确认", value: "pending_confirm" },
  { label: "待审核", value: "pending" },
  { label: "已转正", value: "promoted" },
  { label: "已采纳", value: "approved" },
  { label: "已执行", value: "executed" },
  { label: "已拒绝", value: "rejected" },
  { label: "已过期", value: "expired" },
];
const typeOpts = [
  { label: "全部类型", value: null },
  { label: "买入", value: "buy" },
  { label: "卖出", value: "sell" },
];

// ============================================================
// Table columns
// ============================================================
const statusTag = (status: string) => {
  const map: Record<string, { text: string; type: "info" | "warning" | "success" | "default" | "error" }> = {
    pending: { text: "待审核", type: "warning" },
    pending_confirm: { text: "待确认", type: "warning" },
    pending_manual: { text: "待审核", type: "warning" },
    approved: { text: "已采纳", type: "success" },
    promoted: { text: "已转正", type: "success" },
    executed: { text: "已执行", type: "info" },
    rejected: { text: "已拒绝", type: "default" },
    expired: { text: "已过期", type: "default" },
    cancelled: { text: "已取消", type: "default" },
  };
  return map[status] || { text: status, type: "default" as const };
};

const directionTag = (d: string | undefined) => {
  const dir = (d || "").toLowerCase();
  if (dir === "long" || dir === "buy") return { text: "买入", type: "error" as const };
  if (dir === "short" || dir === "sell") return { text: "卖出", type: "info" as const };
  return { text: d || "--", type: "default" as const };
};

const signalTypeLabel: Record<string, string> = {
  entry: "入场", exit: "出场", stop_loss: "止损", take_profit: "止盈",
  buy: "买入", sell: "卖出", hold: "持有",
};

const columns: DataTableColumns<any> = [
  {
    title: "时间", key: "signal_time", minWidth: 140,
    render: (row) => (row.signal_time || "").toString().slice(0, 16).replace("T", " ") || "--",
  },
  {
    title: "股票", key: "ts_code", minWidth: 100,
    render: (row) => h("a", {
      style: { color: "var(--n-color-primary)", cursor: "pointer", fontWeight: 600 },
      onClick: () => router.push(`/market/stock/${row.ts_code}`),
    }, row.ts_code || "--"),
  },
  { title: "名称", key: "name", minWidth: 110, render: (row) => row.name || "--" },
  {
    title: "方向", key: "direction", minWidth: 65,
    render: (row) => {
      const d = directionTag(row.direction);
      return h(NTag, { type: d.type, size: "small", bordered: false }, { default: () => d.text });
    },
  },
  {
    title: "信号类型", key: "signal_type", minWidth: 72,
    render: (row) => {
      const label = signalTypeLabel[row.signal_type] || row.signal_type || "--";
      const sType = (row.signal_type || "").toLowerCase();
      const type = sType === "entry" || sType === "buy" ? "success"
        : sType === "exit" || sType === "sell" ? "error"
        : sType === "stop_loss" ? "warning" : "info";
      return h(NTag, { type, size: "small", bordered: false }, { default: () => label });
    },
  },
  {
    title: "参考价", key: "price", minWidth: 80,
    render: (row) => row.price != null ? `¥${Number(row.price).toFixed(2)}` : "--",
  },
  {
    title: "价格区间", key: "price_range", minWidth: 120,
    render: (row) => {
      const lo = parseFloat(row.price_limit_low), hi = parseFloat(row.price_limit_high);
      return lo && hi ? `${lo} ~ ${hi}` : (row.price ? `${row.price} ±2%` : "--");
    },
  },
  {
    title: "数量", key: "quantity", minWidth: 70,
    render: (row) => row.quantity ? `${row.quantity}股` : "--",
  },
  {
    title: "置信度", key: "confidence", minWidth: 70,
    render: (row) => {
      const c = parseFloat(row.confidence || row.strength);
      return !isNaN(c) ? `${(c * 100).toFixed(0)}%` : "--";
    },
  },
  {
    title: "强度", key: "strength", minWidth: 100,
    render: (row) => {
      const pct = Math.round((row.strength || 0) * 100);
      const color = pct > 70 ? "var(--n-color-success)" : pct > 40 ? "var(--n-color-warning)" : "var(--n-color-error)";
      return h("div", { style: { display: "flex", alignItems: "center", gap: "6px" } }, [
        h(NProgress, { percentage: pct, showIndicator: false, height: 4, color, style: { width: "50px" } }),
        h("span", { style: { fontSize: "12px" } }, `${pct}%`),
      ]);
    },
  },
  { title: "原因", key: "reason", minWidth: 150, ellipsis: { tooltip: true }, render: (row) => row.reason || "--" },
  {
    title: "状态", key: "status", minWidth: 72,
    render: (row) => h(NTag, { type: statusTag(signalStatus(row)).type, size: "small", bordered: false }, { default: () => statusTag(signalStatus(row)).text }),
  },
  {
    title: "操作", key: "actions", width: 200, fixed: "right" as const,
    render: (row) => {
      const sid = row.signal_id || row.id;
      const st = signalStatus(row);
      const traceBtn = () => h(NButton, { size: "tiny", quaternary: true, onClick: () => openTrace(row) }, { default: () => "追溯" });
      if (st === "pending") {
        return h("div", { style: { display: "flex", gap: "4px" } }, [
          h(NButton, { size: "tiny", type: "success", loading: reviewing.value.has(sid), onClick: () => handleReview(sid, "approved") }, { default: () => "采纳" }),
          h(NButton, { size: "tiny", type: "error", loading: reviewing.value.has(sid), onClick: () => handleReview(sid, "rejected") }, { default: () => "拒绝" }),
          traceBtn(),
        ]);
      }
      if (st === "approved") {
        return h("div", { style: { display: "flex", gap: "4px" } }, [
          h(NButton, { size: "tiny", type: "primary", onClick: () => openFill(row) }, { default: () => "录入成交" }),
          traceBtn(),
        ]);
      }
      return traceBtn();
    },
  },
];

onMounted(() => loadSignals());
</script>

<template>
  <div class="signal-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">信号管理</h1>
          <p class="page-description">查看、审核、追溯所有策略产生的交易信号</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="loadSignals" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- ========== Error ========== -->
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadSignals">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <!-- ========== Stat cards ========== -->
        <div class="stats-row">
          <n-card size="small" :bordered="true" class="stat-card">
            <n-statistic label="待审核" :value="stats.pending">
              <template #prefix><span style="font-size:16px">⚠️</span></template>
            </n-statistic>
          </n-card>
          <n-card size="small" :bordered="true" class="stat-card">
            <n-statistic label="已采纳" :value="stats.approved" />
          </n-card>
          <n-card size="small" :bordered="true" class="stat-card">
            <n-statistic label="已执行" :value="stats.executed" />
          </n-card>
          <n-card size="small" :bordered="true" class="stat-card">
            <n-statistic label="已拒绝" :value="stats.rejected" />
          </n-card>
        </div>

        <!-- ========== Filter bar ========== -->
        <div class="filter-bar">
          <n-space align="center" :wrap="false">
            <n-select
              v-model:value="filters.status"
              :options="statusOpts as any"
              size="small"
              style="width: 120px"
              placeholder="状态"
            />
            <n-select
              v-model:value="filters.signal_type"
              :options="typeOpts as any"
              size="small"
              style="width: 110px"
              placeholder="类型"
            />
            <n-date-picker
              v-model:formatted-value="filters.dateRange as any"
              type="daterange"
              size="small"
              style="width: 220px"
              placeholder="日期范围"
              clearable
            />
            <n-input
              v-model:value="filters.ts_code"
              size="small"
              style="width: 140px"
              placeholder="股票代码"
              clearable
            />
            <n-button size="small" type="primary" @click="handleSearch">搜索</n-button>
            <n-button size="small" @click="handleReset">重置</n-button>
          </n-space>
        </div>

        <!-- ========== Signal table ========== -->
        <n-spin :show="loading">
          <n-data-table
            v-if="signals.length > 0"
            :columns="columns"
            :data="signals"
            :bordered="false"
            size="small"
            :row-key="(row: any) => row.signal_id || row.id"
            :pagination="{
              page: pagination.page,
              pageSize: pagination.page_size,
              itemCount: pagination.total,
              showSizePicker: true,
              pageSizes: [10, 20, 50],
              onChange: handlePageChange,
              onUpdatePageSize: (size: number) => { pagination.page_size = size; loadSignals(); },
            }"
          />
          <n-empty v-else description="暂无信号数据">
            <template #extra>
              <span style="font-size:13px;color:var(--n-text-color-3)">策略运行后，信号将在此显示</span>
            </template>
          </n-empty>
        </n-spin>
      </template>
    </div>

    <!-- ========== 录入成交（复用驾驶舱 TradeRecordModal） ========== -->
    <TradeRecordModal
      v-model="showRecordModal"
      :prefilled="recordPrefill"
      @submitted="handleRecordSubmitted"
    />

    <!-- v3.4: 信号链路追溯 -->
    <SignalTraceModal
      :show="showTrace"
      :signal-id="traceSignalId"
      @update:show="showTrace = $event"
    />
  </div>
</template>

<style scoped lang="scss">
.signal-page {
  min-height: 100vh;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  :deep(.n-statistic__label) {
    font-size: 13px;
  }
  :deep(.n-statistic__value) {
    font-size: 24px;
    font-weight: 700;
  }
}

.filter-bar {
  padding: 12px 16px;
  margin-bottom: 16px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: var(--n-border-radius);
}
</style>
