<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  NTabs, NTabPane, NCard, NDataTable, NButton, NTag, NSpin,
  NResult, NEmpty, NModal, NForm, NFormItem, NInput, NSelect,
  NProgress, NBadge, NAlert, useMessage, NSpace,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import StockContextPanel from "@/components/trade/StockContextPanel.vue";
import TradeRecordModal from "@/components/trade/TradeRecordModal.vue";
import { useWebSocket } from "@/composables/useWebSocket";
import type { Account, Order, Position, Basket } from "@/types";
import request from "@/utils/request";
import tradeAPI from "@/api/trade";
import basketAPI from "@/api/basket";

const router = useRouter();
const route = useRoute();
const message = useMessage();

// WebSocket: VITE_WS_URL 为 ws://host:port/api/ws 格式时才启用
const wsUrl = import.meta.env.VITE_WS_URL as string | undefined;
if (wsUrl && wsUrl.includes("://")) {
  useWebSocket();
}

// ============================================================
// State
// ============================================================
const activeTab = ref((route.query.tab as string) || "signals");
// 仅初始化时从 URL 读取 tab，后续切换不写 URL，避免 router.replace 与侧边栏 push 竞争

const loading = ref(false);
const error = ref(false);
const failedSources = ref<string[]>([]);

// Account
const accounts = ref<Account[]>([]);
const selectedAccountId = ref<string | null>(null);

// Positions
const positions = ref<Position[]>([]);

// Orders
const orders = ref<Order[]>([]);
const orderFilter = ref("all");

// Baskets
const baskets = ref<Basket[]>([]);

// Signals
const signals = ref<any[]>([]);
const signalFilter = ref("pending");
const signalReviewing = ref<Set<string>>(new Set());

// Trade record modal
const showRecordModal = ref(false);
const recordPrefill = ref<any>(null);

// Stock context
const selectedStock = ref<{ tsCode: string; name: string; price: number | null; changePercent: number | null } | null>(null);
const contextLoading = ref(false);

