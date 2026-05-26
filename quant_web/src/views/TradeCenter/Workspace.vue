<script setup lang="ts">
import { ref, computed, onMounted, watch, h } from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  NTabs, NTabPane, NCard, NDataTable, NButton, NTag,
  NSpin, NResult, NEmpty, NModal, NForm, NFormItem,
  NInput, NSelect, NProgress, NPopconfirm, useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import AccountBar from "@/components/trade/AccountBar.vue";
import StockContextPanel from "@/components/trade/StockContextPanel.vue";
import type { Account, Order, Position, Basket } from "@/types";

const router = useRouter();
const route = useRoute();
const message = useMessage();

// ============================================================
// State
// ============================================================
const activeTab = ref((route.query.tab as string) || "positions");

// Sync activeTab to URL query param
watch(activeTab, (tab) => {
  if (route.query.tab !== tab) {
    router.replace({ query: { tab } }).catch(() => {});
  }
});
const loading = ref(false);
const error = ref(false);

// Selected stock context (shared across tabs)
const selectedStock = ref<{
  tsCode: string;
  name: string;
  price: number | null;
  changePercent: number | null;
} | null>(null);
const contextLoading = ref(false);

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

// ============================================================
// Mock data loader
// ============================================================
const loadAllData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 400));

    accounts.value = [
      { id: 1, account_name: "主交易账户", broker: "华泰证券", account_number: "1234567890", total_asset: 1500000, available_cash: 500000, market_value: 1000000, status: "active", created_at: "2024-01-01" } as Account,
      { id: 2, account_name: "测试账户", broker: "广发证券", account_number: "0987654321", total_asset: 100000, available_cash: 100000, market_value: 0, status: "active", created_at: "2024-01-02" } as Account,
    ];
    selectedAccountId.value = "1";

    positions.value = [
      { id: 1, ts_code: "600519.SH", name: "贵州茅台", volume: 100, available_volume: 100, cost_price: 1750.0, current_price: 1850.5, market_value: 185050, profit_loss: 10050, profit_loss_ratio: 5.74, last_update: "2024-01-15 15:00:00" } as Position,
      { id: 2, ts_code: "000858.SZ", name: "五粮液", volume: 500, available_volume: 500, cost_price: 148.0, current_price: 152.3, market_value: 76150, profit_loss: 2150, profit_loss_ratio: 2.91, last_update: "2024-01-15 15:00:00" } as Position,
      { id: 3, ts_code: "600036.SH", name: "招商银行", volume: 1000, available_volume: 1000, cost_price: 38.5, current_price: 40.12, market_value: 40120, profit_loss: 1620, profit_loss_ratio: 4.21, last_update: "2024-01-15 15:00:00" } as Position,
    ];

    orders.value = [
      { order_id: "O001", strategy_id: "ma_cross", ts_code: "600519.SH", order_type: "limit", direction: "buy", price: 1850.0, volume: 100, status: "filled", submitted_at: "2024-01-15 14:30:00", filled_volume: 100, filled_amount: 185000 } as Order,
      { order_id: "O002", ts_code: "000858.SZ", order_type: "market", direction: "sell", price: 0, volume: 200, status: "filled", submitted_at: "2024-01-15 10:15:00", filled_volume: 200, filled_amount: 31000 } as Order,
      { order_id: "O003", ts_code: "600036.SH", order_type: "limit", direction: "buy", price: 38.0, volume: 500, status: "partial_filled", submitted_at: "2024-01-15 09:45:00", filled_volume: 200, filled_amount: 7600 } as Order,
      { order_id: "O004", ts_code: "600519.SH", order_type: "limit", direction: "buy", price: 1840.0, volume: 50, status: "submitted", submitted_at: "2024-01-15 15:00:00" } as Order,
      { order_id: "O005", ts_code: "002415.SZ", order_type: "market", direction: "buy", price: 0, volume: 300, status: "cancelled", submitted_at: "2024-01-15 11:00:00" } as Order,
    ];

    baskets.value = [
      { id: "b1", name: "消费龙头", description: "白酒+家电核心标的", items: [{ ts_code: "600519.SH", weight: 0.25 }, { ts_code: "000858.SZ", weight: 0.20 }, { ts_code: "000333.SZ", weight: 0.15 }, { ts_code: "600887.SH", weight: 0.15 }, { ts_code: "002415.SZ", weight: 0.25 }], created_at: "2024-01-10", items_count: 5 } as unknown as Basket,
      { id: "b2", name: "新能源", description: "光伏+锂电+储能", items: [{ ts_code: "300750.SZ", weight: 0.20 }, { ts_code: "601012.SH", weight: 0.15 }, { ts_code: "002594.SZ", weight: 0.15 }, { ts_code: "300274.SZ", weight: 0.10 }, { ts_code: "688599.SH", weight: 0.10 }, { ts_code: "002129.SZ", weight: 0.10 }, { ts_code: "300014.SZ", weight: 0.10 }, { ts_code: "600438.SH", weight: 0.10 }], created_at: "2024-01-08", items_count: 8 } as unknown as Basket,
      { id: "b3", name: "银行高股息", description: "国有大行+股份行", items: [{ ts_code: "600036.SH", weight: 0.30 }, { ts_code: "601398.SH", weight: 0.25 }, { ts_code: "601939.SH", weight: 0.25 }, { ts_code: "600016.SH", weight: 0.20 }], created_at: "2024-01-05", items_count: 4 } as unknown as Basket,
    ];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

