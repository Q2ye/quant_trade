<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  NTabs, NTabPane, NCard, NDataTable, NButton, NTag, NSpin,
  NResult, NEmpty, NModal, NForm, NFormItem, NInput, NInputNumber, NSelect,
  NProgress, NBadge, NAlert, NRadioGroup, NRadio, useMessage, useDialog, NSpace,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import StockContextPanel from "@/components/trade/StockContextPanel.vue";
import TradeRecordModal from "@/components/trade/TradeRecordModal.vue";
import { useWebSocket } from "@/composables/useWebSocket";
import type { Account, Order, Position, Basket } from "@/types";
import request from "@/utils/request";
import tradeAPI, { SIGNAL_REJECT_REASONS, formatRejectReason } from "@/api/trade";
import basketAPI from "@/api/basket";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const dialog = useDialog();

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
      request.get("/quantTrade/account/list", { params: { page: 1, page_size: 100 } }).catch(() => { failedSources.value.push("账户"); return { data: { data: [] } }; }),
      tradeAPI.getPositions().catch(() => { failedSources.value.push("持仓"); return []; }),
      tradeAPI.getOrders({ pageSize: 50 } as any).catch(() => { failedSources.value.push("订单"); return { items: [], total: 0 }; }),
      basketAPI.getBaskets().catch(() => { failedSources.value.push("篮子"); return { baskets: [], total: 0 }; }),
      tradeAPI.getSignals({ page_size: 50 }).catch(() => { failedSources.value.push("信号"); return { data: [] }; }),
      request.get("/quantTrade/strategy", { params: { page: 1, page_size: 200 } }).then((r: any) => {
        // response interceptor 已提取 response.data，r = { success, data: [...], pagination }
        strategyList.value = r?.data || [];
      }).catch(() => {}),
    ]);

    // 账户列表 API 返回 { success: true, data: [...] }（v2.6 起含 daily_pnl/daily_return）
    const acctList = (acctRes as any)?.data?.data || (acctRes as any)?.data || [];
    accounts.value = (Array.isArray(acctList) ? acctList : []).map((a: any) => ({
      ...a,
      id: String(a.id ?? ""),
      total_asset: a.total_balance ?? a.total_asset ?? 0,
      available_cash: a.available_balance ?? a.available_cash ?? 0,
      market_value: a.market_value ?? 0,
      total_pnl: a.total_pnl ?? a.pnl ?? 0,
      daily_pnl: a.daily_pnl ?? 0,
      daily_return: a.daily_return ?? 0,
    }));
    if (accounts.value.length > 0 && !selectedAccountId.value) {
      selectedAccountId.value = String(accounts.value[0].id);
    }

    positions.value = (Array.isArray(posRes) ? posRes : []) as Position[];
    const orderData = (orderRes as any)?.data ?? (Array.isArray(orderRes) ? orderRes : []);
    orders.value = (Array.isArray(orderData) ? orderData : []) as Order[];
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
  const [posRes, orderRes, acctRes2] = await Promise.all([
    tradeAPI.getPositions().catch(() => []),
    tradeAPI.getOrders({ pageSize: 50 } as any).catch(() => ({ data: [], total: 0 })),
    request.get("/quantTrade/account/list", { params: { page: 1, page_size: 100 } }).catch(() => ({ data: { data: [] } })),
  ]);
  positions.value = (Array.isArray(posRes) ? posRes : []) as Position[];
  const orderData2 = (orderRes as any)?.data ?? (Array.isArray(orderRes) ? orderRes : []);
  orders.value = (Array.isArray(orderData2) ? orderData2 : []) as Order[];
  const acctList2 = (acctRes2 as any)?.data?.data || (acctRes2 as any)?.data || [];
  accounts.value = (Array.isArray(acctList2) ? acctList2 : []).map((a: any) => ({
    ...a,
    id: String(a.id ?? ""),
  }));
};