// ============================================================
// Data loader
// ============================================================
const loadAllData = async () => {
  loading.value = true;
  error.value = false;
  failedSources.value = [];
  try {
    const [acctRes, posRes, orderRes, basketRes, sigRes] = await Promise.all([
      tradeAPI.getAccountInfo().catch(() => { failedSources.value.push("账户"); return []; }),
      tradeAPI.getPositions().catch(() => { failedSources.value.push("持仓"); return []; }),
      tradeAPI.getOrders({ pageSize: 50 } as any).catch(() => { failedSources.value.push("订单"); return { items: [], total: 0 }; }),
      basketAPI.getBaskets().catch(() => { failedSources.value.push("篮子"); return { baskets: [], total: 0 }; }),
      tradeAPI.getSignals({ page_size: 50 }).catch(() => { failedSources.value.push("信号"); return { data: [] }; }),
    ]);

    // 账户 API 返回单对象或数组，统一转为数组
    const acctData = (acctRes as any)?.data ?? acctRes;
    const acctList = Array.isArray(acctData) ? acctData : (acctData ? [acctData] : []);
    accounts.value = acctList.map((a: any) => ({
      ...a,
      id: String(a.id ?? a.account_id ?? ""),
      total_asset: a.total_asset ?? a.total_balance ?? 0,
      available_cash: a.available_cash ?? a.cash ?? a.available_balance ?? 0,
      market_value: a.market_value ?? 0,
      total_pnl: a.total_pnl ?? a.pnl ?? 0,
    }));
    if (accounts.value.length > 0 && !selectedAccountId.value) {
      selectedAccountId.value = String(accounts.value[0].id);
    }

    positions.value = (Array.isArray(posRes) ? posRes : []) as Position[];
    const orderItems = (orderRes as any)?.items ?? (Array.isArray(orderRes) ? orderRes : []);
    orders.value = orderItems as Order[];
    baskets.value = (basketRes as any)?.baskets ?? ([] as Basket[]);

    const sigData = (sigRes as any)?.data ?? (Array.isArray(sigRes) ? sigRes : []);
    signals.value = Array.isArray(sigData) ? sigData : [];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

// 精准刷新（成交录入后只刷新受影响的数据）
const refreshAfterTrade = async () => {
  const [posRes, orderRes, acctRes] = await Promise.all([
    tradeAPI.getPositions().catch(() => []),
    tradeAPI.getOrders({ pageSize: 50 } as any).catch(() => ({ items: [], total: 0 })),
    tradeAPI.getAccountInfo().catch(() => []),
  ]);
  positions.value = (Array.isArray(posRes) ? posRes : []) as Position[];
  const orderItems = (orderRes as any)?.items ?? (Array.isArray(orderRes) ? orderRes : []);
  orders.value = orderItems as Order[];
  const acctData2 = (acctRes as any)?.data ?? acctRes;
  const acctList2 = Array.isArray(acctData2) ? acctData2 : (acctData2 ? [acctData2] : []);
  accounts.value = acctList2.map((a: any) => ({
    ...a,
    id: String(a.id ?? a.account_id ?? ""),
    total_asset: a.total_asset ?? a.total_balance ?? 0,
    available_cash: a.available_cash ?? a.cash ?? a.available_balance ?? 0,
    market_value: a.market_value ?? 0,
    total_pnl: a.total_pnl ?? a.pnl ?? 0,
  }));
};

// ============================================================
// Account summary (top bar)
// ============================================================
const accountStats = computed(() => {
  if (accounts.value.length === 0) return { totalAsset: 0, availableCash: 0, marketValue: 0, pnl: 0, pnlRate: 0 };
  const a = accounts.value.find((ac) => String(ac.id) === selectedAccountId.value) || accounts.value[0];
  return {
    totalAsset: (a as any).total_asset ?? 0,
    availableCash: (a as any).available_cash ?? 0,
    marketValue: (a as any).market_value ?? 0,
    pnl: (a as any).total_pnl ?? 0,
    pnlRate: (a as any).pnl_rate ?? 0,
  };
});

const signalCounts = computed(() => ({
  pending: signals.value.filter((s) => (s.status ?? "pending") === "pending").length,
  approved: signals.value.filter((s) => s.status === "approved").length,
  total: signals.value.length,
}));

// ============================================================
// Signal actions
// ============================================================
const handleReviewSignal = async (signalId: string, action: string) => {
  // 乐观更新：先改 UI
  const found = signals.value.find((s) => s.signal_id === signalId || s.id === signalId);
  const prevStatus = found?.status;
  if (found) found.status = action;

  signalReviewing.value.add(signalId);
  try {
    await tradeAPI.reviewSignal(signalId, action);
    message.success(action === "approved" ? "已采纳" : "已拒绝");
  } catch (e: any) {
    // 失败回滚
    if (found) found.status = prevStatus;
    message.error(e?.response?.data?.detail || "操作失败");
  } finally {
    signalReviewing.value.delete(signalId);
  }
};

const handleRecordFromSignal = (signal: any) => {
  recordPrefill.value = {
    signal_id: signal.signal_id || signal.id,
    strategy_id: signal.strategy_id,
    ts_code: signal.ts_code,
    direction: signal.signal_type || signal.direction,
    price: signal.price,
    quantity: signal.quantity,
  };
  showRecordModal.value = true;
};

const handleRecordSubmitted = () => {
  refreshAfterTrade();
};

// ============================================================
// Signal tab columns
// ============================================================
const statusTag = (status: string) => {
  const map: Record<string, { text: string; type: "info" | "warning" | "success" | "default" | "error" }> = {
    pending: { text: "待审核", type: "warning" },
    approved: { text: "已采纳", type: "success" },
    rejected: { text: "已拒绝", type: "default" },
    executed: { text: "已执行", type: "info" },
  };
  return map[status] || { text: status, type: "default" as const };
};

const filteredSignals = computed(() => {
  if (signalFilter.value === "all") return signals.value;
  return signals.value.filter((s) => (s.status ?? "pending") === signalFilter.value);
});

// ============================================================
// Cross-entity helpers
// ============================================================
const getPositionByTsCode = (tsCode: string): Position | undefined =>
  positions.value.find((p: any) => (p.ts_code || p.symbol) === tsCode);

const getOrdersForStock = (tsCode: string): Order[] =>
  orders.value.filter((o: any) => (o.ts_code || o.symbol) === tsCode);

const getBasketsForStock = (tsCode: string): Basket[] =>
  baskets.value.filter((b) => {
    const items = (b as any).items as { ts_code: string }[] | undefined;
    return items?.some((item) => item.ts_code === tsCode);
  });

const handleSelectStock = async (tsCode: string, name: string) => {
  contextLoading.value = true;
  selectedStock.value = { tsCode, name, price: null, changePercent: null };
  await new Promise((r) => setTimeout(r, 200));
  const pos: any = getPositionByTsCode(tsCode);
  selectedStock.value = {
    tsCode,
    name,
    price: pos?.current_price ?? pos?.last_price ?? null,
    changePercent: pos ? (pos.profit_rate ?? pos.pnl_rate ?? 0) : 0,
  };
  contextLoading.value = false;
};

const selectedPosition = computed(() =>
  selectedStock.value ? (getPositionByTsCode(selectedStock.value.tsCode) ?? null) : null,
);
const selectedRelatedOrders = computed(() =>
  selectedStock.value ? getOrdersForStock(selectedStock.value.tsCode) : [],
);
const selectedRelatedBaskets = computed(() =>
  selectedStock.value ? getBasketsForStock(selectedStock.value.tsCode) : [],
);

// ============================================================
// Basket tab
// ============================================================
const getBasketHoldStats = (basket: Basket) => {
  const items = (basket as any).items as { ts_code: string; weight: number }[] | undefined;
  if (!items || items.length === 0) return { held: 0, total: 0 };
  const held = items.filter((item) => getPositionByTsCode(item.ts_code)).length;
  return { held, total: items.length };
};

const basketColumns: DataTableColumns<Basket> = [
  { title: "篮子名称", key: "name", width: 160, render: (row) => h("span", { style: { fontWeight: 600 } }, row.name) },
  { title: "描述", key: "description", ellipsis: { tooltip: true } },
  {
    title: "持仓覆盖", key: "holdStatus", width: 180,
    render: (row) => {
      const { held, total } = getBasketHoldStats(row);
      const pct = total > 0 ? Math.round((held / total) * 100) : 0;
      return h("div", { style: { display: "flex", alignItems: "center", gap: "8px" } }, [
        h(NProgress, { percentage: pct, color: pct > 50 ? "var(--n-color-success)" : pct > 0 ? "var(--n-color-warning)" : "var(--n-text-color-3)", height: 6, borderRadius: 3, style: { width: "120px" } }),
        h("span", { style: { fontSize: "12px", color: "var(--n-text-color-3)" } }, `${held}/${total}`),
      ]);
    },
  },
  {
    title: "操作", key: "actions", width: 160,
    render: (row) => h("div", { style: { display: "flex", gap: "6px" } }, [
      h(NButton, { size: "small", onClick: () => router.push(`/baskets/detail/${row.id}`) }, { default: () => "详情" }),
    ]),
  },
];

// ============================================================
// Order tab
// ============================================================
const statusMap: Record<string, { text: string; type: "info" | "warning" | "success" | "default" | "error" }> = {
  submitted: { text: "已报", type: "info" },
  partial_filled: { text: "部成", type: "warning" },
  filled: { text: "已成", type: "success" },
  cancelled: { text: "已撤", type: "default" },
  rejected: { text: "废单", type: "error" },
};

const filteredOrders = computed(() => {
  if (orderFilter.value === "all") return orders.value;
  return orders.value.filter((o) => o.status === orderFilter.value);
});

const orderFilterOptions = [
  { label: "全部", value: "all" },
  { label: "已报", value: "submitted" },
  { label: "部成", value: "partial_filled" },
  { label: "已成", value: "filled" },
  { label: "已撤", value: "cancelled" },
];

const orderColumns: DataTableColumns<Order> = [
  { title: "时间", key: "submitted_at", width: 160, render: (row: any) => (row.created_at || row.submitted_at || "").slice(0, 16) },
  {
    title: "代码", key: "ts_code", width: 110,
    render: (row: any) => {
      const code = row.ts_code || row.symbol || "";
      return h("span", { class: "clickable-stock", style: { color: "var(--n-color-primary)", cursor: "pointer" }, onClick: () => handleSelectStock(code, code) }, code);
    },
  },
  {
    title: "方向", key: "direction", width: 60,
    render: (row: any) => h(NTag, { type: row.direction === "buy" ? "success" : "error", size: "small", bordered: false }, { default: () => (row.direction === "buy" ? "买入" : "卖出") }),
  },
  { title: "价格", key: "price", width: 100, render: (row: any) => ((row.price ?? 0) > 0 ? `¥${(row.price ?? 0).toFixed(2)}` : "市价") },
  { title: "数量", key: "volume", width: 80, render: (row: any) => (row.volume ?? 0).toLocaleString() },
  {
    title: "状态", key: "status", width: 80,
    render: (row: any) => h(NTag, { type: statusMap[row.status]?.type || "default", size: "small", bordered: false }, { default: () => statusMap[row.status]?.text || row.status }),
  },
];

// ============================================================
// Position tab
// ============================================================
const positionColumns: DataTableColumns<Position> = [
  {
    title: "代码", key: "ts_code", width: 110,
    render: (row: any) => {
      const code = row.ts_code || row.symbol || "";
      const name = row.name || code;
      return h("span", { class: "clickable-stock", style: { color: "var(--n-color-primary)", cursor: "pointer" }, onClick: () => handleSelectStock(code, name) }, code);
    },
  },
  { title: "持仓量", key: "volume", width: 90, render: (row: any) => (row.volume ?? 0).toLocaleString() },
  { title: "成本价", key: "cost_price", width: 95, render: (row: any) => `¥${(row.cost_price ?? 0).toFixed(2)}` },
  { title: "当前价", key: "current_price", width: 95, render: (row: any) => `¥${(row.current_price ?? 0).toFixed(2)}` },
  { title: "市值", key: "market_value", width: 110, render: (row: any) => {
    const mv = row.market_value ?? ((row.volume ?? 0) * (row.current_price ?? 0));
    return `¥${mv.toLocaleString()}`;
  }},
  {
    title: "盈亏", key: "pnl", width: 110,
    render: (row: any) => {
      const pnl = row.profit ?? row.pnl ?? 0;
      return h("span", { class: pnl >= 0 ? "text-up" : "text-down" }, `¥${pnl.toLocaleString()}`);
    },
  },
  {
    title: "盈亏比", key: "pnl_rate", width: 85,
    render: (row: any) => {
      const rate = row.profit_rate ?? row.pnl_rate ?? 0;
      return h("span", { class: rate >= 0 ? "text-up" : "text-down" }, `${rate.toFixed(2)}%`);
    },
  },
];

// ============================================================
// Account tab
// ============================================================
const accountColumns: DataTableColumns<Account> = [
  { title: "总资产", key: "total_asset", width: 120, render: (row: Account) => `¥${(row.total_asset ?? 0).toLocaleString()}` },
  { title: "可用资金", key: "available_cash", width: 120, render: (row: Account) => `¥${(row.available_cash ?? 0).toLocaleString()}` },
  { title: "持仓市值", key: "market_value", width: 120, render: (row: Account) => `¥${(row.market_value ?? 0).toLocaleString()}` },
  { title: "累计盈亏", key: "total_pnl", width: 110, render: (row: Account) => h("span", { class: (row.total_pnl ?? 0) >= 0 ? "text-up" : "text-down" }, `¥${(row.total_pnl ?? 0).toLocaleString()}`) },
  {
    title: "操作", key: "actions", width: 120,
    render: (row) => h("div", { style: { display: "flex", gap: "4px" } }, [
      h(NButton, { size: "tiny", onClick: () => openAccountEditor(row) }, { default: () => "编辑" }),
      h(NButton, { size: "tiny", type: "error", onClick: () => handleDeleteAccount(row.id) }, { default: () => "删除" }),
    ]),
  },
];

// Account CRUD
const showAccountModal = ref(false);
const editingAccountId = ref<string | null>(null);
const accountForm = reactive({
  account_name: "",
  account_type: "simulation" as string,
  initial_balance: 1000000,
});

function openAccountEditor(acct?: Account) {
  editingAccountId.value = acct ? String(acct.id) : null;
  accountForm.account_name = (acct as any)?.account_name || "";
  accountForm.account_type = (acct as any)?.account_type || "simulation";
  accountForm.initial_balance = (acct as any)?.initial_balance ?? (acct as any)?.total_asset ?? 1000000;
  showAccountModal.value = true;
}

async function handleSaveAccount() {
  try {
    const payload = {
      user_id: "",
      account_name: accountForm.account_name,
      account_type: accountForm.account_type,
      initial_balance: accountForm.initial_balance,
      broker: "sim",
    };
    if (editingAccountId.value) {
      await request.put(`/quantTrade/account/${editingAccountId.value}`, payload);
    } else {
      await request.post("/quantTrade/account", payload);
    }
    message.success(editingAccountId.value ? "账户已更新" : "账户已创建");
    showAccountModal.value = false;
    loadAllData();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "操作失败");
  }
}

async function handleDeleteAccount(id: string) {
  try {
    await request.delete(`/quantTrade/account/${id}`);
    // 乐观移除，避免 loadAllData 触发 vnode 卸载异常
    accounts.value = accounts.value.filter((a) => String(a.id) !== id);
    message.success("账户已删除");
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "删除失败");
  }
}

