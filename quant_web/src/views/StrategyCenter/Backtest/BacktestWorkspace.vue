<!-- BacktestWorkspace.vue — 独立回测工作台：策略卡片选择 + 股票/篮子双模式 + 多策略对比 -->
<template>
  <div class="backtest-workspace bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">回测工作台</h1>
          <p class="page-description">选择策略和股票池后执行回测，对比不同策略的表现</p>
        </div>
        <div class="header-actions">
          <n-button size="small" @click="exportCSV" :disabled="!hasResults">导出CSV</n-button>
          <n-button size="small" v-if="activeCompareTaskId" @click="exportViaApi" :disabled="!activeCompareTaskId">导出报告</n-button>
          <n-button size="small" type="primary" :loading="isRunning" @click="runBacktestAll">
            {{ isRunning ? `回测中 ${progress}%` : '▶ 开始回测' }}
          </n-button>
        </div>
      </div>
    </div>

    <div class="workspace-body">
      <!-- ========== 左侧配置面板 ========== -->
      <div class="config-pane">
        <n-collapse :default-expanded-names="['strategies', 'params']">
          <!-- 策略选择 -->
          <n-collapse-item name="strategies" title="选择策略">
            <template #header-extra>
              <span class="collapse-extra">{{ selectedStrategyIds.length }}/{{ filteredStrategyOptions.length }}</span>
            </template>
            <n-radio-group v-model:value="strategyStatusFilter" size="small" style="margin-bottom:6px;display:flex">
              <n-radio-button value="all">全部</n-radio-button>
              <n-radio-button value="draft">草稿</n-radio-button>
              <n-radio-button value="running">运行中</n-radio-button>
              <n-radio-button value="stopped">已停止</n-radio-button>
            </n-radio-group>
            <n-input v-model:value="strategySearch" size="tiny" placeholder="搜索..." clearable style="margin-bottom:6px" />
            <div class="strategy-card-list" v-if="filteredStrategyOptions.length > 0">
              <div v-for="s in filteredStrategyOptions" :key="s.value" :class="['strategy-chip', { selected: selectedStrategyIds.includes(s.value) }]" @click="toggleStrategy(s.value)">
                <span class="chip-check">{{ selectedStrategyIds.includes(s.value) ? '☑' : '☐' }}</span>
                <span class="chip-name">{{ s.label }}</span>
                <n-tag :type="s.status === 'running' ? 'success' : 'default'" size="tiny">{{ s.statusText }}</n-tag>
              </div>
            </div>
            <n-empty v-else description="暂无策略，请先创建" size="small" style="padding:8px 0" />
          </n-collapse-item>

          <!-- 股票池 / 篮子 -->
          <n-collapse-item name="stocks" title="股票池">
            <template #header-extra>
              <span class="collapse-extra">{{ stockMode === 'stocks' ? stockPool.length + '只' : selectedBasketIds.length + '个篮子' }}</span>
            </template>
            <n-radio-group v-model:value="stockMode" size="small" style="margin-bottom:6px">
              <n-radio-button value="stocks">股票</n-radio-button>
              <n-radio-button value="baskets">篮子</n-radio-button>
            </n-radio-group>
            <template v-if="stockMode === 'stocks'">
              <n-input v-model:value="stockSearch" size="tiny" placeholder="搜索..." clearable style="margin-bottom:4px" />
              <div class="chip-grid">
                <div v-for="s in filteredStockOptions" :key="s.value" :class="['mini-chip', { selected: stockPool.includes(s.value) }]" @click="toggleStock(s.value)">{{ s.label.split(' ')[0] }}</div>
              </div>
            </template>
            <template v-else>
              <div class="basket-list" v-if="basketOptions.length > 0">
                <div v-for="b in basketOptions" :key="b.value" :class="['strategy-chip', { selected: selectedBasketIds.includes(b.value) }]" @click="toggleBasket(b.value)">
                  <span class="chip-check">{{ selectedBasketIds.includes(b.value) ? '☑' : '☐' }}</span>
                  <span class="chip-name">{{ b.label }}</span>
                  <span class="chip-count">{{ b.stockCount || 0 }}只</span>
                </div>
              </div>
              <n-empty v-else description="暂无篮子" size="small" style="padding:8px 0" />
            </template>
          </n-collapse-item>

          <!-- 回测参数 -->
          <n-collapse-item name="params" title="回测参数">
            <div class="date-presets">
              <n-button size="tiny" :type="datePreset === '1y' ? 'primary' : 'default'" @click="setDatePreset('1y')">1年</n-button>
              <n-button size="tiny" :type="datePreset === '3y' ? 'primary' : 'default'" @click="setDatePreset('3y')">3年</n-button>
              <n-button size="tiny" :type="datePreset === '5y' ? 'primary' : 'default'" @click="setDatePreset('5y')">5年</n-button>
              <n-button size="tiny" :type="datePreset === 'all' ? 'primary' : 'default'" @click="setDatePreset('all')">全部</n-button>
            </div>
            <div class="date-row">
              <n-date-picker v-model:value="dateRange" type="daterange" size="small" :input-readonly="false" style="flex:1;min-width:0" />
            </div>
            <div class="param-row">
              <n-input-number v-model:value="initialCapital" :min="10000" :step="100000" size="small" style="flex:1;min-width:0"><template #suffix>元</template></n-input-number>
            </div>
            <div class="param-row">
              <n-select v-model:value="benchmark" :options="benchmarkOptions" size="small" style="flex:1" placeholder="基准" />
            </div>
            <n-button type="primary" block @click="runBacktestAll" :loading="isRunning" class="run-btn">{{ isRunning ? `回测中 ${progress}%` : '▶ 开始回测' }}</n-button>
          </n-collapse-item>

          <!-- 任务列表 -->
          <n-collapse-item name="tasks" title="任务列表">
            <template #header-extra>
              <n-button size="tiny" text @click.stop="loadTaskList" :loading="taskListLoading">刷新</n-button>
            </template>
            <n-spin :show="taskListLoading" size="small">
              <n-empty v-if="!taskListLoading && taskList.length === 0" description="暂无任务" size="small" style="padding:8px 0" />
              <div v-else class="task-list">
                <div v-for="t in taskList" :key="t.task_id" class="task-row" @click="loadResultDetails(t.task_id)" :class="{ active: activeCompareTaskId === t.task_id }">
                  <div class="task-main"><span class="task-name">{{ t.name || t.task_id?.slice(0, 8) }}</span><n-tag :type="statusType(t.status)" size="tiny">{{ statusLabel(t.status) }}</n-tag></div>
                  <div class="task-meta">{{ t.created_at?.slice(0, 10) || '' }}</div>
                  <div class="task-actions" @click.stop>
                    <n-button v-if="t.status === 'running'" size="tiny" type="warning" text @click="cancelTask(t.task_id)" title="取消">✕</n-button>
                    <n-button size="tiny" type="error" text @click="deleteTaskItem(t.task_id)" title="删除">🗑</n-button>
                    <n-button size="tiny" type="primary" text @click="rerunTask(t)" title="重新回测">↻</n-button>
                  </div>
                </div>
              </div>
            </n-spin>
          </n-collapse-item>
        </n-collapse>
      </div>

      <!-- ========== 右侧结果面板 ========== -->
      <div class="result-pane">
        <n-card :class="tokens.surface.card" size="small">
          <n-spin :show="resultLoading">
            <n-empty v-if="!hasResults" description="选择策略和股票池后点击「开始回测」" style="padding:40px 0" />

            <template v-else>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <h4 style="margin:0">{{ activeTaskName || '回测结果' }}</h4>
                <n-space :size="6">
                  <n-select v-if="compareResults.length > 0" v-model:value="activeCompareTaskId" :options="compareSelectOptions" size="tiny" style="width:200px" />
                  <n-button v-if="activeTaskId" size="tiny" type="primary" @click="openReport(activeTaskId)">查看报告</n-button>
                </n-space>
              </div>

              <!-- 指标卡片行 -->
              <div class="metrics-row">
                <div class="metric-item">
                  <span class="metric-label">年化收益</span>
                  <span class="metric-value" :class="activeSummary.annualReturn >= 0 ? 'text-up' : 'text-down'">{{ (activeSummary.annualReturn * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">基准收益</span>
                  <span class="metric-value" :class="benchmarkReturn >= 0 ? 'text-up' : 'text-down'">{{ (benchmarkReturn * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">夏普比率</span>
                  <span class="metric-value">{{ activeSummary.sharpeRatio.toFixed(2) }}</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">最大回撤</span>
                  <span class="metric-value text-down">{{ (activeSummary.maxDrawdown * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">胜率</span>
                  <span class="metric-value">{{ (activeSummary.winRate * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">交易笔数</span>
                  <span class="metric-value">{{ activeSummary.tradesCount }}</span>
                </div>
              </div>
              <!-- 口径标注（2026-08 C4：绩效口径统一） -->
              <div class="metric-footnote">
                口径：夏普 = 日频超额收益 × √252（无风险利率 2%）；年化 = 252 交易日几何复合；最大回撤以负值表示（-15% = 回撤 15%）
              </div>

              <div class="chart-section"><BacktestSubplots :equity="eqPct" :benchmark="bmPct" :dailyReturns="activeDailyReturns" :dailyTurnover="activeDailyTurnover" :drawdown="activeDrawdown" :height="720" /></div>

              <n-tabs v-model:value="activeTab" size="small" style="margin-top:12px">
                <n-tab-pane name="trades" tab="交易列表"><TradeTable :trades="activeTrades" /></n-tab-pane>
                <n-tab-pane name="monthly" tab="月度收益">
                  <MonthlyReturnChart v-if="activeMonthlyReturns.length > 0" :data="activeMonthlyReturns" />
                  <n-empty v-else description="暂无月度收益数据" />
                </n-tab-pane>
              </n-tabs>
            </template>
          </n-spin>
        </n-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { NCard, NSelect, NDatePicker, NInputNumber, NButton, NSpin, NEmpty, NTabs, NTabPane, NTag, NInput, NRadioGroup, NRadioButton, NCollapse, NCollapseItem, NSpace, useMessage } from "naive-ui";
import TradeTable from "@/components/data/TradeTable.vue";
import MonthlyReturnChart from "@/components/charts/MonthlyReturnChart.vue";
import BacktestSubplots from "@/components/charts/BacktestSubplots.vue";
import { tokens } from "@/styles/design-tokens";
import strategyAPI from "@/api/strategy";
import backtestAPI from "@/api/backtest";
import dataAPI from "@/api/data";
import basketAPI from "@/api/basket";
import { useBatchBacktestPolling } from "@/composables/useBacktestPolling";

const router = useRouter();
const route = useRoute();
const msg = useMessage();

// ---- 策略 ----
const strategySelectOptions = ref<Array<{ label: string; value: string; status: string; statusText: string }>>([]);
const selectedStrategyIds = ref<string[]>([]);
const strategySearch = ref("");
// 状态筛选（默认草稿——回测工作台主要对未实盘策略跑回测）
const strategyStatusFilter = ref<"all" | "draft" | "running" | "stopped">("draft");
const filteredStrategyOptions = computed(() => {
  let list = strategySelectOptions.value;
  if (strategyStatusFilter.value !== "all") {
    list = list.filter(s => s.status === strategyStatusFilter.value);
  }
  if (strategySearch.value) {
    const q = strategySearch.value.toLowerCase();
    list = list.filter(s => s.label.toLowerCase().includes(q));
  }
  return list;
});
const toggleStrategy = (id: string) => {
  if (selectedStrategyIds.value.includes(id)) selectedStrategyIds.value = selectedStrategyIds.value.filter(v => v !== id);
  else selectedStrategyIds.value.push(id);
};

// ---- 股票 / 篮子 ----
const stockMode = ref<"stocks" | "baskets">("stocks");
const stockSelectOptions = ref<Array<{ label: string; value: string }>>([]);
const stockPool = ref<string[]>([]);
const stockSearch = ref("");
const filteredStockOptions = computed(() => {
  if (!stockSearch.value) return stockSelectOptions.value.slice(0, 50);
  const q = stockSearch.value.toLowerCase();
  return stockSelectOptions.value.filter(s => s.label.toLowerCase().includes(q)).slice(0, 50);
});
const toggleStock = (code: string) => {
  if (stockPool.value.includes(code)) stockPool.value = stockPool.value.filter(v => v !== code);
  else stockPool.value.push(code);
};

// 篮子
const basketOptions = ref<Array<{ label: string; value: string; stockCount: number; stocks: string[] }>>([]);
const selectedBasketIds = ref<string[]>([]);
const toggleBasket = async (id: string) => {
  if (selectedBasketIds.value.includes(id)) {
    selectedBasketIds.value = selectedBasketIds.value.filter(v => v !== id);
  } else {
    selectedBasketIds.value.push(id);
    // 加载篮子成分股加入股票池
    const basket = basketOptions.value.find(b => b.value === id);
    if (basket && basket.stocks.length > 0) {
      for (const s of basket.stocks) {
        if (!stockPool.value.includes(s)) stockPool.value.push(s);
      }
    }
  }
};

// ---- 回测参数 ----
const dateRange = ref<[number, number]>([Date.now() - 365 * 86400000, Date.now()]);
const datePreset = ref<string>("1y");
const setDatePreset = (preset: string) => {
  datePreset.value = preset;
  const now = Date.now();
  const day = 86400000;
  const ranges: Record<string, [number, number]> = {
    "1y": [now - 365 * day, now],
    "3y": [now - 3 * 365 * day, now],
    "5y": [now - 5 * 365 * day, now],
    all: [new Date("2005-01-01").getTime(), now],
  };
  if (ranges[preset]) dateRange.value = ranges[preset];
};
const initialCapital = ref(1000000);
const benchmark = ref("000300.SH");
const benchmarkReturn = ref(0);
const benchmarkOptions = [
  { label: "沪深300 (000300.SH)", value: "000300.SH" },
  { label: "上证指数 (000001.SH)", value: "000001.SH" },
  { label: "深证成指 (399001.SZ)", value: "399001.SZ" },
  { label: "中证500 (000905.SH)", value: "000905.SH" },
  { label: "创业板指 (399006.SZ)", value: "399006.SZ" },
];

// ---- 状态 ----
const isRunning = ref(false);
const progress = ref(0);
const resultLoading = ref(false);
const hasResults = ref(false);
const activeTab = ref("trades");
const batchTaskIds = ref<string[]>([]);

// ---- 批量回测轮询（自适应间隔 + 容错） ----

const { start: startBatchPolling, stop: stopBatchPolling } = useBatchBacktestPolling(
  batchTaskIds,
  {
    fetchResult: async (taskId: string) => {
      return await backtestAPI.getResult(taskId).catch(() => null);
    },
    onAllDone: (doneResults) => {
      isRunning.value = false;
      progress.value = 100;
      const items: CompareItem[] = [];
      for (const { task, taskId, resultData } of doneResults) {
        if (task.status === "completed") {
          const r = resultData || {};
          items.push({
            name: task.name || task.strategy_name || taskId.slice(0, 8),
            taskId,
            annualReturn: r.annual_return || 0,
            sharpeRatio: r.sharpe_ratio || 0,
            maxDrawdown: r.max_drawdown || 0,
            winRate: r.win_rate || 0,
            tradesCount: r.num_trades || 0,
          });
        }
      }
      compareResults.value = items;
      hasResults.value = items.length > 0;
      if (items.length > 0) {
        activeCompareTaskId.value = items[0].taskId;
        loadResultDetails(items[0].taskId);
      }
      // 刷新任务列表
      loadTaskList();
    },
    onTimeout: () => {
      isRunning.value = false;
      progress.value = 100;
      msg.warning("部分回测任务超时未完成");
    },
  },
  { maxAttempts: 240 },
);

interface CompareItem { name: string; taskId: string; annualReturn: number; sharpeRatio: number; maxDrawdown: number; winRate: number; tradesCount: number; }
const compareResults = ref<CompareItem[]>([]);
const activeCompareTaskId = ref("");
const compareSelectOptions = computed(() => compareResults.value.map(r => ({ label: r.name, value: r.taskId })));
const activeEquityCurve = ref<any[]>([]);
const activeBenchmark = ref<any[]>([]);
const activeDrawdown = ref<any[]>([]);
const activeMonthlyReturns = ref<any[]>([]);
const activeDailyReturns = ref<any[]>([]);
const activeDailyTurnover = ref<any[]>([]);
const activeTrades = ref<any[]>([]);

const eqPct = computed(() => {
  if (!activeEquityCurve.value.length) return [];
  const base = activeEquityCurve.value[0]?.value || 1;
  return activeEquityCurve.value.map((p: any) => ({ date: p.date, value: (p.value / base - 1) * 100 }));
});
const bmPct = computed(() => {
  if (!activeBenchmark.value.length) return [];
  const base = activeBenchmark.value[0]?.value || 1;
  return activeBenchmark.value.map((p: any) => ({ date: p.date, value: (p.value / base - 1) * 100 }));
});

const activeTaskId = ref("");
const activeTaskName = ref("");
const activeSummary = ref({ annualReturn: 0, sharpeRatio: 0, maxDrawdown: 0, winRate: 0, tradesCount: 0 });

function openReport(taskId: string) {
  if (taskId) router.push(`/backtest/report/${taskId}`);
}

interface HistoryItem { id: string; label: string; time: string; taskIds: string[]; }
const historyList = ref<HistoryItem[]>([]);

// v1.3: 后端任务列表
interface TaskListItem { task_id: string; name?: string; strategy_id?: string; status: string; created_at?: string; updated_at?: string; config?: any; }
const taskList = ref<TaskListItem[]>([]);
const taskListLoading = ref(false);

const statusType = (s: string) => {
  const map: Record<string, any> = { running: 'info', completed: 'success', failed: 'error', cancelled: 'warning', pending: 'default' };
  return map[s] || 'default';
};
const statusLabel = (s: string) => {
  const map: Record<string, string> = { running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消', pending: '等待中' };
  return map[s] || s;
};

const loadTaskList = async () => {
  // v3.3: 检查 URL 是否带有 task 参数（从快速回测跳转来）
  const urlTaskId = route.query.task as string;
  if (urlTaskId && !scenarioTaskFromUrl.value) {
    scenarioTaskFromUrl.value = urlTaskId;
    // 自动加载该任务的结果
    setTimeout(async () => {
      try {
        const tr: any = await backtestAPI.getResult(urlTaskId);
        const r = tr?.data || tr;
        if (r) {
          activeTaskName.value = '快速回测';
          activeTaskId.value = urlTaskId;
          loadResultDetails(urlTaskId);
          hasResults.value = true;
        }
      } catch { }
    }, 2000);
  }
  taskListLoading.value = true;
  try {
    const res = await backtestAPI.getTasks({ page_size: 50 }) as any;
    // API returns { data: [], pagination: {...} } or array
    const items = Array.isArray(res) ? res : (res?.data || res?.items || []);
    taskList.value = items.map((t: any) => ({
      task_id: t.id || t.task_id,
      name: t.name,
      strategy_id: t.strategy_id,
      status: t.status,
      created_at: t.created_at,
      updated_at: t.updated_at,
      config: t.config,
    })).sort((a: any, b: any) => (b.created_at || '').localeCompare(a.created_at || ''));
  } catch { /* skip */ } finally { taskListLoading.value = false; }
};

const deleteTaskItem = async (taskId: string) => {
  try {
    await backtestAPI.deleteTask(taskId);
    msg.success('任务已删除');
    taskList.value = taskList.value.filter(t => t.task_id !== taskId);
  } catch { msg.error('删除失败'); }
};

const cancelTask = async (taskId: string) => {
  try {
    await backtestAPI.cancelTask(taskId);
    msg.success('已发送取消请求');
    const idx = taskList.value.findIndex(t => t.task_id === taskId);
    if (idx >= 0) taskList.value[idx].status = 'cancelled';
  } catch { msg.error('取消失败'); }
};

const rerunTask = async (task: TaskListItem) => {
  // 始终清空旧选择并用当前任务的策略替换，避免旧的多策略选择被误用于单策略回测
  selectedStrategyIds.value = task.strategy_id ? [task.strategy_id] : [];
  await runBacktestAll();
};

const loadOptions = async () => {
  const [strategies, stocks, baskets] = await Promise.all([
    strategyAPI.getStrategies().catch(() => []),
    dataAPI.getStockList().catch(() => []),
    basketAPI.getBaskets({ page_size: 100 } as any).then((r: any) => r?.baskets || []).catch(() => []),
  ]);

  if (Array.isArray(strategies)) {
    strategySelectOptions.value = strategies.map((s: any) => ({
      label: s.name || s.id, value: s.id || s.name,
      status: s.status || "draft",
      statusText: s.status === "running" ? "运行中" : s.status === "stopped" ? "已停止" : "草稿",
    }));
  }

  if (Array.isArray(stocks)) {
    stockSelectOptions.value = stocks.slice(0, 200).map((s: any) => ({
      label: `${s.ts_code || s.code || ""} ${s.name || ""}`,
      value: s.ts_code || s.code || "",
    }));
  }

  if (Array.isArray(baskets)) {
    basketOptions.value = baskets.map((b: any) => ({
      label: b.name || b.basket_name || b.id,
      value: b.id || b.basket_id,
      stockCount: b.stock_count || b.stocks?.length || 0,
      stocks: (b.stocks || b.components || b.items || []).map((s: any) =>
        typeof s === "string" ? s : s.ts_code || s.code || s.id
      ),
    }));
  }

  // URL query 预填
  const qStrategies = route.query.strategies as string;
  if (qStrategies) selectedStrategyIds.value = qStrategies.split(",").map(s => s.trim()).filter(Boolean);
  const qStock = route.query.stock as string;
  if (qStock) stockPool.value = qStock.split(",").map(s => s.trim()).filter(Boolean);
};

// ---- 回测执行 ----
const isComposite = computed(() => selectedStrategyIds.value.length >= 2);

const runBacktestAll = async () => {
  if (selectedStrategyIds.value.length === 0) { msg.warning("请选择至少一个策略"); return; }
  const effectiveStocks = stockPool.value.filter(Boolean);

  isRunning.value = true; progress.value = 0; compareResults.value = [];
  const start = new Date(dateRange.value[0]).toISOString().slice(0, 10);
  const end = new Date(dateRange.value[1]).toISOString().slice(0, 10);

  stopBatchPolling();

  const ids: string[] = [];

  // ≥2 个策略 → 组合回测（共享资金池 + CapitalAllocator）
  if (selectedStrategyIds.value.length >= 2) {
    try {
      const labels = selectedStrategyIds.value
        .map(sid => strategySelectOptions.value.find((s: any) => s.value === sid)?.label || sid)
        .join('+');
      const res = await backtestAPI.createCompositeTask({
        name: `组合_${labels}_${start}`,
        strategy_configs: selectedStrategyIds.value.map(sid => ({ strategy_id: sid })),
        start_date: start, end_date: end,
        initial_capital: initialCapital.value,
        symbols: effectiveStocks.length > 0 ? effectiveStocks : undefined,
        benchmark: benchmark.value || undefined,
        // v6.14: 不传 force_regime → 后端按 CSI500 历史动态判定 regime
      });
      if (res?.task_id) ids.push(res.task_id);
      msg.success(`组合回测已提交 (${selectedStrategyIds.value.length}个策略共享资金池)`);
    } catch (e: any) {
      msg.error("组合回测提交失败: " + (e?.message || e));
    }
  } else {
    // 单策略 → 现有路径
    for (const sid of selectedStrategyIds.value) {
      try {
        const strategyLabel = strategySelectOptions.value.find((s: any) => s.value === sid)?.label || sid;
        const res = await backtestAPI.createTask({
          name: `${strategyLabel}_回测_${start}`,
          strategy_id: sid, start_date: start, end_date: end,
          initial_capital: initialCapital.value,
          symbols: effectiveStocks,
          parameters: { benchmark: benchmark.value },
        });
        ids.push(res.task_id);
      } catch { /* skip */ }
    }
  }

  if (ids.length === 0) { msg.error("所有回测提交失败"); isRunning.value = false; return; }

  batchTaskIds.value = ids;
  startBatchPolling();
};

const loadResultDetails = async (taskId: string) => {
  resultLoading.value = true;
  try {
    const [equity, trades, result] = await Promise.all([
      backtestAPI.getEquityCurve(taskId).catch(() => []),
      backtestAPI.getTrades(taskId).catch(() => []),
      backtestAPI.getResult(taskId).catch(() => null),
    ]);
    const eq = Array.isArray(equity) ? equity : [];
    const tr = Array.isArray(trades) ? trades : [];
    const r: Record<string, any> = result || {};
    activeTaskId.value = taskId;
    activeTaskName.value = taskList.value.find((t: any) => t.task_id === taskId)?.name || taskId?.slice(0, 8) || "";
    activeSummary.value = {
      annualReturn: r.annual_return ?? 0,
      sharpeRatio: r.sharpe_ratio ?? 0,
      maxDrawdown: r.max_drawdown ?? 0,
      winRate: r.win_rate ?? 0,
      tradesCount: r.num_trades ?? 0,
    };
    benchmarkReturn.value = r.excess_metrics?.benchmark_annual_return ?? 0;
    activeEquityCurve.value = eq.map((p: any) => ({ date: p.trade_date || p.date, value: p.total_assets || p.equity || 0 }));
    activeBenchmark.value = (r.benchmark_curve || []).map((p: any) => ({ date: p.trade_date || p.date, value: p.total_assets || (p.cumulative_return ? (1 + p.cumulative_return) * 100000 : p.value || 0) }));
    activeDrawdown.value = (r.drawdown_curve || []).map((p: any) => ({ date: p.trade_date || p.date, value: p.drawdown || p.max_drawdown || 0 }));
    activeMonthlyReturns.value = (r.monthly_returns || []).map((p: any) => ({ month: p.month || p.trade_date || "", return: p.return || p.monthly_return || 0 }));
    activeDailyReturns.value = (r.daily_returns || []).map((p: any) => ({ trade_date: p.trade_date || p.date || "", daily_return: p.daily_return ?? 0, daily_pnl: p.daily_pnl ?? 0 }));
    activeDailyTurnover.value = (r.daily_turnover || []).map((p: any) => ({ trade_date: p.trade_date || p.date || "", turnover: p.turnover ?? 0 }));
    activeTrades.value = tr.map((t: any) => {
      const side = t.side || t.direction || '';
      const qty = Number(t.volume || t.quantity || 0);
      const px = Number(t.price || 0);
      return {
        id: t.id || t.trade_id,
        symbol: t.symbol || t.ts_code || '',
        name: t.symbol || t.ts_code || '',
        direction: (side === 'LONG' || side === 'buy') ? 'buy' : 'sell',
        date: t.datetime || t.trade_date || t.date || '',
        price: px,
        quantity: qty,
        amount: px * qty,
        fee: 0,
      };
    });
    // 标记有结果数据，驱动结果面板渲染（历史记录点击时 hasResults 为 false）
    hasResults.value = true;
  } catch { /* skip */ } finally { resultLoading.value = false; }
};

const loadHistoryResult = (h: HistoryItem) => { if (h.taskIds.length > 0) { activeCompareTaskId.value = h.taskIds[0]; loadResultDetails(h.taskIds[0]); } };

const exportViaApi = async () => {
  if (!activeCompareTaskId.value) return;
  try {
    const res = await backtestAPI.exportReport(activeCompareTaskId.value, 'json');
    const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `backtest_report_${activeCompareTaskId.value.slice(0,8)}.json`; a.click(); URL.revokeObjectURL(a.href);
    msg.success('报告已导出');
  } catch { msg.error('导出失败'); }
};

const exportCSV = () => {
  if (activeTrades.value.length === 0) { msg.info("无交易数据可导出"); return; }
  const h = "symbol,direction,date,price,quantity,amount,fee";
  const rows = activeTrades.value.map((t: any) => `${t.symbol},${t.direction},${t.date},${t.price},${t.quantity},${t.amount},${t.fee}`).join("\n");
  const blob = new Blob([h + "\n" + rows], { type: "text/csv" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "backtest_trades.csv"; a.click(); URL.revokeObjectURL(a.href);
};

// v3.3: 处理从快速回测跳转来的 task_id
const scenarioTaskFromUrl = ref('');
onMounted(async () => {
  await Promise.all([loadOptions(), loadTaskList()]);
  // 默认加载最近完成的回测结果
  const latest = taskList.value.find((t: any) => t.status === "completed");
  if (latest) loadResultDetails(latest.task_id);
});
</script>

<style lang="scss" scoped>
.backtest-workspace { height: 100%; overflow-y: auto; }
.workspace-body { display: flex; gap: 12px; padding: 10px 24px 24px; height: calc(100% - 90px); }
.config-pane { width: 300px; flex-shrink: 0; overflow-y: auto;
  h4 { margin: 0 0 6px; font-size: 13px; color: var(--color-text-secondary); }
}
.result-pane { flex: 1; overflow-y: auto; min-width: 0; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.section-hint { font-size: 11px; color: var(--color-text-tertiary); }
.help-icon { display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px; border-radius: 50%; background: rgba(255,255,255,0.12); color: var(--color-text-tertiary); font-size: 10px; cursor: help; margin-left: 4px; }

.strategy-card-list, .basket-list { max-height: 200px; overflow-y: auto; margin-bottom: 4px; }
.strategy-chip { display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; color: var(--color-text-secondary); transition: all 0.15s;
  &:hover { background: rgba(124,111,247,0.06); }
  &.selected { background: rgba(124,111,247,0.12); color: var(--color-primary, #7C3AED); font-weight: 500; }
  .chip-check { font-size: 13px; width: 16px; flex-shrink: 0; }
  .chip-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip-count { font-size: 10px; color: var(--color-text-tertiary); }
}

.chip-grid { display: flex; flex-wrap: wrap; gap: 4px; max-height: 180px; overflow-y: auto; margin-bottom: 4px; }
.mini-chip { padding: 3px 7px; border-radius: 3px; cursor: pointer; font-size: 11px; font-family: monospace; color: var(--color-text-secondary); background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.05); transition: all 0.15s;
  &:hover { border-color: rgba(124,111,247,0.3); }
  &.selected { background: rgba(124,111,247,0.15); border-color: var(--color-primary, #7C3AED); color: var(--color-primary, #7C3AED); font-weight: 500; }
}
.chip-summary { font-size: 11px; color: var(--color-text-tertiary); text-align: right; }

.metrics-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 12px; }
.metric-item { background: var(--color-bg-secondary, rgba(255,255,255,0.06)); border-radius: 6px; padding: 8px 6px; text-align: center;
  .metric-label { font-size: 10px; color: var(--color-text-tertiary); display: block; margin-bottom: 2px; }
  .metric-value { font-size: 15px; font-weight: 700; color: var(--color-text-primary); }
}

.compare-table { overflow-x: auto; margin-bottom: 12px;
  table { width: 100%; border-collapse: collapse; font-size: 12px;
    th, td { padding: 6px 8px; text-align: center; border-bottom: 1px solid var(--color-border, rgba(255,255,255,0.06)); white-space: nowrap; }
    th { font-weight: 600; color: var(--color-text-secondary); background: rgba(255,255,255,0.03); }
    td { color: var(--color-text-primary); }
  }
}
.chart-section { margin: 8px 0; }
.history-item { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.04); cursor: pointer; display: flex; justify-content: space-between;
  &:hover { background: rgba(255,255,255,0.04); }
  .h-label { font-size: 12px; color: var(--color-text-primary); }
  .h-time { font-size: 11px; color: var(--color-text-tertiary); }
}
.date-presets { display: flex; gap: 4px; margin-bottom: 6px; }
.date-row { margin-bottom: 8px; display: flex; }
.param-row { margin-bottom: 8px; display: flex; }
.run-btn { margin-top: 4px; }
.task-list { max-height: 260px; overflow-y: auto; }
.task-row { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.04); cursor: pointer; display: flex; flex-direction: column; gap: 4px; transition: all 0.15s;
  &:hover { background: rgba(124,111,247,0.06); }
  &.active { background: rgba(124,111,247,0.1); border-left: 3px solid var(--color-primary, #7C3AED); }
  .task-main { display: flex; align-items: center; gap: 8px; }
  .task-name { font-size: 12px; color: var(--color-text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .task-meta { font-size: 10px; color: var(--color-text-tertiary); }
  .task-actions { display: flex; gap: 4px; }
}
.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }
.metric-footnote { margin: 2px 0 10px; font-size: 12px; color: var(--color-text-tertiary); line-height: 1.6; }
</style>