// ============================================================
// Cross-entity helpers — 篮子与持仓关联
// ============================================================
const getPositionByTsCode = (tsCode: string): Position | undefined =>
  positions.value.find((p) => p.ts_code === tsCode);

const getBasketHoldStats = (basket: Basket) => {
  const items = (basket as any).items as { ts_code: string; weight: number }[] | undefined;
  if (!items || items.length === 0) return { held: 0, total: 0 };
  const held = items.filter((item) => getPositionByTsCode(item.ts_code)).length;
  return { held, total: items.length };
};

const getBasketsForStock = (tsCode: string): Basket[] =>
  baskets.value.filter((b) => {
    const items = (b as any).items as { ts_code: string }[] | undefined;
    return items?.some((item) => item.ts_code === tsCode);
  });

const getOrdersForStock = (tsCode: string): Order[] =>
  orders.value.filter((o) => o.ts_code === tsCode);

// ============================================================
// Stock selection — 点击股票时更新右侧面板
// ============================================================
const handleSelectStock = async (tsCode: string, name: string) => {
  contextLoading.value = true;
  selectedStock.value = { tsCode, name, price: null, changePercent: null };
  // Simulate fetching real-time data
  await new Promise((r) => setTimeout(r, 200));
  const pos = getPositionByTsCode(tsCode);
  selectedStock.value = {
    tsCode,
    name,
    price: pos?.current_price ?? null,
    changePercent: pos ? pos.profit_loss_ratio : 0,
  };
  contextLoading.value = false;
};

// Selected stock computed properties
const selectedPosition = computed(() =>
  selectedStock.value ? getPositionByTsCode(selectedStock.value.tsCode) ?? null : null
);
const selectedRelatedOrders = computed(() =>
  selectedStock.value ? getOrdersForStock(selectedStock.value.tsCode) : []
);
const selectedRelatedBaskets = computed(() =>
  selectedStock.value ? getBasketsForStock(selectedStock.value.tsCode) : []
);