// ============================================================
// Init
// ============================================================
onMounted(() => loadAllData());
</script>

<template>
  <div class="trading-workspace bg-gradient-mesh bg-noise">
    <!-- ========== Page Header ========== -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">交易驾驶舱</h1>
          <p class="page-description">信号审核、成交录入、持仓订单管理</p>
        </div>
        <div class="header-actions">
          <n-button size="small" @click="router.push('/baskets/create')">
            <template #icon><SmartIcon name="Basket" /></template>
            新建篮子
          </n-button>
          <n-button type="primary" size="small" @click="showRecordModal = true; recordPrefill = null">
            <template #icon><SmartIcon name="Plus" /></template>
            录入成交
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- ========== Top Summary Bar ========== -->
      <div class="summary-bar glass-surface">
        <n-spin :show="loading" size="small">
          <div class="summary-grid">
            <div class="summary-item">
              <span class="summary-label">总资产</span>
              <span class="summary-value">¥{{ accountStats.totalAsset.toLocaleString() }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">可用资金</span>
              <span class="summary-value">¥{{ accountStats.availableCash.toLocaleString() }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">持仓市值</span>
              <span class="summary-value">¥{{ accountStats.marketValue.toLocaleString() }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">当日盈亏</span>
              <span class="summary-value" :class="accountStats.pnl >= 0 ? 'text-up' : 'text-down'">
                {{ accountStats.pnl >= 0 ? '+' : '' }}¥{{ accountStats.pnl.toLocaleString() }}
                <small>({{ accountStats.pnlRate >= 0 ? '+' : '' }}{{ accountStats.pnlRate.toFixed(2) }}%)</small>
              </span>
            </div>
          </div>
        </n-spin>
      </div>

      <!-- ========== Failed sources warning ========== -->
      <n-alert
        v-if="failedSources.length > 0 && !error"
        type="warning"
        :title="`部分数据加载失败: ${failedSources.join('、')}`"
        closable
        style="margin-bottom: 16px"
      />

      <!-- ========== Error ========== -->
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadAllData">重试</n-button>
        </template>
      </n-result>

      <!-- ========== Main Two-Column Layout (B 区) ========== -->
      <n-card v-else class="workspace-card" :bordered="true" size="small">
        <div class="workspace-layout">
          <!-- ===== Left Panel: Tabs ===== -->
          <div class="left-panel">
          <n-tabs v-model:value="activeTab" type="line" size="small">
            <!-- Tab 0: 信号流 -->
            <n-tab-pane name="signals">
              <template #tab>
                <n-badge :value="signalCounts.pending" :max="99" processing>
                  <span>信号流</span>
                </n-badge>
              </template>
              <n-spin :show="loading">
                <!-- Signal filter bar -->
                <div class="tab-toolbar">
                  <n-select
                    v-model:value="signalFilter"
                    :options="[
                      { label: `待审核 (${signalCounts.pending})`, value: 'pending' },
                      { label: `已采纳 (${signalCounts.approved})`, value: 'approved' },
                      { label: '全部', value: 'all' },
                    ]"
                    size="small"
                    style="width: 160px"
                  />
                </div>
                <!-- Signal list -->
                <div v-if="filteredSignals.length > 0" class="signal-list">
                  <div
                    v-for="s in filteredSignals"
                    :key="s.signal_id || s.id"
                    class="signal-card card-surface"
                    :class="{ 'signal-rejected': s.status === 'rejected' }"
                    @click="handleSelectStock(s.ts_code, s.ts_code)"
                  >
                    <div class="signal-left">
                      <div class="signal-top-row">
                        <n-tag
                          :type="(s.signal_type || s.direction) === 'buy' ? 'success' : 'error'"
                          size="tiny" :bordered="false"
                        >
                          {{ (s.signal_type || s.direction) === 'buy' ? '买' : '卖' }}
                        </n-tag>
                        <span class="signal-code">{{ s.ts_code }}</span>
                        <n-tag :type="statusTag(s.status ?? 'pending').type" size="tiny" :bordered="false">
                          {{ statusTag(s.status ?? 'pending').text }}
                        </n-tag>
                      </div>
                      <div class="signal-mid-row">
                        <span v-if="s.price" class="signal-price">¥{{ s.price }}</span>
                        <span v-if="s.quantity" class="signal-qty">×{{ s.quantity }}股</span>
                        <span v-if="s.strength != null" class="signal-strength" :class="s.strength >= 0.7 ? 'text-up' : 'text-secondary'">
                          强度 {{ (s.strength * 100).toFixed(0) }}%
                        </span>
                      </div>
                      <div v-if="s.reason" class="signal-reason">{{ s.reason }}</div>
                    </div>
                    <div class="signal-actions">
                      <template v-if="(s.status ?? 'pending') === 'pending'">
                        <n-button
                          size="tiny" type="success" :loading="signalReviewing.has(s.signal_id || s.id)"
                          @click.stop="handleReviewSignal(s.signal_id || s.id, 'approved')"
                        >采纳</n-button>
                        <n-button
                          size="tiny" type="error" :loading="signalReviewing.has(s.signal_id || s.id)"
                          @click.stop="handleReviewSignal(s.signal_id || s.id, 'rejected')"
                        >拒绝</n-button>
                      </template>
                      <template v-else-if="s.status === 'approved'">
                        <n-tag type="success" size="small" :bordered="false">已采纳 ✓</n-tag>
                        <n-button size="tiny" type="primary" @click.stop="handleRecordFromSignal(s)">录入成交</n-button>
                      </template>
                      <template v-else-if="s.status === 'executed'">
                        <n-tag type="info" size="small" :bordered="false">已执行 ✓</n-tag>
                      </template>
                    </div>
                  </div>
                </div>
                <n-empty v-else description="暂无交易信号">
                  <template #extra>
                    <span class="empty-hint">策略运行后，信号将在此显示</span>
                  </template>
                </n-empty>
              </n-spin>
            </n-tab-pane>

            <!-- Tab 1: 持仓 -->
            <n-tab-pane name="positions" tab="持仓">
              <n-spin :show="loading">
                <n-data-table
                  v-if="positions.length > 0"
                  :columns="positionColumns"
                  :data="positions"
                  :bordered="false"
                  size="small"
                  :row-key="(row: Position) => String(row.id)"
                />
                <n-empty v-else description="暂无持仓">
                  <template #extra>
                    <n-button size="small" type="primary" @click="showRecordModal = true; recordPrefill = null">
                      录入第一笔成交
                    </n-button>
                  </template>
                </n-empty>
              </n-spin>
            </n-tab-pane>

            <!-- Tab 2: 订单 -->
            <n-tab-pane name="orders" tab="订单">
              <n-spin :show="loading">
                <div class="tab-toolbar">
                  <n-select v-model:value="orderFilter" :options="orderFilterOptions" size="small" style="width: 120px" />
                </div>
                <n-data-table
                  v-if="filteredOrders.length > 0"
                  :columns="orderColumns"
                  :data="filteredOrders"
                  :bordered="false"
                  size="small"
                  :row-key="(row: Order) => row.order_id"
                />
                <n-empty v-else description="暂无订单记录">
                  <template #extra>
                    <span class="empty-hint">录入成交后自动生成订单</span>
                  </template>
                </n-empty>
              </n-spin>
            </n-tab-pane>

            <!-- Tab 3: 篮子 -->
            <n-tab-pane name="baskets" tab="篮子">
              <n-spin :show="loading">
                <div class="tab-toolbar">
                  <n-button type="primary" size="small" @click="router.push('/baskets/create')">
                    <template #icon><SmartIcon name="Basket" /></template>
                    新建篮子
                  </n-button>
                </div>
                <n-data-table
                  v-if="baskets.length > 0"
                  :columns="basketColumns"
                  :data="baskets"
                  :bordered="false"
                  size="small"
                  :row-key="(row: Basket) => row.id"
                />
                <n-empty v-else description="暂无篮子数据" />
              </n-spin>
            </n-tab-pane>

            <!-- Tab 4: 账户 -->
            <n-tab-pane name="account" tab="账户">
              <n-spin :show="loading">
                <div class="tab-toolbar">
                  <n-button type="primary" size="small" @click="openAccountEditor()">
                    <template #icon><SmartIcon name="Plus" /></template>
                    新增账户
                  </n-button>
                </div>
                <n-data-table
                  :columns="accountColumns"
                  :data="accounts"
                  :bordered="false"
                  size="small"
                  :row-key="(row: Account) => String(row.id)"
                >
                  <template #empty><n-empty description="暂无账户" /></template>
                </n-data-table>
              </n-spin>
            </n-tab-pane>
          </n-tabs>
        </div>

        <!-- ===== Right Panel: Stock Context (slide-out) ===== -->
        <div class="right-panel" :class="{ 'panel-open': selectedStock }">
          <div class="context-header">
            <span class="context-title">{{ selectedStock?.name || "股票详情" }}</span>
            <n-button size="tiny" text @click="selectedStock = null">
              <template #icon><SmartIcon name="Close" /></template>
            </n-button>
          </div>
          <StockContextPanel
            :ts-code="selectedStock?.tsCode ?? null"
            :stock-name="selectedStock?.name ?? ''"
            :current-price="selectedStock?.price ?? null"
            :change-percent="selectedStock?.changePercent ?? null"
            :position="selectedPosition"
            :related-orders="selectedRelatedOrders"
            :related-baskets="selectedRelatedBaskets"
            :loading="contextLoading"
            @trade="(dir: 'buy'|'sell') => { showRecordModal = true; recordPrefill = { ts_code: selectedStock?.tsCode, direction: dir }; }"
            @add-to-basket="message.info('请从篮子管理中选择目标篮子')"
          />
        </div>
      </div>
      </n-card>
    </div>

    <!-- Account Edit Modal -->
    <n-modal v-model:show="showAccountModal" preset="card" :title="editingAccountId ? '编辑账户' : '新增账户'" style="width: 420px">
      <n-form :model="accountForm" label-placement="left" label-width="100px">
        <n-form-item label="账户名称">
          <n-input v-model:value="accountForm.account_name" placeholder="如：模拟交易账户" />
        </n-form-item>
        <n-form-item label="账户类型">
          <n-select v-model:value="accountForm.account_type" :options="[
            { label: '模拟账户', value: 'simulation' },
            { label: '现金账户', value: 'cash' },
          ]" />
        </n-form-item>
        <n-form-item label="初始资金">
          <n-input-number v-model:value="accountForm.initial_balance" :min="0" :step="10000" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showAccountModal = false">取消</n-button>
          <n-button type="primary" @click="handleSaveAccount">保存</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Trade Record Modal -->
    <TradeRecordModal
      v-model="showRecordModal"
      :prefilled="recordPrefill"
      @submitted="handleRecordSubmitted"
    />
  </div>
</template>

<style scoped lang="scss">
.trading-workspace {
  min-height: 100vh;
}

// ---- Summary Bar (A 区) ----
.summary-bar {
  padding: 16px 20px;
  border-radius: var(--n-border-radius);
  margin-bottom: 20px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.summary-grid {
  display: flex;
  gap: 40px;
}
.summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.summary-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.summary-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--n-text-color-1);
  font-variant-numeric: tabular-nums;
  small {
    font-size: 12px;
    font-weight: 500;
  }
}