// ============================================================
// Account summary (top bar)
// 当日盈亏/收益率取日终结算快照字段（daily_pnl/daily_return），非累计 pnl
// ============================================================
const accountStats = computed(() => {
  if (accounts.value.length === 0) return { totalAsset: 0, availableCash: 0, marketValue: 0, pnl: 0, pnlRate: 0, pnlDate: null };
  const a = accounts.value.find((ac) => String(ac.id) === selectedAccountId.value) || accounts.value[0];
  return {
    totalAsset: (a as any).total_asset ?? 0,
    availableCash: (a as any).available_cash ?? 0,
    marketValue: (a as any).market_value ?? 0,
    pnl: (a as any).daily_pnl ?? 0,
    pnlRate: (a as any).daily_return ?? 0,
    pnlDate: (a as any).daily_pnl_date ?? null,
  };
});

const signalCounts = computed(() => ({
  pending: signals.value.filter((s) => signalStatus(s) === "pending").length,
  approved: signals.value.filter((s) => signalStatus(s) === "approved").length,
  total: signals.value.length,
}));

// ============================================================
// Signal actions
// ============================================================
const handleReviewSignal = async (signalId: string, action: string) => {
  if (action === "rejected") {
    // 拒绝时弹窗选择拒绝原因
    pendingRejectSignalId.value = signalId;
    selectedRejectReason.value = "manual_rejected";
    showRejectDialog.value = true;
    return;
  }
  await doReviewSignal(signalId, action);
};

const doReviewSignal = async (signalId: string, action: string, rejectReason?: string) => {
  // 乐观更新：先改 UI（后端字段为 signal_status）
  const found = signals.value.find((s) => s.signal_id === signalId || s.id === signalId);
  const prevStatus = found?.signal_status;
  if (found) found.signal_status = action;

  signalReviewing.value.add(signalId);
  try {
    await tradeAPI.reviewSignal(signalId, action, undefined, rejectReason);
    message.success(action === "approved" ? "已采纳" : "已拒绝");
  } catch (e: any) {
    // 失败回滚
    if (found) found.signal_status = prevStatus;
    message.error(e?.response?.data?.detail || "操作失败");
  } finally {
    signalReviewing.value.delete(signalId);
  }
};

const showRejectDialog = ref(false);
const selectedRejectReason = ref("manual_rejected");
const pendingRejectSignalId = ref("");

const confirmReject = async () => {
  showRejectDialog.value = false;
  await doReviewSignal(pendingRejectSignalId.value, "rejected", selectedRejectReason.value);
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
// 买入订单 → 快捷卖出
// ============================================================
// 对已成交/部成的买入订单提供"卖出"快捷入口，预填卖出方向 + 标的 + 价格/数量
const handleQuickSell = (order: any) => {
  const ts_code = order.ts_code || order.symbol || "";
  const pos = getPositionByTsCode(ts_code);
  recordPrefill.value = {
    ts_code,
    direction: "sell",
    price: pos?.current_price ?? order.price ?? null,
    quantity: pos?.available_volume ?? pos?.volume ?? order.volume ?? null,
  };
  showRecordModal.value = true;
};

// ============================================================
// 买卖 FIFO 配对追溯
// ============================================================
const showRoundTripModal = ref(false);
const roundTrips = ref<any>(null);
const roundTripLoading = ref(false);

const openRoundTrips = async () => {
  const accountId = selectedAccountId.value;
  if (!accountId) {
    message.warning("请先选择账户");
    return;
  }
  roundTripLoading.value = true;
  showRoundTripModal.value = true;
  roundTrips.value = null;
  try {
    roundTrips.value = await tradeAPI.getRoundTrips(accountId);
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "加载配对失败");
  } finally {
    roundTripLoading.value = false;
  }
};

const roundTripStocks = computed(() => roundTrips.value?.stocks ?? []);
const roundTripSummary = computed(() => roundTrips.value?.summary ?? null);

// ============================================================
// Signal tab columns
// ============================================================
const statusTag = (status: string) => {
  const map: Record<string, { text: string; type: "info" | "warning" | "success" | "default" | "error" }> = {
    pending: { text: "待审核", type: "warning" },
    pending_confirm: { text: "待确认", type: "warning" },
    pending_manual: { text: "待审核", type: "warning" },
    approved: { text: "已采纳", type: "success" },
    promoted: { text: "已转正", type: "success" },
    rejected: { text: "已拒绝", type: "default" },
    expired: { text: "已过期", type: "default" },
    executed: { text: "已执行", type: "info" },
  };
  return map[status] || { text: status, type: "default" as const };
};