// ============================================================
// Tab: 篮子 columns & actions
// ============================================================
const basketColumns: DataTableColumns<Basket> = [
  {
    title: "篮子名称", key: "name", width: 160,
    render: (row) => h("span", { style: { fontWeight: 600 } }, row.name),
  },
  {
    title: "描述", key: "description", ellipsis: { tooltip: true },
  },
  {
    title: "持仓覆盖", key: "holdStatus", width: 180,
    render: (row) => {
      const { held, total } = getBasketHoldStats(row);
      const pct = total > 0 ? Math.round((held / total) * 100) : 0;
      return h("div", { style: { display: "flex", alignItems: "center", gap: "8px" } }, [
        h(NProgress, {
          percentage: pct,
          color: pct > 50 ? "#10B981" : pct > 0 ? "#F59E0B" : "#6B7280",
          indicatorTextColor: "#999",
          height: 6,
          borderRadius: 3,
          style: { width: "120px" },
        }),
        h("span", { style: { fontSize: "12px", color: "var(--n-text-color-3)" } }, `${held}/${total}`),
      ]);
    },
  },
  {
    title: "成分股", key: "items_count", width: 80,
    render: (row) => `${(row as any).items_count ?? (row as any).items?.length ?? 0} 只`,
  },
  {
    title: "操作", key: "actions", width: 200,
    render: (row) =>
      h("div", { style: { display: "flex", gap: "6px" } }, [
        h(NButton, { size: "small", onClick: () => router.push(`/baskets/detail/${row.id}`) }, { default: () => "详情" }),
        h(NButton, { size: "small", type: "primary", onClick: () => message.info(`一键下单: ${row.name}`) }, { default: () => "下单" }),
      ]),
  },
];

// ============================================================
// Tab: 订单 columns
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
  {
    title: "时间", key: "submitted_at", width: 160,
    render: (row) => row.submitted_at?.slice(0, 16),
  },
  {
    title: "代码", key: "ts_code", width: 110,
    render: (row) =>
      h("span", {
        class: "clickable-stock",
        style: { color: "var(--n-color-primary)", cursor: "pointer" },
        onClick: () => handleSelectStock(row.ts_code, row.ts_code),
      }, row.ts_code),
  },
  {
    title: "方向", key: "direction", width: 60,
    render: (row) =>
      h(NTag, { type: row.direction === "buy" ? "success" : "error", size: "small", bordered: false },
        { default: () => (row.direction === "buy" ? "买入" : "卖出") }),
  },
  { title: "价格", key: "price", width: 100, render: (row) => row.price > 0 ? `¥${row.price.toFixed(2)}` : "市价" },
  { title: "数量", key: "volume", width: 80, render: (row) => row.volume.toLocaleString() },
  {
    title: "状态", key: "status", width: 80,
    render: (row) => h(NTag, { type: statusMap[row.status]?.type || "default", size: "small", bordered: false },
      { default: () => statusMap[row.status]?.text }),
  },
  {
    title: "操作", key: "actions", width: 80,
    render: (row) =>
      row.status === "submitted" || row.status === "partial_filled"
        ? h(NPopconfirm, { onPositiveClick: () => message.success(`撤单: ${row.order_id}`) },
          { trigger: () => h(NButton, { size: "tiny", type: "error" }, { default: () => "撤单" }),
            default: () => "确认撤单？" })
        : h("span", { style: { color: "var(--n-text-color-3)", fontSize: "12px" } }, "--"),
  },
];

// ============================================================
// Tab: 持仓 columns
// ============================================================
const positionColumns: DataTableColumns<Position> = [
  {
    title: "代码", key: "ts_code", width: 110,
    render: (row) =>
      h("span", {
        class: "clickable-stock",
        style: { color: "var(--n-color-primary)", cursor: "pointer" },
        onClick: () => handleSelectStock(row.ts_code, row.name),
      }, row.ts_code),
  },
  {
    title: "名称", key: "name", width: 120,
    render: (row) =>
      h("span", {
        class: "clickable-stock",
        style: { cursor: "pointer" },
        onClick: () => handleSelectStock(row.ts_code, row.name),
      }, row.name),
  },
  { title: "持仓量", key: "volume", width: 90, render: (row: Position) => row.volume.toLocaleString() },
  { title: "可用", key: "available_volume", width: 80, render: (row: Position) => row.available_volume.toLocaleString() },
  { title: "成本价", key: "cost_price", width: 95, render: (row: Position) => `¥${row.cost_price.toFixed(2)}` },
  { title: "当前价", key: "current_price", width: 95, render: (row: Position) => `¥${row.current_price.toFixed(2)}` },
  { title: "市值", key: "market_value", width: 110, render: (row: Position) => `¥${row.market_value.toLocaleString()}` },
  {
    title: "盈亏", key: "profit_loss", width: 110,
    render: (row) =>
      h("span", { class: (row.profit_loss ?? 0) >= 0 ? "text-up" : "text-down" },
        `¥${(row.profit_loss ?? 0).toLocaleString()}`),
  },
  {
    title: "盈亏比", key: "profit_loss_ratio", width: 85,
    render: (row) =>
      h("span", { class: (row.profit_loss_ratio ?? 0) >= 0 ? "text-up" : "text-down" },
        `${(row.profit_loss_ratio ?? 0).toFixed(2)}%`),
  },
  {
    title: "操作", key: "actions", width: 140,
    render: (row) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(NButton, { size: "tiny", onClick: () => message.info(`平仓: ${row.name}`) }, { default: () => "平仓" }),
        h(NButton, { size: "tiny", type: "primary", onClick: () => message.info(`加仓: ${row.name}`) }, { default: () => "加仓" }),
      ]),
  },
];