// ---- Workspace Card (B 区) ----
.workspace-card {
  border-radius: var(--n-border-radius);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

// ---- Workspace Layout ----
.workspace-layout {
  display: flex;
  gap: 0;
}

.left-panel {
  flex: 1;
  min-width: 0;
  :deep(.n-tabs-nav) {
    margin-bottom: 12px;
  }
}

.right-panel {
  width: 0;
  overflow: hidden;
  transition: width 0.25s ease;
  border-left: 1px solid transparent;
  &.panel-open {
    width: 320px;
    min-width: 320px;
    border-left-color: var(--n-border-color);
    padding-left: 16px;
    margin-left: 16px;
  }
}
.context-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.context-title {
  font-weight: 600;
  font-size: 15px;
}

// ---- Signal list ----
.signal-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.signal-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-radius: var(--n-border-radius);
  cursor: pointer;
  transition: all 0.2s var(--n-bezier);
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-left: 3px solid var(--n-color-target);
  &.signal-rejected {
    opacity: 0.5;
    border-left-color: var(--n-text-color-3);
  }
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  }
}
.signal-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.signal-top-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.signal-code {
  font-weight: 600;
  font-size: 14px;
  color: var(--n-text-color-1);
}
.signal-mid-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--n-text-color-2);
}
.signal-price {
  font-weight: 600;
}
.signal-qty {
  color: var(--n-text-color-3);
}
.signal-reason {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.signal-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

// ---- Common ----
.tab-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.empty-hint {
  font-size: 13px;
  color: var(--n-text-color-3);
}
.clickable-stock {
  &:hover {
    text-decoration: underline;
  }
}
.text-up {
  color: var(--n-color-success);
}
.text-down {
  color: var(--n-color-error);
}
.text-secondary {
  color: var(--n-text-color-3);
}
</style>