// 后端 signal_status → 前端展示/过滤状态归一化（后端字段为 signal_status）
const signalStatus = (s: any): string => {
  const raw = s?.signal_status ?? s?.status ?? "pending";
  if (raw === "pending" || raw === "pending_manual") return "pending";
  if (raw === "confirmed") return "approved";
  return raw; // approved / rejected / executed / failed / error
};

const filteredSignals = computed(() => {
  if (signalFilter.value === "all") return signals.value;
  return signals.value.filter((s) => signalStatus(s) === signalFilter.value);
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
  {
    title: "操作", key: "actions", width: 80, fixed: "right",
    render: (row: any) => {
      const canQuickSell =
        row.direction === "buy" &&
        (row.status === "filled" || row.status === "partial_filled");
      if (!canQuickSell) return null;
      return h(
        NButton,
        { size: "tiny", type: "error", onClick: () => handleQuickSell(row) },
        { default: () => "卖出" },
      );
    },
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
const strategyList = ref<any[]>([]);

const boundStrategies = computed(() => {
  const map: Record<string, any[]> = {};
  strategyList.value.forEach((s: any) => {
    if (s.account_id) {
      (map[s.account_id] ||= []).push(s);
    }
  });
  return map;
});

const accountColumns: DataTableColumns<Account> = [
  {
    title: "账户", key: "account_name", width: 180,
    render: (row: any) => {
      const broker = row.broker || "";
      const name = row.account_name || row.account_number || row.id || "";
      const typeTag = row.account_type === "simulation" ? h(NTag, { size: "tiny", type: "warning", bordered: false }, { default: () => "仿真" })
        : row.account_type === "cash" ? h(NTag, { size: "tiny", type: "success", bordered: false }, { default: () => "现金" })
        : h(NTag, { size: "tiny", bordered: false }, { default: () => row.account_type || "未知" });
      return h("div", { style: { display: "flex", alignItems: "center", gap: "6px" } }, [
        h("span", { style: { fontWeight: 600 } }, broker || name),
        typeTag,
      ]);
    },
  },
  { title: "券商", key: "broker", width: 80, render: (row: any) => row.broker || "—" },
  { title: "总资产", key: "total_asset", width: 110, render: (row: any) => `¥${((row.total_asset ?? row.total_balance ?? 0)).toLocaleString()}` },
  { title: "可用资金", key: "available_cash", width: 110, render: (row: any) => `¥${((row.available_cash ?? row.available_balance ?? 0)).toLocaleString()}` },
  { title: "持仓市值", key: "market_value", width: 100, render: (row: any) => `¥${((row.market_value ?? 0)).toLocaleString()}` },
  {
    title: "绑定策略", key: "strategies", width: 160,
    render: (row: any) => {
      const bound = boundStrategies.value[row.id] || [];
      if (bound.length === 0) return h("span", { style: { color: "var(--color-text-tertiary)", fontSize: "11px" } }, "无");
      // 只显示运行中策略；停止/淘汰的收敛为一个灰标（保留关联，重启可见）
      const running = bound.filter((s: any) => s.status === "running" || s.status === "paused");
      const stoppedCount = bound.length - running.length;
      return h("div", { style: { display: "flex", flexDirection: "column", gap: "2px" } }, [
        ...running.map((s: any) =>
          h(NTag, { size: "tiny", bordered: false, type: "success" }, {
            default: () => s.name || s.id?.slice(0, 8) || "—"
          })
        ),
        stoppedCount > 0
          ? h(NTag, { size: "tiny", bordered: false, type: "default" }, { default: () => `已停止 ${stoppedCount}` })
          : null,
      ]);
    },
  },
  {
    title: "操作", key: "actions", width: 230,
    render: (row) => h("div", { style: { display: "flex", gap: "4px" } }, [
      h(NButton, { size: "tiny", onClick: () => openAccountEditor(row) }, { default: () => "编辑" }),
      h(NButton, { size: "tiny", type: "success", onClick: () => openFundModal(row, "deposit") }, { default: () => "入金" }),
      h(NButton, { size: "tiny", type: "warning", onClick: () => openFundModal(row, "withdraw") }, { default: () => "出金" }),
      h(NButton, { size: "tiny", type: "error", onClick: () => confirmDeleteAccount(row) }, { default: () => "删除" }),
    ]),
  },
];

// Account CRUD
const showAccountModal = ref(false);
const editingAccountId = ref<string | null>(null);
const accountForm = reactive({
  account_name: "",
  account_type: "cash" as string,
  broker: "",
  broker_account_id: "",
  initial_balance: 1000000,
});

function openAccountEditor(acct?: any) {
  const id = acct?.id || acct?.account_id;
  editingAccountId.value = id ? String(id) : null;
  accountForm.account_name = acct?.account_name || "";
  accountForm.account_type = acct?.account_type || "cash";
  accountForm.broker = acct?.broker || "";
  accountForm.broker_account_id = acct?.broker_account_id || "";
  accountForm.initial_balance = acct?.initial_balance ?? acct?.total_asset ?? acct?.total_balance ?? 1000000;
  showAccountModal.value = true;
}

async function handleSaveAccount() {
  try {
    const payload: any = {
      account_name: accountForm.account_name,
      account_type: accountForm.account_type,
      broker: accountForm.broker,
      broker_account_id: accountForm.broker_account_id,
    };
    // 初始资金仅在创建时提交；编辑时后端无该字段，避免误导
    if (!editingAccountId.value) {
      payload.initial_balance = accountForm.initial_balance;
    }
    if (editingAccountId.value) {
      await request.put(`/quantTrade/account/${editingAccountId.value}`, payload);
      message.success("账户已更新");
    } else {
      await request.post("/quantTrade/account", payload);
      message.success("账户已创建");
    }
    showAccountModal.value = false;
    editingAccountId.value = null;
    await loadAllData();
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

function confirmDeleteAccount(account: any) {
  const name = account.account_name || account.account_number || String(account.id);
  dialog.warning({
    title: "删除账户",
    content: `确定删除账户「${name}」？有持仓或未完成订单时后端会拒绝删除。`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: () => handleDeleteAccount(String(account.id)),
  });
}

// ============================================================
// 入金 / 出金
// ============================================================
const showFundModal = ref(false);
const fundAccount = ref<any>(null);
const fundType = ref<"deposit" | "withdraw">("deposit");
const fundAmount = ref<number | null>(null);
const fundSubmitting = ref(false);

function openFundModal(account: any, type: "deposit" | "withdraw") {
  fundAccount.value = account;
  fundType.value = type;
  fundAmount.value = null;
  showFundModal.value = true;
}

async function handleFundSubmit() {
  if (!fundAccount.value || !fundAmount.value || fundAmount.value <= 0) {
    message.warning("请输入有效金额");
    return;
  }
  const id = String(fundAccount.value.id);
  const url =
    fundType.value === "deposit"
      ? `/quantTrade/account/${id}/deposit`
      : `/quantTrade/account/${id}/withdraw`;
  fundSubmitting.value = true;
  try {
    await request.post(url, { amount: fundAmount.value });
    message.success(fundType.value === "deposit" ? "入金成功" : "出金成功");
    showFundModal.value = false;
    await loadAllData();
  } catch (e: any) {
    message.error(
      e?.response?.data?.detail ||
        (fundType.value === "deposit" ? "入金失败" : "出金失败"),
    );
  } finally {
    fundSubmitting.value = false;
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
              <span class="summary-label"
                >当日盈亏<template v-if="accountStats.pnlDate"
                  >（{{ accountStats.pnlDate.slice(5) }}）</template
                ></span
              >
              <span class="summary-value" :class="accountStats.pnl >= 0 ? 'text-up' : 'text-down'">
                {{ accountStats.pnl >= 0 ? '+' : '' }}¥{{ accountStats.pnl.toLocaleString() }}
                <small>({{ accountStats.pnlRate >= 0 ? '+' : '' }}{{ (accountStats.pnlRate * 100).toFixed(2) }}%)</small>
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
                    :class="{ 'signal-rejected': signalStatus(s) === 'rejected' }"
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
                        <span
                          class="signal-code"
                          @click.stop="router.push(`/market/stock/${s.ts_code}`)"
                        >{{ s.ts_code }}</span>
                        <span v-if="s.name || s.symbolName" class="signal-name">{{ s.name || s.symbolName }}</span>
                        <n-tag :type="statusTag(signalStatus(s)).type" size="tiny" :bordered="false">
                          {{ statusTag(signalStatus(s)).text }}
                        </n-tag>
                      </div>
                      <div class="signal-mid-row">
                        <span v-if="s.price" class="signal-price">¥{{ s.price }}</span>
                        <span v-if="s.quantity" class="signal-qty">×{{ s.quantity }}股</span>
                        <span v-if="s.strength != null" class="signal-strength" :class="s.strength >= 0.7 ? 'text-up' : 'text-secondary'">
                          强度 {{ (s.strength * 100).toFixed(0) }}%
                        </span>
                      </div>
                      <div v-if="s.reason" class="signal-reason">{{ formatRejectReason(s.reason) }}</div>
                    </div>
                    <div class="signal-actions">
                      <template v-if="signalStatus(s) === 'pending'">
                        <n-button
                          size="tiny" type="success" :loading="signalReviewing.has(s.signal_id || s.id)"
                          @click.stop="handleReviewSignal(s.signal_id || s.id, 'approved')"
                        >采纳</n-button>
                        <n-button
                          size="tiny" type="error" :loading="signalReviewing.has(s.signal_id || s.id)"
                          @click.stop="handleReviewSignal(s.signal_id || s.id, 'rejected')"
                        >拒绝</n-button>
                      </template>
                      <template v-else-if="signalStatus(s) === 'approved'">
                        <n-tag type="success" size="small" :bordered="false">已采纳 ✓</n-tag>
                        <n-button size="tiny" type="primary" @click.stop="handleRecordFromSignal(s)">录入成交</n-button>
                      </template>
                      <template v-else-if="signalStatus(s) === 'executed'">
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
                  <n-button size="small" type="primary" @click="openRoundTrips">
                    平仓配对
                  </n-button>
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
    <n-modal v-model:show="showAccountModal" preset="card" :title="editingAccountId ? '编辑账户' : '新增账户'" style="width: 460px">
      <n-form :model="accountForm" label-placement="left" label-width="100px">
        <n-form-item label="账户名称">
          <n-input v-model:value="accountForm.account_name" placeholder="如：华泰实盘账户" />
        </n-form-item>
        <n-form-item label="账户类型">
          <n-select v-model:value="accountForm.account_type" :options="[
            { label: '现金账户（实盘）', value: 'cash' },
            { label: '信用账户（两融）', value: 'margin' },
          ]" />
        </n-form-item>
        <n-form-item label="券商">
          <n-input v-model:value="accountForm.broker" placeholder="如：华泰证券、中信证券" />
        </n-form-item>
        <n-form-item label="券商账号">
          <n-input v-model:value="accountForm.broker_account_id" placeholder="券商端账户号/客户号" />
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

    <!-- 入金 / 出金 Modal -->
    <n-modal
      v-model:show="showFundModal"
      preset="card"
      :title="fundType === 'deposit' ? '账户入金' : '账户出金'"
      style="width: 380px"
      :mask-closable="false"
    >
      <n-form label-placement="left" label-width="80px">
        <n-form-item :label="fundType === 'deposit' ? '入金金额' : '出金金额'">
          <n-input-number
            v-model:value="fundAmount"
            :min="0.01"
            :precision="2"
            style="width: 100%"
            placeholder="输入金额（元）"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showFundModal = false">取消</n-button>
          <n-button
            type="primary"
            :loading="fundSubmitting"
            @click="handleFundSubmit"
          >
            确认
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Trade Record Modal -->
    <TradeRecordModal
      v-model="showRecordModal"
      :prefilled="recordPrefill"
      @submitted="handleRecordSubmitted"
    />

    <!-- 买卖 FIFO 配对追溯 Modal -->
    <n-modal
      v-model:show="showRoundTripModal"
      preset="card"
      title="买卖配对追溯（FIFO）"
      style="width: 720px; max-width: 92vw"
    >
      <n-spin :show="roundTripLoading">
        <div v-if="roundTripSummary" class="rt-summary">
          <span class="rt-summary-item">
            已实现盈亏
            <b :class="roundTripSummary.total_realized_pnl >= 0 ? 'text-up' : 'text-down'">
              ¥{{ roundTripSummary.total_realized_pnl.toLocaleString() }}
            </b>
          </span>
          <span class="rt-summary-item">平仓 <b>{{ roundTripSummary.closed_count }}</b> 笔</span>
          <span class="rt-summary-item">未平仓 <b>{{ roundTripSummary.open_count }}</b> 只</span>
        </div>

        <n-empty
          v-if="!roundTripLoading && roundTripStocks.length === 0"
          description="暂无成交配对数据"
        />

        <div v-for="st in roundTripStocks" :key="st.ts_code" class="rt-stock">
          <div class="rt-stock-head">
            <span class="rt-code">{{ st.ts_code }}</span>
            <span class="rt-pnl" :class="st.realized_pnl >= 0 ? 'text-up' : 'text-down'">
              累计 ¥{{ st.realized_pnl.toFixed(2) }}
            </span>
          </div>

          <!-- 平仓明细 -->
          <div v-for="(c, ci) in st.closed" :key="ci" class="rt-closed">
            <div class="rt-sell-line">
              卖出 {{ c.sell_volume }} 股 @ ¥{{ c.sell_price }}
              <span class="rt-sell-pnl" :class="c.total_realized_pnl >= 0 ? 'text-up' : 'text-down'">
                {{ c.total_realized_pnl >= 0 ? "+" : "" }}¥{{ c.total_realized_pnl.toFixed(2) }}
              </span>
            </div>
            <div v-for="(m, mi) in c.matched_buys" :key="mi" class="rt-buy-line">
              ← 买入 {{ m.matched_volume }} 股 @ ¥{{ m.buy_price }}（持有 {{ m.holding_days }} 天）
              <span class="rt-buy-pnl" :class="m.realized_pnl >= 0 ? 'text-up' : 'text-down'">
                {{ m.realized_pnl >= 0 ? "+" : "" }}¥{{ m.realized_pnl.toFixed(2) }}
              </span>
            </div>
          </div>

          <!-- 未平仓 -->
          <div v-if="st.open && st.open.remaining_volume > 0" class="rt-open">
            持仓 {{ st.open.remaining_volume }} 股，成本 ¥{{ st.open.cost_price.toFixed(4) }}
          </div>
        </div>
      </n-spin>
    </n-modal>

    <!-- 拒绝原因选择 -->
    <n-modal
      v-model:show="showRejectDialog"
      preset="dialog"
      title="选择拒绝原因"
      positive-text="确认拒绝"
      negative-text="取消"
      @positive-click="confirmReject"
    >
      <n-radio-group v-model:value="selectedRejectReason">
        <n-space vertical>
          <n-radio v-for="r in SIGNAL_REJECT_REASONS" :key="r.value" :value="r.value">
            {{ r.label }}
          </n-radio>
        </n-space>
      </n-radio-group>
    </n-modal>
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
  cursor: pointer;
  transition: color 0.15s;
  &:hover {
    color: var(--n-color-primary);
  }
}
.signal-name {
  font-size: 12px;
  color: var(--n-text-color-3);
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

// ---- 买卖配对追溯 Modal ----
.rt-summary {
  display: flex;
  gap: 24px;
  padding: 10px 14px;
  margin-bottom: 14px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: var(--n-border-radius);
  .rt-summary-item {
    font-size: 13px;
    color: var(--n-text-color-2);
    b {
      margin-left: 4px;
      font-size: 14px;
      color: var(--n-text-color-1);
    }
  }
}
.rt-stock {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--n-border-color);
  border-radius: var(--n-border-radius);
  background: rgba(255, 255, 255, 0.02);
}
.rt-stock-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  .rt-code {
    font-weight: 600;
    font-size: 14px;
    color: var(--n-text-color-1);
    font-family: monospace;
  }
  .rt-pnl {
    font-size: 13px;
    font-weight: 600;
  }
}
.rt-closed {
  padding: 6px 0 6px 8px;
  border-left: 2px solid var(--n-color-target);
  margin-bottom: 6px;
}
.rt-sell-line {
  font-size: 13px;
  color: var(--n-text-color-1);
  display: flex;
  justify-content: space-between;
  .rt-sell-pnl {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
}
.rt-buy-line {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-top: 2px;
  display: flex;
  justify-content: space-between;
  .rt-buy-pnl {
    font-variant-numeric: tabular-nums;
  }
}
.rt-open {
  margin-top: 6px;
  font-size: 12px;
  color: var(--n-text-color-2);
}
</style>