// ============================================================
// Quick trade handler
// ============================================================
const handleQuickTrade = (direction: "buy" | "sell") => {
  const s = selectedStock.value;
  if (!s) return;
  router.push({ path: "/trade", query: { symbol: s.tsCode, side: direction } });
};

// ============================================================
// Account tab — reused from AccountManagement
// ============================================================
const dialogVisible = ref(false);
const editingAccount = ref<Account | null>(null);
const accountForm = ref({ account_name: "", broker: "ht", account_number: "", status: "active" });

const brokerMap: Record<string, string> = { ht: "华泰证券", gf: "广发证券", zs: "招商证券", zx: "中信证券" };
const brokerOptions = Object.entries(brokerMap).map(([v, l]) => ({ label: l, value: v }));
const statusOpts = [{ label: "活跃", value: "active" }, { label: "禁用", value: "inactive" }];

const accountColumns: DataTableColumns<Account> = [
  { title: "账户名称", key: "account_name", width: 150 },
  { title: "券商", key: "broker", width: 110, render: (row) => brokerMap[row.broker] || row.broker },
  { title: "账户号码", key: "account_number", width: 150 },
  { title: "总资产", key: "total_asset", width: 120, render: (row) => `¥${row.total_asset.toLocaleString()}` },
  { title: "可用资金", key: "available_cash", width: 120, render: (row) => `¥${row.available_cash.toLocaleString()}` },
  { title: "持仓市值", key: "market_value", width: 120, render: (row) => `¥${row.market_value.toLocaleString()}` },
  {
    title: "状态", key: "status", width: 80,
    render: (row) => h(NTag, { type: row.status === "active" ? "success" : "default", size: "small", bordered: false },
      { default: () => (row.status === "active" ? "活跃" : "禁用") }),
  },
  {
    title: "操作", key: "actions", width: 180,
    render: (row) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(NButton, { size: "tiny", onClick: () => { editingAccount.value = row; accountForm.value = { ...row } as any; dialogVisible.value = true; } }, { default: () => "编辑" }),
        h(NButton, { size: "tiny", type: "error", onClick: () => { accounts.value = accounts.value.filter((a) => a.id !== row.id); message.success("删除成功"); } }, { default: () => "删除" }),
      ]),
  },
];

const saveAccount = () => {
  if (editingAccount.value) {
    const idx = accounts.value.findIndex((a) => a.id === editingAccount.value!.id);
    if (idx !== -1) accounts.value[idx] = { ...editingAccount.value, ...accountForm.value };
  } else {
    accounts.value.push({ id: Date.now(), ...accountForm.value, total_asset: 0, available_cash: 0, market_value: 0 } as Account);
  }
  dialogVisible.value = false;
  message.success(editingAccount.value ? "账户已更新" : "账户已创建");
};

const handleAddAccount = () => {
  editingAccount.value = null;
  accountForm.value = { account_name: "", broker: "ht", account_number: "", status: "active" };
  dialogVisible.value = true;
};

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
          <h1 class="page-title">交易工作台</h1>
        </div>
        <div class="header-actions">
          <n-button size="small" text class="cockpit-btn" @click="router.push('/trade')">
            <template #icon><SmartIcon name="Rocket" /></template>
            驾驶舱
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
    <!-- ========== Top Account Bar ========== -->
    <AccountBar
      :accounts="accounts"
      :selected-account-id="selectedAccountId"
      @select-account="(id: string) => selectedAccountId = id"
    >
      <template #actions>
        <n-button size="small" text @click="router.push('/trade/execution')">
          执行分析
        </n-button>
        <n-button size="small" text @click="router.push('/performance/account')">
          账户绩效
        </n-button>
      </template>
    </AccountBar>

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

    <!-- ========== Main Two-Column Layout ========== -->
    <div v-else class="workspace-layout">
      <!-- ===== Left Panel: Tabs ===== -->
      <div class="left-panel">
        <n-tabs v-model:value="activeTab" type="line" size="small">
          <!-- Tab 1: 篮子 -->
          <n-tab-pane name="baskets" tab="篮子">
            <n-spin :show="loading">
              <div class="basket-actions">
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

          <!-- Tab 2: 订单 -->
          <n-tab-pane name="orders" tab="订单">
            <n-spin :show="loading">
              <div class="tab-toolbar">
                <n-select
                  v-model:value="orderFilter"
                  :options="orderFilterOptions"
                  size="small"
                  style="width: 120px"
                />
              </div>
              <n-data-table
                v-if="filteredOrders.length > 0"
                :columns="orderColumns"
                :data="filteredOrders"
                :bordered="false"
                size="small"
                :row-key="(row: Order) => row.order_id"
              />
              <n-empty v-else description="暂无订单数据" />
            </n-spin>
          </n-tab-pane>

          <!-- Tab 3: 持仓 -->
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
              <n-empty v-else description="暂无持仓" />
            </n-spin>
          </n-tab-pane>

          <!-- Tab 4: 账户 -->
          <n-tab-pane name="account" tab="账户">
            <n-spin :show="loading">
              <div class="tab-toolbar">
                <n-button type="primary" size="small" @click="handleAddAccount">新增账户</n-button>
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
          @trade="handleQuickTrade"
          @add-to-basket="message.info('请从篮子管理中选择目标篮子')"
        />
      </div>
    </div>

    <!-- Account Edit Modal -->
    <n-modal
      v-model:show="dialogVisible"
      preset="dialog"
      :title="editingAccount ? '编辑账户' : '新增账户'"
      positive-text="保存"
      negative-text="取消"
      @positive-click="saveAccount"
    >
      <n-form :model="accountForm" label-width="100px">
        <n-form-item label="账户名称">
          <n-input v-model:value="accountForm.account_name" />
        </n-form-item>
        <n-form-item label="券商">
          <n-select v-model:value="accountForm.broker" :options="brokerOptions" />
        </n-form-item>
        <n-form-item label="账户号码">
          <n-input v-model:value="accountForm.account_number" />
        </n-form-item>
        <n-form-item label="状态">
          <n-select v-model:value="accountForm.status" :options="statusOpts" />
        </n-form-item>
      </n-form>
    </n-modal>
    </div>
  </div>
</template>

<style scoped>
.trading-workspace {
  padding: 0;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.workspace-layout {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
  overflow: hidden;
}

/* ---- Left Panel ---- */
.left-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.left-panel :deep(.n-tabs) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.left-panel :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow-y: auto;
}

/* ---- Right Panel (slide-out) ---- */
.right-panel {
  width: 0;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.02);
  border: none;
  border-radius: 8px;
  padding: 0;
  overflow: hidden;
  height: 100%;
  transition: width 0.3s ease, padding 0.3s ease, border 0.3s ease;
}
.right-panel.panel-open {
  width: 380px;
  padding: 16px;
  border: 1px solid rgba(68, 138, 255, 0.08);
  overflow-y: auto;
}

.context-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.context-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1, rgba(255, 255, 255, 0.9));
}

.cockpit-btn {
  padding: 0 12px;
}

/* ---- Toolbar ---- */
.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.basket-actions {
  margin-bottom: 12px;
}

/* ---- Utility ---- */
.text-up {
  color: var(--color-stock-up, #10B981);
  font-weight: 500;
}

.text-down {
  color: var(--color-stock-down, #EF4444);
  font-weight: 500;
}

.clickable-stock:hover {
  text-decoration: underline;
}
</style>
